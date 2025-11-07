# AI Credits Payment Callback Troubleshooting

**Date**: November 7, 2025  
**Issue**: Users completing AI credits payment are not being redirected back properly  
**Status**: 🔍 INVESTIGATING

---

## Problem Statement

Subscription payments work fine with callback flow, but AI credits purchases have issues navigating back to the home page after payment verification.

## Investigation Findings

### 1. Backend Implementation ✅ CORRECT

The backend **IS** properly configured to send callback URLs to Paystack:

```python
# ai_features/views.py - purchase_credits()
callback_url = serializer.validated_data.get('callback_url')

if callback_url:
    paystack_callback_url = callback_url
else:
    # Default to frontend payment callback page
    paystack_callback_url = f'{settings.FRONTEND_URL}/payment/callback'

# Initialize Paystack transaction with frontend callback
paystack_response = PaystackService.initialize_transaction(
    email=request.user.email,
    amount=total_amount,
    reference=payment_reference,
    metadata={...},
    callback_url=paystack_callback_url  # ✅ Properly passed
)
```

### 2. PaystackService ✅ CORRECT

The Paystack service properly accepts and sends callback_url:

```python
# ai_features/services/paystack.py
@classmethod
def initialize_transaction(cls, email, amount, reference, metadata=None, callback_url=None):
    payload = {
        'email': email,
        'amount': amount_in_pesewas,
        'reference': reference,
        'currency': 'GHS',
    }
    
    if callback_url:
        payload['callback_url'] = callback_url  # ✅ Sent to Paystack
```

### 3. Test Results

**Test 1**: Purchase WITH callback_url parameter  
✅ Backend accepts callback_url  
✅ Paystack transaction initialized  
✅ Reference: AI-CREDIT-1762541677796-4b567fcc  

**Test 2**: Purchase WITHOUT callback_url (uses default)  
✅ Uses default: `http://localhost:5173/payment/callback`  
✅ Paystack transaction initialized  
✅ Reference: AI-CREDIT-1762541678403-77c0f716  

### 4. URL Comparison

| Flow | Callback URL | Status |
|------|-------------|--------|
| **Subscriptions** | `/app/subscription/payment/callback` | ✅ Working |
| **AI Credits** | `/payment/callback` | ❌ Not working |

**Key Difference**: Different frontend routes!

---

## Root Cause Analysis

### The Real Problem: Frontend Route Configuration

The issue is **NOT** with the backend - it's sending the correct callback URL to Paystack.

The problem is one or more of these:

#### Option 1: Missing Frontend Route ❌
The frontend doesn't have a route handler for `/payment/callback`

```tsx
// Frontend router might be missing this:
{
  path: '/payment/callback',
  element: <PaymentCallback />
}
```

#### Option 2: Wrong Route Path ❌
AI credits callback is using `/payment/callback` but should use `/app/subscription/payment/callback` (same as subscriptions)

#### Option 3: Route Not Handling AI Credits ❌
The payment callback component exists but only handles subscription payments, not AI credit payments

#### Option 4: Authentication Issue ❌
The callback page might not be preserving authentication when it loads

---

## Solutions

### Option A: Align AI Credits with Subscription Path (RECOMMENDED ✅)

**Pros:**
- Single callback handler for all payments
- Consistent user experience
- Less code duplication

**Cons:**
- Requires backend change

**Implementation:**

1. **Update Backend Default**:
```python
# ai_features/views.py
if callback_url:
    paystack_callback_url = callback_url
else:
    # Use SAME path as subscriptions
    paystack_callback_url = f'{settings.FRONTEND_URL}/app/subscription/payment/callback'
```

2. **Update Frontend Callback Handler**:
```tsx
// PaymentCallback component should handle both:
const searchParams = useSearchParams();
const reference = searchParams.get('reference') || searchParams.get('trxref');

// Determine payment type from reference prefix
const isAICredit = reference?.startsWith('AI-CREDIT');
const isSubscription = reference?.startsWith('SUB-');

if (isAICredit) {
  // Call AI credits verify endpoint
  await fetch(`/ai/api/credits/verify/?reference=${reference}`);
} else if (isSubscription) {
  // Call subscription verify endpoint
  await fetch(`/subscriptions/api/verify-payment/?reference=${reference}`);
}
```

### Option B: Create Separate AI Credits Route

**Pros:**
- Clear separation of concerns
- Each payment type has its own handler

**Cons:**
- Code duplication
- Two routes to maintain

**Implementation:**

1. **Keep Backend As-Is** (using `/payment/callback`)

2. **Add Frontend Route**:
```tsx
// Router config
{
  path: '/payment/callback',
  element: <AICreditsPaymentCallback />
}
```

