# Warehouse & Storefront Query Fix (October 2025)

This note documents the warehouse/storefront filtering issue reported by the frontend team, how it was resolved on the backend, and what the UI needs to do to stay in sync.

---

## Recap of the issue

Employees were calling:

- `GET /inventory/api/warehouses/`
- `GET /inventory/api/storefronts/`

with an explicit `?business=<uuid>` filter, but the responses still included locations from **every** business the employee belonged to. Owners never noticed the problem because they usually manage a single business.

### Root cause

The Django viewsets ignored any incoming `business` filter and blindly returned “everything the user can see.” For multi-business employees that meant a superset of results, so the UI could not scope the tables to the currently selected business.

### Backend fix

Both endpoints now:

1. Honour `business` (and the alias `business_id`) when supplied.
2. Validate the value as a UUID and respond with `400 {"business": ["Invalid business id supplied."]}` if it’s malformed.
3. Continue to enforce business membership so employees can’t leap into businesses they don’t belong to.

The same helper powers warehouse and storefront queries, keeping behaviour consistent.

---

## Frontend action items

- **Always attach the active business ID** when you want scoped results:
  - `GET /inventory/api/warehouses/?business=<businessUuid>`
  - `GET /inventory/api/storefronts/?business=<businessUuid>`
- **Handle the new validation error**: if the backend returns `400` with the `business` key, surface the message and prompt the user to re-select a business (this typically happens when the cached ID is stale).
- **Omit the param intentionally** when you want the cross-business rollup (admin dashboards, global pickers). The endpoints will fall back to “everything the user can legitimately access.”
- **Keep the active business context cached** alongside the auth token so repeated fetches remain aligned with the user’s selected workspace.

---

## Testing notes

Automated tests now cover:

- Employees requesting businesses they do not belong to (`[]` response).
- Employees belonging to multiple businesses using `business` / `business_id` filters to narrow results.
- Invalid business IDs yielding the new `400` validation path.

No additional frontend mocks are required—the server responses now behave as described above.

---
