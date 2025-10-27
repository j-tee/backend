# Stock Availability Endpoint

## Overview

The stock availability endpoint provides real-time information about product availability at a storefront, including active cart reservations. This is the **critical endpoint** that powers the POS system's ability to display prices and stock quantities.

## Endpoint

```
GET /inventory/api/storefronts/{storefront_id}/stock-products/{product_id}/availability/
```

## Authentication

- **Required**: Yes
- **Type**: Token Authentication
- **Header**: `Authorization: Token {your_token}`

## Permissions

- User must be employed at the specified storefront
- Verified through `StoreFrontEmployee` relationship

## URL Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `storefront_id` | UUID | The ID of the storefront |
| `product_id` | UUID | The ID of the product |

## Response

### Success Response (200 OK)

```json
{
  "total_available": 150,
  "reserved_quantity": 20,
  "unreserved_quantity": 130,
  "batches": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "batch_number": "BATCH-001",
      "quantity": 100,
      "retail_price": "15.50",
      "wholesale_price": "12.00",
      "expiry_date": "2025-12-31T00:00:00Z",
      "created_at": "2025-01-15T10:30:00Z"
    },
    {
      "id": "660e8400-e29b-41d4-a716-446655440001",
      "batch_number": "BATCH-002",
      "quantity": 50,
      "retail_price": "16.00",
      "wholesale_price": "12.50",
      "expiry_date": null,
      "created_at": "2025-01-20T14:45:00Z"
    }
  ],
  "reservations": [
    {
      "id": "770e8400-e29b-41d4-a716-446655440002",
      "quantity": 10,
      "sale_id": "880e8400-e29b-41d4-a716-446655440003",
      "customer_name": "John Doe",
      "expires_at": "2025-01-25T11:00:00Z",
      "created_at": "2025-01-25T10:30:00Z"
    },
    {
      "id": "990e8400-e29b-41d4-a716-446655440004",
      "quantity": 10,
      "sale_id": "aa0e8400-e29b-41d4-a716-446655440005",
      "customer_name": null,
      "expires_at": "2025-01-25T11:15:00Z",
      "created_at": "2025-01-25T10:45:00Z"
    }
  ]
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `total_available` | integer | Total quantity across all batches |
| `reserved_quantity` | integer | Quantity currently reserved in active carts |
| `unreserved_quantity` | integer | Available for new sales (total - reserved) |
| `batches` | array | Array of stock batches with pricing |
| `reservations` | array | Array of active cart reservations |

### Batch Object

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Unique batch identifier |
| `batch_number` | string | Human-readable batch number |
| `quantity` | integer | Quantity in this batch |
| `retail_price` | string (decimal) | Retail price per unit |
| `wholesale_price` | string (decimal) or null | Wholesale price per unit |
| `expiry_date` | ISO 8601 or null | Expiry date if applicable |
| `created_at` | ISO 8601 | When batch was created |

### Reservation Object

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Unique reservation identifier |
| `quantity` | integer | Reserved quantity |
| `sale_id` | UUID | ID of the DRAFT sale (cart) |
| `customer_name` | string or null | Customer name if assigned |
| `expires_at` | ISO 8601 | When reservation expires (30 min) |
| `created_at` | ISO 8601 | When reservation was created |

## Error Responses

### 403 Forbidden

User doesn't have access to the storefront:

```json
{
  "detail": "You do not have access to this storefront."
}
```

### 404 Not Found

Storefront doesn't exist:

```json
{
  "detail": "Storefront not found."
}
```

### 500 Internal Server Error

Unexpected error:

```json
{
  "detail": "Error retrieving stock availability: {error_message}"
}
```

## Business Logic

### Availability Calculation

1. **Total Available**: Sum of quantities across all `StockProduct` batches for the product at the storefront
2. **Reserved Quantity**: Sum of quantities in ACTIVE `StockReservation` records with unexpired `expires_at`
3. **Unreserved Quantity**: `max(0, total_available - reserved_quantity)`

### Reservation Status

- Only ACTIVE reservations with `expires_at > now()` are counted
- Expired reservations are automatically excluded
- Reservations are tied to DRAFT sales (carts)

### Batch Ordering

Batches are ordered by creation date (newest first) to show most recent stock first.

## Frontend Integration

### Display Product Price

Use the first batch's `retail_price` or `wholesale_price`:

```typescript
const response = await fetch(
  `/inventory/api/storefronts/${storefrontId}/stock-products/${productId}/availability/`,
  {
    headers: {
      'Authorization': `Token ${token}`
    }
  }
);

const data = await response.json();

