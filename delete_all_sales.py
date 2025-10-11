#!/usr/bin/env python
"""
Script to remove ONLY sales data from the database.
This will delete:
- All Sale records
- All SaleItem records
- All Payment records linked to sales
- All CustomerCredit records

This will KEEP:
- Warehouse stock (StockProduct)
- Storefront inventory (StoreFrontInventory)
- Transfer requests
- Products, Categories, Suppliers
- Customers
- Users, Businesses, etc.
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from django.db import transaction
from sales.models import Sale, SaleItem, Payment, CreditTransaction

def delete_all_sales_data():
    """Delete all sales-related data from the database."""
    
    print("\n" + "="*80)
    print("🗑️  DELETE ALL SALES DATA")
    print("="*80)
    
    # Count records before deletion
    sales_count = Sale.objects.count()
    sale_items_count = SaleItem.objects.count()
    payments_count = Payment.objects.count()
    credits_count = CreditTransaction.objects.count()
    
    print(f"\n📊 Current Database State:")
    print(f"   Sales: {sales_count}")
    print(f"   Sale Items: {sale_items_count}")
    print(f"   Payments: {payments_count}")
    print(f"   Credit Transactions: {credits_count}")
    
    if sales_count == 0 and sale_items_count == 0 and payments_count == 0:
        print("\n✅ No sales data found. Database is already clean.")
        return
    
    # Confirm deletion
    print("\n⚠️  WARNING: This will DELETE all sales data!")
    print("   The following will be removed:")
    print(f"   • {sales_count} sales")
    print(f"   • {sale_items_count} sale items")
    print(f"   • {payments_count} payments")
    print(f"   • {credits_count} credit transactions")
    print("\n   This action CANNOT be undone!")
    
    response = input("\n❓ Are you sure you want to continue? (yes/no): ").strip().lower()
    
    if response != 'yes':
        print("\n❌ Operation cancelled.")
        sys.exit(0)
    
    # Double confirmation
    response2 = input("❓ Type 'DELETE' to confirm: ").strip()
    
    if response2 != 'DELETE':
        print("\n❌ Operation cancelled.")
        sys.exit(0)
    
    print("\n🔄 Deleting sales data...")
    
    with transaction.atomic():
        # Delete in correct order to avoid foreign key issues
        
        # 1. Delete SaleItems first (they reference Sales)
        print(f"   Deleting {sale_items_count} sale items...")
        deleted_items = SaleItem.objects.all().delete()
        print(f"   ✅ Deleted {deleted_items[0]} sale items")
        
        # 2. Delete Payments (they reference Sales)
        print(f"   Deleting {payments_count} payments...")
        deleted_payments = Payment.objects.all().delete()
        print(f"   ✅ Deleted {deleted_payments[0]} payments")
        
        # 3. Delete CreditTransaction records
        print(f"   Deleting {credits_count} credit transactions...")
        deleted_credits = CreditTransaction.objects.all().delete()
        print(f"   ✅ Deleted {deleted_credits[0]} credit transactions")
        
        # 4. Delete Sales
        print(f"   Deleting {sales_count} sales...")
        deleted_sales = Sale.objects.all().delete()
        print(f"   ✅ Deleted {deleted_sales[0]} sales")
    
    print("\n" + "="*80)
    print("✅ ALL SALES DATA DELETED SUCCESSFULLY")
    print("="*80)
    
    # Verify deletion
    print("\n📊 Database State After Deletion:")
    print(f"   Sales: {Sale.objects.count()}")
    print(f"   Sale Items: {SaleItem.objects.count()}")
    print(f"   Payments: {Payment.objects.count()}")
    print(f"   Credit Transactions: {CreditTransaction.objects.count()}")
    
    # Show what remains
    from inventory.models import StockProduct, Product, TransferRequest
    from sales.models import StoreFrontInventory, StoreFront
    
    print("\n📦 Remaining Data (Untouched):")
    print(f"   Products: {Product.objects.count()}")
    print(f"   Warehouse Stock: {StockProduct.objects.count()}")
    print(f"   Storefronts: {StoreFront.objects.count()}")
    print(f"   Storefront Inventory: {StoreFrontInventory.objects.count()}")
    print(f"   Transfer Requests: {TransferRequest.objects.count()}")
    
    print("\n✅ Sales data removed. All other data preserved.")
    print("="*80 + "\n")

if __name__ == '__main__':
    delete_all_sales_data()
