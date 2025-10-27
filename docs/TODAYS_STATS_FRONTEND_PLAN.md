# Today's Stats Frontend Enhancement Plan

This document outlines the UI work required to expose status-aware sales metrics, surface partial/draft transactions, and let privileged users clean them up (complete or delete). The backend already exposes the necessary data through existing endpoints; no new API work is needed.

## 1. Current backend capabilities recap

Endpoint | Path | Purpose | Key fields for this feature
--- | --- | --- | ---
`todays-stats` | `/sales/api/sales/todays-stats/` | Per-day snapshot used by the Today's Stats widget. Defaults to `status=COMPLETED`. | `transactions`, `total_sales`, `avg_transaction`, `partial_transactions`, `pending_transactions`, `status_breakdown`, `payment_breakdown`.
`summary` | `/sales/api/sales/summary/` | Historical/analytic totals with full filter support. | Same aggregates as above (optionally scoped by `status`, `date_range`, `storefront`, etc.).
`sales list` | `/sales/api/sales/` (GET) | Paginated list of sales. Accepts `status` filter and supports bulk operations via other endpoints. | Individual sale records (`id`, `status`, `total_amount`, etc.)
`sales update` | `/sales/api/sales/<id>/` (PATCH/PUT) | Update a sale (e.g., mark as `COMPLETED`). | Accepts fields such as `status`, `amount_paid`, `amount_due`, `payment_type`.
`sales delete` | `/sales/api/sales/<id>/` (DELETE) | Remove a sale (subject to permissions). | —
`sales complete` | `/sales/api/sales/<id>/complete/` (POST) | Complete a draft sale using a checkout payload. | `payment_type`, `payments[]`, `discount_amount`, `tax_amount`, `notes`.
`sales record payment` | `/sales/api/sales/<id>/record_payment/` (POST) | Apply a payment to a credit sale (moves from PARTIAL→COMPLETED when fully paid). | `amount_paid`, `payment_method`, `reference_number`, `notes`.

## 2. UX goals

1. **Status-aware stats in the Today's Stats card**
   - Show counts and totals for each status the user is allowed to view (Completed, Partial, Pending, Draft).
   - Preserve the existing summary numbers (transactions, total sales, avg transaction) based on the user-selected statuses.

2. **Status tabs / filters for the sales list**
   - Provide quick filters for `COMPLETED`, `PARTIAL`, `PENDING`, `DRAFT` at the top of the sales table.
   - Show badge counts for each status based on the same data used in the card.

3. **Management actions for partial/draft records**
   - Users with `SALE_EDIT` privilege (or higher-level admin role) should be able to:
     - Open a partial sale and complete it (either by adding missing payment info or marking it complete if amount paid equals total).
     - Delete a draft sale that was abandoned.
   - Non-privileged users should see read-only messaging (e.g., "Only managers can finalize or remove draft sales.").

4. **Consistent exposure in other screens**
   - Any page that lists or aggregates sales (reports, dashboards, analytics) should display the same status breakdown and allow the same filters.

## 3. Data sourcing

### 3.1 Fetch status breakdown once

1. Load the snapshot through `todays-stats` with the desired statuses. Example for showing completed + partial by default:

```ts
const response = await api.get('/sales/api/sales/todays-stats/', {
  params: {
    storefront: activeStorefrontId,
    status: ['COMPLETED', 'PARTIAL'],
  },
});
const stats = response.data;
```

2. For management views that need everything (including drafts), add `status=DRAFT` and `status=PENDING`.

3. Use the returned `status_breakdown` array to populate badge counts and tooltips.

### 3.2 Fetch matching sale rows

Use the existing list endpoint with the same status filters to populate the table:

```ts
const salesResponse = await api.get('/sales/api/sales/', {
  params: {
    status: selectedStatuses, // e.g., ['PARTIAL', 'DRAFT']
    date_range: 'today',
    storefront: activeStorefrontId,
  },
});
const { results, count } = salesResponse.data;
```

> **Note:** The list endpoint requires authentication and enforces business/storefront permissions. No extra backend work needed.

## 4. Frontend design proposal

### 4.1 Today's Stats card enhancements

- Replace the current single-column layout with a grid:

```
+---------------------------+
| Today's Stats             |
|---------------------------|
| Completed   |  Transactions: 5
|             |  Total Sales:  ₵824.75
|             |  Avg Ticket:   ₵164.95
|---------------------------|
| Partial     |  Transactions: 2
|             |  Amount Due:   ₵1,155.00
|---------------------------|
| Draft       |  Carts: 45
|             |  Value: ₵2,310.00
+---------------------------+
```

