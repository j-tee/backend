# Stock Management API Documentation

## Overview

This document provides comprehensive API documentation for the stock management system, designed specifically for frontend developers implementing inventory management features. The system supports stock batches, individual stock items, and supplier management with full CRUD operations, pagination, filtering, and ordering capabilities.

## Core Concepts

### Stock Batches (`Stock`)
- **Purpose**: Containers for organizing inventory by arrival date and warehouse
- **Use Case**: Group related stock items from the same delivery or purchase order
- **Relationship**: Contains multiple `StockProduct` items

### Stock Products (`StockProduct`)
- **Purpose**: Individual stock line items with supplier-specific pricing and cost data
- **Use Case**: Track specific products within a stock batch with detailed cost information
- **Relationship**: Belongs to a `Stock` batch and references a `Product` and `Supplier`

### Suppliers (`Supplier`)
- **Purpose**: Track supplier information for cost analysis and procurement
- **Use Case**: Link stock items to suppliers for supplier performance tracking

## API Endpoints

### Stock Batches

#### List Stock Batches
```http
GET /inventory/api/stock/
```

**Query Parameters:**
- `page` (integer): Page number (default: 1)
- `page_size` (integer): Items per page (default: 25, max: 100)
- `warehouse` (UUID): Filter by warehouse ID
- `search` (string): Search in stock description
- `ordering` (string): Sort field (e.g., `-arrival_date`, `created_at`)

**Response:**
```json
{
  "count": 150,
  "next": "http://localhost:8000/inventory/api/stock/?page=2",
  "previous": null,
  "results": [
    {
      "id": "uuid",
      "warehouse": "warehouse-uuid",
      "warehouse_name": "Main Warehouse",
      "arrival_date": "2025-10-01",
      "description": "October Electronics Shipment",
      "created_at": "2025-10-01T10:00:00Z",
      "updated_at": "2025-10-01T10:00:00Z",
      "items": [
        {
          "id": "stock-product-uuid",
          "product": "product-uuid",
          "product_name": "Wireless Mouse",
          "product_sku": "WM-001",
          "supplier": "supplier-uuid",
          "supplier_name": "Tech Supplies Inc",
          "expiry_date": null,
          "quantity": 50,
          "unit_cost": "15.00",
          "unit_tax_rate": "10.00",
          "unit_tax_amount": "1.50",
          "unit_additional_cost": "2.00",
          "retail_price": "25.00",
          "wholesale_price": "20.00",
          "landed_unit_cost": "18.50",
          "total_tax_amount": "75.00",
          "total_additional_cost": "100.00",
          "total_landed_cost": "925.00",
          "description": "Black wireless mouse",
          "created_at": "2025-10-01T10:00:00Z",
          "updated_at": "2025-10-01T10:00:00Z"
        }
      ]
    }
  ]
}
```

#### Create Stock Batch
```http
POST /inventory/api/stock/
```

**Request Body:**
```json
{
  "warehouse": "warehouse-uuid",
  "arrival_date": "2025-10-01",
  "description": "October Electronics Shipment"
}
```

**Response:** Stock batch object (same as list format)

#### Update Stock Batch
```http
PATCH /inventory/api/stock/{id}/
```

**Request Body:** (partial update supported)
```json
{
  "description": "Updated shipment description",
  "arrival_date": "2025-10-02"
}
```

#### Delete Stock Batch
```http
DELETE /inventory/api/stock/{id}/
```

**Response:** `204 No Content`

### Stock Products

#### List Stock Products
```http
GET /inventory/api/stock-products/
```

**Query Parameters:**
- `page` (integer): Page number (default: 1)
- `page_size` (integer): Items per page (default: 25, max: 100)
- `product` (UUID): Filter by product ID
- `stock` (UUID): Filter by stock batch ID
- `supplier` (UUID): Filter by supplier ID
- `has_quantity` (boolean): Filter items with quantity > 0
- `search` (string): Search in product name and SKU
- `ordering` (string): Sort field (e.g., `-created_at`, `quantity`, `unit_cost`)

