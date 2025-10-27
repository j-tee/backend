# ✅ Multi-Storefront Filtering Implementation Complete

**Date:** October 6, 2025  
**Feature:** Permission-based multi-storefront sales filtering  
**Status:** ✅ Implemented & Ready for Testing

---

## 🎯 Overview

Implemented a comprehensive multi-storefront filtering system that:
1. Shows sales from ALL accessible storefronts by default
2. Allows optional filtering to specific storefronts
3. Enforces permission-based access control
4. Maintains backward compatibility

---

## 🔧 Backend Changes

### 1. User Model Enhancements (`accounts/models.py`)

Added two new methods to the `User` model:

#### `get_accessible_storefronts()`
Returns a QuerySet of storefronts the user can access based on their role:

```python
def get_accessible_storefronts(self):
    """Return QuerySet of storefronts user can access based on role and assignments."""
    from inventory.models import StoreFront, StoreFrontEmployee, BusinessStoreFront
    
    # Super admins can access all storefronts
    if self.is_superuser or self.platform_role == self.PLATFORM_SUPER_ADMIN:
        return StoreFront.objects.all()
    
    # Get user's active business membership
    membership = self.business_memberships.filter(is_active=True).first()
    if not membership:
        return StoreFront.objects.none()
    
    business = membership.business
    
    # Business owners and admins can access all business storefronts
    if membership.role in [BusinessMembership.OWNER, BusinessMembership.ADMIN]:
        business_storefronts = BusinessStoreFront.objects.filter(
            business=business,
            is_active=True
        ).values_list('storefront', flat=True)
        return StoreFront.objects.filter(id__in=business_storefronts)
    
    # Managers and staff see their assigned storefronts
    assigned_storefronts = StoreFrontEmployee.objects.filter(
        user=self,
        business=business,
        is_active=True
    ).values_list('storefront', flat=True)
    
    return StoreFront.objects.filter(id__in=assigned_storefronts)
```

**Access Rules:**
| Role | Access |
|------|--------|
| **Super Admin** | All storefronts across all businesses |
| **Business Owner** | All storefronts in their business |
| **Business Admin** | All storefronts in their business |
| **Manager** | Assigned storefronts only |
| **Staff** | Assigned storefronts only |

#### `can_access_storefront(storefront_id)`
Quick permission check for a specific storefront:

```python
def can_access_storefront(self, storefront_id):
    """Check if user can access a specific storefront."""
    return self.get_accessible_storefronts().filter(id=storefront_id).exists()
```

---

### 2. SaleViewSet Update (`sales/views.py`)

Updated `get_queryset()` to filter by accessible storefronts:

**Before:**
```python
def get_queryset(self):
    # ... business filtering only
    if membership:
        queryset = queryset.filter(business=membership.business)
    
    return queryset.order_by('-completed_at', '-created_at')
```

**After:**
```python
def get_queryset(self):
    # ... business filtering
    if membership:
        queryset = queryset.filter(business=membership.business)
        
        # NEW: Apply permission-based storefront filtering
        user_storefronts = user.get_accessible_storefronts()
        queryset = queryset.filter(storefront__in=user_storefronts)
    
    return queryset.order_by('-completed_at', '-created_at')
```

**Impact:**
- Users now see sales from ALL their accessible storefronts by default
- No more automatic single-storefront filtering
- FilterSet can further filter to specific storefront

---

### 3. SaleFilter Enhancement (`sales/filters.py`)

Updated storefront filter to validate permissions:

**Before:**
```python
# Storefront filter
storefront = filters.UUIDFilter(field_name='storefront__id')
```

**After:**
```python
# Storefront filter with permission validation
storefront = filters.UUIDFilter(
    field_name='storefront__id',
    method='filter_storefront'
)

def filter_storefront(self, queryset, name, value):
    """
    Validate user has access to requested storefront before applying filter.
    This ensures users can only filter to storefronts they have permission to view.
    """
    if not value:
        return queryset
    
    # Check if user has access to this storefront
    user = self.request.user
    if user.can_access_storefront(value):
        return queryset.filter(storefront__id=value)
    
    # User doesn't have access - return no results
    return queryset.none()
```

