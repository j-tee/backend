# Frontend Integration Guide

This document gives the frontend team an authoritative roadmap for integrating with the SaaS POS backend. It starts with user registration and authentication, then walks through business setup, inventory control, sales processing, reporting, bookkeeping, and subscription management. Every section maps directly to existing backend endpoints so you never have to guess field names or payload shapes.

> **Subscription Gate**: Portions of the backend enforce an **active subscription** for the current business. If the authenticated user’s business subscription has lapsed, calls that create sales, process payments, or fetch sensitive reports will return `403 Forbidden`. The UI must surface a blocking banner and redirect the operator to billing. Non-critical areas such as inventory intake remain available so stock can be prepared while finance restores the subscription.

---

## 1. API Basics

- **Base URL (development)**: `http://localhost:8000`
- **Authentication**: Token-based using Django REST Framework tokens.
- **Default headers**:
  - `Content-Type: application/json`
  - `Accept: application/json`
  - `Authorization: Token <token>` (required after login/registration)
- **ID format**: All resources use UUID strings (e.g., `"a3e5b8c0-..."`). Preserve them as strings in requests.

### Pagination on collection endpoints

- All list endpoints use server-side pagination via DRF's page-number pagination.
- The default page size is **25** records per request with a maximum of **100** per page.
- Page size can be customized using the `?page_size=<number>` query parameter.
- Responses follow the DRF `PageNumberPagination` envelope:
  ```json
  {
    "count": 125,
    "next": "http://localhost:8000/inventory/api/products/?page=3&page_size=50",
    "previous": "http://localhost:8000/inventory/api/products/?page=1&page_size=50",
    "results": [
      { "id": "...", "name": "Sample product", "sku": "PROD-001", "...": "..." }
    ]
  }
  ```
  - `count` is the total records available for the current filter.
  - `next`/`previous` are absolute URLs or `null` when you've reached the end/beginning.
  - `results` contains the actual data array used to render tables, grids, or virtualized lists.
- Append `?page=<number>&page_size=<size>` to collection URLs (e.g., `/inventory/api/products/?page=3&page_size=50`) to fetch subsequent pages.
- When building infinite scroll or batched table views, persist and increment the `page` pointer until `next` is `null`, and merge each page's `results` into your local cache/state.
- Prefer showing loading spinners while fetching the next page and disable additional fetches if `next` is already `null` to avoid redundant requests.

**Advanced Filtering and Ordering:**
- All inventory endpoints support comprehensive filtering and ordering via query parameters.
- **Filtering**: Use field-specific parameters to narrow results (e.g., `?category=<uuid>&is_active=true`).
- **Ordering**: Use `?ordering=<field>` for ascending or `?ordering=-<field>` for descending order.
- **Search**: Use `?search=<term>` for full-text search across relevant fields.
- See individual endpoint documentation below for available filter and ordering options.

> **Tip**: Capture and re-use the token returned by the registration or login endpoints in every subsequent request that requires authentication.

---

## 2. Onboarding Flow (Public → Authenticated)

> **Heads up**: A dedicated `POST /accounts/api/auth/register/` endpoint is planned but not yet available in this branch. Until it ships, bootstrap both the owner account and the first business with the combined `register-business` endpoint below. Update the frontend to call this route directly to avoid 404s.

### 2.1 Create a user account (owner or employee)
- **Endpoint**: `POST /accounts/api/auth/register/`
- **Authentication**: Public
- **Payload**:
  ```json
  {
    "name": "Jane Doe",
    "email": "jane@example.com",
    "password": "verysecure123",
    "account_type": "OWNER" // or "EMPLOYEE"
  }
  ```
- **Response** (`201 Created`):
  ```json
  {
    "message": "Account created. Check your email for the verification link.",
    "user_id": "c642802f-...",
    "account_type": "OWNER"
  }
  ```
- **Owner flow**: Account is created inactive until the email is confirmed. After verification, the user can register a business.
- **Employee flow**: Registration succeeds only if a pending invitation exists for the provided email. When the email is verified, the account is linked automatically to the invited business with the `STAFF` role (or the role specified in the invite).

### 2.2 Verify email address
- **Endpoint**: `POST /accounts/api/auth/verify-email/`
- **Payload**:
  ```json
  { "token": "d3q09f..." }
  ```