3. **Create Component**:
```tsx
// AICreditsPaymentCallback.tsx
export function AICreditsPaymentCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  
  useEffect(() => {
    const verifyPayment = async () => {
      const reference = searchParams.get('reference');
      const token = localStorage.getItem('authToken');
      
      const response = await fetch(
        `/ai/api/credits/verify/?reference=${reference}`,
        {
          headers: {
            'Authorization': `Token ${token}`,
            'Content-Type': 'application/json'
          }
        }
      );
      
      const data = await response.json();
      
      if (data.status === 'success') {
        // Show success message
        toast.success(`${data.credits_added} credits added!`);
        // Redirect to AI credits page or dashboard
        navigate('/ai/credits');
      } else {
        toast.error('Payment verification failed');
        navigate('/ai/credits');
      }
    };
    
    verifyPayment();
  }, [searchParams, navigate]);
  
  return <LoadingSpinner message="Verifying payment..." />;
}
```

---

## Recommended Solution: Option A

**Why?** Because it's cleaner and more maintainable.

### Step-by-Step Implementation

#### Step 1: Update Backend Default Callback

```python
# File: ai_features/views.py
# Line: ~285 (in purchase_credits view)

# BEFORE:
if callback_url:
    paystack_callback_url = callback_url
else:
    # Default to frontend payment callback page
    paystack_callback_url = f'{settings.FRONTEND_URL}/payment/callback'

# AFTER:
if callback_url:
    paystack_callback_url = callback_url
else:
    # Use same callback as subscriptions for consistency
    paystack_callback_url = f'{settings.FRONTEND_URL}/app/subscription/payment/callback'
```

#### Step 2: Update Frontend Callback Handler

```tsx
// File: src/pages/payment/SubscriptionPaymentCallback.tsx (or similar)

const PaymentCallback = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState('loading');
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
      
      // Determine payment type from reference prefix
      const isAICredit = reference.startsWith('AI-CREDIT');
      const isSubscription = reference.startsWith('SUB-');
      
      try {
        let endpoint = '';
        let redirectPath = '';
        
        if (isAICredit) {
          endpoint = `/ai/api/credits/verify/?reference=${reference}`;
          redirectPath = '/ai/credits';
        } else if (isSubscription) {
          endpoint = `/subscriptions/api/verify-payment/?reference=${reference}`;
          redirectPath = '/app/subscriptions';
        } else {
          throw new Error('Unknown payment type');
        }
        
        const response = await fetch(endpoint, {
          headers: {
            'Authorization': `Token ${token}`,
            'Content-Type': 'application/json'
          }
        });
        
        const data = await response.json();
        
        if (data.status === 'success' || response.ok) {
          setStatus('success');
          
          if (isAICredit) {
            setMessage(`Payment successful! ${data.credits_added} credits added. New balance: ${data.new_balance}`);
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
    <div className="payment-callback">
      {status === 'loading' && <Spinner text="Verifying payment..." />}
      {status === 'success' && <SuccessMessage message={message} />}
      {status === 'error' && <ErrorMessage message={message} />}
    </div>
  );
};
```

#### Step 3: Update Frontend Purchase Call

```tsx
// When initiating AI credits purchase:
const response = await fetch('/ai/api/credits/purchase/', {
  method: 'POST',
  headers: {
    'Authorization': `Token ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    package: 'starter',
    payment_method: 'mobile_money',
    // Use subscription callback path
    callback_url: `${window.location.origin}/app/subscription/payment/callback`
  })
});
```

---

## Testing Checklist

After implementing the fix:

- [ ] Purchase AI credits package
- [ ] Complete payment on Paystack
- [ ] Verify redirect to `/app/subscription/payment/callback`
- [ ] Verify payment is verified automatically
- [ ] Verify credits are added to balance
- [ ] Verify success message is shown
- [ ] Verify redirect to AI credits page
- [ ] Test both WITH and WITHOUT custom callback_url
- [ ] Test subscription payment still works

---

## Additional Notes

### Why Subscriptions Work

Subscriptions work because:
1. Backend sends callback: `/app/subscription/payment/callback`
2. Frontend HAS this route configured
3. Component verifies payment and shows result

### Why AI Credits Don't Work

AI credits don't work because:
1. Backend sends callback: `/payment/callback`
2. Frontend might NOT have this route
3. OR route exists but doesn't handle AI credit verification
4. OR route doesn't preserve authentication properly

---

## Next Steps

1. **Confirm with user**: Which callback path does the frontend currently handle?
   - `/payment/callback` (generic)
   - `/app/subscription/payment/callback` (subscription-specific)
   - Neither (404)?

2. **Implement Solution A**: Align AI credits with subscription callback

3. **Test thoroughly**: Both payment types with shared callback

4. **Update documentation**: Mark as resolved

---

**Status**: Awaiting frontend route confirmation  
**Recommendation**: Implement Option A (unified callback)  
**Next Action**: Check frontend router configuration
