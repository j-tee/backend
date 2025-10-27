# 🚀 Frontend Receipt Integration - Quick Start Guide

**Time to implement**: 30 minutes to 2 hours (depending on approach)  
**Difficulty**: ⭐ Easy (Simple Print) to ⭐⭐ Medium (Full Modal)  
**Backend Status**: ✅ Ready to use

---

## Option 1: Simple Print Link (10 minutes) ⭐

**Best for**: Quick implementation, minimal code

### Add to Sales History Component

```tsx
// SalesHistory.tsx
{sale.status === 'COMPLETED' && (
  <a
    href={`/sales/api/sales/${sale.id}/receipt/?format=html`}
    target="_blank"
    className="btn btn-sm btn-outline-primary"
  >
    🖨️ View Receipt
  </a>
)}
```

**That's it!** User clicks → New tab opens → Browser print dialog (Ctrl+P)

---

## Option 2: Auto-Print Button (30 minutes) ⭐

**Best for**: Better UX, auto-triggers print dialog

```tsx
const handlePrintReceipt = (saleId: string) => {
  const printWindow = window.open(
    `/sales/api/sales/${saleId}/receipt/?format=html`,
    '_blank',
    'width=800,height=600'
  )
  
  // Auto-trigger print when loaded
  printWindow?.addEventListener('load', () => {
    printWindow.print()
  })
}

// In your component
<Button
  variant="outline-primary"
  size="sm"
  onClick={() => handlePrintReceipt(sale.id)}
  disabled={sale.status !== 'COMPLETED'}
>
  🖨️ Print Receipt
</Button>
```

---

## Option 3: Receipt Modal (2 hours) ⭐⭐

**Best for**: Professional UI, preview before print

### Step 1: Create ReceiptModal Component

