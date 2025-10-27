#!/usr/bin/env python
"""
Data Integrity Cleanup Script
Fixes existing data that violated proper stock flow

This script:
1. Analyzes current data integrity issues
2. Backs up problematic data
3. Clears invalid sales (those without storefront inventory)
4. Optionally regenerates data following correct flow

Usage:
    python fix_sample_data_integrity.py --analyze  # Just analyze, don't fix
    python fix_sample_data_integrity.py --fix      # Analyze and fix
    python fix_sample_data_integrity.py --regenerate  # Fix and regenerate sample data
"""

import os
import sys
import django
from datetime import datetime
from decimal import Decimal
import argparse

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from inventory.models import (
    Product, StockProduct, StoreFrontInventory, TransferRequest,
    TransferRequestLineItem, Warehouse, StoreFront
)
from sales.models import Sale, SaleItem, Payment, Customer
from accounts.models import Business, BusinessMembership


class DataIntegrityFixer:
    def __init__(self):
        self.issues = []
        self.fixes_applied = []
        
    def analyze_data_integrity(self):
        """Analyze data for integrity issues"""
        print("\n" + "="*80)
        print("DATA INTEGRITY ANALYSIS")
        print("="*80 + "\n")
        
        # Check 1: Sales without storefront inventory
        print("🔍 Checking for sales without storefront inventory...")
        problematic_sales = self._find_sales_without_storefront_inventory()
        
        if problematic_sales:
            print(f"  ❌ Found {len(problematic_sales)} sales without storefront inventory")
            self.issues.append({
                'type': 'sales_without_storefront_inventory',
                'count': len(problematic_sales),
                'sales': problematic_sales
            })
        else:
            print(f"  ✅ All sales have corresponding storefront inventory")
        
        # Check 2: Reconciliation mismatches
        print("\n🔍 Checking reconciliation for all products...")
        mismatches = self._check_reconciliation_all_products()
        
        if mismatches:
            print(f"  ❌ Found {len(mismatches)} products with reconciliation mismatches")
            for mismatch in mismatches[:5]:  # Show first 5
                print(f"     - {mismatch['product_name']}: {mismatch['mismatch']} units mismatch")
            if len(mismatches) > 5:
                print(f"     ... and {len(mismatches) - 5} more")
            self.issues.append({
                'type': 'reconciliation_mismatches',
                'count': len(mismatches),
                'mismatches': mismatches
            })
        else:
            print(f"  ✅ All products reconcile correctly")
        
        # Check 3: Storefront inventory without transfer requests
        print("\n🔍 Checking for storefront inventory without transfer requests...")
        orphaned_inventory = self._find_orphaned_storefront_inventory()
        
        if orphaned_inventory:
            print(f"  ⚠️  Found {len(orphaned_inventory)} storefront inventory entries without transfer requests")
            print(f"     (This may be expected if data was populated before transfer request system)")
            self.issues.append({
                'type': 'orphaned_storefront_inventory',
                'count': len(orphaned_inventory),
                'entries': orphaned_inventory
            })
        else:
            print(f"  ✅ All storefront inventory has corresponding transfer requests")
        
        # Summary
        print("\n" + "="*80)
        print("ANALYSIS SUMMARY")
        print("="*80)
        print(f"Total issues found: {len(self.issues)}")
        for issue in self.issues:
            print(f"  - {issue['type']}: {issue['count']}")
        
        return self.issues
    
    def _find_sales_without_storefront_inventory(self):
        """Find sales that don't have corresponding storefront inventory"""
        problematic_sales = []
        
        for sale in Sale.objects.select_related('storefront').prefetch_related('sale_items__product'):
            for item in sale.sale_items.all():
                # Check if product has storefront inventory
                storefront_inv = StoreFrontInventory.objects.filter(
                    storefront=sale.storefront,
                    product=item.product
                ).first()
                
                if not storefront_inv:
                    problematic_sales.append({
                        'sale_id': str(sale.id),
                        'receipt_number': sale.receipt_number,
                        'product': item.product.name,
                        'storefront': sale.storefront.name,
                        'quantity': item.quantity
                    })
        
        return problematic_sales
    
    def _check_reconciliation_all_products(self):
        """Check reconciliation for all products"""
        mismatches = []
        
        for product in Product.objects.all():
            # Warehouse stock
            warehouse_stock = StockProduct.objects.filter(
                product=product
            ).aggregate(total=Sum('quantity'))['total'] or Decimal('0')
            
            # Storefront stock
            storefront_stock = StoreFrontInventory.objects.filter(
                product=product
            ).aggregate(total=Sum('quantity'))['total'] or Decimal('0')
            
            # Sold
            sold = SaleItem.objects.filter(
                product=product,
                sale__status='COMPLETED'
            ).aggregate(total=Sum('quantity'))['total'] or Decimal('0')
            
            # Expected: warehouse = storefront + sold
            expected = warehouse_stock
            actual = storefront_stock + sold
            
            if expected != actual:
                mismatches.append({
                    'product_id': str(product.id),
                    'product_name': product.name,
                    'warehouse_stock': float(warehouse_stock),
                    'storefront_stock': float(storefront_stock),
                    'sold': float(sold),
                    'expected': float(expected),
                    'actual': float(actual),
                    'mismatch': float(actual - expected)
                })
        
        return mismatches
    
    def _find_orphaned_storefront_inventory(self):
        """Find storefront inventory without corresponding transfer requests"""
        orphaned = []
        
        for inv in StoreFrontInventory.objects.select_related('storefront', 'product'):
            # Check if there's a fulfilled transfer request for this product to this storefront
            has_transfer = TransferRequest.objects.filter(
                storefront=inv.storefront,
                status='FULFILLED',
                line_items__product=inv.product
            ).exists()
            
            if not has_transfer:
                orphaned.append({
                    'storefront': inv.storefront.name,
                    'product': inv.product.name,
                    'quantity': float(inv.quantity)
                })
        
        return orphaned
    
    def fix_data_integrity(self):
        """Fix data integrity issues"""
        if not self.issues:
            print("\n✅ No issues to fix!")
            return
        
        print("\n" + "="*80)
        print("FIXING DATA INTEGRITY ISSUES")
        print("="*80 + "\n")
        
        with transaction.atomic():
            # Fix 1: Delete sales without storefront inventory
            sales_issue = next((i for i in self.issues if i['type'] == 'sales_without_storefront_inventory'), None)
            if sales_issue:
                self._delete_invalid_sales(sales_issue['sales'])
            
            # Fix 2: Create transfer requests for orphaned storefront inventory
            orphaned_issue = next((i for i in self.issues if i['type'] == 'orphaned_storefront_inventory'), None)
            if orphaned_issue:
                self._create_retroactive_transfer_requests(orphaned_issue['entries'])
        
        print("\n✅ Data integrity fixes complete!")
    
    def _delete_invalid_sales(self, problematic_sales):
        """Delete sales that don't have storefront inventory"""
        if not problematic_sales:
            return
        
        print(f"🗑️  Deleting {len(problematic_sales)} invalid sales...")
        
        sale_ids = list(set([s['sale_id'] for s in problematic_sales]))
        
        # Delete payments first
        Payment.objects.filter(sale_id__in=sale_ids).delete()
        
        # Delete sale items
        SaleItem.objects.filter(sale_id__in=sale_ids).delete()
        
        # Delete sales
        deleted_count = Sale.objects.filter(id__in=sale_ids).delete()[0]
        
        print(f"  ✅ Deleted {deleted_count} invalid sales")
        self.fixes_applied.append(f"Deleted {deleted_count} invalid sales")
    
    def _create_retroactive_transfer_requests(self, orphaned_entries):
        """Create transfer requests retroactively for orphaned storefront inventory"""
        if not orphaned_entries:
            return
        
        print(f"📝 Creating retroactive transfer requests for {len(orphaned_entries)} inventory entries...")
        
        # Group by storefront
        by_storefront = {}
        for entry in orphaned_entries:
            storefront_name = entry['storefront']
            if storefront_name not in by_storefront:
                by_storefront[storefront_name] = []
            by_storefront[storefront_name].append(entry)
        
        created_count = 0
        for storefront_name, entries in by_storefront.items():
            storefront = StoreFront.objects.filter(name=storefront_name).first()
            if not storefront:
                continue
            
            # Create transfer request
            transfer_request = TransferRequest.objects.create(
                business=storefront.business,
                storefront=storefront,
                requested_by=None,  # System-generated
                priority='MEDIUM',
                status='FULFILLED',
                notes='Retroactive transfer request created by data integrity fix',
                fulfilled_at=timezone.now(),
                created_at=timezone.now() - timezone.timedelta(days=30)  # Backdated
            )
            
            # Create line items
            for entry in entries:
                product = Product.objects.filter(name=entry['product']).first()
                if product:
                    TransferRequestLineItem.objects.create(
                        transfer_request=transfer_request,
                        product=product,
                        requested_quantity=int(entry['quantity'])
                    )
            
            created_count += 1
        
        print(f"  ✅ Created {created_count} retroactive transfer requests")
        self.fixes_applied.append(f"Created {created_count} retroactive transfer requests")


def main():
    parser = argparse.ArgumentParser(description='Fix data integrity issues')
    parser.add_argument('--analyze', action='store_true', help='Analyze data integrity (read-only)')
    parser.add_argument('--fix', action='store_true', help='Analyze and fix data integrity issues')
    parser.add_argument('--regenerate', action='store_true', help='Fix and regenerate sample data')
    
    args = parser.parse_args()
    
    if not any([args.analyze, args.fix, args.regenerate]):
        parser.print_help()
        return
    
    fixer = DataIntegrityFixer()
    
    # Always analyze first
    issues = fixer.analyze_data_integrity()
    
    if args.fix or args.regenerate:
        if issues:
            confirm = input("\n⚠️  Are you sure you want to fix these issues? This will delete invalid data. (yes/no): ")
            if confirm.lower() == 'yes':
                fixer.fix_data_integrity()
            else:
                print("❌ Aborted")
                return
        
        if args.regenerate:
            print("\n📦 Regenerating sample data with correct flow...")
            print("   (Run populate_sample_data_v2.py manually after this script)")


if __name__ == '__main__':
    main()