**Security:**
- Validates user has permission before filtering
- Prevents unauthorized access to other storefronts
- Returns empty queryset if permission denied

---

### 4. New API Endpoint (`accounts/views.py`)

Added `/api/users/storefronts/` endpoint to UserViewSet:

```python
@action(detail=False, methods=['get'])
def storefronts(self, request):
    """Get user's accessible storefronts"""
    user = request.user
    storefronts = user.get_accessible_storefronts()
    
    data = [
        {
            'id': str(storefront.id),
            'name': storefront.name,
            'location': storefront.location,
            'is_active': getattr(storefront, 'is_active', True),
        }
        for storefront in storefronts
    ]
    
    return Response({
        'storefronts': data,
        'count': len(data)
    })
```

**Endpoint:** `GET /accounts/api/users/storefronts/`

**Response:**
```json
{
  "storefronts": [
    {
      "id": "uuid-1",
      "name": "Cow Lane Store",
      "location": "Accra Central",
      "is_active": true
    },
    {
      "id": "uuid-2",
      "name": "Adenta Store",
      "location": "Adenta, Ghana",
      "is_active": true
    }
  ],
  "count": 2
}
```

---

## 📊 API Usage Examples

### 1. Get User's Accessible Storefronts
```http
GET /accounts/api/users/storefronts/
Authorization: Bearer <token>

Response:
{
  "storefronts": [
    {"id": "uuid-1", "name": "Cow Lane Store", ...},
    {"id": "uuid-2", "name": "Adenta Store", ...}
  ],
  "count": 2
}
```

### 2. Get All Accessible Sales (Default)
```http
GET /sales/api/sales/?status=COMPLETED
Authorization: Bearer <token>

# Returns COMPLETED sales from ALL accessible storefronts
```

### 3. Filter to Specific Storefront
```http
GET /sales/api/sales/?status=COMPLETED&storefront=uuid-1
Authorization: Bearer <token>

# Returns COMPLETED sales from Cow Lane Store only
# (if user has access to it)
```

### 4. Combined Filters
```http
GET /sales/api/sales/?status=COMPLETED&storefront=uuid-1&date_from=2025-10-01
Authorization: Bearer <token>

# Returns COMPLETED sales from Cow Lane Store since Oct 1
```

### 5. Unauthorized Storefront Access
```http
GET /sales/api/sales/?storefront=uuid-999
Authorization: Bearer <token>

# Returns empty results if user doesn't have access to storefront
```

---

## 🧪 Test Scenarios

### Scenario 1: Single Storefront User (Staff)
**User:** John (Staff at Cow Lane Store)  
**Access:** Cow Lane Store only

```python
# Test 1: Get storefronts
GET /api/users/storefronts/
# Expected: 1 storefront (Cow Lane Store)

# Test 2: Get sales (no storefront filter)
GET /sales/api/sales/?status=COMPLETED
# Expected: All COMPLETED sales from Cow Lane Store

# Test 3: Filter to accessible storefront
GET /sales/api/sales/?storefront=<cow-lane-id>
# Expected: Same as Test 2

# Test 4: Filter to inaccessible storefront
GET /sales/api/sales/?storefront=<adenta-id>
# Expected: Empty results (permission denied)
```

### Scenario 2: Multi-Storefront Manager
**User:** Sarah (Manager of 2 stores)  
**Access:** Cow Lane Store, Adenta Store

```python
# Test 1: Get storefronts
GET /api/users/storefronts/
# Expected: 2 storefronts

# Test 2: Get all sales
GET /sales/api/sales/?status=COMPLETED
# Expected: COMPLETED sales from BOTH stores

# Test 3: Filter to Cow Lane
GET /sales/api/sales/?status=COMPLETED&storefront=<cow-lane-id>
# Expected: Only Cow Lane COMPLETED sales

# Test 4: Filter to Adenta
GET /sales/api/sales/?status=COMPLETED&storefront=<adenta-id>
# Expected: Only Adenta COMPLETED sales

# Test 5: Combined filters
GET /sales/api/sales/?status=COMPLETED&storefront=<cow-lane-id>&date_range=this_month
# Expected: Cow Lane COMPLETED sales this month
```