```tsx
// components/ReceiptModal.tsx
import React, { useState, useEffect } from 'react'
import { Modal, Button, Table, Badge, Spinner, Alert } from 'react-bootstrap'

interface ReceiptModalProps {
  show: boolean
  saleId: string | null
  onHide: () => void
}

export const ReceiptModal: React.FC<ReceiptModalProps> = ({ show, saleId, onHide }) => {
  const [receipt, setReceipt] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  useEffect(() => {
    if (show && saleId) {
      loadReceipt()
    }
  }, [show, saleId])
  
  const loadReceipt = async () => {
    setLoading(true)
    setError(null)
    
    try {
      const response = await fetch(`/sales/api/sales/${saleId}/receipt/`, {
        headers: {
          'Authorization': `Token ${localStorage.getItem('authToken')}`
        }
      })
      
      if (!response.ok) {
        throw new Error('Failed to load receipt')
      }
      
      const data = await response.json()
      setReceipt(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }
  
  const handlePrint = () => {
    window.print()
  }
  
  const handleDownloadPDF = () => {
    window.location.href = `/sales/api/sales/${saleId}/receipt/?format=pdf`
  }
  
  return (
    <Modal show={show} onHide={onHide} size="lg">
      <Modal.Header closeButton>
        <Modal.Title>
          {receipt ? (
            <>
              Receipt #{receipt.receipt_number}
              {receipt.type === 'WHOLESALE' && (
                <Badge bg="warning" text="dark" className="ms-2">WHOLESALE</Badge>
              )}
            </>
          ) : (
            'Loading Receipt...'
          )}
        </Modal.Title>
      </Modal.Header>
      
      <Modal.Body>
        {loading && (
          <div className="text-center py-5">
            <Spinner animation="border" />
            <p className="mt-3">Loading receipt...</p>
          </div>
        )}
        
        {error && (
          <Alert variant="danger">
            <strong>Error:</strong> {error}
          </Alert>
        )}
        
        {receipt && !loading && (
          <div id="receipt-content">
            {/* Business Header */}
            <div className="text-center mb-4 pb-3 border-bottom">
              <h4 className="mb-1">{receipt.business_name}</h4>
              <div className="text-muted">
                <div><strong>{receipt.storefront_name}</strong></div>
                <div style={{ fontSize: '0.9em' }}>{receipt.business_address}</div>
                <div style={{ fontSize: '0.9em' }}>
                  Phone: {receipt.business_phone_numbers?.[0] || 'N/A'}
                </div>
                <div style={{ fontSize: '0.9em' }}>TIN: {receipt.business_tin}</div>
              </div>
            </div>
            
            {/* Sale Type Badge */}
            {receipt.type === 'WHOLESALE' ? (
              <Alert variant="warning" className="text-center fw-bold">
                ⚠️ WHOLESALE SALE ⚠️
              </Alert>
            ) : (
              <Alert variant="info" className="text-center">
                🛒 RETAIL SALE
              </Alert>
            )}
            
            {/* Receipt Details */}
            <Table size="sm" borderless className="mb-3">
              <tbody>
                <tr>
                  <td width="30%"><strong>Receipt #:</strong></td>
                  <td>{receipt.receipt_number}</td>
                </tr>
                <tr>
                  <td><strong>Date:</strong></td>
                  <td>{receipt.completed_at_formatted}</td>
                </tr>
                <tr>
                  <td><strong>Served by:</strong></td>
                  <td>{receipt.served_by || 'Staff'}</td>
                </tr>
                <tr>
                  <td><strong>Customer:</strong></td>
                  <td>
                    {receipt.customer_name || 'Walk-in Customer'}
                    {receipt.customer_type && (
                      <Badge bg="secondary" className="ms-2">{receipt.customer_type}</Badge>
                    )}
                  </td>
                </tr>
                {receipt.customer_phone && (
                  <tr>
                    <td><strong>Phone:</strong></td>
                    <td>{receipt.customer_phone}</td>
                  </tr>
                )}
                <tr>
                  <td><strong>Payment:</strong></td>
                  <td>{receipt.payment_type_display}</td>
                </tr>
              </tbody>
            </Table>
            
            {/* Line Items */}
            <h6 className="border-bottom pb-2 mb-3">ITEMS</h6>
            <Table bordered size="sm">
              <thead className="table-light">
                <tr>
                  <th>Product</th>
                  <th className="text-end">Qty</th>
                  <th className="text-end">Price</th>
                  <th className="text-end">Total</th>
                </tr>
              </thead>
              <tbody>
                {receipt.line_items?.map((item: any, idx: number) => (
                  <React.Fragment key={idx}>
                    <tr>
                      <td>
                        <strong>{item.product_name}</strong>
                        <br />
                        <small className="text-muted">
                          SKU: {item.sku}
                          {receipt.type === 'WHOLESALE' && (
                            <span className="text-warning ms-2">(Wholesale)</span>
                          )}
                        </small>
                      </td>
                      <td className="text-end">{item.quantity}</td>
                      <td className="text-end">GH₵ {Number(item.unit_price).toFixed(2)}</td>
                      <td className="text-end">GH₵ {Number(item.total_price).toFixed(2)}</td>
                    </tr>
                    {item.discount_amount > 0 && (
                      <tr>
                        <td colSpan={3} className="text-end">
                          <small>Item Discount:</small>
                        </td>
                        <td className="text-end text-danger">
                          -GH₵ {Number(item.discount_amount).toFixed(2)}
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
              <tfoot>
                <tr className="table-light">
                  <td colSpan={3} className="text-end">Subtotal:</td>
                  <td className="text-end">GH₵ {Number(receipt.subtotal).toFixed(2)}</td>
                </tr>
                {receipt.discount_amount > 0 && (
                  <tr>
                    <td colSpan={3} className="text-end">Discount:</td>
                    <td className="text-end text-danger">
                      -GH₵ {Number(receipt.discount_amount).toFixed(2)}
                    </td>
                  </tr>
                )}
                {receipt.tax_amount > 0 && (
                  <tr>
                    <td colSpan={3} className="text-end">Tax:</td>
                    <td className="text-end">GH₵ {Number(receipt.tax_amount).toFixed(2)}</td>
                  </tr>
                )}
                <tr className="table-active fw-bold">
                  <td colSpan={3} className="text-end"><strong>TOTAL:</strong></td>
                  <td className="text-end"><strong>GH₵ {Number(receipt.total_amount).toFixed(2)}</strong></td>
                </tr>
                <tr>
                  <td colSpan={3} className="text-end">
                    Paid ({receipt.payment_type}):
                  </td>
                  <td className="text-end">GH₵ {Number(receipt.amount_paid).toFixed(2)}</td>
                </tr>
                {receipt.change_given > 0 && (
                  <tr>
                    <td colSpan={3} className="text-end">Change:</td>
                    <td className="text-end">GH₵ {Number(receipt.change_given).toFixed(2)}</td>
                  </tr>
                )}
                {receipt.amount_due > 0 && (
                  <tr className="text-danger fw-bold">
                    <td colSpan={3} className="text-end"><strong>AMOUNT DUE:</strong></td>
                    <td className="text-end"><strong>GH₵ {Number(receipt.amount_due).toFixed(2)}</strong></td>
                  </tr>
                )}
              </tfoot>
            </Table>
            
            {/* Footer */}
            <div className="text-center mt-4 pt-3 border-top">
              <p className="mb-1"><strong>Thank you for your business!</strong></p>
              <small className="text-muted">
                Items: {receipt.total_items} | Total Qty: {receipt.total_quantity}
              </small>
            </div>
          </div>
        )}
      </Modal.Body>
      
      <Modal.Footer className="no-print">
        <Button variant="outline-secondary" onClick={onHide}>
          Close
        </Button>
        <Button variant="outline-primary" onClick={handleDownloadPDF}>
          📥 Download PDF
        </Button>
        <Button variant="primary" onClick={handlePrint}>
          🖨️ Print
        </Button>
      </Modal.Footer>
    </Modal>
  )
}
```