// Display retail price
const price = data.batches[0]?.retail_price || '0.00';
console.log(`Price: GH₵ ${price}`);
```

### Display Stock Quantity

Use `unreserved_quantity` to show what's available for new sales:

```typescript
const stockBadge = data.unreserved_quantity > 0 
  ? `${data.unreserved_quantity} in stock`
  : 'Out of stock';
```

### Enable/Disable Add to Cart

```typescript
const canAddToCart = data.unreserved_quantity > 0;
addToCartButton.disabled = !canAddToCart;
```

### Show Active Reservations

Display how many units are in other customers' carts:

```typescript
if (data.reserved_quantity > 0) {
  console.log(`${data.reserved_quantity} units reserved in ${data.reservations.length} carts`);
}
```

## Example Usage

### Search and Display Product

```typescript
// 1. Search for product
const searchResponse = await fetch(
  `/inventory/api/products/?search=Coca%20Cola`,
  {
    headers: { 'Authorization': `Token ${token}` }
  }
);
const products = await searchResponse.json();
const product = products.results[0];

// 2. Get availability
const availResponse = await fetch(
  `/inventory/api/storefronts/${storefrontId}/stock-products/${product.id}/availability/`,
  {
    headers: { 'Authorization': `Token ${token}` }
  }
);
const availability = await availResponse.json();

// 3. Display to user
console.log(`Product: ${product.name}`);
console.log(`Price: GH₵ ${availability.batches[0]?.retail_price || '0.00'}`);
console.log(`Stock: ${availability.unreserved_quantity} units available`);
console.log(`Add to Cart: ${availability.unreserved_quantity > 0 ? 'Enabled' : 'Disabled'}`);
```

### Handle No Stock

```typescript
const availability = await fetchAvailability(storefrontId, productId);

if (availability.total_available === 0) {
  showMessage('This product is out of stock');
} else if (availability.unreserved_quantity === 0) {
  showMessage(`All ${availability.total_available} units are reserved in other carts`);
  showMessage(`${availability.reservations.length} active reservations`);
} else {
  showMessage(`${availability.unreserved_quantity} units available`);
}
```

## Performance Notes

- Endpoint runs 2-3 database queries:
  1. Get storefront and verify access
  2. Get all batches for product
  3. Get active reservations (if sales app installed)
- Uses `select_related` to minimize queries for reservation details
- Indexed on `(storefront_id, product_id)` for fast lookups

## Fallback Strategy

If this endpoint fails, frontend can fallback to:

```
GET /inventory/api/stock-products/?storefront={storefront_id}&product={product_id}
```

However, this fallback:
- ❌ Doesn't account for reservations
- ❌ Shows total stock, not unreserved
- ❌ May allow overselling if multiple carts active
- ✅ Does provide pricing information

**Recommendation**: Always use the availability endpoint for POS operations.

## Testing

### Test Case 1: Product with Stock

```bash
curl -H "Authorization: Token YOUR_TOKEN" \
  http://localhost:8000/inventory/api/storefronts/{storefront_id}/stock-products/{product_id}/availability/
```

Expected: `unreserved_quantity > 0`, batches array populated

### Test Case 2: Product with Reservations

1. Create DRAFT sale with items
2. Check availability
3. Expected: `reserved_quantity > 0`, reservations array populated

### Test Case 3: Product Out of Stock

Expected: `total_available = 0`, empty batches array

### Test Case 4: All Stock Reserved

Expected: `unreserved_quantity = 0`, but `total_available > 0`

## Troubleshooting

### Prices Show GH₵ 0.00

**Cause**: Batches array is empty or first batch has no price
**Solution**: Ensure `StockProduct` records exist with `retail_price` set

### Stock Shows "N/A"

**Cause**: Endpoint not found (404) or access denied (403)
**Solution**: Verify URL pattern, check user employment at storefront

### Reserved Quantity Incorrect

**Cause**: Expired reservations not filtered out
**Solution**: Reservations automatically filter `expires_at > now()`

### Add to Cart Always Disabled

**Cause**: `unreserved_quantity` is 0 (all stock reserved or out of stock)
**Solution**: Check `reserved_quantity` and `total_available` to diagnose

## Related Documentation

- [Sales Integration Guide](./frontend-sales-integration-guide.md)
- [Product Search Strategy](./PRODUCT_SEARCH_STRATEGY.md)
- [Backend API Documentation](./BACKEND_READY_FOR_FRONTEND.md)
- [Stock Request Backend Contract](./stock_request_backend_contract.md)

## Version History

- **v1.0** (2025-01-25): Initial implementation
  - Returns total_available, reserved_quantity, unreserved_quantity
  - Includes batches array with pricing
  - Includes reservations array for active carts
  - Multi-tenant access control
  - Handles sales app availability gracefully
