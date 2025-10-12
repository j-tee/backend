#!/usr/bin/env python
"""
Quick test for multi-storefront catalog endpoint
Verifies that Sugar 1kg and other products appear correctly
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory, force_authenticate
from inventory.views import StoreFrontViewSet
import json

User = get_user_model()


def test_multi_storefront_catalog():
    """Test the multi-storefront catalog endpoint"""
    
    print("\n" + "="*80)
    print("MULTI-STOREFRONT CATALOG ENDPOINT TEST")
    print("="*80)
    
    # Get a user (business owner)
    user = User.objects.first()
    if not user:
        print("❌ No users found in database")
        return False
    
    print(f"\nTesting as: {user.name} ({user.email})")
    
    # Create request
    factory = APIRequestFactory()
    request = factory.get('/inventory/api/storefronts/multi-storefront-catalog/')
    force_authenticate(request, user=user)
    
    # Call endpoint
    view = StoreFrontViewSet.as_view({'get': 'multi_storefront_catalog'})
    response = view(request)
    
    # Check response
    print(f"\nResponse Status: {response.status_code}")
    
    if response.status_code != 200:
        print(f"❌ FAILED: Expected 200, got {response.status_code}")
        return False
    
    data = response.data
    
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"Total Storefronts: {data.get('total_storefronts', 0)}")
    print(f"Total Products: {data.get('total_products', 0)}")
    
    # Show storefronts
    print(f"\n{'='*80}")
    print("ACCESSIBLE STOREFRONTS")
    print(f"{'='*80}")
    
    storefronts = data.get('storefronts', [])
    if not storefronts:
        print("⚠️  No storefronts accessible")
        return False
    
    for sf in storefronts:
        print(f"✅ {sf['name']} ({sf['business_name']})")
    
    # Test specific products
    print(f"\n{'='*80}")
    print("SPECIFIC PRODUCT TESTS")
    print(f"{'='*80}")
    
    products = data.get('products', [])
    
    # Test 1: Sugar 1kg (the reported issue)
    print(f"\n1. Testing for 'Sugar 1kg' (FOOD-0003)...")
    sugar = next((p for p in products if p['sku'] == 'FOOD-0003'), None)
    
    if sugar:
        print(f"   ✅ FOUND!")
        print(f"      Name: {sugar['product_name']}")
        print(f"      Total Available: {sugar['total_available']} units")
        print(f"      Price: ${sugar['retail_price']}")
        print(f"      Locations:")
        for loc in sugar['locations']:
            print(f"        - {loc['storefront_name']}: {loc['available_quantity']} units")
    else:
        print(f"   ❌ NOT FOUND - This is the problem!")
        return False
    
    # Test 2: Multi-location product
    print(f"\n2. Testing for multi-location product (Coca Cola)...")
    cola = next((p for p in products if p['sku'] == 'BEV-0001'), None)
    
    if cola:
        print(f"   ✅ FOUND!")
        print(f"      Name: {cola['product_name']}")
        print(f"      Total Available: {cola['total_available']} units")
        if len(cola['locations']) > 1:
            print(f"      ✅ Available in {len(cola['locations'])} locations:")
            for loc in cola['locations']:
                print(f"        - {loc['storefront_name']}: {loc['available_quantity']} units")
        else:
            print(f"      ℹ️  Only in 1 location: {cola['locations'][0]['storefront_name']}")
    else:
        print(f"   ⚠️  Coca Cola not found")
    
    # Show all products
    print(f"\n{'='*80}")
    print("ALL PRODUCTS (first 15)")
    print(f"{'='*80}")
    print(f"{'SKU':<15} | {'Product Name':<40} | {'Total':>6} | {'Locations':>3}")
    print("-"*80)
    
    for product in products[:15]:
        loc_count = len(product.get('locations', []))
        print(f"{product['sku']:<15} | {product['product_name']:<40} | {product['total_available']:>6} | {loc_count:>3}")
    
    if len(products) > 15:
        print(f"\n... and {len(products) - 15} more products")
    
    # Final verdict
    print(f"\n{'='*80}")
    print("TEST RESULT")
    print(f"{'='*80}")
    
    if sugar and data.get('total_products', 0) > 0:
        print("✅ ALL TESTS PASSED!")
        print("\nThe endpoint is working correctly.")
        print("Frontend should use: /inventory/api/storefronts/multi-storefront-catalog/")
        return True
    else:
        print("❌ SOME TESTS FAILED")
        return False


def test_search_functionality():
    """Test searching for products"""
    
    print("\n" + "="*80)
    print("SEARCH FUNCTIONALITY TEST")
    print("="*80)
    
    user = User.objects.first()
    factory = APIRequestFactory()
    request = factory.get('/inventory/api/storefronts/multi-storefront-catalog/')
    force_authenticate(request, user=user)
    
    view = StoreFrontViewSet.as_view({'get': 'multi_storefront_catalog'})
    response = view(request)
    
    products = response.data.get('products', [])
    
    # Test searches
    test_queries = ['sugar', 'FOOD-0003', 'coca', 'laptop']
    
    for query in test_queries:
        query_lower = query.lower()
        results = [
            p for p in products
            if query_lower in p['product_name'].lower() or 
               query_lower in p['sku'].lower()
        ]
        
        print(f"\nSearch: '{query}'")
        print(f"  Results: {len(results)}")
        
        for result in results[:3]:
            print(f"    - {result['sku']}: {result['product_name']}")


if __name__ == '__main__':
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*20 + "MULTI-STOREFRONT CATALOG TEST" + " "*29 + "║")
    print("╚" + "="*78 + "╝")
    
    success = test_multi_storefront_catalog()
    
    if success:
        test_search_functionality()
        
        print("\n" + "="*80)
        print("NEXT STEPS")
        print("="*80)
        print("""
Frontend Integration:

1. Update API call:
   FROM: /inventory/api/storefronts/{id}/sale-catalog/
   TO:   /inventory/api/storefronts/multi-storefront-catalog/

2. Update product display to show locations:
   - Show all storefronts where product is available
   - Display quantity per location
   - Allow user to select location when adding to cart

3. Test searching for 'sugar 1kg' - should now appear!

See MULTI_STOREFRONT_CATALOG_API.md for detailed documentation.
        """)
    
    print("\n")