- **Response** (`200 OK`):
  ```json
  {
    "message": "Email verified successfully. You can now log in.",
    "user_id": "c642802f-...",
    "account_type": "OWNER"
  }
  ```
- Tokens expire after 48 hours. Resubmit the registration form to generate a fresh link if required.
- Employee verification also activates the invited business membership.

### 2.3 Login existing user
- **Endpoint**: `POST /accounts/api/auth/login/`
- **Body schema**:
  ```json
  {
    "email": "jane@example.com",
    "password": "verysecure123"
  }
  ```
- **Response** (`200 OK`):
  ```json
  {
    "token": "9d2f4b6f0a0b47...",
    "user": { ...same structure as above... }
  }
  ```
  Store the token and include it in the `Authorization` header for the rest of the session.

### 2.4 Register a business (owners only)
- **Endpoint**: `POST /accounts/api/auth/register-business/`
- **Authentication**: Token required. The caller must be a verified owner. Employee accounts receive `403 Forbidden`.
- **Payload** (all required unless noted):
  ```json
  {
    "name": "Jane's Retail",
    "tin": "TIN-001122",
    "email": "contact@janesretail.com",
    "address": "14 Market Street, Accra",
    "phone_numbers": ["+233201112223", "+233501234567"],
    "website": "https://janesretail.com",           // optional
    "social_handles": {                              // optional
      "instagram": "@janesretail",
      "facebook": "janesretail"
    }
  }
  ```
- **Response** (`201 Created`):
  ```json
  {
    "business": {
      "id": "ac552552-...",
      "name": "Jane's Retail",
      "tin": "TIN-001122",
      "email": "contact@janesretail.com",
      "address": "14 Market Street, Accra",
      "website": "https://janesretail.com",
      "phone_numbers": ["+233201112223", "+233501234567"],
      "social_handles": {
        "instagram": "@janesretail",
        "facebook": "janesretail"
      },
      "owner": "c642802f-...",
      "owner_name": "Jane Doe",
      "memberships": [ ...owner membership data... ],
      "created_at": "2025-09-27T14:12:01Z",
      "updated_at": "2025-09-27T14:12:01Z"
    },
    "user": {
      "id": "c642802f-...",
      "name": "Jane Doe",
      "email": "jane@example.com",
      "email_verified": true,
      "account_type": "OWNER",
      "subscription_status": "Inactive",
      "is_active": true,
      "profile": null,
      "created_at": "2025-09-27T14:12:01Z",
      "updated_at": "2025-09-27T14:12:01Z"
    }
  }
  ```
- **Failure responses**: `403 Forbidden` (not a verified owner) or `400 Bad Request` when `tin`/`email` already exists.

> **Employee note**: Employees skip the business registration step. After verification, they can log in and access the invited business immediately. Attempting to hit the business registration endpoint returns `403 Forbidden`.

### 2.5 Logout
- **Endpoint**: `POST /accounts/api/auth/logout/`
- **Headers**: `Authorization` token required
- **Response**: `{"message": "Successfully logged out"}` and the token is invalidated server-side.

### 2.6 Change password
- **Endpoint**: `POST /accounts/api/auth/change-password/`
- **Body schema**:
  ```json
  {
    "old_password": "verysecure123",
    "new_password": "evenmoresecure456"
  }
  ```
- On success: `{ "message": "Password changed successfully" }` and all tokens are revoked.

### 2.7 Current user snapshot
- **Endpoint**: `GET /accounts/api/users/me/`
- **Response**: Same shape as the `user` object returned during login.

---

## 3. User & Role Management

> All endpoints in this section require a valid token. Users without the `Admin` role will only see or modify their own record unless noted.

| Resource | Endpoint | Notes |
| --- | --- | --- |
| Roles | `GET /accounts/api/roles/` | List available roles (e.g., Admin, Manager, Cashier, Warehouse Staff). |
| Users | `GET /accounts/api/users/` | Admins see everyone; others see only themselves. Supports `?search=` on `name`/`email`.
|  | `POST /accounts/api/users/` | Fields: `name`, `email`, `password`, optional `role`. |
|  | `PATCH /accounts/api/users/{id}/` | Update any mutable fields (password optional). |
|  | `POST /accounts/api/users/{id}/activate/` | Activate account. |
|  | `POST /accounts/api/users/{id}/deactivate/` | Deactivate account. |
| Profiles | `GET /accounts/api/profiles/` | Admins see all, others only their profile.
|  | `PATCH /accounts/api/profiles/{id}/` | Update `phone`, `address`, `date_of_birth`, `emergency_contact`.
| Audit logs | `GET /accounts/api/audit-logs/` | Optional filters: `?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD`. Non-admins only see their own actions.

