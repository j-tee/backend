# 📋 Sales History: Missing Product Details - Frontend Fix Guide

**Date:** October 7, 2025  
**Issue:** Sales table doesn't show which products were sold  
**Solution:** The API already returns product data - frontend just needs to display it!  
**Priority:** 🔴 HIGH

---

## ✅ Good News: Backend Already Sends Product Data!

The API response for each sale includes:

```json
{
  "id": "sale-uuid",
  "receipt_number": "REC-202510-01220",
  "customer": {
    "id": "customer-uuid",
    "name": "TechPro Ghana"
  },
  "total_amount": "3166.25",
  "status": "COMPLETED",
  "line_items": [  ← PRODUCTS ARE HERE!
    {
      "id": "item-uuid",
      "product": {
        "id": "product-uuid",
        "name": "MS Office Home & Business",
        "sku": "SOFT-DL-0002",
        "category": {
          "name": "Software"
        }
      },
      "quantity": "13.00",
      "unit_price": "243.56",
      "discount": "0.00"
    }
  ]
}
```

**The `line_items` array contains all the products sold!**

---

## 🎯 Frontend Implementation: Expandable Rows

### Step 1: Add Expanded State

```typescript
// In SalesHistory.tsx
const [expandedSale, setExpandedSale] = useState<string | null>(null);

const toggleSaleDetails = (saleId: string) => {
  setExpandedSale(expandedSale === saleId ? null : saleId);
};
```

### Step 2: Update Table Row

```tsx
{sales.map((sale) => (
  <React.Fragment key={sale.id}>
    {/* Main row - clickable */}
    <tr 
      onClick={() => toggleSaleDetails(sale.id)}
      style={{ cursor: 'pointer' }}
      className={expandedSale === sale.id ? 'table-active' : ''}
    >
      <td>{sale.receipt_number || 'N/A'}</td>
      <td>{formatDate(sale.completed_at || sale.created_at)}</td>
      <td>{sale.customer?.name || 'Walk-in'}</td>
      <td>
        {/* Show expandable icon */}
        {expandedSale === sale.id ? '▼' : '►'} {sale.line_items?.length || 0} items
      </td>
      <td>GH¢{sale.total_amount}</td>
      <td>
        <Badge bg={getStatusColor(sale.status)}>
          {sale.status}
        </Badge>
      </td>
      <td>{sale.payment_type || 'CASH'}</td>
    </tr>

    {/* Expanded row - shows products */}
    {expandedSale === sale.id && (
      <tr className="sale-details-row">
        <td colSpan={7} style={{ backgroundColor: '#f8f9fa', padding: '1rem' }}>
          <div className="sale-products">
            <h6 className="mb-3">📦 Products Sold:</h6>
            <Table size="sm" bordered>
              <thead>
                <tr>
                  <th>Product</th>
                  <th>SKU</th>
                  <th>Category</th>
                  <th className="text-end">Qty</th>
                  <th className="text-end">Unit Price</th>
                  <th className="text-end">Discount</th>
                  <th className="text-end">Total</th>
                </tr>
              </thead>
              <tbody>
                {sale.line_items?.map((item) => (
                  <tr key={item.id}>
                    <td><strong>{item.product.name}</strong></td>
                    <td><code>{item.product.sku}</code></td>
                    <td>
                      <Badge bg="secondary" pill>
                        {item.product.category?.name || 'N/A'}
                      </Badge>
                    </td>
                    <td className="text-end">{item.quantity}</td>
                    <td className="text-end">GH¢{item.unit_price}</td>
                    <td className="text-end">
                      {parseFloat(item.discount) > 0 ? (
                        <span className="text-success">-GH¢{item.discount}</span>
                      ) : (
                        '-'
                      )}
                    </td>
                    <td className="text-end">
                      <strong>
                        GH¢{(parseFloat(item.quantity) * parseFloat(item.unit_price) - parseFloat(item.discount)).toFixed(2)}
                      </strong>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td colSpan={6} className="text-end"><strong>Total:</strong></td>
                  <td className="text-end">
                    <strong className="text-primary">GH¢{sale.total_amount}</strong>
                  </td>
                </tr>
              </tfoot>
            </Table>

            {/* Additional sale info */}
            <Row className="mt-3">
              <Col md={6}>
                <small className="text-muted">
                  <strong>Payment:</strong> {sale.payment_type} | 
                  <strong> Cashier:</strong> {sale.user?.name}
                </small>
              </Col>
              <Col md={6} className="text-end">
                <small className="text-muted">
                  <strong>Date:</strong> {formatDateTime(sale.completed_at || sale.created_at)}
                </small>
              </Col>
            </Row>
          </div>
        </td>
      </tr>
    )}
  </React.Fragment>
))}
```

