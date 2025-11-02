# Payment Infrastructure Implementation Guide

## Overview

This document describes the implementation of the backend-first payment infrastructure for the POS subscription system, including Paystack integration, pricing calculation, and webhook handling.

## Architecture

### Backend-First Design Principles

1. **All Calculations on Backend**: Frontend ONLY displays what backend provides
2. **Single Source of Truth**: Backend performs all pricing computations
3. **Security**: No sensitive calculations exposed to client
4. **Consistency**: Same pricing logic used across all endpoints

### Key Components

1. **Pricing Calculation Endpoint**: `/api/subscriptions/pricing/calculate/`
2. **Payment Initialization**: Paystack transaction initialization
3. **Webhook Handler**: `/api/subscriptions/webhooks/paystack/`
4. **Payment Verification**: Transaction verification after payment

## Configuration

### Environment Variables

```bash
# Paystack Configuration (Test Keys)
PAYSTACK_SECRET_KEY=sk_test_16b164b455153a23804423ec0198476b3c4ca206
PAYSTACK_PUBLIC_KEY=pk_test_5309f5af38555dbf7ef47287822ef2c6d3019b9d
PAYSTACK_APP_NAME=pos

# Frontend Configuration
FRONTEND_URL=http://localhost:5173
```

### Django Settings

Add to `app/settings.py`:

```python
from decouple import config

# Paystack Configuration
PAYSTACK_SECRET_KEY = config(
    'PAYSTACK_SECRET_KEY', 
    default='sk_test_16b164b455153a23804423ec0198476b3c4ca206'
)
PAYSTACK_PUBLIC_KEY = config(
    'PAYSTACK_PUBLIC_KEY', 
    default='pk_test_5309f5af38555dbf7ef47287822ef2c6d3019b9d'
)
PAYSTACK_APP_NAME = config('PAYSTACK_APP_NAME', default='pos')
FRONTEND_URL = config('FRONTEND_URL', default='http://localhost:5173')
```

## API Endpoints

### 1. Pricing Calculation

**Endpoint**: `POST /api/subscriptions/pricing/calculate/`

**Purpose**: Calculate exact pricing breakdown before payment initialization

**Request**:
```json
{
    "plan_id": 1,
    "storefront_count": 5,
    "duration_months": 1
}
```

**Response**:
```json
{
    "success": true,
    "data": {
        "plan": {
            "id": 1,
            "name": "Professional",
            "interval": "monthly"
        },
        "storefront_count": 5,
        "duration_months": 1,
        "pricing_breakdown": {
            "base_amount": "150.00",
            "additional_storefronts": 2,
            "additional_storefront_cost": "40.00",
            "subtotal": "190.00",
            "taxes": [
                {
                    "name": "VAT",
                    "rate": "15.00",
                    "amount": "28.50"
                },
                {
                    "name": "NHIL",
                    "rate": "2.50",
                    "amount": "4.75"
                },
                {
                    "name": "GETFund Levy",
                    "rate": "2.50",
                    "amount": "4.75"
                },
                {
                    "name": "COVID-19 Levy",
                    "rate": "1.00",
                    "amount": "1.90"
                }
            ],
            "total_tax": "39.90",
            "service_charges": [
                {
                    "name": "Paystack Transaction Fee",
                    "type": "percentage",
                    "rate": "1.95",
                    "amount": "4.48"
                }
            ],
            "total_service_charges": "4.48",
            "grand_total": "234.38"
        },
        "payment_gateway": "paystack",
        "currency": "GHS"
    }
}
```

**Error Response** (Invalid Plan):
```json
{
    "success": false,
    "error": "Subscription plan not found"
}
```

### 2. Payment Initialization

**Method**: Use the Paystack Gateway directly from views

