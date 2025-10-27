# Subscription System - Quick Setup Guide

## 1. Install Dependencies

```bash
# Navigate to backend directory
cd /home/teejay/Documents/Projects/pos/backend

# Activate virtual environment
source venv/bin/activate

# Install required packages
pip install stripe requests celery python-dateutil redis
```

## 2. Run Migrations

```bash
# Create and apply migrations
python manage.py makemigrations subscriptions
python manage.py migrate subscriptions
```

## 3. Configure Payment Gateways

### Option A: Via Django Admin (Recommended)
1. Go to http://localhost:8000/admin/
2. Navigate to "Subscriptions" → "Payment Gateway Configs"
3. Add Paystack configuration:
   - Gateway: PAYSTACK
   - Is Active: ✓
   - Public Key: `pk_test_xxxxx` (from Paystack dashboard)
   - Secret Key: `sk_test_xxxxx`
   - Webhook Secret: (from Paystack webhook settings)
   - Test Mode: ✓ (for development)

4. Add Stripe configuration:
   - Gateway: STRIPE
   - Is Active: ✓
   - Public Key: `pk_test_xxxxx` (from Stripe dashboard)
   - Secret Key: `sk_test_xxxxx`
   - Webhook Secret: (from Stripe webhook settings)
   - Test Mode: ✓

### Option B: Via Django Shell
```python
python manage.py shell

from subscriptions.models import PaymentGatewayConfig

# Paystack
PaymentGatewayConfig.objects.create(
    gateway='PAYSTACK',
    is_active=True,
    public_key='pk_test_YOUR_KEY',
    secret_key='sk_test_YOUR_KEY',
    webhook_secret='whsec_YOUR_SECRET',
    test_mode=True
)

# Stripe
PaymentGatewayConfig.objects.create(
    gateway='STRIPE',
    is_active=True,
    public_key='pk_test_YOUR_KEY',
    secret_key='sk_test_YOUR_KEY',
    webhook_secret='whsec_YOUR_SECRET',
    test_mode=True
)
```

## 4. Create Subscription Plans

### Via Django Admin
1. Go to http://localhost:8000/admin/subscriptions/subscriptionplan/
2. Click "Add Subscription Plan"
3. Fill in details:
   ```
   Name: Starter
   Description: Perfect for small businesses
   Price: 99.00
   Currency: GHS
   Billing Cycle: MONTHLY
   Max Users: 5
   Max Storefronts: 2
   Max Products: 100
   Features: ["Basic reporting", "Mobile app access", "Email support"]
   Is Active: ✓
   Trial Period Days: 14
   ```

### Via Django Shell
```python
from subscriptions.models import SubscriptionPlan

SubscriptionPlan.objects.create(
    name='Starter',
    description='Perfect for small businesses',
    price=99.00,
    currency='GHS',
    billing_cycle='MONTHLY',
    max_users=5,
    max_storefronts=2,
    max_products=100,
    features=["Basic reporting", "Mobile app access", "Email support"],
    is_active=True,
    trial_period_days=14,
    sort_order=1
)

SubscriptionPlan.objects.create(
    name='Professional',
    description='For growing businesses',
    price=199.00,
    currency='GHS',
    billing_cycle='MONTHLY',
    max_users=15,
    max_storefronts=5,
    max_products=500,
    features=[
        "Advanced reporting",
        "Multi-storefront",
        "Priority support",
        "Custom integrations"
    ],
    is_active=True,
    is_popular=True,
    trial_period_days=14,
    sort_order=2
)

SubscriptionPlan.objects.create(
    name='Enterprise',
    description='For large operations',
    price=499.00,
    currency='GHS',
    billing_cycle='MONTHLY',
    max_users=None,  # Unlimited
    max_storefronts=None,
    max_products=None,
    features=[
        "All Professional features",
        "Unlimited everything",
        "Dedicated support",
        "Custom development",
        "SLA guarantee"
    ],
    is_active=True,
    trial_period_days=30,
    sort_order=3
)
```

## 5. Configure Celery (For Background Tasks)

### Install Redis (if not installed)
```bash
# Ubuntu/Debian
sudo apt-get install redis-server
sudo systemctl start redis
sudo systemctl enable redis

# macOS
brew install redis
brew services start redis
```

### Create Celery Configuration

Add to `settings/settings.py`:
```python
# Celery Configuration
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_BEAT_SCHEDULE = {
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
    'check-usage-limits': {
        'task': 'subscriptions.tasks.check_usage_limits',
        'schedule': crontab(minute=0),
    },
    'generate-monthly-invoices': {
        'task': 'subscriptions.tasks.generate_monthly_invoices',
        'schedule': crontab(day_of_month=1, hour=1, minute=0),
    },
    'cleanup-old-webhooks': {
        'task': 'subscriptions.tasks.cleanup_old_webhook_events',
        'schedule': crontab(day_of_week=0, hour=3, minute=0),
    },
}
```

