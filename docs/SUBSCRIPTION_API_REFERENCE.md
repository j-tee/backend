# Subscription API - Quick Reference Card

## Base URL
```
/subscriptions/api/
```

## Authentication
All endpoints except plans require JWT token:
```
Authorization: Bearer <your-jwt-token>
```

---

## 📋 Subscription Plans

### List Plans (Public)
```http
GET /plans/
```

### Get Plan Details (Public)
```http
GET /plans/{id}/
```

### Popular Plans (Public)
```http
GET /plans/popular/
```

---

## 💳 Subscriptions

### Create Subscription
```http
POST /subscriptions/

{
    "plan_id": "uuid",
    "business_id": "uuid",  // optional
    "payment_method": "PAYSTACK",
    "is_trial": true
}
```

### My Active Subscription
```http
GET /subscriptions/me/
```

### List My Subscriptions
```http
GET /subscriptions/
```

### Get Subscription Details
```http
GET /subscriptions/{id}/
```

### Cancel Subscription
```http
POST /subscriptions/{id}/cancel/

{
    "immediately": false,  // true = cancel now, false = at period end
    "reason": "string"
}
```

### Renew Subscription
```http
POST /subscriptions/{id}/renew/

{
    "payment_method": "PAYSTACK"  // optional
}
```

### Check Usage Limits
```http
GET /subscriptions/{id}/usage/
```

---

## 💰 Payments

### Initialize Payment (Paystack)
```http
POST /subscriptions/{id}/initialize_payment/

{
    "gateway": "PAYSTACK",
    "callback_url": "https://yourdomain.com/callback"
}

Response:
{
    "success": true,
    "authorization_url": "https://checkout.paystack.com/...",
    "reference": "SUB_..."
}
```

### Initialize Payment (Stripe)
```http
POST /subscriptions/{id}/initialize_payment/

{
    "gateway": "STRIPE",
    "success_url": "https://yourdomain.com/success",
    "cancel_url": "https://yourdomain.com/cancel"
}

Response:
{
    "success": true,
    "session_id": "cs_test_...",
    "checkout_url": "https://checkout.stripe.com/..."
}
```

### Verify Payment
```http
POST /subscriptions/{id}/verify_payment/

{
    "gateway": "PAYSTACK",  // or "STRIPE"
    "reference": "SUB_..."  // or session_id for Stripe
}

Response:
{
    "success": true,
    "message": "Payment verified successfully",
    "payment": { ... }
}
```

### Payment History
```http
GET /payments/
GET /subscriptions/{id}/payments/
```

---

## 📄 Invoices

### List Invoices
```http
GET /invoices/
GET /subscriptions/{id}/invoices/
```

### Get Invoice Details
```http
GET /invoices/{id}/
```

### Mark Invoice as Paid (Admin)
```http
POST /invoices/{id}/mark_paid/
```

---

## 🔔 Alerts

### Get Alerts
```http
GET /alerts/
GET /subscriptions/{id}/alerts/
```

### Unread Alerts
```http
GET /alerts/unread/
```

### Critical Alerts
```http
GET /alerts/critical/
```

### Mark Alert as Read
```http
POST /alerts/{id}/mark_read/
```

### Dismiss Alert
```http
POST /alerts/{id}/dismiss/
```

---

## 📊 Statistics (Admin Only)

### Overview
```http
GET /stats/overview/

Response:
{
    "total_subscriptions": 150,
    "active_subscriptions": 120,
    "trial_subscriptions": 20,
    "expired_subscriptions": 5,
    "cancelled_subscriptions": 5,
    "total_revenue": "25000.00",
    "monthly_recurring_revenue": "15000.00",
    "average_subscription_value": "199.00",
    "churn_rate": 3.5
}
```

### Revenue by Plan
```http
GET /stats/revenue_by_plan/
```

### Expiring Soon
```http
GET /stats/expiring_soon/
```

---

## 🔧 Admin Actions

### Suspend Subscription
```http
POST /subscriptions/{id}/suspend/

{
    "reason": "Payment fraud detected"
}
```

### Activate Subscription
```http
POST /subscriptions/{id}/activate/
```

---

## 🎯 Common Workflows