### Business entities

| Resource | Endpoint | Payload essentials |
| --- | --- | --- |
| Businesses | `GET/POST /accounts/api/businesses/` | `name`, `tin`, `email`, `address`, optional `website`, `phone_numbers` (array), `social_handles` (object). `owner` auto-populates from the authenticated user during creation. |
| Business memberships | `GET/POST /accounts/api/business-memberships/` | Fields: `business` (UUID), `user` (UUID), `role` (one of `OWNER`, `ADMIN`, `MANAGER`, `STAFF`), `is_admin` (bool). Creating a membership sets `invited_by` to the current user automatically. |

---

## 4. Inventory Setup

All inventory endpoints live under `/inventory/api/` and require authentication.

### 4.1 Taxonomy & locations

| Resource | Fields |
| --- | --- |
| Categories (`/inventory/api/categories/`) | `name`, optional `description`, optional `parent` (UUID). `children` is read-only. |
| Warehouses (`/inventory/api/warehouses/`) | `name`, `location`, optional `manager` (user UUID). `manager_name` is read-only. |
| StoreFronts (`/inventory/api/storefronts/`) | `user` (owner UUID), `name`, `location`, optional `manager` (user UUID). |
| Business ↔ Warehouse (`/inventory/api/business-warehouses/`) | `business` UUID, `warehouse` UUID, optional `is_active`. Read-only `business_name`, `warehouse_name`. |
| Business ↔ StoreFront (`/inventory/api/business-storefronts/`) | `business`, `storefront`, optional `is_active`. |
| StoreFront employees (`/inventory/api/storefront-employees/`) | `business`, `storefront`, `user`, `role` (use `accounts.BusinessMembership.ROLE_CHOICES` values), `is_active`. `assigned_at`/`removed_at` are read-only. |
| Warehouse employees (`/inventory/api/warehouse-employees/`) | Same pattern as storefront employees. |

### 4.2 Products & stock lots

| Resource | Endpoint | Required fields | Read-only highlights | Filtering & Ordering |
| --- | --- | --- | --- | --- |
| Products | `/inventory/api/products/` | `name`, `sku`, `category`, `unit`, optional `description`, optional `is_active`. (Pricing fields are no longer exposed here.) | `category_name`, `created_at`, `updated_at` | **Filtering**: `?category=<uuid>&is_active=true&search=<term>`<br>**Ordering**: `?ordering=name` or `?ordering=-created_at`<br>**Search**: Searches in name and SKU |
| Stock (receipted lots) | `/inventory/api/stock/` | `warehouse`, `product`, `quantity`, `unit_cost`, optional `supplier`, `reference_code`, `arrival_date`, `expiry_date`, `unit_tax_rate` (nullable), `unit_tax_amount` (nullable), `unit_additional_cost` (nullable), `description`. | Derived pricing fields: `landed_unit_cost`, `total_tax_amount`, `total_additional_cost`, `total_landed_cost`. | **Filtering**: `?warehouse=<uuid>&search=<term>`<br>**Ordering**: `?ordering=-arrival_date`<br>**Search**: Searches in description |
| Stock Products | `/inventory/api/stock-products/` | `stock`, `product`, `quantity`, `unit_cost`, optional `supplier`, `expiry_date`, `unit_tax_rate` (nullable), `unit_tax_amount` (nullable), `unit_additional_cost` (nullable), `description`. | `landed_unit_cost`, `total_tax_amount`, `total_additional_cost`, `total_landed_cost`, `product_name`, `product_sku`, `supplier_name`. | **Filtering**: `?product=<uuid>&stock=<uuid>&supplier=<uuid>&has_quantity=true&search=<term>`<br>**Ordering**: `?ordering=-created_at` or `?ordering=quantity`<br>**Search**: Searches in product name and SKU |
| Suppliers | `/inventory/api/suppliers/` | `name`, optional `contact_person`, `email`, `phone_number`, `address`, `notes`. | `created_at`, `updated_at` | **Search**: `?search=<term>` (name, contact, email)<br>**Ordering**: `?ordering=name` |

