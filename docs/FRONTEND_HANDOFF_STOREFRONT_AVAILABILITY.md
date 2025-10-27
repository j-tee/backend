# Storefront Fulfillment & Availability Backend Update — Frontend Integration Guide

_Last updated: 2025-10-08_

This note documents the recent backend work that unblocks the "fulfilled transfer still shows Out of stock" issue. It explains:

- What changed in the API (endpoints, payloads, and error shapes)
- How the new data should flow through the existing POS UI
- Implementation steps and edge cases for frontend developers
- Optional enhancements you can ship to make the UX feel snappier

> **Need to update the POS product list/search panel?** See `FRONTEND_SALE_CATALOG_HANDOFF.md` for the catalog endpoint contract that removes ghost items such as ELEC-0009.
>
> **Reconciling warehouse vs. storefront totals?** Pair this doc with `FRONTEND_STOCK_RECONCILIATION_GUIDE.md` for a breakdown of how the detail view should compute each metric.

---

## 1. API surface area changes

### 1.1 Storefront availability endpoint (preferred path)

```
GET /inventory/api/storefronts/<storefront_id>/stock-products/<product_id>/availability/
```

**What’s new:**

- Always returns `total_available`, `reserved_quantity`, `unreserved_quantity` even when the product has zero stock (previously, the endpoint returned 404s in some storefront misconfiguration cases).
- Adds a `reservations` array listing active holds the POS created via cart sessions. Each reservation includes the sale ID, quantity, and expiry timestamp. This lets the UI show “Reserved” badges or debug anomalies.
- `batches` now includes the warehouse name so you can display “From Warehouse X” if you want to surface batch provenance.
- Most importantly, when a transfer request is fulfilled (including manually fulfilled requests), the storefront inventory quantity is incremented immediately, so `total_available` and `unreserved_quantity` now reflect the stock increase in near real time.

**Auth & scope:** unchanged (requires regular authenticated POS user with access to the storefront).

### 1.2 Warehouse availability endpoint (fallback path)

```
GET /inventory/api/stock/availability/?warehouse=<uuid>&product=<uuid>[&quantity=<int>]
```

**What’s new:**

- Endpoint is back online; it had regressed to 404. Existing React fallback in `fetchStockLevels` works as before.
- Returns a simple JSON payload `{ warehouse, product, available_quantity, requested_quantity, is_available }`.
- Use only if the storefront endpoint above fails, exactly as the existing POS does.

### 1.3 Sale endpoints

- `POST /sales/api/sales/<sale_id>/add-item/` now responds with detailed error payloads when stock is insufficient. Keys: `error`, `code` (`INSUFFICIENT_STOCK`), `developer_message`, and `details.{available, requested, stock_product_id, product_id}`. This drives better UX when a cashier tries to add more units than available.
- `POST /sales/api/sales/<sale_id>/abandon/` is a new action. It releases any active reservations and flips the sale to `CANCELLED` so cart-cleanup buttons can unstick a jammed draft. It is now **idempotent**—if the sale is already completed (or otherwise finalized) the endpoint still returns `200 OK`, releases any straggling reservations, and leaves the sale status untouched.
- `POST /sales/api/sales/<sale_id>/complete/` now clears reservations and storefront stock in one transaction. If the UI retries completion after a network hiccup, the endpoint is fully idempotent—no duplicate decrements.

### 1.4 Reporting & dashboards

- `GET /sales/api/sales/summary/` now includes accurate `total_cogs`, `realized_profit`, `outstanding_profit`, and a richer `credit_health` block. No frontend wiring yet, but analytics dashboards can consume this instantly.
- `GET /sales/api/sales/todays-stats/` is a brand new lightweight endpoint that mirrors the most important bits of `/summary` for a single day/storefront. Ideal for a “Today’s Sales” widget without crunching large payloads client-side.

### 1.5 Background maintenance

- New Celery task `sales.tasks.release_expired_reservations` and CLI `python manage.py release_expired_reservations [--dry-run]` keep stale cart holds from poisoning availability metrics. Nothing to do on the frontend, but good to know if you record metrics based on reservations.

---

## 2. Frontend impact & implementation steps

The POS already calls the correct endpoint. With the backend fixed, the badge will flip automatically once the transfer is fulfilled. Still, here’s how to validate and, if needed, tighten the UX.

### 2.1 Confirm the availability payload in DevTools

