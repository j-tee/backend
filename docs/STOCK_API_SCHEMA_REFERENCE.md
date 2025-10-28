# Stock Management API Schema Reference

**Last Updated:** October 28, 2025  
**Status:** Current Implementation

---

## Overview

This document provides the complete API schema for Stock and StockProduct management in the POS system. Stock batches are now tied to the **business** (not warehouse), while individual stock products carry the **warehouse** relationship.

---

## 1. Stock Batch (Stock) Endpoints

### POST `/inventory/api/stock/` - Create Stock Batch

**Request Payload:**
```typescript
{
  // Optional fields only - business is auto-set from authenticated user
  arrival_date?: string;      // Format: "YYYY-MM-DD" (optional)
  description?: string;        // Optional description
}
```

**Example:**
```json
{
  "arrival_date": "2025-10-28",
  "description": "October shipment from supplier"
}
```

**Response (201 Created):**
```typescript
{
  id: string;                  // UUID
  business: string;            // UUID (auto-set, read-only)
  business_name: string;       // Read-only
  arrival_date: string | null; // "YYYY-MM-DD"
  description: string | null;
  warehouse_id: string | null; // Derived from first item (read-only)
  warehouse_name: string | null; // Derived from first item (read-only)
  total_items: number;         // Count of stock products (read-only)
  total_quantity: number;      // Sum of all quantities (read-only)
  items: StockProduct[];       // Array of stock products (read-only)
  created_at: string;          // ISO datetime
  updated_at: string;          // ISO datetime
}
```

**Notes:**
- `business` field is **automatically set** from the authenticated user's business membership
- Do **NOT** send `business` in the request - it will be ignored
- `warehouse_id` and `warehouse_name` are derived from the first stock product item (for convenience)

---

## 2. Stock Product (StockProduct) Endpoints

### POST `/inventory/api/stock-products/` - Create Stock Product

**Request Payload:**
```typescript
{
  // Required fields
  stock: string;               // UUID - Stock batch ID
  warehouse: string;           // UUID - Warehouse ID (REQUIRED!)
  product: string;             // UUID - Product ID
  quantity: number;            // Positive integer
  unit_cost: string;           // Decimal "0.00"
  
  // Optional fields
  supplier?: string;           // UUID - Supplier ID (nullable)
  expiry_date?: string;        // "YYYY-MM-DD" (nullable)
  unit_tax_rate?: string;      // Decimal "0.00" to "100.00" (nullable)
  unit_tax_amount?: string;    // Decimal "0.00" (auto-calculated if tax_rate provided)
  unit_additional_cost?: string; // Decimal "0.00" (nullable)
  retail_price?: string;       // Decimal "0.00" (defaults to 0)
  wholesale_price?: string;    // Decimal "0.00" (defaults to 0)
  description?: string;        // Text description (nullable)
}
```

**Example:**
```json
{
  "stock": "977d2c6e-5e-4f1b-9be8-8ff6024ba623",
  "warehouse": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "product": "633bcd1f-5393-ddec-9608-2f5491ba42b4",
  "supplier": "bd75dfe1-df36-4e53-9fce-bf3d6b71dd33",
  "quantity": 100,
  "unit_cost": "75.00",
  "unit_tax_rate": "3.00",
  "unit_additional_cost": "2.00",
  "retail_price": "100.00",
  "wholesale_price": "85.00",
  "description": "Premium quality items",
  "expiry_date": "2026-12-31"
}
```

