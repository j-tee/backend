# Frontend Fix: Sugar 1kg Showing "Out of Stock"

**Issue**: Sugar 1kg shows "Out of Stock" on sales page  
**Reality**: 917 units available in Cow Lane Store  
**Cause**: Frontend querying Adenta Store only, not seeing Cow Lane inventory  
**Fix**: Update to use multi-storefront endpoint

---

## 🚨 The Problem

Your sales page is currently calling:
```javascript
// ❌ CURRENT (WRONG)
GET /inventory/api/storefronts/cc45f197-b169-4be2-a769-99138fd02d5b/sale-catalog/
// This is Adenta Store's ID - Sugar is NOT in Adenta Store!
```

**Result**: 
- Adenta Store has NO Sugar → Shows "Out of Stock" ❌
- Cow Lane Store has 917 units → Not visible ❌

---

## ✅ The Solution

### Option 1: Quick Fix (Use Multi-Storefront Endpoint)

**Recommended**: Replace the API call with the multi-storefront endpoint:

```javascript
// ✅ NEW (CORRECT)
GET /inventory/api/storefronts/multi-storefront-catalog/

// Returns products from ALL accessible storefronts
// Business owner will see: Adenta + Cow Lane + Main Store + Test Store
```

**In your SalesPage.tsx file**, find the API call (likely in `fetchProducts` or similar function):

```typescript
// FIND THIS:
const fetchProducts = async () => {
  const response = await fetch(
    `/inventory/api/storefronts/${storefrontId}/sale-catalog/`,
    { headers: { 'Authorization': `Token ${token}` } }
  );
  const data = await response.json();
  setProducts(data.products);
};

// REPLACE WITH THIS:
const fetchProducts = async () => {
  const response = await fetch(
    '/inventory/api/storefronts/multi-storefront-catalog/',
    { headers: { 'Authorization': `Token ${token}` } }
  );
  const data = await response.json();
  setProducts(data.products);
  setStorefronts(data.storefronts); // Also get accessible storefronts
};
```

### Option 2: Alternative Quick Fix (Add Cow Lane to Query)

If you must keep the single-storefront approach temporarily, query BOTH storefronts:

```typescript
const fetchProducts = async () => {
  // Get products from both Adenta and Cow Lane
  const [adentaData, cowLaneData] = await Promise.all([
    fetch('/inventory/api/storefronts/cc45f197-b169-4be2-a769-99138fd02d5b/sale-catalog/', 
      { headers: { 'Authorization': `Token ${token}` } }
    ).then(r => r.json()),
    fetch('/inventory/api/storefronts/ceb5f89e-2fad-4ca1-bc8b-012c6431c073/sale-catalog/',
      { headers: { 'Authorization': `Token ${token}` } }
    ).then(r => r.json())
  ]);
  
  // Combine products
  const allProducts = [
    ...adentaData.products.map(p => ({...p, storefront_name: 'Adenta Store'})),
    ...cowLaneData.products.map(p => ({...p, storefront_name: 'Cow Lane Store'}))
  ];
  
  setProducts(allProducts);
};
```

---

## 🧪 Test the Fix

### Test 1: Search for Sugar
```
1. Open sales page
2. Search for "sugar" or "FOOD-0003"
3. Expected result: ✅ Shows "Sugar 1kg" with 917 units
4. Should NOT show "Out of Stock"
```

### Test 2: Check Location Info
```
If using multi-storefront endpoint:
- Product should show: "Location: Cow Lane Store"
- Quantity: 917 units
- Price: GH₵ 3.12
```

### Test 3: Multi-Location Product
```
1. Search for "Coca Cola" or "BEV-0001"
2. Should show: "Available at 2 locations"
   - Adenta Store: 1921 units
   - Cow Lane Store: 100 units
3. Total: 2021 units
```

---

## 📊 API Response Comparison

### Old Endpoint (Adenta Store Only)
```bash
GET /inventory/api/storefronts/cc45f197-b169-4be2-a769-99138fd02d5b/sale-catalog/
```

**Response**:
```json
{
  "storefront": "cc45f197-b169-4be2-a769-99138fd02d5b",
  "products": [
    // 10 products from Adenta Store only
    // ❌ Sugar NOT in this list (not in Adenta)
  ]
}
```

### New Endpoint (All Storefronts)
```bash
GET /inventory/api/storefronts/multi-storefront-catalog/
```

