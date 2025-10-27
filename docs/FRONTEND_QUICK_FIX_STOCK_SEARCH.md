# 🔧 Quick Fix: Stock Product Search in Create Adjustment Modal

**TL;DR:** Use `/inventory/api/stock-products/?search={term}` endpoint, not OPTIONS metadata.

---

## ❌ Don't Do This

```typescript
// This won't work for foreign keys
const response = await fetch('/inventory/api/stock-adjustments/', {
  method: 'OPTIONS'
});
const choices = response.actions.POST.stock_product.choices; // undefined!
```

## ✅ Do This Instead

```typescript
// Use the search endpoint
const searchStockProducts = async (term: string) => {
  const response = await fetch(
    `/inventory/api/stock-products/?search=${encodeURIComponent(term)}`,
    { headers: { 'Authorization': `Bearer ${token}` } }
  );
  return (await response.json()).results;
};

// In your component
const [searchTerm, setSearchTerm] = useState('');
const [results, setResults] = useState([]);

useEffect(() => {
  const timer = setTimeout(async () => {
    if (searchTerm.length >= 2) {
      const products = await searchStockProducts(searchTerm);
      setResults(products);
    }
  }, 300); // Debounce 300ms
  
  return () => clearTimeout(timer);
}, [searchTerm]);

// Render
<Autocomplete
  options={results}
  getOptionLabel={(opt) => `${opt.product.name} (${opt.product.sku})`}
  onInputChange={(_, value) => setSearchTerm(value)}
  onChange={(_, value) => setFieldValue('stock_product', value?.id)}
/>
```

---

## API Response Example

**Request:**
```
GET /inventory/api/stock-products/?search=10mm
Authorization: Bearer <token>
```

**Response:**
```json
{
  "count": 1,
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

## When Submitting the Form

Send only the **stock_product UUID**, not the whole object:

```typescript
// ✅ Correct
const formData = {
  stock_product: "83096f71-b4aa-4fbe-8a18-dd9b12824a5e", // UUID string
  adjustment_type: "DAMAGE",
  quantity: -5,
  reason: "Water damage"
};

// ❌ Wrong
const formData = {
  stock_product: { id: "...", product: {...} }, // Don't send object
  ...
};
```

---

## Testing

1. Open Create Stock Adjustment modal
2. Type "10mm" in search
3. Check Network tab - should see: `GET /inventory/api/stock-products/?search=10mm`
4. Verify response has `count: 1` and results array
5. Select product from dropdown
6. Submit - should work ✅

---

**Backend is fixed!** Now just update the frontend to use the search endpoint. 🚀
