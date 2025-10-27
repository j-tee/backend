# 🔧 Fix: User Storefronts 404 Error

**Date:** October 7, 2025  
**Issue:** Frontend getting 404 error when loading user storefronts  
**Status:** ✅ ROOT CAUSE IDENTIFIED  

---

## ❌ The Problem

**Error in Screenshot:**
```
Request URL: http://localhost:8000/api/users/storefronts/
Status: 404 Not Found
```

**Root Cause:**
Frontend is calling the **wrong URL** - missing the `/accounts/` prefix!

---

## ✅ The Solution

### Correct URL

```
❌ WRONG:   http://localhost:8000/api/users/storefronts/
✅ CORRECT: http://localhost:8000/accounts/api/users/storefronts/
```

---

## 🔧 Frontend Fix

### Find Your API Service File

Look for where you make the storefronts API call. It might be in:
- `src/services/userService.ts`
- `src/services/authService.ts`
- `src/api/users.ts`
- Or similar

### Update the URL

**Before (Wrong):**
```typescript
// ❌ Missing /accounts/ prefix
export const getUserStorefronts = async () => {
  const response = await api.get('/api/users/storefronts/')
  return response.data
}
```

**After (Correct):**
```typescript
// ✅ Include /accounts/ prefix
export const getUserStorefronts = async () => {
  const response = await api.get('/accounts/api/users/storefronts/')
  return response.data
}
```

### Or Use Relative URL

If your API base URL is already configured:

**Option 1: Base URL includes /accounts/api/**
```typescript
// In axios config
const api = axios.create({
  baseURL: 'http://localhost:8000/accounts/api/'
})

// Then in service
export const getUserStorefronts = async () => {
  const response = await api.get('users/storefronts/')  // No leading slash
  return response.data
}
```

**Option 2: Base URL is just domain**
```typescript
// In axios config
const api = axios.create({
  baseURL: 'http://localhost:8000'
})

// Then in service
export const getUserStorefronts = async () => {
  const response = await api.get('/accounts/api/users/storefronts/')
  return response.data
}
```

---

## 🧪 Verify the Fix

### Test with curl (Backend)

```bash
# With authentication token
curl -H "Authorization: Token YOUR_TOKEN" \
  http://localhost:8000/accounts/api/users/storefronts/
```

**Expected Response:**
```json
{
  "storefronts": [
    {
      "id": "uuid-here",
      "name": "Main Store",
      "location": "Accra",
      "is_active": true
    }
  ],
  "count": 1
}
```

### Test in Browser Console

```javascript
// Open browser console on your frontend
fetch('http://localhost:8000/accounts/api/users/storefronts/', {
  headers: {
    'Authorization': 'Token YOUR_TOKEN_HERE'
  }
})
  .then(r => r.json())
  .then(console.log)
  .catch(console.error)
```

---

## 📋 All Accounts API Endpoints

For reference, here are the correct URLs for the accounts app:

```
✅ Correct URLs (with /accounts/ prefix):

Authentication:
POST   /accounts/api/auth/login/
POST   /accounts/api/auth/logout/
POST   /accounts/api/auth/register/
POST   /accounts/api/auth/change-password/
POST   /accounts/api/auth/password-reset/request/
POST   /accounts/api/auth/password-reset/confirm/

Users:
GET    /accounts/api/users/              - List users
GET    /accounts/api/users/{id}/         - Get user detail
GET    /accounts/api/users/me/           - Current user profile
GET    /accounts/api/users/storefronts/  - User's accessible storefronts ← THIS ONE!
POST   /accounts/api/users/{id}/activate/
POST   /accounts/api/users/{id}/deactivate/

Businesses:
GET    /accounts/api/businesses/
GET    /accounts/api/businesses/{id}/
POST   /accounts/api/businesses/

Business Memberships:
GET    /accounts/api/business-memberships/
GET    /accounts/api/business-memberships/{id}/
```

---

## 🔍 Why This Happens

Django app URLs are namespaced by app:

```python
# In accounts/urls.py
urlpatterns = [
    path('api/', include(router.urls)),  # ← Creates /accounts/api/...
    # ...
]
```

```python
# In main urls.py (app/urls.py)
urlpatterns = [
    path('accounts/', include('accounts.urls')),  # ← Adds /accounts/ prefix
    path('sales/', include('sales.urls')),        # ← Sales has /sales/ prefix
    path('inventory/', include('inventory.urls')), # ← Inventory has /inventory/
]
```

So the **full URL** is: `/accounts/` + `/api/` + `/users/storefronts/`

---

## ✅ Quick Checklist

- [ ] Find your frontend API service file
- [ ] Update storefronts URL to include `/accounts/`
- [ ] Check if baseURL is configured correctly
- [ ] Test the API call
- [ ] Verify storefronts load in UI
- [ ] Check browser network tab (should be 200 OK, not 404)

---

## 💡 Pro Tip: Environment Variables

Use environment variables for API URLs:

```typescript
// .env or .env.local
VITE_API_BASE_URL=http://localhost:8000

// In your API config
const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL
})

// Then use full paths
api.get('/accounts/api/users/storefronts/')
```

This makes it easy to switch between development, staging, and production!

---

**Status:** Root cause identified  
**Fix:** Update frontend URL to include `/accounts/` prefix  
**Expected Time:** 2 minutes  

---

**Need help?** Check the browser network tab to see the exact URL being called! 🔍
