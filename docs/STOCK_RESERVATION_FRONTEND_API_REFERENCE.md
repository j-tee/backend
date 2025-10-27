# POS Reservation Workflow – Frontend API Reference

This document lists everything a frontend engineer needs from the backend to implement a reservation-aware POS experience. It splits the information into:

1. **Existing APIs** you can call today.
2. **Payload & error reference** so you can wire success and failure states correctly.
3. **Gaps we (backend) still need to close** to support a smooth "discard sale" flow.
4. **Integration blueprint** that ties the endpoints together for day-to-day POS usage.

---

## 1. Existing endpoints

All endpoints require an authenticated session (standard DRF auth). UUIDs are returned as strings.

### 1.1 Create a draft sale (cart)
`POST /sales/api/sales/`

Purpose: start a new cart and receive the sale ID the frontend must pass into subsequent calls.

Example request:
```json
{
  "storefront": "<storefront_uuid>",
  "customer": null,
  "payment_type": "CASH",
  "notes": "optional"
}
```

Response `201 Created` (excerpt):
```json
{
  "id": "0f4dc1d2-a12b-4c6d-8b43-dc91a74e76ff",
  "storefront": "<storefront_uuid>",
  "status": "DRAFT",
  "subtotal": 0,
  "amount_due": 0,
  "line_items": []
}
```

Notes:
- `business` and `user` default from the authenticated user’s active membership.
- `status` is `DRAFT` until checkout.

### 1.2 Fetch an existing sale/cart
`GET /sales/api/sales/{sale_id}/`

Returns the same shape as above, including `line_items` and `payments`. Use this to restore a cart when the UI reloads.

### 1.3 Add item to sale (creates reservation)
`POST /sales/api/sales/{sale_id}/add_item/`

Request body:
```json
{
  "product": "<product_uuid>",
  "stock_product": "<stock_product_uuid>",
  "quantity": "5",
  "unit_price": "65.00"
}
```

#### Success `201 Created`
Returns a `SaleItem` payload (includes `stock_product`, `quantity`, `total_price`, etc.). Stock is reserved immediately for the requested quantity.

#### Failure – insufficient stock `400 Bad Request`
```json
{
  "error": "Unable to add item due to stock restrictions.",
  "code": "INSUFFICIENT_STOCK",
  "developer_message": "Insufficient stock. Available: 1.00, Requested: 5.00",
  "details": {
    "available": "1.00",
    "requested": "5.00",
    "stock_product_id": "<stock_product_uuid>",
    "product_id": "<product_uuid>"
  }
}
```
Use `error` for user messaging (e.g., toast) and log/display `developer_message` & `details` for diagnostics.

### 1.4 Update item quantity
`PATCH /sales/api/sale-items/{sale_item_id}/`

Body can include `quantity`, `unit_price`, etc. When reducing quantity, you must separately release the extra reservation (see section 3). **Current backend behaviour does not automatically release when quantity drops**, so plan to call the future release endpoint.

### 1.5 Remove item
`DELETE /sales/api/sale-items/{sale_item_id}/`

Delete the line from the sale. Reservations remain `ACTIVE` until we expose a manual release action (section 3).

### 1.6 Complete checkout (commits stock & releases reservations)
`POST /sales/api/sales/{sale_id}/complete/`

Example request:
```json
{
  "payment_type": "CASH",
  "payments": [
    {"amount_paid": "325.00", "payment_method": "CASH"}
  ],
  "notes": "optional"
}
```

- Success returns the full sale with updated status (`COMPLETED`, `PARTIAL`, or `PENDING`).
- On success, `sale.release_reservations()` runs automatically.
- On failure, check `developer_message` for context (credit limit breaches, etc.).

### 1.7 Storefront availability insight
`GET /inventory/api/storefronts/{storefront_id}/stock-products/{product_id}/availability/`

Response sample:
```json
{
  "total_available": 51,
  "reserved_quantity": 45,
  "unreserved_quantity": 6,
  "reservations": [
    {
      "id": "df79...",
      "sale_id": "a6cd...",
      "quantity": 5,
      "customer_name": "John Mensah",
      "expires_at": "2025-10-08T12:30:00Z"
    },
    ...
  ],
  "batches": [
    {
      "id": "<stock_product_uuid>",
      "quantity": 11,
      "retail_price": "65.00",
      "warehouse": "Main Warehouse"
    }
  ]
}
```

Use this to display the real sellable quantity (`unreserved_quantity`) and list the carts that are holding stock.

### 1.8 Release expired reservations (backend maintenance)
`StockReservation.release_expired()` is a backend utility, not a public endpoint. We need to run it on a schedule (cron / Celery). Until that happens, stale drafts will keep stock locked for 30 minutes.

### 1.9 Abandon sale and release reservations
`POST /sales/api/sales/{sale_id}/abandon/`

