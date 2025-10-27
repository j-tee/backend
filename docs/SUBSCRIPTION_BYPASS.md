# Subscription Bypass for Development

## Overview

The subscription bypass feature allows you to disable subscription checks during development, making it easier to test features without worrying about subscription status.

## Quick Start

### Automatic Bypass (Recommended for Development)

The bypass is **automatically enabled** when `DEBUG=True` in your settings. No additional configuration needed!

```python
# In settings.py
DEBUG = True  # Subscription checks are automatically bypassed
```

### Manual Configuration

If you want to explicitly control the bypass independently of DEBUG mode:

**Option 1: Environment Variable**

Add to your `.env.development` file:
```bash
BYPASS_SUBSCRIPTION_CHECK=True
```

**Option 2: Direct Setting**

Add to your `settings.py`:
```python
BYPASS_SUBSCRIPTION_CHECK = True
```

## How It Works

### Setting Configuration

Located in `app/settings.py`:
```python
# Subscription bypass for development
# Set to True to bypass all subscription checks during development
BYPASS_SUBSCRIPTION_CHECK = config('BYPASS_SUBSCRIPTION_CHECK', default=DEBUG, cast=bool)
```

**Default Behavior:**
- `DEBUG=True` → Subscription checks are bypassed ✅
- `DEBUG=False` → Subscription checks are enforced ⚠️

### User Model Method

Added to `accounts/models.py` - `User.has_active_subscription()`:

```python
def has_active_subscription(self):
    """
    Check if user has an active subscription.
    Returns True if BYPASS_SUBSCRIPTION_CHECK is enabled or user has active subscription.
    """
    from django.conf import settings
    
    # Bypass check if setting is enabled (typically in DEBUG mode)
    if getattr(settings, 'BYPASS_SUBSCRIPTION_CHECK', False):
        return True
    
    # Check for actual active subscription
    # ... rest of implementation
```

## Usage in Code

### Checking Subscription Status

```python
# In your views or business logic
from django.contrib.auth import get_user_model

User = get_user_model()

def my_view(request):
    user = request.user
    
    # This automatically respects the bypass setting
    if not user.has_active_subscription():
        return Response({
            'error': 'Active subscription required'
        }, status=403)
    
    # Continue with your logic
    ...
```

### In ViewSets or API Views

```python
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status

class MyViewSet(viewsets.ModelViewSet):
    def create(self, request):
        # Check subscription
        if not request.user.has_active_subscription():
            return Response({
                'error': 'You need an active subscription to create items'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Your create logic here
        ...
```

## Testing

### Development Testing

With `DEBUG=True` (default bypass enabled):
```bash
# All subscription checks will pass
curl -X POST http://localhost:8000/api/sales/ \
  -H "Authorization: Bearer {token}" \
  -d '{"customer": "123", ...}'

# ✅ Works even without active subscription
```

### Production-Like Testing

To test with actual subscription enforcement in development:

**Method 1: Environment Variable**
```bash
# In your .env.development
DEBUG=True
BYPASS_SUBSCRIPTION_CHECK=False  # Explicitly disable bypass
```

**Method 2: Temporary Code Change**
```python
# In settings.py (temporary for testing)
BYPASS_SUBSCRIPTION_CHECK = False  # Force enforcement
```

Then test:
```python
# This will now check for real subscriptions
if not user.has_active_subscription():
    # Will fail if user has no active subscription
    ...
```

## Production Deployment

### Important: Production Settings

**CRITICAL:** Ensure these settings for production:

```python
# In production settings or .env.production
DEBUG = False
BYPASS_SUBSCRIPTION_CHECK = False  # Optional - will be False by default
```

The bypass will automatically be disabled when `DEBUG=False`.

### Verification

Before deploying to production, verify:

1. **Check Settings:**
```python
# In Django shell
from django.conf import settings

print(f"DEBUG: {settings.DEBUG}")
print(f"BYPASS_SUBSCRIPTION_CHECK: {settings.BYPASS_SUBSCRIPTION_CHECK}")

# Expected in production:
# DEBUG: False
# BYPASS_SUBSCRIPTION_CHECK: False
```

