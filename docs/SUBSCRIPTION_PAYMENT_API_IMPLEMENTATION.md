# Subscription Payment API Implementation

## Overview
This document describes the three critical endpoints implemented for subscription payment processing. The frontend is already fully implemented and requires these endpoints to function.

## Implementation Date
**January 2025**

---

## Endpoints Implemented

### 1. Create Subscription
**Endpoint:** `POST /api/subscriptions/`

**Purpose:** Create a new subscription for a business with INACTIVE status.

**Request Body:**
```json
{
    "plan": "uuid-of-plan",
    "business": "uuid-of-business"
}
```

**Response (201 Created):**
```json
{
    "id": "subscription-uuid",
    "plan": {
        "id": "plan-uuid",
        "name": "Professional Plan",
        "description": "Full-featured plan for growing businesses",
        "price": "299.99",
        "currency": "GHS",
        "billing_cycle": "MONTHLY",
        "max_users": 10,
        "max_storefronts": 5,
        "max_products": 1000
    },
    "business": {
        "id": "business-uuid",
        "business_name": "Example Business"
    },
    "status": "INACTIVE",
    "payment_status": "UNPAID",
    "start_date": null,
    "end_date": null,
    "auto_renew": false,
    "created_at": "2025-01-23T10:00:00Z"
}
```

**Implementation Details:**
- Uses `ModelViewSet.create()` with `SubscriptionCreateSerializer`
- Automatically sets `status='INACTIVE'` and `payment_status='UNPAID'`
- Accessible via standard DRF create action
- Requires authentication (`IsAuthenticated` permission)
- Users can only create subscriptions for businesses they're members of

**Location:** `subscriptions/views.py` - `SubscriptionViewSet.create()`

---

### 2. Initialize Payment
**Endpoint:** `POST /api/subscriptions/{subscription_id}/initialize_payment/`

**Purpose:** Calculate pricing, create payment record, and initialize payment with gateway (Paystack/Stripe).

**Request Body:**
```json
{
    "gateway": "PAYSTACK",
    "callback_url": "https://pos.alphalogiquetechnologies.com/subscriptions/verify"
}
```

**Response (200 OK):**
```json
{
    "success": true,
    "payment_id": "payment-uuid",
    "authorization_url": "https://checkout.paystack.com/abc123xyz",
    "reference": "SUB-ABC123-1234567890",
    "amount": "347.97",
    "currency": "GHS",
    "pricing_breakdown": {
        "base_price": "299.99",
        "taxes": [
            {
                "name": "VAT (15%)",
                "rate": "15.00",
                "amount": "44.99"
            },
            {
                "name": "NHIL (2.5%)",
                "rate": "2.50",
                "amount": "7.50"
            }
        ],
        "service_charges": [
            {
                "name": "Payment Gateway Fee (1.5%)",
                "rate": "1.50",
                "amount": "4.50"
            }
        ],
        "total_tax": "52.49",
        "total_service_charges": "4.50",
        "storefront_count": 3
    }
}
```

**Implementation Details:**

1. **Validation:**
   - Checks user is member of business
   - Verifies subscription is not already paid
   - Validates gateway type (PAYSTACK/STRIPE)

2. **Storefront Counting:**
   ```python
   storefront_count = StoreFront.objects.filter(
       id__in=BusinessMembership.objects.filter(
           business=subscription.business
       ).values_list('storefront_id', flat=True)
   ).distinct().count()
   ```

3. **Pricing Calculation:**
   - Finds applicable `SubscriptionPricingTier` based on storefront count
   - Calculates base price: `tier.calculate_price(storefront_count)`
   - Calculates taxes from `TaxConfiguration` (VAT, NHIL, GETFund, COVID levy)
   - Calculates service charges from `ServiceCharge`
   - Computes total amount

4. **Payment Record Creation:**
   ```python
   payment = SubscriptionPayment.objects.create(
       subscription=subscription,
       amount=total_amount,
       currency=currency,
       base_amount=base_price,
       storefront_count=storefront_count,
       pricing_tier_snapshot={...},
       tax_breakdown=tax_breakdown,
       total_tax_amount=total_tax,
       service_charges_breakdown=service_charges_breakdown,
       total_service_charges=total_service_charges,
       transaction_reference=reference,
       status='PENDING'
   )
   ```

5. **Gateway Integration:**
   - **Paystack:** Calls `initialize_transaction()` with metadata:
     ```python
     metadata = {
         'subscription_id': str(subscription.id),
         'business_id': str(subscription.business.id),
         'business_name': subscription.business.business_name,
         'storefront_count': storefront_count,
         'app_name': 'pos'  # Critical for routing in shared account
     }
     ```
   - **Stripe:** Creates checkout session with line items

