# Unified Permission System - Migration Guide

## Problem Statement

The POS backend previously used **three different permission systems** simultaneously:
1. **Django-rules** - Rule-based permissions with predicates
2. **Django Guardian** - Object-level permissions
3. **Custom RBAC** - Role and Permission models with many-to-many relationships

This created several critical issues:

### Issues with Dual/Triple System

1. **Complexity & Confusion**
   - Developers don't know which system to check
   - "Why do I have access?" becomes impossible to debug
   - Onboarding new developers takes longer

2. **Performance Overhead**
   - Every permission check queries multiple systems
   - No unified caching strategy
   - N+1 queries when checking multiple objects

3. **Potential Conflicts**
   - Guardian says "No" but RBAC says "Yes"
   - Rules grant access but Guardian denies
   - No clear precedence order

4. **Maintenance Burden**
   - Bug fixes must be applied to multiple systems
   - Testing requires checking all combinations
   - Documentation must explain all three systems

## Solution: Unified Permission Service

The `UnifiedPermissionService` provides a **single interface** that intelligently combines all three systems with a clear priority order.

### Priority Hierarchy

```
1. Explicit DENY (Guardian) ─────────── Highest Priority
2. Platform Roles (SUPER_ADMIN) ───────┐
3. RBAC (Custom Roles + Permissions) ──┤─── Normal Operations
4. Rules (django-rules predicates) ────┤
5. Guardian GRANT (object-level) ──────┘
6. Default DENY ────────────────────── Lowest Priority (safe default)
```

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              UnifiedPermissionService                        │
│                                                               │
│  check(permission, obj=None, business=None, storefront=None) │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
        ▼             ▼             ▼
┌─────────────┐ ┌──────────┐ ┌─────────┐
│ django-rules│ │ Guardian │ │  RBAC   │
│             │ │          │ │         │
│ Predicates  │ │ Object   │ │ Roles + │
│ & Rules     │ │ Perms    │ │ Perms   │
└─────────────┘ └──────────┘ └─────────┘
```

## Migration Guide

### Before (Confusing Multiple Checks)

```python
# Old approach - checking multiple systems manually
def can_user_edit_storefront(user, storefront):
    # Check 1: Guardian object permission
    if user.has_perm('inventory.change_storefront', storefront):
        return True
    
    # Check 2: django-rules
    if rules.has_perm('inventory.change_storefront', user, storefront):
        return True
    
    # Check 3: Custom RBAC
    business = storefront.business_link.business
    if user.has_permission('change_storefront', business=business):
        return True
    
    # Check 4: Platform admin override
    if user.platform_role == 'SUPER_ADMIN':
        return True
    
    return False
```

### After (Single Unified Check)

```python
# New approach - one clear check
from accounts.permissions import UnifiedPermissionService

def can_user_edit_storefront(user, storefront):
    service = UnifiedPermissionService(user)
    return service.check('inventory.change_storefront', obj=storefront)
```

### Quick Function for Simple Cases

```python
from accounts.permissions import check_permission

# Even simpler for one-off checks
if check_permission(request.user, 'inventory.change_storefront', storefront):
    storefront.name = new_name
    storefront.save()
```

### DRF ViewSet Integration

#### Before (Multiple Permission Classes)

```python
from rest_framework import viewsets, permissions
from guardian.shortcuts import get_objects_for_user
import rules

class StoreFrontViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        # Check multiple systems manually
        if user.platform_role == 'SUPER_ADMIN':
            return StoreFront.objects.all()
        
        # Guardian objects
        guardian_objs = get_objects_for_user(
            user, 
            'inventory.view_storefront',
            StoreFront
        )
        
        # Business-based filtering
        from accounts.models import BusinessMembership
        business_ids = BusinessMembership.objects.filter(
            user=user,
            is_active=True
        ).values_list('business_id', flat=True)
        
        business_objs = StoreFront.objects.filter(
            business_link__business_id__in=business_ids
        )
        
        # Combine results
        return (guardian_objs | business_objs).distinct()
    
    def perform_update(self, serializer):
        instance = self.get_object()
        
        # Manual permission check
        if not (
            rules.has_perm('inventory.change_storefront', self.request.user, instance) or
            self.request.user.has_perm('inventory.change_storefront', instance) or
            self.request.user.platform_role == 'SUPER_ADMIN'
        ):
            raise PermissionDenied("You cannot edit this storefront")
        
        serializer.save()
```

#### After (Clean and Simple)

```python
from rest_framework import viewsets
from accounts.permissions import UnifiedObjectPermission, filter_accessible

class StoreFrontViewSet(viewsets.ModelViewSet):
    permission_classes = [UnifiedObjectPermission]
    
    def get_queryset(self):
        # Single line to get accessible objects
        return filter_accessible(
            self.request.user,
            StoreFront.objects.all(),
            'inventory.view_storefront'
        )
    
    # No need to override perform_update - UnifiedObjectPermission handles it!
