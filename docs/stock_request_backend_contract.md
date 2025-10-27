# Stock Request & Transfer Workflow Contract (Backend Reference)

_Last updated: 2025-10-03_

This document summarises the current backend contracts for the warehouse → storefront fulfilment flow. It consolidates everything a frontend integration needs to rebuild Redux slices, API helpers, and TypeScript models under the “Stock Request” banner while the backend continues to expose the legacy `TransferRequest` and `Transfer` endpoints.

The pipeline still has **two cooperating resources**:

1. **Stock Requests** (`TransferRequest` model) — created by storefront staff to signal demand.
2. **Transfers** (`Transfer` model) — created by managers (or automation) to fulfil the demand by allocating warehouse stock and shipping inventory to the storefront.

Both resources are linked via a nullable `Transfer.request` one-to-one field. When the link exists, lifecycle events on either side keep the other entity in sync.

---

## 1. Status lifecycle

### 1.1 Stock request statuses (`TransferRequest.status`)

| Status | Meaning | Transitions |
| ------ | ------- | ----------- |
| `NEW` | Request has been created by storefront staff (or managers on their behalf). | `ASSIGNED` (when a transfer is linked) · `CANCELLED` (user cancels before fulfilment) |
| `ASSIGNED` | A transfer now owns the request. Request waits for warehouse fulfilment. | `FULFILLED` (after dispatch/receipt) · `CANCELLED` (manager cancels) |
| `FULFILLED` | Request is satisfied. Set automatically when the linked transfer finishes and requester confirms receipt. | _(terminal)_ |
| `CANCELLED` | Request was cancelled by staff or management. | _(terminal)_ |

### 1.2 Transfer statuses (`Transfer.status`)

| Status | Meaning | Transitions |
| ------ | ------- | ----------- |
| `DRAFT` | Manager is drafting quantities/destinations. | `REQUESTED` (submit) · `CANCELLED` |
| `REQUESTED` | Awaiting approval by privileged roles. | `APPROVED` (approve) · `REJECTED` (reject) · `CANCELLED` |
| `APPROVED` | Ready to dispatch goods; quantities may be adjusted. | `IN_TRANSIT` (dispatch) · `CANCELLED` |
| `IN_TRANSIT` | Stock has been deducted from warehouse and is travelling. | `COMPLETED` (complete) · `CANCELLED` |
| `COMPLETED` | Goods have landed in storefront inventory. | `IN_TRANSIT` (rare correction) |
| `REJECTED` | Approval step failed; transfer can be edited or resubmitted. | `DRAFT` (edit) · `REQUESTED` (resubmit) |
| `CANCELLED` | Transfer aborted after submission. Stock is returned if already deducted. | _(terminal)_ |

**Receipting:** Requesters call `confirm-receipt`, which stamps `received_by`, `received_at`, logs an audit entry, bumps any linked request to `FULFILLED`, and stabilises the transfer status (typically `COMPLETED`).

---

## 2. REST endpoints

Base prefix: `/inventory/api/`

### 2.1 Stock request endpoints (`TransferRequestViewSet`)

| Method & Path | Purpose | Notes |
| ------------- | ------- | ----- |
| `GET /transfer-requests/` | List & filter (`status`, `storefront`, `priority`). | Business-scoped; pagination via `page`/`page_size`. |
| `POST /transfer-requests/` | Create a new request. | Body matches serializer (see §3.1). Caller must be assigned to the storefront or be a manager/owner. |
| `GET /transfer-requests/{id}/` | Retrieve single request. | Includes nested `line_items`. |
| `PATCH /transfer-requests/{id}/` | Update priority/notes/line items while `status=NEW`. | Managers can adjust beyond `NEW`. |
| `POST /transfer-requests/{id}/cancel/` | Cancel request (`NEW`/`ASSIGNED`). | Clears transfer link if present. |
| `POST /transfer-requests/{id}/fulfill/` | Mark request fulfilled when linked transfer is `IN_TRANSIT`/`COMPLETED`. | Requester or manager roles only. |
| `POST /transfer-requests/{id}/update-status/` | Manually update request status (manager override). | Accepts `status` (NEW/ASSIGNED/FULFILLED/CANCELLED) and optional `force` flag. Manager-only endpoint. |

> **Assumption for redux**: Build a slice keyed by request `status`, `priority`, and storefront filters. Each request returns `linked_transfer_reference` + `linked_transfer_id` (derived client-side from embedded transfer when API includes it).

### 2.2 Transfer endpoints (`TransferViewSet`)

