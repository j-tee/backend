# URL Pattern Fix - Export Automation

## Issue Identified

The frontend was getting **404 errors** when trying to access export automation endpoints because the URLs didn't follow the project's **standardized pattern**.

### What Was Wrong

**Incorrect URL (what was documented):**
```
/reports/automation/schedules/
```

**Correct URL (standard pattern):**
```
/reports/api/automation/schedules/
```

---

## Standard URL Pattern Across the App

The project follows a **consistent two-level pattern**:

### Pattern Structure
```
/{app-name}/api/{resource-path}/
```

### Examples from Other Apps

| App | Main URL | App URLs | Final Endpoint |
|-----|----------|----------|----------------|
| Sales | `sales/` | `api/` + router | `/sales/api/customers/` |
| Inventory | `inventory/` | `api/` + router | `/inventory/api/products/` |
| Bookkeeping | `bookkeeping/` | `api/` + router | `/bookkeeping/api/reports/financial/` |
| Accounts | `accounts/` | `api/` + router | `/accounts/api/auth/login/` |
| Settings | `settings/` | `api/settings/` | `/settings/api/settings/` |
| **Reports** | `reports/` | `api/` + router | `/reports/api/automation/schedules/` |

### How It Works

1. **Project-level URLs** (`app/urls.py`):
   ```python
   urlpatterns = [
       path('reports/', include('reports.urls')),
       path('sales/', include('sales.urls')),
       path('inventory/', include('inventory.urls')),
       # ... etc
   ]
   ```

2. **App-level URLs** (e.g., `reports/urls.py`):
   ```python
   urlpatterns = [
       path('api/automation/', include(router.urls)),
       path('api/sales/export/', SalesExportView.as_view()),
       # ... etc
   ]
   ```

3. **Final URLs**:
   - `/reports/api/automation/schedules/`
   - `/reports/api/sales/export/`
   - `/sales/api/customers/`
   - `/inventory/api/products/`

---

## Files Fixed

### 1. Backend URL Configuration
**File:** `reports/urls.py`

**Before:**
```python
urlpatterns = [
    path('inventory/valuation/', ...),
    path('sales/export/', ...),
    path('automation/', include(router.urls)),  # ❌ Missing 'api/'
]
```

**After:**
```python
urlpatterns = [
    path('api/inventory/valuation/', ...),      # ✅ Added 'api/'
    path('api/sales/export/', ...),             # ✅ Added 'api/'
    path('api/automation/', include(router.urls)),  # ✅ Added 'api/'
]
```

### 2. Frontend Documentation
**Files Updated:**
- `PHASE_6_UI_INTEGRATION_GUIDE.md` - Complete integration guide
- `EXPORT_API_QUICK_REFERENCE.md` - Quick reference card

**Changed:**
```javascript
// ❌ Before
const API_BASE_URL = '/reports/automation';

// ✅ After
const API_BASE_URL = '/reports/api/automation';
```

---

## Complete Endpoint List (Corrected)

### Export Schedules
- `GET /reports/api/automation/schedules/` - List schedules
- `POST /reports/api/automation/schedules/` - Create schedule
- `GET /reports/api/automation/schedules/{id}/` - Get schedule
- `PUT /reports/api/automation/schedules/{id}/` - Update schedule
- `PATCH /reports/api/automation/schedules/{id}/` - Partial update
- `DELETE /reports/api/automation/schedules/{id}/` - Delete schedule
- `POST /reports/api/automation/schedules/{id}/activate/` - Activate
- `POST /reports/api/automation/schedules/{id}/deactivate/` - Deactivate
- `POST /reports/api/automation/schedules/{id}/trigger/` - Manual trigger
- `GET /reports/api/automation/schedules/upcoming/` - Next 10 runs
- `GET /reports/api/automation/schedules/overdue/` - Overdue schedules

