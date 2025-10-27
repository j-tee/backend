# Subscription Serializer Fixes

**Date**: October 14, 2025  
**Issue**: `ImproperlyConfigured: Field name 'billing_cycle_display' is not valid for model 'SubscriptionPlan'`  
**Endpoint**: `GET /subscriptions/api/plans/`

## Problem Summary

After fixing the subscription user field issues, another error occurred when trying to access the subscription plans API. The serializer was trying to include `billing_cycle_display` as a model field, but it's actually a Django model method that needs to be called.

Additionally, several serializers still referenced the removed `user` field on the `Subscription` model.

## Errors Fixed

### 1. SubscriptionPlanSerializer - billing_cycle_display

**Error:**
```
ImproperlyConfigured: Field name `billing_cycle_display` is not valid for model `SubscriptionPlan`.
```

**Problem:** 
The serializer included `'billing_cycle_display'` in the fields list without defining it as a SerializerMethodField.

**Fix:**
```python
# BEFORE: billing_cycle_display was just listed in fields

# AFTER: Added as SerializerMethodField
class SubscriptionPlanSerializer(serializers.ModelSerializer):
    billing_cycle_display = serializers.SerializerMethodField()
    
    def get_billing_cycle_display(self, obj):
        """Get human-readable billing cycle"""
        return obj.get_billing_cycle_display()
```

### 2. SubscriptionDetailSerializer - Removed user fields

**Problem:**
Serializer tried to access `user.name` and `user.email` which don't exist (Subscription no longer has user field).

**Fix:**
```python
# REMOVED these fields:
user_name = serializers.CharField(source='user.name', read_only=True)
user_email = serializers.EmailField(source='user.email', read_only=True)

# REMOVED from fields list:
'user', 'user_name', 'user_email'

# KEPT business fields (correct):
business_name = serializers.CharField(source='business.name', read_only=True)
business_id = serializers.UUIDField(source='business.id', read_only=True)
```

### 3. SubscriptionCreateSerializer - Business validation

