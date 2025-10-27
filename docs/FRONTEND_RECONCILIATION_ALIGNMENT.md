# Frontend Banner Alignment for Stock Reconciliation

**Date:** 2025-10-09  
**Context:** Tracking the reconciliation banner requirements coming out of the warehouse-to-storefront flow discussion and confirming the backend contracts now available on `development`.

---

## Backend contract confirmations

- **Per-product warehouse totals**
  - `GET /inventory/api/products/<product_id>/stock-reconciliation/` returns:
    - `warehouse.recorded_quantity`: Sum of all `StockProduct.quantity` for this product (total received at intake)
    - `warehouse.inventory_on_hand`: **Calculated as** `recorded_quantity - storefront.total_on_hand` (what remains at the warehouse)
    - `warehouse.inventory_breakdown[]`: Raw `Inventory` table entries (for audit/debugging only)
  - **Important:** `warehouse.inventory_on_hand` is now a **computed value**, not a direct database sum, reflecting the logical definition: what was received minus what was transferred out.
- **Storefront availability after transfers**
  - `storefront.total_on_hand`: Sum of all `StoreFrontInventory.quantity` for this product
  - `storefront.breakdown[]`: Per-storefront details with:
    - `on_hand`: Total quantity at this storefront
    - `sellable`: On-hand minus active reservations for this storefront
    - `reserved`: Active cart reservations linked to sales at this storefront
- **Sales, shrinkage, corrections, reservations**
  - `sales.completed_units` / `sales.completed_value`: Derived from completed sale items.
  - `adjustments.shrinkage_units` & `adjustments.correction_units`: Aggregated from completed `StockAdjustment` rows.
  - `reservations.details[]`, `reservations.linked_units`, `reservations.orphaned_units`: Active reservations, distinguishing linked carts from orphaned holds.

## UI math expectations

The reconciliation banner follows this logical flow:

1. **Recorded batch size** = Sum of `StockProduct.quantity` (what arrived at the warehouse)
2. **Storefront on hand** = Sum of `StoreFrontInventory.quantity` (what was transferred and fulfilled)
3. **Warehouse on hand** = Recorded batch size − Storefront on hand
4. **Available for sale** = Storefront on hand − Units sold

The baseline reconciliation formula is:

$$\text{baseline} = \text{warehouse\_on\_hand} + \text{storefront\_on\_hand} + \text{completed\_sales\_units} - \text{shrinkage\_units} + \text{correction\_units} - \text{active\_reservations\_units}$$

When everything is accounted for correctly, `baseline` should equal `recorded_batch_size` and `baseline_vs_recorded_delta` should be `0`.

The banner should:

1. Display **Recorded batch size** as `warehouse.recorded_quantity`
2. Display **Warehouse on hand** as `warehouse.inventory_on_hand` (computed: recorded − storefront)
3. Display **Storefront on hand** as `storefront.total_on_hand`
4. For each storefront in `storefront.breakdown[]`, show:
   - **On hand**: Total quantity at this location
   - **Sellable**: `on_hand - reserved` (what customers can actually purchase)
   - **Reserved**: Active cart reservations for this storefront
5. Display shrinkage and corrections separately using `adjustments.shrinkage_units` and `adjustments.correction_units`
6. Show a warning when `formula.baseline_vs_recorded_delta ≠ 0`, indicating missing transactions or data drift

## Next coordination notes

- **Baseline reference**: We are not persisting an additional `initial_quantity` field. The UI should continue to rely on `formula.calculated_baseline` and surface the `baseline_vs_recorded_delta` warning when needed. If the strategy changes, this doc will be amended accordingly.
- **Adjustment replays**: The management command `python manage.py inventory_replay_completed_adjustments` remains available to reapply historical adjustments if data drifts. When runs are scheduled or completed, we will surface the status here so the frontend can clear outstanding warnings.
- **Further endpoints**: If we extract dedicated endpoints for sales, shrinkage, or reservations in the future, they will mirror the same aggregation logic that feeds `stock-reconciliation`. For now, the single endpoint guarantees consistent numbers across the banner.

Please hook the UI directly into these response fields. Ping the backend team if you need additional schema tweaks or if the reconciliation strategy changes.
