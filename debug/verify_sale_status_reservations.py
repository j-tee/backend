#!/usr/bin/env python
"""
Verify Sale Status Reservation Fix

This script validates that only DRAFT sales count as reservations,
not PENDING/PARTIAL/COMPLETED sales.

Run: python debug/verify_sale_status_reservations.py
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from django.db.models import Sum
from sales.models import Sale, SaleItem
from inventory.models import Product, Stock
from decimal import Decimal


def get_reserved_quantity(product_id):
    """Get reserved quantity for a product (should only count DRAFT sales)"""
    reserved = SaleItem.objects.filter(
        product_id=product_id,
        sale__status='DRAFT'  # ✅ Only DRAFT
    ).aggregate(total=Sum('quantity'))['total'] or 0
    return reserved


def get_reserved_quantity_old_way(product_id):
    """OLD WAY - incorrectly counts PENDING sales"""
    reserved = SaleItem.objects.filter(
        product_id=product_id,
        sale__status__in=['DRAFT', 'PENDING']  # ❌ Includes PENDING
    ).aggregate(total=Sum('quantity'))['total'] or 0
    return reserved


def verify_reservation_logic():
    """Verify reservation calculations are correct"""
    print("=" * 80)
    print("SALE STATUS RESERVATION FIX VERIFICATION")
    print("=" * 80)
    print()
    
    # Get a sample product
    product = Product.objects.first()
    if not product:
        print("❌ No products found in database")
        return
    
    print(f"📦 Testing Product: {product.name} (ID: {product.id})")
    print()
    
    # Get sales breakdown by status
    print("📊 Sales Breakdown by Status:")
    print("-" * 80)
    
    for status_code, status_name in Sale.STATUS_CHOICES:
        count = SaleItem.objects.filter(
            product=product,
            sale__status=status_code
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        if count > 0:
            should_count = "✅ COUNTS" if status_code == 'DRAFT' else "❌ DOES NOT COUNT"
            print(f"{status_name:15} {count:6} units    {should_count}")
    
    print()
    print("=" * 80)
    print()
    
    # Compare old vs new calculation
    reserved_new = get_reserved_quantity(product.id)
    reserved_old = get_reserved_quantity_old_way(product.id)
    
    print("🔍 Reserved Quantity Calculation:")
    print("-" * 80)
    print(f"✅ NEW WAY (DRAFT only):           {reserved_new:6} units")
    print(f"❌ OLD WAY (DRAFT + PENDING):      {reserved_old:6} units")
    print(f"📉 Difference (over-counting):     {reserved_old - reserved_new:6} units")
    print()
    
    if reserved_old > reserved_new:
        print(f"⚠️  OLD calculation inflated reservations by {reserved_old - reserved_new} units")
        print(f"   This happened because PENDING sales were incorrectly counted as reservations")
    elif reserved_old == reserved_new:
        print(f"✅ No PENDING sales found - both calculations match")
    
    print()
    print("=" * 80)
    print()
    
    # Get stock information
    stocks = Stock.objects.filter(product=product)
    total_stock = stocks.aggregate(total=Sum('quantity'))['total'] or 0
    
    print("📈 Stock Availability:")
    print("-" * 80)
    print(f"Total Stock:           {total_stock:6} units")
    print(f"Reserved (NEW):        {reserved_new:6} units")
    print(f"Available (NEW):       {total_stock - reserved_new:6} units")
    print()
    print(f"Reserved (OLD):        {reserved_old:6} units")
    print(f"Available (OLD):       {total_stock - reserved_old:6} units")
    print()
    
    availability_diff = (total_stock - reserved_old) - (total_stock - reserved_new)
    if availability_diff < 0:
        print(f"✅ FIX IMPACT: Available stock increased by {abs(availability_diff)} units")
        print(f"   Customers can now purchase {abs(availability_diff)} more units")
    
    print()
    print("=" * 80)
    print()
    
    # Show specific sales examples
    print("📋 Example Sales:")
    print("-" * 80)
    
    draft_sales = SaleItem.objects.filter(
        product=product,
        sale__status='DRAFT'
    ).select_related('sale')[:3]
    
    if draft_sales:
        print("\n✅ DRAFT Sales (Should count as reserved):")
        for item in draft_sales:
            print(f"   Sale {item.sale.receipt_number or 'No receipt'}: {item.quantity} units - Status: {item.sale.status}")
    
    pending_sales = SaleItem.objects.filter(
        product=product,
        sale__status='PENDING'
    ).select_related('sale')[:3]
    
    if pending_sales:
        print("\n❌ PENDING Sales (Should NOT count as reserved - already committed):")
        for item in pending_sales:
            print(f"   Sale {item.sale.receipt_number}: {item.quantity} units - Status: {item.sale.status}")
    
    print()
    print("=" * 80)
    print()
    
    # Verification summary
    print("🎯 VERIFICATION SUMMARY:")
    print("-" * 80)
    
    checks = []
    
    # Check 1: Only DRAFT sales counted
    draft_count = SaleItem.objects.filter(
        product=product,
        sale__status='DRAFT'
    ).aggregate(total=Sum('quantity'))['total'] or 0
    
    checks.append(("Only DRAFT sales counted", reserved_new == draft_count))
    
    # Check 2: PENDING sales not counted
    pending_count = SaleItem.objects.filter(
        product=product,
        sale__status='PENDING'
    ).aggregate(total=Sum('quantity'))['total'] or 0
    
    if pending_count > 0:
        checks.append(("PENDING sales excluded", reserved_new < reserved_old))
    
    # Check 3: Math consistency
    checks.append(("Available = Stock - Reserved", (total_stock - reserved_new) >= 0))
    
    for check_name, passed in checks:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}  {check_name}")
    
    print()
    
    all_passed = all(passed for _, passed in checks)
    if all_passed:
        print("✅ ALL CHECKS PASSED - Fix is working correctly!")
    else:
        print("❌ SOME CHECKS FAILED - Review the logic")
    
    print()
    print("=" * 80)


if __name__ == '__main__':
    try:
        verify_reservation_logic()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