**Response (201 Created):**
```typescript
{
  // Basic fields
  id: string;                  // UUID
  stock: string;               // UUID
  warehouse: string;           // UUID
  warehouse_name: string;      // Read-only
  product: string;             // UUID
  product_name: string;        // Read-only
  product_sku: string;         // Read-only
  supplier: string | null;     // UUID
  supplier_name: string | null; // Read-only
  
  // Inventory fields
  quantity: number;
  expiry_date: string | null;  // "YYYY-MM-DD"
  description: string | null;
  
  // Cost fields (writable)
  unit_cost: string;           // Decimal
  unit_tax_rate: string | null; // Decimal
  unit_tax_amount: string | null; // Decimal (auto-calculated)
  unit_additional_cost: string | null; // Decimal
  retail_price: string;        // Decimal
  wholesale_price: string;     // Decimal
  
  // Calculated cost fields (read-only)
  landed_unit_cost: string;    // unit_cost + unit_tax_amount + unit_additional_cost
  total_base_cost: string;     // unit_cost * quantity
  total_tax_amount: string;    // unit_tax_amount * quantity
  total_additional_cost: string; // unit_additional_cost * quantity
  total_landed_cost: string;   // landed_unit_cost * quantity
  
  // Profit calculations (read-only)
  expected_profit_amount: string;   // Based on retail price
  expected_profit_margin: string;   // Percentage
  expected_total_profit: string;    // Total profit at retail
  projected_retail_profit: string;  // If all sold at retail
  projected_wholesale_profit: string; // If all sold at wholesale
  
  // Timestamps
  created_at: string;          // ISO datetime
  updated_at: string;          // ISO datetime
}
```

**Notes:**
- `warehouse` field is **REQUIRED** - this is the main fix from the previous implementation
- If you provide `unit_tax_rate` without `unit_tax_amount`, it will be auto-calculated
- All calculated fields (landed costs, profit margins, etc.) are read-only and computed by the backend

---

## 3. GET Endpoints

### GET `/inventory/api/stock/` - List Stock Batches

Returns paginated list with the same structure as POST response.

**Query Parameters:**
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 25, max: 100)
- `ordering`: `-arrival_date`, `arrival_date`, `-created_at`, `created_at`
- `search`: Search in description

**Example:**
```
GET /inventory/api/stock/?page=1&page_size=25&ordering=-arrival_date
```

---

### GET `/inventory/api/stock/{id}/` - Get Single Stock Batch

Returns single stock batch with nested `items` array populated.

**Example:**
```
GET /inventory/api/stock/977d2c6e-5e-4f1b-9be8-8ff6024ba623/
```

---

### GET `/inventory/api/stock-products/` - List Stock Products

Returns paginated list with full calculation fields.

**Query Parameters:**
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 25, max: 100)
- `ordering`: `quantity`, `-quantity`, `unit_cost`, `-unit_cost`, `landed_unit_cost`, `-landed_unit_cost`, `expiry_date`, `-created_at`, etc.
- `search`: Search in product name, SKU, or description
- **Filters:**
  - `product`: Filter by product UUID
  - `warehouse`: Filter by warehouse UUID
  - `supplier`: Filter by supplier UUID
  - `stock`: Filter by stock batch UUID

**Example:**
```
GET /inventory/api/stock-products/?page=1&page_size=25&warehouse=a1b2c3d4&ordering=-created_at
```

---

### GET `/inventory/api/stock-products/{id}/` - Get Single Stock Product

Returns single stock product with all calculation fields.

**Example:**
```
GET /inventory/api/stock-products/f8b9a3c2-1234-5678-abcd-ef9876543210/
```

---

## 4. Key Changes Summary

| Aspect | Old (Incorrect) | New (Correct) |
|--------|----------------|---------------|
| **Stock.business** | ❌ Not sent/required | ✅ Auto-set from user, read-only |
| **Stock.warehouse** | ❌ Field existed on Stock | ✅ Removed - warehouse is on StockProduct |
| **StockProduct.warehouse** | ⚠️ Sometimes optional | ✅ **REQUIRED** - must be sent in payload |
| **Business association** | Via Stock.warehouse | Via Stock.business (direct FK) |

---

## 5. TypeScript Interface Definitions

### Stock Batch Interfaces

```typescript
/**
 * Payload for creating a new stock batch
 * Business is auto-set from authenticated user
 */
interface StockBatchCreatePayload {
  arrival_date?: string;      // Format: "YYYY-MM-DD"
  description?: string;
}

/**
 * Stock batch response from API
 */
interface StockBatch {
  id: string;
  business: string;           // Read-only
  business_name: string;      // Read-only
  arrival_date: string | null;
  description: string | null;
  warehouse_id: string | null;  // Read-only, derived from first item
  warehouse_name: string | null; // Read-only, derived from first item
  total_items: number;        // Read-only
  total_quantity: number;     // Read-only
  items: StockProduct[];      // Read-only
  created_at: string;
  updated_at: string;
}
```

