# Frontend Sales Integration Guide

Complete API reference for building the Sales POS frontend.

## 📋 Table of Contents
1. [Authentication](#authentication)
2. [Product Search API](#product-search-api)
3. [Cart Management API](#cart-management-api)
4. [Customer Management API](#customer-management-api)
5. [Sales History API](#sales-history-api)
6. [Complete Workflow Examples](#complete-workflow-examples)
7. [Error Handling](#error-handling)
8. [WebSocket Updates (Future)](#websocket-updates)

---

## 🔐 Authentication

All API requests require authentication via Token.

### Login
```http
POST /accounts/api/auth/login/
Content-Type: application/json

{
  "username": "user@example.com",
  "password": "password123"
}
```

**Response:**
```json
{
  "token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b",
  "user": {
    "id": "uuid",
    "username": "user@example.com",
    "email": "user@example.com",
    "name": "John Doe"
  },
  "business": {
    "id": "uuid",
    "name": "My Store"
  }
}
```

### Using the Token
Include in all subsequent requests:
```http
Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b
```

---

## 🔍 Product Search API

### 1. Search Products
**Endpoint:** `GET /inventory/api/products/`

**Query Parameters:**
- `search` - Search in name and SKU
- `category` - Filter by category UUID
- `is_active` - Filter active products (true/false)
- `page` - Page number (default: 1)
- `page_size` - Items per page (default: 25, max: 100)
- `ordering` - Sort by field (name, sku, created_at, -name for descending)

**Examples:**

```http
# Search for "milk"
GET /inventory/api/products/?search=milk&is_active=true
```

```http
# Get products with pagination
GET /inventory/api/products/?page=1&page_size=20&ordering=name
```

**Response:**
```json
{
  "count": 150,
  "next": "http://localhost:8000/inventory/api/products/?page=2",
  "previous": null,
  "results": [
    {
      "id": "uuid",
      "name": "Fresh Milk 1L",
      "sku": "MILK-001",
      "description": "Fresh whole milk",
      "category": "uuid",
      "category_name": "Dairy",
      "barcode": "1234567890123",
      "unit": "piece",
      "reorder_level": 10.00,
      "is_active": true,
      "image": "/media/products/milk.jpg",
      "created_at": "2025-10-01T10:00:00Z",
      "updated_at": "2025-10-03T15:30:00Z"
    }
  ]
}
```

### 2. Get Product Stock Levels
**Endpoint:** `GET /inventory/api/stock-products/`

**Query Parameters:**
- `product` - Filter by product UUID
- `stock` - Filter by stock/batch UUID
- `has_quantity` - Only products with stock > 0 (true/false)
- `search` - Search in product name/SKU

**Example:**
```http
# Get stock for a specific product at all locations
GET /inventory/api/stock-products/?product=<product_uuid>&has_quantity=true
```

**Response:**
```json
{
  "count": 3,
  "results": [
    {
      "id": "uuid",
      "product": "uuid",
      "product_name": "Fresh Milk 1L",
      "product_sku": "MILK-001",
      "stock": "uuid",
      "stock_name": "Batch-2025-001",
      "supplier": "uuid",
      "supplier_name": "ABC Suppliers",
      "quantity": 50.00,
      "purchase_price": 1.50,
      "wholesale_price": 2.00,
      "retail_price": 2.50,
      "available_quantity": 45.00,  // After reservations
      "created_at": "2025-10-01T08:00:00Z"
    }
  ]
}
```

**Note:** `available_quantity` shows stock minus active reservations (items in other carts).

### 3. Get Product by Barcode
```http
GET /inventory/api/products/?search=<barcode>
```

Since barcode search isn't explicitly implemented, use the general search which searches name and SKU. If you need dedicated barcode scanning, let me know and I'll add a custom endpoint.

### 4. Get Categories (for filtering)
```http
GET /inventory/api/categories/
```

**Response:**
```json
{
  "count": 10,
  "results": [
    {
      "id": "uuid",
      "name": "Dairy",
      "description": "Dairy products",
      "parent": null,
      "is_active": true
    }
  ]
}
```

---

## 🛒 Cart Management API

### 1. Create a New Cart (DRAFT Sale)
**Endpoint:** `POST /sales/api/sales/`

**Request:**
```json
{
  "storefront": "uuid",  // Required: Which store/POS terminal
  "customer": "uuid",     // Optional: For credit sales or tracking
  "type": "RETAIL",       // RETAIL or WHOLESALE
  "payment_type": "CASH"  // CASH, CARD, MOBILE, CREDIT, MIXED
}
```

**Response:**
```json
{
  "id": "uuid",
  "business": "uuid",
  "storefront": "uuid",
  "storefront_name": "Main Store",
  "user": "uuid",
  "user_name": "John Cashier",
  "customer": null,
  "customer_name": null,
  "receipt_number": null,  // Only set when completed
  "type": "RETAIL",
  "status": "DRAFT",  // Cart is in draft mode
  "subtotal": 0.00,
  "discount_amount": 0.00,
  "tax_amount": 0.00,
  "total_amount": 0.00,
  "amount_paid": 0.00,
  "amount_due": 0.00,
  "payment_type": "CASH",
  "manager_override": false,
  "notes": null,
  "cart_session_id": null,
  "created_at": "2025-10-03T22:50:00Z",
  "updated_at": "2025-10-03T22:50:00Z",
  "completed_at": null,
  "sale_items": []
}
```

### 2. Add Item to Cart
**Endpoint:** `POST /sales/api/sales/{sale_id}/add_item/`

**Request:**
```json
{
  "product": "uuid",
  "stock_product": "uuid",  // Specific stock/batch to sell from
  "quantity": 2.00,
  "unit_price": 2.50,       // Can override price
  "discount_percentage": 10.00  // Optional: item-level discount
}
```

**Response:**
```json
{
  "id": "uuid",  // Sale ID
  "sale_items": [
    {
      "id": "uuid",
      "product": "uuid",
      "product_name": "Fresh Milk 1L",
      "product_sku": "MILK-001",
      "stock_product": "uuid",
      "quantity": 2.00,
      "unit_price": 2.50,
      "discount_percentage": 10.00,
      "discount_amount": 0.50,  // Calculated
      "total_price": 4.50,       // (2.50 * 2) - 0.50
      "profit_margin": 2.00,     // Calculated from purchase price
      "product_snapshot": {
        "name": "Fresh Milk 1L",
        "sku": "MILK-001",
        "purchase_price": 1.50
      }
    }
  ],
  "subtotal": 4.50,
  "total_amount": 4.50,
  "amount_due": 4.50
}
```

**Note:** Creating a reservation automatically reserves stock for 30 minutes.

### 3. Update Item Quantity
**Endpoint:** `PATCH /sales/api/sale-items/{item_id}/`

**Request:**
```json
{
  "quantity": 3.00
}
```

### 4. Remove Item from Cart
**Endpoint:** `DELETE /sales/api/sale-items/{item_id}/`

### 5. Apply Sale-Level Discount
**Endpoint:** `PATCH /sales/api/sales/{sale_id}/`

**Request:**
```json
{
  "discount_amount": 5.00
}
```

### 6. Get Current Cart
**Endpoint:** `GET /sales/api/sales/{sale_id}/`

Returns full sale object with all items.

### 7. List Active Carts (DRAFT sales)
**Endpoint:** `GET /sales/api/sales/?status=DRAFT`

---

## 👥 Customer Management API

### 1. Search Customers
**Endpoint:** `GET /sales/api/customers/`

**Query Parameters:**
- `search` - Search by name, phone, email
- `customer_type` - RETAIL or WHOLESALE
- `is_active` - true/false
- `credit_blocked` - true/false

**Example:**
```http
GET /sales/api/customers/?search=john&is_active=true
```

**Response:**
```json
{
  "count": 5,
  "results": [
    {
      "id": "uuid",
      "business": "uuid",
      "name": "John Smith",
      "email": "john@example.com",
      "phone": "+256700000000",
      "address": "123 Main St",
      "customer_type": "RETAIL",
      "credit_limit": 1000.00,
      "outstanding_balance": 250.00,
      "available_credit": 750.00,
      "credit_terms_days": 30,
      "credit_blocked": false,
      "contact_person": "Jane Smith",
      "is_active": true,
      "created_at": "2025-09-01T10:00:00Z"
    }
  ]
}
```

### 2. Create New Customer
**Endpoint:** `POST /sales/api/customers/`

**Request:**
```json
{
  "name": "John Smith",
  "email": "john@example.com",
  "phone": "+256700000000",
  "address": "123 Main St",
  "customer_type": "RETAIL",
  "credit_limit": 1000.00,
  "credit_terms_days": 30,
  "contact_person": "Jane Smith"
}
```

### 3. Get Customer Credit Status
**Endpoint:** `GET /sales/api/customers/{customer_id}/credit_status/`

**Response:**
```json
{
  "customer": {
    "id": "uuid",
    "name": "John Smith"
  },
  "credit_limit": 1000.00,
  "outstanding_balance": 250.00,
  "available_credit": 750.00,
  "credit_blocked": false,
  "overdue_balance": 50.00,
  "can_purchase": true,
  "message": "Customer has available credit"
}
```

### 4. Get Customer Purchase History
**Endpoint:** `GET /sales/api/sales/?customer={customer_id}&status=COMPLETED`

---

## 💳 Complete Sale (Checkout)

### Endpoint: `POST /sales/api/sales/{sale_id}/complete/`

**Request:**
```json
{
  "payment_type": "CASH",        // CASH, CARD, MOBILE, CREDIT, MIXED
  "amount_paid": 50.00,          // Amount tendered
  "discount_amount": 0.00,       // Optional final discount
  "tax_amount": 0.00,            // Optional tax
  "notes": "Customer paid cash"  // Optional notes
}
```

**Response:**
```json
{
  "id": "uuid",
  "receipt_number": "storefront-uuid-20251003-0001",  // Generated!
  "status": "COMPLETED",  // or PENDING, PARTIAL
  "total_amount": 45.00,
  "amount_paid": 50.00,
  "amount_due": 0.00,
  "change": 5.00,  // Included in response
  "completed_at": "2025-10-03T23:00:00Z",
  "sale_items": [...],
  "message": "Sale completed successfully"
}
```

**Status Logic:**
- `COMPLETED` - Fully paid (amount_due = 0)
- `PARTIAL` - Partially paid (amount_paid > 0, amount_due > 0)
- `PENDING` - Awaiting payment (amount_paid = 0)

**What Happens:**
1. ✅ Receipt number generated
2. ✅ Stock quantities committed (deducted)
3. ✅ Reservations released
4. ✅ Customer credit updated (if credit sale)
5. ✅ Audit log created

---

## 📜 Sales History API

### 1. List Sales
**Endpoint:** `GET /sales/api/sales/`

**Query Parameters:**
- `status` - DRAFT, PENDING, COMPLETED, PARTIAL, REFUNDED, CANCELLED
- `customer` - Filter by customer UUID
- `storefront` - Filter by storefront UUID
- `payment_type` - CASH, CARD, MOBILE, CREDIT, MIXED
- `created_at__gte` - From date (ISO 8601: 2025-10-01T00:00:00Z)
- `created_at__lte` - To date
- `page`, `page_size` - Pagination

**Examples:**

```http
# Today's completed sales
GET /sales/api/sales/?status=COMPLETED&created_at__gte=2025-10-03T00:00:00Z
```

```http
# Customer's purchase history
GET /sales/api/sales/?customer=<uuid>&status=COMPLETED&ordering=-created_at
```

### 2. Get Sale Details
**Endpoint:** `GET /sales/api/sales/{sale_id}/`

Returns complete sale with all line items.

### 3. Get Receipt Data
Same as sale details. Frontend can format the receipt for printing.

---

## 🔄 Complete Workflow Examples

### Workflow 1: Quick Cash Sale

```javascript
// 1. Create cart
const cart = await fetch('/sales/api/sales/', {
  method: 'POST',
  headers: {
    'Authorization': 'Token xxx',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    storefront: STOREFRONT_ID,
    type: 'RETAIL',
    payment_type: 'CASH'
  })
}).then(r => r.json());

// 2. Add items
await fetch(`/sales/api/sales/${cart.id}/add_item/`, {
  method: 'POST',
  headers: {
    'Authorization': 'Token xxx',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    product: PRODUCT_ID,
    stock_product: STOCK_PRODUCT_ID,
    quantity: 2,
    unit_price: 2.50
  })
}).then(r => r.json());

// 3. Complete sale
const completedSale = await fetch(`/sales/api/sales/${cart.id}/complete/`, {
  method: 'POST',
  headers: {
    'Authorization': 'Token xxx',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    payment_type: 'CASH',
    amount_paid: 10.00
  })
}).then(r => r.json());

console.log('Receipt:', completedSale.receipt_number);
```

### Workflow 2: Credit Sale with Customer

```javascript
// 1. Search customer
const customers = await fetch('/sales/api/customers/?search=john')
  .then(r => r.json());

// 2. Check credit status
const creditStatus = await fetch(`/sales/api/customers/${customers.results[0].id}/credit_status/`)
  .then(r => r.json());

if (!creditStatus.can_purchase) {
  alert(creditStatus.message);
  return;
}

// 3. Create cart with customer
const cart = await fetch('/sales/api/sales/', {
  method: 'POST',
  body: JSON.stringify({
    storefront: STOREFRONT_ID,
    customer: customers.results[0].id,
    type: 'RETAIL',
    payment_type: 'CREDIT'
  })
}).then(r => r.json());

// 4. Add items...
// 5. Complete sale
```

### Workflow 3: Barcode Scanning

```javascript
function handleBarcodeScan(barcode) {
  // Search product by barcode
  fetch(`/inventory/api/products/?search=${barcode}`)
    .then(r => r.json())
    .then(data => {
      if (data.results.length === 0) {
        alert('Product not found');
        return;
      }
      
      const product = data.results[0];
      
      // Get available stock
      fetch(`/inventory/api/stock-products/?product=${product.id}&has_quantity=true`)
        .then(r => r.json())
        .then(stockData => {
          if (stockData.results.length === 0) {
            alert('Product out of stock');
            return;
          }
          
          const stockProduct = stockData.results[0];
          
          // Add to cart
          addItemToCart(product.id, stockProduct.id, 1, stockProduct.retail_price);
        });
    });
}
```

---

## ⚠️ Error Handling

### Common Error Responses

**400 Bad Request** - Validation error
```json
{
  "field_name": ["Error message"],
  "quantity": ["Insufficient stock. Available: 5, Requested: 10"]
}
```

**401 Unauthorized** - Missing/invalid token
```json
{
  "detail": "Authentication credentials were not provided."
}
```

**403 Forbidden** - Permission denied
```json
{
  "detail": "You do not have permission to perform this action."
}
```

**404 Not Found**
```json
{
  "detail": "Not found."
}
```

**500 Internal Server Error**
```json
{
  "detail": "Internal server error"
}
```

### Recommended Error Handling

```javascript
async function apiCall(url, options) {
  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        'Authorization': `Token ${getToken()}`,
        'Content-Type': 'application/json',
        ...options.headers
      }
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(JSON.stringify(error));
    }
    
    return await response.json();
  } catch (error) {
    console.error('API Error:', error);
    // Show user-friendly message
    showErrorToast('An error occurred. Please try again.');
    throw error;
  }
}
```

---

## 🚀 Performance Optimization

### 1. Debounce Search
```javascript
const debouncedSearch = debounce((query) => {
  fetch(`/inventory/api/products/?search=${query}`)
    .then(r => r.json())
    .then(data => updateProductList(data.results));
}, 300);
```

### 2. Cache Product Data
```javascript
const productCache = new Map();

async function getProduct(id) {
  if (productCache.has(id)) {
    return productCache.get(id);
  }
  
  const product = await fetch(`/inventory/api/products/${id}/`)
    .then(r => r.json());
  
  productCache.set(id, product);
  return product;
}
```

### 3. Pagination Strategy
- Load first page immediately
- Implement infinite scroll or "Load More" button
- Don't fetch all pages at once

---

## 📊 Data Structures Reference

### Product Object
```typescript
interface Product {
  id: string;
  name: string;
  sku: string;
  description: string;
  category: string;
  category_name: string;
  barcode: string;
  unit: string;
  reorder_level: number;
  is_active: boolean;
  image: string | null;
  created_at: string;
  updated_at: string;
}
```

### StockProduct Object
```typescript
interface StockProduct {
  id: string;
  product: string;
  product_name: string;
  product_sku: string;
  stock: string;
  stock_name: string;
  supplier: string;
  supplier_name: string;
  quantity: number;
  purchase_price: number;
  wholesale_price: number;
  retail_price: number;
  available_quantity: number;  // After reservations
  created_at: string;
}
```

### Sale Object
```typescript
interface Sale {
  id: string;
  business: string;
  storefront: string;
  storefront_name: string;
  user: string;
  user_name: string;
  customer: string | null;
  customer_name: string | null;
  receipt_number: string | null;
  type: 'RETAIL' | 'WHOLESALE';
  status: 'DRAFT' | 'PENDING' | 'COMPLETED' | 'PARTIAL' | 'REFUNDED' | 'CANCELLED';
  subtotal: number;
  discount_amount: number;
  tax_amount: number;
  total_amount: number;
  amount_paid: number;
  amount_due: number;
  payment_type: 'CASH' | 'CARD' | 'MOBILE' | 'CREDIT' | 'MIXED';
  manager_override: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  sale_items: SaleItem[];
}
```

### SaleItem Object
```typescript
interface SaleItem {
  id: string;
  product: string;
  product_name: string;
  product_sku: string;
  stock_product: string;
  quantity: number;
  unit_price: number;
  discount_percentage: number;
  discount_amount: number;
  total_price: number;
  profit_margin: number;
  product_snapshot: {
    name: string;
    sku: string;
    purchase_price: number;
  };
}
```

### Customer Object
```typescript
interface Customer {
  id: string;
  business: string;
  name: string;
  email: string | null;
  phone: string;
  address: string | null;
  customer_type: 'RETAIL' | 'WHOLESALE';
  credit_limit: number;
  outstanding_balance: number;
  available_credit: number;
  credit_terms_days: number;
  credit_blocked: boolean;
  contact_person: string | null;
  is_active: boolean;
  created_at: string;
}
```

---

## 🔮 Future Enhancements (Not Yet Implemented)

### WebSocket for Real-time Updates
```javascript
// Future: Real-time stock updates
const ws = new WebSocket('ws://localhost:8000/ws/stock/');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  updateStockLevel(data.product_id, data.new_quantity);
};
```

### Payment Gateway Integration
- Stripe payment endpoint
- Mobile Money API integration
- Payment webhooks

---

## ✅ API Checklist for Frontend Developer

### Phase 1: Product Search ✅ READY
- [x] `GET /inventory/api/products/` - Search & list products
- [x] `GET /inventory/api/stock-products/` - Get stock levels
- [x] `GET /inventory/api/categories/` - Category filter

### Phase 2: Cart Management ✅ READY
- [x] `POST /sales/api/sales/` - Create cart
- [x] `POST /sales/api/sales/{id}/add_item/` - Add to cart
- [x] `PATCH /sales/api/sale-items/{id}/` - Update quantity
- [x] `DELETE /sales/api/sale-items/{id}/` - Remove item
- [x] `GET /sales/api/sales/{id}/` - Get cart

### Phase 3: Checkout ✅ READY
- [x] `POST /sales/api/sales/{id}/complete/` - Complete sale

### Phase 4: Customer Management ✅ READY
- [x] `GET /sales/api/customers/` - Search customers
- [x] `POST /sales/api/customers/` - Create customer
- [x] `GET /sales/api/customers/{id}/credit_status/` - Credit check

### Phase 5: Sales History ✅ READY
- [x] `GET /sales/api/sales/?status=COMPLETED` - List sales
- [x] `GET /sales/api/sales/{id}/` - Receipt data

---

## 🎯 Recommendations for Frontend

### What to Build First (Priority Order):

1. **Product Search Component** 🔴
   - SearchBar with debounced API calls
   - ProductCard showing stock levels
   - Quick add to cart

2. **Cart Display & Management** 🔴
   - Line items list
   - Quantity editing
   - Remove items
   - Real-time total calculation

3. **Checkout Flow** 🔴
   - Payment method selection
   - Amount input
   - Complete sale button
   - Receipt display

4. **Customer Management** 🟡
   - Customer search
   - Quick create customer modal
   - Credit status display

5. **Sales History** 🟢
   - Sales list with filters
   - Receipt reprint

### Missing Backend Features:

1. **Barcode Search** - Current search works but not optimized
   - Should I add `GET /inventory/api/products/by_barcode/{barcode}/`?

2. **Receipt Printing** - Just formatting needed on frontend

3. **Payment Gateway** - Future integration needed

---

## 📞 Support

If you need:
- Additional endpoints
- Different response format
- Specific validations
- Performance optimization

Let me know and I'll update the backend immediately! 🚀