Create `celery.py` in your project root:
```python
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings.settings')

app = Celery('pos_backend')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
```

### Start Celery Workers
```bash
# Terminal 1: Celery worker
celery -A settings worker -l info

# Terminal 2: Celery beat (scheduler)
celery -A settings beat -l info
```

## 6. Update Main URLs

Add to `settings/urls.py`:
```python
from django.urls import path, include

urlpatterns = [
    # ... existing patterns ...
    path('subscriptions/', include('subscriptions.urls')),
]
```

## 7. Test the API

### Start the server
```bash
python manage.py runserver
```

### Test endpoints
```bash
# Get all plans (public)
curl http://localhost:8000/subscriptions/api/plans/

# Create subscription (requires authentication)
curl -X POST http://localhost:8000/subscriptions/api/subscriptions/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "plan_id": "uuid-from-plans-endpoint",
    "payment_method": "PAYSTACK",
    "is_trial": true
  }'

# Get current subscription
curl http://localhost:8000/subscriptions/api/subscriptions/me/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 8. Configure Webhooks

### Paystack Webhook
1. Go to Paystack Dashboard → Settings → Webhooks
2. Add webhook URL: `https://yourdomain.com/subscriptions/api/webhooks/payment/`
3. Copy webhook secret to PaymentGatewayConfig

### Stripe Webhook
1. Go to Stripe Dashboard → Developers → Webhooks
2. Add endpoint: `https://yourdomain.com/subscriptions/api/webhooks/payment/`
3. Select events:
   - `checkout.session.completed`
   - `payment_intent.succeeded`
   - `payment_intent.payment_failed`
4. Copy signing secret to PaymentGatewayConfig

## 9. Environment Variables (Optional)

Create `.env` file:
```bash
# Paystack
PAYSTACK_PUBLIC_KEY=pk_test_xxxxx
PAYSTACK_SECRET_KEY=sk_test_xxxxx

# Stripe
STRIPE_PUBLIC_KEY=pk_test_xxxxx
STRIPE_SECRET_KEY=sk_test_xxxxx

# Redis
REDIS_URL=redis://localhost:6379/0
```

Load in settings:
```python
import os
from dotenv import load_dotenv

load_dotenv()

PAYSTACK_PUBLIC_KEY = os.getenv('PAYSTACK_PUBLIC_KEY')
PAYSTACK_SECRET_KEY = os.getenv('PAYSTACK_SECRET_KEY')
```

## 10. Common Commands

```bash
# Create superuser (for admin access)
python manage.py createsuperuser

# Run migrations
python manage.py migrate

# Run tests
python manage.py test subscriptions

# Check for issues
python manage.py check

# Create sample data (optional)
python manage.py shell < create_sample_plans.py
```

## Quick Test Workflow

1. **Access admin**: http://localhost:8000/admin/
2. **Create plans**: Add 2-3 subscription plans
3. **Configure gateways**: Add Paystack/Stripe configs (test mode)
4. **Test API**: Use curl or Postman
5. **Create subscription**: POST to /subscriptions/api/subscriptions/
6. **Initialize payment**: POST to /subscriptions/{id}/initialize_payment/
7. **Complete payment**: Use test card in Paystack/Stripe checkout
8. **Verify payment**: POST to /subscriptions/{id}/verify_payment/
9. **Check alerts**: GET /subscriptions/api/alerts/unread/
10. **Monitor admin**: View subscriptions in admin dashboard

## Troubleshooting

### Issue: "No module named 'subscriptions'"
```bash
# Make sure app is in INSTALLED_APPS
# settings/settings.py
INSTALLED_APPS = [
    ...
    'subscriptions',
]
```

### Issue: "Paystack gateway not configured"
```bash
# Add PaymentGatewayConfig via admin or shell
python manage.py shell
>>> from subscriptions.models import PaymentGatewayConfig
>>> PaymentGatewayConfig.objects.create(gateway='PAYSTACK', is_active=True, ...)
```

### Issue: Celery tasks not running
```bash
# Check Redis is running
redis-cli ping  # Should return PONG

# Check Celery workers are running
celery -A settings inspect active
```

### Issue: Webhook signature verification failed
```bash
# Make sure webhook_secret is correct in PaymentGatewayConfig
# Check webhook URL is accessible from internet (use ngrok for local testing)
ngrok http 8000
```

## Next Steps

1. ✅ Backend setup complete
2. ⏳ Frontend integration (by frontend team)
3. ⏳ Email/SMS notification setup
4. ⏳ Production deployment
5. ⏳ Monitoring and analytics

---

**Quick Reference**: See `SUBSCRIPTION_BACKEND_COMPLETE.md` for full API documentation
