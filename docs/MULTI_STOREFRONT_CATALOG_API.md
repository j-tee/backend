# Multi-Storefront Catalog API - Documentation

**Date**: October 11, 2025  
**Endpoint**: `/inventory/api/storefronts/multi-storefront-catalog/`  
**Purpose**: Return products from ALL storefronts accessible to the current user  
**Status**: ✅ IMPLEMENTED AND TESTED

---

## 🎯 Overview

This endpoint solves the requirement that **business owners should see products from ALL their storefronts** on the sales page, while **employees should only see products from storefronts they're assigned to**.

### Key Features

1. **Role-Based Access**:
   - Business owners/managers: See products from ALL storefronts in their business
   - Employees: See products only from storefronts they're assigned to

2. **Multi-Location Tracking**:
   - Products available in multiple storefronts show all locations
   - Each location displays its own quantity

3. **Combined Availability**:
   - Shows total available quantity across all locations
   - Useful for business owners to see company-wide inventory

---

## 📡 API Specification

### Request

```http
GET /inventory/api/storefronts/multi-storefront-catalog/
Authorization: Token <auth-token>
```

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `include_zero` | boolean | false | Include products with zero quantity |

**Example**:
```http
GET /inventory/api/storefronts/multi-storefront-catalog/?include_zero=true
```

---

### Response

#### Success (200 OK)

```json
{
  "storefronts": [
    {
      "id": "cc45f197-b169-4be2-a769-99138fd02d5b",
      "name": "Adenta Store",
      "business_id": "2050bdf4-88b7-4ffa-a26a-b5bb34e9b9fb",
      "business_name": "DataLogique Systems"
    },
    {
      "id": "ceb5f89e-2fad-4ca1-bc8b-012c6431c073",
      "name": "Cow Lane Store",
      "business_id": "2050bdf4-88b7-4ffa-a26a-b5bb34e9b9fb",
      "business_name": "DataLogique Systems"
    }
  ],
  "products": [
    {
      "product_id": "55b900ea-a046-4148-99e6-43cf7ed0e406",
      "product_name": "Sugar 1kg",
      "sku": "FOOD-0003",
      "category_name": "Food",
      "retail_price": "3.12",
      "wholesale_price": "2.65",
      "total_available": 917,
      "locations": [
        {
          "storefront_id": "ceb5f89e-2fad-4ca1-bc8b-012c6431c073",
          "storefront_name": "Cow Lane Store",
          "available_quantity": 917
        }
      ],
      "stock_product_ids": ["...", "..."],
      "last_stocked_at": "2025-10-10T17:25:04.384609Z"
    },
    {
      "product_id": "...",
      "product_name": "Coca Cola 500ml",
      "sku": "BEV-0001",
      "category_name": "Beverages",
      "retail_price": "0.77",
      "wholesale_price": "0.65",
      "total_available": 2021,
      "locations": [
        {
          "storefront_id": "cc45f197-b169-4be2-a769-99138fd02d5b",
          "storefront_name": "Adenta Store",
          "available_quantity": 1921
        },
        {
          "storefront_id": "ceb5f89e-2fad-4ca1-bc8b-012c6431c073",
          "storefront_name": "Cow Lane Store",
          "available_quantity": 100
        }
      ],
      "stock_product_ids": ["...", "..."],
      "last_stocked_at": "2025-10-10T17:24:28.947829Z"
    }
  ],
  "total_products": 20,
  "total_storefronts": 2
}
```

#### No Access (200 OK with empty results)

```json
{
  "storefronts": [],
  "products": [],
  "message": "No accessible storefronts found for this user"
}
```

---

## 🔑 Response Fields

### Root Level

| Field | Type | Description |
|-------|------|-------------|
| `storefronts` | array | List of storefronts the user has access to |
| `products` | array | Combined product catalog from all accessible storefronts |
| `total_products` | integer | Total number of unique products |
| `total_storefronts` | integer | Total number of accessible storefronts |

### Storefront Object

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Storefront ID |
| `name` | string | Storefront name |
| `business_id` | UUID | Business ID |
| `business_name` | string | Business name |

### Product Object

| Field | Type | Description |
|-------|------|-------------|
| `product_id` | UUID | Product ID |
| `product_name` | string | Product name |
| `sku` | string | Product SKU |
| `category_name` | string | Category name (nullable) |
| `retail_price` | decimal | Retail price per unit |
| `wholesale_price` | decimal | Wholesale price (nullable) |
| `total_available` | integer | Total quantity across all locations |
| `locations` | array | List of storefronts where this product is available |
| `stock_product_ids` | array | Stock batch IDs |
| `last_stocked_at` | datetime | Last time product was stocked |