### Step 2: Add Print-specific CSS

```css
/* Add to your global CSS file */
@media print {
  /* Hide everything */
  body * {
    visibility: hidden;
  }
  
  /* Show only receipt content */
  #receipt-content,
  #receipt-content * {
    visibility: visible;
  }
  
  #receipt-content {
    position: absolute;
    left: 0;
    top: 0;
    width: 100%;
  }
  
  /* Hide modal controls */
  .no-print,
  .modal-header,
  .modal-footer {
    display: none !important;
  }
  
  /* Optimize modal for print */
  .modal {
    position: static !important;
  }
  
  .modal-dialog {
    width: 100% !important;
    max-width: none !important;
    margin: 0 !important;
  }
  
  .modal-content {
    border: none !important;
    box-shadow: none !important;
  }
  
  /* Ensure colors print */
  * {
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
  }
}
```

### Step 3: Use in Sales History

```tsx
// SalesHistory.tsx
import { ReceiptModal } from './components/ReceiptModal'

const SalesHistory = () => {
  const [showReceipt, setShowReceipt] = useState(false)
  const [selectedSaleId, setSelectedSaleId] = useState<string | null>(null)
  
  const handleViewReceipt = (saleId: string) => {
    setSelectedSaleId(saleId)
    setShowReceipt(true)
  }
  
  return (
    <>
      <Table>
        <tbody>
          {sales.map(sale => (
            <tr key={sale.id}>
              <td>{sale.receipt_number}</td>
              <td>{sale.customer_name || 'Walk-in'}</td>
              <td>GH₵ {sale.total_amount}</td>
              <td>
                {sale.status === 'COMPLETED' && (
                  <Button
                    variant="outline-primary"
                    size="sm"
                    onClick={() => handleViewReceipt(sale.id)}
                  >
                    🖨️ View Receipt
                  </Button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </Table>
      
      <ReceiptModal
        show={showReceipt}
        saleId={selectedSaleId}
        onHide={() => setShowReceipt(false)}
      />
    </>
  )
}
```