**Response:**
```json
{
  "count": 500,
  "next": "http://localhost:8000/inventory/api/stock-products/?page=2",
  "previous": null,
  "results": [
    {
      "id": "uuid",
      "stock": "stock-batch-uuid",
      "warehouse_name": "Main Warehouse",
      "product": "product-uuid",
      "product_name": "Wireless Mouse",
      "product_sku": "WM-001",
      "supplier": "supplier-uuid",
      "supplier_name": "Tech Supplies Inc",
      "expiry_date": "2026-10-01",
      "quantity": 50,
      "unit_cost": "15.00",
      "unit_tax_rate": "10.00",
      "unit_tax_amount": "1.50",
      "unit_additional_cost": "2.00",
      "retail_price": "25.00",
      "wholesale_price": "20.00",
      "landed_unit_cost": "18.50",
      "total_tax_amount": "75.00",
      "total_additional_cost": "100.00",
      "total_landed_cost": "925.00",
      "description": "Black wireless mouse",
      "created_at": "2025-10-01T10:00:00Z",
      "updated_at": "2025-10-01T10:00:00Z"
    }
  ]
}
```

#### Create Stock Product
```http
POST /inventory/api/stock-products/
```

**Request Body:**
```json
{
  "stock": "stock-batch-uuid",
  "product": "product-uuid",
  "supplier": "supplier-uuid", // optional
  "expiry_date": "2026-10-01", // optional
  "quantity": 50,
  "unit_cost": "15.00",
  "unit_tax_rate": "10.00", // optional, nullable, calculates unit_tax_amount
  "unit_tax_amount": "1.50", // optional, nullable if unit_tax_rate provided
  "unit_additional_cost": "2.00", // optional, nullable
  "retail_price": "25.00", // optional
  "wholesale_price": "20.00", // optional
  "description": "Black wireless mouse" // optional
}
```

**Cost Calculation Logic:**
- If `unit_tax_rate` is provided, backend ALWAYS calculates: `unit_tax_amount = unit_cost * unit_tax_rate / 100` (overrides any manually entered tax_amount)
- If `unit_tax_rate` is null/None, manually entered `unit_tax_amount` is preserved
- `landed_unit_cost = unit_cost + unit_tax_amount + unit_additional_cost`
- Total fields are calculated: `total_* = unit_* * quantity`

#### Update Stock Product
```http
PATCH /inventory/api/stock-products/{id}/
```

**Request Body:** (partial update supported)
```json
{
  "quantity": 45,
  "unit_cost": "16.00",
  "retail_price": "26.00",
  "wholesale_price": "21.00",
  "description": "Updated description"
}
```

#### Delete Stock Product
```http
DELETE /inventory/api/stock-products/{id}/
```

**Response:** `204 No Content`

### Suppliers

#### List Suppliers
```http
GET /inventory/api/suppliers/
```

**Query Parameters:**
- `page` (integer): Page number (default: 1)
- `page_size` (integer): Items per page (default: 25, max: 100)
- `search` (string): Search in name, contact person, and email
- `ordering` (string): Sort field (e.g., `name`, `-created_at`)

**Response:**
```json
{
  "count": 25,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "uuid",
      "name": "Tech Supplies Inc",
      "contact_person": "John Smith",
      "email": "john@techsupplies.com",
      "phone_number": "+1-555-0123",
      "address": "123 Tech Street, Silicon Valley, CA",
      "notes": "Reliable supplier for electronics",
      "created_at": "2025-09-01T10:00:00Z",
      "updated_at": "2025-09-01T10:00:00Z"
    }
  ]
}
```

#### Create Supplier
```http
POST /inventory/api/suppliers/
```

**Request Body:**
```json
{
  "name": "Tech Supplies Inc",
  "contact_person": "John Smith",
  "email": "john@techsupplies.com",
  "phone_number": "+1-555-0123",
  "address": "123 Tech Street, Silicon Valley, CA",
  "notes": "Reliable supplier for electronics"
}
```

#### Update Supplier
```http
PATCH /inventory/api/suppliers/{id}/
```

**Request Body:** (partial update supported)
```json
{
  "contact_person": "Jane Smith",
  "phone_number": "+1-555-0124"
}
```

#### Delete Supplier
```http
DELETE /inventory/api/suppliers/{id}/
```

**Response:** `204 No Content`

