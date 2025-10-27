# Wholesale & Retail Sales Implementation Guide

**Status**: ✅ **COMPLETE** - Backend fully implemented  
**Date**: October 11, 2025  
**Priority**: HIGH - Critical feature for business operations

---

## 📋 Overview

Your POS system now supports **both RETAIL and WHOLESALE sales** with automatic price selection based on sale type. This allows you to:

- Sell the same product at different prices (retail vs wholesale)
- Toggle between retail and wholesale mode during sale creation
- Track retail vs wholesale sales separately for reporting
- Maintain proper profit calculations for both sale types

---

## 🏗️ Backend Architecture

### Database Schema

The system already had the foundation in place:

#### **StockProduct Model** (inventory/models.py)
```python
class StockProduct(models.Model):
    retail_price = DecimalField(max_digits=12, decimal_places=2)      # Higher price
    wholesale_price = DecimalField(max_digits=12, decimal_places=2)   # Lower price
    # ... other fields
```

#### **Sale Model** (sales/models.py)
```python
class Sale(models.Model):
    TYPE_RETAIL = 'RETAIL'
    TYPE_WHOLESALE = 'WHOLESALE'
    
    type = CharField(
        max_length=20,
        choices=[
            (TYPE_RETAIL, 'Retail'),
            (TYPE_WHOLESALE, 'Wholesale')
        ],
        default=TYPE_RETAIL
    )
    # ... other fields
```

---

## 🔧 Backend Implementation

### 1. Multi-Storefront Catalog Endpoint

**Endpoint**: `GET /inventory/api/storefronts/multi-storefront-catalog/`

**Already returns both prices**:
```json
{
  "storefronts": [...],
  "products": [
    {
      "product_id": "55b900ea-a046-4148-99e6-43cf7ed0e406",
      "product_name": "Sugar 1kg",
      "sku": "FOOD-0003",
      "retail_price": "3.12",       // ← Retail price
      "wholesale_price": "2.80",    // ← Wholesale price (if set)
      "total_available": 917,
      "locations": [...]
    }
  ]
}
```

**Note**: `wholesale_price` will be `null` if not set for a product.

---

### 2. Create Sale with Type

**Endpoint**: `POST /sales/api/sales/`

**Request**:
```json
{
  "storefront": "ceb5f89e-2fad-4ca1-bc8b-012c6431c073",
  "type": "WHOLESALE",     // ← NEW: Specify RETAIL or WHOLESALE
  "status": "DRAFT"
}
```

**Response**:
```json
{
  "id": "abc-123-def",
  "storefront": "ceb5f89e-2fad-4ca1-bc8b-012c6431c073",
  "type": "WHOLESALE",     // ← Sale type
  "status": "DRAFT",
  "total_amount": "0.00",
  ...
}
```

---

### 3. Add Item to Sale (Auto-Pricing)

**Endpoint**: `POST /sales/api/sales/{sale_id}/add_item/`

#### **Option A: Auto-Determine Price (Recommended)**

The backend will automatically use the correct price based on sale type:

**Request**:
```json
{
  "product": "55b900ea-a046-4148-99e6-43cf7ed0e406",
  "stock_product": "stock-product-id",
  "quantity": 10
  // ← NO unit_price needed! Backend auto-selects based on sale.type
}
```

**Backend Logic**:
```python
if sale.type == 'WHOLESALE':
    unit_price = stock_product.wholesale_price or stock_product.retail_price
else:  # RETAIL
    unit_price = stock_product.retail_price
```

#### **Option B: Explicit Price (Manual Override)**

You can still provide a custom price if needed:

**Request**:
```json
{
  "product": "55b900ea-a046-4148-99e6-43cf7ed0e406",
  "stock_product": "stock-product-id",
  "quantity": 10,
  "unit_price": "2.50"  // ← Custom price (overrides auto-pricing)
}
```

---

### 4. Toggle Sale Type (NEW!)

**Endpoint**: `POST /sales/api/sales/{sale_id}/toggle_sale_type/`

**Description**: Switch between RETAIL and WHOLESALE mode for a draft sale. Automatically updates all item prices.

**Request Option 1 - Auto-Toggle**:
```json
{}
// Toggles: RETAIL → WHOLESALE or WHOLESALE → RETAIL
```

