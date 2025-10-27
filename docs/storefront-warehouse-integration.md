# Storefront & Warehouse API Integration Guide

This document focuses on the endpoints and request/response contracts required to let business owners manage storefronts and warehouses from the frontend.

---

## 1. Common Rules

- All endpoints live under `/inventory/api/`.
- Authentication: include `Authorization: Token <auth-token>` in every request.
- Only **business owners** with an active business can create storefronts or warehouses. They must be logged in with a token generated via `/accounts/api/auth/login/`.
- Employees can view resources scoped to their businesses but cannot create new storefronts/warehouses.
- On successful creation, the backend links the resource to the owner’s primary business and enrolls the owner as the manager.

---

## 2. Storefronts

### 2.1 List Storefronts
- **Endpoint:** `GET /inventory/api/storefronts/`
- **Purpose:** Retrieve storefronts belonging to the authenticated user’s businesses.
- **Success Response (200):**
  ```json
  [
    {
      "id": "<uuid>",
      "user": "<owner-uuid>",
      "user_name": "Owner Name",
      "name": "Flagship Store",
      "location": "Main Street",
      "manager": "<uuid|null>",
      "manager_name": "Manager Name",
      "created_at": "2025-09-30T12:34:56Z",
      "updated_at": "2025-09-30T12:34:56Z"
    }
  ]
  ```

### 2.2 Create Storefront
- **Endpoint:** `POST /inventory/api/storefronts/`
- **Request Body:**
  ```json
  {
    "name": "Flagship Store",
    "location": "Main Street",
    "manager": "<optional-manager-uuid>"
  }
  ```
  - `manager` is optional. If omitted, the owner remains the default manager.
- **Success Response (201):** storefront payload identical to the list format.
- **Error Responses:**
  - `403` if caller is not an owner or lacks an active business.
  - `400` with validation errors (e.g., duplicate name per business).

### 2.3 Update Storefront
- **Endpoint:** `PATCH /inventory/api/storefronts/{id}/`
- **Request Body (example):**
  ```json
  {
    "name": "Renovated Store",
    "location": "New Town"
  }
  ```
- **Success Response (200):** updated storefront payload.
- **Rules:**
  - Only owners/superusers tied to the storefront’s business can update.
  - Employees receive `403 Forbidden`.

### 2.4 Delete Storefront
- **Endpoint:** `DELETE /inventory/api/storefronts/{id}/`
- **Success Response:** `204 No Content`.
- **Rules:** same permission guard as update.

### 2.5 Owner Workspace Snapshot
- **Endpoint:** `GET /inventory/api/owner/workspace/`
- **Purpose:** One-call summary showing storefronts, warehouses, and counts.
- **Response (200):**
  ```json
  {
    "business": {
      "id": "<uuid>",
      "name": "API Biz",
      "storefront_count": 2,
      "warehouse_count": 1
    },
    "storefronts": [...],
    "warehouses": [...]
  }
  ```
  Useful for dashboards or initial page loads.

---

## 3. Warehouses

### 3.1 List Warehouses
- **Endpoint:** `GET /inventory/api/warehouses/`
- **Response (200):**
  ```json
  [
    {
      "id": "<uuid>",
      "name": "Primary Warehouse",
      "location": "Industrial Estate",
      "manager": "<uuid|null>",
      "manager_name": "Manager Name",
      "created_at": "2025-09-30T12:34:56Z",
      "updated_at": "2025-09-30T12:34:56Z"
    }
  ]
  ```

### 3.2 Create Warehouse
- **Endpoint:** `POST /inventory/api/warehouses/`
- **Request Body:**
  ```json
  {
    "name": "Primary Warehouse",
    "location": "Industrial Estate",
    "manager": "<optional-manager-uuid>"
  }
  ```
- **Success Response (201):** warehouse payload matching list format.
- **Backend Behavior:** automatically links warehouse to owner’s primary business and assigns the owner as the first WarehouseEmployee (role OWNER).

### 3.3 Update Warehouse
- **Endpoint:** `PATCH /inventory/api/warehouses/{id}/`
- **Request Body (example):**
  ```json
  {
    "name": "Updated Warehouse",
    "location": "New Zone"
  }
  ```
- **Success Response (200):** updated warehouse payload.
- **Permissions:** owner or superuser only; employees get `403`.

### 3.4 Delete Warehouse
- **Endpoint:** `DELETE /inventory/api/warehouses/{id}/`
- **Success Response:** `204 No Content`.
- **Permissions:** same as update.

---

## 4. Error Handling Reference

| Status | Meaning | Typical Payload |
| ------ | ------- | ---------------- |
| 400 | Validation error | `{ "name": ["This field is required."] }` |
| 403 | Not allowed (not owner or lacks business link) | `{ "detail": "You do not have permission to update this warehouse." }` |
| 404 | Resource not found | `{ "detail": "Not found." }` |

Surface these messages in the UI verbatim when possible—they’re already user friendly.

---

## 5. Frontend Implementation Checklist

1. **Authentication**
   - Ensure the owner is logged in and token is stored securely.
   - Attach `Authorization: Token …` on every request.

2. **Creation Forms**
   - Collect `name`, `location`, optional manager selection.
   - POST to `/storefronts/` or `/warehouses/` respectively.
   - On success, refresh the owner workspace or list view.

3. **Edit/Delete Workflows**
   - Use PATCH with partial data for inline edits.
   - Confirm deletion with the user before sending DELETE.
   - If API returns 403, display a permission warning.

4. **Workspace Overview**
   - Call `/owner/workspace/` to pre-populate dashboards.
   - Use that response to seed UI state for storefront and warehouse tables.