1. Fulfill a `TransferRequest` in the back office (manual or via the transfer workflow).
2. In the POS UI, re-search or focus the product list.
3. Open DevTools → Network and inspect the latest `GET /inventory/api/storefronts/.../availability/`.
4. Verify that `unreserved_quantity` now shows the higher quantity. If yes, the badge will update on its next render. If not, back-end data is still off—raise it with the API team.

### 2.2 Ensure `fetchStockLevels` handles the richer payload

No code change is strictly required if you already read `unreserved_quantity`. Still, confirm the following to avoid subtle bugs:

- When `reservations` is present, ignore it (or use it for UI niceties) but ensure your `setState` only depends on `unreserved_quantity` or `total_available`.
- If you presently parse numeric values as strings, upgrade them to numbers because the endpoint now returns integers/floats natively.
- Double-check that the fallback `catch` path still hits `/inventory/api/stock/availability/` (the endpoint is alive again).

### 2.3 Optional UX improvements

- **Show reserved breakdown:** With the new `reservations` array, you can expose “2 reserved (expires in 12 mins)” beside the badge, or surface a tooltip for supervisors.
- **Manual refresh button:** If salespeople frequently want to “check again,” add a small icon that replays `fetchStockLevels` on demand. No backend change needed.
- **Toast on zero stock:** Given we now return precise `developer_message` strings, bubble them up in the UI when a cashier tries to add more units than available.
- **Today’s stats widget:** Consider wiring `/sales/api/sales/todays-stats/?storefront=<id>` into dashboards. The payload includes `transactions`, `total_sales`, `cash_at_hand`, and credit snapshots.

### 2.4 Edge cases to test on the frontend

| Scenario | What to check | Expected API behavior |
| --- | --- | --- |
| Fulfillment via **manual update status** | Inventory increments and availability API shows updated `unreserved_quantity` | Works out of the box; backend automatically calls `apply_manual_inventory_fulfillment()` |
| Fulfillment via **transfer completion** | Inventory increments, reservations unaffected | Works; existing transfer completion still increments storefront inventory |
| **Abandon sale** (new action) | After calling `POST /sales/.../abandon/`, confirm `StockReservation` entries disappear and availability returns to original value | Backend releases reservations and responds with `released.total_quantity` |
| **Expired reservations** | Leave a cart idle past its expiry (30 mins default). After Celery cleanup (15 min cadence) or manual CLI, availability increases | Use the command or wait for the scheduled task |
| **Multiple reservations, different storefronts** | Ensure reservations per storefront are isolated | Backend only subtracts reservations that match the storefront of the sale |

---

## 3. Sample payloads

### 3.1 Storefront availability (after fulfilled transfer)

```json
{
  "total_available": 48,
  "reserved_quantity": 0,
  "unreserved_quantity": 48,
  "batches": [
    {
      "id": "e980...",
      "batch_number": null,
      "quantity": 48,
      "retail_price": "12.00",
      "wholesale_price": null,
      "expiry_date": null,
      "created_at": "2025-10-08T10:15:43.912Z",
      "warehouse": "Central Depot"
    }
  ],
  "reservations": []
}
```

### 3.2 Insufficient stock error payload (cart add)

```json
{
  "error": "Unable to add item due to stock restrictions.",
  "code": "INSUFFICIENT_STOCK",
  "developer_message": "Insufficient stock. Available: 1, Requested: 5",
  "details": {
    "available": "1",
    "requested": "5",
    "stock_product_id": "8f6f...",
    "product_id": "ee30..."
  }
}
```

### 3.3 Manual fulfillment response (transfer request update)

```json
{
  "id": "3df4...",
  "status": "FULFILLED",
  "_inventory_adjustments": [
    {
      "product_id": "9a1c...",
      "quantity_added": 5
    }
  ],
  ...
}
```

UI can leverage `_inventory_adjustments` for inline notifications (“Added 5 units to Downtown Storefront”).

---

## 4. Communication checklist

When handing this off or filing integration tickets, include:

- ✅ The DevTools screenshot showing `unreserved_quantity` after fulfillment.
- ✅ Reference to this doc (`docs/FRONTEND_HANDOFF_STOREFRONT_AVAILABILITY.md`).
- ✅ Mention that no frontend polling or manual cache invalidation is required once the backend patch is deployed.
- ✅ Optional: confirm Celery beat is running (operations item) so reservations stay healthy.

That’s it! With these backend fixes live, `fetchStockLevels` should instantly show the new quantity right after fulfillment. Let us know if any field names or payload variations cause trouble and we can nudge the serializers accordingly.