> **Pricing shift**: Selling prices now originate from stock records or cashier input at the time of sale. The frontend must stop reading or writing `retail_price` / `wholesale_price` on `/inventory/api/products/` and instead derive price suggestions from `StockProduct` cost data or dedicated pricing UI controls.

> **Landed cost logic**: When `unit_tax_rate` is provided, the backend ALWAYS calculates `unit_tax_amount = unit_cost * unit_tax_rate / 100` (overriding any manual entry). When `unit_tax_rate` is null, manually entered `unit_tax_amount` is preserved. The `landed_unit_cost` is `unit_cost + unit_tax_amount + unit_additional_cost`. Keep UI consistent with these calculations.

**Query Examples:**
```bash
# Get products with pagination and filtering
GET /inventory/api/products/?page=2&page_size=10&category=<uuid>&is_active=true&search=laptop&ordering=name

# Get stock products with advanced filtering
GET /inventory/api/stock-products/?page=1&page_size=50&supplier=<uuid>&has_quantity=true&search=widget&ordering=-created_at

# Get stock batches for specific warehouse
GET /inventory/api/stock/?warehouse=<uuid>&ordering=-arrival_date&page_size=20

# Search suppliers
GET /inventory/api/suppliers/?search=acme&ordering=name
```

### 4.3 Inventory & transfers

| Resource | Endpoint | Notes |
| --- | --- | --- |
| Inventory snapshot | `/inventory/api/inventory/` | Denormalized view per `(warehouse, product, stock)` trio. `quantity` is mutable via PATCH/PUT if you build adjustments. Read-only fields expose linked stock cost data and supplier info. |
| Transfers | `/inventory/api/transfers/` | Fields: `product`, optional `stock`, `from_warehouse`, `to_storefront`, `quantity`, `status` (choices: `PENDING`, `IN_TRANSIT`, `COMPLETED`, `CANCELLED`), `requested_by`, optional `approved_by`, `note`. |
| Stock alerts | `/inventory/api/stock-alerts/` | Fields: `product`, `warehouse`, `alert_type` (`LOW_STOCK`, `OUT_OF_STOCK`, `EXPIRY_WARNING`), `current_quantity`, `threshold_quantity`, `is_resolved`. `resolved_at` auto-populates when resolved. |

### 4.4 Inventory reports

Two placeholder dashboards currently return empty arrays (ready for UI scaffolding):
- `GET /inventory/api/reports/inventory-summary/`
- `GET /inventory/api/reports/stock-arrivals/`

You can still build the UI skeleton that handles an empty list gracefully while waiting for backend data enrichment.

---

## 5. Sales Operations

All endpoints under `/sales/api/` require authentication.

### 5.1 Core resources

> **Reminder**: Check subscription status before enabling sale creation or payment processing UI. The backend will reject these operations when the business lacks an active subscription, so disable submit buttons and display upgrade messaging proactively.

| Resource | Key fields |
| --- | --- |
| Customers | `name`, optional `email`, `phone`, `address`, `credit_limit`. Server maintains `outstanding_balance`, `available_credit`, and flags. |
| Sales | `storefront`, optional `customer`, `user` (cashier), `total_amount`, `payment_type` (`CASH`, `CARD`, `MOBILE`, `CREDIT`, `MIXED`), `status` (`COMPLETED`, `PENDING`, `REFUNDED`, `PARTIAL`, `CANCELLED`), `type` (`RETAIL`, `WHOLESALE`), `amount_due`, `discount_amount`, `tax_amount`, unique `receipt_number`, optional `notes`.
| Sale items | `sale`, `product`, optional `stock`, `quantity`, `unit_price`, `discount_amount`, optional `tax_rate`, optional `tax_amount`, `total_price`. Missing `tax_amount` triggers automatic calculation from `tax_rate` and `quantity`.
| Payments | `sale` (optional if allocating to customer account), `customer`, `amount_paid`, `payment_method` (`CASH`, `MOMO`, `CARD`, `PAYSTACK`, `STRIPE`, `BANK_TRANSFER`), `status` (`SUCCESSFUL`, `PENDING`, `FAILED`, `CANCELLED`), optional gateway identifiers.
| Refunds | `sale`, `refund_type` (`FULL`, `PARTIAL`, `EXCHANGE`), `amount`, `reason`, `status` (`PENDING`, `APPROVED`, `PROCESSED`, `REJECTED`), `requested_by`, optional `approved_by`/`processed_by`.
| Refund items | `refund`, `sale_item`, `quantity`, `amount`.
| Credit transactions | `customer`, `transaction_type` (`CREDIT_SALE`, `PAYMENT`, `ADJUSTMENT`, `REFUND`), `amount`, `balance_before`, `balance_after`, optional `reference_id`, optional `description`.

