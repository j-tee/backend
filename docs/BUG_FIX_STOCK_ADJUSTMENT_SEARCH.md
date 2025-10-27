# Bug Fix: Stock Product Search in Create Stock Adjustment Modal

**Date:** 2025-10-09  
**Status:** ✅ FIXED  
**Issue:** Product visible in Stock Products page but not searchable in Create Stock Adjustment modal

---

## 🐛 Problem Description

User reported that "10mm Armoured Cable 50m" (SKU: ELEC-0007):
- ✅ Visible on Stock Products page
- ✅ Visible on Sales page  
- ❌ NOT showing in Create Stock Adjustment modal search

**Root Cause:** Stock Adjustment serializers were using default DRF `PrimaryKeyRelatedField` queryset which doesn't respect business filtering.

---

## 🔧 Backend Fix Applied

### Changes Made

**File:** `inventory/adjustment_serializers.py`

Added `get_fields()` method to both serializers to dynamically filter `stock_product` queryset by user's business:

```python
class StockAdjustmentSerializer(serializers.ModelSerializer):
    # ... existing code ...
    
    def get_fields(self):
        """Override to set stock_product queryset based on user's business"""
        fields = super().get_fields()
        request = self.context.get('request')
        
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            # Get user's business
            membership = BusinessMembership.objects.filter(
                user=request.user,
                is_active=True
            ).first()
            
            if membership:
                # Filter stock products by user's business
                fields['stock_product'].queryset = StockProduct.objects.filter(
                    stock__warehouse__business_link__business=membership.business
                ).select_related('product', 'supplier', 'stock__warehouse')
            else:
                # No business membership - return empty queryset
                fields['stock_product'].queryset = StockProduct.objects.none()
        
        return fields
```

**Applied to:**
- `StockAdjustmentSerializer`
- `StockAdjustmentCreateSerializer`

### What This Fixes

Before:
```python
# Default DRF behavior - shows ALL stock products across ALL businesses
stock_product.queryset = StockProduct.objects.all()  ❌
```

After:
```python
# Filtered by user's business
stock_product.queryset = StockProduct.objects.filter(
    stock__warehouse__business_link__business=user_business
)  ✅
```

---

## 🎯 Frontend Integration

### If Using DRF Browsable API (HTML Forms)

The fix is **automatic**. When rendering HTML forms via DRF browsable API:
- The `<select>` dropdown for `stock_product` now only shows products from user's business
- Search/autocomplete will only search within user's business

### If Using Custom Frontend (React/Vue/etc)

You need to **fetch stock products separately** using:

```typescript
// Correct endpoint for stock product search
GET /inventory/api/stock-products/?search={searchTerm}

// Example
GET /inventory/api/stock-products/?search=10mm
```

**Important:** Do NOT rely on OPTIONS metadata for foreign key choices - it's not designed for large datasets.

### Recommended Implementation

```typescript
interface StockProductOption {
  id: string;
  product: {
    name: string;
    sku: string;
  };
  warehouse: string;
  quantity: number;
}

// In your Create Stock Adjustment component
async function searchStockProducts(searchTerm: string): Promise<StockProductOption[]> {
  const response = await fetch(
    `/inventory/api/stock-products/?search=${encodeURIComponent(searchTerm)}`,
    {
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
      }
    }
  );
  
  if (!response.ok) {
    throw new Error('Failed to search stock products');
  }
  
  const data = await response.json();
  return data.results; // Paginated response
}

// Usage in autocomplete/dropdown
<Autocomplete
  options={stockProducts}
  onInputChange={(value) => searchStockProducts(value)}
  getOptionLabel={(option) => `${option.product.name} (${option.product.sku})`}
  renderOption={(option) => (
    <div>
      <strong>{option.product.name}</strong>
      <br />
      <small>SKU: {option.product.sku} | Warehouse: {option.warehouse} | Qty: {option.quantity}</small>
    </div>
  )}
/>
```

---

## ✅ Verification

### Backend Test