- Pull values from `transactions` (completed), `partial_transactions`, and the `status_breakdown` entries for `DRAFT` and `PENDING`.
- Tooltip text can explain the default filters and the difference between statuses.

### 4.2 Status filters above the sales table

- Add a segmented control or tabs: `Completed`, `Partial`, `Pending`, `Draft`, `All`.
- Each tab fires the list endpoint with the corresponding `status` array.
- Display count badges using the same breakdown data so the UI updates instantly without re-fetching.

### 4.3 Action buttons per row

Status | Action | API | Notes
--- | --- | --- | ---
`DRAFT` | **Complete** | `POST /sales/api/sales/<id>/complete/` | Present checkout modal if payments are missing; send selected payment data.
`DRAFT` | **Delete** | `DELETE /sales/api/sales/<id>/` | Show confirmation dialog. Only show when `user.hasPermission('SALE_DELETE')`.
`PARTIAL` | **Apply payment** | `POST /sales/api/sales/<id>/record_payment/` | Launch modal to collect payment details; call endpoint, then refresh stats.
`PARTIAL` | **Mark complete** | `PATCH /sales/api/sales/<id>/` (`status='COMPLETED'`) OR route through `complete/` with zero additional payment | Warn if `amount_due > 0`.
`COMPLETED` | (existing receipts/download actions) | — | No change.

### 4.4 Access control logic

- Use the backend-provided permissions (e.g., role claims, membership flags) already exposed on the authenticated user.
- Hide or disable destructive actions (delete, mark complete) if the user lacks `SALE_EDIT` or `SALE_DELETE` authority.
- For read-only users, show contextual tooltips: "Ask your manager to finalize this sale.".

### 4.5 Shared components for other pages

- Encapsulate the status breakdown widget into a reusable component (`<SalesStatusSummary />`).
- Inject it into:
  - Reports page (overview cards).
  - Dashboard (top-level sales metrics).
  - Any modal where the user sees a summary before confirming.

## 5. Suggested UI workflow

1. **Initial load**: Fetch snapshot for `['COMPLETED', 'PARTIAL']`; populate card and default table (completed sales).
2. **Tab switch**: When the user clicks `Partial`, update the tab state, reuse cached breakdown if it already includes `PARTIAL`, otherwise re-fetch the snapshot with additional statuses to keep counts accurate.
3. **Action completion**: After a sale transitions (e.g., partial → completed), trigger a refresh of both the card and the list to keep counts in sync.
4. **Draft cleanup**: Provide a "Clean up drafts" button that filters to `DRAFT` and batches deletions (still one API call per sale). Optionally add a confirmation modal summarizing the number of drafts.

## 6. UI edge cases to handle

- **No data**: Show "No sales yet today" for each status section when counts are zero.
- **Mixed statuses**: If the user requests `status=COMPLETED&status=PARTIAL`, the card should indicate which totals are included (e.g., highlight rows with the selected statuses).
- **Large draft counts**: Offer pagination or a compact list view. Provide multi-select delete only if we add a backend bulk delete endpoint; otherwise, stick to one-by-one.
- **Permission errors**: If an action returns HTTP 403, catch it and show an inline alert (e.g., "Your role doesn’t allow deleting drafts.").

## 7. Testing checklist for the frontend

- [ ] Snapshot card shows correct counts for mock data (0 completed, 2 partial, 45 drafts).
- [ ] Switching storefronts updates the card and table.
- [ ] Toggling statuses updates counts and doesn’t include drafts when unselected.
- [ ] Partial → complete workflow triggers a refresh and removes the sale from the partial tab.
- [ ] Draft delete removes the row and decrements the draft count.
- [ ] Permissions GUI hides actions for read-only users.

## 8. Optional enhancements

- **Auto-refresh timer**: Poll the snapshot every 60 seconds while the tab is open.
- **Export button**: Add a quick link to `/sales/api/sales/export/?date_range=today&status=<tab>`.
- **Audit trail modal**: Link to audit logs (already available via `/sales/api/audit-logs/?sale=<id>`).

## 9. Implementation order of operations

1. Build the shared `SalesStatusSummary` component and wire it to `todays-stats`.
2. Update the Today's Stats card to use the new component and show status rows.
3. Enhance the sales table header with status tabs and counts.
4. Add per-row actions and modals for completing/deleting partial/draft sales (respect permissions).
5. Roll the component into other screens (dashboard, reports).
6. QA using seeded data (e.g., run `populate_datalogique_data.py` and verify the counts match backend outputs).

With these steps, the frontend will give operators immediate visibility into drafts and partial payments, along with the tools to resolve them without backend changes.