### 5.2 Reports

> **Subscription check**: Access to revenue and customer credit reports is subscription-locked. Guard the pages and show a paywall or renewal CTA if the backend responds with `403`.

Currently implemented as empty shells (always return `[]` so UI must tolerate no data):
- `GET /sales/api/reports/sales/`
- `GET /sales/api/reports/customer-credit/`

---

## 6. Printable Inventory Valuation Report

The `reports` app exposes a fully functional export endpoint.

- **Endpoint**: `GET /reports/inventory/valuation/`
- **Headers**: Auth token required
- **Query parameters**:
  - `format` (optional): one of `excel` (default), `pdf`, `docx`
  - `warehouse_id` (optional): filter by warehouse UUID
  - `product_id` (optional)
  - `business_id` (optional): filters via warehouse business linkage
  - `min_quantity` (optional integer)
- **Response**: File download with accurate `Content-Type` and filename `inventory-valuation-YYYYMMDD_HHMMSS.<extension>`.
- **Payload contents** (for reference when previewing in UI):
  - Summary block totals: rows, distinct products, warehouses, quantity, tax, additional cost, total value.
  - Detailed rows per inventory record including landed cost calculations.

When building the UI, prefer asynchronous download handlers and show appropriate progress states.

---

## 7. Bookkeeping

All bookkeeping endpoints require authentication and currently expose CRUD without extra business logic. Shapes derive directly from models; consult `bookkeeping/models.py` for every field. Highlights:

| Endpoint | Purpose |
| --- | --- |
| `/bookkeeping/api/account-types/` | Manage chart-of-account groupings. |
| `/bookkeeping/api/accounts/` | CRUD for ledger accounts. |
| `/bookkeeping/api/journal-entries/` | Double-entry journals. Expect to provide nested debit/credit lines aligning with `LedgerEntry` records. |
| `/bookkeeping/api/ledger-entries/` | Low-level ledger lines. |
| `/bookkeeping/api/trial-balances/` | Period summaries. |
| `/bookkeeping/api/financial-periods/` | Manage fiscal periods. |
| `/bookkeeping/api/budgets/` | Budget tracking per account/period. |
| `/bookkeeping/api/reports/financial/` | Placeholder returning `[]`; UI should visualise “No data yet”. |

---

## 8. Subscription & Billing

Endpoints under `/subscriptions/api/` manage SaaS billing. A business must keep at least one active subscription record for revenue-critical modules (sales, payments, financial reports) to function.

| Resource | Fields |
| --- | --- |
| Plans | `name`, `price`, `billing_cycle`, `features` (JSON), etc. |
| Subscriptions | `business`, `plan`, `status`, `current_period_start/end`, `auto_renew`, etc. |
| Payments | `subscription`, `amount`, `status`, `transaction_reference`, etc. |
| Gateway configs | Store API keys per gateway. |
| Webhook events | Raw payload capture for reconciliation. |
| Usage tracking | Metered usage counters. |
| Invoices | Generated invoices per billing period. |

Special endpoints:
- `POST /subscriptions/api/webhooks/payment/` – Public webhook receiver (no auth header). Expect to relay gateway callbacks here.
- `GET /subscriptions/api/reports/subscriptions/` – Placeholder returning `[]`.

---

## 9. Error Handling & Validation

- Validation errors return `400` with a JSON body mapping field names to arrays of messages (standard DRF format).
- Authentication issues return `401 Unauthorized` when the token is missing or invalid, `403 Forbidden` when the user lacks permission.
- Record lookups that fail return `404`.
- Bulk operations are not currently exposed; all endpoints follow standard DRF pagination responses for list views.

Example validation error:
```json
{
  "business_tin": ["A business with this TIN already exists."]
}
```

---

## 10. Recommended Frontend Delivery Milestones