```python
from subscriptions.payment_gateways import PaystackGateway

# Initialize payment
gateway = PaystackGateway()
result = gateway.initialize_transaction(
    email=user.email,
    amount=grand_total,
    metadata={
        'subscription_id': subscription.id,
        'plan_id': plan.id,
        'storefront_count': storefront_count,
        'app_name': 'pos'  # CRITICAL: For shared account routing
    }
)

# result contains:
# - authorization_url: Redirect user here
# - access_code: Payment access code
# - reference: Transaction reference
```

### 3. Webhook Handler

**Endpoint**: `POST /api/subscriptions/webhooks/paystack/`

**Purpose**: Handle Paystack payment notifications

**Headers Required**:
```
X-Paystack-Signature: <HMAC-SHA512 signature>
```

**Request Body** (Paystack sends):
```json
{
    "event": "charge.success",
    "data": {
        "reference": "txn_1234567890",
        "amount": 23438,
        "status": "success",
        "metadata": {
            "app_name": "pos",
            "subscription_id": 123,
            "plan_id": 1,
            "storefront_count": 5
        }
    }
}
```

**Features**:
- HMAC-SHA512 signature validation
- App name routing (filters out other apps)
- Automatic payment verification
- Subscription activation
- Status history tracking

**Response**:
```json
{
    "status": "success",
    "message": "Webhook processed successfully"
}
```

## Payment Flow

### Complete Payment Process

```
1. FRONTEND: User selects plan + storefront count
   ↓
2. BACKEND: Calculate exact pricing
   POST /api/subscriptions/pricing/calculate/
   ↓
3. FRONTEND: Display pricing breakdown to user
   ↓
4. USER: Confirms and clicks "Pay Now"
   ↓
5. BACKEND: Create subscription + initialize Paystack transaction
   - Create Subscription (status='pending_payment')
   - Create SubscriptionPayment (status='pending')
   - Initialize Paystack transaction
   - Return authorization_url
   ↓
6. FRONTEND: Redirect to Paystack payment page
   window.location.href = authorization_url
   ↓
7. USER: Completes payment on Paystack
   ↓
8. PAYSTACK: Sends webhook to backend
   POST /api/subscriptions/webhooks/paystack/
   ↓
9. BACKEND: Webhook handler
   - Validates signature
   - Checks app_name routing
   - Verifies payment
   - Updates subscription status → 'active'
   - Updates payment status → 'completed'
   - Records status history
   ↓
10. PAYSTACK: Redirects user back to frontend
    {FRONTEND_URL}/subscription/success?reference=txn_xxx
    ↓
11. FRONTEND: Verify payment status
    GET /api/subscriptions/payments/{payment_id}/
    ↓
12. FRONTEND: Display success message + subscription details
```

## Code Examples

### Frontend: Calculate Pricing

```javascript
// Step 1: Calculate pricing before showing payment
async function calculatePricing(planId, storefrontCount, durationMonths = 1) {
    const response = await fetch('/api/subscriptions/pricing/calculate/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${accessToken}`
        },
        body: JSON.stringify({
            plan_id: planId,
            storefront_count: storefrontCount,
            duration_months: durationMonths
        })
    });
    
    const result = await response.json();
    
    if (result.success) {
        // Display pricing breakdown
        displayPricingBreakdown(result.data);
        return result.data;
    } else {
        showError(result.error);
        return null;
    }
}