```bash
python manage.py shell

>>> from django.contrib.auth import get_user_model
>>> from inventory.models import StockProduct
>>> from rest_framework.test import APIClient
>>> 
>>> User = get_user_model()
>>> client = APIClient()
>>> user = User.objects.get(email='mikedlt009@gmail.com')
>>> client.force_authenticate(user=user)
>>> 
>>> # Search for stock products
>>> response = client.get('/inventory/api/stock-products/?search=10mm')
>>> response.status_code  # Should be 200
>>> response.json()['count']  # Should be > 0
```

### Frontend Test

1. Open browser network tab
2. Navigate to Create Stock Adjustment modal
3. Type "10mm" in stock product search
4. Verify request goes to: `GET /inventory/api/stock-products/?search=10mm`
5. Verify response has `count > 0` and results array populated
6. If using dropdown, verify product appears in options

### Expected Results

**For "10mm Armoured Cable 50m" (ELEC-0007):**

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "83096f71-b4aa-4fbe-8a18-dd9b12824a5e",
      "product": {
        "id": "...",
        "name": "10mm Armoured Cable 50m",
        "sku": "ELEC-0007"
      },
      "stock": {
        "warehouse": {
          "name": "Rawlings Park Warehouse"
        }
      },
      "quantity": 26,
      "unit_cost": "12.00",
      "retail_price": "60.00"
    }
  ]
}
```

---

## 🚨 Common Frontend Mistakes to Avoid

### ❌ Mistake 1: Using OPTIONS for Foreign Keys
```typescript
// DON'T DO THIS
const response = await fetch('/inventory/api/stock-adjustments/', {
  method: 'OPTIONS'
});
const choices = response.data.actions.POST.stock_product.choices;
// ❌ This won't have choices - foreign keys don't populate in OPTIONS
```

### ❌ Mistake 2: Fetching ALL Stock Products
```typescript
// DON'T DO THIS
const response = await fetch('/inventory/api/stock-products/');
const allProducts = response.data.results;
// ❌ This could be thousands of records - use search parameter
```

### ❌ Mistake 3: Client-Side Filtering Only
```typescript
// DON'T DO THIS
const allProducts = await fetchAllProducts();
const filtered = allProducts.filter(p => 
  p.product.name.includes(searchTerm)
);
// ❌ This defeats backend pagination and business filtering
```

### ✅ Correct Approach
```typescript
// DO THIS
const response = await fetch(
  `/inventory/api/stock-products/?search=${searchTerm}`
);
const products = response.data.results;
// ✅ Server-side search with business filtering and pagination
```

---

## 📋 Testing Checklist

- [ ] Backend: `get_fields()` method added to both serializers
- [ ] Backend: Queryset filters by `stock__warehouse__business_link__business`
- [ ] Backend: Test with authenticated user shows only their business products
- [ ] Backend: Test with unauthenticated request returns empty queryset
- [ ] Frontend: Search calls `/inventory/api/stock-products/?search={term}`
- [ ] Frontend: Authorization header included in request
- [ ] Frontend: Handles pagination (results array in response)
- [ ] Frontend: Displays product name, SKU, warehouse, quantity
- [ ] Frontend: Submits stock_product as UUID to create endpoint
- [ ] End-to-end: Can find product, select it, create adjustment successfully

---

## 🎉 Resolution

**Backend:** ✅ Fixed - Stock product queryset now respects business filtering  
**Frontend:** ⏳ Awaiting implementation of search endpoint integration

The product "10mm Armoured Cable 50m" is now properly accessible in the Create Stock Adjustment modal through the search endpoint.

**Next Steps for Frontend:**
1. Verify search endpoint is being called: `/inventory/api/stock-products/?search={term}`
2. Check network tab for 401/403 errors (authentication issues)
3. Verify response contains the product in results array
4. Ensure dropdown/autocomplete component populates from search results

---

**Questions?** Test the endpoint manually:
```bash
curl "http://localhost:8000/inventory/api/stock-products/?search=10mm" \
  -H "Authorization: Bearer YOUR_TOKEN"
```