```

### Custom Permission Requirements

```python
from accounts.permissions import UnifiedObjectPermission

class StoreFrontViewSet(viewsets.ModelViewSet):
    permission_classes = [UnifiedObjectPermission]
    
    def get_permissions_required(self, action):
        """Override to specify custom permissions per action"""
        return {
            'list': ['inventory.view_storefront'],
            'retrieve': ['inventory.view_storefront'],
            'create': ['inventory.add_storefront'],
            'update': ['inventory.change_storefront'],
            'destroy': ['inventory.delete_storefront'],
            'assign_employees': ['inventory.manage_storefront_employees'],
        }.get(action, ['inventory.view_storefront'])
```

### Using Decorators

```python
from accounts.permissions import require_permission

class StoreFrontViewSet(viewsets.ModelViewSet):
    
    @require_permission('inventory.change_storefront', obj_param='instance')
    def perform_update(self, instance):
        # Permission already checked by decorator
        super().perform_update(instance)
    
    @require_permission('inventory.delete_storefront', obj_param='instance')
    def perform_destroy(self, instance):
        # Permission already checked
        super().perform_destroy(instance)
```

## Advanced Usage

### Business-Scoped Permissions

```python
from accounts.permissions import UnifiedPermissionService

def process_sale(user, sale, business):
    service = UnifiedPermissionService(user)
    
    # Check permission within business context
    if service.check('sales.create_sale', business=business, raise_exception=True):
        # Process the sale
        sale.status = 'COMPLETED'
        sale.save()
```

### Storefront-Scoped Permissions

```python
def assign_cashier(user, cashier_user, storefront):
    service = UnifiedPermissionService(user)
    
    # Check if user can manage employees at this specific storefront
    if service.check(
        'inventory.manage_storefront_employees',
        storefront=storefront,
        raise_exception=True
    ):
        StoreFrontEmployee.objects.create(
            storefront=storefront,
            user=cashier_user,
            role='CASHIER'
        )
```

### Checking Multiple Permissions

```python
from accounts.permissions import UnifiedPermissionService

def export_financial_report(user, business):
    service = UnifiedPermissionService(user)
    
    # User needs BOTH permissions
    required_perms = [
        'reports.view_financial_reports',
        'reports.export_reports'
    ]
    
    for perm in required_perms:
        if not service.check(perm, business=business):
            raise PermissionDenied(f"Missing permission: {perm}")
    
    # Generate and export report
    return generate_report(business)
```

### Getting User's Role

```python
from accounts.permissions import UnifiedPermissionService

def customize_dashboard(user, business):
    service = UnifiedPermissionService(user)
    role = service.get_user_role_in_business(business)
    
    if role == 'OWNER':
        return get_owner_dashboard(business)
    elif role == 'ADMIN':
        return get_admin_dashboard(business)
    elif role == 'MANAGER':
        return get_manager_dashboard(business)
    else:
        return get_staff_dashboard(business)
```

## Performance Optimization

### Built-in Caching

The service automatically caches permission checks within a request:

```python
service = UnifiedPermissionService(user)

# First check - queries database
can_edit = service.check('inventory.change_storefront', obj=storefront)

# Subsequent checks - returns cached result
can_edit_again = service.check('inventory.change_storefront', obj=storefront)
```

### Clear Cache After Role Changes

```python
from accounts.permissions import UnifiedPermissionService

def assign_role_to_user(user, role, business):
    # Assign the role
    user.assign_role(role, business=business)
    
    # Clear permission cache
    service = UnifiedPermissionService(user)
    service.clear_cache()
```

### Bulk Object Filtering

Instead of checking each object individually:

```python
# BAD - N queries
service = UnifiedPermissionService(user)
accessible_storefronts = []
for storefront in StoreFront.objects.all():
    if service.check('inventory.view_storefront', obj=storefront):
        accessible_storefronts.append(storefront)

# GOOD - Single optimized query
accessible_storefronts = service.get_accessible_queryset(
    StoreFront.objects.all(),
    'inventory.view_storefront'
)
```

## Testing

### Unit Tests

```python
from django.test import TestCase
from accounts.permissions import UnifiedPermissionService, PermissionDenied

class PermissionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(email='test@example.com')
        self.business = Business.objects.create(name='Test Business')
        self.storefront = StoreFront.objects.create(name='Test Store')
    
    def test_owner_can_edit_storefront(self):
        # Assign OWNER role
        self.user.assign_role('OWNER', business=self.business)
        
        # Check permission
        service = UnifiedPermissionService(self.user)
        self.assertTrue(
            service.check('inventory.change_storefront', obj=self.storefront)
        )
    
    def test_staff_cannot_delete_storefront(self):
        # Assign STAFF role (lower privilege)
        self.user.assign_role('STAFF', business=self.business)
        
        # Should raise PermissionDenied
        service = UnifiedPermissionService(self.user)
        with self.assertRaises(PermissionDenied):
            service.check(
                'inventory.delete_storefront',
                obj=self.storefront,
                raise_exception=True
            )
    
    def test_super_admin_overrides_all(self):
        # Make user super admin
        self.user.platform_role = 'SUPER_ADMIN'
        self.user.save()
        
        # Should have permission even without business membership
        service = UnifiedPermissionService(self.user)
        self.assertTrue(
            service.check('inventory.delete_storefront', obj=self.storefront)
        )