### Location Object

| Field | Type | Description |
|-------|------|-------------|
| `storefront_id` | UUID | Storefront ID |
| `storefront_name` | string | Storefront name |
| `available_quantity` | integer | Quantity available at this location |

---

## 🎭 User Roles & Access

### Business Owner / Manager

**Access**: All storefronts in their business(es)

**Example**:
- User owns "DataLogique Systems"
- DataLogique has 2 storefronts: "Adenta Store" and "Cow Lane Store"
- **Result**: Sees products from both storefronts

**Response**:
```json
{
  "storefronts": [
    {"name": "Adenta Store", ...},
    {"name": "Cow Lane Store", ...}
  ],
  "products": [...],  // Products from both stores
  "total_storefronts": 2
}
```

### Employee (Assigned to Specific Storefronts)

**Access**: Only storefronts they're assigned to via `StoreFrontEmployee`

**Example**:
- User is assigned to "Cow Lane Store" only
- **Result**: Sees products only from Cow Lane Store

**Response**:
```json
{
  "storefronts": [
    {"name": "Cow Lane Store", ...}
  ],
  "products": [...],  // Products only from Cow Lane
  "total_storefronts": 1
}
```

### Employee (Not Assigned to Any Storefront)

**Access**: None

**Response**:
```json
{
  "storefronts": [],
  "products": [],
  "message": "No accessible storefronts found for this user"
}
```

---

## 💻 Frontend Integration

### Recommended Implementation

#### 1. Replace Single-Storefront Catalog Call

**OLD (Per-Storefront)**:
```javascript
// ❌ DON'T USE THIS for sales page
GET /inventory/api/storefronts/{storefront_id}/sale-catalog/
```

**NEW (Multi-Storefront)**:
```javascript
// ✅ USE THIS for sales page
GET /inventory/api/storefronts/multi-storefront-catalog/
```

#### 2. Example Frontend Code

```javascript
// Fetch multi-storefront catalog
const fetchSalesInventory = async () => {
  try {
    const response = await fetch(
      '/inventory/api/storefronts/multi-storefront-catalog/',
      {
        headers: {
          'Authorization': `Token ${authToken}`
        }
      }
    );
    
    const data = await response.json();
    
    // Update UI
    setAccessibleStorefronts(data.storefronts);
    setProducts(data.products);
    setTotalProducts(data.total_products);
    
    console.log(`Loaded ${data.total_products} products from ${data.total_storefronts} storefronts`);
    
  } catch (error) {
    console.error('Failed to load inventory:', error);
  }
};
```

#### 3. Product Search with Multi-Location

```javascript
// Search products
const searchProducts = (query) => {
  const results = products.filter(product => 
    product.product_name.toLowerCase().includes(query.toLowerCase()) ||
    product.sku.toLowerCase().includes(query.toLowerCase())
  );
  
  return results;
};

// Display product with location info
const ProductCard = ({ product }) => {
  const multipleLocations = product.locations.length > 1;
  
  return (
    <div className="product-card">
      <h3>{product.product_name}</h3>
      <p>SKU: {product.sku}</p>
      <p>Price: ${product.retail_price}</p>
      <p className="total">Total Available: {product.total_available} units</p>
      
      {multipleLocations && (
        <div className="locations">
          <strong>Available at:</strong>
          {product.locations.map(loc => (
            <div key={loc.storefront_id}>
              📍 {loc.storefront_name}: {loc.available_quantity} units
            </div>
          ))}
        </div>
      )}
      
      {!multipleLocations && (
        <p>Location: {product.locations[0].storefront_name}</p>
      )}
    </div>
  );
};
```

#### 4. Select Storefront for Sale

```javascript
// When creating a sale, let user select which storefront to sell from
const createSale = (product, quantity) => {
  // If product available in multiple locations, ask user to choose
  if (product.locations.length > 1) {
    const storefront = selectStorefrontDialog(product.locations);
    
    // Create sale at selected storefront
    return api.post('/sales/api/sales/', {
      storefront: storefront.storefront_id,
      items: [{
        product: product.product_id,
        quantity: quantity
      }]
    });
  } else {
    // Only one location, use it
    return api.post('/sales/api/sales/', {
      storefront: product.locations[0].storefront_id,
      items: [{
        product: product.product_id,
        quantity: quantity
      }]
    });
  }
};
```

---

## 🧪 Testing

### Test Case 1: Business Owner Sees All Storefronts

**Setup**:
- Login as business owner (e.g., Julius Kudzo Tetteh)
- Business has 2 storefronts: Adenta Store, Cow Lane Store

**Expected**:
```bash
GET /inventory/api/storefronts/multi-storefront-catalog/
```

