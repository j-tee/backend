# Proposal: Implement a Dedicated Warehouse Transfer API Endpoint

## Purpose
This document proposes the implementation of a dedicated API endpoint for warehouse stock transfers, outlining the benefits, recommended design, and impact on both backend and frontend workflows.

---

## 1. Problem Statement
- The current workflow requires the frontend to create two separate StockAdjustment records (TRANSFER_OUT and TRANSFER_IN) and manually link them by `reference_number`.
- This approach increases the risk of:
  - Incomplete or mismatched transfers
  - Data inconsistency if one adjustment fails
  - Complex frontend logic and error handling

---

## 2. Superior Solution: Custom Transfer Endpoint
### Recommended Endpoint
`POST /inventory/api/stock-adjustments/transfer/`

### Features
- Accepts a single payload describing both source and destination warehouse details.
- Atomically creates both paired adjustments in one transaction.
- Returns both records in the response, ensuring traceability and consistency.
- Reduces frontend complexity and risk of partial transfers.

---

## 3. Example Payload
```json
{
  "source_stock_product": "uuid-of-source-stock-product",
  "destination_stock_product": "uuid-of-destination-stock-product",
  "quantity": 10,
  "unit_cost": 5.00,
  "reference_number": "TRF-20251016-001",
  "reason": "Transfer from Warehouse A to B"
}
```

### Example Response
```json
{
  "transfer_out": {
    "id": "uuid-1",
    "adjustment_type": "TRANSFER_OUT",
    // ...other fields
  },
  "transfer_in": {
    "id": "uuid-2",
    "adjustment_type": "TRANSFER_IN",
    // ...other fields
  }
}
```

---

## 4. Benefits
- **Atomicity:** Both adjustments are created together, preventing partial transfers.
- **Simplicity:** Frontend only needs to make one API call per transfer.
- **Consistency:** Backend enforces correct linkage and business rules.
- **Auditability:** Easier to track and report on transfers.

---

## 5. Implementation Notes
- The backend should validate both stock products and ensure sufficient stock in the source warehouse.
- The endpoint should return appropriate error messages for validation failures.
- The transaction should be rolled back if any part of the transfer fails.

---

## 6. Recommendation
The backend team is strongly encouraged to implement this endpoint to:
- Improve data integrity
- Simplify frontend development
- Reduce support and debugging overhead

---

## 7. Next Steps
- Review this proposal and discuss with stakeholders.
- Estimate development effort and timeline.
- Communicate changes and update documentation upon implementation.

---

**This proposal is intended to align backend and frontend workflows for robust, efficient warehouse transfer management.**
