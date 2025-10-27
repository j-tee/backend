# Transfer Approvals, Receipt Confirmation & Employee Dashboard (October 2025)

This document captures the new requirements around privileged transfer approvals, requester receipt acknowledgements, and the employee workspace metrics needed for the frontend dashboards.

---

## 1. Manager approval flow

Managers (roles `OWNER`, `ADMIN`, `MANAGER`) advance a transfer that originated from a storefront request using privileged workflow actions. Authentication is via the standard Token header `Authorization: Token <token>`.

### 1.1 Workflow endpoints

| Step | Endpoint | Allowed current statuses | Role requirement | Request body | Success response |
| ---- | -------- | ------------------------ | ---------------- | ------------- | ---------------- |
| Submit | `POST /inventory/api/transfers/{id}/submit/` | `DRAFT`, `REJECTED` | Any member of the business | `none` | `200 OK` with full [`Transfer`](#4-typescript-interfaces) payload in `REQUESTED` state |
| Approve | `POST /inventory/api/transfers/{id}/approve/` | `REQUESTED` | `OWNER`·`ADMIN`·`MANAGER` | Optional line-item adjustments (see below) | `200 OK` with transfer payload in `APPROVED` state |
| Dispatch | `POST /inventory/api/transfers/{id}/dispatch/` | `APPROVED` | `OWNER`·`ADMIN`·`MANAGER` | Optional fulfilled quantities | `200 OK`, transfer moves to `IN_TRANSIT`; stock deducted from warehouse |
| Complete | `POST /inventory/api/transfers/{id}/complete/` | `IN_TRANSIT` | `OWNER`·`ADMIN`·`MANAGER` | Optional fulfilled quantities | `200 OK`, transfer status `COMPLETED`; storefront stock incremented |

#### Adjustable line items payload

```json
{
	"line_items": [
		{
			"id": "<transfer-line-item-uuid>",
			"approved_quantity": 18
		}
	]
}
```

For `dispatch` and `complete`, replace `approved_quantity` with `fulfilled_quantity`. Omitted line items retain their previous values.

#### Common error responses

| Scenario | Status | Payload |
| -------- | ------ | ------- |
| Missing privileges | `403` | `{ "detail": "You do not have the required role for this action." }` |
| Invalid state transition | `400` | `{ "status": ["Invalid transition from APPROVED. Expected: REQUESTED."] }` |
| Stock shortfall on dispatch | `400` | `{ "line_items": ["Insufficient stock for Sparkle Orange Juice at Main Warehouse."] }` |

### 1.2 Backend side effects

- **Inventory updates** happen inside the endpoint transactions. No extra API call is required for the frontend to “finalise” quantities.
- **Transfer requests** linked via `request_id` automatically move to `STATUS_ASSIGNED` once a transfer is created. Rejections or cancellations return the request to `NEW`.
- **Audit log entries** are emitted for every action (`SUBMITTED`, `APPROVED`, `DISPATCHED`, `COMPLETED`). They appear inside the `audit_log` array of the transfer response.

---

## 2. Requester receipt acknowledgement

Storefront staff who created the original request can acknowledge delivery via:

```
POST /inventory/api/transfers/{id}/confirm-receipt/
```

- Confirmation sets `received_by` / `received_at` on the transfer.
- If the transfer is linked to a request, the request moves to `FULFILLED` and records `fulfilled_by` / `fulfilled_at`.
- The endpoint only succeeds when the transfer status is `IN_TRANSIT` or `COMPLETED`; surface the action in the UI accordingly.

After confirmation, the API response includes the updated transfer payload so the UI can refresh in place.

### 2.1 Request & responses

**Request body**

```json
{
	"notes": "All cartons delivered intact"
}
```

`notes` is optional. An empty body is also valid.

**Success (200)**

```json
{
	"id": "9a5b...",
	"status": "COMPLETED",
	"received_by": "d5c1...",
	"received_by_name": "Store Staff",
	"received_at": "2025-10-03T09:45:11.321Z",
	"request_id": "6d94...",
	"audit_log": [
		{
			"action": "RECEIPT_CONFIRMED",
			"actor_name": "Store Staff",
			"remarks": "All cartons delivered intact",
			"created_at": "2025-10-03T09:45:11.335Z"
		}
	],
	"...existing transfer fields"
}
```

**Error conditions**

| Situation | Status | Example payload |
| --------- | ------ | --------------- |
| Transfer not in transit or completed | `400` | `{ "detail": "Transfer must be in transit or completed before confirming receipt." }` |
| Requester tries to confirm without membership | `403` | `{ "detail": "You are not a member of this business." }` |
| Transfer already confirmed | `400` | `{ "detail": "Receipt already confirmed for this transfer." }` |

---

## 3. Employee workspace dashboard

A new aggregated endpoint feeds dashboards for both managers and storefront staff:

```
GET /inventory/api/employee/workspace/
```

What it returns (scoped to the caller’s business memberships and assignments):

- **businesses**: list of businesses the employee can see, including role, transfer/transfer-request counts by status, and stock totals (`warehouse_on_hand`, `storefront_on_hand`).
- **warehouses / storefronts**: resources the user manages (managers) or is explicitly assigned to (staff), each with scope labels and on-hand quantities. Storefront entries also include `pending_requests` counts.
- **pending_approvals**: for managers, transfers stuck in `REQUESTED` status that require attention.
- **incoming_transfers**: in-transit or recently completed transfers headed to storefronts the employee can operate.
- **my_transfer_requests**: the latest requests submitted by the employee, reflecting their current pipeline state.

Continue using `/inventory/api/owner/workspace/` for the owner dashboard; it remains owner-specific. The new employee workspace endpoint plugs directly into the manager/staff views and respects RBAC without additional frontend filtering.

### 3.1 Response schema

```json
{
	"businesses": [
		{
			"id": "<uuid>",
			"name": "DataLogique Systems",
			"role": "MANAGER",
			"storefront_count": 2,
			"warehouse_count": 1,
			"transfer_requests": {
				"by_status": {
					"NEW": 3,
					"ASSIGNED": 1,
					"FULFILLED": 4,
					"CANCELLED": 0
				}
			},
			"transfers": {
				"by_status": {
					"DRAFT": 0,
					"REQUESTED": 1,
					"APPROVED": 0,
					"IN_TRANSIT": 1,
					"COMPLETED": 5,
					"REJECTED": 0,
					"CANCELLED": 0
				}
			},
			"stock": {
				"warehouse_on_hand": 120,
				"storefront_on_hand": 85
			}
		}
	],
	"warehouses": [
		{
			"id": "<uuid>",
			"name": "Transfer Warehouse",
			"business": "<uuid>",
			"business_name": "DataLogique Systems",
			"scope": "manager",
			"stock_on_hand": 120
		}
	],
	"storefronts": [
		{
			"id": "<uuid>",
			"name": "Downtown Store",
			"business": "<uuid>",
			"business_name": "DataLogique Systems",
			"scope": "assigned",
			"inventory_on_hand": 85,
			"pending_requests": 2
		}
	],
	"pending_approvals": [
		{
			"id": "<transfer-uuid>",
			"reference": "TRF-20251003-ABC123",
			"status": "REQUESTED",
			"destination_storefront": "<uuid>",
			"destination_storefront_name": "Downtown Store",
			"created_at": "2025-10-03T09:31:03Z"
		}
	],
	"incoming_transfers": [
		{
			"id": "<transfer-uuid>",
			"reference": "TRF-20251003-XYZ890",
			"status": "IN_TRANSIT",
			"destination_storefront": "<uuid>",
			"destination_storefront_name": "Downtown Store",
			"completed_at": null,
			"received_at": null
		}
	],
	"my_transfer_requests": [
		{
			"id": "<request-uuid>",
			"status": "FULFILLED",
			"priority": "HIGH",
			"storefront": "<uuid>",
			"storefront_name": "Downtown Store",
			"linked_transfer_reference": "TRF-20251003-XYZ890",
			"created_at": "2025-10-02T15:20:10Z"
		}
	]
}
```

Fields you can rely on:

	- `scope`: either `manager` (user can manage every warehouse/storefront in the business) or `assigned` (user only sees explicitly assigned locations).
	- `transfer_requests.by_status` & `transfers.by_status`: every status from the enum is present; counts default to `0` so the UI can render without guarding for missing keys.
	- `stock.warehouse_on_hand` / `stock.storefront_on_hand`: aggregate integer quantities (never `null`).
	- `pending_approvals`: empty array for staff; managers receive up to the 10 oldest `REQUESTED` transfers.
	- `incoming_transfers`: transfers in `IN_TRANSIT` or `COMPLETED` for the storefronts the user can see (staff) or every storefront (managers).
	- `my_transfer_requests`: latest 10 requests created by the authenticated user ordered by `created_at desc`.

	Pagination is not applied; the lists are already truncated to 10 items each for UX simplicity.

	### 3.2 Role-based shaping

	- **Managers** see every warehouse/storefront in their businesses plus approval queues. They do **not** need individual assignments.
	- **Staff** only see locations where they are explicitly assigned (`StoreFrontEmployee`, `WarehouseEmployee`). If the UI is missing data, confirm the assignment list through `/inventory/api/storefront-employees/` or `/inventory/api/warehouse-employees/`.
	- A business membership that is inactive or missing is filtered out entirely (response becomes empty arrays).

	### 3.3 Error cases

	The endpoint returns `200` with empty arrays when the user has no active memberships. Permission errors surface as the standard `{ "detail": "Authentication credentials were not provided." }` (401) or `{ "detail": "Invalid token." }` (401) if the token is missing or expired.

	---

	## 4. TypeScript interfaces

	Reuse these when wiring the frontend client. The transfer/transfer request interfaces mirror the definitions in `transfer-documentation.md`; repeated here for convenience with the new fields highlighted.

	```ts
	export type TransferStatus =
		| 'DRAFT'
		| 'REQUESTED'
		| 'APPROVED'
		| 'IN_TRANSIT'
		| 'COMPLETED'
		| 'REJECTED'
		| 'CANCELLED';

	export interface TransferLineItemPayload {
		id: string;
		approved_quantity?: number;
		fulfilled_quantity?: number;
	}

	export interface TransferWorkflowResponse extends Transfer {
		received_by: string | null;
		received_by_name: string | null;
		received_at: string | null;
		audit_log: Array<{
			action: string;
			actor: string | null;
			actor_name: string | null;
			remarks: string | null;
			created_at: string;
		}>;
	}

	export interface PendingApprovalSummary {
		id: string;
		reference: string;
		status: TransferStatus;
		destination_storefront: string;
		destination_storefront_name: string;
		created_at: string;
	}

	export interface IncomingTransferSummary extends PendingApprovalSummary {
		completed_at: string | null;
		received_at: string | null;
	}

	export interface WorkspaceBusinessSummary {
		id: string;
		name: string;
		role: 'OWNER' | 'ADMIN' | 'MANAGER' | 'STAFF';
		storefront_count: number;
		warehouse_count: number;
		transfer_requests: {
			by_status: Record<'NEW' | 'ASSIGNED' | 'FULFILLED' | 'CANCELLED', number>;
		};
		transfers: {
			by_status: Record<TransferStatus, number>;
		};
		stock: {
			warehouse_on_hand: number;
			storefront_on_hand: number;
		};
	}

	export interface WorkspaceWarehouseSummary {
		id: string;
		name: string;
		business: string | null;
		business_name: string | null;
		scope: 'manager' | 'assigned';
		stock_on_hand: number;
	}

	export interface WorkspaceStorefrontSummary {
		id: string;
		name: string;
		business: string | null;
		business_name: string | null;
		scope: 'manager' | 'assigned';
		inventory_on_hand: number;
		pending_requests: number;
	}

	export interface WorkspaceTransferRequestSummary {
		id: string;
		status: 'NEW' | 'ASSIGNED' | 'FULFILLED' | 'CANCELLED';
		priority: 'LOW' | 'MEDIUM' | 'HIGH';
		storefront: string;
		storefront_name: string;
		linked_transfer_reference: string | null;
		created_at: string;
	}

	export interface EmployeeWorkspaceResponse {
		businesses: WorkspaceBusinessSummary[];
		warehouses: WorkspaceWarehouseSummary[];
		storefronts: WorkspaceStorefrontSummary[];
		pending_approvals: PendingApprovalSummary[];
		incoming_transfers: IncomingTransferSummary[];
		my_transfer_requests: WorkspaceTransferRequestSummary[];
	}
	```

	When modelling API hooks, treat all string timestamps as ISO 8601 values (UTC). Numeric counts are basic integers; no BigInt handling is required.

---

	## 5. Frontend implementation checklist

- Gate approval actions behind role checks (owner/admin/manager) and wire the workflow buttons to the endpoints above.
- Show the receipt confirmation button only when the transfer status is `IN_TRANSIT` or `COMPLETED` and the viewer is the original requester (or another user with confirmation rights supplied by the backend).
- Refresh dashboards with `GET /inventory/api/employee/workspace/` after each workflow action so counts and stock levels stay current.
- Surface validation errors (e.g., attempting to confirm before dispatch) directly in the UI; the API returns precise reason strings.
	- For optimistic UI updates, mirror the state transitions in the tables (`REQUESTED` → `APPROVED` → `IN_TRANSIT` → `COMPLETED`) while awaiting the server response; reconcile with the payload returned by the API to capture audit entries and timestamps.
	- Cache the workspace response per business selector and invalidate after any transfer/receipt action so counts stay accurate.
	- If you need to rehydrate lists beyond the top 10 items, fall back to the canonical endpoints (`/inventory/api/transfers/`, `/inventory/api/transfer-requests/`) and apply the same filters the workspace uses (business scope, storefront assignments).