## Frontend Integration Examples

### Basic API Usage Patterns

**Filtering and Pagination:**
```
# Get stock products with filters
GET /inventory/api/stock-products/?page=2&page_size=10&supplier=<uuid>&has_quantity=true&search=widget&ordering=-created_at

# Get stock batches for specific warehouse
GET /inventory/api/stock/?warehouse=<uuid>&ordering=-arrival_date&page_size=20

# Search suppliers
GET /inventory/api/suppliers/?search=acme&ordering=name
```

**Creating Stock Products:**
```json
POST /inventory/api/stock-products/
{
  "stock": "stock-batch-uuid",
  "product": "product-uuid",
  "supplier": "supplier-uuid",
  "quantity": 50,
  "unit_cost": "15.00",
  "unit_tax_rate": "10.00",
  "unit_additional_cost": "2.00",
  "retail_price": "25.00",
  "wholesale_price": "20.00",
  "description": "Product description"
}
```

**Updating Stock Items:**
```json
PATCH /inventory/api/stock-products/{id}/
{
  "quantity": 45,
  "unit_cost": "16.00",
  "retail_price": "26.00",
  "wholesale_price": "21.00"
}
```

## Business Logic Considerations

### Cost Calculations
- **Unit Tax Amount**: Automatically calculated when `unit_tax_rate` is provided
- **Landed Unit Cost**: `unit_cost + unit_tax_amount + unit_additional_cost`
- **Total Costs**: All total fields are calculated as `unit_field * quantity`

### Business Scoping
- All endpoints automatically scope data to the authenticated user's businesses
- Users can only access products, stock, and suppliers from warehouses and businesses they have permission to manage
- Suppliers are scoped to those associated with the user's business stock
- **Security Enhancement**: Recent critical security update implemented business-level data isolation to prevent cross-business data access in the multi-tenant SaaS platform

### Validation Rules
- Stock products must belong to a valid stock batch
- Quantities must be positive integers
- Costs must be valid decimal numbers
- Expiry dates must be in the future for new stock

## Error Handling

### Common Error Responses

**400 Bad Request:**
```json
{
  "stock": ["This field is required."],
  "quantity": ["Ensure this value is greater than or equal to 0."]
}
```

**403 Forbidden:**
```json
{
  "detail": "You do not have permission to access this stock item."
}
```

**404 Not Found:**
```json
{
  "detail": "Not found."
}
```

### Frontend Error Handling Example

```javascript
const handleApiError = (error) => {
  if (error.response?.status === 400) {
    // Validation errors - show field-specific messages
    const validationErrors = error.response.data;
    Object.keys(validationErrors).forEach(field => {
      showFieldError(field, validationErrors[field].join(', '));
    });
  } else if (error.response?.status === 403) {
    // Permission error
    showNotification('You do not have permission to perform this action', 'error');
  } else if (error.response?.status === 404) {
    // Not found
    showNotification('The requested item was not found', 'error');
  } else {
    // Generic error
    showNotification('An unexpected error occurred', 'error');
  }
};
```

## Performance Optimization Tips

1. **Pagination**: Always use pagination for large datasets
2. **Filtering**: Apply filters to reduce data transfer
3. **Search**: Use search sparingly and debounce user input
4. **Caching**: Cache supplier/product data to avoid repeated API calls
5. **Batch Operations**: Consider batch create/update operations for bulk imports

## Testing Recommendations

### Unit Tests
- Test cost calculation logic
- Test filter and search functionality
- Test pagination behavior
- Test business scoping and data isolation
- Test permission checks for cross-business access prevention

### Integration Tests
- Test full CRUD workflows
- Test cross-entity relationships
- Test permission boundaries and business scoping
- Test error scenarios
- Test multi-tenant data isolation

### E2E Tests
- Test complete stock management workflows
- Test data consistency across related entities
- Test performance with large datasets

---

*This documentation is specifically designed for frontend developers implementing stock management features. For backend implementation details, refer to the main product implementation changes document. For security implementation details regarding business scoping, see the business-scoping-security-fix.md document.*</content>
<parameter name="filePath">/home/teejay/Documents/Projects/pos/backend/docs/stock-management-api.md