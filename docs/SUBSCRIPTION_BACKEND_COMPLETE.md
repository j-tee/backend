# Subscription Management System - Backend Implementation

## Overview
Complete subscription billing and management backend for the POS system. Supports multiple payment gateways (Paystack for Ghana/Mobile Money, Stripe for International cards), automated renewals, usage tracking, and comprehensive alerts.

## Architecture

### Models
1. **SubscriptionPlan** - Pricing tiers and features
2. **Subscription** - User/business subscriptions
3. **SubscriptionPayment** - Payment records
4. **PaymentGatewayConfig** - Payment gateway configurations
5. **WebhookEvent** - Gateway webhook logs
6. **UsageTracking** - Resource usage monitoring
7. **Invoice** - Billing invoices
8. **Alert** - Notifications and alerts

### Components
- **Serializers** (`serializers.py`) - Data serialization/validation
- **Views** (`views.py`) - REST API endpoints
- **Payment Gateways** (`payment_gateways.py`) - Paystack & Stripe integrations
- **Tasks** (`tasks.py`) - Celery background jobs
- **Admin** (`admin.py`) - Django admin interface

## API Endpoints

### Public Endpoints

#### Subscription Plans
```
GET /subscriptions/api/plans/
GET /subscriptions/api/plans/{id}/
GET /subscriptions/api/plans/popular/
GET /subscriptions/api/plans/{id}/features/
```

### Authenticated Endpoints

#### Subscriptions
```
GET    /subscriptions/api/subscriptions/           # List user's subscriptions
POST   /subscriptions/api/subscriptions/           # Create subscription
GET    /subscriptions/api/subscriptions/me/        # Get active subscription
GET    /subscriptions/api/subscriptions/{id}/      # Get subscription details
PATCH  /subscriptions/api/subscriptions/{id}/      # Update subscription
DELETE /subscriptions/api/subscriptions/{id}/      # Delete subscription

# Custom Actions
POST   /subscriptions/api/subscriptions/{id}/initialize_payment/
POST   /subscriptions/api/subscriptions/{id}/verify_payment/
POST   /subscriptions/api/subscriptions/{id}/cancel/
POST   /subscriptions/api/subscriptions/{id}/renew/
GET    /subscriptions/api/subscriptions/{id}/usage/
GET    /subscriptions/api/subscriptions/{id}/invoices/
GET    /subscriptions/api/subscriptions/{id}/payments/
GET    /subscriptions/api/subscriptions/{id}/alerts/
```

#### Alerts
```
GET    /subscriptions/api/alerts/                  # List alerts
GET    /subscriptions/api/alerts/{id}/             # Get alert details
POST   /subscriptions/api/alerts/{id}/mark_read/   # Mark as read
POST   /subscriptions/api/alerts/{id}/dismiss/     # Dismiss alert
GET    /subscriptions/api/alerts/unread/           # Get unread alerts
GET    /subscriptions/api/alerts/critical/         # Get critical alerts
```

#### Payments & Invoices
```
GET    /subscriptions/api/payments/                # Payment history
GET    /subscriptions/api/invoices/                # Invoice list
GET    /subscriptions/api/invoices/{id}/           # Invoice details
POST   /subscriptions/api/invoices/{id}/mark_paid/ # Mark invoice as paid (admin)
```

### Platform Admin Endpoints

#### Subscription Management
```
POST   /subscriptions/api/subscriptions/{id}/suspend/    # Suspend subscription
POST   /subscriptions/api/subscriptions/{id}/activate/   # Activate subscription
```

#### Statistics
```
GET    /subscriptions/api/stats/overview/           # Overall stats
GET    /subscriptions/api/stats/revenue_by_plan/    # Revenue breakdown
GET    /subscriptions/api/stats/expiring_soon/      # Expiring subscriptions
```

### Webhook Endpoints
```
POST   /subscriptions/api/webhooks/payment/         # Payment gateway webhooks
```

## Payment Gateway Integration

### Paystack (Mobile Money - Ghana)

#### Initialize Payment
```python
POST /subscriptions/api/subscriptions/{id}/initialize_payment/

Request:
{
    "gateway": "PAYSTACK",
    "callback_url": "https://yourdomain.com/payment/callback"
}

Response:
{
    "success": true,
    "authorization_url": "https://checkout.paystack.com/xyz",
    "access_code": "abc123",
    "reference": "SUB_uuid_timestamp"
}
```

#### Verify Payment
```python
POST /subscriptions/api/subscriptions/{id}/verify_payment/

Request:
{
    "gateway": "PAYSTACK",
    "reference": "SUB_uuid_timestamp"
}

Response:
{
    "success": true,
    "message": "Payment verified successfully",
    "payment": { ... }
}
```

### Stripe (International Cards)