6. **Response:**
   - Returns `authorization_url` for frontend redirect
   - Includes `payment_id` for tracking
   - Provides `reference` for verification
   - Includes detailed pricing breakdown

**Error Responses:**
- `403 Forbidden`: User not member of business
- `400 Bad Request`: Already paid, missing gateway, invalid callback URL
- `404 Not Found`: No pricing tier found
- `500 Internal Server Error`: Gateway error, unexpected error

**Location:** `subscriptions/views.py` - `SubscriptionViewSet.initialize_payment()`

---

### 3. Verify Payment
**Endpoint:** `POST /api/subscriptions/{subscription_id}/verify_payment/`

**Purpose:** Verify payment with gateway and activate subscription if successful.

**Request Body:**
```json
{
    "gateway": "PAYSTACK",
    "reference": "SUB-ABC123-1234567890"
}
```

**Response (200 OK) - Success:**
```json
{
    "success": true,
    "message": "Payment verified successfully",
    "payment": {
        "id": "payment-uuid",
        "amount": "347.97",
        "status": "SUCCESSFUL",
        "payment_date": "2025-01-23T10:15:00Z"
    },
    "subscription": {
        "id": "subscription-uuid",
        "status": "ACTIVE",
        "payment_status": "PAID",
        "start_date": "2025-01-23",
        "end_date": "2025-02-23"
    }
}
```

**Response (200 OK) - Failure:**
```json
{
    "success": false,
    "message": "Payment verification failed",
    "reason": "Insufficient funds"
}
```

**Implementation Details:**

1. **Find Payment Record:**
   ```python
   payment = SubscriptionPayment.objects.filter(
       transaction_reference=reference,
       subscription=subscription
   ).first()
   ```

2. **Gateway Verification:**
   - **Paystack:** Calls `verify_transaction(reference)`
     - Checks `data['status'] == 'success'`
     - Extracts transaction ID and gateway reference
   - **Stripe:** Calls `retrieve_session(session_id)`
     - Checks `payment_status == 'paid'`

3. **Update Payment Record (if successful):**
   ```python
   payment.status = 'SUCCESSFUL'
   payment.payment_date = timezone.now()
   payment.transaction_id = gateway_transaction_id
   payment.gateway_reference = gateway_reference
   payment.gateway_response = verification_data
   payment.save()
   ```

4. **Activate Subscription (if successful):**
   ```python
   subscription.payment_status = 'PAID'
   subscription.status = 'ACTIVE'
   subscription.payment_method = 'PAYSTACK'
   subscription.start_date = timezone.now().date()
   subscription.end_date = start_date + timedelta(days=30)
   subscription.save()
   ```

5. **Update Business Status:**
   ```python
   subscription.business.subscription_status = 'ACTIVE'
   subscription.business.save()
   ```

6. **Update Payment Record (if failed):**
   ```python
   payment.status = 'FAILED'
   payment.failure_reason = gateway_error_message
   payment.gateway_response = verification_data
   payment.save()
   ```

**Error Responses:**
- `400 Bad Request`: Missing reference, unsupported gateway
- `404 Not Found`: Payment record not found
- `500 Internal Server Error`: Gateway error, unexpected error

**Location:** `subscriptions/views.py` - `SubscriptionViewSet.verify_payment()`

---

## Payment Gateway Configuration

### Paystack (Primary)
**Environment Variables:**
```bash
PAYSTACK_SECRET_KEY=sk_test_16b164b455153a23804423ec0198476b3c4ca206
PAYSTACK_PUBLIC_KEY=pk_test_5309f5af38555dbf7ef47287822ef2c6d3019b9d
```

**Test Cards:**
```
Mastercard (Success): 5531886652142950 | CVV: 564 | PIN: 3310
Verve (Success):     5060666666666666666 | CVV: 123 | OTP: 123456
Visa (Declined):     4084084084084081   | CVV: 408 | Expiry: 01/99
```

**API Base:** `https://api.paystack.co`

**Shared Account:** Uses `app_name='pos'` in metadata for multi-app routing

### Stripe (Alternative)
**Environment Variables:**
```bash
STRIPE_SECRET_KEY=your_stripe_secret_key
STRIPE_PUBLIC_KEY=your_stripe_public_key
```

---

## Pricing Models

### SubscriptionPricingTier
**Fields:**
- `name`: Tier name (e.g., "1-3 Storefronts")
- `min_storefronts`: Minimum storefront count
- `max_storefronts`: Maximum storefront count (null = unlimited)
- `base_price`: Base monthly price
- `price_per_storefront`: Additional price per storefront
- `is_active`: Active status

