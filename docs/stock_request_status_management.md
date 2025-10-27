# Stock Request Status Management (Manager Override)

_Feature added: 2025-10-03_

This document describes the new manual status update capability for stock requests, allowing managers to override workflow states when needed.

---

## Overview

Managers (roles: `OWNER`, `ADMIN`, `MANAGER`) can now manually adjust stock request status using a dedicated endpoint. This is useful for:

- **Resolving stuck workflows:** When automation fails or transfers are completed outside the system
- **Manual fulfillment:** Marking requests as fulfilled when stock arrives through alternative channels
- **Corrections:** Resetting erroneous states or clearing assignments
- **Administrative overrides:** Handling edge cases that don't fit the normal workflow

The endpoint respects role-based access control and includes safety guards to prevent accidental state changes.

---

## API endpoint

```
POST /inventory/api/transfer-requests/{id}/update-status/
```

**Authentication:** Token required  
**Authorization:** Manager roles only (`OWNER`, `ADMIN`, `MANAGER`)

### Request body

```json
{
  "status": "FULFILLED",
  "force": false
}
```

**Fields:**
- `status` (required): Target status value
  - Valid values: `NEW`, `ASSIGNED`, `FULFILLED`, `CANCELLED`
- `force` (optional, default `false`): Override terminal state protection
  - Set to `true` to allow transitions from `FULFILLED` status

### Response (200 OK)

```json
{
  "id": "a1b2c3d4...",
  "status": "FULFILLED",
  "fulfilled_at": "2025-10-03T14:30:00Z",
  "fulfilled_by": "manager-uuid",
  "...other request fields...",
  "_status_change": {
    "old_status": "ASSIGNED",
    "new_status": "FULFILLED",
    "changed_by": "Manager Name"
  }
}
```

The `_status_change` object provides audit context for the UI to display what changed and who made the change.

### Error responses

| HTTP Status | Scenario | Response Body |
| ----------- | -------- | ------------- |
| `400` | Invalid status value | `{"status": "Invalid status. Must be one of: NEW, ASSIGNED, FULFILLED, CANCELLED"}` |
| `400` | Terminal state protection | `{"status": "Cannot change status from FULFILLED. Use force=true to override."}` |
| `400` | Missing status field | `{"status": "This field is required."}` |
| `403` | Non-manager user | `{"detail": "You do not have the required role for this action."}` |

---

## Status transitions

### Manual fulfillment (ASSIGNED → FULFILLED)

**Use case:** Transfer was completed outside the system, and you need to close the request.

```json
POST /transfer-requests/{id}/update-status/
{
  "status": "FULFILLED"
}
```

**Effect:**
- Sets `fulfilled_at` to current timestamp
- Sets `fulfilled_by` to the manager performing the action
- Request moves to terminal `FULFILLED` state

### Reset to NEW (any status → NEW)

**Use case:** Clear assignment or undo a mistaken status change.

```json
POST /transfer-requests/{id}/update-status/
{
  "status": "NEW"
}
```

**Effect:**
- Clears any transfer link (`linked_transfer_reference` → `null`)
- Resets `assigned_at` to `null`
- Request returns to initial `NEW` state

If the request is currently `FULFILLED`, you must include `"force": true`:

```json
POST /transfer-requests/{id}/update-status/
{
  "status": "NEW",
  "force": true
}
```

### Manual assignment (NEW → ASSIGNED)

**Use case:** Reserve the request for a transfer you're about to create, or mark it as "in progress" without linking a transfer yet.

```json
POST /transfer-requests/{id}/update-status/
{
  "status": "ASSIGNED"
}
```

**Effect:**
- Sets `assigned_at` to current timestamp (if not already set)
- Request moves to `ASSIGNED` state
- Note: Does not create or link a transfer automatically

### Mark as cancelled

**Use case:** Administratively cancel a request.

```json
POST /transfer-requests/{id}/update-status/
{
  "status": "CANCELLED"
}
```

**Effect:**
- Calls the model's `mark_cancelled` method
- Sets `cancelled_at` and `cancelled_by`
- Clears any transfer links
- Request moves to terminal `CANCELLED` state

---

## Frontend integration

### Service helper