function displayPricingBreakdown(data) {
    const breakdown = data.pricing_breakdown;
    
    // Display base amount
    console.log(`Base Amount: ${breakdown.base_amount} ${data.currency}`);
    
    // Display additional storefronts
    if (breakdown.additional_storefronts > 0) {
        console.log(`Additional Storefronts (${breakdown.additional_storefronts}): ${breakdown.additional_storefront_cost}`);
    }
    
    // Display subtotal
    console.log(`Subtotal: ${breakdown.subtotal}`);
    
    // Display taxes
    breakdown.taxes.forEach(tax => {
        console.log(`${tax.name} (${tax.rate}%): ${tax.amount}`);
    });
    
    // Display service charges
    breakdown.service_charges.forEach(charge => {
        console.log(`${charge.name}: ${charge.amount}`);
    });
    
    // Display grand total
    console.log(`TOTAL: ${breakdown.grand_total} ${data.currency}`);
}
```

### Frontend: Initialize Payment

```javascript
// Step 2: Initialize payment (after user confirms)
async function initializePayment(planId, storefrontCount, pricingData) {
    const response = await fetch('/api/subscriptions/subscriptions/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${accessToken}`
        },
        body: JSON.stringify({
            plan: planId,
            storefront_count: storefrontCount,
            // Backend will initialize payment and return authorization_url
        })
    });
    
    const result = await response.json();
    
    if (result.authorization_url) {
        // Redirect to Paystack
        window.location.href = result.authorization_url;
    } else {
        showError('Failed to initialize payment');
    }
}
```

### Backend: Create Subscription with Payment

```python
from subscriptions.payment_gateways import PaystackGateway
from subscriptions.models import Subscription, SubscriptionPayment

def create_subscription_with_payment(user, plan, storefront_count):
    """
    Create subscription and initialize payment
    """
    # 1. Calculate pricing
    pricing = calculate_pricing(plan, storefront_count)
    
    # 2. Create subscription
    subscription = Subscription.objects.create(
        user=user,
        plan=plan,
        storefront_count=storefront_count,
        status='pending_payment',
        # ... other fields
    )
    
    # 3. Create payment record
    payment = SubscriptionPayment.objects.create(
        subscription=subscription,
        user=user,
        amount=pricing['grand_total'],
        base_amount=pricing['base_amount'],
        storefront_count=storefront_count,
        tax_breakdown=pricing['taxes'],
        service_charges_breakdown=pricing['service_charges'],
        status='pending',
        gateway='paystack',
    )
    
    # 4. Initialize Paystack transaction
    gateway = PaystackGateway()
    result = gateway.initialize_transaction(
        email=user.email,
        amount=payment.amount,
        metadata={
            'subscription_id': subscription.id,
            'payment_id': payment.id,
            'plan_id': plan.id,
            'storefront_count': storefront_count,
            'app_name': 'pos',  # CRITICAL
        }
    )
    
    # 5. Update payment with transaction reference
    payment.transaction_reference = result['reference']
    payment.save()
    
    return {
        'subscription': subscription,
        'payment': payment,
        'authorization_url': result['authorization_url'],
    }
```

## Webhook Configuration

### Paystack Dashboard Setup

1. **Login to Paystack Dashboard**: https://dashboard.paystack.com
2. **Navigate to**: Settings → Webhooks
3. **Add Webhook URL**: `https://your-domain.com/api/subscriptions/webhooks/paystack/`
4. **Select Events**:
   - `charge.success` ✓
   - `charge.failed` (optional)
   - `subscription.create` (optional)

### Webhook Security

The webhook handler validates:
1. **Signature**: HMAC-SHA512 using Paystack secret key
2. **App Name**: Filters events by `metadata.app_name == 'pos'`
3. **Event Type**: Only processes `charge.success` events

### Testing Webhooks Locally

Use **ngrok** for local testing:

```bash
# Install ngrok
npm install -g ngrok

# Start ngrok tunnel
ngrok http 8000

# Copy the HTTPS URL (e.g., https://abc123.ngrok.io)
# Add to Paystack dashboard: https://abc123.ngrok.io/api/subscriptions/webhooks/paystack/
```

## Testing

### Test Paystack Payment

```bash
# 1. Calculate pricing
curl -X POST http://localhost:8000/api/subscriptions/pricing/calculate/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "plan_id": 1,
    "storefront_count": 5,
    "duration_months": 1
  }'

# 2. Use test card on Paystack
# Card Number: 4084084084084081
# CVV: 408
# Expiry: Any future date
# PIN: 0000
# OTP: 123456
```

### Verify Webhook Signature