### Stock Product Interfaces

```typescript
/**
 * Payload for creating a new stock product
 */
interface StockProductCreatePayload {
  // Required fields
  stock: string;              // Stock batch UUID
  warehouse: string;          // Warehouse UUID - REQUIRED!
  product: string;            // Product UUID
  quantity: number;           // Positive integer
  unit_cost: string;          // Decimal as string, e.g., "75.00"
  
  // Optional fields
  supplier?: string | null;   // Supplier UUID
  expiry_date?: string | null; // "YYYY-MM-DD"
  unit_tax_rate?: string | null; // "0.00" to "100.00"
  unit_tax_amount?: string | null; // Auto-calculated if not provided
  unit_additional_cost?: string | null; // "0.00"
  retail_price?: string;      // Defaults to "0.00"
  wholesale_price?: string;   // Defaults to "0.00"
  description?: string | null;
}

/**
 * Stock product response from API
 */
interface StockProduct {
  // Identifiers
  id: string;
  stock: string;
  warehouse: string;
  warehouse_name: string;     // Read-only
  product: string;
  product_name: string;       // Read-only
  product_sku: string;        // Read-only
  supplier: string | null;
  supplier_name: string | null; // Read-only
  
  // Inventory fields
  quantity: number;
  expiry_date: string | null;
  description: string | null;
  
  // Cost fields (writable)
  unit_cost: string;
  unit_tax_rate: string | null;
  unit_tax_amount: string | null;
  unit_additional_cost: string | null;
  retail_price: string;
  wholesale_price: string;
  
  // Calculated fields (all read-only)
  landed_unit_cost: string;
  total_base_cost: string;
  total_tax_amount: string;
  total_additional_cost: string;
  total_landed_cost: string;
  expected_profit_amount: string;
  expected_profit_margin: string;
  expected_total_profit: string;
  projected_retail_profit: string;
  projected_wholesale_profit: string;
  
  // Timestamps
  created_at: string;
  updated_at: string;
}
```

---

## 6. Cost Calculation Logic

### Tax Amount Calculation
If `unit_tax_rate` is provided but `unit_tax_amount` is not:
```
unit_tax_amount = (unit_cost × unit_tax_rate) ÷ 100
```

**Example:**
- `unit_cost` = 75.00
- `unit_tax_rate` = 3.00
- **Calculated:** `unit_tax_amount` = (75.00 × 3.00) ÷ 100 = 2.25

### Landed Unit Cost
```
landed_unit_cost = unit_cost + unit_tax_amount + unit_additional_cost
```

**Example:**
- `unit_cost` = 75.00
- `unit_tax_amount` = 2.25
- `unit_additional_cost` = 2.00
- **Calculated:** `landed_unit_cost` = 75.00 + 2.25 + 2.00 = 79.25

### Total Costs
```
total_base_cost = unit_cost × quantity
total_tax_amount = unit_tax_amount × quantity
total_additional_cost = unit_additional_cost × quantity
total_landed_cost = landed_unit_cost × quantity
```

### Profit Calculations
```
expected_profit_amount = retail_price - landed_unit_cost
expected_profit_margin = (expected_profit_amount ÷ retail_price) × 100
expected_total_profit = expected_profit_amount × quantity
projected_retail_profit = (retail_price - landed_unit_cost) × quantity
projected_wholesale_profit = (wholesale_price - landed_unit_cost) × quantity
```

---

## 7. Important Implementation Notes

### 1. Business Field
- **Never send the `business` field** in create/update requests
- It's automatically set from the authenticated user's business membership
- Marked as read-only in the serializer

### 2. Warehouse Field (Critical!)
- **Must be included** when creating StockProduct
- This is a **required field** in the model
- Frontend must send the warehouse UUID selected by the user

### 3. Decimal Fields
- Always send decimal values as **strings**, not numbers
- Correct: `"75.00"`, `"3.50"`
- Incorrect: `75`, `3.5`