5. **Error UX**
   - Show validation messages directly near form fields.
   - Provide retry options for transient 500 responses.

With these endpoints and rules wired up, the frontend can deliver full CRUD management for storefronts and warehouses while honoring the business-owner permissions baked into the backend.

---

## 6. Sample Responses (Captured via Owner API Tests)

Use these snapshots to shape fixtures or unit tests on the frontend. UUIDs and timestamps will differ in production, but payload shapes and status codes are representative of live behavior.

### Workspace (Empty State)

- **Request:** `GET /inventory/api/owner/workspace/`
- **Status:** `200 OK`
- **Body:**
  ```json
  {
    "business": {
      "id": "f0661458-51d9-44cc-9c76-fa503501a66b",
      "name": "API Biz 2db03e",
      "storefront_count": 0,
      "warehouse_count": 0
    },
    "storefronts": [],
    "warehouses": []
  }
  ```

### Create Storefront

- **Request:** `POST /inventory/api/storefronts/`
- **Payload:**
  ```json
  {
    "name": "Flagship Store",
    "location": "Main Street"
  }
  ```
- **Status:** `201 Created`
- **Body:**
  ```json
  {
    "id": "0f97531b-8736-45fd-a848-769011f585d4",
    "user": "b79895d2-2773-470d-9e89-ac7cc7c556bb",
    "user_name": "API Owner",
    "name": "Flagship Store",
    "location": "Main Street",
    "manager": null,
    "created_at": "2025-10-01T13:14:18.407130Z",
    "updated_at": "2025-10-01T13:14:18.407144Z"
  }
  ```

### Create Warehouse

- **Request:** `POST /inventory/api/warehouses/`
- **Payload:**
  ```json
  {
    "name": "Primary Warehouse",
    "location": "Industrial Estate"
  }
  ```
- **Status:** `201 Created`
- **Body:**
  ```json
  {
    "id": "bf93c13d-3d46-460c-b9b6-450def601fb6",
    "name": "Primary Warehouse",
    "location": "Industrial Estate",
    "manager": null,
    "created_at": "2025-10-01T13:14:18.487229Z",
    "updated_at": "2025-10-01T13:14:18.487248Z"
  }
  ```

### Workspace (After Creation)

- **Request:** `GET /inventory/api/owner/workspace/`
- **Status:** `200 OK`
- **Body:**
  ```json
  {
    "business": {
      "id": "f0661458-51d9-44cc-9c76-fa503501a66b",
      "name": "API Biz 2db03e",
      "storefront_count": 1,
      "warehouse_count": 1
    },
    "storefronts": [
      {
        "id": "0f97531b-8736-45fd-a848-769011f585d4",
        "user": "b79895d2-2773-470d-9e89-ac7cc7c556bb",
        "user_name": "API Owner",
        "name": "Flagship Store",
        "location": "Main Street",
        "manager": null,
        "created_at": "2025-10-01T13:14:18.407130Z",
        "updated_at": "2025-10-01T13:14:18.407144Z"
      }
    ],
    "warehouses": [
      {
        "id": "bf93c13d-3d46-460c-b9b6-450def601fb6",
        "name": "Primary Warehouse",
        "location": "Industrial Estate",
        "manager": null,
        "created_at": "2025-10-01T13:14:18.487229Z",
        "updated_at": "2025-10-01T13:14:18.487248Z"
      }
    ]
  }
  ```

### Update Storefront

- **Request:** `PATCH /inventory/api/storefronts/0f97531b-8736-45fd-a848-769011f585d4/`
- **Payload:**
  ```json
  {
    "name": "Renovated Store",
    "location": "New Town"
  }
  ```
- **Status:** `200 OK`
- **Body:**
  ```json
  {
    "id": "0f97531b-8736-45fd-a848-769011f585d4",
    "user": "b79895d2-2773-470d-9e89-ac7cc7c556bb",
    "user_name": "API Owner",
    "name": "Renovated Store",
    "location": "New Town",
    "manager": null,
    "created_at": "2025-10-01T13:14:18.407130Z",
    "updated_at": "2025-10-01T13:14:18.581157Z"
  }
  ```

### Update Warehouse

- **Request:** `PATCH /inventory/api/warehouses/bf93c13d-3d46-460c-b9b6-450def601fb6/`
- **Payload:**
  ```json
  {
    "name": "Updated Warehouse",
    "location": "Zone 5"
  }
  ```
- **Status:** `200 OK`
- **Body:**
  ```json
  {
    "id": "bf93c13d-3d46-460c-b9b6-450def601fb6",
    "name": "Updated Warehouse",
    "location": "Zone 5",
    "manager": null,
    "created_at": "2025-10-01T13:14:18.487229Z",
    "updated_at": "2025-10-01T13:14:18.616370Z"
  }
  ```

### Delete Storefront & Warehouse

- **Requests:**
  - `DELETE /inventory/api/storefronts/0f97531b-8736-45fd-a848-769011f585d4/`
  - `DELETE /inventory/api/warehouses/bf93c13d-3d46-460c-b9b6-450def601fb6/`
- **Status:** `204 No Content` (both)
- **Body:** `null`

### Workspace (After Deletions)

- **Request:** `GET /inventory/api/owner/workspace/`
- **Status:** `200 OK`
- **Body:**
  ```json
  {
    "business": {
      "id": "f0661458-51d9-44cc-9c76-fa503501a66b",
      "name": "API Biz 2db03e",
      "storefront_count": 0,
      "warehouse_count": 0
    },
    "storefronts": [],
    "warehouses": []
  }
  ```