```python
import hmac
import hashlib
from django.conf import settings

def verify_paystack_signature(request_body, signature):
    """
    Verify Paystack webhook signature
    """
    secret = settings.PAYSTACK_SECRET_KEY.encode('utf-8')
    hash_value = hmac.new(
        secret, 
        request_body, 
        hashlib.sha512
    ).hexdigest()
    
    return hash_value == signature
```

## Shared Paystack Account

### Multi-App Routing

Since the Paystack account is shared across multiple applications:

1. **Always set `app_name` in metadata**:
```python
metadata = {
    'app_name': 'pos',  # CRITICAL
    'subscription_id': 123,
    # ... other data
}
```

2. **Webhook filters by app_name**:
```python
# In paystack_webhook function
app_name = metadata.get('app_name')
if app_name != settings.PAYSTACK_APP_NAME:
    # Ignore events for other apps
    return JsonResponse({'status': 'ignored'})
```

3. **Test vs Live Keys**:
   - **Test**: `sk_test_16b164b455153a23804423ec0198476b3c4ca206`
   - **Live**: Get from Paystack dashboard when deploying to production

## Deployment Checklist

### Pre-Deployment

- [ ] Run migrations: `python manage.py migrate`
- [ ] Setup default pricing: `python manage.py setup_default_pricing`
- [ ] Create superuser: `python manage.py createsuperuser`
- [ ] Verify environment variables in `.env`
- [ ] Test pricing calculation endpoint
- [ ] Test payment initialization

### Production Setup

- [ ] Switch to Paystack **LIVE** keys in `.env`
- [ ] Update `FRONTEND_URL` to production domain
- [ ] Configure webhook URL in Paystack dashboard
- [ ] Enable SSL/HTTPS for webhook endpoint
- [ ] Set up monitoring for webhook failures
- [ ] Configure email notifications for failed payments
- [ ] Test webhook with live payment

### Security

- [ ] Validate webhook signatures
- [ ] Use HTTPS for all endpoints
- [ ] Rotate Paystack keys periodically
- [ ] Log all payment transactions
- [ ] Monitor for suspicious activity
- [ ] Set up rate limiting on webhook endpoint

## Troubleshooting

### Common Issues

**1. Webhook not receiving events**
```
Solution:
- Check Paystack dashboard webhook logs
- Verify webhook URL is accessible (test with curl)
- Ensure HTTPS is configured
- Check firewall rules
```

**2. Signature validation failing**
```
Solution:
- Verify PAYSTACK_SECRET_KEY is correct
- Ensure request body is raw (not parsed)
- Check for whitespace/encoding issues
```

**3. Payment successful but subscription not activated**
```
Solution:
- Check webhook logs for errors
- Verify app_name in metadata
- Ensure subscription ID is valid
- Check payment verification response
```

**4. Pricing calculation errors**
```
Solution:
- Verify pricing tier exists for storefront count
- Check tax configuration is active
- Ensure service charges are configured
- Validate decimal precision
```

## Monitoring

### Key Metrics

1. **Payment Success Rate**: Track successful vs failed payments
2. **Webhook Processing Time**: Monitor webhook handler performance
3. **Pricing Calculation Latency**: Track API response times
4. **Failed Webhook Retries**: Alert on multiple failures

### Logging

```python
import logging

logger = logging.getLogger(__name__)

# Log all payment events
logger.info(f"Payment initialized: {payment.id}")
logger.info(f"Webhook received: {reference}")
logger.error(f"Payment verification failed: {reference}")
```

## Support

For issues or questions:
- **Paystack Support**: support@paystack.com
- **Documentation**: https://paystack.com/docs
- **Dashboard**: https://dashboard.paystack.com

## Next Steps

1. **Frontend Integration**: Implement payment UI components
2. **Email Notifications**: Send payment receipts to users
3. **Payment Analytics**: Build dashboard for payment metrics
4. **Subscription Management**: Add upgrade/downgrade functionality
5. **Invoice Generation**: Create PDF invoices for payments