#### Initialize Payment
```python
POST /subscriptions/api/subscriptions/{id}/initialize_payment/

Request:
{
    "gateway": "STRIPE",
    "success_url": "https://yourdomain.com/payment/success",
    "cancel_url": "https://yourdomain.com/payment/cancel"
}

Response:
{
    "success": true,
    "session_id": "cs_test_xyz",
    "checkout_url": "https://checkout.stripe.com/pay/cs_test_xyz"
}
```

#### Verify Payment
```python
POST /subscriptions/api/subscriptions/{id}/verify_payment/

Request:
{
    "gateway": "STRIPE",
    "reference": "cs_test_xyz"  # session_id
}

Response:
{
    "success": true,
    "message": "Payment verified successfully",
    "payment": { ... }
}
```

## Usage Examples

### 1. Create Subscription
```python
POST /subscriptions/api/subscriptions/

{
    "plan_id": "uuid-of-plan",
    "business_id": "uuid-of-business",  # optional
    "payment_method": "PAYSTACK",
    "is_trial": true
}
```

### 2. Get Current Subscription
```python
GET /subscriptions/api/subscriptions/me/

Response:
{
    "id": "uuid",
    "plan": { ... },
    "status": "ACTIVE",
    "payment_status": "PAID",
    "start_date": "2024-01-01",
    "end_date": "2024-02-01",
    "days_until_expiry": 15,
    "is_active": true,
    "usage_limits": {
        "users": {
            "current": 5,
            "limit": 10,
            "exceeded": false
        },
        ...
    },
    ...
}
```

### 3. Check Usage Limits
```python
GET /subscriptions/api/subscriptions/{id}/usage/

Response:
{
    "subscription_id": "uuid",
    "plan_name": "Professional",
    "usage": {
        "users": {
            "current": 8,
            "limit": 10,
            "exceeded": false
        },
        "storefronts": {
            "current": 3,
            "limit": 5,
            "exceeded": false
        },
        "products": {
            "current": 450,
            "limit": 500,
            "exceeded": false
        }
    }
}
```

### 4. Cancel Subscription
```python
POST /subscriptions/api/subscriptions/{id}/cancel/

{
    "immediately": false,  # false = cancel at period end
    "reason": "Switching to competitor"
}
```

### 5. Get Alerts
```python
GET /subscriptions/api/alerts/unread/

Response:
[
    {
        "id": "uuid",
        "alert_type": "PAYMENT_DUE",
        "priority": "HIGH",
        "title": "Payment Due",
        "message": "Your subscription renewal payment of GHS 199.00 is due on 2024-02-01.",
        "is_read": false,
        "created_at": "2024-01-25T10:00:00Z",
        ...
    }
]
```

## Celery Background Tasks

### Task Schedule (Recommended)

```python
# settings/celery.py or celery_beat_schedule

CELERY_BEAT_SCHEDULE = {
    # Run every day at 2:00 AM
    'check-trial-expirations': {
        'task': 'subscriptions.tasks.check_trial_expirations',
        'schedule': crontab(hour=2, minute=0),
    },
    'process-trial-expirations': {
        'task': 'subscriptions.tasks.process_trial_expirations',
        'schedule': crontab(hour=3, minute=0),
    },
    'check-subscription-expirations': {
        'task': 'subscriptions.tasks.check_subscription_expirations',
        'schedule': crontab(hour=4, minute=0),
    },
    'process-subscription-expirations': {
        'task': 'subscriptions.tasks.process_subscription_expirations',
        'schedule': crontab(hour=5, minute=0),
    },
    'process-auto-renewals': {
        'task': 'subscriptions.tasks.process_auto_renewals',
        'schedule': crontab(hour=6, minute=0),
    },
    'send-payment-reminders': {
        'task': 'subscriptions.tasks.send_payment_reminders',
        'schedule': crontab(hour=9, minute=0),
    },
    
    # Run every hour
    'check-usage-limits': {
        'task': 'subscriptions.tasks.check_usage_limits',
        'schedule': crontab(minute=0),  # Every hour
    },
    
    # Run on 1st of month at 1:00 AM
    'generate-monthly-invoices': {
        'task': 'subscriptions.tasks.generate_monthly_invoices',
        'schedule': crontab(day_of_month=1, hour=1, minute=0),
    },
    
    # Run weekly on Sunday at 3:00 AM
    'cleanup-old-webhooks': {
        'task': 'subscriptions.tasks.cleanup_old_webhook_events',
        'schedule': crontab(day_of_week=0, hour=3, minute=0),
    },
}
```

### Available Tasks

1. **check_trial_expirations** - Alert users 3 days before trial ends
2. **process_trial_expirations** - Convert/deactivate expired trials
3. **check_subscription_expirations** - Alert 7 days before expiry
4. **process_subscription_expirations** - Mark expired subscriptions
5. **process_auto_renewals** - Handle automatic renewals
6. **check_usage_limits** - Monitor usage and send warnings
7. **send_payment_reminders** - Remind about overdue payments
8. **generate_monthly_invoices** - Create monthly invoices
9. **cleanup_old_webhook_events** - Clean old webhook logs

