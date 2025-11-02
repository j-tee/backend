# Quick Start Guide - Payment Infrastructure

## Prerequisites
- Python 3.8+
- PostgreSQL database
- Redis (for Celery)
- Git

## Installation & Setup

### 1. Environment Setup

```bash
# Navigate to backend directory
cd /home/teejay/Documents/Projects/pos/backend

# Activate virtual environment
source venv/bin/activate

# Create environment file from template
cp .env.template .env

# Edit .env with your configuration
nano .env
```

### 2. Database Migration

```bash
# Activate virtual environment
source venv/bin/activate

# Create migrations for new models
python manage.py makemigrations subscriptions

# Apply migrations
python manage.py migrate

# Setup default pricing data
python manage.py setup_default_pricing
```

### 3. Create Superuser (if needed)

```bash
python manage.py createsuperuser
```

### 4. Start Development Server

```bash
# Activate virtual environment (if not already activated)
source venv/bin/activate

# Start Django server
python manage.py runserver
```

## Testing the Implementation

### 1. Test Pricing Calculation

```bash
# First, get an authentication token (if using JWT)
# Then test pricing calculation

curl -X POST http://localhost:8000/api/subscriptions/pricing/calculate/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "plan_id": 1,
    "storefront_count": 5,
    "duration_months": 1
  }'
```

**Expected Response**:
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
      "taxes": [...],
      "total_tax": "39.90",
      "service_charges": [...],
      "total_service_charges": "4.48",
      "grand_total": "234.38"
    }
  }
}
```

### 2. Test Paystack Integration

```bash
# Activate virtual environment
source venv/bin/activate

# In Django shell
python manage.py shell
```

```python
from subscriptions.payment_gateways import PaystackGateway
from accounts.models import User

# Get a user
user = User.objects.first()

# Initialize payment
gateway = PaystackGateway()
result = gateway.initialize_transaction(
    email=user.email,
    amount=100.00,
    metadata={
        'app_name': 'pos',
        'subscription_id': 1,
        'plan_id': 1,
        'storefront_count': 3
    }
)

print(result)
# Should print: {'authorization_url': '...', 'access_code': '...', 'reference': '...'}
```

### 3. Test Webhook Handler Locally

**Option A: Using ngrok**

```bash
# Install ngrok (if not already installed)
npm install -g ngrok

# Start ngrok tunnel
ngrok http 8000

# Copy the HTTPS URL (e.g., https://abc123.ngrok.io)
# Add to Paystack dashboard: https://abc123.ngrok.io/api/subscriptions/webhooks/paystack/
```

**Option B: Manual webhook simulation**

```bash
# Create a test payload
cat > webhook_test.json << EOF
{
  "event": "charge.success",
  "data": {
    "reference": "test_txn_123",
    "amount": 23438,
    "status": "success",
    "metadata": {
      "app_name": "pos",
      "subscription_id": 1,
      "payment_id": 1
    }
  }
}
EOF

# Generate signature
python -c "
import hmac
import hashlib
import json

secret = 'sk_test_16b164b455153a23804423ec0198476b3c4ca206'
with open('webhook_test.json', 'rb') as f:
    payload = f.read()
    
signature = hmac.new(
    secret.encode('utf-8'),
    payload,
    hashlib.sha512
).hexdigest()

print(signature)
"

# Test webhook (replace SIGNATURE with output from above)
curl -X POST http://localhost:8000/api/subscriptions/webhooks/paystack/ \
  -H "Content-Type: application/json" \
  -H "X-Paystack-Signature: SIGNATURE" \
  -d @webhook_test.json
```

### 4. Test Payment Stats

```bash
# Get payment overview
curl -X GET http://localhost:8000/api/subscriptions/payment-stats/overview/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# Get revenue chart
curl -X GET "http://localhost:8000/api/subscriptions/payment-stats/revenue-chart/?period=month" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Paystack Test Cards

Use these test cards for payment testing:

### Successful Payment
- **Card Number**: 4084084084084081
- **CVV**: 408
- **Expiry**: Any future date
- **PIN**: 0000
- **OTP**: 123456

### Failed Payment (Insufficient Funds)
- **Card Number**: 5060666666666666666
- **CVV**: 123
- **Expiry**: Any future date

### More test cards: https://paystack.com/docs/payments/test-payments

## Admin Panel

Access Django admin to manage pricing tiers, taxes, and service charges:

```
URL: http://localhost:8000/admin/
```

### Available Admin Sections
- **Subscription Pricing Tiers**: Manage pricing tiers
- **Tax Configuration**: Configure Ghana taxes
- **Service Charges**: Manage payment gateway fees
- **Subscription Payments**: View all payments

## API Endpoints Reference