### Step 3: Add CSS Styling

```css
/* In SalesHistory.module.css or global styles */

.sale-details-row {
  background-color: #f8f9fa !important;
}

.sale-products {
  padding: 1rem;
  animation: slideDown 0.3s ease-out;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

tr[style*="cursor: pointer"]:hover {
  background-color: #e9ecef;
}

.table-active {
  background-color: #e7f1ff !important;
}
```

---

## 🎨 Alternative: View Details Button

If you prefer a button instead of clickable rows:

```tsx
<td>
  <Button 
    size="sm" 
    variant="outline-primary"
    onClick={() => toggleSaleDetails(sale.id)}
  >
    {expandedSale === sale.id ? 'Hide' : 'View'} Details
  </Button>
</td>
```

---

## 📊 Example: What Users Will See

**Before (Current):**
```
Receipt #         | Date       | Customer        | Items    | Amount   | Status
REC-202510-01220 | Oct 3, 2025 | TechPro Ghana  | 1 Items  | GH¢3,166 | COMPLETED
```

**After (With Expandable Row):**
```
Receipt #         | Date       | Customer        | Items       | Amount   | Status
▼ REC-202510-01220| Oct 3, 2025 | TechPro Ghana  | ▼ 1 items  | GH¢3,166 | COMPLETED

  📦 Products Sold:
  Product                    | SKU           | Category | Qty  | Unit Price | Discount | Total
  MS Office Home & Business  | SOFT-DL-0002  | Software | 13.00| GH¢243.56  | -        | GH¢3,166.28
                                                                            Total: GH¢3,166.25
  Payment: CASH | Cashier: Mike Tetteh | Date: Oct 3, 2025 12:13 PM
```

---

## ✅ Implementation Checklist

- [ ] Add `expandedSale` state to SalesHistory component
- [ ] Add `toggleSaleDetails` function
- [ ] Update table row with click handler
- [ ] Add expanded row with product details table
- [ ] Add expand/collapse icon (► / ▼)
- [ ] Style the expanded section
- [ ] Add hover effects
- [ ] Test with different sales (1 item, multiple items)
- [ ] Test expand/collapse animation

---

## 🔧 TypeScript Types Needed

```typescript
// Add to your types file
interface SaleLineItem {
  id: string;
  product: {
    id: string;
    name: string;
    sku: string;
    category?: {
      name: string;
    };
  };
  quantity: string;
  unit_price: string;
  discount: string;
}

interface Sale {
  id: string;
  receipt_number: string;
  customer?: {
    id: string;
    name: string;
  };
  total_amount: string;
  status: string;
  payment_type: string;
  line_items: SaleLineItem[];  ← ADD THIS
  user?: {
    name: string;
  };
  completed_at: string;
  created_at: string;
}
```

---

## 🎯 Benefits

1. **See What Was Sold** - Users can expand any sale to see products
2. **Verify Prices** - Check if products are being sold at correct prices
3. **Better UX** - Smooth expand/collapse animation
4. **No Extra API Calls** - Data is already loaded
5. **Mobile Friendly** - Expandable rows work on all screen sizes

---

## 📝 Next: Fix Unrealistic Prices

Once you can SEE the products, we can verify if the prices match your inventory:

1. Expand a few sales
2. Check the product names and prices
3. Compare with your stock prices (`Manage stocks` page)
4. If prices don't match, we'll fix the data generation script

---

**Status:** Ready to implement  
**Estimated Time:** 30 minutes  
**Impact:** HIGH - Users will finally see what products were sold!

