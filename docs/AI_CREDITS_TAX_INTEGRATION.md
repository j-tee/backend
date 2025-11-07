# AI Credits Purchase - Tax Integration Complete

## ✅ Implementation Summary

The AI credit purchase system now includes **full tax calculation and Paystack payment integration**, matching the subscription system's approach.

---

## 🔄 Complete Payment Flow

```
1. User selects package (Starter/Value/Premium)
   ↓
2. Backend calculates:
   - Base amount (e.g., GHS 80.00)
   - VAT (3%)
   - NHIL (2.5%)
   - GETFund (2.5%)
   - COVID-19 Levy (1%)
   = Total with taxes (e.g., GHS 87.20)
   ↓
3. Backend generates invoice with full breakdown
   ↓
4. Backend initializes Paystack transaction
   ↓
5. Backend returns authorization_url + invoice
   ↓
6. Frontend redirects user to Paystack checkout
   ↓
7. User completes payment (mobile money/card)
   ↓
8. Paystack redirects to verification endpoint
   ↓
9. Backend verifies payment with Paystack API
   ↓
10. Backend credits AI credits to business account
   ↓
11. User sees success message + new balance
```

---

## 📊 Tax Calculation

### Active Taxes (Ghana):
- **VAT**: 3.00%
- **NHIL**: 2.50%
- **GETFund Levy**: 2.50%
- **COVID-19 Health Recovery Levy**: 1.00%
- **Total Tax Rate**: 9.00%

### Example Calculation (Value Pack):
```
Base Amount:     GHS 80.00
VAT (3%):        GHS  2.40
NHIL (2.5%):     GHS  2.00
GETFund (2.5%):  GHS  2.00
COVID-19 (1%):   GHS  0.80
─────────────────────────
Total Tax:       GHS  7.20
Total Amount:    GHS 87.20

Credits: 100 (80 + 20 bonus)
```

---

## 🔌 API Endpoint

### POST `/ai/api/credits/purchase/`

**Request:**
```json
{
  "package": "value",
  "payment_method": "mobile_money"
}
```

**Response (200 OK):**
```json
{
  "authorization_url": "https://checkout.paystack.com/xxx",
  "access_code": "xxx",
  "reference": "AI-CREDIT-1699357200-abc123",
  "invoice": {
    "base_amount": 80.00,
    "taxes": [
      {
        "name": "VAT",
        "code": "VAT_GH",
        "rate": 3.0,
        "amount": 2.40,
        "applies_to": "SUBTOTAL"
      },
      {
        "name": "NHIL",
        "code": "NHIL_GH",
        "rate": 2.5,
        "amount": 2.00,
        "applies_to": "SUBTOTAL"
      },
      {
        "name": "GETFund Levy",
        "code": "GETFUND_GH",
        "rate": 2.5,
        "amount": 2.00,
        "applies_to": "SUBTOTAL"
      },
      {
        "name": "COVID-19 Health Recovery Levy",
        "code": "COVID19_GH",
        "rate": 1.0,
        "amount": 0.80,
        "applies_to": "SUBTOTAL"
      }
    ],
    "total_tax": 7.20,
    "total_amount": 87.20
  },
  "credits_to_add": 100.0,
  "package": "value"
}
```

**Error Response (400 - Invalid Email):**
```json
{
  "error": "invalid_email",
  "message": "A valid email address is required for payment processing. Please update your profile."
}
```

---

## 📦 Credit Packages (with taxes)

| Package | Base Price | Total Price* | Credits | Bonus | Total Credits | Value |
|---------|-----------|-------------|---------|-------|---------------|-------|
| Starter | GHS 30.00 | GHS 32.70 | 30 | 0 | 30 | Standard |
| Value | GHS 80.00 | GHS 87.20 | 80 | 20 | 100 | +25% bonus |
| Premium | GHS 180.00 | GHS 196.20 | 180 | 70 | 250 | +39% bonus |

*Total includes 9% Ghana taxes (VAT + NHIL + GETFund + COVID-19 levy)

---

## 🔐 Security & Validation

### User Email Validation:
- ✅ Checks if user has valid email address
- ✅ Rejects "AnonymousUser" or invalid emails
- ✅ Returns clear error message to update profile

### Payment Verification:
- ✅ Verifies with Paystack API before crediting
- ✅ Checks payment amount matches expected total
- ✅ Prevents double-processing of same payment
- ✅ Stores gateway response for audit trail

### Data Integrity:
- ✅ Creates pending purchase record before payment
- ✅ Updates status to 'completed' only after verification
- ✅ Stores tax breakdown in gateway_response field
- ✅ Links to business and user for tracking

---

## 💾 Database Schema

### AICreditPurchase Model:
```python
{
    "business_id": "uuid",
    "user_id": "uuid",
    "amount_paid": 87.20,        # Total including taxes
    "credits_purchased": 80.00,
    "bonus_credits": 20.00,
    "payment_reference": "AI-CREDIT-xxx",
    "payment_method": "mobile_money",
    "payment_status": "pending" | "completed" | "failed",
    "gateway_response": {
        "base_amount": "80.00",
        "tax_breakdown": [...],
        "total_tax": "7.20",
        "total_amount": "87.20"
    }
}
```

---

## 🎨 Frontend Integration

### 1. Show Invoice Before Payment