### 1️⃣ New Subscription Flow
```
1. GET /plans/                          # Browse plans
2. POST /subscriptions/                 # Create subscription
3. POST /subscriptions/{id}/initialize_payment/
4. [User completes payment]
5. POST /subscriptions/{id}/verify_payment/
6. GET /subscriptions/me/               # Check active subscription
```

### 2️⃣ Payment Flow (Paystack)
```
1. Initialize: POST /subscriptions/{id}/initialize_payment/
2. Redirect user to: response.authorization_url
3. User completes payment on Paystack
4. Paystack redirects to: callback_url?reference=XXX
5. Verify: POST /subscriptions/{id}/verify_payment/
```

### 3️⃣ Payment Flow (Stripe)
```
1. Initialize: POST /subscriptions/{id}/initialize_payment/
2. Redirect user to: response.checkout_url
3. User completes payment on Stripe
4. Stripe redirects to: success_url
5. Verify: POST /subscriptions/{id}/verify_payment/ with session_id
```

### 4️⃣ Cancel Subscription
```
1. GET /subscriptions/me/               # Get current subscription
2. POST /subscriptions/{id}/cancel/     # Cancel it
   - immediately: false → active until period end
   - immediately: true → deactivate now
```

### 5️⃣ Monitor Usage
```
1. GET /subscriptions/me/               # Get subscription with usage
2. GET /subscriptions/{id}/usage/       # Detailed usage breakdown
3. GET /alerts/unread/                  # Check for usage warnings
```

---

## 🚨 Alert Types

| Type | Priority | Trigger |
|------|----------|---------|
| PAYMENT_DUE | HIGH | Payment due date approaching |
| PAYMENT_FAILED | CRITICAL | Payment attempt failed |
| PAYMENT_SUCCESS | MEDIUM | Payment successful |
| TRIAL_ENDING | HIGH | Trial ends in 3 days |
| SUBSCRIPTION_EXPIRING | HIGH | Expiry in 7 days |
| SUBSCRIPTION_EXPIRED | CRITICAL | Subscription expired |
| USAGE_LIMIT_WARNING | MEDIUM | 80% of limit reached |
| USAGE_LIMIT_REACHED | CRITICAL | Limit exceeded |
| SUBSCRIPTION_CANCELLED | HIGH | Subscription cancelled |
| SUBSCRIPTION_SUSPENDED | CRITICAL | Admin suspended |
| SUBSCRIPTION_ACTIVATED | HIGH | Subscription activated |

---

## 📝 Status Values

### Subscription Status
- `TRIAL` - In trial period
- `ACTIVE` - Paid and active
- `PAST_DUE` - Payment failed, in grace period
- `INACTIVE` - Not active
- `CANCELLED` - User cancelled
- `SUSPENDED` - Admin suspended
- `EXPIRED` - Not renewed after grace period

### Payment Status
- `PAID` - Payment successful
- `PENDING` - Awaiting payment
- `FAILED` - Payment failed
- `OVERDUE` - Payment overdue
- `CANCELLED` - Payment cancelled

### Invoice Status
- `DRAFT` - Not sent
- `SENT` - Sent to customer
- `PAID` - Payment received
- `OVERDUE` - Past due date
- `CANCELLED` - Cancelled

---

## 🔐 Test Cards

### Paystack Test Cards
```
Success: 4084084084084081
Declined: 5060666666666666666
```

### Stripe Test Cards
```
Success: 4242424242424242
Decline: 4000000000000002
3D Secure: 4000002500003155
```

---

## 🌐 Webhooks

### Endpoint
```
POST /webhooks/payment/
```

### Paystack Events
- `charge.success`
- `subscription.disable`

### Stripe Events
- `checkout.session.completed`
- `payment_intent.succeeded`
- `payment_intent.payment_failed`

---

## 💡 Tips

1. **Always verify payments** after redirect
2. **Check usage limits** before creating resources
3. **Monitor alerts** for payment issues
4. **Use test mode** for development
5. **Secure webhook endpoints** properly
6. **Handle grace periods** appropriately
7. **Notify users** before expiry

---

**Full Documentation**: `SUBSCRIPTION_BACKEND_COMPLETE.md`
**Setup Guide**: `SUBSCRIPTION_SETUP_GUIDE.md`