| Method & Path | Purpose | Notes |
| ------------- | ------- | ----- |
| `GET /transfers/` | List transfers with filters (`status`, `source_warehouse`, `destination_storefront`). | Includes `line_items` with requested/approved/fulfilled quantities. |
| `POST /transfers/` | Create transfer draft. | If payload includes `request`, the backend links the corresponding stock request and pushes it to `ASSIGNED`. |
| `GET /transfers/{id}/` | Fetch transfer details and audit log. | Serializer returns nested `line_items`, `audit_entries`, timestamps, and role metadata. |
| `PATCH /transfers/{id}/` | Update draft/rejected transfers (edit quantities, notes, linking). | Disallowed once status leaves editable states. |
| `DELETE /transfers/{id}/` | Remove draft/rejected transfer. | Managers or above. |
| `POST /transfers/{id}/submit/` | Transition `DRAFT|REJECTED → REQUESTED`. | Sets `submitted_at`, emitter audit entry. |
| `POST /transfers/{id}/approve/` | Transition `REQUESTED → APPROVED`. | Accepts optional `line_items[]` payload with `approved_quantity`. |
| `POST /transfers/{id}/reject/` | Transition `REQUESTED → REJECTED`. | Requires `reason`. |
| `POST /transfers/{id}/dispatch/` | Transition `APPROVED → IN_TRANSIT`. | Deducts stock; accepts `line_items[]` with `fulfilled_quantity`. |
| `POST /transfers/{id}/complete/` | Transition `IN_TRANSIT → COMPLETED`. | Optional `line_items[]`; credits storefront stock. |
| `POST /transfers/{id}/cancel/` | Abort transfer. | Restores warehouse quantities when required. |
| `POST /transfers/{id}/confirm-receipt/` | Requester acknowledgement. | Optional `notes`. |

### 2.3 Workspace dashboard

`GET /inventory/api/employee/workspace/` supplies the aggregated dashboard for staff & managers. See §3.3 for field shape. Owners still use `/inventory/api/owner/workspace/`.

### 2.4 Manual status update (manager override)

The `POST /inventory/api/transfer-requests/{id}/update-status/` endpoint allows managers and above to manually adjust stock request status when workflow automation fails or manual intervention is required.

**Request body:**

```json
{
  "status": "FULFILLED",
  "force": false
}
```

**Parameters:**
- `status` (required): One of `NEW`, `ASSIGNED`, `FULFILLED`, `CANCELLED`
- `force` (optional, default `false`): Set to `true` to override terminal state protections (e.g., changing from `FULFILLED` back to `NEW`)

**Response (200 OK):**

```json
{
  "...standard request fields...",
  "_status_change": {
    "old_status": "ASSIGNED",
    "new_status": "FULFILLED",
    "changed_by": "Manager Name"
  }
}
```

**Common scenarios:**

| Goal | Payload | Effect |
| ---- | ------- | ------ |
| Mark as fulfilled without transfer | `{"status": "FULFILLED"}` | Sets `fulfilled_at`, `fulfilled_by` to current time/user |
| Reset to NEW | `{"status": "NEW"}` | Clears assignment, removes transfer link |
| Force-reset from FULFILLED | `{"status": "NEW", "force": true}` | Overrides terminal state protection |
| Mark as assigned manually | `{"status": "ASSIGNED"}` | Sets `assigned_at` without requiring a transfer link |

**Error responses:**

| Scenario | Status | Response |
| -------- | ------ | -------- |
| Invalid status value | `400` | `{"status": "Invalid status. Must be one of: NEW, ASSIGNED, FULFILLED, CANCELLED"}` |
| Changing from FULFILLED without force | `400` | `{"status": "Cannot change status from FULFILLED. Use force=true to override."}` |
| Non-manager attempts update | `403` | `{"detail": "You do not have the required role for this action."}` |

---

## 3. Payload shape highlights

The API uses the Django REST Framework serializers `TransferRequestSerializer` and `TransferSerializer`. Important fields for the frontend are documented below and align with the TypeScript interfaces already included in `docs/transfer_approvals_receipt_dashboard.md` (§4).

### 3.1 Stock request payload (`TransferRequestSerializer`)

```jsonc
{
  "id": "<uuid>",
  "business": "<uuid>",
  "storefront": "<uuid>",
  "storefront_name": "Downtown Store",
  "requested_by": "<uuid>",
  "requested_by_name": "Alice",
  "priority": "HIGH",
  "status": "ASSIGNED",
  "notes": "Need promotional stock",
  "linked_transfer_reference": "TRF-20251003-XYZ890",
  "linked_transfer_id": "<uuid or null>",
  "assigned_at": "2025-10-03T09:31:03Z",
  "fulfilled_at": null,
  "fulfilled_by": "<uuid>",
  "cancelled_at": null,
  "line_items": [
    {
      "id": "<uuid>",
      "product": "<uuid>",
      "product_name": "Sparkle Orange Juice",
      "requested_quantity": 24,
      "approved_quantity": 20,
      "fulfilled_quantity": 20,
      "unit_of_measure": "carton",
      "notes": null
    }
  ],
  "created_at": "2025-10-02T10:20:10Z",
  "updated_at": "2025-10-03T09:45:11Z"
}
```

