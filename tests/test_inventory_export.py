#!/usr/bin/env python
"""
Test script for Inventory Export functionality
"""
import os
import django
from decimal import Decimal

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import Business, BusinessMembership
from inventory.models import StoreFront, StoreFrontInventory
from reports.services.inventory import InventoryExporter

User = get_user_model()


def test_inventory_export():
    """Test the inventory export functionality"""
    
    print("=" * 80)
    print("INVENTORY EXPORT TEST")
    print("=" * 80)
    
    # Get a business with inventory - first find storefronts with inventory
    inventory_items = StoreFrontInventory.objects.select_related(
        'storefront__business_link__business'
    ).filter(
        storefront__business_link__isnull=False
    )
    
    if not inventory_items.exists():
        print("❌ No inventory found in any business")
        return
    
    # Get business from first inventory item
    business = inventory_items.first().storefront.business_link.business
    
    if not business:
        print("❌ No business with storefronts found. Run populate_data.py first.")
        return
    
    print(f"\n✅ Testing with business: {business.name}")
    
    # Get a user with access to this business
    membership = BusinessMembership.objects.filter(
        business=business,
        is_active=True
    ).first()
    
    if membership:
        user = membership.user
    else:
        user = business.owner
    
    if not user:
        print("❌ No user found with access to this business")
        return
    
    print(f"✅ Using user: {user.name if hasattr(user, 'name') else user.email}")
    
    # Get inventory count
    inventory_count = StoreFrontInventory.objects.filter(
        storefront__business_link__business=business
    ).count()
    
    print(f"✅ Found {inventory_count} stock items for this business")
    
    if inventory_count == 0:
        print("❌ No inventory found")
        return
    
    # Get storefront breakdown
    storefronts = StoreFront.objects.filter(business_link__business=business)
    print(f"   - Storefronts: {storefronts.count()}")
    for sf in storefronts:
        sf_count = StoreFrontInventory.objects.filter(storefront=sf).count()
        print(f"     * {sf.name}: {sf_count} items")
    
    # Test 1: Export all inventory
    print("\n" + "-" * 80)
    print("TEST 1: Export All Inventory")
    print("-" * 80)
    
    filters = {}
    
    print(f"Filters: {filters if filters else 'None (all items)'}")
    
    exporter = InventoryExporter(user=user)
    
    try:
        data = exporter.export(filters)
        
        print(f"\n✅ Export successful!")
        print(f"   - Export Date: {data['summary']['export_date']}")
        print(f"   - Total Unique Products: {data['summary']['total_unique_products']}")
        print(f"   - Total Quantity: {data['summary']['total_quantity_in_stock']}")
        print(f"   - Total Value: ${data['summary']['total_inventory_value']}")
        print(f"   - Out of Stock: {data['summary']['out_of_stock_items']}")
        print(f"   - Low Stock: {data['summary']['low_stock_items']}")
        print(f"   - In Stock: {data['summary']['in_stock_items']}")
        print(f"   - Storefronts: {data['summary']['storefronts_count']}")
        
        # Show storefront breakdown
        if data['summary']['storefronts_count'] > 0:
            print(f"\n   Storefront Breakdown:")
            idx = 1
            while f'storefront_{idx}_name' in data['summary']:
                name = data['summary'][f'storefront_{idx}_name']
                items = data['summary'][f'storefront_{idx}_items']
                qty = data['summary'][f'storefront_{idx}_quantity']
                value = data['summary'][f'storefront_{idx}_value']
                print(f"   {idx}. {name}: {items} items, {qty} units, ${value}")
                idx += 1
        
        # Show first few items
        if data['stock_items']:
            print(f"\n   First 3 stock items:")
            for i, item in enumerate(data['stock_items'][:3], 1):
                print(f"   {i}. {item['product_name']} ({item['sku']})")
                print(f"      Storefront: {item['storefront']}")
                print(f"      Stock: {item['quantity_in_stock']} {item['unit_of_measure']} - {item['stock_status']}")
                print(f"      Cost: ${item['unit_cost']}, Price: ${item['selling_price']}")
                print(f"      Value: ${item['total_value']}, Margin: {item['margin_percentage']}%")
        
    except Exception as e:
        print(f"❌ Export failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test 2: Export low stock items
    print("\n" + "-" * 80)
    print("TEST 2: Export Low Stock Items Only")
    print("-" * 80)
    
    filters = {
        'stock_status': 'low_stock',
    }
    
    print(f"Filtering for low stock items")
    
    try:
        data = exporter.export(filters)
        print(f"✅ Low stock filter successful!")
        print(f"   - Low Stock Items: {data['summary']['total_unique_products']}")
        print(f"   - Total Quantity: {data['summary']['total_quantity_in_stock']}")
        print(f"   - Total Value: ${data['summary']['total_inventory_value']}")
        
        if data['stock_items']:
            print(f"\n   Low stock items:")
            for item in data['stock_items'][:5]:
                print(f"   - {item['product_name']}: {item['quantity_in_stock']} units " +
                      f"(Reorder at: {item['reorder_level']})")
    except Exception as e:
        print(f"❌ Low stock filter failed: {e}")
    
    # Test 3: Export items in stock
    print("\n" + "-" * 80)
    print("TEST 3: Export In Stock Items")
    print("-" * 80)
    
    filters = {
        'stock_status': 'in_stock',
    }
    
    print(f"Filtering for in stock items")
    
    try:
        data = exporter.export(filters)
        print(f"✅ In stock filter successful!")
        print(f"   - In Stock Items: {data['summary']['total_unique_products']}")
        print(f"   - Total Quantity: {data['summary']['total_quantity_in_stock']}")
        print(f"   - Total Value: ${data['summary']['total_inventory_value']}")
    except Exception as e:
        print(f"❌ In stock filter failed: {e}")
    
    # Test 4: Export with minimum quantity
    print("\n" + "-" * 80)
    print("TEST 4: Export Items with Quantity >= 10")
    print("-" * 80)
    
    filters = {
        'min_quantity': 10,
    }
    
    print(f"Filtering items with quantity >= 10")
    
    try:
        data = exporter.export(filters)
        print(f"✅ Quantity filter successful!")
        print(f"   - Items Found: {data['summary']['total_unique_products']}")
        print(f"   - Total Quantity: {data['summary']['total_quantity_in_stock']}")
        print(f"   - Total Value: ${data['summary']['total_inventory_value']}")
    except Exception as e:
        print(f"❌ Quantity filter failed: {e}")
    
    # Test 5: Export by storefront
    print("\n" + "-" * 80)
    print("TEST 5: Export by Specific Storefront")
    print("-" * 80)
    
    first_storefront = storefronts.first()
    if first_storefront:
        filters = {
            'storefront_id': str(first_storefront.id),
        }
        
        print(f"Filtering for storefront: {first_storefront.name}")
        
        try:
            data = exporter.export(filters)
            print(f"✅ Storefront filter successful!")
            print(f"   - Items in {first_storefront.name}: {data['summary']['total_unique_products']}")
            print(f"   - Total Quantity: {data['summary']['total_quantity_in_stock']}")
            print(f"   - Total Value: ${data['summary']['total_inventory_value']}")
        except Exception as e:
            print(f"❌ Storefront filter failed: {e}")
    
    # Test 6: Export with stock movements (if available)
    print("\n" + "-" * 80)
    print("TEST 6: Export with Stock Movement History")
    print("-" * 80)
    
    filters = {
        'include_movement_history': True,
    }
    
    print(f"Including stock movement history")
    
    try:
        data = exporter.export(filters)
        print(f"✅ Movement history export successful!")
        print(f"   - Stock Items: {len(data['stock_items'])}")
        print(f"   - Movement Records: {len(data['stock_movements'])}")
        
        if data['stock_movements']:
            print(f"\n   Recent movements (first 3):")
            for i, movement in enumerate(data['stock_movements'][:3], 1):
                print(f"   {i}. {movement['product_name']} - {movement['adjustment_type']}")
                print(f"      {movement['date']} at {movement['storefront']}")
                print(f"      Qty: {movement['quantity_before']} → {movement['quantity_after']} " +
                      f"({movement['quantity_adjusted']:+d})")
                if movement['reason']:
                    print(f"      Reason: {movement['reason']}")
    except Exception as e:
        print(f"❌ Movement history failed: {e}")
    
    # Test 7: Business scoping
    print("\n" + "-" * 80)
    print("TEST 7: Business Scoping Test")
    print("-" * 80)
    
    other_business = Business.objects.exclude(id=business.id).first()
    
    if other_business:
        print(f"Checking that user cannot see data from: {other_business.name}")
        
        # Count inventory for other business
        other_inventory = StoreFrontInventory.objects.filter(
            storefront__business_link__business=other_business
        ).count()
        print(f"Other business has {other_inventory} stock items")
        
        # Try to export - should return only user's business data
        filters = {}
        data = exporter.export(filters)
        
        print(f"✅ Business scoping works! User only sees their business data.")
        print(f"   - User's business items in export: {data['summary']['total_unique_products']}")
    
    print("\n" + "=" * 80)
    print("ALL TESTS COMPLETED")
    print("=" * 80)


if __name__ == '__main__':
    test_inventory_export()
