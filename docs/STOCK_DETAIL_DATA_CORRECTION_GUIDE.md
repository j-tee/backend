# Stock Detail Banner Data Corrections

_Last updated: 2025-10-09_

This note documents the discrepancies we found between the frontend stock detail widget and the live database for SKU `ELEC-0007` (stock batch `83096f71-b4aa-4fbe-8a18-dd9b12824a5e`). It also lists the changes each team needs to make so the reconciliation banner matches the persisted data.

---

## 1. Ground truth snapshot (backend queries)

| Metric | Query source | Value | Notes |
| --- | --- | --- | --- |
| Recorded batch quantity | `inventory_stockproduct.quantity` | **26** | Represents the batch total _after_ any adjustments that were actually applied. |
| Storefront on hand | `storefront_inventory` | **23** (Adenta 20, Cow Lane 3) | Matches the UI chips. |
| Completed sales | `sales_saleitem` (status `COMPLETED`) | **10** | UI shows 10 — confirmed. |
| Negative adjustments | `inventory_stock_adjustments` (`COMPLETED`, `quantity < 0`) | **18** | Damage/sample/loss rows entered as completed but never applied to the batch quantity. |
| Positive adjustments | same table (`quantity > 0`) | **0** | None for this batch. |
| Active reservations | `sales_stockreservation` (status `ACTIVE`) | **3** | Two carts (2 + 1 units) remain flagged active even though the associated sales were abandoned. |

Reconciliation using the checklist formula (`warehouse + storefront + sold + adjustments_out – adjustments_in – reservations`) yields `0 + 23 + 10 + 18 – 0 – 0 = 51`. The banner in the screenshot currently states `59 = initial intake 26`, so we are mixing incompatible data sources.

---

## 2. What the frontend must adjust

1. **Use consistent reservation numbers.**
   * The chip labelled “Active reservations” pulls `reserved_quantity` from the storefront availability API, which filters reservations that still map to an accessible sale.
   * `Sellable now` subtracts _all_ active holds, including orphaned reservations whose `cart_session_id` no longer maps to a sale.
   * Choose one definition and apply it to both fields. If the UI keeps the broader definition, fetch the full reservation count from the availability response (`reservations` array) and align the chip with the “Sellable now” math.

2. **Rename and re-frame adjustment labels.**
   * The number currently shown as “Adjustments out (18)” is shrinkage; it reduces stock. Rename it to something clearer (`Shrinkage / write-offs`) and subtract it in the banner sentence.
   * If we later surface positive corrections, label them as “Adjustments in (returns/corrections)” and add them to the tally.

3. **Stop claiming the initial intake is 26 until backend reconciliation is fixed.**
   * Either hide the “Initial intake” tag temporarily or change it to “Recorded batch size” so it reflects the actual `StockProduct.quantity` field.
   * Once the backend writes the historical intake somewhere authoritative (see below), you can restore the formula with the true baseline.

4. **Document the banner equation in code comments.**
   * Add a brief comment (or reuse the checklist) near the reducer that composes the reconciliation string so the next reader understands each term.

---

## 3. Backend fixes required

1. **Apply outstanding stock adjustments.**
   * The four rows created on 2025-10-06 were inserted directly as `status='COMPLETED'`. Because `StockAdjustment.complete()` was never called, `StockProduct.quantity` still reports 26 instead of 8.
   * Recommended approach: write a one-off script or management command that iterates over `inventory_stock_adjustments` where `status='COMPLETED'` and `completed_at` is set but `quantity_before` equals the batch’s current quantity. For each, call the model’s `complete()` logic (or manually decrement/increment `stock_product.quantity`). Make sure the change is wrapped in a transaction to avoid partial updates.

2. **Decide how to store “initial intake.”**
   * If we need to keep the processed quantity for reporting, add a dedicated field (e.g., `initial_quantity`) when the batch is created. That value never changes, while `quantity` reflects the live on-hand balance.
   * Update the stock-product serializer to expose both `quantity` (current on hand) and `initial_quantity` (baseline) so the frontend does not have to infer it via adjustments.

3. **Clean up or expose orphaned reservations.**
   * Run a periodic job that releases `StockReservation` rows whose `cart_session_id` no longer matches an existing sale, or
   * Extend the storefront availability endpoint to surface both “reservations tied to open sales” and “orphaned holds” so the frontend can display them separately.

4. **Optional: expose a consolidated analytics endpoint.**
   * If the POS needs fewer round-trips, consider adding an endpoint that returns all banner metrics (warehouse quantity, storefront total, sold quantity, shrinkage, reservations) in a single payload. This prevents the client from stitching inconsistent datasets together.

---

## 4. Immediate next steps

| Owner | Task | Status |
| --- | --- | --- |
| Backend | Run adjustment replay (or manual reconciliation) for batch `83096f71-b4aa-4fbe-8a18-dd9b12824a5e`. | ☐ |
| Backend | Decide on `initial_quantity` strategy and update serializer. | ☐ |
| Backend | Define reservation policy (release vs. expose orphaned holds). | ☐ |
| Frontend | Rename adjustment chips & update banner math to subtract shrinkage. | ☐ |
| Frontend | Align “Active reservations” metric with the chosen definition. | ☐ |
| Frontend | Replace “Initial intake 26” copy until backend exposes authoritative baseline. | ☐ |

Once the backend items are complete, rerun the checklist with fresh data and update the screenshot in `FRONTEND_STOCK_DETAIL_UI_CHECKLIST.md` so it matches production reality.
