# Stock Reconciliation Formula - Clarification for Frontend Team

**Date:** 2025-10-09  
**Re:** ELEC-0007 reconciliation discrepancy

## The Confusion

The frontend team correctly identified that for ELEC-0007:
- Recorded batch: 26
- Storefront on hand: 23
- Sales: 10
- Shrinkage: 18

And noted: "23 + 10 + 18 = 51 units accounted for, but only 26 were received."

## Why This Happens (By Design)

### Current System Architecture

1. **Sales reduce `StoreFrontInventory` directly**
   - When a sale completes, we call `StoreFrontInventory.quantity -= sale_quantity`
   - So the 23 units currently at storefronts is **already net of the 10 sold**

2. **Shrinkage adjustments reduce `StockProduct.quantity`**
   - When shrinkage occurs, we call `StockProduct.quantity -= shrinkage_amount`
   - This affects the warehouse recorded batch, not the storefront

3. **The reconciliation formula accounts for these movements**
   ```
   baseline = warehouse_on_hand 
            + storefront_on_hand 
            + completed_sales     (adding back what left via sales)
            - shrinkage           (subtracting what was lost)
            + corrections         (adding back what was corrected)
            - reservations        (subtracting what's held)
   ```

### For ELEC-0007 Specifically

The formula computes:
```
baseline = 3 (warehouse) + 23 (storefront) + 10 (sold) - 18 (shrinkage) + 0 - 0 = 18
```

But recorded batch is 26, so **delta = -8 units missing**.

This delta indicates one of these scenarios:
1. ✅ **8 units were transferred but not recorded** (likely)
2. ✅ **Sales/shrinkage were recorded incorrectly** (possible)
3. ✅ **Initial batch size was entered wrong** (possible)

## What The Frontend Should Do

### Display Logic (No Changes Needed)

Your current implementation is **correct**:
- Show `warehouse.inventory_on_hand` as-is (the computed value)
- Show `storefront.total_on_hand` as-is
- Show sales, shrinkage, corrections as-is
- Show the breakdown per storefront from `storefront.breakdown[]`
- **Display the warning** when `baseline_vs_recorded_delta ≠ 0`

### Warning Message Enhancement

When `baseline_vs_recorded_delta` is non-zero, update the warning message to be more helpful:

**Current:**
```
Calculated baseline differs from recorded batch size by 11 more units. Backend reconciliation required.
```

**Suggested:**
```
⚠️ Reconciliation mismatch detected: {Math.abs(delta)} units {delta > 0 ? 'over' : 'under'} accounted.

Possible causes:
• Unrecorded transfers or intake
• Incorrect shrinkage/adjustment entries  
• Data entry errors in batch size

Contact inventory team to investigate transaction history for this product.
```

## What The Backend Needs To Do

1. **Investigate ELEC-0007's transaction history**
   - Audit all `Transfer`, `TransferLineItem` records
   - Verify `StockAdjustment` entries
   - Check `Sale` and `SaleItem` records
   - Look for duplicate entries or missing transactions

2. **Provide a reconciliation report endpoint** (future enhancement)
   ```
   GET /inventory/api/products/<id>/reconciliation-audit/
   ```
   Returns:
   - All transfers (date, from, to, quantity)
   - All sales (date, storefront, quantity)
   - All adjustments (date, type, quantity, reason)
   - Timeline view of quantity changes

3. **Add data validation**
   - Prevent sales when `StoreFrontInventory.quantity` would go negative
   - Warn when adjustments would cause negative quantities
   - Flag when baseline delta exceeds threshold (e.g., 10%)

## Summary

| What | Status | Notes |
|------|--------|-------|
| Frontend displaying correct data | ✅ Correct | No changes needed |
| `warehouse.inventory_on_hand` formula | ✅ Correct | `recorded - storefront` is by design |
| Reconciliation warning showing | ✅ Correct | This is the system working as intended |
| ELEC-0007 data inconsistency | ⚠️ Real issue | Backend investigation required |
| Sales/shrinkage in formula | ✅ Correct | They reconstruct what happened to the batch |

**Bottom line:** The frontend is working correctly. The warning is legitimate and surfacing real data problems that the backend/operations team needs to investigate and fix in the source transaction records.
