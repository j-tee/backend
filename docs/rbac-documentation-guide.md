# RBAC Documentation Guide

## 1. Purpose & Audience

This guide explains how the platform’s role-based access control (RBAC) system works so that backend, frontend, and DevOps engineers share a common mental model. It summarizes the user and membership role taxonomies, the predicates and permissions registered through `django-rules`, the APIs that surface capability data, and best practices for testing and observability.

---

## 2. Role Taxonomy

### 2.1 Platform-Level Roles (`accounts.User.platform_role`)

| Role | Description | Typical Abilities |
| --- | --- | --- |
| `SUPER_ADMIN` | Platform-wide superuser who can administer every business and assign platform roles. | Assign platform roles, access global dashboards, override business ownership checks. |
| `SAAS_ADMIN` | Platform operations/admin staff. | Read/write access to businesses they support, manage memberships and invitations. |
| `SAAS_STAFF` | Support/CS staff. | Read-only access for troubleshooting; cannot mutate high-risk resources. |
| `NONE` | Default when no platform role is granted. | No platform-wide powers beyond business memberships. |

### 2.2 Business-Level Roles (`accounts.BusinessMembership.role`)

| Role | Implied Flags | Description |
| --- | --- | --- |
| `OWNER` | `is_admin = true` | Business creator/owner. Full control over business resources. |
| `ADMIN` | `is_admin = true` | Trusted manager with nearly all owner capabilities except billing-level actions. |
| `MANAGER` | `is_admin = false` | Mid-level manager who controls inventory operations, not account administration. |
| `STAFF` | `is_admin = false` | Day-to-day staff with limited permissions. |

### 2.3 Role Matrix

Membership detail responses include a computed `role_matrix` block:

```json
{
  "business": {
    "role": "ADMIN",
    "is_owner": false,
    "is_admin": true,
    "is_manager": false,
    "is_staff": false
  },
  "platform": {
    "role": "SAAS_ADMIN",
    "is_platform_super_admin": false,
    "is_platform_admin": true,
    "is_platform_staff": true
  }
}
```

Use this matrix to toggle frontend features and to inform API clients about permitted actions.

---

## 3. RBAC Engine (`accounts/rbac.py`)

We use [`django-rules`](https://github.com/dfunckt/django-rules) to define reusable predicates and register permissions.

### 3.1 Core Predicates

- `is_super_admin`: `True` when user has `SUPER_ADMIN` platform role or is a Django superuser.
- `is_saas_admin`: `True` when user has `SAAS_ADMIN` platform role.
- `is_saas_staff`: `True` when user has `SAAS_STAFF` platform role.
- `is_business_owner`, `is_business_admin`, `is_business_manager`, `is_business_staff`: Evaluate active memberships for the given business object.
- `is_business_member`: Checks that the user is an active member of the referenced business.
- `manages_storefront`, `manages_warehouse`: Verify roster assignments for storefront/warehouse employees.

### 3.2 Registered Permissions (Selected)

| Permission | Predicate | Purpose |
| --- | --- | --- |
| `inventory.view_storefront` | `is_super_admin` \| `is_saas_admin` \| `is_saas_staff` \| `is_business_member` | List/inspect storefronts. |
| `inventory.add_storefront` | `is_super_admin` \| `is_saas_admin` \| `is_business_owner` \| `is_business_admin` | Create storefronts. |
| `inventory.change_storefront` | Managers may edit storefronts assigned to them; admins/owners have broad access. |
| `accounts.manage_business_memberships` | `is_super_admin` \| `is_saas_admin` \| `is_business_owner` \| `is_business_admin` | Invite, update, suspend members. |
| `accounts.assign_storefronts` | Same as membership managers. | Assign roster to storefronts. |
| `accounts.assign_platform_roles` | `is_super_admin` | Only super admins can assign or clear `platform_role`. |

See `accounts/rbac.py` for the exhaustive list.

---

## 4. API Surface Area

### 4.1 Capability Retrieval

| Endpoint | Method | Description |
| --- | --- | --- |
| `/inventory/api/memberships/` | `GET` | Paginated memberships for the current business scope; includes `platform_role` and summary user info. |
| `/inventory/api/memberships/{membership_id}/` | `GET` | Detailed membership view with `role_matrix` and storefront assignments—primary source of truth for frontend RBAC decisions. |
| `/inventory/api/memberships/{membership_id}/` | `PATCH` | Allows business role changes and, for super admins only, platform role changes. |

### 4.2 Error Semantics

- Unauthorized access returns `401` (missing/invalid token).
- Permission denials return `403` with `