### Scenario 3: Business Owner/Admin
**User:** Mike (Owner of DataLogique Systems)  
**Access:** All business storefronts

```python
# Test 1: Get storefronts
GET /api/users/storefronts/
# Expected: All DataLogique storefronts

# Test 2: Get all sales
GET /sales/api/sales/?status=COMPLETED
# Expected: COMPLETED sales from ALL storefronts

# Test 3: Filter to specific storefront
GET /sales/api/sales/?status=COMPLETED&storefront=<any-storefront-id>
# Expected: Sales from that specific storefront
```

---

## 🔐 Permission Matrix

| User Role | Default View | Can Filter To | Permission Check |
|-----------|--------------|---------------|------------------|
| **Super Admin** | All storefronts, all businesses | Any storefront | ✅ Always passes |
| **Business Owner** | All business storefronts | Any business storefront | ✅ Checks business ownership |
| **Business Admin** | All business storefronts | Any business storefront | ✅ Checks business membership |
| **Manager** | Assigned storefronts | Only assigned storefronts | ✅ Checks StoreFrontEmployee |
| **Staff** | Assigned storefronts | Only assigned storefronts | ✅ Checks StoreFrontEmployee |

---

## 🚀 Frontend Integration Guide

### Step 1: Load User's Storefronts

```typescript
// On app initialization or login
const loadUserStorefronts = async () => {
  const response = await api.get('/accounts/api/users/storefronts/')
  dispatch(setAccessibleStorefronts(response.data.storefronts))
}
```

### Step 2: Show Storefront Dropdown (if multiple)

```tsx
// In SalesHistory component
const userStorefronts = useAppSelector(selectUserStorefronts)
const showStorefrontFilter = userStorefronts.length > 1

{showStorefrontFilter && (
  <Form.Select
    value={selectedStorefront}
    onChange={(e) => handleStorefrontChange(e.target.value)}
  >
    <option value="">🏪 All My Stores</option>
    {userStorefronts.map(store => (
      <option key={store.id} value={store.id}>
        {store.name}
      </option>
    ))}
  </Form.Select>
)}
```

### Step 3: Handle Filter Changes

```typescript
const handleStorefrontChange = (storefrontId: string) => {
  setSelectedStorefront(storefrontId)
  dispatch(setSalesPage(1)) // Reset pagination
  
  if (storefrontId) {
    dispatch(setSalesFilters({ 
      ...filters, 
      storefront: storefrontId 
    }))
  } else {
    // Remove storefront filter (show all)
    const { storefront, ...rest } = filters
    dispatch(setSalesFilters(rest))
  }
}
```

### Step 4: Display Active Filters

```tsx
{selectedStorefront && (
  <Badge bg="primary" className="me-2">
    📍 {userStorefronts.find(s => s.id === selectedStorefront)?.name}
    <button onClick={() => handleStorefrontChange('')}>×</button>
  </Badge>
)}
```

---

## 📋 Implementation Checklist

### Backend ✅
- [x] Add `get_accessible_storefronts()` to User model
- [x] Add `can_access_storefront()` to User model
- [x] Update `SaleViewSet.get_queryset()` for permission-based filtering
- [x] Add `filter_storefront()` validation method to SaleFilter
- [x] Create `/api/users/storefronts/` endpoint
- [x] Add permission validation to storefront filter
- [ ] Add tests for storefront permissions
- [ ] Add tests for combined filters

### Frontend (Pending)
- [ ] Add `storefront` to `SalesFilters` interface
- [ ] Create `selectUserStorefronts` selector
- [ ] Add storefront dropdown to SalesHistory component
- [ ] Implement `handleStorefrontChange` handler
- [ ] Update active filters badge to show storefront
- [ ] Load user storefronts on app init
- [ ] Add loading/error states for storefronts
- [ ] Add tests for storefront filtering

---

## 🔍 How It Works

### Before (❌ Broken)
```
User Request → SaleViewSet
  ↓
Filter by business only
  ↓
Return ALL business sales (no storefront check)
  ↓
Frontend shows sales from all storefronts
  ↓
❌ User sees sales from stores they don't have access to
```

