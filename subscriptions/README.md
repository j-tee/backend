# Subscription Management System

Complete backend implementation for subscription billing and management in the POS SaaS platform.

## Features

- ✅ Multiple subscription tiers with custom pricing
- ✅ Trial periods with automatic conversion
- ✅ Payment processing (Paystack + Stripe)
- ✅ Automated renewals and expiration handling
- ✅ Usage tracking and limit enforcement
- ✅ Invoice generation
- ✅ Alert/notification system
- ✅ Admin dashboard
- ✅ Comprehensive API

## Quick Start

### 1. Apply Migrations
```bash
python manage.py migrate subscriptions
```

### 2. Access Admin
```
http://localhost:8000/admin/subscriptions/
```

### 3. Create Subscription Plans
See `SUBSCRIPTION_SETUP_GUIDE.md` for detailed instructions

### 4. Test API
```bash
# Get plans (public)
curl http://localhost:8000/subscriptions/api/plans/

# Create subscription (authenticated)
curl -X POST http://localhost:8000/subscriptions/api/subscriptions/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"plan_id": "uuid", "is_trial": true}'
```

## Documentation

- **Complete Guide**: `SUBSCRIPTION_BACKEND_COMPLETE.md`
- **Setup Instructions**: `SUBSCRIPTION_SETUP_GUIDE.md`
- **API Reference**: `SUBSCRIPTION_API_REFERENCE.md`
- **Implementation Summary**: `SUBSCRIPTION_IMPLEMENTATION_SUMMARY.md`
- **Deployment Checklist**: `SUBSCRIPTION_DEPLOYMENT_CHECKLIST.md`

## Architecture

### Models
- `SubscriptionPlan` - Pricing tiers
- `Subscription` - User subscriptions
- `SubscriptionPayment` - Payment records
- `PaymentGatewayConfig` - Gateway settings
- `WebhookEvent` - Webhook logs
- `UsageTracking` - Resource usage
- `Invoice` - Billing invoices
- `Alert` - Notifications

### Payment Gateways
- **Paystack** - Mobile Money (Ghana)
- **Stripe** - International cards

### Background Tasks (Celery)
- Trial expiration checks
- Subscription expiration monitoring
- Auto-renewal processing
- Usage limit warnings
- Payment reminders
- Invoice generation

## API Endpoints

### Public
- `GET /api/plans/` - List plans
- `GET /api/plans/{id}/` - Plan details

### Authenticated
- `POST /api/subscriptions/` - Create subscription
- `GET /api/subscriptions/me/` - Current subscription
- `POST /api/subscriptions/{id}/initialize_payment/` - Start payment
- `POST /api/subscriptions/{id}/verify_payment/` - Verify payment
- `GET /api/subscriptions/{id}/usage/` - Check usage
- `GET /api/alerts/unread/` - Get alerts

### Admin Only
- `POST /api/subscriptions/{id}/suspend/` - Suspend subscription
- `GET /api/stats/overview/` - Statistics

Full API documentation: `SUBSCRIPTION_API_REFERENCE.md`

## Configuration

### Payment Gateways
Configure via Django Admin:
1. Navigate to **Subscriptions → Payment Gateway Configs**
2. Add Paystack and/or Stripe configurations
3. Set test mode for development

### Celery Tasks (Optional)
```python
# settings.py
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_BEAT_SCHEDULE = {
    'check-trial-expirations': {
        'task': 'subscriptions.tasks.check_trial_expirations',
        'schedule': crontab(hour=2, minute=0),
    },
    # ... more tasks
}
```

Start workers:
```bash
celery -A app worker -l info
celery -A app beat -l info
```

## Testing

```bash
# Test with curl
curl http://localhost:8000/subscriptions/api/plans/

# Test with Python
import requests
response = requests.get('http://localhost:8000/subscriptions/api/plans/')
print(response.json())
```

## Security

- JWT authentication required (except public plan listing)
- Webhook signature verification
- Permission-based access control
- Encrypted gateway credentials

## Support

- Check logs in Django admin → Webhook Events
- Review `SUBSCRIPTION_DEPLOYMENT_CHECKLIST.md`
- Test in gateway test mode first

---

**Status**: ✅ Production Ready  
**Version**: 1.0  
**Last Updated**: January 2025
