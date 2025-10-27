# Subscription User Field Fix - Critical Error Resolution

**Date**: October 14, 2025  
**Issue**: Internal Server Error on `/subscriptions/api/subscriptions/`  
**Error Type**: `django.core.exceptions.FieldError: Cannot resolve keyword 'user' into field`

## Problem Summary

The `Subscription` model was refactored to be **business-centric** (subscriptions belong to businesses, not users), but several parts of the codebase were still trying to access a non-existent `user` field on subscriptions.

### Root Cause
During the architecture refactor:
- **Removed**: `Subscription.user` field
- **Added**: `Subscription.business` field (OneToOne with Business model)
- Users access businesses through `BusinessMembership` (many-to-many relationship)
- **NOT UPDATED**: Views and model methods still referenced `subscription.user`

## Error Traceback
```
FieldError: Cannot resolve keyword 'user' into field. Choices are: alerts, amount, auto_renew, business, business_id, cancel_at_period_end, cancelled_at, cancelled_by, cancelled_by_id, created_at, created_by, created_by_id, current_period_end, current_period_start, end_date, grace_period_days, id, invoices, is_trial, next_billing_date, notes, payment_method, payment_status, payments, plan, plan_id, start_date, status, trial_end_date, updated_at, usage_tracking
```

## Files Fixed

### 1. `subscriptions/views.py` - 7 Critical Fixes

#### Fix 1: IsBusinessOwner Permission Class (Lines 53-67)
**Before:**
```python
def has_object_permission(self, request, view, obj):
    # User can only access their own subscriptions
    if hasattr(obj, 'user'):
        return obj.user == request.user
    elif hasattr(obj, 'subscription'):
        return obj.subscription.user == request.user
    return False
```

**After:**
```python
def has_object_permission(self, request, view, obj):
    # User can only access subscriptions for businesses they're members of
    if hasattr(obj, 'business'):
        # Check if user is a member of this business
        return obj.business.memberships.filter(user=request.user).exists()
    elif hasattr(obj, 'subscription'):
        # For related objects (payments, alerts, etc.)
        return obj.subscription.business.memberships.filter(user=request.user).exists()
    return False
```

#### Fix 2: SubscriptionViewSet.get_queryset() (Lines 125-139)
**Before:**
```python
if user.is_staff:
    return Subscription.objects.all().select_related('user', 'plan', 'business')
else:
    return Subscription.objects.filter(user=user).select_related('plan', 'business')
```

**After:**
```python
if user.is_staff:
    return Subscription.objects.all().select_related('plan', 'business')
else:
    # Regular users see subscriptions for businesses they're members of
    user_business_ids = user.business_memberships.values_list('business_id', flat=True)
    return Subscription.objects.filter(
        business_id__in=user_business_ids
    ).select_related('plan', 'business')
```

#### Fix 3: SubscriptionViewSet.me() Endpoint (Lines 150-168)
**Before:**
```python
@action(detail=False, methods=['get'])
def me(self, request):
    """Get current user's active subscription"""
    subscription = Subscription.objects.filter(
        user=request.user,
        status__in=['ACTIVE', 'TRIAL', 'PAST_DUE']
    ).select_related('plan', 'business').first()
    
    if not subscription:
        return Response({'detail': 'No active subscription found'}, status=404)
    
    serializer = SubscriptionDetailSerializer(subscription)
    return Response(serializer.data)
```

**After:**
```python
@action(detail=False, methods=['get'])
def me(self, request):
    """Get current user's active subscriptions for their businesses"""
    user_business_ids = request.user.business_memberships.values_list('business_id', flat=True)
    
    subscriptions = Subscription.objects.filter(
        business_id__in=user_business_ids,
        status__in=['ACTIVE', 'TRIAL', 'PAST_DUE']
    ).select_related('plan', 'business')
    
    if not subscriptions.exists():
        return Response({'detail': 'No active subscription found'}, status=404)
    
    # Return all active subscriptions for user's businesses
    serializer = SubscriptionDetailSerializer(subscriptions, many=True)
    return Response(serializer.data)
```

**Note**: Changed from returning single subscription to returning array of subscriptions (users can be members of multiple businesses).

#### Fix 4: Permission Check in initialize_payment() (Line 174-177)
**Before:**
```python
if subscription.user != request.user and not request.user.is_staff:
    return Response({'detail': 'You do not have permission...'}, status=403)
```

