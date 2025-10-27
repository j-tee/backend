# User Role Serialization Fix

## Problem

The frontend was showing `null` for user roles because:
1. The `UserSerializer` was using the **deprecated** `role` ForeignKey field
2. The User model now uses a `roles` many-to-many relationship through `UserRole`
3. The login response didn't populate `final_userRole` for business owners
4. The `employment` data was only sent for employees, not owners

## Root Cause

The system underwent a migration from:
- **Old:** Single `role` ForeignKey on User model
- **New:** Multiple `roles` via `UserRole` junction table with scope (Platform/Business/Storefront)

However, the serializers and views were still referencing the old deprecated field.

## Changes Made

### 1. Updated `UserSerializer` (accounts/serializers.py)

**Added:**
- New `user_roles` field to return all active roles with their scopes
- Made `role_name` nullable to handle deprecated field gracefully

**Before:**
```python
class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)
    role_name = serializers.CharField(source='role.name', read_only=True)
    # ...
    fields = ['id', 'name', 'email', 'role', 'role_name', ...]
```

**After:**
```python
class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)
    role_name = serializers.CharField(source='role.name', read_only=True, allow_null=True)
    user_roles = serializers.SerializerMethodField()
    # ...
    fields = ['id', 'name', 'email', 'role', 'role_name', 'user_roles', ...]
    
    def get_user_roles(self, obj):
        """Get all active roles with their scopes"""
        from accounts.models import UserRole
        roles = UserRole.objects.filter(
            user=obj,
            is_active=True
        ).select_related('role', 'business', 'storefront')
        
        return [
            {
                'id': str(ur.id),
                'role': {
                    'id': str(ur.role.id),
                    'name': ur.role.name,
                    'description': ur.role.description,
                },
                'scope': ur.scope,
                'business': {...} if ur.business else None,
                'storefront': {...} if ur.storefront else None,
            }
            for ur in roles
        ]
```

### 2. Updated `LoginView` (accounts/views.py)

**Changed:**
- Now fetches business membership for **all users** (not just employees)
- Sets `final_userRole` from `BusinessMembership.role`
- Populates `employment` data for all users with business memberships
- Falls back to `UserRole` if no business membership exists
- Fixed field name bug: `created_at` → `assigned_at` for UserRole ordering

**Before:**
```python
employment_data = None
if user.account_type == User.ACCOUNT_EMPLOYEE:
    membership = user.business_memberships.filter(is_active=True).first()
    if membership:
        employment_data = BusinessMembershipSummarySerializer(membership).data

response_payload = {
    'token': token.key,
    'user': UserSerializer(user, context={'request': request}).data,
    'employment': employment_data,
}
```

**After:**
```python
employment_data = None
final_user_role = None

# Get primary business membership (for both employees and owners)
membership = user.business_memberships.filter(is_active=True).first()

if membership:
    final_user_role = membership.role
    employment_data = BusinessMembershipSummarySerializer(membership).data

# Fallback to UserRole if no business membership
if not final_user_role:
    primary_user_role = UserRole.objects.filter(
        user=user, is_active=True
    ).order_by('-assigned_at').first()
    if primary_user_role:
        final_user_role = primary_user_role.role.name

# Add computed fields to user data
user_data = UserSerializer(user, context={'request': request}).data
user_data['final_userRole'] = final_user_role
user_data['employment'] = employment_data

response_payload = {
    'token': token.key,
    'user': user_data,
    'employment': employment_data,
}
```

## Files Modified

1. **`accounts/serializers.py`**
   - Added `user_roles` SerializerMethodField
   - Made `role_name` nullable
   - Added `get_user_roles()` method

2. **`accounts/views.py`**
   - Updated `LoginView.post()` to populate roles for all users
   - Fixed UserRole ordering field bug
   - Added `final_userRole` to response

## Test Results

**Before Fix:**
```json
{
  "user": {
    "role": null,
    "role_name": null,
    "final_userRole": null
  },
  "employment": null
}
```

**After Fix:**
```json
{
  "user": {
    "account_type": "OWNER",
    "platform_role": "NONE",
    "role": null,
    "role_name": null,
    "final_userRole": "OWNER",
    "user_roles": [],
    "employment": {
      "role": "OWNER",
      "business": {
        "id": "...",
        "name": "DataLogique Systems"
      }
    }
  },
  "employment": {
    "role": "OWNER",
    "business": {...}
  }
}
```

## Frontend Integration

The frontend can now access user roles via:

1. **`user.final_userRole`** - Primary role (from BusinessMembership or UserRole)
2. **`user.employment.role`** - Business-level role
3. **`user.user_roles`** - Array of all scoped roles (if using UserRole system)
4. **`user.employment.business`** - Business details

## Status

✅ **FIXED** - All role fields now properly serialized
✅ System check passes
✅ Login tested successfully
✅ Ready for frontend use

The frontend should now display user roles correctly in the console and UI.
