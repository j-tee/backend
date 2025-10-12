#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from sales.models import StoreFrontInventory
from inventory.models import Product

# Check Samsung TV
tv = Product.objects.filter(name__icontains='Samsung TV').first()
if tv:
    inv = StoreFrontInventory.objects.filter(product=tv).select_related('storefront').first()
    print(f"\n{'='*60}")
    print(f"Product: {tv.name}")
    print(f"SKU: {tv.sku}")
    print(f"Storefront: {inv.storefront.name if inv else 'None'}")
    print(f"Quantity in StoreFrontInventory: {inv.quantity if inv else 0}")
    print(f"{'='*60}\n")

# Show all storefront inventory
print("\nAll Storefront Inventory (first 10):")
print(f"{'='*60}")
for inv in StoreFrontInventory.objects.select_related('product', 'storefront')[:10]:
    print(f"{inv.storefront.name:20} | {inv.product.name:30} | {inv.quantity:>6} units")
