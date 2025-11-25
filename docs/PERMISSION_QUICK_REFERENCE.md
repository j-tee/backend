# Unified Permission System - Quick Reference Card

## 🎯 When to Use What

| Scenario | Use This | Example |
|----------|----------|---------|
| DRF ViewSet | `UnifiedObjectPermission` | `permission_classes = [UnifiedObjectPermission]` |
| Filter queryset | `filter_accessible()` | `filter_accessible(user, Model.objects.all(), 'perm')` |
| Quick check | `check_permission()` | `if check_permission(user, 'perm', obj):` |
| Custom action | `service.check()` | `service.check('perm', obj, raise_exception=True)` |
| Decorator | `@require_permission` | `@require_permission('perm', obj_param='instance')` |

## 🚀 Quick Start

### 1. Check Permission (Simple)
```python
from accounts.permissions import check_permission

if check_permission(request.user, 'inventory.change_storefront', storefront):
    storefront.name = "New Name"
    storefront.save()
```

### 2. Check Permission (With Exception)
```python
from accounts.permissions import check_permission, PermissionDenied

try:
    check_permission(
        request.user,
        'inventory.delete_storefront',
        storefront,
        raise_exception=True
    )
    storefront.delete()
except PermissionDenied as e:
    return Response({'error': str(e)}, status=403)
```

### 3. Filter Queryset
```python
from accounts.permissions import filter_accessible

# Get only storefronts user can view
accessible_storefronts = filter_accessible(
    request.user,
    StoreFront.objects.all(),
    'inventory.view_storefront'
)
```

### 4. DRF ViewSet (Standard)
```python
from accounts.permissions import UnifiedObjectPermission, filter_accessible

class MyViewSet(viewsets.ModelViewSet):
    permission_classes = [UnifiedObjectPermission]
    
    def get_queryset(self):
        return filter_accessible(
            self.request.user,
            MyModel.objects.all(),
            'app.view_model'
        )
```

### 5. DRF ViewSet (Custom Permissions)
```python
class MyViewSet(viewsets.ModelViewSet):
    permission_classes = [UnifiedObjectPermission]
    
    def get_permissions_required(self, action):
        return {
            'list': ['app.view_model'],
            'retrieve': ['app.view_model'],
            'create': ['app.add_model'],
            'update': ['app.change_model'],
            'destroy': ['app.delete_model'],
            'custom_action': ['app.custom_permission'],
        }.get(action, ['app.view_model'])
```

### 6. Custom Action
```python
from accounts.permissions import UnifiedPermissionService
from rest_framework.decorators import action

class MyViewSet(viewsets.ModelViewSet):
    @action(detail=True, methods=['post'])
    def custom_action(self, request, pk=None):
        obj = self.get_object()
        
        service = UnifiedPermissionService(request.user)
        service.check(
            'app.custom_permission',
            obj=obj,
            raise_exception=True
        )
        
        # Permission granted - do work
        return Response({'status': 'success'})
```

### 7. Business Context
```python
service = UnifiedPermissionService(user)
service.check(
    'sales.create_sale',
    business=business,
    raise_exception=True
)
```

### 8. Storefront Context
```python
service = UnifiedPermissionService(user)
service.check(
    'inventory.manage_employees',
    storefront=storefront,
    raise_exception=True
)
```

### 9. Using Decorators
```python
from accounts.permissions import require_permission

class MyViewSet(viewsets.ModelViewSet):
    
    @require_permission('app.change_model', obj_param='instance')
    def perform_update(self, instance):
        # Permission already checked by decorator
        super().perform_update(instance)
```

### 10. Check User's Role
```python
from accounts.permissions import UnifiedPermissionService

service = UnifiedPermissionService(user)
role = service.get_user_role_in_business(business)

if role == 'OWNER':
    # Owner-specific logic
    pass
elif role == 'ADMIN':
    # Admin-specific logic
    pass
```

## 📋 Permission String Format

### Standard Django Format
```
'app_label.permission_model'
```

### Examples
```python
'inventory.view_storefront'
'inventory.add_storefront'
'inventory.change_storefront'
'inventory.delete_storefront'
'sales.create_sale'
'reports.view_financial_reports'
'reports.export_reports'
```

## 🔍 Priority Order (Debug Reference)

When checking permissions, the system checks in this order:

```
1. ❌ Explicit DENY (Guardian) ───────── If denied here, always False
2. ✅ Platform Roles (SUPER_ADMIN) ──── Always True for SUPER_ADMIN
3. ✅ RBAC (Custom Roles) ──────────── Check user's roles & permissions
4. ✅ Rules (django-rules) ─────────── Check predicates
5. ✅ Guardian GRANT (object-level) ─── Check object permissions
6. ❌ Default DENY ─────────────────── If nothing matches, False
```

## 🛠️ Common Patterns