Purpose: manually cancel a draft sale and free all associated reservations immediately.

Request body: empty object `{}` (payload optional).

Success `200 OK` response (excerpt):
```json
{
  "message": "Sale cancelled and reservations released.",
  "sale": {
    "id": "0f4dc1d2-a12b-4c6d-8b43-dc91a74e76ff",
    "status": "CANCELLED",
    "line_items": [...]
  },
  "released": {
    "count": 2,
    "total_quantity": "7.00",
    "reservations": [
      {
        "reservation_id": "...",
        "stock_product_id": "...",
        "product_id": "...",
        "product_name": "Wireless Router",
        "quantity": "5.00",
        "expires_at": "2025-10-08T12:30:00Z"
      }
    ]
  }
}
```

If the sale is not in `DRAFT` (or is already `CANCELLED`), the endpoint returns `400 Bad Request` with `code="INVALID_SALE_STATUS"` and includes the current status for diagnostics. Repeat calls on a cancelled sale are safe and simply return the existing sale snapshot with zero released reservations.

---

## 2. Missing backend pieces (to be implemented)

The frontend can only offer a frictionless workflow if the backend supplies these additional APIs/features:

| Need | Suggested endpoint/action | What it should do |
| --- | --- | --- |
| Release reservation when a single line item is removed or reduced | Could extend the `abandon` action by accepting `line_item_id` filters, or add `POST /sales/api/sale-items/{item_id}/release_reservation/`. | Immediately sets the associated reservation rows to `RELEASED`. |
| Automatic expiry enforcement | Scheduler (Celery beat / cron) invoking `StockReservation.release_expired()` | Keeps stock free when carts are abandoned.
| Reservation audit visibility | Optional: `GET /sales/api/sales/{sale_id}/reservations/` | Provide a filtered view of reservations for UI panels. (Data already available via availability endpoint, so this is optional.) |

With the `abandon` endpoint shipped, the main remaining backend gap is a per-line release helper and the automated expiry job.

---

## 3. Frontend integration blueprint

1. **Start session**
   - Look up or create a draft sale via `POST /sales/api/sales/`.
   - Persist `sale_id` in the POS state (URL, Redux, etc.).

2. **Render catalogue**
   - For each product tile, call the availability endpoint lazily (on hover/details) or proactively to display both `total_available` and `unreserved_quantity`.
   - If `reserved_quantity > 0`, surface which carts own the hold.

3. **Add to cart**
   - Call `POST /sales/api/sales/{sale_id}/add_item/` with the chosen `stock_product`.
   - On error `INSUFFICIENT_STOCK`, show `error` to cashier and optionally include the reservation list from the availability endpoint.

4. **Adjust quantities**
   - Use `PATCH /sales/api/sale-items/{id}/` for increases.
   - For decreases/removals, call the upcoming release endpoint to free the unused reservation immediately.

5. **Abandon cart**
  - When the cashier cancels/ends shift, call `POST /sales/api/sales/{sale_id}/abandon/`.
  - After a successful response, refresh availability panels so the newly freed stock is visible.

6. **Checkout**
   - Collect payment info and call `POST /sales/api/sales/{sale_id}/complete/`.
   - On success, redirect/print receipt; the backend already handles inventory deduction and reservation release.

7. **Stale cart handling**
   - Display countdown UI based on `reservations[*].expires_at`.
   - Optionally poll availability; if the reservation disappears (expiry triggered), prompt the user to reload the cart state.

---

## 4. Error handling quick reference

| Scenario | Status | Code | Frontend action |
| --- | --- | --- | --- |
| Not enough stock | 400 | `INSUFFICIENT_STOCK` | Display short message from `error`, show details to power user, refresh availability panel. |
| Attempt to add item to non-draft sale | 400 | `error` = "Can only add items to draft sales" | Force refresh of cart (sale likely completed by another cashier). |
| Cart abandoned but reservations still active | 400/409 (if future per-line release endpoint rejects) | e.g., `RESERVATION_CONFLICT` | Ask user to retry after releasing residual reservations or abandon the cart. |

---

## 5. What the frontend developer needs from backend (summary)

1. **Documented existing endpoints** – covered above; these are live and ready (including the new `abandon` action).
2. **Line-item release control (optional enhancement)** – still pending if we want per-item abandonment instead of whole-sale cancellation.
3. **Scheduled job for `release_expired()`** – so the UI can trust the expiry timestamps.
4. **Optional**: telemetry endpoint for reservations if we want richer dashboards.

With the `abandon` endpoint in place, the frontend can already offer a complete cart lifecycle—provided we schedule the expiry task and, optionally, deliver finer-grained release controls.

---

For follow-up questions or to collaborate on the new endpoint contract, see `docs/STOCK_RESERVATION_AND_RELEASE_GUIDE.md` or sync with the backend team.
