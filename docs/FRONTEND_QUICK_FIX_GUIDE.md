# Frontend Quick Fix Guide - AI Credits Callback

**Task**: Update payment callback to handle both subscriptions AND AI credits  
**Estimated Time**: 15-20 minutes  
**Difficulty**: Easy

---

## The Problem

Your payment callback page currently only handles **subscriptions**. When users purchase **AI credits**, they complete the payment but the callback doesn't verify the AI credits purchase.

## The Solution

Update your existing `PaymentCallback` component to detect the payment type and call the appropriate verification endpoint.

---

## Step-by-Step Guide

### Step 1: Find Your PaymentCallback Component

It's probably in one of these locations:
- `src/pages/payment/PaymentCallback.tsx`
- `src/pages/subscription/PaymentCallback.tsx`
- `src/components/payment/PaymentCallback.tsx`

### Step 2: Update the useEffect Hook

**BEFORE** (only handles subscriptions):
```tsx
useEffect(() => {
  const verifyPayment = async () => {
    const reference = searchParams.get('reference');
    
    // Only calls subscription endpoint
    const response = await fetch('/subscriptions/api/verify-payment/...');
  };
}, []);
```

**AFTER** (handles both):
```tsx
useEffect(() => {
  const verifyPayment = async () => {
    const reference = searchParams.get('reference') || searchParams.get('trxref');
    const token = localStorage.getItem('authToken');
    
    // ✅ NEW: Detect payment type
    const isAICredit = reference?.startsWith('AI-CREDIT');
    const isSubscription = reference?.startsWith('SUB-');
    
    let endpoint = '';
    let redirectPath = '';
    
    if (isAICredit) {
      endpoint = `/ai/api/credits/verify/?reference=${reference}`;
      redirectPath = '/ai/credits'; // Change to your AI credits page
    } else if (isSubscription) {
      endpoint = `/subscriptions/api/verify-payment/?reference=${reference}`;
      redirectPath = '/app/subscriptions';
    }
    
    const response = await fetch(endpoint, {
      headers: {
        'Authorization': `Token ${token}`
      }
    });
    
    const data = await response.json();
    
    if (data.status === 'success') {
      // Show success message
      setTimeout(() => navigate(redirectPath), 3000);
    }
  };
  
  verifyPayment();
}, [searchParams, navigate]);
```

### Step 3: Update Success Message

**BEFORE**:
```tsx
<p>Subscription activated successfully!</p>
```

**AFTER**:
```tsx
{isAICredit && (
  <p>Payment successful! {data.credits_added} credits added.</p>
)}
{isSubscription && (
  <p>Subscription activated successfully!</p>
)}
```

### Step 4: Test

1. **Test AI Credits**:
   - Buy AI credits
   - Complete payment
   - Should redirect to callback
   - Should show "X credits added"
   - Should redirect to AI credits page

2. **Test Subscription** (regression):
   - Subscribe/upgrade
   - Complete payment
   - Should still work as before

---

## Full Component Example

Here's a complete, working example:

```tsx
import { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';

export default function PaymentCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('');
  
  useEffect(() => {
    const verifyPayment = async () => {
      const reference = searchParams.get('reference') || searchParams.get('trxref');
      
      if (!reference) {
        setStatus('error');
        setMessage('Invalid payment reference');
        return;
      }
      
      const token = localStorage.getItem('authToken');
      if (!token) {
        setStatus('error');
        setMessage('Authentication required');
        return;
      }
      
      try {
        // Detect payment type from reference prefix
        const isAICredit = reference.startsWith('AI-CREDIT');
        const isSubscription = reference.startsWith('SUB-');
        
        let endpoint = '';
        let redirectPath = '/dashboard';
        
        if (isAICredit) {
          endpoint = `/ai/api/credits/verify/?reference=${reference}`;
          redirectPath = '/ai/credits';
        } else if (isSubscription) {
          endpoint = `/subscriptions/api/verify-payment/?reference=${reference}`;
          redirectPath = '/app/subscriptions';
        } else {
          throw new Error('Unknown payment type');
        }
        
        const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
        const response = await fetch(`${API_BASE}${endpoint}`, {
          headers: {
            'Authorization': `Token ${token}`,
            'Content-Type': 'application/json'
          }
        });
        
        const data = await response.json();
        
        if (data.status === 'success' || response.ok) {
          setStatus('success');
          
          if (isAICredit) {
            setMessage(`${data.credits_added} credits added! New balance: ${data.new_balance}`);
          } else {
            setMessage('Subscription activated successfully!');
          }
          
          setTimeout(() => navigate(redirectPath), 3000);
        } else {
          setStatus('error');
          setMessage(data.message || 'Payment verification failed');
        }
      } catch (error) {
        setStatus('error');
        setMessage('Failed to verify payment. Please contact support.');
      }
    };
    
    verifyPayment();
  }, [searchParams, navigate]);
  
  return (
    <div className="min-h-screen flex items-center justify-center">
      {status === 'loading' && (
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-lg text-gray-600">Verifying your payment...</p>
        </div>
      )}
      
      {status === 'success' && (
        <div className="text-center">
          <div className="text-green-500 text-6xl mb-4">✓</div>
          <h2 className="text-2xl font-bold mb-2">Payment Successful!</h2>
          <p className="text-gray-600 mb-4">{message}</p>
          <p className="text-sm text-gray-500">Redirecting...</p>
        </div>
      )}
      
      {status === 'error' && (
        <div className="text-center">
          <div className="text-red-500 text-6xl mb-4">✗</div>
          <h2 className="text-2xl font-bold mb-2">Payment Verification Failed</h2>
          <p className="text-gray-600 mb-4">{message}</p>
          <button
            onClick={() => navigate('/dashboard')}
            className="bg-blue-600 text-white px-6 py-2 rounded hover:bg-blue-700"
          >
            Go to Dashboard
          </button>
        </div>
      )}
    </div>
  );
}
```

---

## Key Points

1. **Payment Type Detection**: Use reference prefix
   - `AI-CREDIT-xxx` = AI credits
   - `SUB-xxx` = Subscription

2. **Different Endpoints**:
   - AI credits: `/ai/api/credits/verify/`
   - Subscription: `/subscriptions/api/verify-payment/`

3. **Different Redirects**:
   - AI credits: `/ai/credits` (or your AI page)
   - Subscription: `/app/subscriptions`

4. **Auth Token**: Get from `localStorage.getItem('authToken')`

---

## Testing Commands

```bash
# Backend is already updated and running
# Just update your frontend component and test:

# 1. Start your frontend dev server
npm run dev

# 2. Login to the app
# 3. Try purchasing AI credits
# 4. Complete payment on Paystack
# 5. Verify you're redirected back and credits are added
```

---

## What Changed on the Backend?

The backend now sends both payment types to the **same callback URL**:
- Old: AI credits → `/payment/callback`
- Old: Subscription → `/app/subscription/payment/callback`
- **New: Both → `/app/subscription/payment/callback`** ✅

This means your **existing route** now needs to handle both types!

---

## Need Help?

If you get stuck:

1. **Check the reference in the URL**:
   - Does it start with `AI-CREDIT-`? 
   - Or `SUB-`?

2. **Check your API endpoint**:
   - Is it being called?
   - What's the response?

3. **Check authentication**:
   - Is the token in localStorage?
   - Is it being sent in headers?

4. **Check the console**:
   - Any errors?
   - Network tab showing API calls?

---

## That's It!

One component change, and both payment types will work! 🎉

**Estimated time**: 15-20 minutes  
**Difficulty**: Easy  
**Impact**: High - fixes broken AI credits purchase flow