## Subscription Status Flow

```
TRIAL → ACTIVE (after payment)
      ↓
TRIAL → INACTIVE (trial expired, no payment)

ACTIVE → PAST_DUE (payment failed, within grace period)
       ↓
PAST_DUE → EXPIRED (grace period ended)
         ↓
EXPIRED → ACTIVE (payment made, reactivated)

ACTIVE → CANCELLED (user cancelled)
ACTIVE → SUSPENDED (admin suspended)
```

## Payment Status Flow

```
PENDING → PAID (successful payment)
        → FAILED (payment failed)
        → CANCELLED (user cancelled)

PAID → OVERDUE (renewal payment missed)
```

## Alert Types

- **PAYMENT_DUE** - Payment is due soon
- **PAYMENT_FAILED** - Payment failed
- **PAYMENT_SUCCESS** - Payment successful
- **TRIAL_ENDING** - Trial ending in 3 days
- **SUBSCRIPTION_EXPIRING** - Subscription expiring in 7 days
- **SUBSCRIPTION_EXPIRED** - Subscription expired
- **SUBSCRIPTION_CANCELLED** - Subscription cancelled
- **SUBSCRIPTION_SUSPENDED** - Subscription suspended (admin)
- **SUBSCRIPTION_ACTIVATED** - Subscription activated
- **USAGE_LIMIT_WARNING** - At 80% of limit
- **USAGE_LIMIT_REACHED** - Limit exceeded

## Configuration

### Payment Gateway Setup

#### Paystack
```python
# In Django Admin or via API
PaymentGatewayConfig.objects.create(
    gateway='PAYSTACK',
    is_active=True,
    public_key='pk_test_xxxxx',
    secret_key='sk_test_xxxxx',
    webhook_secret='whsec_xxxxx',
    test_mode=True
)
```

#### Stripe
```python
PaymentGatewayConfig.objects.create(
    gateway='STRIPE',
    is_active=True,
    public_key='pk_test_xxxxx',
    secret_key='sk_test_xxxxx',
    webhook_secret='whsec_xxxxx',
    test_mode=True
)
```

### Environment Variables
```bash
# Optionally add to .env for extra security
PAYSTACK_PUBLIC_KEY=pk_test_xxxxx
PAYSTACK_SECRET_KEY=sk_test_xxxxx
STRIPE_PUBLIC_KEY=pk_test_xxxxx
STRIPE_SECRET_KEY=sk_test_xxxxx
```

## Database Migrations

```bash
# Create migrations
python manage.py makemigrations subscriptions

# Apply migrations
python manage.py migrate subscriptions
```

## Dependencies

Add to `requirements.txt`:
```
stripe>=5.0.0
requests>=2.31.0
celery>=5.3.0
python-dateutil>=2.8.2
```

## Testing

### Manual Test Script
```bash
# Test subscription creation
curl -X POST http://localhost:8000/subscriptions/api/subscriptions/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "plan_id": "uuid-of-plan",
    "payment_method": "PAYSTACK",
    "is_trial": true
  }'

# Test payment initialization
curl -X POST http://localhost:8000/subscriptions/api/subscriptions/{id}/initialize_payment/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "gateway": "PAYSTACK",
    "callback_url": "http://localhost:3000/payment/callback"
  }'
```

## Security Considerations

1. **Webhook Signatures** - Always verify webhook signatures
2. **API Keys** - Store securely, never commit to git
3. **HTTPS** - Always use HTTPS in production
4. **CSRF** - Webhooks are CSRF-exempt but use signature verification
5. **Permissions** - Enforce strict permission checks
6. **Rate Limiting** - Implement rate limiting on payment endpoints

## Monitoring & Logging

All operations are logged to Django logger `subscriptions`:

```python
import logging
logger = logging.getLogger('subscriptions')
```

Key events logged:
- Payment initializations/verifications
- Webhook processing
- Task executions
- Errors and exceptions

## Admin Interface

Access Django admin at `/admin/` to manage:
- Subscription plans
- Active subscriptions
- Payments and invoices
- Alerts and notifications
- Payment gateway configs
- Webhook events

## Next Steps

1. **Set up payment gateways** - Configure Paystack and Stripe
2. **Create subscription plans** - Add your pricing tiers
3. **Configure Celery** - Set up Celery beat for scheduled tasks
4. **Test webhooks** - Use gateway test tools
5. **Monitor logs** - Check for errors
6. **Set up email/SMS** - Configure notification channels

## Support & Issues

For issues or questions:
1. Check logs in `/logs/`
2. Review admin dashboard
3. Test with gateway test modes first
4. Verify webhook signatures

---

**Implementation Status**: ✅ Backend Complete
**Frontend Status**: To be implemented by frontend team
**Last Updated**: 2024
