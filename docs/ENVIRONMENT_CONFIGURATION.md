# Environment Configuration Guide

## Overview

The POS backend uses environment variables for configuration, with separate files for different environments. The Paystack payment gateway keys **must** be set in environment variables - they are not hardcoded in the codebase.

## Environment Files

### Available Environment Files

1. **`.env.development`** - For local development (uses test keys)
2. **`.env.production`** - For production deployment (requires live keys)
3. **`.env.template`** - Template with all available variables

### How Django Loads Environment Files

The application uses `python-decouple` to load environment variables. By default:

- **Development**: Loads `.env.development` (or falls back to `.env`)
- **Production**: Set `DJANGO_ENV_FILE=.env.production` environment variable

You can also override this:
```bash
export DJANGO_ENV_FILE=.env.production
python manage.py runserver
```

## Paystack Configuration

### Required Variables

The following Paystack variables **MUST** be set in your environment file:

```bash
# Paystack Keys (REQUIRED)
PAYSTACK_SECRET_KEY=sk_test_your_secret_key_here
PAYSTACK_PUBLIC_KEY=pk_test_your_public_key_here

# App Name for shared account routing (REQUIRED)
PAYSTACK_APP_NAME=pos
```

### Development Setup (`.env.development`)

For development, use the provided test keys:

```bash
# Development/Test Keys
PAYSTACK_SECRET_KEY=sk_test_16b164b455153a23804423ec0198476b3c4ca206
PAYSTACK_PUBLIC_KEY=pk_test_5309f5af38555dbf7ef47287822ef2c6d3019b9d
PAYSTACK_APP_NAME=pos
```

These test keys are already configured in `.env.development`.

### Production Setup (`.env.production`)

For production, you **MUST** replace the placeholder values with your live Paystack keys:

```bash
# Production/Live Keys - GET FROM PAYSTACK DASHBOARD
PAYSTACK_SECRET_KEY=sk_live_your_actual_live_secret_key
PAYSTACK_PUBLIC_KEY=pk_live_your_actual_live_public_key
PAYSTACK_APP_NAME=pos
```

⚠️ **IMPORTANT**: Never commit your live keys to version control!

### Getting Your Paystack Keys

1. **Login to Paystack Dashboard**: https://dashboard.paystack.com
2. **Navigate to**: Settings → API Keys & Webhooks
3. **Copy Your Keys**:
   - **Test Mode**: Use for development/testing
   - **Live Mode**: Use for production

### Shared Account Routing

Since the Paystack account is shared across multiple applications, the `PAYSTACK_APP_NAME` is critical:

```bash
# This identifies your app in webhook callbacks
PAYSTACK_APP_NAME=pos
```

All payment transactions include `app_name: 'pos'` in metadata, and the webhook handler filters events by this value.

## Django Settings Integration

The `app/settings.py` file reads these variables:

```python
from decouple import config

# Paystack Configuration
PAYSTACK_SECRET_KEY = config('PAYSTACK_SECRET_KEY')  # Required - no default
PAYSTACK_PUBLIC_KEY = config('PAYSTACK_PUBLIC_KEY')  # Required - no default
PAYSTACK_APP_NAME = config('PAYSTACK_APP_NAME', default='pos')  # Has default
```

**Note**: `PAYSTACK_SECRET_KEY` and `PAYSTACK_PUBLIC_KEY` have **no default values** - if they're not set in your environment file, Django will raise an error on startup.

## Verifying Configuration

### Check if Keys are Loaded

```bash
# Activate virtual environment
source venv/bin/activate

# Start Django shell
python manage.py shell
```

```python
from django.conf import settings

# Verify keys are loaded
print(f"Secret Key: {settings.PAYSTACK_SECRET_KEY[:10]}...")
print(f"Public Key: {settings.PAYSTACK_PUBLIC_KEY[:10]}...")
print(f"App Name: {settings.PAYSTACK_APP_NAME}")
```

### Test Paystack Connection

```bash
# Activate virtual environment
source venv/bin/activate

# Start Django shell
python manage.py shell
```

```python
from subscriptions.payment_gateways import PaystackGateway

gateway = PaystackGateway()
result = gateway.initialize_transaction(
    email='test@example.com',
    amount=100.00,
    metadata={'test': True, 'app_name': 'pos'}
)

print(result)
# Should return: {'authorization_url': '...', 'access_code': '...', 'reference': '...'}
```

## Other Important Environment Variables

### Frontend Configuration

```bash
# Frontend URL for payment callbacks
FRONTEND_URL=http://localhost:5173

# CORS allowed origins
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
```

