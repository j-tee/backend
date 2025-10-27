# Stock Request Management - Quick Reference

## What's New (2025-10-03)

✅ **Manager Status Override Endpoint** - Manually adjust stock request status when needed  
✅ **Edit Fulfilled Requests** - Managers can directly update quantities on fulfilled requests

## Endpoints Summary

All endpoints under `/inventory/api/transfer-requests/`:

| Endpoint | Method | Role Required | Purpose |
| -------- | ------ | ------------- | ------- |
| `/` | GET | Any member | List requests with filters |
| `/` | POST | Staff+ | Create new request |
| `/{id}/` | GET | Any member | Retrieve request details |
| `/{id}/` | PATCH | Staff (own) / Manager+ | Update request |
| `/{id}/cancel/` | POST | Staff (own, NEW) / Manager+ | Cancel request |
| `/{id}/fulfill/` | POST | Requester / Manager+ | Mark as fulfilled |
| `/{id}/update-status/` | POST | **Manager+** | **Manual status override** |

## Quick Examples

### List stock requests for a storefront

```bash
GET /inventory/api/transfer-requests/?storefront={uuid}&status=NEW
```

### Create a stock request

```bash
POST /inventory/api/transfer-requests/
{
  "storefront": "storefront-uuid",
  "priority": "HIGH",
  "notes": "Need promotional stock",
  "line_items": [
    {
      "product": "product-uuid",
      "requested_quantity": 24
    }
  ]
}
```

### Cancel a request

```bash
POST /inventory/api/transfer-requests/{id}/cancel/
{}
```

### **NEW: Manually update status (Manager only)**

```bash
POST /inventory/api/transfer-requests/{id}/update-status/
{
  "status": "FULFILLED"
}
```

**With force override:**

```bash
POST /inventory/api/transfer-requests/{id}/update-status/
{
  "status": "NEW",
  "force": true
}
```

## Status Flow

```
NEW → ASSIGNED → FULFILLED
  ↓      ↓          ↓
  └──> CANCELLED <──┘
```

**Manual override capabilities:**
- Reset to `NEW` from any state (clears assignments)
- Jump to `FULFILLED` directly (sets timestamps)
- Mark as `ASSIGNED` without transfer link
- Move to `CANCELLED` administratively

## Response Shape

All endpoints return the full request object:

```json
{
  "id": "uuid",
  "business": "uuid",
  "storefront": "uuid",
  "storefront_name": "Store Name",
  "requested_by": "uuid",
  "requested_by_name": "User Name",
  "priority": "HIGH|MEDIUM|LOW",
  "status": "NEW|ASSIGNED|FULFILLED|CANCELLED",
  "notes": "text",
  "linked_transfer_reference": "TRF-20251003-ABC123",
  "linked_transfer_id": "uuid or null",
  "assigned_at": "ISO-8601 or null",
  "fulfilled_at": "ISO-8601 or null",
  "fulfilled_by": "uuid or null",
  "cancelled_at": "ISO-8601 or null",
  "cancelled_by": "uuid or null",
  "line_items": [
    {
      "id": "uuid",
      "product": "uuid",
      "product_name": "Product Name",
      "requested_quantity": 10,
      "unit_of_measure": "carton",
      "notes": "text or null"
    }
  ],
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601"
}
```

**Status update response includes:**

```json
{
  "...all standard fields...",
  "_status_change": {
    "old_status": "ASSIGNED",
    "new_status": "FULFILLED",
    "changed_by": "Manager Name"
  }
}
```

## Role Permissions

| Role | Create | Update Own | Cancel Own | Fulfill | Update Status | **Edit FULFILLED** |
| ---- | ------ | ---------- | ---------- | ------- | ------------- | ------------------ |
| STAFF | ✅ | ✅ (NEW only) | ✅ (NEW only) | ✅ (requester) | ❌ | ❌ |
| MANAGER | ✅ | ✅ | ✅ | ✅ | ✅ | **✅** |
| ADMIN | ✅ | ✅ | ✅ | ✅ | ✅ | **✅** |
| OWNER | ✅ | ✅ | ✅ | ✅ | ✅ | **✅** |

## Common Use Cases

### 1. Staff creates request → Manager fulfills via transfer

```
1. POST /transfer-requests/ (staff)
   → status: NEW

2. POST /transfers/ with request_id (manager)
   → request status: ASSIGNED

3. POST /transfers/{id}/submit/ (manager)
4. POST /transfers/{id}/approve/ (manager)
5. POST /transfers/{id}/dispatch/ (manager)
   → transfer status: IN_TRANSIT

6. POST /transfers/{id}/confirm-receipt/ (staff)
   → request status: FULFILLED
```

### 2. Manager manually marks request as fulfilled

```
1. POST /transfer-requests/ (staff)
   → status: NEW

2. POST /transfer-requests/{id}/update-status/ (manager)
   { "status": "FULFILLED" }
   → request status: FULFILLED
   → No transfer needed
```

### 3. Fixing stuck request

```
1. Request is stuck in ASSIGNED but transfer was deleted
   
2. POST /transfer-requests/{id}/update-status/ (manager)
   { "status": "NEW" }
   → Clears assignment
   → Request can be reassigned
```

### 4. **NEW: Correcting fulfilled request quantities**

```
1. Request fulfilled with 20 cables (staff over-requested)

2. PATCH /transfer-requests/{id}/ (manager)
   {
     "notes": "Adjusted - only need 10",
     "line_items": [{
       "id": "line-item-uuid",
       "product": "product-uuid",
       "requested_quantity": 10,
       "notes": "Reduced from 20 to 10"
     }]
   }
   → Quantities updated
   → Request still FULFILLED
   → Inventory calculations use new quantity
```

## Documentation Index

1. **Backend Contract** - `docs/stock_request_backend_contract.md`
   - Complete endpoint reference
   - Payload schemas
   - TypeScript interfaces

2. **Manager Status Override** - `docs/stock_request_status_management.md`
   - Detailed use cases
   - Frontend integration examples
   - Security considerations

3. **Editing Fulfilled Requests** - `docs/editing_fulfilled_requests.md`
   - Manager quantity adjustments
   - Frontend integration guide
   - Best practices and audit trail

4. **Transfer Workflow** - `docs/transfer_approvals_receipt_dashboard.md`
   - Manager approval flow
   - Receipt confirmation
   - Employee workspace dashboard

5. **Storefront Integration** - `docs/storefront-warehouse-integration.md`
   - Business context
   - Warehouse/storefront relationship

## Testing

Run the full test suite:

```bash
python manage.py test inventory.tests.TransferRequestWorkflowAPITest
```

Current coverage:
- ✅ Create request (staff)
- ✅ Link to transfer (manager)
- ✅ Receipt confirmation
- ✅ Stock adjustments
- ✅ Workspace dashboard updates
- ✅ Cancel request
- ✅ **Manual status update (manager)**
- ✅ **Permission enforcement**
- ✅ **Invalid status rejection**

---

**Last updated:** 2025-10-03  
**Tests passing:** 8/8 ✅