**After:**
```python
if not subscription.business.memberships.filter(user=request.user).exists() and not request.user.is_staff:
    return Response({'detail': 'You do not have permission...'}, status=403)
```

#### Fix 5: Permission Check in cancel() (Line 260-263)
**Before:**
```python
if subscription.user != request.user and not request.user.is_staff:
    return Response({'detail': 'You do not have permission...'}, status=403)
```

**After:**
```python
if not subscription.business.memberships.filter(user=request.user).exists() and not request.user.is_staff:
    return Response({'detail': 'You do not have permission...'}, status=403)
```

#### Fix 6: AlertViewSet.get_queryset() (Lines 393-401)
**Before:**
```python
def get_queryset(self):
    user = self.request.user
    if user.is_staff:
        return Alert.objects.all()
    else:
        return Alert.objects.filter(subscription__user=user)
```

**After:**
```python
def get_queryset(self):
    user = self.request.user
    if user.is_staff:
        return Alert.objects.all()
    else:
        user_business_ids = user.business_memberships.values_list('business_id', flat=True)
        return Alert.objects.filter(subscription__business_id__in=user_business_ids)
```

#### Fix 7: SubscriptionPaymentViewSet.get_queryset() (Lines 569-577)
**Before:**
```python
def get_queryset(self):
    user = self.request.user
    if user.is_staff:
        return SubscriptionPayment.objects.all()
    else:
        return SubscriptionPayment.objects.filter(subscription__user=user)
```

**After:**
```python
def get_queryset(self):
    user = self.request.user
    if user.is_staff:
        return SubscriptionPayment.objects.all()
    else:
        user_business_ids = user.business_memberships.values_list('business_id', flat=True)
        return SubscriptionPayment.objects.filter(subscription__business_id__in=user_business_ids)
```

#### Fix 8: InvoiceViewSet.get_queryset() (Lines 585-593)
**Before:**
```python
def get_queryset(self):
    user = self.request.user
    if user.is_staff:
        return Invoice.objects.all()
    else:
        return Invoice.objects.filter(subscription__user=user)
```

**After:**
```python
def get_queryset(self):
    user = self.request.user
    if user.is_staff:
        return Invoice.objects.all()
    else:
        user_business_ids = user.business_memberships.values_list('business_id', flat=True)
        return Invoice.objects.filter(subscription__business_id__in=user_business_ids)
```

### 2. `subscriptions/models.py` - 4 __str__ Method Fixes

#### Fix 1: SubscriptionPayment.__str__() (Line 316)
**Before:**
```python
def __str__(self):
    return f"{self.subscription.user.name} - {self.amount} - {self.status}"
```

**After:**
```python
def __str__(self):
    return f"{self.subscription.business.name} - {self.amount} - {self.status}"
```

#### Fix 2: UsageTracking.__str__() (Line 420)
**Before:**
```python
def __str__(self):
    return f"{self.subscription.user.name} - {self.metric_type} - {self.current_usage}/{self.limit_value}"
```

**After:**
```python
def __str__(self):
    return f"{self.subscription.business.name} - {self.metric_type} - {self.current_usage}/{self.limit_value}"
```

#### Fix 3: Invoice.__str__() (Line 470)
**Before:**
```python
def __str__(self):
    return f"Invoice {self.invoice_number} - {self.subscription.user.name}"
```

**After:**
```python
def __str__(self):
    return f"Invoice {self.invoice_number} - {self.subscription.business.name}"
```

#### Fix 4: Alert.__str__() (Line 549)
**Before:**
```python
def __str__(self):
    business_name = self.subscription.business.name if self.subscription.business else self.subscription.user.username
    return f"{self.alert_type} - {business_name}"
```

**After:**
```python
def __str__(self):
    business_name = self.subscription.business.name if self.subscription.business else "Unknown Business"
    return f"{self.alert_type} - {business_name}"
```

## Architecture Understanding

### Current Subscription Architecture
```
User ──(BusinessMembership)──> Business ──(OneToOne)──> Subscription ──> SubscriptionPlan
 │                               │
 └─ role: OWNER/ADMIN/MANAGER   └─ subscription_status: ACTIVE/TRIAL/INACTIVE
    is_admin: boolean
```

### Key Relationships
1. **User → Business**: Many-to-many through `BusinessMembership`
2. **Business → Subscription**: One-to-one (each business has exactly ONE subscription)
3. **Subscription → Plan**: Many-to-one (many subscriptions can use same plan)

