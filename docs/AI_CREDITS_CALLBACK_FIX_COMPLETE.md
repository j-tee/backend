# AI Credits Payment Callback Fix - COMPLETE ✅

**Date**: November 7, 2025  
**Status**: ✅ **BACKEND FIXED** - Frontend update required  
**Issue**: AI credits callback not working, subscription callback working fine  
**Solution**: Unified callback path for both payment types

---

## Summary

The backend has been updated so that **both AI credits and subscriptions now use the SAME callback URL path**. This allows the frontend to have a single payment callback handler that detects the payment type from the reference prefix.

### What Was Changed

**File**: `ai_features/views.py` (line ~285)

**BEFORE**:
```python
if callback_url:
    paystack_callback_url = callback_url
else:
    # Default to frontend payment callback page
    paystack_callback_url = f'{settings.FRONTEND_URL}/payment/callback'
```

**AFTER**:
```python
if callback_url:
    paystack_callback_url = callback_url
else:
    # Default to same callback as subscriptions for consistency
    # Frontend can detect payment type from reference prefix (AI-CREDIT-xxx vs SUB-xxx)
    paystack_callback_url = f'{settings.FRONTEND_URL}/app/subscription/payment/callback'
```

---

## How It Works

### Payment Flow

```
┌──────────────────────────────────────────────────────────────────┐
│  USER INITIATES PAYMENT                                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  AI Credits: POST /ai/api/credits/purchase/                     │
│  OR                                                              │
│  Subscription: POST /subscriptions/api/.../initialize_payment/  │
│                                                                  │
└───────────────────────┬──────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────────┐
│  BACKEND CONFIGURES PAYSTACK                                     │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ✅ Callback URL: /app/subscription/payment/callback             │
│  ✅ Reference: AI-CREDIT-xxx OR SUB-xxx                          │
│                                                                  │
└───────────────────────┬──────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────────┐
│  USER COMPLETES PAYMENT ON PAYSTACK                              │
└───────────────────────┬──────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────────┐
│  PAYSTACK REDIRECTS TO FRONTEND                                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  URL: /app/subscription/payment/callback?reference=xxx&trxref=xxx│
│                                                                  │
└───────────────────────┬──────────────────────────────────────────┘
                        │
                        ▼
┌──────────────────────────────────────────────────────────────────┐
│  FRONTEND PAYMENT CALLBACK PAGE                                  │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. Extract reference from URL                                   │
│  2. Detect payment type from prefix:                             │
│     - AI-CREDIT-xxx → AI credits                                 │
│     - SUB-xxx → Subscription                                     │
│  3. Call appropriate verification endpoint                       │
│  4. Show success/error message                                   │
│  5. Redirect to appropriate page                                 │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Frontend Implementation Required

### Current State
- ✅ Route exists: `/app/subscription/payment/callback`
- ✅ Handles subscription payments
- ❌ Does NOT handle AI credit payments

### Required Update

Update the existing `PaymentCallback` component to handle both payment types:

```tsx
// File: src/pages/payment/PaymentCallback.tsx (or similar)

import { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Spinner, SuccessMessage, ErrorMessage } from '@/components';

