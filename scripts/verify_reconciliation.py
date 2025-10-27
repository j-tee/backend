#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from sales.models import StoreFrontInventory
from inventory.models import Product, StockProduct
from sales.models import SaleItem

# Check Samsung TV reconciliation
tv = Product.objects.filter(name__icontains='Samsung TV').first()

if tv:
    # Get stock data
    stock_products = StockProduct.objects.filter(product=tv)
    total_warehouse = sum(sp.quantity for sp in stock_products)
    
    # Get storefront data
    storefront_inv = StoreFrontInventory.objects.filter(product=tv)
    total_storefront = sum(inv.quantity for inv in storefront_inv)
    
    # Get sales data
    sold = SaleItem.objects.filter(
        product=tv,
        sale__status='COMPLETED'
    ).count()
    
    print("\n" + "="*60)
    print("SAMSUNG TV 43\" RECONCILIATION CHECK")
    print("="*60)
    print(f"\nProduct: {tv.name}")
    print(f"SKU: {tv.sku}")
    
    print(f"\n📦 Warehouse Stock:")
    for sp in stock_products:
        print(f"   Batch: {sp.quantity} units (Warehouse: {sp.warehouse.name if sp.warehouse else 'N/A'})")
    print(f"   Total: {total_warehouse} units")
    
    print(f"\n🏪 Storefront Inventory:")
    for inv in storefront_inv:
        print(f"   {inv.storefront.name}: {inv.quantity} units")
    print(f"   Total: {total_storefront} units")
    
    print(f"\n💰 Sales:")
    print(f"   Sold: {sold} units")
    
    print(f"\n🧮 Reconciliation:")
    print(f"   Warehouse: {total_warehouse} units")
    print(f"   Storefront: {total_storefront} units")
    print(f"   Sold: {sold} units")
    print(f"   Formula: warehouse - storefront + sold")
    
    # Calculate based on backend formula
    # warehouse_on_hand = total_warehouse - total_storefront
    warehouse_on_hand = total_warehouse - total_storefront
    calculated_baseline = warehouse_on_hand + total_storefront - sold
    
    print(f"\n   Warehouse on hand: {total_warehouse} - {total_storefront} = {warehouse_on_hand}")
    print(f"   Calculated baseline: {warehouse_on_hand} + {total_storefront} - {sold} = {calculated_baseline}")
    print(f"   Recorded batch: {total_warehouse}")
    print(f"   Delta: {total_warehouse} - {calculated_baseline} = {total_warehouse - calculated_baseline}")
    
    if total_warehouse == calculated_baseline:
        print(f"\n   ✅ RECONCILIATION BALANCED!")
    else:
        print(f"\n   ⚠️  MISMATCH: {abs(total_warehouse - calculated_baseline)} units")
    
    print("="*60 + "\n")