**Calculation:**
```python
price = base_price + (storefront_count * price_per_storefront)
```

### TaxConfiguration
**Ghana Taxes:**
- **VAT:** 15% (Value Added Tax)
- **NHIL:** 2.5% (National Health Insurance Levy)
- **GETFund:** 2.5% (Ghana Education Trust Fund)
- **COVID-19 Levy:** 1% (Health Recovery Levy)

### ServiceCharge
**Payment Gateway Fees:**
- **Paystack:** 1.5% + GHS 0.50
- **Stripe:** 2.9% + USD 0.30

---

## SubscriptionPayment Model

**Key Fields:**
```python
{
    "subscription": ForeignKey,
    "amount": Decimal,              # Total amount paid
    "currency": CharField,          # GHS/USD/EUR
    "base_amount": Decimal,         # Price before taxes/charges
    "storefront_count": Integer,    # Number of storefronts
    "pricing_tier_snapshot": JSON,  # Tier details at payment time
    "tax_breakdown": JSON,          # Array of taxes
    "total_tax_amount": Decimal,    # Sum of all taxes
    "service_charges_breakdown": JSON,  # Array of charges
    "total_service_charges": Decimal,   # Sum of all charges
    "transaction_reference": CharField, # SUB-XXX-TIMESTAMP
    "gateway_reference": CharField,     # Paystack/Stripe reference
    "transaction_id": CharField,        # Gateway transaction ID
    "status": CharField,            # PENDING/SUCCESSFUL/FAILED
    "payment_date": DateTime,       # When payment completed
    "failure_reason": TextField,    # Why payment failed
    "gateway_response": JSON,       # Full gateway response
    "status_history": JSON          # Auto-tracked status changes
}
```

**Status History Auto-Tracking:**
```python
def save(self, *args, **kwargs):
    if self.pk:
        old_status = SubscriptionPayment.objects.get(pk=self.pk).status
        if old_status != self.status:
            self.status_history.append({
                'from_status': old_status,
                'to_status': self.status,
                'changed_at': timezone.now().isoformat()
            })
    super().save(*args, **kwargs)
```

---

## Frontend Integration

### Environment Variables
```javascript
VITE_FRONTEND_URL=https://pos.alphalogiquetechnologies.com
VITE_API_BASE_URL=https://api.pos.alphalogiquetechnologies.com
```

### Complete Payment Flow

```javascript
// 1. Create Subscription
const createResponse = await fetch('/api/subscriptions/', {
    method: 'POST',
    headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({
        plan: selectedPlanId,
        business: businessId
    })
});
const subscription = await createResponse.json();

// 2. Initialize Payment
const initResponse = await fetch(`/api/subscriptions/${subscription.id}/initialize_payment/`, {
    method: 'POST',
    headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({
        gateway: 'PAYSTACK',
        callback_url: 'https://pos.alphalogiquetechnologies.com/subscriptions/verify'
    })
});
const paymentData = await initResponse.json();

// 3. Redirect to Payment Gateway
window.location.href = paymentData.authorization_url;

// 4. Handle Callback (after user completes payment)
// URL: https://pos.alphalogiquetechnologies.com/subscriptions/verify?reference=SUB-XXX-TIMESTAMP

const urlParams = new URLSearchParams(window.location.search);
const reference = urlParams.get('reference');

// 5. Verify Payment
const verifyResponse = await fetch(`/api/subscriptions/${subscription.id}/verify_payment/`, {
    method: 'POST',
    headers: {
        'Authorization': `Bearer ${accessToken}`,
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({
        gateway: 'PAYSTACK',
        reference: reference
    })
});
const verificationResult = await verifyResponse.json();

if (verificationResult.success) {
    // Payment successful - subscription is now ACTIVE
    console.log('Subscription activated:', verificationResult.subscription);
} else {
    // Payment failed
    console.error('Payment failed:', verificationResult.reason);
}
```

---

## Testing

### Test Payment Flow (Paystack)

1. **Create Test Subscription:**
   ```bash
   curl -X POST http://localhost:8000/api/subscriptions/ \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "plan": "PLAN_UUID",
       "business": "BUSINESS_UUID"
     }'
   ```

2. **Initialize Payment:**
   ```bash
   curl -X POST http://localhost:8000/api/subscriptions/SUBSCRIPTION_UUID/initialize_payment/ \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "gateway": "PAYSTACK",
       "callback_url": "http://localhost:3000/verify"
     }'
   ```

3. **Visit Authorization URL:**
   - Open `authorization_url` from response
   - Use test card: **5531886652142950**
   - CVV: **564**
   - PIN: **3310**
   - Complete payment