2. **Test Subscription Enforcement:**
```python
from accounts.models import User

user = User.objects.first()
print(f"Has active subscription: {user.has_active_subscription()}")

# Should return False if user has no active subscription
```

## Environment-Specific Configuration

### .env.development
```bash
DEBUG=True
# BYPASS_SUBSCRIPTION_CHECK=True  # Optional - True by default when DEBUG=True
```

### .env.production
```bash
DEBUG=False
BYPASS_SUBSCRIPTION_CHECK=False  # Explicit enforcement
```

### .env.testing
```bash
DEBUG=True
BYPASS_SUBSCRIPTION_CHECK=True  # Allow tests to run without subscriptions
```

## Migration Guide

### Adding Subscription Checks to Existing Code

If you want to add subscription checks to an existing view:

**Before:**
```python
class SaleViewSet(viewsets.ModelViewSet):
    def create(self, request):
        # No subscription check
        sale = Sale.objects.create(...)
        return Response(serializer.data)
```

**After:**
```python
class SaleViewSet(viewsets.ModelViewSet):
    def create(self, request):
        # Add subscription check
        if not request.user.has_active_subscription():
            return Response({
                'error': 'Active subscription required to create sales',
                'code': 'SUBSCRIPTION_REQUIRED'
            }, status=status.HTTP_403_FORBIDDEN)
        
        sale = Sale.objects.create(...)
        return Response(serializer.data)
```

During development with `DEBUG=True`, the check is bypassed automatically.

## Troubleshooting

### Issue: Bypass Not Working

**Problem:** Subscription checks still failing even with `DEBUG=True`

**Solution:**
```bash
# 1. Verify settings
python manage.py shell
>>> from django.conf import settings
>>> print(settings.BYPASS_SUBSCRIPTION_CHECK)
True  # Should be True

# 2. Restart Django server
# Changes to settings.py require server restart

# 3. Clear any cached settings
python manage.py shell
>>> from django.core.cache import cache
>>> cache.clear()
```

### Issue: Bypass Enabled in Production

**Problem:** Subscription checks not working in production

**Solution:**
```python
# Check production settings
from django.conf import settings

assert not settings.DEBUG, "DEBUG should be False in production"
assert not settings.BYPASS_SUBSCRIPTION_CHECK, "Bypass should be disabled"
```

## Advanced: Custom Permission Classes

You can also create a custom permission class:

```python
# accounts/permissions.py
from rest_framework import permissions
from django.conf import settings

class HasActiveSubscription(permissions.BasePermission):
    """
    Permission check for active subscription.
    Automatically bypassed when BYPASS_SUBSCRIPTION_CHECK is True.
    """
    
    message = 'Active subscription required to access this resource.'
    
    def has_permission(self, request, view):
        # Bypass check in development
        if getattr(settings, 'BYPASS_SUBSCRIPTION_CHECK', False):
            return True
        
        # Check for active subscription
        return request.user.is_authenticated and request.user.has_active_subscription()
```

**Usage:**
```python
from accounts.permissions import HasActiveSubscription

class SaleViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, HasActiveSubscription]
    
    # All actions now require active subscription
    # (automatically bypassed in development)
```

## Summary

✅ **Automatic Bypass** - Enabled when `DEBUG=True`  
✅ **Easy Configuration** - Single environment variable  
✅ **Production Safe** - Disabled automatically in production  
✅ **Flexible** - Can be overridden per environment  
✅ **Developer Friendly** - No subscription setup needed for development  

The bypass feature allows you to:
- Develop without creating test subscriptions
- Test all features without subscription restrictions
- Deploy to production with automatic enforcement
- Easily toggle between modes for testing

---

**Implementation Date:** January 2025  
**Status:** ✅ Active and Ready to Use  
**Default:** Enabled in development (`DEBUG=True`)