**Result**:
- `total_storefronts`: 2
- `storefronts`: Contains both "Adenta Store" and "Cow Lane Store"
- `products`: Contains products from both locations
- Products like "Coca Cola" show 2 locations

### Test Case 2: Search for "Sugar 1kg"

**Setup**:
- Sugar 1kg (FOOD-0003) exists in Cow Lane Store with 917 units

**Expected**:
```javascript
const results = searchProducts('sugar');
```

**Result**:
```json
{
  "product_name": "Sugar 1kg",
  "sku": "FOOD-0003",
  "total_available": 917,
  "locations": [
    {
      "storefront_name": "Cow Lane Store",
      "available_quantity": 917
    }
  ]
}
```

### Test Case 3: Product in Multiple Locations

**Setup**:
- Coca Cola exists in Adenta (1921 units) and Cow Lane (100 units)

**Expected**:
```javascript
const cocaCola = products.find(p => p.sku === 'BEV-0001');
```

**Result**:
```json
{
  "product_name": "Coca Cola 500ml",
  "total_available": 2021,
  "locations": [
    {"storefront_name": "Adenta Store", "available_quantity": 1921},
    {"storefront_name": "Cow Lane Store", "available_quantity": 100}
  ]
}
```

---

## 🔄 Migration from Old Endpoint

### Phase 1: Sales Page (Immediate)

Replace single-storefront catalog with multi-storefront catalog:

```diff
- // OLD: Single storefront
- GET /inventory/api/storefronts/{id}/sale-catalog/

+ // NEW: Multi storefront
+ GET /inventory/api/storefronts/multi-storefront-catalog/
```

### Phase 2: POS System (When Ready)

Keep single-storefront endpoint for specific-location sales:

```javascript
// Still valid for POS at a physical location
GET /inventory/api/storefronts/{id}/sale-catalog/
```

### Both Endpoints Coexist

- **Multi-storefront** (`/multi-storefront-catalog/`): For management, reports, overview
- **Single-storefront** (`/{id}/sale-catalog/`): For POS at a physical location

---

## 📊 Performance Considerations

### Query Optimization

The endpoint:
- Uses `select_related()` to minimize database queries
- Aggregates inventory with `Sum()`
- Fetches stock products in a single query per storefront

### Caching Recommendation

For production, consider caching:

```python
from django.core.cache import cache

cache_key = f'multi_catalog_{user.id}'
cached_data = cache.get(cache_key)

if not cached_data:
    # Generate catalog
    cached_data = generate_catalog()
    cache.set(cache_key, cached_data, 300)  # 5 minutes

return cached_data
```

---

## 🐛 Troubleshooting

### Product Not Appearing

**Problem**: Product exists in StoreFrontInventory but doesn't appear in catalog

**Checklist**:
1. ✅ Product has `quantity > 0` in StoreFrontInventory?
2. ✅ Product has StockProduct records in warehouse?
3. ✅ User has access to the storefront?
4. ✅ Storefront belongs to user's business?

**Debug**:
```python
# Check StoreFrontInventory
StoreFrontInventory.objects.filter(
    product__sku='FOOD-0003',
    storefront__name='Cow Lane Store'
)

# Check StockProduct
StockProduct.objects.filter(product__sku='FOOD-0003')

# Check user access
StoreFrontEmployee.objects.filter(user=user, storefront__name='Cow Lane Store')
```

### Empty Catalog

**Problem**: Endpoint returns no products

**Possible Causes**:
1. User not assigned to any storefronts
2. User not member of any business
3. All products have zero quantity
4. No StockProduct records exist

**Solution**:
- Assign user to storefronts via `StoreFrontEmployee`
- Create transfer requests to move stock to storefronts
- Ensure warehouse has StockProduct batches

---

## 📚 Related Documentation

- `STOREFRONT_SEARCH_RESOLUTION.md` - Original issue analysis
- `inventory/views.py` - Implementation code (lines 420-539)
- `inventory/models.py` - StoreFrontEmployee model

---

## ✅ Summary

**Problem Solved**:
- Business owners can now see products from ALL their storefronts
- Employees see products only from assigned storefronts
- Products show which locations they're available at
- Solves "Sugar 1kg not appearing on sales page" issue

**Next Steps**:
1. Update frontend to use `/multi-storefront-catalog/` endpoint
2. Update sales page search to use this endpoint
3. Add storefront selection when product available in multiple locations
4. Test with different user roles (owner, manager, employee)

---

**Last Updated**: October 11, 2025  
**Status**: ✅ Ready for Frontend Integration  
**Endpoint**: `/inventory/api/storefronts/multi-storefront-catalog/`