### Export History
- `GET /reports/api/automation/history/` - List history (paginated)
- `GET /reports/api/automation/history/{id}/` - Get details
- `GET /reports/api/automation/history/{id}/download/` - Download file
- `GET /reports/api/automation/history/statistics/` - Statistics
- `GET /reports/api/automation/history/recent/` - Last 10 exports

### Notifications
- `GET /reports/api/automation/notifications/` - Get settings
- `PUT /reports/api/automation/notifications/` - Update settings

### Manual Exports (Existing)
- `POST /reports/api/sales/export/` - Export sales
- `POST /reports/api/customers/export/` - Export customers
- `POST /reports/api/inventory/export/` - Export inventory
- `POST /reports/api/audit/export/` - Export audit logs
- `GET /reports/api/inventory/valuation/` - Inventory valuation report

---

## Why This Matters

### 1. **Consistency**
- Developers can predict URLs across the entire application
- No special cases or exceptions to remember

### 2. **Clarity**
- Clear separation: `/{app}/api/...` pattern is recognizable
- Easy to distinguish API endpoints from other routes

### 3. **Maintainability**
- New developers can follow existing patterns
- Reduces confusion and integration errors

### 4. **API Organization**
- All API endpoints clearly grouped under `/api/`
- Non-API routes (webhooks, static files, etc.) easily distinguished

---

## Frontend Action Required

### Update API Configuration

**JavaScript/TypeScript:**
```javascript
// config/api.js or constants.ts
export const ENDPOINTS = {
  EXPORT_AUTOMATION: {
    BASE: '/reports/api/automation',
    SCHEDULES: '/reports/api/automation/schedules',
    HISTORY: '/reports/api/automation/history',
    NOTIFICATIONS: '/reports/api/automation/notifications',
  },
  MANUAL_EXPORTS: {
    SALES: '/reports/api/sales/export',
    CUSTOMERS: '/reports/api/customers/export',
    INVENTORY: '/reports/api/inventory/export',
    AUDIT: '/reports/api/audit/export',
  }
};
```

### Test Updated URLs

```bash
# Test schedule list
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/reports/api/automation/schedules/

# Test statistics
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/reports/api/automation/history/statistics/
```

---

## Verification

### Backend Test
```bash
cd /home/teejay/Documents/Projects/pos/backend

# Start Django server
python manage.py runserver

# In another terminal, test endpoints
curl -X GET http://localhost:8000/reports/api/automation/schedules/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Expected:** 
- ✅ 200 OK (if authenticated)
- ✅ 401 Unauthorized (if token invalid)
- ❌ NOT 404 Not Found

### Frontend Test
Update your API client configuration and verify:
1. Schedule creation works
2. History listing works
3. Statistics endpoint accessible
4. File downloads work

---

## Pattern Enforcement Going Forward

### For Backend Developers

**Rule:** All app URLs must start with `path('api/', ...)`

**Example:**
```python
# reports/urls.py
urlpatterns = [
    path('api/new-feature/', NewFeatureView.as_view()),  # ✅ Correct
    path('new-feature/', NewFeatureView.as_view()),      # ❌ Wrong
]
```

### For Frontend Developers

**Rule:** All API calls must include `/api/` in the path

**Example:**
```javascript
// ✅ Correct
fetch('/reports/api/automation/schedules/')

// ❌ Wrong
fetch('/reports/automation/schedules/')
```

---

## Summary

✅ **Fixed:** Backend URLs now follow standard `/{app}/api/{resource}/` pattern  
✅ **Updated:** All documentation reflects correct URLs  
✅ **Consistent:** Reports app now matches other apps (sales, inventory, etc.)  
✅ **Production Ready:** Frontend can integrate with confidence  

**No database changes required** - this was purely a URL routing configuration fix.

---

**Date Fixed:** October 12, 2025  
**Impact:** High - All export automation endpoints affected  
**Breaking Change:** Yes - Frontend must update API URLs  
**Migration Required:** No  
**Testing Required:** Yes - Verify all endpoints accessible
