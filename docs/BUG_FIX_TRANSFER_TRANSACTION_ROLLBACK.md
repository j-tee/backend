# Transfer Request Transaction Rollback Bug Fix

## Problem Summary

When confirming/fulfilling transfer requests with insufficient warehouse stock, the system was:
1. Showing validation error to the user ("Insufficient warehouse stock")
2. **BUT still incrementing StoreFrontInventory**
3. Each retry attempt added more to storefront inventory
4. Result: Storefront showing 284 units when warehouse only had 10 units available

## Root Cause

The `apply_manual_inventory_fulfillment()` method in `TransferRequest` had a nested `transaction.atomic()` block that **committed inventory changes immediately**, even when the outer transaction failed validation.

### Code Flow (BEFORE Fix)

```python
# In views.py - _complete_transfer_request()
with transaction.atomic():  # Outer transaction
    transfer_request.status = STATUS_FULFILLED
    transfer_request.save()  # Signal validates - PASSES (inventory not updated yet)
    
    # In models.py - apply_manual_inventory_fulfillment()
    with transaction.atomic():  # INNER TRANSACTION - PROBLEM!
        for line in line_items:
            entry.quantity += line.requested_quantity
            entry.save()
        # COMMITS HERE - Inventory changes are persisted!
    
    # If any error happens after this, outer transaction rolls back
    # the TransferRequest status, but StoreFrontInventory changes
    # were already committed by the inner transaction!
```

### Why Validation Didn't Prevent the Problem

The `pre_save` signal on TransferRequest validates **before** `save()` completes, which is **before** `apply_manual_inventory_fulfillment()` runs. So:

1. Signal checks: "Do we have enough stock?" → YES (inventory not updated yet)
2. Save completes successfully
3. `apply_manual_inventory_fulfillment()` runs → Updates StoreFrontInventory in **separate committed transaction**
4. If anything fails after step 3, it's too late - inventory is already committed

## The Fix

Removed the nested `transaction.atomic()` from `apply_manual_inventory_fulfillment()`:

```python
# BEFORE (models.py line 683)
with transaction.atomic():
    for line in self.line_items.select_related('product'):
        entry, _ = StoreFrontInventory.objects.select_for_update().get_or_create(...)
        entry.quantity += line.requested_quantity
        entry.save()

# AFTER
# Note: No transaction.atomic() here - caller must handle transaction boundary
# This ensures rollback works if validation fails after inventory changes
for line in self.line_items.select_related('product'):
    entry, _ = StoreFrontInventory.objects.select_for_update().get_or_create(...)
    entry.quantity += line.requested_quantity
    entry.save()
```

Now inventory changes are part of the **caller's transaction**, which means:
- If outer transaction fails → StoreFrontInventory changes are rolled back
- If outer transaction succeeds → Everything commits together atomically

## Files Modified

1. **inventory/models.py** (line 683)
   - Removed `with transaction.atomic():` wrapper from `apply_manual_inventory_fulfillment()`
   - Added comment explaining caller must handle transaction boundary

2. **inventory/views.py** (lines 1598-1623)
   - Previously added `_complete_transfer_request()` method with proper transaction handling
   - Previously added `_convert_django_validation_error()` for proper error responses

## Testing the Fix

### Test Case 1: Insufficient Stock Validation
```bash
# Create transfer request for 100 units when only 10 available
POST /api/inventory/transfer-requests/{id}/fulfill/

Expected Result:
- HTTP 400 Bad Request
- Error: "Insufficient warehouse stock: requested 100 units, only 10 available"
- StoreFrontInventory remains UNCHANGED
- TransferRequest status remains NEW (not FULFILLED)
```

### Test Case 2: Sufficient Stock Success
```bash
# Create transfer request for 5 units when 10 available
POST /api/inventory/transfer-requests/{id}/fulfill/

Expected Result:
- HTTP 200 OK
- TransferRequest status → FULFILLED
- StoreFrontInventory increases by 5 units
- Both changes committed together
```

### Test Case 3: Verify Rollback
```python
# In Django shell
from inventory.models import TransferRequest, StoreFrontInventory
from django.db import transaction

# Get initial inventory
initial_qty = StoreFrontInventory.objects.get(product=product).quantity

# Try to fulfill request with insufficient stock
try:
    request.fulfill()
except ValidationError:
    pass

# Verify inventory UNCHANGED
final_qty = StoreFrontInventory.objects.get(product=product).quantity
assert initial_qty == final_qty, "Inventory should not change on validation failure!"
```

## Production Cleanup Required

The bug has already caused data corruption in production:

```sql
-- Product: "10mm Metal Cable"
-- Expected: max 10 units (warehouse intake)
-- Actual: 284 units in storefront
-- Difference: 274 units overcapacity
```

### Cleanup Script
```python
# management command: fix_corrupted_storefront_inventory.py
from inventory.models import StoreFrontInventory, TransferRequest, StockProduct

def fix_product_inventory(product_id):
    """Recalculate correct storefront inventory from fulfilled transfers only."""
    
    # Get all FULFILLED transfers for this product
    fulfilled_transfers = TransferRequestLineItem.objects.filter(
        product_id=product_id,
        request__status='FULFILLED'
    ).aggregate(total=Sum('requested_quantity'))['total'] or 0
    
    # Get sold quantity (already deducted from storefront)
    # Don't subtract this - it's already reflected in current quantity
    
    # Update storefront to correct value
    StoreFrontInventory.objects.filter(
        product_id=product_id
    ).update(quantity=fulfilled_transfers)
    
    print(f"Fixed {product.name}: Set to {fulfilled_transfers} units")
```

## Prevention Measures

1. **Transaction Boundaries**: Always use `transaction.atomic()` at the **highest level** (view/API endpoint), not in nested model methods
2. **Validation Placement**: Validate BEFORE making database changes, not after
3. **Integration Tests**: Add tests that verify rollback behavior on validation failures
4. **Monitoring**: Log inventory changes with request IDs to detect anomalies

## Related Files

- `inventory/models.py`: TransferRequest.apply_manual_inventory_fulfillment()
- `inventory/views.py`: TransferRequestViewSet._complete_transfer_request()
- `inventory/signals.py`: validate_transfer_has_sufficient_stock signal
- `docs/STOCK_API_SCHEMA_REFERENCE.md`: API documentation

## Git Commit Message

```
fix: Remove nested transaction in apply_manual_inventory_fulfillment

Fixes bug where StoreFrontInventory was being updated even when
transfer request validation failed. The nested transaction.atomic()
in apply_manual_inventory_fulfillment() was committing changes
independently of the outer transaction, preventing proper rollback
on validation errors.

This caused repeated failed fulfillment attempts to increment
storefront inventory despite showing error messages to users,
resulting in negative available stock calculations.

Changes:
- Remove transaction.atomic() from apply_manual_inventory_fulfillment()
- Inventory updates now inherit caller's transaction boundary
- Validation failures properly roll back all changes atomically

Resolves: Production issue with 284 units transferred when only
10 units available in warehouse
```

## Deployment Notes

1. **Deploy this fix immediately** - Critical data integrity issue
2. **Run cleanup script** to fix corrupted inventory records
3. **Monitor transfer requests** for next 24-48 hours
4. **Communicate with users** about the temporary inventory discrepancies

## Additional Observations

The signal validation currently calculates available stock as:
```
available = total_intake + adjustments - transferred - sold
```

Where `transferred` sums ALL StoreFrontInventory quantities. This is correct because:
- Each fulfilled transfer adds to storefront
- Sales deduct from storefront (but we track separately)
- Available warehouse stock = what we received - what we've sent to stores - what sold from warehouse
