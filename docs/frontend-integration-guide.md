# Frontend Integration Guide: Stock Management Updates

## Overview

This guide provides frontend developers with essential information about recent backend changes that affect frontend integration. These updates include new pricing fields, critical security enhancements for multi-tenant data isolation, improved API capabilities, and role-based access control (RBAC) primitives that the frontend must respect.

---

## RBAC Integration Checklist

### 1. Understand the Role Model

- **Platform roles (`accounts.User.platform_role`)** drive cross-business capabilities. Options: `SUPER_ADMIN`, `SAAS_ADMIN`, `SAAS_STAFF`, `NONE`.
- **Business roles (`accounts.BusinessMembership.role`)** drive in-business capabilities. Options: `OWNER`, `ADMIN`, `MANAGER`, `STAFF`.
- **Admins vs Managers vs Staff**: `OWNER` and `ADMIN` are always managers (`is_admin=true`). `MANAGER` and `STAFF` are non-admin roles with progressively limited rights.
- **Role matrix field**: Every membership detail response returns a `role_matrix` block so UI code can gate features without re-implementing backend logic.

### 2. Fetch Capability Data

- Use `GET /inventory/api/memberships/` to list memberships for the signed-in user (requires the user to be an active member). Each row includes `platform_role` and summaries.
- Use `GET /inventory/api/memberships/{membership_id}/` to obtain the definitive `role_matrix` for a specific business membership. Example response:

```json
{
  "id": "b1b18062-9d42-44b3-a368-5b0ded51ce7e",
  "business": "43e1b7f7-d76d-4420-bd12-7e25fb016174",
  "user": {
    "id": "6e2c6f9b-53f8-4af6-81f2-1814cfb8ef99",
    "name": "Ama Mensah",
    "email": "ama@example.com",
    "is_active": true,
    "platform_role": "SAAS_ADMIN"
  },
  "role": "ADMIN",
  "is_admin": true,
  "is_active": true,
  "status": "ACTIVE",
  "platform_role": "SAAS_ADMIN",
  "role_matrix": {
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
  },
  "assigned_storefronts": [
    {
      "id": "0a38e1b8-20a6-45d8-9f30-70a89cf0c758",
      "name": "Downtown Store",
      "location": "Accra Central"
    }
  ]
}
```

### 3. Derive Frontend Permissions

- Parse the `role_matrix` to toggle UI affordances. Suggested mapping:
  - `role_matrix.business.is_owner` → allow plan management, invitation revocation, destructive business actions.
  - `role_matrix.business.is_admin` → allow inviting employees, updating memberships, assigning storefronts.
  - `role_matrix.business.is_manager` → allow storefront schedule/roster edits but not membership role changes.
  - `role_matrix.platform.is_platform_super_admin` → show global admin console, platform-wide analytics.
  - `role_matrix.platform.is_platform_admin` → allow cross-business read/write actions where exposed.
  - `role_matrix.platform.is_platform_staff` → allow support tooling that should remain read-only.
- Always evaluate both business and platform contexts before unlocking actions. For example, a `SAAS_STAFF` user who is not part of a business should remain read-only across business-specific UIs.

### 4. Cache & Refresh Strategy

- Cache the `role_matrix` per `(user, business)` pair in state management (e.g., Redux slice, React query cache).
- Invalidate the cache after membership mutations (PATCH/DELETE) or authentication changes.
- Fallback strategy: treat users as `STAFF` with `NONE` platform role until data loads to prevent accidental exposure.

### 5. Handling Denied Actions

- Backend returns `403` with `"detail": "You do not have permission to perform this action."` when RBAC denies an operation.
- Surface human-friendly messages (e.g., “You need admin access to invite employees”). Optionally read `error.detail` strings for diagnostics.
- Log permission denials (without sensitive data) for observability dashboards.

### 6. Mutating Platform Roles (Super Admin Only)

- Only users with `role_matrix.platform.is_platform_super_admin = true` can change another user’s platform role via `PATCH /inventory/api/memberships/{id}/` with `"platform_role": "SAAS_ADMIN" | "SAAS_STAFF" | "NONE"`.
- Non-super-admin callers will receive HTTP 403; frontends should hide platform-role dropdowns unless the viewer is a super admin.
- Always submit business role updates and platform role updates in a single PATCH if both change to avoid race conditions.