export default function PaymentCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('');
  
  useEffect(() => {
    const verifyPayment = async () => {
      // Get reference from URL
      const reference = searchParams.get('reference') || searchParams.get('trxref');
      
      if (!reference) {
        setStatus('error');
        setMessage('Invalid payment reference');
        return;
      }
      
      // Get auth token
      const token = localStorage.getItem('authToken');
      if (!token) {
        setStatus('error');
        setMessage('Authentication required');
        navigate('/login');
        return;
      }
      
      try {
        // ✅ NEW: Detect payment type from reference prefix
        const isAICredit = reference.startsWith('AI-CREDIT');
        const isSubscription = reference.startsWith('SUB-');
        
        let endpoint = '';
        let redirectPath = '';
        let successMessageTemplate = '';
        
        if (isAICredit) {
          // AI Credits verification
          endpoint = `/ai/api/credits/verify/?reference=${reference}`;
          redirectPath = '/ai/credits'; // or wherever you show AI credits
          successMessageTemplate = (data: any) => 
            `Payment successful! ${data.credits_added} credits added. New balance: ${data.new_balance}`;
        } else if (isSubscription) {
          // Subscription verification
          endpoint = `/subscriptions/api/verify-payment/?reference=${reference}`;
          redirectPath = '/app/subscriptions';
          successMessageTemplate = () => 'Subscription activated successfully!';
        } else {
          throw new Error('Unknown payment type');
        }
        
        // Call verification endpoint
        const response = await fetch(`${import.meta.env.VITE_API_BASE_URL}${endpoint}`, {
          method: 'GET',
          headers: {
            'Authorization': `Token ${token}`,
            'Content-Type': 'application/json'
          }
        });
        
        const data = await response.json();
        
        // Check if successful
        if (data.status === 'success' || response.ok) {
          setStatus('success');
          setMessage(successMessageTemplate(data));
          
          // Redirect after 3 seconds
          setTimeout(() => navigate(redirectPath), 3000);
        } else {
          setStatus('error');
          setMessage(data.message || 'Payment verification failed');
        }
      } catch (error) {
        console.error('Payment verification error:', error);
        setStatus('error');
        setMessage('Failed to verify payment. Please contact support.');
      }
    };
    
    verifyPayment();
  }, [searchParams, navigate]);
  
  return (
    <div className="payment-callback-container">
      {status === 'loading' && (
        <div className="loading">
          <Spinner />
          <p>Verifying your payment...</p>
        </div>
      )}
      
      {status === 'success' && (
        <div className="success">
          <SuccessIcon />
          <h2>Payment Successful!</h2>
          <p>{message}</p>
          <p>Redirecting...</p>
        </div>
      )}
      
      {status === 'error' && (
        <div className="error">
          <ErrorIcon />
          <h2>Payment Verification Failed</h2>
          <p>{message}</p>
          <button onClick={() => navigate('/dashboard')}>
            Go to Dashboard
          </button>
        </div>
      )}
    </div>
  );
}
```

### Key Changes

1. **Detect Payment Type**: Check if reference starts with `AI-CREDIT` or `SUB-`
2. **Route to Correct Endpoint**:
   - AI Credits: `/ai/api/credits/verify/`
   - Subscription: `/subscriptions/api/verify-payment/`
3. **Show Appropriate Message**:
   - AI Credits: "X credits added, new balance: Y"
   - Subscription: "Subscription activated"
4. **Redirect to Correct Page**:
   - AI Credits: `/ai/credits` (or dashboard)
   - Subscription: `/app/subscriptions`

---

## Testing

### Backend Testing ✅ COMPLETE

```bash
cd /home/teejay/Documents/Projects/pos/backend
python test_ai_callback_url.py
```

**Results**:
- ✅ AI credits WITHOUT callback_url uses: `/app/subscription/payment/callback`
- ✅ Subscriptions use: `/app/subscription/payment/callback`
- ✅ Both use the SAME path

### Frontend Testing Required

After implementing the frontend changes:

#### Test 1: AI Credits Purchase
1. Login to the application
2. Navigate to AI Credits page
3. Click "Buy Credits"
4. Select a package (e.g., Starter - GHS 30)
5. Complete payment on Paystack
6. **Verify**: Redirected to `/app/subscription/payment/callback`
7. **Verify**: "Verifying payment..." spinner shows
8. **Verify**: Success message: "Payment successful! 30 credits added. New balance: X"
9. **Verify**: Auto-redirects to AI credits page
10. **Verify**: New balance reflects added credits

#### Test 2: Subscription Purchase (Regression Test)
1. Login to the application
2. Navigate to Subscriptions page
3. Click "Subscribe" or "Upgrade"
4. Complete payment on Paystack
5. **Verify**: Still redirected to `/app/subscription/payment/callback`
6. **Verify**: Success message: "Subscription activated successfully!"
7. **Verify**: Auto-redirects to subscriptions page
8. **Verify**: Subscription status is active

#### Test 3: Error Handling
1. Initiate AI credits purchase
2. Close payment page before completing
3. Manually navigate to callback with invalid reference
4. **Verify**: Error message shown
5. **Verify**: Can navigate back to dashboard

---

## API Endpoints Reference

### AI Credits Purchase
```
POST /ai/api/credits/purchase/

Headers:
  Authorization: Token <user_token>
  Content-Type: application/json