```

### Integration Tests

```python
from rest_framework.test import APITestCase
from rest_framework import status

class StoreFrontAPITests(APITestCase):
    def test_manager_can_update_storefront(self):
        # Setup
        user = self.create_user_with_role('MANAGER')
        storefront = self.create_storefront()
        self.client.force_authenticate(user=user)
        
        # Attempt update
        response = self.client.patch(
            f'/api/storefronts/{storefront.id}/',
            {'name': 'Updated Name'}
        )
        
        # Should succeed
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_staff_cannot_delete_storefront(self):
        # Setup
        user = self.create_user_with_role('STAFF')
        storefront = self.create_storefront()
        self.client.force_authenticate(user=user)
        
        # Attempt deletion
        response = self.client.delete(f'/api/storefronts/{storefront.id}/')
        
        # Should be denied
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
```

## Debugging Permission Issues

### Enable Debug Mode

```python
from accounts.permissions import UnifiedPermissionService

service = UnifiedPermissionService(user)

# Check with exception to get detailed reason
try:
    service.check(
        'inventory.delete_storefront',
        obj=storefront,
        raise_exception=True
    )
except PermissionDenied as e:
    print(f"Denied: {e.message}")
    print(f"Reason: {e.reason}")
```

### Check All Permission Sources

```python
def debug_permission(user, permission, obj=None):
    """Helper function to see which systems grant/deny permission"""
    service = UnifiedPermissionService(user)
    
    print(f"Checking: {permission} for {user.email}")
    print(f"Object: {obj}")
    print("="*60)
    
    # Check each system individually
    print(f"Platform Permission: {service._check_platform_permission(permission)}")
    print(f"RBAC Permission: {service._check_rbac_permission(permission, None, None)}")
    print(f"Rules Permission: {service._check_rules_permission(permission, obj)}")
    if obj:
        print(f"Guardian Permission: {service._check_guardian_permission(permission, obj)}")
    
    print("="*60)
    print(f"Final Result: {service.check(permission, obj=obj)}")

# Usage
debug_permission(
    user=request.user,
    permission='inventory.change_storefront',
    obj=storefront
)
```

## Migration Checklist

### Phase 1: Add Unified System (No Breaking Changes)
- [x] Create `accounts/permissions.py` with `UnifiedPermissionService`
- [ ] Add tests for unified permission system
- [ ] Deploy without removing old systems

### Phase 2: Migrate ViewSets
- [ ] Update ViewSets to use `UnifiedObjectPermission`
- [ ] Replace manual permission checks with `check_permission()`
- [ ] Test each ViewSet thoroughly

### Phase 3: Update Business Logic
- [ ] Replace direct `rules.has_perm()` calls with `service.check()`
- [ ] Replace Guardian `user.has_perm(perm, obj)` with unified service
- [ ] Replace custom RBAC checks with unified service

### Phase 4: Deprecate Old Patterns
- [ ] Add deprecation warnings to old permission checking code
- [ ] Update documentation to show unified approach only
- [ ] Create linter rules to catch old patterns

### Phase 5: Cleanup (Optional)
- [ ] Remove django-rules if no longer needed
- [ ] Remove Guardian if object-level permissions not required
- [ ] Simplify RBAC system if rules are sufficient

## Best Practices

### DO ✅

- Use `UnifiedPermissionService` for all permission checks
- Use `filter_accessible()` for querysets
- Raise exceptions for critical operations: `check(..., raise_exception=True)`
- Clear cache after role changes
- Document custom permission requirements in ViewSets

### DON'T ❌

- Don't mix old and new permission checks
- Don't check permissions in templates (do it in views)
- Don't forget to authenticate before checking permissions
- Don't cache User objects across requests (cached permissions become stale)
- Don't bypass permission system for "performance" (use queryset filtering instead)

## Summary

The `UnifiedPermissionService` solves the dual/triple permission system problem by:

1. **Single Interface**: One method to check all permissions
2. **Clear Priority**: Predictable precedence order
3. **Performance**: Built-in caching and optimized queries
4. **Debugging**: Detailed error messages and denial reasons
5. **Flexibility**: Works with existing django-rules, Guardian, and RBAC
6. **Backward Compatible**: Can be adopted gradually without breaking changes

**Result**: Simpler code, fewer bugs, better performance, easier maintenance.