```typescript
export async function updateStockRequestStatus(
  requestId: string,
  status: 'NEW' | 'ASSIGNED' | 'FULFILLED' | 'CANCELLED',
  force?: boolean
): Promise<TransferRequest> {
  const response = await apiClient.post(
    `/inventory/api/transfer-requests/${requestId}/update-status/`,
    { status, force }
  );
  return response.data;
}
```

### UI patterns

**Action button example:**

```tsx
<Button
  onClick={async () => {
    try {
      const updated = await updateStockRequestStatus(request.id, 'FULFILLED');
      // Show success notification
      toast.success(`Request ${updated.id} marked as fulfilled`);
      // Refresh the request list
      refetchRequests();
    } catch (error) {
      if (error.response?.status === 400 && error.response.data.status?.includes('force')) {
        // Prompt user for confirmation
        if (confirm('This request is already fulfilled. Reset anyway?')) {
          const updated = await updateStockRequestStatus(request.id, 'FULFILLED', true);
          refetchRequests();
        }
      } else {
        toast.error('Failed to update status: ' + error.message);
      }
    }
  }}
>
  Mark as Fulfilled
</Button>
```

**Status badge with action menu:**

Display current status alongside quick actions:

```tsx
<div className="flex items-center gap-2">
  <StatusBadge status={request.status} />
  
  {isManager && (
    <DropdownMenu>
      <DropdownMenuTrigger>⋮</DropdownMenuTrigger>
      <DropdownMenuContent>
        {request.status !== 'NEW' && (
          <DropdownMenuItem onClick={() => updateStatus('NEW')}>
            Reset to NEW
          </DropdownMenuItem>
        )}
        {request.status !== 'FULFILLED' && (
          <DropdownMenuItem onClick={() => updateStatus('FULFILLED')}>
            Mark Fulfilled
          </DropdownMenuItem>
        )}
        {request.status !== 'CANCELLED' && (
          <DropdownMenuItem onClick={() => updateStatus('CANCELLED')}>
            Cancel Request
          </DropdownMenuItem>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )}
</div>
```

### Redux action (RTK Query example)

```typescript
updateRequestStatus: builder.mutation<
  TransferRequest,
  { id: string; status: string; force?: boolean }
>({
  query: ({ id, status, force }) => ({
    url: `/transfer-requests/${id}/update-status/`,
    method: 'POST',
    body: { status, force },
  }),
  invalidatesTags: (result, error, { id }) => [
    { type: 'TransferRequest', id },
    { type: 'TransferRequest', id: 'LIST' },
  ],
}),
```

---

## Testing checklist

- [x] Manager can update status from `NEW` to `ASSIGNED`
- [x] Manager can manually fulfill request (`ASSIGNED` → `FULFILLED`)
- [x] Manager can reset request to `NEW` from any state (with `force` when needed)
- [x] Manager can cancel request
- [x] Staff users are denied access (403)
- [x] Invalid status values are rejected (400)
- [x] Attempting to change from `FULFILLED` without `force` is rejected (400)
- [x] `_status_change` metadata is included in response
- [x] `fulfilled_at` and `fulfilled_by` are set on manual fulfillment
- [x] Transfer link is cleared when resetting to `NEW`

---

## Security considerations

- **Role enforcement:** Only users with `OWNER`, `ADMIN`, or `MANAGER` roles can access this endpoint
- **Business membership:** User must be an active member of the business that owns the request
- **Terminal state protection:** Requires explicit `force` flag to modify `FULFILLED` requests, preventing accidental data loss
- **Audit trail:** The `_status_change` object provides visibility into who made the change

---

## Related documentation

- **Stock Request Backend Contract:** `docs/stock_request_backend_contract.md` (§2.1, §2.4)
- **Transfer Approvals & Receipt Confirmation:** `docs/transfer_approvals_receipt_dashboard.md`
- **Workflow endpoint reference:** `/inventory/api/transfer-requests/` endpoints

---

## Changelog

**2025-10-03:**
- Initial implementation of `POST /transfer-requests/{id}/update-status/`
- Added `force` flag for terminal state override
- Comprehensive test coverage (8 tests in `TransferRequestWorkflowAPITest`)
- Documentation updates to backend contract