4. **Verify Payment:**
   ```bash
   curl -X POST http://localhost:8000/api/subscriptions/SUBSCRIPTION_UUID/verify_payment/ \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "gateway": "PAYSTACK",
       "reference": "SUB-XXX-TIMESTAMP"
     }'
   ```

5. **Verify Subscription Active:**
   ```bash
   curl -X GET http://localhost:8000/api/subscriptions/SUBSCRIPTION_UUID/ \
     -H "Authorization: Bearer YOUR_TOKEN"
   ```
   
   Should return `status: "ACTIVE"` and `payment_status: "PAID"`

---

## Error Handling

### Common Errors

1. **User Not Business Member:**
   ```json
   {
       "error": "Unauthorized",
       "detail": "You must be a member of this business to manage subscriptions"
   }
   ```

2. **Already Paid:**
   ```json
   {
       "error": "Already paid",
       "detail": "This subscription has already been paid for"
   }
   ```

3. **No Pricing Tier:**
   ```json
   {
       "error": "Pricing not available",
       "detail": "No pricing tier found for 5 storefronts"
   }
   ```

4. **Gateway Error:**
   ```json
   {
       "error": "Payment initialization failed",
       "detail": "Failed to initialize payment: Invalid API key"
   }
   ```

5. **Payment Not Found:**
   ```json
   {
       "error": "Payment not found",
       "detail": "No payment found with reference SUB-XXX-TIMESTAMP"
   }
   ```

---

## Security Considerations

1. **Server-Side Pricing:**
   - All pricing calculations done server-side
   - Frontend cannot manipulate prices
   - Pricing tier snapshot stored in payment record

2. **Payment Verification:**
   - Always verify with gateway before activating
   - Never trust frontend payment status
   - Store complete gateway response for audit

3. **Business Membership:**
   - Users can only create/pay for subscriptions of businesses they're members of
   - Enforced via `get_queryset()` filtering

4. **Reference Generation:**
   - Unique references: `SUB-{random_string}-{timestamp}`
   - Prevents duplicate payments
   - Traceable in logs

5. **Metadata Routing:**
   - `app_name='pos'` ensures webhooks route correctly
   - Critical for shared Paystack account
   - Prevents payment misattribution

---

## Related Endpoints

### Get Pricing Calculation
**Endpoint:** `POST /api/subscriptions/pricing/calculate/`

**Request:**
```json
{
    "storefront_count": 3,
    "gateway": "PAYSTACK"
}
```

**Response:**
```json
{
    "base_price": "299.99",
    "currency": "GHS",
    "taxes": [...],
    "total_tax": "52.49",
    "service_charges": [...],
    "total_service_charges": "4.50",
    "total_amount": "347.97",
    "storefront_count": 3,
    "pricing_tier": {...}
}
```

### Get Current User's Subscriptions
**Endpoint:** `GET /api/subscriptions/me/`

**Response:**
```json
[
    {
        "id": "subscription-uuid",
        "plan": {...},
        "business": {...},
        "status": "ACTIVE",
        "payment_status": "PAID",
        "start_date": "2025-01-23",
        "end_date": "2025-02-23"
    }
]
```

---

## Implementation Summary

### Files Modified
1. **subscriptions/views.py:**
   - Enhanced `SubscriptionViewSet.initialize_payment()` (260 lines)
   - Enhanced `SubscriptionViewSet.verify_payment()` (170 lines)
   - Added comprehensive error handling
   - Integrated pricing calculation
   - Added payment record creation
   - Added subscription/business activation

### Dependencies
- `subscriptions/payment_gateways.py` - PaystackGateway, StripeGateway
- `subscriptions/models.py` - SubscriptionPayment, SubscriptionPricingTier, TaxConfiguration, ServiceCharge
- `subscriptions/serializers.py` - SubscriptionCreateSerializer, SubscriptionDetailSerializer

### Django System Check
```bash
python manage.py check
# System check identified no issues (0 silenced)
```

---

## Next Steps

1. **Test with Frontend:**
   - Deploy backend changes
   - Test complete payment flow
   - Verify subscription activation
   - Test error scenarios

2. **Production Deployment:**
   - Switch to production Paystack keys
   - Configure production callback URLs
   - Set up webhook endpoints
   - Monitor payment logs

3. **Monitoring:**
   - Track payment success/failure rates
   - Monitor gateway response times
   - Log failed payments for analysis
   - Set up alerts for payment issues

---

## Contact

**Implementation Date:** January 23, 2025  
**Developer:** AI Assistant  
**Documentation Version:** 1.0
