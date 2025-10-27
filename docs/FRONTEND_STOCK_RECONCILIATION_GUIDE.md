# Stock Item Detail Metrics — Frontend Reconciliation Guide

_Last updated: 2025-10-09_

This note explains how the warehouse, transfer, storefront, and POS sales layers line up so a stock item detail screen can display consistent numbers. It complements `FRONTEND_HANDOFF_STOREFRONT_AVAILABILITY.md` (real-time storefront view) and `FRONTEND_SALE_CATALOG_HANDOFF.md` (catalog list contract).

> **Need a frontend-specific wiring guide?** See `FRONTEND_STOCK_DETAIL_UI_CHECKLIST.md` for the exact API calls, formulas, and pseudo-code used by the POS modal.

---

## 1. Mental model

1. Warehouse intake creates a **`StockProduct`** record (batch-level quantities tied to a warehouse and supplier).
2. Transfers or manual adjustments move units out of the warehouse batch into **`StoreFrontInventory`** rows (one per storefront/product pair).
3. POS carts place **`StockReservation`** holds against the storefront quantity so we do not oversell.
4. Completing a sale converts reservations into real deductions on the storefront inventory while also writing **`Sale` / `SaleItem`** records.

All reporting derives from those four tables, and every REST endpoint simply surfaces different slices of the same state.

---

## 2. Data model cheat sheet

| Table / model | Scope | Key columns to know | When it changes |
| --- | --- | --- | --- |
| `inventory.StockProduct` | Warehouse batch | `quantity`, `retail_price`, `warehouse_name`, `product_id` | On warehouse receiving, transfers out, manual adjustments |
| `inventory.StoreFrontInventory` | Storefront shelf | `quantity`, `storefront_id`, `product_id` | On transfers in, sales, manual storefront adjustments |
| `inventory.stock_adjustments.StockAdjustment` | Shrinkage / corrections | `adjustment_type`, `quantity`, `status`, `notes` | When theft, damage, sampling, recounts, or manual corrections are recorded (status `COMPLETED` affects totals) |
| `sales.StockReservation` | POS cart holds | `quantity`, `cart_session_id`, `expires_at`, `status` | When an item is added to a live draft sale |
| `sales.SaleItem` | Completed or in-flight sale line | `quantity`, `sale_id`, `product_id`, `stock_product_id` | When a sale is completed (status `COMPLETED`/`PARTIAL`) |

Derived terms used on the stock item page:

- **Warehouse on hand** = `StockProduct.quantity` for the batch.
- **Storefront on hand** = sum of `StoreFrontInventory.quantity` for the product per storefront.
- **Reserved for carts** = sum of active `StockReservation.quantity` per storefront/product.
- **Sellable right now** = storefront on hand − active reservations (never negative).
- **Units sold** = sum of `SaleItem.quantity` for completed or partial sales.
- **Adjustments out** (shrinkage) = absolute sum of negative `StockAdjustment.quantity` values with status `COMPLETED` (types: THEFT, LOSS, DAMAGE, SPOILAGE, SAMPLE, WRITE_OFF, etc.).
- **Adjustments in** (corrections) = sum of positive `StockAdjustment.quantity` values with status `COMPLETED` (types: COUNT_CORRECTION, RETURN_TO_STOCK, etc.).

> Tip: The models expose helpers like `StockProduct.get_adjustment_summary()` and `get_shrinkage_total()` if you are aggregating server-side.

---

## 3. API quick reference

| What you need | Endpoint | Important fields | Notes |
| --- | --- | --- | --- |
| Warehouse batch details | `GET /inventory/api/stock-products/<stock_product_id>/` | `quantity` (warehouse on hand), `product`, `retail_price`, `wholesale_price`, `warehouse_name` | Use this as the base payload for the detail modal. |
| Storefront snapshot (single storefront + product) | `GET /inventory/api/storefronts/<storefront_id>/stock-products/<product_id>/availability/` | `total_available`, `reserved_quantity`, `unreserved_quantity`, `batches[]`, `reservations[]` | The same endpoint powers the POS badge. All numbers are returned as integers unless fractional stock is configured. |
| Storefront catalog list | `GET /inventory/api/storefronts/<storefront_id>/sale-catalog/` | For each product: `available_quantity`, `retail_price`, `wholesale_price`, `stock_product_ids[]` | Ideal for bulk rendering. Use `stock_product_ids` to link back to the batch detail. |
| Warehouse fallback (legacy) | `GET /inventory/api/stock/availability/?warehouse=<uuid>&product=<uuid>[&quantity=<int>]` | `available_quantity`, `is_available` | Only needed if the storefront endpoint returns a 404/500. |
| Transfer ledger | `GET /inventory/api/transfers/?destination_storefront=<uuid>&status=COMPLETED` | Each transfer embeds `line_items[]` with `product_id`, `fulfilled_quantity` | Sum `fulfilled_quantity` for a storefront → total units ever delivered. |
| Sold quantity (per product) | `GET /sales/api/sales/?product=<uuid>&status=COMPLETED` (filter + client-side sum of `sale_items`) **or** use the `/sales/api/sales/summary/` analytics endpoint if wired | `sale_items[].quantity`, `summary.products[]` (when using analytics) | Filtering by product keeps the payload small; only completed/partial sales affect stock. |
| Adjustment history | `GET /inventory/api/stock-adjustments/?stock_product=<uuid>&status=COMPLETED` | `adjustment_type`, `quantity`, `total_cost`, `notes`, `created_at` | Positive quantities add back units, negative quantities remove them. Use aggregations to compute shrinkage vs. corrections. |

