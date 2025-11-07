# Paystack Payment Integration Guide

**Status:** ✅ Implemented  
**Date:** November 7, 2025  
**For:** AI Credits Purchase

---

## 🎯 Overview

The AI Credits purchase system now uses **Paystack** for secure payment processing. When users click "Buy Credits", they are redirected to Paystack's secure checkout page to complete payment.

---

## 🔧 Backend Setup

### 1. Get Paystack API Keys

1. Go to [Paystack Dashboard](https://dashboard.paystack.com/)
2. Navigate to **Settings** → **API Keys & Webhooks**
3. Copy your **Secret Key** and **Public Key**

**For Testing:**
- Use **Test Mode** keys (starts with `sk_test_...`)
- Test cards: `4084084084084081` (success), `5060666666666666666` (declined)

**For Production:**
- Use **Live Mode** keys (starts with `sk_live_...`)
- Enable your live mode after verifying your business

### 2. Configure Environment Variables

**For Development** - Add to `.env.development`:

```env
# Paystack Configuration (Test Mode)
PAYSTACK_SECRET_KEY=sk_test_your_secret_key_here
PAYSTACK_PUBLIC_KEY=pk_test_your_public_key_here
```

**For Production** - Add to `.env.production`:

```env
# Paystack Configuration (Live Mode)
PAYSTACK_SECRET_KEY=sk_live_your_secret_key_here
PAYSTACK_PUBLIC_KEY=pk_live_your_public_key_here
```

### 3. Install Dependencies

Already included in `requirements.txt`:
```bash
requests==2.31.0  # For Paystack API calls
```

### 4. Configure Webhook

In Paystack Dashboard:
1. Go to **Settings** → **Webhooks**
2. Add webhook URL: `https://yourdomain.com/ai/api/webhooks/paystack/`
3. Copy the webhook secret (optional, for extra security)

---

## 🔄 Payment Flow

### Step 1: Initialize Payment

**Frontend calls:**
```javascript
POST /ai/api/credits/purchase/
{
  "package": "value",
  "payment_method": "mobile_money"
}
```

**Backend responds with:**
```json
{
  "authorization_url": "https://checkout.paystack.com/xxx",
  "access_code": "xxx",
  "reference": "AI-CREDIT-1699357200-abc123",
  "amount": 80.00,
  "credits_to_add": 100.0
}
```

### Step 2: Redirect to Paystack

Frontend redirects user to `authorization_url`:
```javascript
window.location.href = response.authorization_url;
```

### Step 3: User Completes Payment

User pays using:
- Mobile Money (MTN, Vodafone, AirtelTigo)
- Bank Card (Visa, Mastercard)
- Bank Transfer
- USSD

### Step 4: Paystack Redirects Back

After payment, Paystack redirects to:
```
https://yourdomain.com/ai/api/credits/verify/?reference=AI-CREDIT-xxx
```

### Step 5: Verify Payment

Backend verifies with Paystack and credits account:
```json
{
  "status": "success",
  "message": "Payment verified and credits added successfully",
  "reference": "AI-CREDIT-1699357200-abc123",
  "credits_added": 100.0,
  "new_balance": 145.5
}
```

### Step 6: Webhook Notification (Optional)

Paystack also sends webhook notification:
```
POST /ai/api/webhooks/paystack/
X-Paystack-Signature: xxx

{
  "event": "charge.success",
  "data": {
    "reference": "AI-CREDIT-xxx",
    "amount": 8000,  // in pesewas
    "status": "success"
  }
}
```

---

## 📱 Frontend Implementation

### React Example

```jsx
import React, { useState } from 'react';

const PurchaseCredits = () => {
  const [loading, setLoading] = useState(false);

  const handlePurchase = async (packageType) => {
    setLoading(true);
    
    try {
      // 1. Initialize payment
      const response = await fetch('/ai/api/credits/purchase/', {
        method: 'POST',
        headers: {
          'Authorization': `Token ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          package: packageType,
          payment_method: 'mobile_money'
        })
      });

      const data = await response.json();

      if (!response.ok) {
        alert(`Error: ${data.error || 'Purchase failed'}`);
        return;
      }

      // 2. Redirect to Paystack
      window.location.href = data.authorization_url;

      // User will be redirected back after payment
      // Handle verification on the return page
    } catch (error) {
      console.error('Purchase failed:', error);
      alert('Failed to initialize payment. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="purchase-options">
      <button 
        onClick={() => handlePurchase('starter')}
        disabled={loading}
      >
        {loading ? 'Processing...' : 'Buy Starter Pack (GHS 30)'}
      </button>

      <button 
        onClick={() => handlePurchase('value')}
        disabled={loading}
      >
        {loading ? 'Processing...' : 'Buy Value Pack (GHS 80)'}
      </button>

      <button 
        onClick={() => handlePurchase('premium')}
        disabled={loading}
      >
        {loading ? 'Processing...' : 'Buy Premium Pack (GHS 180)'}
      </button>
    </div>
  );
};