### 3.2 Transfer payload (`TransferSerializer`)

```jsonc
{
  "id": "<uuid>",
  "reference": "TRF-20251003-XYZ890",
  "business": "<uuid>",
  "status": "IN_TRANSIT",
  "source_warehouse": "<uuid>",
  "source_warehouse_name": "Main Warehouse",
  "destination_storefront": "<uuid>",
  "destination_storefront_name": "Downtown Store",
  "request": "<uuid or null>",
  "requested_by": "<uuid>",
  "requested_by_name": "Manager Mike",
  "approved_by": "<uuid>",
  "fulfilled_by": "<uuid>",
  "received_by": null,
  "submitted_at": "2025-10-03T09:31:03Z",
  "approved_at": "2025-10-03T09:35:03Z",
  "dispatched_at": "2025-10-03T09:40:03Z",
  "completed_at": null,
  "received_at": null,
  "notes": "Urgent restock",
  "line_items": [
    {
      "id": "<uuid>",
      "product": "<uuid>",
      "product_name": "Sparkle Orange Juice",
      "requested_quantity": 24,
      "approved_quantity": 20,
      "fulfilled_quantity": 20,
      "unit_of_measure": "carton",
      "notes": null
    }
  ],
  "audit_log": [
    {
      "action": "SUBMITTED",
      "actor": "<uuid>",
      "actor_name": "Manager Mike",
      "remarks": null,
      "created_at": "2025-10-03T09:31:05Z"
    },
    {
      "action": "DISPATCHED",
      "actor": "<uuid>",
      "actor_name": "Warehouse Sam",
      "remarks": null,
      "created_at": "2025-10-03T09:40:04Z"
    }
  ],
  "created_at": "2025-10-03T09:25:00Z",
  "updated_at": "2025-10-03T09:40:05Z"
}
```

### 3.3 Employee workspace response (excerpt)

See the detailed schema already published in `docs/transfer_approvals_receipt_dashboard.md` §3.1. Key for the UI slices:

- `businesses[*].transfer_requests.by_status` → aggregate counts for badge counters.
- `businesses[*].transfers.by_status` → progress widgets.
- `pending_approvals` (managers only) → feed for approval inbox.
- `incoming_transfers` → restful list of in-flight/completed transfers directed to the user’s storefronts.
- `my_transfer_requests` → quick access to the requester’s recent submissions.

---

## 4. Frontend reconstruction notes

- Keep separate Redux slices or RTK Query endpoints for **stock requests** and **transfers**; the backend still delivers both resources independently. The “Stock Request” product umbrella refers to the combination of both experiences rather than a single API entity.
- When rebranding UI copy to “Stock requests”, you can alias the old endpoints in your client services (e.g. `fetchStockRequests = inventoryService.listTransferRequests`).
- Use the TypeScript interfaces from `docs/transfer_approvals_receipt_dashboard.md` §4. They already include the audit log, receipt metadata, and workspace summaries expected by the dashboard pages.
- Confirmation of existing endpoints: both `/inventory/api/transfers/` and `/inventory/api/transfer-requests/` remain intact. No new consolidated endpoint has been introduced yet, so the frontend should keep orchestrating both collections.
- Migration path toward a unified “Stock Request” view can happen at the client level first (rename Redux slices/selectors, but continue calling the same URLs). Future backend refactors (e.g. renaming models) will ship with compatibility wrappers and version notes before the endpoints change.

---

## 5. Suggested UI wiring (quick start)

1. **Services:** expose `listStockRequests`, `createStockRequest`, `cancelStockRequest`, `fulfillStockRequest`, `listTransfers`, `createTransfer`, and workflow helpers (`submitTransfer`, `approveTransfer`, etc.). They should map one-to-one to the endpoints above.
2. **Slices:**
   - `stockRequests` slice keyed by `status`, `storefront`, `priority` filters.
   - `transfers` slice keyed by `status`, `destination_storefront`, plus `pendingApprovals` derived selector for managers.
   - `workspace` slice storing the payload from `/employee/workspace/` for dashboard widgets.
3. **Pages:**
   - `StockRequestsPage` surfaces the request grid (list + call-to-action to draft transfers).
   - `TransferApprovalsPage` (or rename of `TransfersPage`) operates the approval → dispatch workflow.
   - `IncomingTransfersPage` (or part of dashboard) consumes `incoming_transfers` and `confirm-receipt` action.

By aligning with this contract you can reintroduce any missing slices and selectors while confidently migrating UI messaging to “Stock Requests” without waiting on additional backend changes.