**Response**:
```json
{
  "storefronts": [
    {"id": "...", "name": "Adenta Store"},
    {"id": "...", "name": "Cow Lane Store"}
  ],
  "products": [
    {
      "product_name": "Sugar 1kg",
      "sku": "FOOD-0003",
      "total_available": 917,
      "retail_price": "3.12",
      "locations": [
        {
          "storefront_id": "ceb5f89e-2fad-4ca1-bc8b-012c6431c073",
          "storefront_name": "Cow Lane Store",
          "available_quantity": 917
        }
      ]
    }
    // ... 19 more products from all storefronts
  ],
  "total_products": 20,
  "total_storefronts": 2
}
```

---

## 🎯 Expected Behavior After Fix

### For Sugar 1kg:
- ✅ Shows in search results
- ✅ Shows "917 units available"
- ✅ Shows "Cow Lane Store" as location
- ✅ Price: GH₵ 3.12
- ✅ Can be added to cart

### For Coca Cola (multi-location):
- ✅ Shows total: 2021 units
- ✅ Shows 2 locations:
  - Adenta Store: 1921 units
  - Cow Lane Store: 100 units
- ✅ User can select which location to sell from

---

## 🔍 Where to Find the Code

### Likely Files to Update:

1. **`src/features/dashboard/pages/SalesPage.tsx`** or similar
   - Look for `fetchProducts`, `loadInventory`, or similar function
   - Update the API endpoint URL

2. **`src/services/inventoryService.ts`** or similar
   - Look for `getSaleCatalog` or similar method
   - Update to call multi-storefront endpoint

3. **Example location**:
   ```typescript
   // In src/services/inventoryService.ts
   export const getSaleCatalog = async (token: string) => {
     // OLD:
     // return api.get(`/storefronts/${storefrontId}/sale-catalog/`);
     
     // NEW:
     return api.get('/storefronts/multi-storefront-catalog/');
   };
   ```

---

## 🐛 Debugging Steps

If Sugar still doesn't show after the fix:

### Step 1: Check API Response
Open browser DevTools → Network tab:
```
1. Search for "sugar"
2. Look for request to /multi-storefront-catalog/
3. Check response - should include Sugar 1kg
4. If not in response → Backend issue (unlikely)
5. If in response but not showing → Frontend filtering issue
```

### Step 2: Check Console
```javascript
// Add this temporarily to debug
fetch('/inventory/api/storefronts/multi-storefront-catalog/', {
  headers: { 'Authorization': `Token ${token}` }
})
.then(r => r.json())
.then(data => {
  console.log('Total products:', data.total_products);
  console.log('Storefronts:', data.storefronts.map(s => s.name));
  
  const sugar = data.products.find(p => p.sku === 'FOOD-0003');
  console.log('Sugar 1kg:', sugar);
  // Should log: {product_name: "Sugar 1kg", total_available: 917, ...}
});
```

### Step 3: Check Filtering
```javascript
// Make sure you're not filtering out Cow Lane products
const filteredProducts = products.filter(p => {
  // ❌ DON'T DO THIS:
  // return p.storefront_id === adentaStoreId;
  
  // ✅ DO THIS (or no filtering at all):
  return p.total_available > 0;
});
```

---

## 📞 Quick Reference

### Storefront IDs
```
Adenta Store:   cc45f197-b169-4be2-a769-99138fd02d5b
Cow Lane Store: ceb5f89e-2fad-4ca1-bc8b-012c6431c073
```

### Sugar 1kg Details
```
Product Name: Sugar 1kg
SKU: FOOD-0003
Product ID: 55b900ea-a046-4148-99e6-43cf7ed0e406
Location: Cow Lane Store ONLY
Quantity: 917 units
Price: GH₵ 3.12
```

### API Endpoints
```
❌ OLD: /inventory/api/storefronts/{id}/sale-catalog/
✅ NEW: /inventory/api/storefronts/multi-storefront-catalog/
```

---

## ✅ Verification Checklist

After making the fix:

- [ ] Sugar 1kg appears in search results
- [ ] Shows 917 units available
- [ ] Shows "Cow Lane Store" location
- [ ] NOT showing "Out of Stock"
- [ ] Can add to cart successfully
- [ ] Coca Cola shows 2 locations (Adenta + Cow Lane)
- [ ] All 20 products appear (not just 10 from Adenta)

---

## 🎉 Summary

**The Issue**: Frontend is only looking at Adenta Store, where Sugar doesn't exist.

**The Fix**: Use `/multi-storefront-catalog/` endpoint to see ALL storefronts.

**The Result**: Sugar (and all other products) will show with their correct quantities and locations.

**Time to Fix**: 5-10 minutes (just change one API endpoint URL)

---

**Last Updated**: October 11, 2025  
**Status**: Backend working ✅ - Frontend fix required  
**Priority**: URGENT - Blocking sales
