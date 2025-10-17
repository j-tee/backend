# Warehouse Stock Transfer API: Actual Implementation

## Overview
This documentation describes the **actual** backend implementation for warehouse stock transfers. It clarifies the available endpoints, expected workflows, and provides examples for the frontend team. This supersedes any previous documentation that referenced a custom `/transfer/` endpoint.

---

## 1. No Custom Transfer Endpoint
- The endpoint `POST /inventory/api/stock-adjustments/transfer/` is **NOT** currently available in the backend.
- Any attempt to use this endpoint will result in a `405 Method Not Allowed` error.

---

## 2. How Warehouse Transfers Are Implemented
- Warehouse transfers are handled by creating **two** StockAdjustment records:
  - One `TRANSFER_OUT` adjustment for the source warehouse (negative quantity)
  - One `TRANSFER_IN` adjustment for the destination warehouse (positive quantity)
- Both adjustments should use the same `reference_number` to link them as a single transfer event.

---

## 3. API Endpoints to Use

### Create a Stock Adjustment
**Endpoint:**
`POST /inventory/api/stock-adjustments/`

**Payload Example (TRANSFER_OUT):**
```json
{
  "stock_product": "uuid-of-source-stock-product",
  "adjustment_type": "TRANSFER_OUT",
  "quantity": -10,
  "unit_cost": 5.00,
  "reference_number": "TRF-20251016-001",
  "reason": "Transfer to Warehouse B"
}
```

**Payload Example (TRANSFER_IN):**
```json
{
  "stock_product": "uuid-of-destination-stock-product",
  "adjustment_type": "TRANSFER_IN",
  "quantity": 10,
  "unit_cost": 5.00,
  "reference_number": "TRF-20251016-001",
  "reason": "Transfer from Warehouse A"
}
```

**Response Example:**
```json
{
  "id": "uuid",
  "adjustment_type": "TRANSFER_OUT",
  // ...other fields
}
```

---

### List All Adjustments (Including Transfers)
**Endpoint:**
`GET /inventory/api/stock-adjustments/`

**Query Parameters:**
- `adjustment_type=TRANSFER_OUT` or `TRANSFER_IN` (to filter for transfers)
- `reference_number=...` (to find paired adjustments)

---

## 4. Workflow for Warehouse Transfers
1. **Frontend** creates two adjustments (one out, one in) using the standard endpoint above.
2. Both adjustments use the same `reference_number` for traceability.
3. The frontend can display, link, and audit transfers by filtering on `reference_number` and `adjustment_type`.

---

## 5. Future Plans
- If a custom `/transfer/` endpoint is required, the backend team will communicate its availability and provide updated documentation and payload formats.
- Until then, **use the standard adjustment endpoint as described above**.

---

## 6. Contact
If you have questions or need changes to the workflow, please contact the backend team.

---

**This documentation reflects the actual, current backend implementation.**
