# Security Fixes Implementation Guide

## 🚨 CRITICAL: Immediate Actions Required

### 1. Rotate ALL Exposed Credentials (DO THIS FIRST!)

Your `.env.development` file was exposed in our conversation. These credentials are now compromised:

#### Database
```bash
# Change PostgreSQL password
sudo -u postgres psql
ALTER USER postgres WITH PASSWORD 'NEW_SECURE_PASSWORD';
# Update .env.development with new password
```

#### Django Secret Key
```bash
python scripts/generate_secure_keys.py
# Copy new SECRET_KEY to .env.development
```

#### Email (Gmail App Password)
1. Go to: https://myaccount.google.com/apppasswords
2. Revoke old app password
3. Generate new app-specific password
4. Update EMAIL_HOST_PASSWORD in .env.development

#### OpenAI API Key
1. Go to: https://platform.openai.com/api-keys
2. Revoke exposed key: `sk-proj-pZdqd...`
3. Generate new key
4. Update OPENAI_API_KEY in .env.development

#### Paystack Keys (If Live Keys Were Used)
1. Go to: https://dashboard.paystack.com/settings/developer
2. Regenerate keys
3. Update .env.development

---

## 📋 Implemented Fixes

### 1. Row-Level Security (RLS)
**File**: `deployment/enable_rls.sql`

Implements PostgreSQL RLS for defense-in-depth security:
- Database-level business isolation
- Automatic filtering on all queries
- Protection against application-level bugs

**Deployment**:
```bash
psql -U postgres -d pos_db -f deployment/enable_rls.sql
```

**Testing**:
```python
# Should only return user's business products
products = Product.objects.all()  # RLS applies automatically
```

---

### 2. Business Scoping Middleware
**File**: `app/middleware.py`

- Sets PostgreSQL session variables for RLS
- Validates production configurations
- Prevents accidental deployment with test keys

**Activation**: Add to `settings.py`:
```python
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'app.middleware.EnvironmentSecurityMiddleware',  # Add this
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'app.middleware.BusinessScopingMiddleware',  # Add this
    # ... rest of middleware
]
```

---

### 3. AI Features - GDPR Compliance
**File**: `ai_features/utils.py`

Implements:
- **PII Sanitization**: Removes sensitive data before storage
- **Credit Reservation**: Prevents race conditions and overdrafts
- **Budget Caps**: Enforces daily/monthly limits
- **Data Retention**: Auto-deletion after 90 days
- **Right to Erasure**: GDPR deletion handler

**Usage**:
```python
from ai_features.utils import process_ai_request_with_reservation

result = process_ai_request_with_reservation(
    business=business,
    feature='customer_insight',
    estimated_cost=Decimal('2.50'),
    processor_func=lambda: call_openai_api(...)
)
```

**Celery Task** (add to `celery.py`):
```python
from ai_features.utils import cleanup_expired_ai_data

@periodic_task(run_every=timedelta(days=1))
def cleanup_ai_data():
    cleanup_expired_ai_data()
```

---

### 4. Payment Gateway Failover
**File**: `subscriptions/payment_gateway.py`

Implements:
- **Automatic Failover**: Tries alternative gateways if primary fails
- **Circuit Breaker**: Prevents repeated calls to failing gateways
- **Smart Routing**: Selects best gateway based on business/amount

**Usage**:
```python
from subscriptions.payment_gateway import payment_router

result = payment_router.process_payment_with_failover(
    business=business,
    amount=Decimal('100.00'),
    currency='GHS',
    metadata={'subscription_id': str(subscription.id)}
)
```

---

### 5. Secure Key Generator
**File**: `scripts/generate_secure_keys.py`

Generates cryptographically secure keys:
```bash
python scripts/generate_secure_keys.py
```

---

## 🔧 Configuration Changes Needed

### 1. Update `settings.py`

