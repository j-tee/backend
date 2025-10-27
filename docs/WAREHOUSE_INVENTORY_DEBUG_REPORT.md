# Warehouse Inventory Debug Report

**Date:** 2025-10-09  
**Product:** Network Cable Tester (SKU NET-DL-0006)

## Summary
- Frontend rendered `warehouse_on_hand` as `0`, yet there are no storefront, sales, adjustments, or reservations, while the recorded batch quantity is `528`.
- Direct API call to `/inventory/api/products/d2e3e825-e712-425a-80a1-7a98a758c0b9/stock-reconciliation/` confirms `warehouse_inventory_on_hand` now equals `528` after the code fix, matching the `Inventory` table.
- The remaining mismatch is limited to the frontend cache/state; backend data is consistent.

## Backend Verification Steps
1. Pulled latest `development` branch containing the formula correction.
2. Activated virtual environment and ran targeted regression:
   ```bash
   source venv/bin/activate
   python manage.py test inventory.tests.StockReconciliationAPITest
   ```
   - Result: PASS, baseline = 17, recorded batch = 20 in fixture.
3. Queried reconciliation endpoint locally:
   ```python
   from django.test import Client
   from django.contrib.auth import get_user_model
   from inventory.models import Product
   
   client = Client()
   User = get_user_model()
   user = User.objects.filter(is_superuser=True).first()
   client.force_login(user)
   product = Product.objects.get(sku="NET-DL-0006")
   response = client.get(
       f"/inventory/api/products/{product.id}/stock-reconciliation/",
   )
   print(response.json()["warehouse"]["inventory_on_hand"])
   ```
   - Output: `528`

## Next Actions
- Ask frontend to hard-reload or invalidate cached reconciliation payload for this product.
- If issue persists, capture the network response in-browser and verify the JSON mirrors the backend results above.
- No additional backend changes required at this time.
