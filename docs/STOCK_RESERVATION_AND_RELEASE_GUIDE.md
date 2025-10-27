# Stock Reservation & Release Guide

This guide explains how stock reservations work in the backend, why draft/partial sales can block stock, and what a full front-end implementation needs to do to avoid misleading stock levels.

## 1. Why reservations exist

Point-of-sale sessions can involve multiple cashiers adding items to carts concurrently. Without a reservation system two clerks could sell the last unit of a product at the same time. To prevent overselling the backend "parks" stock for an in-progress sale by creating a `StockReservation` record whenever an item is added to a draft sale. Reserved quantities are excluded from the available stock calculation that guards subsequent add-to-cart calls.

Key properties of the system:

| Concept | Description |
| --- | --- |
| **Draft sale** | A sale with status `DRAFT` that behaves like a shopping cart. |
| **Reservation** | A row in `sales_stockreservations` linking a cart session to a `StockProduct` batch and quantity. |
| **Expiry** | Reservations default to 30 minutes. When the timer elapses they should be released automatically. |
| **Commit** | When a sale is completed the reservation is marked `COMMITTED` after inventory is deducted. |
| **Release** | If a reservation is no longer needed it must be set to `RELEASED` so its quantity returns to the available pool. |

## 2. Data model essentials

`StockReservation` lives in `sales/models.py` and carries the following important fields:

- `stock_product` – the inventory batch being held.
- `quantity` – decimal quantity reserved (supports partial units).
- `cart_session_id` – string reference to the sale ID or session identifier.
- `status` – state machine (`ACTIVE`, `COMMITTED`, `RELEASED`, `CANCELLED`). Only `ACTIVE` records subtract from availability.
- `expires_at` – timestamp when the reservation should auto-release.

The helper `StockProduct.get_available_quantity()` (in `inventory/models.py`) returns `stock_product.quantity - active_reservations`, meaning *any* active reservation lowers the available quantity for future transactions.

## 3. Reservation lifecycle

### 3.1 Creation

`SaleViewSet.add_item` (POST `/sales/api/sales/{sale_id}/add_item/`) calls `StockReservation.create_reservation(...)` whenever a product is added to a draft sale and a `stock_product` is supplied. That method:

1. Computes the available quantity via `StockProduct.get_available_quantity()`.
2. Raises a structured validation error if the request exceeds availability.
3. Creates a reservation with a 30-minute expiry.
4. Logs the action in the audit trail.

### 3.2 During cart updates

- **Adding the same product again**: each POST creates another reservation. Together they represent the full quantity held for the draft sale.
- **Removing an item**: today the backend does **not** automatically release reservations when a sale item is deleted. Front-end or additional backend logic must do this.
- **Adjusting quantity**: editing a sale item calls validation that allows the existing reserved quantity to be reused, but explicit release is still required if the item quantity decreases.

### 3.3 Checkout

When `Sale.complete_sale()` runs (triggered by POST `/sales/api/sales/{sale_id}/complete/`):

1. Inventory quantities are decremented.
2. `sale.release_reservations()` marks all `ACTIVE` reservations for that sale as `RELEASED`.
3. Sale status transitions to `COMPLETED`, `PARTIAL`, or `PENDING` depending on payments.

At that point the stock is reflected in actual inventory counts, so holding the reservation is no longer necessary.

### 3.4 Automatic expiry

`StockReservation.release_expired()` queries for reservations where `status='ACTIVE'` and `expires_at < now`, then flips them to `RELEASED`. **Nothing in the repository schedules this**—it must be wired to a periodic worker (Celery beat, cron + management command, etc.). If expiry isnt triggered, abandoned carts will hold stock indefinitely.

### 3.5 Manual release / cancellation

Use `POST /sales/api/sales/{sale_id}/abandon/` to cancel a draft and immediately free all `ACTIVE` reservations linked to that sale. The endpoint:

- Validates the sale is still a `DRAFT` (or already `CANCELLED`).
- Calls `sale.release_reservations()` under the hood and timestamps each reservation with `released_at`.
- Marks the sale `CANCELLED` for audit purposes and returns the updated sale plus a breakdown of released quantities.

Because the action is idempotent, multiple calls are safe even if the cart was already cancelled. Frontend flows should invoke it whenever a cashier discards a cart.

## 4. Stock visibility and reported discrepancies

