# Frontend Integration Guide: Stock Management Updates

## Overview

This guide provides frontend developers with essential information about recent backend changes that affect frontend integration. These updates include new pricing fields, critical security enhancements for multi-tenant data isolation, and improved API capabilities.

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