export default PurchaseCredits;
```

### Verification Page

Create a page to handle Paystack redirect:

```jsx
// pages/PaymentCallback.jsx
import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';

const PaymentCallback = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState('verifying');
  const [message, setMessage] = useState('Verifying your payment...');

  useEffect(() => {
    const reference = searchParams.get('reference');
    
    if (!reference) {
      setStatus('error');
      setMessage('No payment reference found');
      return;
    }

    // Verify payment
    fetch(`/ai/api/credits/verify/?reference=${reference}`, {
      headers: {
        'Authorization': `Token ${localStorage.getItem('token')}`,
      }
    })
    .then(res => res.json())
    .then(data => {
      if (data.status === 'success') {
        setStatus('success');
        setMessage(`Success! ${data.credits_added} credits added to your account.`);
        
        // Redirect to dashboard after 3 seconds
        setTimeout(() => {
          navigate('/dashboard');
        }, 3000);
      } else {
        setStatus('error');
        setMessage(data.message || 'Payment verification failed');
      }
    })
    .catch(error => {
      setStatus('error');
      setMessage('Failed to verify payment. Please contact support.');
    });
  }, [searchParams, navigate]);

  return (
    <div className="payment-callback">
      {status === 'verifying' && (
        <div className="spinner">
          <div className="loading-icon"></div>
          <p>{message}</p>
        </div>
      )}

      {status === 'success' && (
        <div className="success">
          <div className="checkmark">✓</div>
          <h2>Payment Successful!</h2>
          <p>{message}</p>
          <p>Redirecting to dashboard...</p>
        </div>
      )}

      {status === 'error' && (
        <div className="error">
          <div className="error-icon">✗</div>
          <h2>Payment Failed</h2>
          <p>{message}</p>
          <button onClick={() => navigate('/credits')}>
            Try Again
          </button>
        </div>
      )}
    </div>
  );
};

export default PaymentCallback;
```

### Add Route

```jsx
// App.jsx
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import PaymentCallback from './pages/PaymentCallback';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* ... other routes ... */}
        <Route path="/payment/callback" element={<PaymentCallback />} />
      </Routes>
    </BrowserRouter>
  );
}
```

---

## 🧪 Testing

### Test with Paystack Test Cards

**Successful Payment:**
```
Card Number: 4084084084084081
CVV: 408
Expiry: Any future date
PIN: 0000
OTP: 123456
```

**Declined Payment:**
```
Card Number: 5060666666666666666
CVV: 123
Expiry: Any future date
```

### Test Flow

1. **Start Purchase:**
```bash
curl -X POST http://localhost:8000/ai/api/credits/purchase/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"package": "starter", "payment_method": "card"}'
```

2. **Visit the authorization_url** returned in response

3. **Complete test payment** using test card

4. **Verify payment:**
```bash
curl http://localhost:8000/ai/api/credits/verify/?reference=AI-CREDIT-xxx \
  -H "Authorization: Token YOUR_TOKEN"