Add new settings:
```python
# GDPR Compliance
ANONYMIZATION_SALT = config('ANONYMIZATION_SALT', default=SECRET_KEY)

# AI Budget Caps (already exists, but verify)
AI_BUDGET_CAPS = {
    'per_business_daily': Decimal('10.0'),
    'per_business_monthly': Decimal('200.0'),
}

# Add middleware
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'app.middleware.EnvironmentSecurityMiddleware',  # NEW
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'app.middleware.BusinessScopingMiddleware',  # NEW
    # ... existing middleware
]
```

### 2. Add to `.env.example`
```bash
# Add to template
ANONYMIZATION_SALT=generate_using_scripts_generate_secure_keys
```

### 3. Update `requirements.txt`
```bash
# Add if not present
django-cryptography==1.1
```

---

## 🧪 Testing Plan

### 1. Test RLS
```bash
python manage.py test tests.test_business_isolation_security
```

### 2. Test AI Credit Reservation
```python
# Create test
def test_concurrent_ai_requests():
    # Simulate 2 concurrent requests with GHS 5 balance
    # Both should not succeed (would cause overdraft)
    pass
```

### 3. Test Payment Failover
```python
def test_payment_failover():
    # Mock Paystack failure
    # Should automatically try Stripe
    pass
```

### 4. Test GDPR Deletion
```python
def test_gdpr_deletion():
    # Verify PII is removed
    # Verify billing data is retained
    pass
```

---

## 📊 Monitoring & Alerts

### 1. Add Logging
```python
# In settings.py
LOGGING['loggers']['security'] = {
    'handlers': ['console', 'file'],
    'level': 'WARNING',
    'propagate': False,
}
```

### 2. Monitor Circuit Breaker
```python
# Add to monitoring dashboard
from subscriptions.payment_gateway import circuit_breaker
circuit_breaker.failures  # Check failure counts
```

### 3. Alert on Security Issues
- Failed RLS queries
- Budget cap violations
- Payment gateway failures
- GDPR deletion requests

---

## 🚀 Deployment Checklist

- [ ] Rotate ALL exposed credentials
- [ ] Add new files to repository
- [ ] Update `settings.py` with middleware
- [ ] Update `.env.example` template
- [ ] Run `enable_rls.sql` on database
- [ ] Run migrations (if needed)
- [ ] Test RLS with security tests
- [ ] Test AI credit reservation
- [ ] Test payment failover
- [ ] Configure monitoring alerts
- [ ] Update documentation
- [ ] Train team on new security features

---

## 📞 Emergency Procedures

### If Data Breach Suspected:
1. **Immediately disable RLS**: `ALTER TABLE products DISABLE ROW LEVEL SECURITY;`
2. Investigate logs: `grep "SECURITY" logs/django.log`
3. Check affected businesses
4. Notify affected users within 72 hours (GDPR)
5. Document incident
6. Fix vulnerability
7. Re-enable RLS with fixes

### If Payment Gateway Down:
1. Check circuit breaker status
2. Manually failover if needed
3. Monitor alternative gateway
4. Notify platform owner

### If AI Budget Exhausted:
1. Check if legitimate spike or abuse
2. Temporarily increase caps if legitimate
3. Investigate abuse if suspicious
4. Alert affected businesses

---

## 🔐 Security Best Practices Going Forward

1. **Never commit secrets** - Use `.env` files
2. **Rotate keys regularly** - Every 90 days minimum
3. **Monitor logs** - Set up alerts for security events
4. **Test security** - Run security tests in CI/CD
5. **Audit access** - Review who has database access
6. **Encrypt data** - Use `django-cryptography` for PII
7. **Document changes** - Update this file for new security features

---

## 📚 Additional Resources

- [Django Security Checklist](https://docs.djangoproject.com/en/stable/topics/security/)
- [PostgreSQL RLS Documentation](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [GDPR Compliance Guide](https://gdpr.eu/)

---

**Last Updated**: November 25, 2025
**Reviewed By**: Security Team
**Next Review**: February 25, 2026