Because reservations subtract from "available" stock, any UI that only displays the raw on-hand quantity (like the product card in the POS view) can mislead cashiers. Two numbers are relevant:

- **On-hand quantity** – stored in `inventory_storefrontinventory.quantity`. This is what the card currently shows (e.g., 51 units).
- **Sellable quantity** – on-hand minus the sum of `ACTIVE` reservations. This is what `StockReservation.create_reservation()` uses to accept/reject new adds.

The endpoint `GET /inventory/api/storefronts/{storefront_id}/products/{product_id}/availability/` already exposes both values:

```json
{
  "total_available": 51,
  "reserved_quantity": 45,
  "unreserved_quantity": 6,
  "reservations": [
    {"sale_id": "...", "quantity": 5, "expires_at": "..."},
    ...
  ]
}
```

Front-end code should rely on `unreserved_quantity` (and ideally show the reservations list) to explain why a product cant be added anymore.

## 5. Front-end requirements checklist

| Scenario | Front-end responsibility |
| --- | --- |
| **Entering a cart** | Create or reuse a draft sale and track its ID. Every add-to-cart call must pass that ID so reservations stay linked. |
| **Displaying stock** | Use the storefront availability endpoint to show both on-hand and reserved quantities. Highlight when reservations consume most of the stock. |
| **User abandons checkout** | Provide a "Discard Sale" action that calls `POST /sales/api/sales/{sale_id}/abandon/` to release reservations immediately. |
| **Removing items / reducing quantities** | After decreasing quantity to zero, call the release endpoint for the sale or reissue the add-item call with the lower quantity so the backend can adjust. Today this requires backend support. |
| **Session timeout** | Prompt the user before session end; if they decline to continue, release the reservations immediately. |
| **Monitoring stale drafts** | Build a dashboard that highlights drafts approaching expiry using the `expires_at` values. This allows staff to manually clear carts if the automatic job isnt running. |

## 6. Implementation recommendations

1. **Schedule expiry cleanup**
   - Add a Celery beat task or cron job that runs `StockReservation.release_expired()` every 515 minutes.
   - Optionally add a management command that can be invoked manually for maintenance.

2. **Expose a manual release API** *(✅ done)*
   - `POST /sales/api/sales/{sale_id}/abandon/` now wraps `sale.release_reservations()`, cancels the draft, and returns the released quantities.
   - Front-end should call this whenever a cashier cancels or replaces a cart.

3. **Update POS UI**
   - Show `unreserved` vs `reserved` counts per item.
   - When a reservation failure occurs (HTTP 400 with `INSUFFICIENT_STOCK`), surface the user-friendly `error` message and optionally display the list of reservations for context.

4. **Educate staff**
   - Draft/partial sales are operationally equivalent to items being on hold.
   - Encourage staff to finalize or discard drafts rapidly to keep stock accurate.

## 7. Quick reference snippets

- **Creating a reservation**: handled automatically by `POST /sales/api/sales/{sale_id}/add_item/` when a `stock_product` is supplied.
- **Releasing on completion**: automatic via `sale.complete_sale()`.
- **Automatic expiry**: must be scheduled using `StockReservation.release_expired()`.
- **Manual release**: use `POST /sales/api/sales/{sale_id}/abandon/` for draft cancellations.
- **Investigating discrepancies**: use `test_stock_availability.py` patterns or run `Sale.objects.filter(status='DRAFT')` and inspect related reservations.

## 8. Frequently asked questions

**Q: Why does the POS show 51 units when adding a product fails?**  
A: The 51 reflects the storefronts on-hand balance. However, 45 units are reserved by draft sales (`reserved_quantity=45`), leaving only 6 units truly available. When the cashier tries to add 5 units to a new sale, the backend considers `available=6` so the add is allowed. If they exceed 6 units the request fails with `INSUFFICIENT_STOCK`.

**Q: What happens if the browser closes mid-transaction?**  
A: The reservations remain `ACTIVE` until the 30-minute expiry job runs. During that window stock appears depleted. Staff should have a way to reopen the draft or discard it.

**Q: Can the front-end delete the sale to free stock?**  
A: Deleting the sale alone is insufficient because reservations reference the sale by string ID. Always release reservations before deleting or cancelling the sale.

---

By aligning the front-end workflow with the reservation lifecycles expectations—and by adding a manual release pathway—we can ensure stock levels in the POS stay trustworthy while still protecting against overselling.
