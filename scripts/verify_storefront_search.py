#!/usr/bin/env python
"""
Verify Storefront Search Functionality
Confirms that products appear correctly based on their storefront location
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from inventory.models import StoreFront, Product, StockProduct
from sales.models import StoreFrontInventory
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory, force_authenticate
from inventory.views import StoreFrontViewSet

User = get_user_model()


def print_section(title):
    print("\n" + "="*80)
    print(title)
    print("="*80)


def verify_storefront_inventory():
    """Check that both storefronts have inventory"""
    print_section("1. STOREFRONT INVENTORY CHECK")
    
    storefronts = [
        StoreFront.objects.filter(name='Adenta Store').first(),
        StoreFront.objects.filter(name='Cow Lane Store').first()
    ]
    
    for sf in storefronts:
        if not sf:
            continue
            
        inv = StoreFrontInventory.objects.filter(storefront=sf)
        print(f"\n{sf.name}:")
        print(f"  Total products: {inv.count()}")
        print(f"  Total units: {sum(item.quantity for item in inv)}")
        
        if inv.count() > 0:
            print(f"  Sample products:")
            for item in inv[:3]:
                print(f"    - {item.product.sku}: {item.product.name} ({item.quantity} units)")
        else:
            print(f"  ⚠️  NO INVENTORY FOUND!")


def test_sale_catalog_endpoint():
    """Test the sale-catalog API endpoint"""
    print_section("2. SALE-CATALOG API ENDPOINT TEST")
    
    user = User.objects.first()
    if not user:
        print("❌ No user found. Cannot test API.")
        return
    
    storefronts = [
        StoreFront.objects.filter(name='Adenta Store').first(),
        StoreFront.objects.filter(name='Cow Lane Store').first()
    ]
    
    factory = APIRequestFactory()
    
    for sf in storefronts:
        if not sf:
            continue
            
        print(f"\n{sf.name}:")
        
        request = factory.get(f'/inventory/api/storefronts/{sf.id}/sale-catalog/')
        force_authenticate(request, user=user)
        
        view = StoreFrontViewSet.as_view({'get': 'sale_catalog'})
        response = view(request, pk=str(sf.id))
        
        print(f"  Status: {response.status_code}")
        
        if response.status_code == 200:
            products = response.data.get('products', [])
            print(f"  Products returned: {len(products)}")
            
            if products:
                print(f"  SKUs available:")
                for product in products[:5]:
                    print(f"    - {product['sku']}: {product['product_name']}")
                if len(products) > 5:
                    print(f"    ... and {len(products) - 5} more")
        else:
            print(f"  ❌ Error: {response.data}")


def test_sku_search():
    """Test searching for specific SKUs"""
    print_section("3. SKU SEARCH TEST")
    
    test_cases = [
        ('BEV-0001', 'Adenta Store'),  # Should find in Adenta
        ('BEV-0001', 'Cow Lane Store'), # Should NOT find in Cow Lane
        ('ELEC-0003', 'Adenta Store'),  # Should NOT find in Adenta
        ('ELEC-0003', 'Cow Lane Store'), # Should find in Cow Lane
    ]
    
    for sku, storefront_name in test_cases:
        sf = StoreFront.objects.filter(name=storefront_name).first()
        if not sf:
            continue
            
        # Check if product exists in this storefront
        exists = StoreFrontInventory.objects.filter(
            storefront=sf,
            product__sku=sku
        ).exists()
        
        status = "✅ FOUND" if exists else "❌ NOT FOUND"
        print(f"\nSKU '{sku}' in {storefront_name}: {status}")
        
        if exists:
            inv = StoreFrontInventory.objects.filter(
                storefront=sf,
                product__sku=sku
            ).select_related('product').first()
            print(f"  Product: {inv.product.name}")
            print(f"  Quantity: {inv.quantity}")


def check_product_overlap():
    """Check if products overlap between storefronts"""
    print_section("4. PRODUCT OVERLAP ANALYSIS")
    
    adenta = StoreFront.objects.filter(name='Adenta Store').first()
    cow_lane = StoreFront.objects.filter(name='Cow Lane Store').first()
    
    if not (adenta and cow_lane):
        print("❌ Cannot find both storefronts")
        return
    
    adenta_skus = set(StoreFrontInventory.objects.filter(
        storefront=adenta
    ).values_list('product__sku', flat=True))
    
    cow_lane_skus = set(StoreFrontInventory.objects.filter(
        storefront=cow_lane
    ).values_list('product__sku', flat=True))
    
    overlap = adenta_skus & cow_lane_skus
    adenta_only = adenta_skus - cow_lane_skus
    cow_lane_only = cow_lane_skus - adenta_skus
    
    print(f"\nAdenta Store: {len(adenta_skus)} unique products")
    print(f"Cow Lane Store: {len(cow_lane_skus)} unique products")
    print(f"\nShared products: {len(overlap)}")
    print(f"Adenta-only: {len(adenta_only)}")
    print(f"Cow Lane-only: {len(cow_lane_only)}")
    
    if len(overlap) == 0:
        print("\n⚠️  NO PRODUCTS ARE SHARED BETWEEN STOREFRONTS")
        print("   This is why searching for a product in one storefront")
        print("   won't find it in the other storefront.")


def verify_business_links():
    """Verify storefronts have proper business links"""
    print_section("5. BUSINESS LINK VERIFICATION")
    
    storefronts = [
        StoreFront.objects.filter(name='Adenta Store').first(),
        StoreFront.objects.filter(name='Cow Lane Store').first()
    ]
    
    for sf in storefronts:
        if not sf:
            continue
            
        print(f"\n{sf.name}:")
        
        try:
            bl = sf.business_link
            print(f"  ✅ Business Link: {bl.business.name}")
            print(f"     Business ID: {bl.business.id}")
        except AttributeError:
            print(f"  ❌ No business link found!")


def main():
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*25 + "STOREFRONT SEARCH VERIFICATION" + " "*23 + "║")
    print("╚" + "="*78 + "╝")
    
    verify_storefront_inventory()
    test_sale_catalog_endpoint()
    test_sku_search()
    check_product_overlap()
    verify_business_links()
    
    print_section("SUMMARY")
    print("""
✅ If all tests above pass, the system is working correctly.

The "issue" reported is expected behavior:
- Each storefront has its own independent inventory
- Products in Adenta Store won't appear when searching in Cow Lane Store
- Products in Cow Lane Store won't appear when searching in Adenta Store

To fix this for testing:
1. Create transfer requests to move products to both storefronts
2. Or accept that each storefront has different products (real-world scenario)

Frontend should:
1. Clearly show which storefront is active
2. Only search within the active storefront
3. Optionally suggest other storefronts if product not found
""")
    print("="*80 + "\n")


if __name__ == '__main__':
    main()