**Request Option 2 - Specify Type**:
```json
{
  "type": "WHOLESALE"
}
```

**Response**:
```json
{
  "message": "Sale type changed from RETAIL to WHOLESALE",
  "sale": {
    "id": "abc-123",
    "type": "WHOLESALE",
    "total_amount": "28.00",  // ← Updated total
    ...
  },
  "updated_items": [
    {
      "product_name": "Sugar 1kg",
      "old_price": "3.12",
      "new_price": "2.80"
    },
    {
      "product_name": "Coca Cola",
      "old_price": "4.50",
      "new_price": "4.00"
    }
  ]
}
```

**Validation Rules**:
- ✅ Can only toggle DRAFT sales
- ✅ Automatically updates all items with new pricing
- ✅ Recalculates sale totals
- ✅ Logs audit trail
- ❌ Cannot change type after sale is completed

---

## 📊 API Response Examples

### Complete Sale Flow

#### Step 1: Create Draft Sale
```bash
POST /sales/api/sales/
{
  "storefront": "ceb5f89e-2fad-4ca1-bc8b-012c6431c073",
  "type": "RETAIL"
}
```

#### Step 2: Add Items (Auto-Pricing)
```bash
POST /sales/api/sales/{sale_id}/add_item/
{
  "product": "55b900ea-a046-4148-99e6-43cf7ed0e406",  // Sugar 1kg
  "quantity": 10
}
# Backend uses retail_price: 3.12
# Subtotal: 10 × 3.12 = 31.20
```

#### Step 3: Toggle to Wholesale
```bash
POST /sales/api/sales/{sale_id}/toggle_sale_type/
{}
# Backend updates all items to wholesale_price: 2.80
# New subtotal: 10 × 2.80 = 28.00
```

#### Step 4: Complete Sale
```bash
POST /sales/api/sales/{sale_id}/complete/
{
  "payment_type": "CASH",
  "payments": [{"amount_paid": "28.00", "payment_method": "CASH"}]
}
```

---

## 🎨 Frontend Integration Guide

### 1. Update Sale Creation Page

**Add Toggle Button**:
```typescript
const [saleType, setSaleType] = useState<'RETAIL' | 'WHOLESALE'>('RETAIL');

// Create sale with type
const createSale = async () => {
  const response = await fetch('/sales/api/sales/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Token ${token}`
    },
    body: JSON.stringify({
      storefront: storefrontId,
      type: saleType,  // ← Pass sale type
      status: 'DRAFT'
    })
  });
  
  const sale = await response.json();
  setCurrentSale(sale);
};
```

**Toggle Button Component**:
```tsx
<div className="sale-type-toggle">
  <button
    className={saleType === 'RETAIL' ? 'active' : ''}
    onClick={() => toggleSaleType('RETAIL')}
  >
    🛒 Retail Sale
  </button>
  <button
    className={saleType === 'WHOLESALE' ? 'active' : ''}
    onClick={() => toggleSaleType('WHOLESALE')}
  >
    📦 Wholesale Sale
  </button>
