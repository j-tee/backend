#!/usr/bin/env python
"""
Quick script to create transfer requests and fulfill them for existing warehouse stock.
This will populate storefronts with inventory so sales can be made.
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from django.utils import timezone
from django.db import transaction
from django.db.models import Sum
from inventory.models import StockProduct, Product, TransferRequest, TransferRequestLineItem
from sales.models import StoreFront, StoreFrontInventory, SaleItem
from accounts.models import User
from datetime import datetime, timedelta
import random

def create_storefront_inventory():
    """Create transfer requests and fulfill them to populate storefronts"""
    
    print("\n" + "="*80)
    print("📦 CREATING STOREFRONT INVENTORY")
    print("="*80)
    
    # Get the first user (admin/manager)
    user = User.objects.filter(is_superuser=True).first()
    if not user:
        user = User.objects.first()
    
    if not user:
        print("❌ No users found. Please create a user first.")
        sys.exit(1)
    
    # Get storefronts
    storefronts = list(StoreFront.objects.all())
    if not storefronts:
        print("❌ No storefronts found. Please create storefronts first.")
        sys.exit(1)
    
    print(f"✅ Found {len(storefronts)} storefronts:")
    for sf in storefronts:
        print(f"   - {sf.name}")
    
    # Get all warehouse stock
    stock_products = StockProduct.objects.select_related(
        'product', 'warehouse'
    ).filter(quantity__gt=0)
    
    if not stock_products:
        print("❌ No warehouse stock found. Please populate warehouse stock first.")
        sys.exit(1)
    
    print(f"✅ Found {stock_products.count()} stock items in warehouse")
    
    # Group stock by product
    from collections import defaultdict
    stock_by_product = defaultdict(list)
    for sp in stock_products:
        stock_by_product[sp.product_id].append(sp)
    
    print(f"✅ {len(stock_by_product)} unique products")
    
    transfer_count = 0
    items_transferred = 0
    
    with transaction.atomic():
        # For each product, create transfer requests to move stock to storefronts
        for product_id, stock_list in stock_by_product.items():
            product = stock_list[0].product
            
            # Get storefronts for this product's business
            product_storefronts = [sf for sf in storefronts 
                                  if sf.business_link and sf.business_link.business_id == product.business_id]
            
            if not product_storefronts:
                print(f"   ⚠️  No storefronts found for {product.name} (Business: {product.business.name})")
                continue
            
            # Calculate AVAILABLE quantity (not just total warehouse quantity)
            # Available = Total Warehouse Quantity - Already Sold - Already Transferred
            
            total_warehouse_qty = sum(sp.quantity for sp in stock_list)
            
            # Check how much has already been sold
            sold_qty = SaleItem.objects.filter(
                product=product,
                sale__status='COMPLETED'
            ).aggregate(total=Sum('quantity'))['total'] or 0
            
            # Check how much has already been transferred to storefronts
            transferred_qty = StoreFrontInventory.objects.filter(
                product=product
            ).aggregate(total=Sum('quantity'))['total'] or 0
            
            available_qty = total_warehouse_qty - sold_qty - transferred_qty
            available_qty = int(available_qty)  # Convert Decimal to int
            
            if available_qty <= 0:
                print(f"   ⚠️  No available stock for {product.name} (Warehouse: {total_warehouse_qty}, Sold: {sold_qty}, Transferred: {transferred_qty})")
                continue
            
            # Only transfer 50-70% of available stock (leave some in warehouse)
            transfer_percentage = random.uniform(0.5, 0.7)
            total_to_transfer = int(available_qty * transfer_percentage)
            
            if total_to_transfer == 0:
                continue
            
            # Pick one storefront randomly for this product (simpler approach)
            storefront = random.choice(product_storefronts)
            qty_to_transfer = total_to_transfer
            
            # Create transfer request
            transfer_request = TransferRequest.objects.create(
                business=product.business,
                storefront=storefront,
                requested_by=user,
                status='NEW',
                notes=f'Initial stock transfer for {product.name}'
            )
            
            # Add line item
            TransferRequestLineItem.objects.create(
                request=transfer_request,
                product=product,
                requested_quantity=qty_to_transfer
            )
            
            # Mark as fulfilled FIRST (this triggers validation signal)
            transfer_request.status = 'FULFILLED'
            transfer_request.fulfilled_by = user
            fulfillment_date = timezone.now() - timedelta(days=random.randint(1, 15))
            transfer_request.fulfilled_at = fulfillment_date
            transfer_request.save()  # This triggers validation
            
            # NOW fulfill the request (this creates StoreFrontInventory)
            transfer_request.apply_manual_inventory_fulfillment()
            
            transfer_count += 1
            items_transferred += qty_to_transfer
            
            print(f"   📦 {product.name}: {qty_to_transfer} units → {storefront.name}")
    
    # Verify storefront inventory was created
    storefront_inv_count = StoreFrontInventory.objects.count()
    
    print("\n" + "="*80)
    print("✅ TRANSFER REQUESTS COMPLETED")
    print("="*80)
    print(f"📊 Transfer Requests Created: {transfer_count}")
    print(f"📊 Total Items Transferred: {items_transferred}")
    print(f"📊 Storefront Inventory Records: {storefront_inv_count}")
    
    # Show inventory by storefront
    print("\n📋 Inventory by Storefront:")
    for storefront in storefronts:
        inv_items = StoreFrontInventory.objects.filter(storefront=storefront)
        total_units = sum(item.quantity for item in inv_items)
        print(f"   {storefront.name}: {inv_items.count()} products, {total_units} total units")
    
    print("\n✅ Storefronts are now ready for sales!")
    print("="*80 + "\n")

if __name__ == '__main__':
    create_storefront_inventory()