### 7. UX Recommendations

- Display both platform and business roles in user profiles, e.g., “SaaS Admin · Business Admin”.
- For multi-business users, show role chips per business membership using the `role_matrix` data.
- Provide read-only tooltips describing capabilities (e.g., “Can invite employees”) derived from the RBAC mapping to set user expectations.

---

## Critical Security Update: Business Scoping

### What Changed
A critical security vulnerability has been fixed that ensures proper data isolation between businesses in the multi-tenant SaaS platform. All inventory-related data (products, suppliers, stock) is now scoped to specific businesses.

### Frontend Implications

#### API Behavior Changes
- **Automatic Filtering**: All API endpoints now automatically filter data by the authenticated user's business permissions
- **403 Forbidden Responses**: Attempts to access data from unauthorized businesses will return 403 errors
- **Data Isolation**: Users can only see products, suppliers, and stock from businesses they have access to

#### Authentication Requirements
Ensure proper authentication headers are always sent with API requests:
```
Authorization: Token <user_token>
Content-Type: application/json
```

#### Error Response Changes
New error responses related to business scoping:
```json
{
  "detail": "You do not have permission to access this stock item."
}
```

#### Business Context Awareness
Frontend applications should be aware that:
- All data is automatically scoped to user's businesses
- Business selection UI may be needed for multi-business users
- API responses only include data from authorized businesses

## New Pricing Fields

### StockProduct Model Updates

#### New Fields Added
- `retail_price`: Suggested retail selling price per unit
- `wholesale_price`: Suggested wholesale selling price per unit

#### API Response Changes
Stock product API responses now include the new pricing fields:

```json
{
  "id": "uuid",
  "stock": "stock-batch-uuid",
  "product": "product-uuid",
  "supplier": "supplier-uuid",
  "quantity": 50,
  "unit_cost": "15.00",
  "unit_tax_rate": "10.00",
  "unit_tax_amount": "1.50",
  "unit_additional_cost": "2.00",
  "retail_price": "25.00",      // NEW FIELD
  "wholesale_price": "20.00",   // NEW FIELD
  "landed_unit_cost": "18.50",
  "total_tax_amount": "75.00",
  "total_additional_cost": "100.00",
  "total_landed_cost": "925.00",
  "description": "Product description",
  "created_at": "2025-10-01T10:00:00Z",
  "updated_at": "2025-10-01T10:00:00Z"
}
```

### Frontend Form Updates Required

#### Stock Product Creation Form
Frontend forms for creating stock products must now include:
- `retail_price` field (optional, decimal)
- `wholesale_price` field (optional, decimal)
- `unit_tax_rate` field (optional, nullable, decimal)
- `unit_tax_amount` field (optional, nullable, decimal)
- `unit_additional_cost` field (optional, nullable, decimal)

#### Validation Requirements
New validation rules for pricing fields:
- Retail and wholesale prices cannot be negative
- Retail price should typically be higher than wholesale price
- All pricing fields must be valid decimal numbers
- **When `unit_tax_rate` is provided, `unit_tax_amount` is automatically calculated and cannot be manually overridden**

#### API Request Format
Stock product creation/update requests should include the new fields:
```json
{
  "stock": "stock-batch-uuid",
  "product": "product-uuid",
  "supplier": "supplier-uuid",
  "quantity": 50,
  "unit_cost": "15.00",
  "unit_tax_rate": "10.00",        // optional, nullable - ALWAYS determines tax_amount when provided
  "unit_tax_amount": "1.50",       // optional, nullable - auto-calculated from tax_rate if provided
  "unit_additional_cost": "2.00",  // optional, nullable
  "retail_price": "25.00",         // optional
  "wholesale_price": "20.00",      // optional
  "expiry_date": "2026-10-01",
  "description": "Product description"
}
```

## Enhanced API Capabilities

### Pagination, Filtering, and Ordering

#### Updated API Parameters
All list endpoints now support enhanced pagination, filtering, and ordering:

**Common Parameters:**
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 25, max: 100)
- `ordering`: Sort field (prefix with `-` for descending)
- `search`: Full-text search across relevant fields

**Product-specific Filters:**
- `category`: Filter by product category
- `is_active`: Filter by active status (true/false)