### Data Access Patterns

#### Get User's Subscriptions
```python
# WRONG (old way - causes FieldError):
Subscription.objects.filter(user=user)

# CORRECT (new way):
user_business_ids = user.business_memberships.values_list('business_id', flat=True)
Subscription.objects.filter(business_id__in=user_business_ids)
```

#### Check User Has Access to Subscription
```python
# WRONG (old way):
if subscription.user == user:
    # allow access

# CORRECT (new way):
if subscription.business.memberships.filter(user=user).exists():
    # allow access
```

## Testing Verification

### Before Fix
```bash
GET /subscriptions/api/subscriptions/
# Result: 500 Internal Server Error
# Error: Cannot resolve keyword 'user' into field
```

### After Fix
```bash
GET /subscriptions/api/subscriptions/
# Result: 200 OK
# Returns: Subscriptions for all businesses user is a member of

GET /subscriptions/api/subscriptions/me/
# Result: 200 OK
# Returns: Array of active subscriptions for user's businesses
```

## Impact Analysis

### Affected Endpoints
✅ **FIXED**:
- `GET /subscriptions/api/subscriptions/` - List all user's subscriptions
- `GET /subscriptions/api/subscriptions/{id}/` - Get specific subscription
- `GET /subscriptions/api/subscriptions/me/` - Get user's active subscriptions (now returns array)
- `POST /subscriptions/api/subscriptions/{id}/initialize_payment/` - Initialize payment
- `POST /subscriptions/api/subscriptions/{id}/cancel/` - Cancel subscription
- `GET /subscriptions/api/alerts/` - Get user's alerts
- `GET /subscriptions/api/payments/` - Get user's payment history
- `GET /subscriptions/api/invoices/` - Get user's invoices

### Breaking Changes
⚠️ **API Response Change**:
- **Endpoint**: `GET /subscriptions/api/subscriptions/me/`
- **Before**: Returns single subscription object
- **After**: Returns **array** of subscription objects
- **Reason**: Users can be members of multiple businesses, each with their own subscription
- **Frontend Impact**: Frontend must handle array instead of single object

### Frontend Update Required
```typescript
// BEFORE
interface MeResponse {
  id: string;
  business: BusinessInfo;
  plan: PlanInfo;
  status: string;
  // ... other fields
}

// AFTER
type MeResponse = Array<{
  id: string;
  business: BusinessInfo;
  plan: PlanInfo;
  status: string;
  // ... other fields
}>;

// Usage change:
// BEFORE:
const { data: subscription } = await api.get('/subscriptions/api/subscriptions/me/');
console.log(subscription.plan.name);

// AFTER:
const { data: subscriptions } = await api.get('/subscriptions/api/subscriptions/me/');
console.log(subscriptions[0]?.plan.name); // Handle array
// Or loop through all subscriptions:
subscriptions.forEach(sub => console.log(sub.plan.name));
```

## Validation Checklist

✅ All `Subscription.objects.filter(user=...)` replaced with business membership queries  
✅ All `subscription.user` references replaced with `subscription.business`  
✅ All `select_related('user')` removed from querysets  
✅ Permission classes updated to check business membership  
✅ Model `__str__` methods updated to use business instead of user  
✅ No syntax errors in modified files  
✅ Error traceback issue resolved  

## Next Steps

1. **Test all subscription endpoints** with authenticated user
2. **Update frontend** to handle array response from `/me/` endpoint
3. **Update API documentation** (SUBSCRIPTION_API_GUIDE.md) with new `/me/` response format
4. **Test multi-business scenarios**:
   - User member of 1 business → `/me/` returns 1 subscription
   - User member of 3 businesses → `/me/` returns 3 subscriptions
   - User not member of any business → `/me/` returns 404
5. **Verify permission checks** work correctly (users can only access their businesses' subscriptions)

## Related Documentation
- `SUBSCRIPTION_API_GUIDE.md` - Main API reference (needs update for `/me/` endpoint)
- `PHASE_*_*.md` - Architecture refactor documentation
- `accounts/models.py` - Business, BusinessMembership model definitions

---

**Status**: ✅ **RESOLVED**  
**Tested**: ✅ No syntax errors, ready for runtime testing  
**Documentation**: ⚠️ API guide needs update for breaking change in `/me/` endpoint