### Pattern 1: List + Detail ViewSet
```python
class ProductViewSet(viewsets.ModelViewSet):
    permission_classes = [UnifiedObjectPermission]
    
    def get_queryset(self):
        return filter_accessible(
            self.request.user,
            Product.objects.all(),
            'inventory.view_product'
        )
```
**Permissions checked:**
- `list`: `inventory.view_product`
- `retrieve`: `inventory.view_product`
- `create`: `inventory.add_product`
- `update`: `inventory.change_product`
- `destroy`: `inventory.delete_product`

### Pattern 2: Read-Only ViewSet
```python
class ReportViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [UnifiedObjectPermission]
    
    def get_queryset(self):
        return filter_accessible(
            self.request.user,
            Report.objects.all(),
            'reports.view_report'
        )
```

### Pattern 3: Custom Actions with Multiple Permissions
```python
@action(detail=True, methods=['post'])
def approve(self, request, pk=None):
    obj = self.get_object()
    service = UnifiedPermissionService(request.user)
    
    # Need BOTH permissions
    required = ['app.view_model', 'app.approve_model']
    for perm in required:
        service.check(perm, obj=obj, raise_exception=True)
    
    obj.approved = True
    obj.save()
    return Response({'status': 'approved'})
```

## ⚡ Performance Tips

### ✅ DO THIS (Efficient)
```python
# Get filtered queryset once
storefronts = filter_accessible(user, StoreFront.objects.all(), 'perm')
for storefront in storefronts:
    # Use storefront (already filtered)
    process(storefront)
```

### ❌ DON'T DO THIS (Slow)
```python
# Check each object individually (N queries!)
for storefront in StoreFront.objects.all():
    if check_permission(user, 'perm', storefront):
        process(storefront)
```

### Cache Clearing
```python
service = UnifiedPermissionService(user)

# Make permission check
can_edit = service.check('perm', obj)  # Cached

# User role changed
user.assign_role('NEW_ROLE', business)

# Clear cache for new checks
service.clear_cache()

# Fresh check with new role
can_edit = service.check('perm', obj)  # Rechecked
```

## 🐛 Debugging

### See Why Permission Denied
```python
from accounts.permissions import UnifiedPermissionService, PermissionDenied

service = UnifiedPermissionService(user)

try:
    service.check('inventory.delete_storefront', obj=storefront, raise_exception=True)
except PermissionDenied as e:
    print(f"Denied: {e.message}")
    print(f"Reason: {e.reason}")
```

### Debug Helper
```python
from accounts.permissions import UnifiedPermissionService

def debug_permission(user, perm, obj=None):
    service = UnifiedPermissionService(user)
    
    print(f"User: {user.email}")
    print(f"Permission: {perm}")
    print(f"Object: {obj}")
    print("-" * 60)
    print(f"Platform: {service._check_platform_permission(perm)}")
    print(f"RBAC: {service._check_rbac_permission(perm, None, None)}")
    print(f"Rules: {service._check_rules_permission(perm, obj)}")
    if obj:
        print(f"Guardian: {service._check_guardian_permission(perm, obj)}")
    print("-" * 60)
    print(f"Result: {service.check(perm, obj=obj)}")

# Usage
debug_permission(request.user, 'inventory.change_storefront', storefront)
```

## 📝 Testing

### Unit Test
```python
from accounts.permissions import UnifiedPermissionService, PermissionDenied

def test_permission(self):
    service = UnifiedPermissionService(self.user)
    
    # Test granted
    self.assertTrue(service.check('perm', obj=self.obj))
    
    # Test denied
    with self.assertRaises(PermissionDenied):
        service.check('other_perm', obj=self.obj, raise_exception=True)
```

### API Test
```python
def test_api_permission(self):
    self.client.force_authenticate(user=self.user)
    
    response = self.client.get('/api/storefronts/')
    
    self.assertEqual(response.status_code, 200)
    # Should only see accessible storefronts
    self.assertEqual(len(response.data['results']), 2)
```

## 🚫 Common Mistakes

### ❌ Checking Anonymous User
```python
# BAD - No check for authentication
if check_permission(request.user, 'perm'):
    do_something()

# GOOD - Check authentication first
if request.user.is_authenticated:
    if check_permission(request.user, 'perm'):
        do_something()

# BEST - Let DRF handle it
permission_classes = [UnifiedObjectPermission]
```

### ❌ Wrong Permission String
```python
# BAD - Missing app label
check_permission(user, 'change_storefront')

# GOOD - Full permission string
check_permission(user, 'inventory.change_storefront')
```

### ❌ Forgetting Object Context
```python
# BAD - No object for object-level permission
check_permission(user, 'inventory.delete_storefront')

# GOOD - Include object
check_permission(user, 'inventory.delete_storefront', storefront)
```

## 📚 More Help

- **Full Guide:** `docs/UNIFIED_PERMISSION_SYSTEM.md`
- **Examples:** `docs/UNIFIED_PERMISSION_EXAMPLE.py`
- **Summary:** `docs/PERMISSION_SYSTEM_FIX_SUMMARY.md`
- **Code:** `accounts/permissions.py`

---

**💡 Remember:** One system, one way, consistent everywhere!