</div>
```

### 2. Display Appropriate Price

**Product Card**:
```tsx
const ProductCard = ({ product, saleType }) => {
  const price = saleType === 'WHOLESALE' 
    ? product.wholesale_price || product.retail_price
    : product.retail_price;
  
  const hasWholesale = product.wholesale_price !== null;
  
  return (
    <div className="product-card">
      <h3>{product.product_name}</h3>
      
      {/* Show both prices if wholesale available */}
      {hasWholesale && (
        <div className="price-display">
          <div className={saleType === 'RETAIL' ? 'active-price' : 'inactive-price'}>
            Retail: GH₵ {product.retail_price}
          </div>
          <div className={saleType === 'WHOLESALE' ? 'active-price' : 'inactive-price'}>
            Wholesale: GH₵ {product.wholesale_price}
          </div>
        </div>
      )}
      
      {/* Single price if wholesale not set */}
      {!hasWholesale && (
        <div className="price-display">
          GH₵ {product.retail_price}
        </div>
      )}
      
      <button onClick={() => addToCart(product, price)}>
        Add to Cart
      </button>
    </div>
  );
};
```

### 3. Toggle Sale Type Mid-Transaction

**Toggle Function**:
```typescript
const toggleSaleType = async (newType?: 'RETAIL' | 'WHOLESALE') => {
  if (!currentSale || currentSale.status !== 'DRAFT') {
    alert('Can only change sale type for draft sales');
    return;
  }
  
  const response = await fetch(
    `/sales/api/sales/${currentSale.id}/toggle_sale_type/`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Token ${token}`
      },
      body: JSON.stringify(newType ? { type: newType } : {})
    }
  );
  
  const result = await response.json();
  
  // Update current sale with new totals
  setCurrentSale(result.sale);
  setSaleType(result.sale.type);
  
  // Show notification
  toast.success(result.message);
  
  // Optionally show price changes
  if (result.updated_items?.length > 0) {
    console.log('Price changes:', result.updated_items);
  }
};
```

### 4. Add Item Without Price (Let Backend Handle It)

**Simplified Add to Cart**:
```typescript
const addItemToSale = async (product: Product, quantity: number) => {
  const response = await fetch(
    `/sales/api/sales/${currentSale.id}/add_item/`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Token ${token}`
      },
      body: JSON.stringify({
        product: product.product_id,
        stock_product: product.stock_product_ids[0],  // Latest stock
        quantity: quantity
        // NO unit_price! Backend auto-determines based on sale.type
      })
    }
  );
  
  const saleItem = await response.json();
  
  // Refresh sale to get updated totals
  refreshSale();
};
```

---

## 📱 UI/UX Recommendations

### Visual Indicators

1. **Color Coding**:
   - Retail mode: Blue/Default
   - Wholesale mode: Orange/Amber
   
2. **Price Display**:
   ```
   When in RETAIL mode:
   ┌─────────────────────────┐
   │ Sugar 1kg               │
   │ ✓ GH₵ 3.12 (Retail)     │  ← Active (bold, highlighted)
   │   GH₵ 2.80 (Wholesale)  │  ← Inactive (greyed out)
   └─────────────────────────┘
   
   When in WHOLESALE mode:
   ┌─────────────────────────┐
   │ Sugar 1kg               │
   │   GH₵ 3.12 (Retail)     │  ← Inactive (greyed out)
   │ ✓ GH₵ 2.80 (Wholesale)  │  ← Active (bold, highlighted)
   └─────────────────────────┘
   ```

3. **Sale Summary Badge**:
   ```
   🛒 RETAIL SALE     or     📦 WHOLESALE SALE
   ```

4. **Confirmation on Toggle**:
   ```
   "Switch to Wholesale?
    All prices will be updated:
    - Sugar 1kg: GH₵ 3.12 → GH₵ 2.80
    - Coca Cola: GH₵ 4.50 → GH₵ 4.00
    
    New Total: GH₵ 28.00
    
    [Cancel] [Confirm]"
   ```

---

## 🔍 Testing Checklist

### Backend Tests

- [ ] Create RETAIL sale → default type is RETAIL
- [ ] Create WHOLESALE sale → type is WHOLESALE
- [ ] Add item to RETAIL sale → uses retail_price
- [ ] Add item to WHOLESALE sale → uses wholesale_price
- [ ] Add item with no wholesale_price → falls back to retail_price
- [ ] Toggle DRAFT sale RETAIL → WHOLESALE → prices update
- [ ] Toggle DRAFT sale WHOLESALE → RETAIL → prices update
- [ ] Toggle COMPLETED sale → returns error
- [ ] Complete WHOLESALE sale → status changes, type preserved

### Frontend Tests

- [ ] Toggle button switches between RETAIL/WHOLESALE
- [ ] Product cards show correct price based on mode
- [ ] Adding item uses correct price
- [ ] Toggling mid-transaction updates all items
- [ ] Sale summary shows correct total after toggle
- [ ] Cannot toggle after sale completion
- [ ] Visual indicators clearly show current mode

---

## 🐛 Troubleshooting

### Issue: Product shows "Out of Stock" but has inventory

**Diagnosis**: Wrong storefront being queried.  
**Fix**: Use `/multi-storefront-catalog/` endpoint instead of single-storefront endpoint.  
**See**: `FRONTEND_FIX_OUT_OF_STOCK.md`

---

### Issue: Wholesale price is null

**Cause**: Wholesale price not set on StockProduct.  
**Solution**: 
1. Backend falls back to retail_price automatically
2. Update StockProduct to set wholesale_price:
   ```python
   stock_product.wholesale_price = Decimal('2.80')
   stock_product.save()
   ```

---

### Issue: Toggle returns error "Can only change sale type for draft sales"

**Cause**: Trying to toggle a completed/cancelled sale.  
**Solution**: Only allow toggle button for DRAFT sales:
```tsx
{currentSale?.status === 'DRAFT' && (
  <SaleTypeToggle />
)}
```

---

### Issue: Prices not updating after toggle

**Cause**: Frontend not refreshing sale data.  
**Solution**: Refresh sale after toggle:
```typescript
const result = await toggleSaleType();
setCurrentSale(result.sale);  // ← Update state with new data
```

---

## 📊 Reporting & Analytics

### Track Retail vs Wholesale Sales

**Query retail sales**:
```sql
SELECT COUNT(*), SUM(total_amount)
FROM sales
WHERE type = 'RETAIL' AND status = 'COMPLETED'
```

**Query wholesale sales**:
```sql
SELECT COUNT(*), SUM(total_amount)
FROM sales
WHERE type = 'WHOLESALE' AND status = 'COMPLETED'
```

**Future Enhancement**: Add dashboard widgets for:
- Retail sales today
- Wholesale sales today
- Retail vs wholesale ratio
- Average transaction value by type

---

## 🎯 Business Rules

### When to Use Wholesale Pricing

**Typical Scenarios**:
1. Bulk purchases (e.g., buying 100+ units)
2. Registered wholesale customers
3. Business-to-business (B2B) sales
4. Special promotions

**Access Control** (Future Enhancement):
- Regular cashiers: Retail only
- Managers: Both retail and wholesale
- Wholesale customers: Auto-default to wholesale

### Price Setting Guidelines

**Example**:
- **Cost**: GH₵ 2.00
- **Retail Price**: GH₵ 3.12 (56% markup)
- **Wholesale Price**: GH₵ 2.80 (40% markup)

**Rule**: Wholesale price should still be profitable but lower than retail.

---

## 🔐 Security & Audit

### Audit Trail

All sale type changes are logged:
```python
AuditLog.log_event(
    event_type='sale.type_changed',
    user=request.user,
    sale=sale,
    event_data={
        'old_type': 'RETAIL',
        'new_type': 'WHOLESALE',
        'items_updated': 2,
        'updated_items': [...]
    },
    description='Sale type changed from RETAIL to WHOLESALE'
)
```

**Access Log**:
- Who changed the sale type
- When it was changed
- What prices were updated
- IP address and user agent

---

## 📚 API Quick Reference

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/inventory/api/storefronts/multi-storefront-catalog/` | GET | Get products with retail & wholesale prices |
| `/sales/api/sales/` | POST | Create sale (specify `type: RETAIL/WHOLESALE`) |
| `/sales/api/sales/{id}/add_item/` | POST | Add item (auto-prices based on sale type) |
| `/sales/api/sales/{id}/toggle_sale_type/` | POST | Toggle RETAIL ↔ WHOLESALE |
| `/sales/api/sales/{id}/complete/` | POST | Complete sale (preserves type) |

---

## ✅ Summary

### What Changed

1. **`AddSaleItemSerializer`** - `unit_price` now optional, auto-determines from sale type
2. **`SaleViewSet`** - Added `toggle_sale_type()` action
3. **Auto-Pricing Logic** - Selects retail vs wholesale price based on `sale.type`
4. **Audit Logging** - Tracks all sale type changes

### What Stayed The Same

- Database schema (already had fields)
- Sale completion flow
- Payment processing
- Inventory management

### Frontend Work Required

1. Add RETAIL/WHOLESALE toggle button
2. Display both prices (highlight active one)
3. Call `toggle_sale_type` endpoint when toggled
4. Update UI based on sale type

**Estimated Time**: 2-4 hours for frontend implementation

---

## 🚀 Next Steps

1. **Test Backend** - Use Postman/curl to verify all endpoints
2. **Implement Frontend** - Add toggle button and price display
3. **User Training** - Educate staff on when to use wholesale mode
4. **Set Wholesale Prices** - Update StockProducts with wholesale pricing
5. **Monitor Usage** - Track retail vs wholesale sales in reports

---

**Last Updated**: October 11, 2025  
**Status**: ✅ Backend Complete - Frontend Integration Needed  
**Priority**: HIGH
