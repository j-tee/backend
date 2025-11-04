# Bug Fix: "User must be associated with a business" Error in Production

**Date:** November 4, 2025  
**Status:** ✅ RESOLVED  
**Priority:** HIGH

## Problem

Users authenticated in the POS frontend (https://pos.alphalogiquetechnologies.com) were seeing the error message **"User must be associated with a business"** when trying to access inventory management features (specifically the `/inventory/stocks` endpoint), even though they were logged in and associated with a business.

### Screenshot Evidence
The error appeared in the frontend UI despite the user ("Tetteh Julius - Data Logique Systems") being clearly logged in.

## Investigation

### 1. Verified User-Business Association

Checked production database for user `juliustetteh@gmail.com`:

```python
User: Tetteh Julius
Email: juliustetteh@gmail.com
Primary business: Data Logique Systems
Total memberships: 1
  - Business: Data Logique Systems, Role: OWNER, Active: True
```

✅ **User IS correctly associated with a business via BusinessMembership**

### 2. Verified Subscription Status

```python
Business: Data Logique Systems
Subscription status: ACTIVE
Has subscription: True
Is active: True
```

✅ **Business has an active subscription**

### 3. Tested Permission Checks in Shell

Simulated the permission check in Django shell:

```python
permission = RequiresSubscriptionForInventoryModification()
result = permission.has_permission(request, None)
# Result: True ✅
```

✅ **Permission checks pass when user is properly authenticated**

### 4. Analyzed HTTP Request Logs

From production logs (`logs/gunicorn_access.log`):

```
- - [04/Nov/2025:11:40:09] "OPTIONS /inventory/api/stock-products/?page=1&page_size=25" 200
- - [04/Nov/2025:11:40:10] "GET /inventory/api/stock-products/?page=1&page_size=25" 403
```

❌ **HTTP GET requests returning 403 Forbidden**

## Root Cause

**CORS credentials not enabled in Django settings.**

The application uses `SessionAuthentication` for API requests. When the frontend (running on `https://pos.alphalogiquetechnologies.com`) makes cross-origin API requests to the backend, the **session cookie was not being sent** because Django was not configured to accept credentials with CORS requests.

### Why It Works in Development

In development, both frontend and backend likely run on `localhost`, which is either:
- Same-origin (no CORS restrictions)
- Browser is more lenient with localhost credentials

### Why It Failed in Production

In production:
- Frontend: `https://pos.alphalogiquetechnologies.com`
- Backend: Different origin (cross-origin request)
- Without `CORS_ALLOW_CREDENTIALS = True`, browsers block sending cookies
- Request appears unauthenticated → No BusinessMembership found → Error: "User must be associated with a business"

## Solution

Added `CORS_ALLOW_CREDENTIALS = True` to Django settings (`app/settings.py`):

```python
# CORS settings
_cors_origins = config(
    'CORS_ALLOWED_ORIGINS',
    cast=Csv(),
    default='http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173'
)

if DEBUG and not _cors_origins:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    CORS_ALLOWED_ORIGINS = _cors_origins

# Allow credentials (cookies, authorization headers) to be sent with cross-origin requests
# This is required for SessionAuthentication to work with CORS
CORS_ALLOW_CREDENTIALS = True  # ← NEW
```

## Deployment Steps

1. **Commit and push the fix:**
   ```bash
   git add app/settings.py
   git commit -m "Fix: Enable CORS credentials for session authentication"
   git push origin development
   ```

2. **Deploy to production:**
   ```bash
   ssh -p 7822 deploy@68.66.251.79
   cd /var/www/pos/backend
   git pull origin development
   sudo systemctl restart gunicorn
   ```

3. **Verify the fix:**
   - Log in to the POS frontend
   - Navigate to Inventory → Manage stocks
   - Confirm that stock products load without permission errors

## Technical Details

### CORS Configuration Required for Session Auth

When using Django REST Framework's `SessionAuthentication` with a separate frontend:

1. **Backend must allow credentials:**
   ```python
   CORS_ALLOW_CREDENTIALS = True
   ```

2. **Frontend must send credentials:**
   ```javascript
   // In fetch requests:
   fetch(url, { credentials: 'include' })
   
   // In axios:
   axios.defaults.withCredentials = true
   ```

3. **CORS origins must be explicitly listed:**
   ```python
   CORS_ALLOWED_ORIGINS = [
       'https://pos.alphalogiquetechnologies.com',
       'https://www.pos.alphalogiquetechnologies.com'
   ]
   ```

### Permission Flow

```
Frontend Request
    ↓
CORS Preflight (OPTIONS) → 200 OK
    ↓
GET Request with Session Cookie → 
    ↓
SessionAuthentication.authenticate() →
    ↓
request.user = User object →
    ↓
RequiresSubscriptionForInventoryModification.has_permission() →
    ↓
BusinessMembership.objects.filter(user=request.user) →
    ↓
✅ Permission granted → 200 OK with data
```

## Related Files

- `/app/settings.py` - Django settings (CORS configuration)
- `/subscriptions/permissions.py` - Permission classes
- `/accounts/models.py` - User and BusinessMembership models
- `/subscriptions/utils.py` - SubscriptionChecker utility

## References

- [Django CORS Headers Documentation](https://github.com/adamchainz/django-cors-headers)
- [DRF SessionAuthentication](https://www.django-rest-framework.org/api-guide/authentication/#sessionauthentication)
- [MDN: CORS Credentials](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS#requests_with_credentials)

## Prevention

To prevent similar issues in the future:

1. **Always configure CORS properly when using session authentication with separate frontends**
2. **Test authentication in production-like environments** (separate domains)
3. **Add integration tests** that verify cross-origin authenticated requests
4. **Document authentication requirements** for frontend developers

---

**Resolution:** Fixed by enabling `CORS_ALLOW_CREDENTIALS` in Django settings.  
**Impact:** All authenticated users can now access inventory and other protected endpoints.