### 4. Stock Batch Workflow

**Step 1:** Create stock batch
```json
POST /inventory/api/stock/
{
  "arrival_date": "2025-10-28",
  "description": "October shipment"
}
```

**Step 2:** Get the stock batch ID from response
```json
{
  "id": "977d2c6e-5e-4f1b-9be8-8ff6024ba623",
  ...
}
```

**Step 3:** Create stock products referencing that batch
```json
POST /inventory/api/stock-products/
{
  "stock": "977d2c6e-5e-4f1b-9be8-8ff6024ba623",
  "warehouse": "warehouse-uuid-here",
  "product": "product-uuid-here",
  "quantity": 100,
  "unit_cost": "75.00",
  ...
}
```

### 5. Validation Rules

**Product & Supplier:**
- Product must belong to the user's business
- Supplier must belong to the user's business
- Backend validates these automatically

**Warehouse:**
- Creates `BusinessWarehouse` relationship if it doesn't exist
- This links the warehouse to the user's business

### 6. Filtering & Searching

**Stock Batches:**
- Search in: description
- Order by: arrival_date, created_at

**Stock Products:**
- Search in: product name, product SKU, description
- Filter by: product, warehouse, supplier, stock batch
- Order by: quantity, unit_cost, landed_unit_cost, expiry_date, created_at

---

## 8. Common Frontend Scenarios

### Scenario A: Creating a new stock intake

```typescript
// 1. Create stock batch
const stockResponse = await api.post('/inventory/api/stock/', {
  arrival_date: '2025-10-28',
  description: 'New shipment'
});

const stockId = stockResponse.data.id;

// 2. For each product in the shipment, create stock product
const stockProductPayload = {
  stock: stockId,
  warehouse: selectedWarehouseId,  // From user selection
  product: selectedProductId,
  supplier: selectedSupplierId,
  quantity: 100,
  unit_cost: '75.00',
  unit_tax_rate: '3.00',
  unit_additional_cost: '2.00',
  retail_price: '100.00',
  wholesale_price: '85.00'
};

await api.post('/inventory/api/stock-products/', stockProductPayload);
```

### Scenario B: Listing stock products for a warehouse

```typescript
const response = await api.get('/inventory/api/stock-products/', {
  params: {
    warehouse: warehouseId,
    page: 1,
    page_size: 25,
    ordering: '-created_at'
  }
});

// Response includes all calculated fields
const products = response.data.results;
```

### Scenario C: Viewing stock batch details with items

```typescript
const response = await api.get(`/inventory/api/stock/${stockId}/`);

// Response includes nested items array
const stock = response.data;
console.log(stock.items);  // Array of StockProduct
console.log(stock.total_items);  // Count
console.log(stock.total_quantity);  // Sum of quantities
```

---

## 9. Error Responses

### Missing Required Field
```json
{
  "warehouse": ["This field is required."]
}
```

### Invalid Business Association
```json
{
  "product": ["Product does not belong to your business."]
}
```

### Validation Error
```json
{
  "unit_cost": ["Ensure this value is greater than or equal to 0.00."]
}
```

---

## 10. Migration Notes

### From Old Schema to New Schema

**Changed:**
- ✅ Stock batches now have direct `business` FK (not via warehouse)
- ✅ `business` field is auto-set and read-only
- ✅ Warehouse relationship moved from Stock to StockProduct

**Frontend Updates Needed:**
1. Remove `business` from Stock creation payloads
2. **Add `warehouse` to StockProduct creation payloads** (most critical!)
3. Update TypeScript interfaces to match new schema
4. Update form validation to require warehouse field
5. Update display logic to show `warehouse_id`/`warehouse_name` from Stock (derived fields)

---

## Questions or Issues?

If you encounter any issues or have questions about this API schema, please:
1. Check the serializer definitions in `inventory/serializers.py`
2. Review the viewset logic in `inventory/views.py`
3. Test the endpoints directly with tools like Postman or curl
4. Refer to the model definitions in `inventory/models.py`

---

**Document Version:** 1.0  
**Last Reviewed:** October 28, 2025
