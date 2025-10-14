#!/usr/bin/env python
"""
Subtotal Integrity Verification Script

Verifies that all Sale.subtotal values match the calculated sum of their SaleItems.
This script can be run periodically to ensure data integrity.

Usage:
    python scripts/verify_subtotal_integrity.py
    
    # With auto-fix:
    python scripts/verify_subtotal_integrity.py --fix
"""

import os
import sys
import django
from decimal import Decimal

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from sales.models import Sale
from django.db.models import Sum


def verify_subtotal_integrity(fix=False):
    """
    Verify all sale subtotals match calculated values
    
    Args:
        fix: If True, automatically fix mismatches
        
    Returns:
        tuple: (issues_found, issues_fixed)
    """
    print("=" * 80)
    print("SUBTOTAL INTEGRITY VERIFICATION")
    print("=" * 80)
    print()
    
    issues = []
    fixed = 0
    
    # Get all sales
    total_sales = Sale.objects.count()
    print(f"📊 Checking {total_sales} sales...")
    print()
    
    for idx, sale in enumerate(Sale.objects.all(), 1):
        if idx % 100 == 0:
            print(f"  Progress: {idx}/{total_sales} sales checked...")
        
        # Calculate subtotal from sale items
        calculated = sale.sale_items.aggregate(
            total=Sum('total_price')
        )['total'] or Decimal('0.00')
        
        # Compare with stored value
        if sale.subtotal != calculated:
            difference = sale.subtotal - calculated
            issue = {
                'sale_id': str(sale.id),
                'receipt': sale.receipt_number or 'N/A',
                'status': sale.status,
                'stored_subtotal': float(sale.subtotal),
                'calculated_subtotal': float(calculated),
                'difference': float(difference),
                'items_count': sale.sale_items.count()
            }
            issues.append(issue)
            
            # Auto-fix if requested
            if fix:
                sale.calculate_totals()
                sale.save()
                fixed += 1
    
    print()
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print()
    
    if not issues:
        print("✅ SUCCESS: All sale subtotals are correct!")
        print(f"   Verified {total_sales} sales - no issues found.")
    else:
        print(f"⚠️  WARNING: Found {len(issues)} sales with mismatched subtotals")
        print()
        print("Issues Details:")
        print("-" * 80)
        
        for issue in issues[:10]:  # Show first 10
            print(f"  Receipt: {issue['receipt']}")
            print(f"  Status: {issue['status']}")
            print(f"  Stored:     ${issue['stored_subtotal']:,.2f}")
            print(f"  Calculated: ${issue['calculated_subtotal']:,.2f}")
            print(f"  Difference: ${issue['difference']:,.2f}")
            print(f"  Items: {issue['items_count']}")
            print()
        
        if len(issues) > 10:
            print(f"  ... and {len(issues) - 10} more issues")
            print()
        
        if fix:
            print(f"✅ FIXED: {fixed} sales updated with correct subtotals")
        else:
            print()
            print("💡 TIP: Run with --fix flag to automatically correct these issues:")
            print("   python scripts/verify_subtotal_integrity.py --fix")
    
    print()
    print("=" * 80)
    
    return issues, fixed


def main():
    """Main execution"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Verify sale subtotal integrity')
    parser.add_argument(
        '--fix',
        action='store_true',
        help='Automatically fix any mismatches found'
    )
    
    args = parser.parse_args()
    
    issues, fixed = verify_subtotal_integrity(fix=args.fix)
    
    # Exit with error code if issues found (and not fixed)
    if issues and not args.fix:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