### Pricing Management
- `GET /api/subscriptions/pricing-tiers/` - List all pricing tiers
- `POST /api/subscriptions/pricing-tiers/` - Create pricing tier (Admin only)
- `GET /api/subscriptions/pricing-tiers/{id}/` - Get pricing tier details
- `PUT /api/subscriptions/pricing-tiers/{id}/` - Update pricing tier (Admin only)
- `DELETE /api/subscriptions/pricing-tiers/{id}/` - Delete pricing tier (Admin only)
- `GET /api/subscriptions/pricing-tiers/{id}/calculate/` - Calculate pricing for tier

### Tax Configuration
- `GET /api/subscriptions/tax-config/` - List all tax configurations
- `POST /api/subscriptions/tax-config/` - Create tax config (Admin only)
- `GET /api/subscriptions/tax-config/active/` - Get active tax configuration
- `GET /api/subscriptions/tax-config/{id}/` - Get tax config details
- `PUT /api/subscriptions/tax-config/{id}/` - Update tax config (Admin only)

### Service Charges
- `GET /api/subscriptions/service-charges/` - List all service charges
- `POST /api/subscriptions/service-charges/` - Create service charge (Admin only)
- `GET /api/subscriptions/service-charges/{id}/` - Get service charge details
- `PUT /api/subscriptions/service-charges/{id}/` - Update service charge (Admin only)

### Payment Operations
- `POST /api/subscriptions/pricing/calculate/` - Calculate subscription pricing
- `POST /api/subscriptions/webhooks/paystack/` - Paystack webhook handler
- `GET /api/subscriptions/payment-stats/overview/` - Payment statistics
- `GET /api/subscriptions/payment-stats/revenue-chart/` - Revenue chart data

## Troubleshooting

### Issue: "Subscription plan not found"
**Solution**: Ensure you've run `python manage.py setup_default_pricing`

### Issue: "Invalid signature" on webhook
**Solution**: 
1. Verify `PAYSTACK_SECRET_KEY` in `.env` matches Paystack dashboard
2. Ensure webhook payload is sent as raw JSON (not parsed)
3. Check for whitespace in signature header

### Issue: Pricing calculation returns 0
**Solution**:
1. Check that pricing tiers exist in database
2. Verify tax configuration is active
3. Ensure storefront_count is within tier range

### Issue: Payment initialized but webhook not received
**Solution**:
1. Check Paystack dashboard webhook logs
2. Verify webhook URL is accessible (test with curl)
3. Ensure `app_name` metadata is set to 'pos'
4. Check firewall/security group settings

## Development Workflow

### Making Changes to Pricing Logic

1. **Update models** (if needed): `subscriptions/models.py`
2. **Create migration**: `python manage.py makemigrations`
3. **Apply migration**: `python manage.py migrate`
4. **Update views**: `subscriptions/views.py`
5. **Test changes**: Run unit tests
6. **Update docs**: Document new behavior

### Testing Payment Flow

1. **Calculate pricing**: Use pricing calculation endpoint
2. **Initialize payment**: Create subscription with payment
3. **Complete payment**: Use Paystack test card
4. **Verify webhook**: Check webhook logs
5. **Confirm activation**: Verify subscription status is 'active'

## Monitoring & Logs

### View Django Logs
```bash
# Activate virtual environment
source venv/bin/activate

# View logs
tail -f logs/django.log
```

### View Celery Logs (if using async tasks)
```bash
tail -f logs/celery.log
```

### View Payment Logs
```bash
# Activate virtual environment
source venv/bin/activate

# In Django shell
python manage.py shell
```

```python
from subscriptions.models import SubscriptionPayment

# View recent payments
payments = SubscriptionPayment.objects.order_by('-created_at')[:10]
for p in payments:
    print(f"{p.id}: {p.status} - {p.amount} {p.currency}")
```

## Production Deployment

See `docs/PAYMENT_INFRASTRUCTURE_IMPLEMENTATION.md` for complete deployment guide.

### Quick Production Checklist
- [ ] Switch to Paystack LIVE keys in `.env`
- [ ] Update `FRONTEND_URL` to production domain
- [ ] Configure production webhook URL in Paystack dashboard
- [ ] Enable HTTPS/SSL
- [ ] Setup monitoring
- [ ] Configure email notifications
- [ ] Test with small live payment

## Support & Documentation

- **Full Documentation**: `docs/PAYMENT_INFRASTRUCTURE_IMPLEMENTATION.md`
- **Implementation Summary**: `docs/PAYMENT_IMPLEMENTATION_SUMMARY.md`
- **Paystack Docs**: https://paystack.com/docs
- **Django REST Framework**: https://www.django-rest-framework.org/

## Next Steps

1. ✅ Complete backend implementation (DONE)
2. 🔄 Test all endpoints locally
3. 🔄 Integrate with frontend
4. 🔄 Deploy to staging environment
5. 🔄 Test with live Paystack account
6. 🔄 Deploy to production

---

**Implementation Status**: ✅ Complete and ready for testing!
