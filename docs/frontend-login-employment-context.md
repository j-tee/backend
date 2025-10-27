# Frontend Guide: Login Employment Context

## Overview

When an employee signs into the platform, the backend now returns additional context describing the business that employed the user. This document explains the response shape, when the new `employment` payload appears, and how the frontend should consume it. The intent is to remove guesswork for RBAC bootstrapping and keep the UI aligned with backend expectations.

---

## Endpoint & Response

**Endpoint:** `POST /accounts/api/auth/login/`

**Success Response (employee account):**

```json
{
  "token": "<auth-token>",
  "user": {
    "id": "bdf2f7f0-19e3-4d9d-9cb1-07dc07b22661",
    "name": "Ama Mensah",
    "email": "ama.employee@example.com",
    "account_type": "EMPLOYEE",
    "platform_role": "NONE",
    "is_active": true,
    "subscription_status": "Inactive",
    "role": null,
    "role_name": null,
    "picture_url": null,
    "email_verified": true,
    "created_at": "2025-10-02T16:10:33.811Z",
    "updated_at": "2025-10-02T16:10:33.811Z"
  },
  "employment": {
    "id": "5dbd6bfd-2c64-4fce-9556-11bbecbe4d3c",
    "role": "STAFF",
    "is_admin": false,
    "is_active": true,
    "created_at": "2025-09-01T12:08:15.251Z",
    "updated_at": "2025-10-02T16:10:33.811Z",
    "business": {
      "id": "43e1b7f7-d76d-4420-bd12-7e25fb016174",
      "name": "Kumasi Retail Hub",
      "tin": "TIN-KUM-0001",
      "email": "care@kumasi-retail.com",
      "address": "15 Asafo Road, Kumasi",
      "website": "https://kumasi-retail.com",
      "phone_numbers": ["+233202020202"],
      "social_handles": {"instagram": "@kumasi_retail"},
      "is_active": true,
      "owner": "0f76cf7a-1d66-4cad-a204-d5c0c5805464",
      "owner_name": "Kwame Mensah",
      "created_at": "2025-07-14T09:22:01.024Z",
      "updated_at": "2025-09-20T08:11:52.002Z"
    }
  }
}
```

**Success Response (non-employee account):**

```json
{
  "token": "<auth-token>",
  "user": {
    "id": "bb8d6aca-85a7-4d49-9747-0b6ff269f9b8",
    "name": "Kojo Owner",
    "email": "owner@example.com",
    "account_type": "OWNER",
    "platform_role": "NONE",
    "is_active": true,
    "subscription_status": "Inactive",
    "role": null,
    "role_name": null,
    "picture_url": null,
    "email_verified": true,
    "created_at": "2025-08-31T10:03:44.772Z",
    "updated_at": "2025-09-05T14:12:20.551Z"
  },
  "employment": null
}
```

---

## When to Expect `employment`

- Present only when `user.account_type == "EMPLOYEE"` **and** the user has at least one active business membership.
- The serializer chooses the most recently updated active membership (fallback to newest by creation time). If you need to surface a selectable list, call the memberships endpoint after login (see below).
- Owners or platform-only users receive `employment = null`.

---

## Field Definitions

| Field | Type | Notes |
| --- | --- | --- |
| `employment.id` | UUID | Business membership ID. Use if you need to reference the membership later. |
| `employment.role` | Enum | One of `OWNER`, `ADMIN`, `MANAGER`, `STAFF`. Mirrors `accounts.BusinessMembership.role`. |
| `employment.is_admin` | Boolean | Indicates if the membership is admin-level (true for OWNER/ADMIN). |
| `employment.business.id` | UUID | Primary business identifier. |
| `employment.business.name` | String | Business display name—safe to show in header/sidebar. |
| `employment.business.owner` | UUID | Owner user ID. (Useful for escalations or support dashboards.) |
| `employment.business.owner_name` | String | Owner display name. |
| `employment.business.phone_numbers` | Array | Primary contact numbers (optional). |
| `employment.business.social_handles` | Object | Social handles (optional). |

All fields inside `employment` are read-only snapshots derived from the backend. If any field is missing, treat it as null/blank rather than making assumptions.

---

## Frontend Expectations

1. **Bootstrap RBAC Quickly**: Use the `employment` object to fetch a detailed membership record only when necessary. For most dashboards, the included business data is enough to tailor navigation.
2. **Guard Against Null**: Always handle the `employment = null` case gracefully—e.g., show a prompt to choose/create a business or fall back to owner workflows.
3. **Cache With Token**: Store the employment payload alongside the auth token so you can render the shell of the app immediately after login.
4. **Sync After Changes**: If the user switches businesses or their membership gets updated (role change, suspension), refresh from `/inventory/api/memberships/{membership_id}/` to retrieve the latest `role_matrix`.
5. **Multiple Businesses**: For multi-business employees, expose a business switcher that calls `GET /inventory/api/memberships/` to list all active memberships. The login response only picks the first one.
6. **Error Handling**: A missing `employment` field for an employee typically means the membership is inactive or pending. Display an explanatory message and surface support contacts.

---

## Related APIs

- `GET /inventory/api/memberships/` — list all memberships (supports pagination).
- `GET /inventory/api/memberships/{membership_id}/` — full detail with `role_matrix` and storefront assignments.
- `PATCH /inventory/api/memberships/{membership_id}/` — role or status changes (admins only).

---

## Testing Tips (Frontend)

- Use a mock server or fixture to simulate both employee and owner login payloads.
- Verify session storage persists the `employment` block between reloads.
- Ensure user switching or logout clears cached employment data.

---

_Last updated: 2025-10-02_

Questions? Reach out to the backend platform team before inferring new behavior. We’ll keep this doc aligned with future API iterations.
