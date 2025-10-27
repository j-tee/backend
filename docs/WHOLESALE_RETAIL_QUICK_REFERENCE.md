# Quick Reference: Wholesale & Retail Sales API

---

## 🚀 API Endpoints

### 1. Get Product Catalog (with both prices)
```bash
GET /inventory/api/storefronts/multi-storefront-catalog/
Authorization: Token {your-token}
```

**Response**:
```json
{
  "products": [
    {
      "product_id": "uuid",
      "product_name": "Sugar 1kg",
      "sku": "FOOD-0003",
      "retail_price": "3.12",      ← Higher price
      "wholesale_price": "2.65",   ← Lower price (or null)
      "total_available": 917
    }
  ]
}
```

---

### 2. Create Sale
```bash
POST /sales/api/sales/
Authorization: Token {your-token}
Content-Type: application/json

{
  "storefront": "storefront-uuid",
  "type": "WHOLESALE",    ← "RETAIL" or "WHOLESALE"
  "status": "DRAFT"
}
```

**Response**:
```json
{
  "id": "sale-uuid",
  "type": "WHOLESALE",
  "status": "DRAFT",
  "total_amount": "0.00"
}
```

---

### 3. Add Item (Auto-Pricing)
```bash
POST /sales/api/sales/{sale-id}/add_item/
Authorization: Token {your-token}
Content-Type: application/json

{
  "product": "product-uuid",
  "quantity": 10
  ← NO unit_price needed! Backend auto-determines
}
```

**What happens**:
- If sale.type == 'WHOLESALE' → uses wholesale_price
- If sale.type == 'RETAIL' → uses retail_price
- If wholesale_price is null → falls back to retail_price

**Response**:
```json
{
  "id": "item-uuid",
  "product": "product-uuid",
  "quantity": "10.00",
  "unit_price": "2.65",    ← Auto-determined
  "total_price": "26.50"
}
```

---

### 4. Toggle Sale Type (NEW!)
```bash
POST /sales/api/sales/{sale-id}/toggle_sale_type/
Authorization: Token {your-token}
Content-Type: application/json

{}  ← Empty toggles RETAIL ↔ WHOLESALE

# Or specify type:
{"type": "WHOLESALE"}
```

**Response**:
```json
{
  "message": "Sale type changed from RETAIL to WHOLESALE",
  "sale": {
    "id": "sale-uuid",
    "type": "WHOLESALE",
    "total_amount": "26.50"  ← Updated!
  },
  "updated_items": [
    {
      "product_name": "Sugar 1kg",
      "old_price": "3.12",
      "new_price": "2.65"
    }
  ]
}
```

**Rules**:
- ✅ Only works for DRAFT sales
- ✅ Updates all items automatically
- ✅ Recalculates totals
- ❌ Cannot toggle completed sales

---

### 5. Complete Sale
```bash
POST /sales/api/sales/{sale-id}/complete/
Authorization: Token {your-token}
Content-Type: application/json

{
  "payment_type": "CASH",
  "payments": [
    {
      "amount_paid": "26.50",
      "payment_method": "CASH"
    }
  ]
}
```

**Response**:
```json
{
  "id": "sale-uuid",
  "type": "WHOLESALE",       ← Type preserved
  "status": "COMPLETED",
  "total_amount": "26.50",
  "receipt_number": "SAL-001234"
}
```

---

## 💻 Frontend Code Snippets

### Create Sale with Type
```typescript
const createSale = async (type: 'RETAIL' | 'WHOLESALE') => {
  const response = await fetch('/sales/api/sales/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Token ${token}`
    },
    body: JSON.stringify({
      storefront: storefrontId,
      type: type,
      status: 'DRAFT'
    })
  });
  return response.json();
};
```

### Add Item (Auto-Pricing)
```typescript
const addItem = async (saleId: string, productId: string, quantity: number) => {
  const response = await fetch(`/sales/api/sales/${saleId}/add_item/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Token ${token}`
    },
    body: JSON.stringify({
      product: productId,
      quantity: quantity
      // NO unit_price - backend handles it!
    })
  });
  return response.json();
};
```

### Toggle Sale Type
```typescript
const toggleType = async (saleId: string, newType?: 'RETAIL' | 'WHOLESALE') => {
  const response = await fetch(`/sales/api/sales/${saleId}/toggle_sale_type/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Token ${token}`
    },
    body: JSON.stringify(newType ? { type: newType } : {})
  });
  return response.json();
};
```

### Display Price
```tsx
const activePrice = saleType === 'WHOLESALE'
  ? product.wholesale_price || product.retail_price
  : product.retail_price;

<div className="price">GH₵ {activePrice}</div>
```

---

## 📊 Price Comparison

| Product | Retail | Wholesale | Savings |
|---------|--------|-----------|---------|
| Sugar 1kg | GH₵ 3.12 | GH₵ 2.65 | 15.1% |
| Coca Cola | GH₵ 4.50 | GH₵ 4.00 | 11.1% |
| HP Laptop | GH₵ 3500 | GH₵ 3200 | 8.6% |

**10 units of Sugar**:
- Retail: 10 × 3.12 = **GH₵ 31.20**
- Wholesale: 10 × 2.65 = **GH₵ 26.50**
- **Savings: GH₵ 4.70**

---

## ✅ Testing Checklist

- [ ] Fetch catalog - see both prices
- [ ] Create RETAIL sale
- [ ] Add item - verify uses retail_price
- [ ] Create WHOLESALE sale
- [ ] Add item - verify uses wholesale_price
- [ ] Toggle RETAIL → WHOLESALE
- [ ] Verify all prices update
- [ ] Toggle WHOLESALE → RETAIL
- [ ] Complete sale - verify type preserved
- [ ] Try toggle completed sale - verify error

---

## 🐛 Common Issues

**Issue**: "unit_price is required"  
**Fix**: Remove `unit_price` from request - let backend auto-determine

**Issue**: "Can only change sale type for draft sales"  
**Fix**: Only allow toggle when `sale.status === 'DRAFT'`

**Issue**: Wholesale price is null  
**Fix**: Backend falls back to retail_price automatically (no error)

**Issue**: Prices not updating after toggle  
**Fix**: Refresh sale data from API response

---

## 📚 Documentation Files

1. **WHOLESALE_RETAIL_SUMMARY.md** - Overview & summary
2. **WHOLESALE_RETAIL_IMPLEMENTATION.md** - Complete guide
3. **FRONTEND_WHOLESALE_INTEGRATION.md** - Frontend examples
4. **test_wholesale_retail.py** - Test script

---

## 🎯 Key Points

✨ **Auto-Pricing**: Backend determines price based on sale type  
🔄 **Toggle Anytime**: Switch between retail/wholesale during draft  
💾 **Type Preserved**: Sale type saved for reporting  
📝 **Audit Trail**: All changes logged  
🛡️ **Safe Fallback**: Uses retail price if wholesale not set  

---

**Last Updated**: October 11, 2025  
**Status**: ✅ Ready for Production