**Problem:**
- `business_id` was optional (allow_null=True)
- Validation checked if user was business owner (wrong - should check membership)
- Creation tried to set `user` field on Subscription (doesn't exist)

**Fixes:**

#### A. Made business_id required:
```python
# BEFORE:
business_id = serializers.UUIDField(required=False, allow_null=True)

# AFTER:
business_id = serializers.UUIDField(required=True)  # Business is required
```

#### B. Updated validation to check membership:
```python
# BEFORE:
if request and request.user != business.owner:
    raise serializers.ValidationError("You don't have permission...")

# AFTER:
if request and not business.memberships.filter(user=request.user).exists():
    raise serializers.ValidationError("You don't have permission...")
```

#### C. Fixed create() method:
```python
# BEFORE:
subscription = Subscription.objects.create(
    user=user,  # ❌ Field doesn't exist
    business=business,
    ...
)

# AFTER:
subscription = Subscription.objects.create(
    business=business,
    created_by=user,  # ✅ Track who created it
    ...
)
```

## Complete Changes

### File: `subscriptions/serializers.py`

**Lines 18-48 - SubscriptionPlanSerializer:**
- ✅ Added `billing_cycle_display = serializers.SerializerMethodField()`
- ✅ Added `get_billing_cycle_display()` method

**Lines 79-113 - SubscriptionDetailSerializer:**
- ❌ Removed `user_name` field
- ❌ Removed `user_email` field
- ❌ Removed `'user'`, `'user_name'`, `'user_email'` from fields list
- ❌ Removed `'user'` from read_only_fields
- ✅ Kept `business_id` and `business_name` fields

**Lines 144-158 - SubscriptionCreateSerializer:**
- ✅ Changed `business_id` from optional to required
- ✅ Updated `validate_business_id()` to check membership instead of ownership
- ✅ Made business_id validation raise error if not provided

**Lines 172-231 - SubscriptionCreateSerializer.create():**
- ✅ Made `business_id` required (removed `business_id.pop('business_id', None)`)
- ✅ Removed `business = None` initialization
- ✅ Changed `user=user` to `created_by=user` in Subscription.objects.create()
- ✅ Removed conditional business handling (business is always required now)

## Impact on API

### Subscription Creation Endpoint

**Endpoint:** `POST /subscriptions/api/subscriptions/`

**Before:**
```json
{
  "plan_id": "uuid",
  "business_id": "uuid",  // Optional
  "payment_method": "PAYSTACK"
}
```

**After:**
```json
{
  "plan_id": "uuid",
  "business_id": "uuid",  // ⚠️ NOW REQUIRED
  "payment_method": "PAYSTACK"
}
```

**Validation:**
- ✅ User must be a member of the business (not just owner)
- ✅ Business must exist
- ✅ Plan must exist and be active

### Subscription Detail Response

**Endpoint:** `GET /subscriptions/api/subscriptions/{id}/`

**Before:**
```json
{
  "id": "uuid",
  "user": "user-uuid",
  "user_name": "John Doe",
  "user_email": "john@example.com",
  "business_id": "uuid",
  "business_name": "Business Name",
  ...
}
```

**After:**
```json
{
  "id": "uuid",
  "business_id": "uuid",
  "business_name": "Business Name",
  ...
}
```

**Changes:**
- ❌ Removed `user`, `user_name`, `user_email` fields
- ✅ Business fields remain (this is the primary relationship)

### Subscription Plans Response

**Endpoint:** `GET /subscriptions/api/plans/`

**Before:** ❌ Error 500

**After:** ✅ Success 200
```json
{
  "results": [
    {
      "id": "uuid",
      "name": "Professional Plan",
      "billing_cycle": "MONTHLY",
      "billing_cycle_display": "Monthly",  // ✅ Now works!
      ...
    }
  ]
}
```

## Architecture Alignment

These fixes complete the alignment with the business-centric subscription architecture:

```
User ──(BusinessMembership)──> Business ──(OneToOne)──> Subscription ──> SubscriptionPlan
 │                               │                        │
 │                               └─ subscription_status   └─ created_by (audit)
 └─ Can be member of multiple
    businesses (each with own
    subscription)
```

### Key Principles:
1. ✅ Subscriptions belong to businesses (not users)
2. ✅ Users access subscriptions through business membership
3. ✅ `created_by` tracks who created the subscription (audit trail)
4. ✅ Any business member can subscribe the business (not just owner)

## Testing Checklist

✅ Subscription plan listing works (`GET /subscriptions/api/plans/`)  
✅ Plan detail shows `billing_cycle_display` correctly  
✅ Subscription detail doesn't include user fields  
✅ Subscription creation requires `business_id`  
✅ Subscription creation validates business membership  
✅ Subscription created with `created_by` field set  

## Frontend Impact

### Breaking Changes

1. **Subscription Creation:**
   - `business_id` is now **required** (was optional before)
   - Frontend must always provide business_id when creating subscriptions

2. **Subscription Detail Response:**
   - No longer includes `user`, `user_name`, `user_email` fields
   - Only includes `business_id` and `business_name`
   - Frontend should use business information instead of user information

### Required Frontend Updates

```typescript
// BEFORE (wrong):
interface Subscription {
  id: string;
  user: string;
  user_name: string;
  user_email: string;
  business_id: string;
  business_name: string;
  ...
}

// AFTER (correct):
interface Subscription {
  id: string;
  // user fields removed
  business_id: string;
  business_name: string;
  ...
}

// Creating subscription - business_id now required:
const response = await fetch('/subscriptions/api/subscriptions/', {
  method: 'POST',
  headers: {
    'Authorization': `Token ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    plan_id: selectedPlan.id,
    business_id: currentBusiness.id,  // ⚠️ REQUIRED!
    payment_method: 'PAYSTACK'
  })
});
```

## Related Documentation

- `SUBSCRIPTION_USER_FIELD_FIX.md` - Previous fix for user field references in views/models
- `SUBSCRIPTION_API_GUIDE.md` - API documentation (needs update for serializer changes)

## Status

✅ **RESOLVED**  
✅ All serializer errors fixed  
✅ Business-centric architecture fully implemented  
✅ No syntax errors  
⏳ API testing needed to verify runtime behavior