1. **Public onboarding experience**
   - Implement the business + owner registration form using the exact request schema above.
   - Handle success (store token, redirect to authenticated area) and show specific field errors from the response.

2. **Authentication shell**
   - Build login form and token storage (localStorage/secure storage).
   - Global HTTP client that injects the `Authorization` header and handles `401` → logout.
   - Implement logout + password change screens.

3. **Account dashboard**
   - Use `/accounts/api/users/me/` to populate the header/profile.
   - Provide UI for editing user profile and uploading optional picture URL (field exists in model though no upload endpoint yet).
   - Display current business metadata from `/accounts/api/businesses/` filtered by owner membership.

4. **Team & roles management**
   - Screens for inviting team members (create user, then create `BusinessMembership`).
   - Activation/deactivation controls via the dedicated endpoints.

5. **Inventory foundations**
   - Category management UI.
   - Warehouse/storefront management with business associations.
   - Staff assignment flows for warehouses/storefronts.

6. **Product catalog & stock intake**
   - Product CRUD matching serializer fields.
   - Stock intake form capturing cost, tax rate, additional costs, supplier metadata.
   - Inventory list view that surfaces landed cost figures.

7. **Transfers & stock alerts**
   - Transfer requests with status transitions.
   - Alerts dashboard with resolve toggle.

8. **Sales workflow**
   - Customer CRM module.
   - POS cart → sale creation: ensure you post sale, then sale items, then payments. Respect enumerated choices.
   - Credit sales UI tying into credit transactions and outstanding balances.

9. **After-sales**
   - Refund initiation screens (select sale items, specify quantities & amounts).
   - Payment history display per customer/sale.

10. **Reporting & exports**
    - Inventory valuation download button with filter controls.
    - Placeholder charts for sales/credit/bookkeeping/subscription reports (display empty states until backend fills them with data).

11. **Billing management**
    - Subscription plan selection and subscription status display for a business.
    - Invoice history and payment receipts.

---

## 11. Reference Tables (Enumerations)

| Context | Field | Allowed values |
| --- | --- | --- |
| `sales.Sale.payment_type` | `payment_type` | `CASH`, `CARD`, `MOBILE`, `CREDIT`, `MIXED` |
| `sales.Sale.status` | `status` | `COMPLETED`, `PENDING`, `REFUNDED`, `PARTIAL`, `CANCELLED` |
| `sales.Sale.type` | `type` | `RETAIL`, `WHOLESALE` |
| `sales.SaleItem.tax_rate` | `tax_rate` | Decimal percentage `0.00 - 100.00` |
| `sales.Payment.payment_method` | `payment_method` | `CASH`, `MOMO`, `CARD`, `PAYSTACK`, `STRIPE`, `BANK_TRANSFER` |
| `sales.Payment.status` | `status` | `SUCCESSFUL`, `PENDING`, `FAILED`, `CANCELLED` |
| `sales.Refund.refund_type` | `refund_type` | `FULL`, `PARTIAL`, `EXCHANGE` |
| `sales.Refund.status` | `status` | `PENDING`, `APPROVED`, `PROCESSED`, `REJECTED` |
| `inventory.Transfer.status` | `status` | `PENDING`, `IN_TRANSIT`, `COMPLETED`, `CANCELLED` |
| `inventory.StockAlert.alert_type` | `alert_type` | `LOW_STOCK`, `OUT_OF_STOCK`, `EXPIRY_WARNING` |
| `accounts.BusinessMembership.role` | `role` | `OWNER`, `ADMIN`, `MANAGER`, `STAFF` |
| `subscriptions.Subscription.status` | `status` | Platform-defined choices (see `subscriptions/models.py`). |

---

## 12. Testing & Mock Data

- Use `python manage.py createsuperuser` in development to fabricate data quickly via the Django admin.
- Emulate onboarding by hitting the registration endpoint locally; this seeds the `Business` and `BusinessMembership` automatically.
- For inventory valuation previews, populate `Stock` and `Inventory` tables so the `/reports/inventory/valuation/` export yields meaningful data.

---

### Need something else?
Ping the backend team with the exact endpoint and payload you need clarified. Every section here mirrors live code (`accounts`, `inventory`, `sales`, `bookkeeping`, `subscriptions`, `reports` apps), so feel free to build confidently on top of it.
