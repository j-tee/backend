# Storefront Management API Contracts

This guide explains the REST endpoints the frontend should use to display and manage storefronts. All routes require authentication (token or session) and live under the `/inventory/api/` namespace.

---

## Authentication & Headers

Send the user9s token on every request:

```
Authorization: Token <auth-token>
Content-Type: application/json
Accept: application/json
```

Requests without a valid token return `401 Unauthorized` with a standard DRF error payload.

---

## Data model quick reference

Each storefront record surfaces the following fields via `StoreFrontSerializer`:

| Field | Type | Notes |
| --- | --- | --- |
| `id` | UUID | Primary key. |
| `user` | UUID | Owner account. Set automatically on create. Read-only. |
| `user_name` | string | Convenience label for the owner. |
| `name` | string | Display name of the storefront. |
| `location` | string | Free-form location / address details. |
| `manager` | UUID or `null` | User ID of the assigned store manager. Optional. |
| `manager_name` | string or `null` | Friendly name of the manager. |
| `created_at` | ISO-8601 datetime | Record creation timestamp (UTC). |
| `updated_at` | ISO-8601 datetime | Last modification timestamp (UTC). |

> Business linkage happens behind the scenes through `BusinessStoreFront`. A user must belong to the business in order to see or mutate a storefront.

---

## Listing storefronts (paginated)

### Endpoint
- `GET /inventory/api/storefronts/`

### Query parameters
| Param | Type | Default | Description |
| --- | --- | --- | --- |
| `page` | integer | `1` | 1-indexed page number. |

- The API uses `PageNumberPagination` with a fixed page size of **20** records.
- Custom page sizes are not currently exposed; `page_size` is ignored.
- Results respect the authenticated user9s business membership. Superusers see all storefronts.

### Success response (200)
```json
{
  "count": 3,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "9eafec8f-2f3b-476b-8cf4-1b07f01c5733",
      "user": "b1f3a4f2-3b88-4f35-8554-8de410db5228",
      "user_name": "Test Owner",
      "name": "Osu Flagship Store",
      "location": "Oxford Street, Accra",
      "manager": "1bc1f173-9d36-4f36-8d96-02e740b41fd8",
      "manager_name": "Kojo Mensah",
      "created_at": "2025-09-18T12:24:09.546Z",
      "updated_at": "2025-09-21T08:13:44.109Z"
    }
  ]
}
```

### Error responses
- `403 Forbidden` if the user belongs to no business with storefront access.
- `401 Unauthorized` when the token is missing or invalid.

---

## Retrieve single storefront

### Endpoint
- `GET /inventory/api/storefronts/<id>/`

Returns the same payload shape as the list entry. Use this for edit forms that need the latest persisted data.

---

## Create storefront

### Endpoint
- `POST /inventory/api/storefronts/`

### Request body
```json
{
  "name": "Takoradi Outlet",
  "location": "Market Circle, Takoradi",
  "manager": "1bc1f173-9d36-4f36-8d96-02e740b41fd8"
}
```

### Notes
- `user` is auto-set to the authenticated owner; omit it in the payload.
- Only business owners with an active business can create storefronts. Others receive `403 PermissionDenied` with a descriptive message.

### Success response (201)
Returns the serialized storefront document.

### Validation errors (400)
Standard DRF error objects keyed by field name, e.g.
```json
{ "name": ["This field may not be blank."] }
```

---

## Update storefront

### Endpoints
- `PUT /inventory/api/storefronts/<id>/` (full replace)
- `PATCH /inventory/api/storefronts/<id>/` (partial update)

### Example partial update
```json
{
  "name": "Takoradi Outlet (Phase 2)",
  "manager": null
}
```

### Behaviour
- Only superusers or members of the storefront9s business can edit.
- Field-level validation mirrors creation rules (e.g., `name` required for `PUT`).
- Timestamps update automatically; response mirrors serializer output.

### Failure modes
- `403 Forbidden` if the storefront belongs to a different business.
- `404 Not Found` when the ID is invalid or outside the user9s scope.

---

## Delete storefront

### Endpoint
- `DELETE /inventory/api/storefronts/<id>/`

### Behaviour
- Hard delete the storefront record and cascading relations (e.g., employee links) handled by the database.
- Same permission checks as update: superusers or members of the owning business only.

### Responses
- `204 No Content` on success.
- `403 Forbidden` for insufficient permissions.
- `404 Not Found` if the record is missing or inaccessible.

---

## Frontend integration checklist

- Build a paginated table or list that reads `count`, `next`, `previous`, and `results`.
- Use `page` query param when navigating to subsequent pages; stop when `next` is `null`.
- Surface the `manager_name` and `user_name` fields directly for display labels.
- When submitting create/update forms, send only mutable fields (`name`, `location`, `manager`).
- Expect permission errors (`403`) and render clear messaging (e.g., "You need business owner privileges to add storefronts").
- After mutations (create/update/delete), refetch page 1 to keep pagination in sync.

---

## Future enhancements (for awareness)

These aren9t implemented yet but commonly requested by business users:

1. **Search & filtering** – e.g., by name, region, or manager.
2. **Sortable columns** – especially by `created_at` or `name`.
3. **Custom page size** – expose `page_size` query param to fine-tune list density.
4. **Soft deletes / archive** – to preserve history while hiding inactive storefronts.

Reach out before relying on any of the above; they will require backend changes.