---

## 🎯 Quick Integration Summary

### What You Need

1. **Backend API** (✅ Already available):
   ```
   GET /sales/api/sales/{sale_id}/receipt/
   GET /sales/api/sales/{sale_id}/receipt/?format=html
   GET /sales/api/sales/{sale_id}/receipt/?format=pdf
   ```

2. **Frontend Code** (Choose one):
   - Option 1: Simple link (1 line of code)
   - Option 2: Auto-print button (5 lines of code)
   - Option 3: Full modal (copy-paste component above)

3. **Print CSS** (Required for all options):
   - Copy print styles to your CSS file

### Files to Modify

```
frontend/
├── src/
│   ├── components/
│   │   └── ReceiptModal.tsx        ← Create this (Option 3)
│   ├── pages/
│   │   └── SalesHistory.tsx        ← Add button here
│   └── styles/
│       └── print.css               ← Add print styles
```

---

## ✅ Testing Checklist

After implementation, verify:

- [ ] Receipt button only shows for COMPLETED sales
- [ ] Clicking button opens receipt (new tab or modal)
- [ ] Business name and address display correctly
- [ ] Wholesale sales show yellow warning badge
- [ ] Retail sales show blue info badge
- [ ] Customer name shows (or "Walk-in Customer")
- [ ] All products and prices display correctly
- [ ] Totals calculate correctly
- [ ] Print function works (Ctrl+P or Print button)
- [ ] Receipt prints cleanly (no cut-off content)
- [ ] PDF download works (if implemented)

---

## 🐛 Common Issues & Solutions

### Issue: Receipt prints on multiple pages

**Solution**: Adjust printer settings
```
1. Open print dialog (Ctrl+P)
2. Click "More settings"
3. Set "Scale" to "Fit to page"
4. Or set custom scale (e.g., 85%)
```

### Issue: Colors don't print

**Solution**: Enable background graphics
```css
/* Already in CSS above */
* {
  -webkit-print-color-adjust: exact !important;
  print-color-adjust: exact !important;
}
```

Or in browser print dialog:
```
1. Open print dialog
2. Click "More settings"
3. Enable "Background graphics"
```

### Issue: Modal doesn't print, blank page appears

**Solution**: Check print CSS is loaded
```css
/* Ensure this is in your CSS */
@media print {
  #receipt-content,
  #receipt-content * {
    visibility: visible;
  }
}
```

### Issue: "Failed to load receipt" error

**Solution**: Check sale status
```tsx
// Only COMPLETED sales can have receipts
if (sale.status !== 'COMPLETED') {
  // Don't show button or disable it
}
```

---

## 📱 Mobile Considerations

For mobile devices:

```tsx
// Detect mobile and show different button
const isMobile = /iPhone|iPad|Android/i.test(navigator.userAgent)

{isMobile ? (
  <Button onClick={() => window.location.href = receiptUrl}>
    📱 View Receipt
  </Button>
) : (
  <Button onClick={handlePrint}>
    🖨️ Print Receipt
  </Button>
)}
```

---

## 🚀 Next Steps

1. **Choose your approach** (Simple link, Auto-print, or Modal)
2. **Copy the code** to your project
3. **Add print CSS** to your styles
4. **Test with sample data**
5. **Deploy and verify** in production

**Estimated Time**:
- Option 1 (Link): 10 minutes
- Option 2 (Auto-print): 30 minutes
- Option 3 (Modal): 2 hours

---

## 📚 Additional Resources

- [Full Implementation Guide](RECEIPT_SYSTEM_IMPLEMENTATION.md)
- [Backend API Documentation](COMPREHENSIVE_API_DOCUMENTATION.md)
- [Wholesale/Retail Documentation](WHOLESALE_RETAIL_IMPLEMENTATION.md)

---

**Questions?** Check the full implementation guide or test the API endpoints directly in your browser!