### How adjustments affect totals

1. **Shrinkage (loss, damage, theft, sampling)** reduces the expected stock without a sale. Recordings live on the `StockAdjustment` endpoint with negative quantities.
2. **Positive corrections** (cycle count increases, returns) add units back. They appear as positive quantities.
3. When reconciling a batch, calculate the *net adjustment*:

   ```
   net_adjustment = adjustments_in - adjustments_out
   ```

   Apply that to the warehouse total:

   ```
   expected_batch_total = initial_receipt + net_adjustment
   ```

   Your UI can then ensure:

   ```
   warehouse_on_hand
   + storefront_on_hand
   + units_sold
   + adjustments_out
   - adjustments_in
   - reservations
   = expected_batch_total
   ```

   (When there are no adjustments the formula collapses back to the simpler version.)

---

## 4. Implementation walk-through for a stock product detail page

1. **Fetch the batch.** Call `GET /inventory/api/stock-products/<stock_product_id>/` as soon as the details drawer opens. Render
   - Warehouse quantity (`quantity`)
   - Pricing (`retail_price`, `wholesale_price`)
   - Metadata (supplier, expiry, warehouse name).
2. **Identify storefronts.** Either
   - Use the authenticated user’s storefront assignments (`GET /inventory/api/storefronts/?business=<id>`), or
   - Hardcode the storefronts the UI lets the user pick.
3. **Pull per-storefront availability.** For each storefront the user cares about:
   - Call `/inventory/api/storefronts/<storefront_id>/stock-products/<product_id>/availability/`.
   - Render `total_available` (what is physically on the shelf), `reserved_quantity` (held by carts), and `unreserved_quantity` (immediately sellable).
   - Display `reservations[]` if you want to show “reserved by Sale #… until …”.
4. **Show sold vs delivered.**
   - Total delivered = sum of `fulfilled_quantity` for transfers into that storefront (complete transfers only).
   - Units sold = delivered − current `total_available` − active reservations. You can double-check against the sales API if you need the absolute number.
5. **Keep data fresh.** When the POS completes a sale or a transfer arrives, refresh step 3. The availability endpoint is idempotent and safe to poll or refetch on demand.

Pseudo-flow in React (conceptual):

```ts
const batch = await api.get(`/inventory/api/stock-products/${stockProductId}/`);
const storefronts = await loadStorefronts();

const availabilityByStorefront = await Promise.all(
  storefronts.map(async (store) => {
    const { data } = await api.get(
      `/inventory/api/storefronts/${store.id}/stock-products/${batch.product}/availability/`
    );
    return { store, availability: data };
  })
);
```

---

## 5. Sanity check: SKU `ELEC-0007`

The numbers below come straight from the staging database on 2025-10-09.

| Layer | Query used | Result |
| --- | --- | --- |
| Warehouse batch | `StockProduct.objects.filter(product__sku='ELEC-0007')` | 26 units remain at `Rawlings Park Warehouse` |
| Storefront stock | `StoreFrontInventory.objects.filter(product__sku='ELEC-0007')` | `Cow Lane Store: 3`, `Adenta Store: 20` (total 23) |
| POS sales | `SaleItem.objects.filter(product__sku='ELEC-0007', sale__status__in=['COMPLETED','PARTIAL'])` | 10 units sold |
| Reservations | Active `StockReservation` rows for the SKU | 0 units reserved |
| Adjustments | `StockAdjustment.objects.filter(stock_product__product__sku='ELEC-0007', status='COMPLETED')` | 0 units removed, 0 units added |

Reconciliation rule of thumb:

```
warehouse_on_hand (26)
+ storefront_on_hand (23)
+ units_sold (10)
+ adjustments_out (0)
- adjustments_in (0)
- reservations (0)
= 59 units processed from that batch
```

That matches the original intake for ELEC-0007. The storefront availability endpoint currently returns `unreserved_quantity = 23`, so the POS product list should show the same number.

---

## 6. Troubleshooting checklist

- **Storefront shows zero but transfer completed:** Hit the availability endpoint directly; if `total_available` increased, the UI is caching old data.
- **Reserved quantity never clears:** Ensure the POS calls `POST /sales/api/sales/<sale_id>/complete/` or `.../abandon/` so `StockReservation` rows flip out of `ACTIVE`.
- **Warehouse quantity negative:** Transfers or adjustments are subtracting more than the batch holds—double-check the batch’s adjustment log (`/inventory/api/stock-adjustments/`).
- **Front end only needs totals:** When you do not need per-reservation detail, prefer `sale-catalog` for a single round trip instead of multiple availability calls.

Ping the backend channel if any endpoint contracts differ from the examples above—we can tweak the serializer rather than bolting on client-side math.