Body:
{
  "package": "starter" | "value" | "premium",
  "payment_method": "mobile_money" | "card",
  "callback_url": "https://..." // Optional
}

Response:
{
  "authorization_url": "https://checkout.paystack.com/...",
  "reference": "AI-CREDIT-1762541799963-5119dfa7",
  "credits_to_add": 30.0,
  ...
}
```

### AI Credits Verification
```
GET /ai/api/credits/verify/?reference=AI-CREDIT-xxx

Headers:
  Authorization: Token <user_token>

Response (Success):
{
  "status": "success",
  "message": "Payment verified and credits added successfully",
  "reference": "AI-CREDIT-xxx",
  "credits_added": 30.0,
  "new_balance": 75.50
}

Response (Already Processed):
{
  "status": "success",
  "message": "Payment already processed",
  "reference": "AI-CREDIT-xxx",
  "credits_added": 30.0,
  "current_balance": 75.50
}

Response (Failed):
{
  "status": "failed",
  "message": "Payment was not successful",
  "reference": "AI-CREDIT-xxx"
}
```

---

## Benefits of This Solution

### 1. **Single Source of Truth** ✅
- One callback page handles all payment types
- No route duplication
- Easier to maintain

### 2. **Type Detection** ✅
- Reference prefix automatically identifies payment type
- `AI-CREDIT-xxx` → AI credits
- `SUB-xxx` → Subscription
- Extensible for future payment types

### 3. **Consistent UX** ✅
- Same loading/success/error flow
- Same visual design
- Predictable behavior

### 4. **Better Error Handling** ✅
- Single place to handle errors
- Unified logging
- Easier debugging

### 5. **Future-Proof** ✅
- Easy to add new payment types
- Just add new prefix detection
- No new routes needed

---

## Rollback Plan

If issues arise, you can quickly rollback by reverting the backend change:

```python
# File: ai_features/views.py
# Revert to:

if callback_url:
    paystack_callback_url = callback_url
else:
    paystack_callback_url = f'{settings.FRONTEND_URL}/payment/callback'
```

Then create a new frontend route for `/payment/callback` specifically for AI credits.

---

## Summary

### ✅ Completed (Backend)
- [x] Updated default callback URL to match subscriptions
- [x] Tested with multiple scenarios
- [x] Verified references are prefixed correctly
- [x] Documented changes

### ⏳ Required (Frontend)
- [ ] Update `PaymentCallback` component to detect payment type
- [ ] Add logic to route to correct verification endpoint
- [ ] Test AI credits purchase flow
- [ ] Test subscription purchase flow (regression)
- [ ] Deploy to production

### 📋 Deployment Checklist
1. Deploy backend changes (already done via auto-reload)
2. Update frontend `PaymentCallback` component
3. Test locally with both payment types
4. Deploy frontend to staging
5. Test in staging environment
6. Deploy to production
7. Monitor for errors
8. Verify metrics (conversion rates, error rates)

---

## Support & Troubleshooting

### If Frontend Still Doesn't Redirect Properly

1. **Check Router Configuration**:
   ```tsx
   // Ensure this route exists:
   {
     path: '/app/subscription/payment/callback',
     element: <PaymentCallback />
   }
   ```

2. **Check FRONTEND_URL in Backend**:
   ```bash
   # In backend .env
   FRONTEND_URL=http://localhost:5173
   ```

3. **Check Browser Console**:
   - Look for 404 errors
   - Check for authentication issues
   - Verify API calls are being made

4. **Check Network Tab**:
   - Verify callback URL in Paystack response
   - Check if verification endpoint is called
   - Look at response status codes

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| 404 on callback | Route not configured | Add route to router |
| 403 on verify | Auth token missing | Check localStorage for token |
| Payment not verified | Wrong endpoint | Check payment type detection |
| Infinite loading | API error | Check network tab, backend logs |

---

## Contact

For questions or issues:
- Check backend logs: `/home/teejay/Documents/Projects/pos/backend/logs/`
- Review this document: `docs/AI_CREDITS_CALLBACK_FIX_COMPLETE.md`
- Test script: `test_ai_callback_url.py`

---

**Status**: ✅ Backend Complete - Awaiting Frontend Update  
**Last Updated**: November 7, 2025  
**Next Action**: Update frontend PaymentCallback component