### After (✅ Fixed)
```
User Request → SaleViewSet
  ↓
Filter by business
  ↓
Get user's accessible storefronts (permission check)
  ↓
Filter sales to ONLY accessible storefronts
  ↓
Apply additional filters (status, storefront, etc.)
  ↓
✅ User sees only sales from their accessible storefronts
```

---

## 🎯 Example Use Cases

### Use Case 1: Staff Member
- John works at Cow Lane Store
- Assigned to Cow Lane Store only
- Default view: All sales from Cow Lane Store
- Cannot see Adenta Store sales (permission denied)

### Use Case 2: Multi-Store Manager
- Sarah manages Cow Lane and Adenta stores
- Assigned to both stores
- Default view: All sales from both stores combined
- Can filter to see just Cow Lane or just Adenta
- Cannot see Rawlings Park sales (not assigned)

### Use Case 3: Business Owner
- Mike owns DataLogique Systems
- Has 3 storefronts: Cow Lane, Adenta, Rawlings Park
- Default view: All sales from all 3 stores
- Can filter to any specific storefront
- Full access to all business data

---

## 🐛 Troubleshooting

### Issue: User sees no sales

**Check:**
1. Does user have active business membership?
   ```python
   user.business_membership.filter(is_active=True).exists()
   ```

2. Does user have storefront assignments?
   ```python
   user.get_accessible_storefronts().count()
   ```

3. Do sales exist for accessible storefronts?
   ```python
   Sale.objects.filter(storefront__in=user.get_accessible_storefronts()).count()
   ```

### Issue: Storefront filter returns empty

**Check:**
1. Does user have access to requested storefront?
   ```python
   user.can_access_storefront(storefront_id)
   ```

2. Is storefront ID valid?
   ```python
   StoreFront.objects.filter(id=storefront_id).exists()
   ```

### Issue: User sees wrong storefronts

**Check:**
1. User's business membership role:
   ```python
   membership = user.business_membership.filter(is_active=True).first()
   print(membership.role)  # OWNER, ADMIN, MANAGER, STAFF?
   ```

2. User's storefront assignments:
   ```python
   StoreFrontEmployee.objects.filter(user=user, is_active=True).values('storefront__name')
   ```

---

## 📚 Related Documentation

- **Original Issue:** PROOF_BACKEND_WORKS_FRONTEND_ISSUE.md
- **Data Population:** DATALOGIQUE_DATA_POPULATION_SUCCESS.md
- **API Enhancements:** SALES_API_ENHANCEMENTS_COMPLETE.md
- **Frontend Integration:** FRONTEND_SALES_HISTORY_FIX.md

---

## ✅ Testing Commands

### Test User Storefronts
```python
from accounts.models import User

user = User.objects.get(email='mikedlt009@gmail.com')

# Get accessible storefronts
storefronts = user.get_accessible_storefronts()
print(f"User has access to {storefronts.count()} storefronts:")
for sf in storefronts:
    print(f"  - {sf.name} ({sf.location})")

# Check specific storefront
from inventory.models import StoreFront
sf = StoreFront.objects.first()
print(f"Can access {sf.name}? {user.can_access_storefront(sf.id)}")
```

### Test Sales Filtering
```python
from sales.models import Sale

# Get sales for user's accessible storefronts
user_storefronts = user.get_accessible_storefronts()
sales = Sale.objects.filter(storefront__in=user_storefronts, status='COMPLETED')
print(f"User can see {sales.count()} COMPLETED sales")

# Group by storefront
from django.db.models import Count
sales_by_store = sales.values('storefront__name').annotate(count=Count('id'))
for item in sales_by_store:
    print(f"  {item['storefront__name']}: {item['count']} sales")
```

### Test API Endpoint
```bash
# Get user storefronts
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/accounts/api/users/storefronts/

# Get all accessible sales
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/sales/api/sales/?status=COMPLETED"

# Filter to specific storefront
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/sales/api/sales/?status=COMPLETED&storefront=<uuid>"
```

---

**Status:** ✅ Backend Implementation Complete  
**Next Step:** Frontend integration  
**Last Updated:** October 6, 2025