```jsx
const handlePurchase = async (packageType) => {
  const response = await fetch('/ai/api/credits/purchase/', {
    method: 'POST',
    headers: {
      'Authorization': `Token ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      package: packageType,
      payment_method: 'mobile_money'
    })
  });
  
  const data = await response.json();
  
  if (response.ok) {
    // Show invoice modal
    showInvoice({
      baseAmount: data.invoice.base_amount,
      taxes: data.invoice.taxes,
      totalTax: data.invoice.total_tax,
      totalAmount: data.invoice.total_amount,
      credits: data.credits_to_add
    });
    
    // Then redirect to Paystack
    window.location.href = data.authorization_url;
  } else if (data.error === 'invalid_email') {
    // Prompt user to update email
    showUpdateEmailPrompt(data.message);
  }
};
```

### 2. Display Invoice Breakdown

```jsx
const InvoiceModal = ({ invoice, onConfirm }) => {
  return (
    <div className="invoice-modal">
      <h3>Payment Invoice</h3>
      
      <div className="invoice-details">
        <div className="line-item">
          <span>Base Amount:</span>
          <span>GHS {invoice.baseAmount.toFixed(2)}</span>
        </div>
        
        <div className="taxes-section">
          <h4>Taxes:</h4>
          {invoice.taxes.map(tax => (
            <div key={tax.code} className="tax-line">
              <span>{tax.name} ({tax.rate}%):</span>
              <span>GHS {tax.amount.toFixed(2)}</span>
            </div>
          ))}
        </div>
        
        <div className="line-item subtotal">
          <span>Total Tax:</span>
          <span>GHS {invoice.totalTax.toFixed(2)}</span>
        </div>
        
        <div className="line-item total">
          <span>Total Amount:</span>
          <span>GHS {invoice.totalAmount.toFixed(2)}</span>
        </div>
        
        <div className="credits-info">
          <strong>You will receive: {invoice.credits} AI Credits</strong>
        </div>
      </div>
      
      <button onClick={onConfirm}>Proceed to Payment</button>
    </div>
  );
};
```

---

## ✅ Testing Checklist

- [x] Tax configuration exists in database
- [x] Tax calculation works correctly
- [x] Invoice breakdown generated properly
- [x] Email validation prevents invalid payments
- [x] Paystack integration works with total amount
- [x] Purchase record created with pending status
- [ ] **TODO:** Test complete payment flow with test card
- [ ] **TODO:** Verify credits credited after payment
- [ ] **TODO:** Test webhook for redundant verification
- [ ] **TODO:** Frontend displays invoice before redirect

---

## 🧪 Test Payment

### Test Card Details:
- **Card**: 4084084084084081
- **CVV**: 408
- **PIN**: 0000
- **OTP**: 123456
- **Expiry**: Any future date

### Test Flow:
1. User with valid email selects "Value Pack"
2. Backend calculates: GHS 80.00 + GHS 7.20 tax = GHS 87.20
3. Backend returns invoice + Paystack URL
4. Frontend shows invoice modal
5. User clicks "Proceed to Payment"
6. Redirects to Paystack checkout
7. User enters test card details
8. Payment succeeds
9. Paystack redirects to `/ai/api/credits/verify/?reference=xxx`
10. Backend verifies payment (GHS 87.20)
11. Backend credits 100 credits to account
12. User sees success message

---

## 📝 Key Changes Made

### File: `ai_features/views.py`
- ✅ Added tax calculation using TaxConfiguration model
- ✅ Added invoice generation with full breakdown
- ✅ Added user email validation
- ✅ Updated Paystack amount to include taxes
- ✅ Store tax breakdown in gateway_response field
- ✅ Return invoice in API response

### Tax Source:
- Uses existing `TaxConfiguration` model from subscriptions
- Filters by `is_active=True` and `applies_to_subscriptions=True`
- Respects `effective_from` and `effective_until` dates
- Applies taxes in `calculation_order`

### Response Changes:
**Before:**
```json
{
  "authorization_url": "...",
  "amount": 80.00,
  "credits_to_add": 100.0
}
```

**After:**
```json
{
  "authorization_url": "...",
  "invoice": {
    "base_amount": 80.00,
    "taxes": [...],
    "total_tax": 7.20,
    "total_amount": 87.20
  },
  "credits_to_add": 100.0
}
```

---

## 🎯 Benefits

1. ✅ **Compliance**: Properly calculates and collects Ghana taxes
2. ✅ **Transparency**: Users see exactly what they're paying for
3. ✅ **Consistency**: Uses same tax system as subscriptions
4. ✅ **Accuracy**: Tax rates managed centrally in database
5. ✅ **Audit Trail**: All tax details stored in purchase records
6. ✅ **Flexibility**: Tax rates can be updated without code changes

---

## 🚀 Production Deployment

### Environment Variables Required:
```env
# .env.production
PAYSTACK_SECRET_KEY=sk_live_xxxxxx
PAYSTACK_PUBLIC_KEY=pk_live_xxxxxx
OPENAI_API_KEY=sk-xxxxxx
```

### Pre-Launch Checklist:
- [ ] Live Paystack keys configured
- [ ] Tax rates verified for Ghana
- [ ] Email validation working
- [ ] Invoice display tested
- [ ] Payment verification tested
- [ ] Webhook endpoint configured
- [ ] Error logging enabled
- [ ] User email collection enforced

---

**Implementation Complete!** ✅

The AI credit purchase system now matches the subscription system's payment flow with full tax calculation, invoice generation, and Paystack integration.