```

---

## 🔐 Security Features

### 1. Webhook Signature Verification
```python
# Backend automatically verifies webhook signature
PaystackService.verify_webhook_signature(request.body, signature)
```

### 2. Payment Reference Uniqueness
```python
# Each payment gets unique reference with timestamp + random string
reference = f"AI-CREDIT-{timestamp}-{random_hex}"
```

### 3. Double-Processing Prevention
```python
# Backend checks if payment already processed
if purchase.payment_status == 'completed':
    return "already_processed"
```

### 4. Amount Verification
```python
# Backend verifies amount from Paystack matches expected amount
amount_paid_ghs = Decimal(str(payment_data['amount'])) / Decimal('100')
```

---

## 📊 Database Schema

### AICreditPurchase Model

```python
class AICreditPurchase(models.Model):
    business = ForeignKey(Business)
    user = ForeignKey(User)
    amount_paid = DecimalField()  # GHS amount
    credits_purchased = DecimalField()
    bonus_credits = DecimalField()
    payment_reference = CharField(unique=True)  # Paystack reference
    payment_method = CharField()  # 'mobile_money', 'card'
    payment_status = CharField()  # 'pending', 'completed', 'failed'
    completed_at = DateTimeField(null=True)
    created_at = DateTimeField(auto_now_add=True)
```

**Payment Status Flow:**
```
pending → completed (after successful payment)
pending → failed (if payment fails)
```

---

## 🚨 Error Handling

### Common Errors

**1. Paystack API Key Not Configured**
```json
{
  "error": "payment_initialization_failed",
  "message": "PAYSTACK_SECRET_KEY not configured in settings"
}
```
**Solution:** Add `PAYSTACK_SECRET_KEY` to `.env`

**2. Network Error**
```json
{
  "error": "payment_initialization_failed",
  "message": "Failed to initialize payment: Connection timeout"
}
```
**Solution:** Check internet connection, Paystack API status

**3. Invalid Reference**
```json
{
  "error": "Purchase record not found"
}
```
**Solution:** Payment reference doesn't exist in database

**4. Payment Already Processed**
```json
{
  "status": "success",
  "message": "Payment already processed"
}
```
**Solution:** This is normal - credits already added

---

## 📈 Monitoring

### Check Payment Status

```bash
# List recent purchases
curl http://localhost:8000/ai/api/transactions/ \
  -H "Authorization: Token YOUR_TOKEN"

# Check Paystack dashboard
https://dashboard.paystack.com/transactions
```

### Webhook Logs

Monitor webhook deliveries in Paystack Dashboard:
- **Settings** → **Webhooks** → **View Logs**

---

## 🔄 Production Deployment

### Checklist

- [ ] Get live Paystack API keys
- [ ] Add to `.env.production`:
  ```env
  PAYSTACK_SECRET_KEY=sk_live_xxx
  PAYSTACK_PUBLIC_KEY=pk_live_xxx
  ```
- [ ] Configure webhook URL in Paystack Dashboard
- [ ] Test with real GHS 1.00 transaction
- [ ] Monitor first few transactions
- [ ] Enable webhook signature verification

---

## 💡 Features

✅ **Secure Payment Processing**  
✅ **Multiple Payment Methods** (Card, Mobile Money, Bank Transfer)  
✅ **Automatic Credit Addition**  
✅ **Webhook Support** (real-time notifications)  
✅ **Double-Processing Prevention**  
✅ **Test Mode** (for development)  
✅ **GHS Currency Support**  
✅ **Mobile-Friendly Checkout**

---

## 📞 Support

**Paystack Issues:**
- Email: support@paystack.com
- Docs: https://paystack.com/docs/api/

**Backend Issues:**
- Check Django logs
- Verify environment variables
- Test webhook signature

---

**Status:** Production Ready ✅  
**Last Updated:** November 7, 2025  
**Version:** 1.0.0
