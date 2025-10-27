#!/usr/bin/env python
"""
Add Shared Products to Both Storefronts
Creates transfer requests to move some products to both locations for testing
"""
import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from inventory.models import StoreFront, Product, TransferRequest, TransferRequestLineItem
from sales.models import StoreFrontInventory
from django.contrib.auth import get_user_model
from django.db import transaction

User = get_user_model()


def create_shared_inventory():
    """Create transfer requests to add shared products to both storefronts"""
    
    print("\n" + "="*80)
    print("CREATING SHARED PRODUCTS FOR BOTH STOREFRONTS")
    print("="*80)
    
    # Get storefronts
    adenta = StoreFront.objects.filter(name='Adenta Store').first()
    cow_lane = StoreFront.objects.filter(name='Cow Lane Store').first()
    
    if not (adenta and cow_lane):
        print("❌ Error: Could not find both storefronts")
        return
    
    print(f"\n✅ Found storefronts:")
    print(f"   - {adenta.name}")
    print(f"   - {cow_lane.name}")
    
    # Get user
    user = User.objects.filter(is_superuser=True).first() or User.objects.first()
    if not user:
        print("❌ Error: No user found")
        return
    
    print(f"\n✅ Using user: {user.name}")
    
    # Products to share:
    # - Move some Adenta products to Cow Lane
    # - Move some Cow Lane products to Adenta
    
    transfers_to_create = [
        # Transfer Adenta products to Cow Lane
        (adenta, cow_lane, 'BEV-0001', 100, 'Coca Cola to Cow Lane'),  # Coca Cola
        (adenta, cow_lane, 'ELEC-0005', 10, 'Samsung TV to Cow Lane'),  # Samsung TV
        
        # Transfer Cow Lane products to Adenta
        (cow_lane, adenta, 'ELEC-0003', 20, 'HP Laptop to Adenta'),  # HP Laptop
        (cow_lane, adenta, 'FOOD-0002', 50, 'Cooking Oil to Adenta'),  # Cooking Oil
    ]
    
    print(f"\n📦 Creating {len(transfers_to_create)} transfer requests...")
    
    created_count = 0
    
    with transaction.atomic():
        for source_sf, dest_sf, sku, qty, notes in transfers_to_create:
            # Get the product
            product = Product.objects.filter(sku=sku).first()
            if not product:
                print(f"   ⚠️  Product {sku} not found, skipping...")
                continue
            
            # Check if product exists in source storefront
            source_inv = StoreFrontInventory.objects.filter(
                storefront=source_sf,
                product=product
            ).first()
            
            if not source_inv or source_inv.quantity < qty:
                available = source_inv.quantity if source_inv else 0
                print(f"   ⚠️  Insufficient inventory in {source_sf.name} for {sku}")
                print(f"      Need: {qty}, Available: {available}")
                continue
            
            # Check if product already exists in destination
            dest_inv = StoreFrontInventory.objects.filter(
                storefront=dest_sf,
                product=product
            ).first()
            
            if dest_inv and dest_inv.quantity > 0:
                print(f"   ℹ️  {sku} already exists in {dest_sf.name} ({dest_inv.quantity} units)")
                continue
            
            # Create transfer request (from dest storefront's perspective)
            transfer_request = TransferRequest.objects.create(
                business=dest_sf.business_link.business,
                storefront=dest_sf,
                requested_by=user,
                priority='MEDIUM',
                status='NEW',
                notes=notes
            )
            
            # Create line item
            TransferRequestLineItem.objects.create(
                request=transfer_request,
                product=product,
                requested_quantity=qty
            )
            
            # Fulfill the request
            transfer_request.apply_manual_inventory_fulfillment()
            transfer_request.status = 'FULFILLED'
            transfer_request.fulfilled_by = user
            transfer_request.save(update_fields=['status', 'fulfilled_by', 'updated_at'])
            
            # Update source storefront inventory (remove from source)
            source_inv.quantity -= qty
            source_inv.save()
            
            print(f"   ✅ Transferred {qty} units of {product.name} ({sku})")
            print(f"      From: {source_sf.name} → To: {dest_sf.name}")
            
            created_count += 1
    
    print(f"\n" + "="*80)
    print(f"✅ COMPLETED: {created_count} transfers created")
    print("="*80)
    
    # Show updated inventory
    print(f"\n📋 Updated Inventory:")
    
    for sf in [adenta, cow_lane]:
        inv = StoreFrontInventory.objects.filter(
            storefront=sf,
            quantity__gt=0
        ).select_related('product')
        
        print(f"\n{sf.name}: {inv.count()} products")
        for item in inv[:10]:
            print(f"  - {item.product.sku}: {item.product.name} ({item.quantity} units)")
        if inv.count() > 10:
            print(f"  ... and {inv.count() - 10} more")
    
    # Show overlap
    adenta_skus = set(StoreFrontInventory.objects.filter(
        storefront=adenta,
        quantity__gt=0
    ).values_list('product__sku', flat=True))
    
    cow_lane_skus = set(StoreFrontInventory.objects.filter(
        storefront=cow_lane,
        quantity__gt=0
    ).values_list('product__sku', flat=True))
    
    overlap = adenta_skus & cow_lane_skus
    
    print(f"\n" + "="*80)
    print(f"📊 OVERLAP ANALYSIS")
    print("="*80)
    print(f"Adenta Store: {len(adenta_skus)} products")
    print(f"Cow Lane Store: {len(cow_lane_skus)} products")
    print(f"Shared products: {len(overlap)}")
    
    if overlap:
        print(f"\nShared SKUs:")
        for sku in sorted(overlap):
            product = Product.objects.get(sku=sku)
            adenta_qty = StoreFrontInventory.objects.get(
                storefront=adenta, product=product
            ).quantity
            cow_lane_qty = StoreFrontInventory.objects.get(
                storefront=cow_lane, product=product
            ).quantity
            print(f"  - {sku}: {product.name}")
            print(f"    Adenta: {adenta_qty} units | Cow Lane: {cow_lane_qty} units")
    
    print(f"\n✅ You can now test searching for shared products in both storefronts!")
    print("="*80 + "\n")


if __name__ == '__main__':
    create_shared_inventory()
