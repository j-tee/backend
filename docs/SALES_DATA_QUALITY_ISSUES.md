# Sales Data Quality Issues - Analysis & Solutions

**Date:** October 7, 2025  
**Issues Identified:**
1. Frontend table doesn't show which products were sold
2. Sales prices may not match actual stock prices  
**Status:** 🔍 Investigating

---

## 🔴 Issue 1: Frontend Doesn't Show Products

### Current Frontend Display
The Sales History table shows:
- Receipt #
- Date  
- Customer
- **Items** (just a count like "1 Items", "3 Items")
- Amount
- Status
- Payment

**Problem:** You can't see WHAT products were actually sold!

### What Users Need to See
Users should be able to:
1. **Expand each sale** to see the product list
2. **See product details**: Name, SKU, Quantity, Unit Price, Subtotal
3. **Verify the products** match expected inventory

### Recommended Frontend Changes

#### Option 1: Expandable Rows (BEST)
```tsx
<tr onClick={() => toggleSaleDetails(sale.id)}>
  {/* Regular columns */}
</tr>
{expandedSale === sale.id && (
  <tr className="sale-details-row">
    <td colSpan={8}>
      <div className="sale-items">
        <h6>Products Sold:</h6>
        <table className="table table-sm">
          <thead>
            <tr>
              <th>Product</th>
              <th>SKU</th>
              <th>Qty</th>
              <th>Unit Price</th>
              <th>Total</th>
            </tr>
          </thead>
          <tbody>
            {sale.sale_items.map(item => (
              <tr key={item.id}>
                <td>{item.product.name}</td>
                <td>{item.product.sku}</td>
                <td>{item.quantity}</td>
                <td>GH¢{item.unit_price}</td>
                <td>GH¢{item.quantity * item.unit_price}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </td>
  </tr>
)}
```

#### Option 2: Modal/Popup
Click "View Details" button → Opens modal with full sale information including products

#### Option 3: Tooltip on Hover
Hover over "Items" column → Shows popup with product list

---

## 🔴 Issue 2: Unrealistic Sales Prices

### Investigation Needed

Let me check:
1. Are sale prices matching stock selling prices?
2. Are products being sold that don't exist in stock?
3. Are the generated prices random or based on actual inventory?

### Quick Check Script

```python
# Run this to verify price accuracy
python manage.py shell <<'EOF'
from sales.models import Sale
from inventory.models import StockProduct
from accounts.models import Business

biz = Business.objects.get(name='DataLogique Systems')
sales = Sale.objects.filter(business=biz, status='COMPLETED')[:5]

print("Checking 5 sample sales...")
for sale in sales:
    print(f"\n{sale.receipt_number} - GH¢{sale.total_amount}")
    for item in sale.sale_items.all():
        # Find current stock price
        stock = item.stock_product
        if stock:
            print(f"  {item.product.name}: GH¢{item.unit_price} (stock shows GH¢{stock.retail_price})")
        else:
            print(f"  {item.product.name}: GH¢{item.unit_price} (NO STOCK LINK!)")
EOF
```

---

##  Recommended Solutions

### For Frontend: Add Product Details View

**Priority 1: Expandable Rows**
This is the best UX - click row to expand and see products

**Implementation:**
1. Add `expanded` state to SalesHistory component
2. Add click handler to table rows
3. Render product details when expanded
4. Style the expanded section

**API Already Returns Product Data:**
The backend already includes `sale_items` with product details in the response!

```json
{
  "id": "uuid",
  "receipt_number": "REC-202510-01220",
  "sale_items": [
    {
      "product": {
        "name": "MS Office Home & Business",
        "sku": "SOFT-DL-0002"
      },
      "quantity": "13.00",
      "unit_price": "243.56"
    }
  ]
}
```

### For Backend: Verify Data Quality

**If prices are wrong, we need to:**
1. Fix the data generation script (`populate_datalogique_simple.py`)
2. Regenerate the sales data with correct prices
3. Ensure sale prices match stock selling prices

---

## Next Steps

1. **Check Frontend API Response** - Verify `sale_items` are in the data
2. **Implement Expandable Rows** - Show product details
3. **Verify Price Accuracy** - Run script to check sale vs stock prices
4. **Fix Data if Needed** - Regenerate with correct prices

---

**Status:** Waiting for investigation results  
**Priority:** HIGH - Users need to see what products were sold!