**Stock Product-specific Filters:**
- `product`: Filter by product UUID
- `stock`: Filter by stock batch UUID
- `supplier`: Filter by supplier UUID
- `has_quantity`: Filter items with quantity > 0 (true/false)

#### Response Format
All paginated endpoints return:
```json
{
  "count": 150,
  "next": "http://api.example.com/products/?page=3",
  "previous": "http://api.example.com/products/?page=1",
  "results": [
    // Array of items
  ]
}
```

### API Endpoint Updates

#### Products
- `GET /products/?search=laptop&category=electronics&ordering=name`
- `GET /products/?is_active=true&page_size=50`

#### Stock Products
- `GET /stock-products/?product=uuid&has_quantity=true`
- `GET /stock-products/?supplier=uuid&ordering=-created_at`

#### Suppliers
- `GET /suppliers/?search=acme&ordering=name`

## Business Context Management

### Business Selection Requirements
For users with access to multiple businesses, frontend applications should provide business selection functionality. The backend automatically scopes all data access based on the authenticated user's current business context.

### API Behavior with Business Context
- All inventory API calls automatically filter data by the user's accessible businesses
- No business ID parameters needed in API requests - scoping is handled server-side
- Business context is determined by user authentication and role permissions

### Error Handling for Business Context
When business scoping violations occur, the API returns:
```json
{
  "detail": "You do not have permission to perform this action.",
  "code": "permission_denied"
}
```

Frontend applications should handle these errors by:
- Displaying user-friendly error messages
- Checking user authentication status
- Potentially prompting business selection if multi-business support is enabled

## Migration Steps for Frontend Code

### Phase 1: Security and Authentication Updates
1. **Update API client configuration** to ensure authentication headers are always sent
2. **Add business context management** to store user's accessible businesses
3. **Update error handling** to properly handle 403 responses for business scoping violations
4. **Add business selector component** if multi-business support is needed

### Phase 2: UI Updates for New Pricing Fields
1. **Update stock product forms** to include retail_price and wholesale_price fields
2. **Add validation** for the new pricing fields
3. **Update table/list views** to display the new pricing columns
4. **Add pricing display components** for better price visualization

### Phase 3: API Integration Improvements
1. **Implement pagination components** for all list views
2. **Add filtering and search capabilities** to product and stock management pages
3. **Update data loading patterns** to use the enhanced API features
4. **Add loading states and error boundaries** for better UX

### Phase 4: Testing and Validation
1. **Update unit tests** to cover new pricing fields and business scoping
2. **Add integration tests** for API pagination and filtering
3. **Test business isolation** to ensure proper data scoping
4. **Validate error handling** for permission-related scenarios

## Performance Considerations

### API Optimization
1. **Debounced Search**: Implement debouncing for search inputs to reduce API calls
2. **Pagination Limits**: Respect the 100 item maximum page size limit
3. **Caching Strategy**: Cache category and supplier data to reduce repeated requests
4. **Lazy Loading**: Load detailed data only when needed

### Frontend Performance
1. **Virtual Scrolling**: For large lists, implement virtual scrolling
2. **Memoization**: Use appropriate memoization techniques for expensive components
3. **State Management**: Optimize state updates to prevent unnecessary re-renders
4. **Bundle Splitting**: Split code to reduce initial bundle size

## Support and Resources

### Documentation References
- [Stock Management API Documentation](./stock-management-api.md)
- [Business Scoping Security Fix](./business-scoping-security-fix.md)
- [Product Implementation Changes](./product-implementation-changes.md)

### API Endpoints Summary
- `GET /inventory/api/products/` - List/Create products
- `GET /inventory/api/stock-products/` - List/Create stock products
- `GET /inventory/api/suppliers/` - List/Create suppliers
- `GET /inventory/api/stock/` - List/Create stock batches

### Getting Help
1. Check the API documentation for endpoint specifications
2. Review error responses for specific error messages
3. Test API calls using tools like Postman or curl
4. Contact backend team for authentication or permission issues

---

*This guide should be used alongside the updated API documentation. For any questions or clarifications, please refer to the backend team or check the latest API documentation.*</content>
<parameter name="filePath">/home/teejay/Documents/Projects/pos/backend/docs/frontend-integration-guide.md