# Warehouse Stock Transfer API: Frontend Integration Guide

## Overview
This guide describes the backend API for warehouse stock transfers, including available endpoints, payloads, responses, and workflow. It is intended for frontend developers integrating warehouse transfer functionality.

---

## 1. Endpoint

**POST /inventory/api/stock-adjustments/transfer/**

Creates a paired warehouse transfer (TRANSFER_OUT and TRANSFER_IN) in a single atomic operation.

---

## 2. Request Payload

```json
{
  "product_id": "<uuid-of-product>",
  "from_warehouse_id": "<uuid-of-source-warehouse>",
  "to_warehouse_id": "<uuid-of-destination-warehouse>",
  "quantity": 10,
  "unit_cost": "12.50", // Optional, uses source cost if omitted
  "reason": "Transfer from Warehouse A to B"
}
```

- `product_id`: UUID of the product to transfer
- `from_warehouse_id`: UUID of the source warehouse
- `to_warehouse_id`: UUID of the destination warehouse
- `quantity`: Number of units to transfer (must be positive)
- `unit_cost`: Cost per unit (optional)
- `reason`: Reason for transfer (optional)

---

## 3. Response

**Success (201 Created):**
```json
{
  "success": true,
  "transfer_reference": "IWT-XXXXXXXXXX",
  "out_adjustment_id": "<uuid>",
  "in_adjustment_id": "<uuid>",
  "source_stock_id": "<uuid>",
  "dest_stock_id": "<uuid>",
  "message": "Transferred 10 units of Widget from Warehouse A to Warehouse B."
}
```

**Error (400/404):**
```json
{
  "error": "Missing or invalid parameters."
}
```

---

## 4. Workflow
1. Frontend sends a POST request to `/inventory/api/stock-adjustments/transfer/` with the payload above.
2. Backend validates input, checks stock, and creates paired adjustments atomically.
3. On success, both adjustments are created and stock quantities updated.
4. Use the returned `transfer_reference` to link and audit the transfer event.

---

## 5. Listing Transfers
- All transfer adjustments are available via `GET /inventory/api/stock-adjustments/`.
- Filter by `adjustment_type=TRANSFER_OUT` or `TRANSFER_IN` and/or `reference_number` to find paired records.

---

## 6. Notes
- Transfers are atomic: both adjustments succeed or fail together.
- The endpoint enforces business rules and stock validation.
- No separate transfer endpoint or file exists; all logic is unified under stock adjustments.

---

## 7. Example Usage

**Create Transfer:**
```js
fetch('/inventory/api/stock-adjustments/transfer/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    product_id: '...',
    from_warehouse_id: '...',
    to_warehouse_id: '...',
    quantity: 10,
    reason: 'Routine transfer'
  })
})
.then(res => res.json())
.then(data => console.log(data));
```

---

## 8. Contact
For questions or issues, contact the backend team.

---

**This guide reflects the current backend implementation for warehouse stock transfers.**
