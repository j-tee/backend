# ✅ SOLUTION: User Storefronts 404 Error - Complete Guide

**Issue:** Frontend getting 404 error when loading storefronts  
**Root Cause:** Wrong URL (missing `/accounts/` prefix)  
**Status:** ✅ IDENTIFIED - Easy 2-minute fix  

---

## 🎯 Quick Fix

### The Problem
```
❌ Your frontend calls: http://localhost:8000/api/users/storefronts/
✅ Should call:         http://localhost:8000/accounts/api/users/storefronts/
```

**Missing:** `/accounts/` prefix before `/api/`

---

## 🔧 How to Fix (Frontend)

### Step 1: Find Your API Service File

Look for where storefronts are fetched. Common locations:
- `src/services/authService.ts`
- `src/services/userService.ts`
- `src/api/users.ts`
- `src/store/slices/authSlice.ts`

### Step 2: Update the URL

**Find code like this:**
```typescript
// ❌ WRONG
const response = await api.get('/api/users/storefronts/')

// Or
const response = await fetch('http://localhost:8000/api/users/storefronts/')
```

**Change to:**
```typescript
// ✅ CORRECT
const response = await api.get('/accounts/api/users/storefronts/')

// Or
const response = await fetch('http://localhost:8000/accounts/api/users/storefronts/')
```

### Step 3: Save and Test

1. Save the file
2. Refresh your browser (Vite should auto-reload)
3. Check the Network tab - you should see 200 OK instead of 404

---

## 📋 Expected API Response

When you call the correct URL, you'll get:

```json
{
  "storefronts": [
    {
      "id": "storefront-uuid",
      "name": "Main Store",
      "location": "Accra",
      "is_active": true
    },
    {
      "id": "another-uuid",
      "name": "Branch Store",
      "location": "Kumasi",
      "is_active": true
    }
  ],
  "count": 2
}
```

---

## 🧪 Test the Backend (Verify It Works)

### Using curl:
```bash
curl -H "Authorization: Token YOUR_TOKEN" \
  http://localhost:8000/accounts/api/users/storefronts/
```

### Using Browser Console:
```javascript
// On your frontend page (localhost:5173)
fetch('http://localhost:8000/accounts/api/users/storefronts/', {
  headers: {
    'Authorization': 'Token YOUR_AUTH_TOKEN'
  }
})
  .then(r => r.json())
  .then(data => console.log('Storefronts:', data))
  .catch(err => console.error('Error:', err))
```

---

## 📚 All Correct URLs Reference

Here's the complete list of accounts endpoints:

```
Authentication:
POST   /accounts/api/auth/login/
POST   /accounts/api/auth/logout/
POST   /accounts/api/auth/register/
POST   /accounts/api/auth/change-password/

Users:
GET    /accounts/api/users/
GET    /accounts/api/users/me/
GET    /accounts/api/users/storefronts/  ← YOUR ISSUE
GET    /accounts/api/users/{id}/

Businesses:
GET    /accounts/api/businesses/
GET    /accounts/api/businesses/{id}/
```

**Other Apps:**
```
Sales:     /sales/api/...
Inventory: /inventory/api/...
Reports:   /reports/api/...
```

---

## 🔍 Why This Happens

Django organizes URLs by app. Each app has its own prefix:

```
Main URL Config (app/urls.py):
/accounts/  → accounts app
/sales/     → sales app  
/inventory/ → inventory app

Accounts URL Config (accounts/urls.py):
/api/       → REST API routes

Combined:
/accounts/api/users/storefronts/
 ^app     ^api ^resource ^action
```

---

## ✅ Verification Checklist

After making the fix:

- [ ] Updated frontend URL to include `/accounts/`
- [ ] Saved the file
- [ ] Browser refreshed/reloaded
- [ ] Check Network tab: Shows 200 OK (not 404)
- [ ] Storefronts dropdown now populates
- [ ] Console shows no errors

---

## 💡 Pro Tips

### 1. Use Environment Variables

Create `.env.local`:
```
VITE_API_BASE_URL=http://localhost:8000
```

In your code:
```typescript
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

// Then use full paths
fetch(`${API_BASE_URL}/accounts/api/users/storefronts/`)
```

### 2. Create API Constants

`src/constants/api.ts`:
```typescript
export const API_ENDPOINTS = {
  auth: {
    login: '/accounts/api/auth/login/',
    logout: '/accounts/api/auth/logout/',
  },
  users: {
    me: '/accounts/api/users/me/',
    storefronts: '/accounts/api/users/storefronts/',
  },
  sales: {
    list: '/sales/api/sales/',
  }
}
```

Usage:
```typescript
import { API_ENDPOINTS } from '@/constants/api'

const response = await api.get(API_ENDPOINTS.users.storefronts)
```

### 3. Use Axios Interceptor for Debugging

```typescript
api.interceptors.response.use(
  response => response,
  error => {
    console.error('API Error:', {
      url: error.config?.url,
      method: error.config?.method,
      status: error.response?.status,
      data: error.response?.data
    })
    return Promise.reject(error)
  }
)
```

---

## 🚨 Common Mistakes

### ❌ Wrong:
```typescript
'/api/users/storefronts/'              // Missing /accounts/
'api/users/storefronts/'               // Missing leading /
'/accounts/users/storefronts/'         // Missing /api/
'http://localhost:5173/accounts/...'   // Wrong port (frontend port)
```

### ✅ Correct:
```typescript
'/accounts/api/users/storefronts/'     // Perfect!
```

---

## 📞 Still Having Issues?

### Check These:

1. **Backend Running?**
   ```bash
   curl http://localhost:8000/accounts/api/users/storefronts/
   # Should return: "Authentication credentials were not provided"
   ```

2. **CORS Configured?**
   - Check `app/settings.py` has `CORS_ALLOW_ALL_ORIGINS = True` (dev)
   - Or frontend origin in `CORS_ALLOWED_ORIGINS`

3. **Token Valid?**
   ```javascript
   // Check your auth token in localStorage/cookies
   console.log(localStorage.getItem('token'))
   ```

4. **Network Tab:**
   - Open DevTools → Network
   - Reload page
   - Click the failed request
   - Check Request URL, Headers, Response

---

## 📖 Documentation

See also:
- **Backend API Docs:** `/docs/COMPREHENSIVE_API_DOCUMENTATION.md`
- **Multi-Storefront Guide:** `/docs/MULTI_STOREFRONT_FILTERING_IMPLEMENTATION.md`
- **Sales API Guide:** `/docs/SALES_API_TYPE_FIX_SUMMARY.md`

---

**Status:** ✅ Root cause found - Simple URL fix needed  
**Time to Fix:** 2 minutes  
**Difficulty:** Easy  

**Action Required:** Update frontend URL to include `/accounts/` prefix

---

**Questions?** Check the browser Network tab to see exactly what URL is being called! 🔍