### Database Configuration

```bash
DB_NAME=pos_db
DB_USER=postgres
DB_PASSWORD=your_secure_password
DB_HOST=localhost
DB_PORT=5432
```

### Django Settings

```bash
SECRET_KEY=your-django-secret-key
DEBUG=true
ALLOWED_HOSTS=localhost,127.0.0.1
```

### Email Configuration

```bash
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_HOST_USER=your-email@example.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=your-email@example.com
```

## Environment File Security

### Development

- ✅ `.env.development` can contain test keys
- ✅ Can be committed to version control (test keys only)
- ⚠️ Never commit if it contains live keys

### Production

- ❌ **NEVER** commit `.env.production` with live keys
- ✅ Use `.env.production.example` as a template
- ✅ Set actual keys on the server directly
- ✅ Restrict file permissions: `chmod 600 .env.production`

### Git Configuration

Ensure `.env.production` is in `.gitignore`:

```gitignore
# Environment files with sensitive data
.env.production
.env.local
.env

# Keep templates/examples
!.env.template
!.env.example
!.env.development  # Only if using test keys
```

## Deployment Checklist

### Pre-Deployment

- [ ] Copy `.env.production.example` to `.env.production`
- [ ] Set all required Paystack keys (live keys)
- [ ] Set `PAYSTACK_APP_NAME=pos`
- [ ] Update `FRONTEND_URL` to production domain
- [ ] Set `DEBUG=false`
- [ ] Update `ALLOWED_HOSTS`
- [ ] Set secure `SECRET_KEY`
- [ ] Configure production database credentials

### Post-Deployment

- [ ] Verify keys are loaded: `python manage.py shell`
- [ ] Test Paystack connection
- [ ] Configure webhook URL in Paystack dashboard
- [ ] Test payment flow with test card
- [ ] Monitor logs for any configuration errors

## Troubleshooting

### Error: "PAYSTACK_SECRET_KEY not found"

**Cause**: Environment variable not set

**Solution**:
1. Check your environment file (`.env.development` or `.env.production`)
2. Ensure `PAYSTACK_SECRET_KEY=sk_test_...` or `sk_live_...` is set
3. Restart Django server after changes

### Error: "Invalid Paystack keys"

**Cause**: Using wrong environment keys (test vs live)

**Solution**:
1. For development: Use `sk_test_...` keys
2. For production: Use `sk_live_...` keys
3. Verify keys match in Paystack dashboard

### Webhook Signature Validation Failing

**Cause**: Wrong `PAYSTACK_SECRET_KEY` in environment

**Solution**:
1. Verify `PAYSTACK_SECRET_KEY` matches Paystack dashboard
2. Ensure you're using the correct environment (test vs live)
3. Check webhook logs in Paystack dashboard

### Payment Not Working in Production

**Checklist**:
- [ ] Using live keys (`sk_live_...`, `pk_live_...`)
- [ ] Webhook URL configured in Paystack dashboard
- [ ] Webhook URL is accessible (HTTPS)
- [ ] `PAYSTACK_APP_NAME` matches metadata
- [ ] Frontend has correct public key

## Testing

### Test Environment Variables

Create a `.env.test` for running tests:

```bash
# Copy development config
cp .env.development .env.test

# Or use test-specific values
PAYSTACK_SECRET_KEY=sk_test_16b164b455153a23804423ec0198476b3c4ca206
PAYSTACK_PUBLIC_KEY=pk_test_5309f5af38555dbf7ef47287822ef2c6d3019b9d
PAYSTACK_APP_NAME=pos
DB_NAME=test_pos_db
```

Run tests with test environment:

```bash
# Activate virtual environment
source venv/bin/activate

# Run tests
DJANGO_ENV_FILE=.env.test python manage.py test
```

## Best Practices

1. **Never hardcode keys** - Always use environment variables
2. **Use test keys in development** - Reserve live keys for production only
3. **Restrict file permissions** - `chmod 600 .env.production`
4. **Rotate keys regularly** - Update keys periodically for security
5. **Monitor key usage** - Check Paystack dashboard for unusual activity
6. **Use different keys per environment** - Separate test and live keys
7. **Document required variables** - Keep `.env.template` updated

## Support

For environment configuration issues:
- Check Django logs: `tail -f logs/django.log`
- Verify variable loading: `python manage.py shell`
- Test Paystack connection: See "Test Paystack Connection" above

For Paystack key issues:
- Paystack Dashboard: https://dashboard.paystack.com
- Paystack Support: support@paystack.com
- Paystack Docs: https://paystack.com/docs
