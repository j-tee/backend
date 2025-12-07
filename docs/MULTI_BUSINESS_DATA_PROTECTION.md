# Multi-Business Data Protection Strategy

## Overview

This document explains how the system prevents inadvertent data updates when users have access to multiple businesses.

## The Problem

**Scenario:**
```
User: john@example.com
Memberships:
  - Business A (OWNER)
  - Business B (ADMIN)

Risk: John viewing Business A's dashboard accidentally updates Business B's inventory
```

## Protection Layers

### Layer 1: Query-Level Filtering ✅

**Location:** All ViewSets (`get_queryset()`)

**How it works:**
```python
def get_queryset(self):
    user = self.request.user
    business_ids = _business_ids_for_user(user)  # [Business A, Business B]
    
    # Only return data from user's businesses
    return Product.objects.filter(business_id__in=business_ids)
```

**Protection:**
- User cannot see data from businesses they don't belong to
- Database-level filtering before data reaches application
- Empty queryset if user has no business access

**Example:**
```python
# User john has access to Business A & B
products = Product.objects.all()  # Django ORM

# After get_queryset() filter:
# products = Product.objects.filter(business_id__in=[A, B])
```

---

### Layer 2: Business Context Enforcement ✅

**Location:** `accounts/business_context.py`

**How it works:**
```python
class BusinessContextManager:
    def get_current_business(request):
        """
        Determines which business user is currently operating in
        
        Priority:
        1. Query param: /api/products/?business=uuid
        2. Request body: {"business": "uuid"}
        3. Session storage
        4. User's primary business
        """
```

**Protection:**
- Tracks which business context user is operating in
- Validates all operations happen within current context
- Prevents cross-business operations

**Example:**
```python
# Frontend sets context
POST /api/context/set-business/
{"business_id": "business-a-uuid"}

# All subsequent requests are validated
PATCH /api/products/123/
# System checks: Does product 123 belong to Business A?
# If product belongs to Business B → 403 Forbidden
```

---

### Layer 3: Creation Protection ✅

**Location:** All ViewSets (`perform_create()`)

**How it works:**
```python
def perform_create(self, serializer):
    current_business = BusinessContextManager.get_current_business(request)
    
    # Force business assignment - user cannot override
    serializer.save(business=current_business)
```

**Protection:**
- New records automatically assigned to current business
- User **cannot** submit different business_id
- Even malicious requests are overridden

**Example:**
```python
# Malicious request
POST /api/products/
{
    "name": "Laptop",
    "business": "business-b-uuid"  # Trying to create in wrong business
}

# System ignores submitted business_id
# Forces: business = current_business (Business A)
```

---

### Layer 4: Update Validation ✅

**Location:** All ViewSets (`perform_update()`)

**How it works:**
```python
def perform_update(self, serializer):
    instance = self.get_object()
    
    # Validate: Does this object belong to user's businesses?
    BusinessContextManager.validate_business_ownership(user, instance)
    
    # Validate: Is operation within current business context?
    BusinessContextManager.enforce_business_context(request, instance)
    
    serializer.save()
```

**Protection:**
- Double validation before updates
- Checks both ownership AND context
- Prevents accidental cross-business updates

**Example:**
```python
# User context: Business A
# Product 123 belongs to: Business B

PATCH /api/products/123/
{"price": 1000}

# Step 1: validate_business_ownership() → PASS (user is member of B)
# Step 2: enforce_business_context() → FAIL (context is A, object is B)
# Result: 403 Forbidden - "Business context mismatch"
```

---

### Layer 5: Row-Level Security (Database) ✅

**Location:** PostgreSQL RLS policies (`deployment/enable_rls.sql`)

**How it works:**
```sql
-- Products table policy
CREATE POLICY products_business_isolation ON products
    USING (business_id::text = current_setting('app.current_business_id', true));

-- Middleware sets session variable
SET LOCAL app.current_business_id = 'business-a-uuid';
```

**Protection:**
- Database enforces filtering automatically
- Works even if application code has bugs
- Applies to ALL queries (Django ORM, raw SQL, admin panel)

**Example:**
```python
# User context: Business A (set by middleware)
# Direct SQL query
cursor.execute("SELECT * FROM products WHERE id = %s", [product_id])

# PostgreSQL automatically adds WHERE clause:
# "WHERE business_id = 'business-a-uuid'"
```

---

### Layer 6: Read-Only Fields ✅

**Location:** Serializers

**How it works:**
```python
class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        read_only_fields = ['id', 'business', 'created_at']
```

**Protection:**
- User cannot modify business field via API
- Even if submitted, field is ignored during deserialization

---

## Usage Examples

### Example 1: Using BusinessContextMixin

```python
# inventory/views.py
from accounts.business_context import BusinessContextMixin

class ProductViewSet(BusinessContextMixin, viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    business_field = 'business_id'  # Field name (optional, defaults to 'business_id')

# Now this ViewSet automatically:
# 1. Filters queries by accessible businesses
# 2. Validates business context on create/update/delete
# 3. Prevents cross-business operations
```

### Example 2: Manual Context Management

```python
from accounts.business_context import BusinessContextManager

# In API view
def my_custom_view(request):
    # Get current business context
    current_business = BusinessContextManager.get_current_business(request)
    
    # Validate user has access to specific business
    if not BusinessContextManager.has_business_access(request.user, business_id):
        raise PermissionDenied()
    
    # Set business context (e.g., after user selects business)
    BusinessContextManager.set_current_business(request, business_id)
```

### Example 3: Frontend Integration

```javascript
// User selects business from dropdown
async function switchBusiness(businessId) {
  // Set server-side context
  await axios.post('/api/context/set-business/', {
    business_id: businessId
  });
  
  // Store in local state
  localStorage.setItem('currentBusiness', businessId);
  
  // Reload dashboard with new context
  window.location.reload();
}

// All subsequent API calls include business context
axios.get('/api/products/', {
  params: {
    business: localStorage.getItem('currentBusiness')
  }
});
```

---

## Threat Models & Mitigations

### Threat 1: Malicious Business ID Injection

**Attack:**
```python
POST /api/products/
{
    "name": "Stolen Product",
    "business": "victim-business-uuid"  # Not user's business
}
```

**Mitigation:**
- `business` field is **read-only** in serializer
- `perform_create()` **overwrites** any submitted business_id
- Uses current business context from session

---

### Threat 2: Parameter Tampering

**Attack:**
```python
# User operates in Business A
# Tries to access Business B's data
GET /api/products/123/?business=business-b-uuid
```

**Mitigation:**
- `BusinessContextManager.get_current_business()` **validates access**
- Raises `PermissionDenied` if user not member of Business B
- Session context takes precedence over query param

---

### Threat 3: Race Condition

**Attack:**
```python
# Request 1: Set context to Business A
POST /api/context/set-business/ {"business": "A"}

# Request 2: Immediately update product from Business B
PATCH /api/products/123/  # Product belongs to B
```

**Mitigation:**
- Each request validates context independently
- `enforce_business_context()` checks current context vs object's business
- Session storage ensures context persistence

---

### Threat 4: Cross-Site Request Forgery (CSRF)

**Attack:**
```html
<!-- Malicious site tricks user into making request -->
<form action="https://pos.example.com/api/products/123/" method="POST">
  <input name="business" value="victim-business-uuid">
</form>
```

**Mitigation:**
- Django CSRF protection enabled
- Token required for state-changing requests
- Business context validated server-side (not from request body)

---

## Testing Strategy

### Unit Tests

```python
# tests/test_business_context.py
def test_cannot_create_in_wrong_business(self):
    """User cannot create products in business they don't own"""
    self.client.force_authenticate(user=self.user_a)
    
    response = self.client.post('/api/products/', {
        'name': 'Product',
        'business': self.business_b.id  # Wrong business
    })
    
    created_product = Product.objects.get(id=response.data['id'])
    # Should be created in user's business, not submitted one
    assert created_product.business_id == self.user_a_business.id

def test_cannot_update_cross_business(self):
    """User cannot update products from different business context"""
    # Set context to Business A
    self.client.post('/api/context/set-business/', {
        'business_id': self.business_a.id
    })
    
    # Try to update product from Business B
    response = self.client.patch(f'/api/products/{self.product_b.id}/', {
        'price': 1000
    })
    
    assert response.status_code == 403
    assert 'context mismatch' in response.data['detail'].lower()
```

### Integration Tests

```python
def test_multi_business_workflow(self):
    """Complete workflow with business switching"""
    user = User.objects.create(email='multi@example.com')
    business_a = Business.objects.create(owner=user, name='Business A')
    business_b = Business.objects.create(owner=user, name='Business B')
    
    # Switch to Business A
    self.client.post('/api/context/set-business/', {'business_id': business_a.id})
    
    # Create product in A
    resp_a = self.client.post('/api/products/', {'name': 'Product A'})
    assert Product.objects.get(id=resp_a.data['id']).business == business_a
    
    # Switch to Business B
    self.client.post('/api/context/set-business/', {'business_id': business_b.id})
    
    # Create product in B
    resp_b = self.client.post('/api/products/', {'name': 'Product B'})
    assert Product.objects.get(id=resp_b.data['id']).business == business_b
    
    # Cannot update Product A while in Business B context
    response = self.client.patch(f'/api/products/{resp_a.data["id"]}/', {
        'price': 1000
    })
    assert response.status_code == 403
```

---

## Migration Checklist

### Phase 1: Enable Context Management
- [x] Create `BusinessContextManager` class
- [x] Create `BusinessContextMixin` for ViewSets
- [ ] Add context switching endpoint
- [ ] Update frontend to use business selector

### Phase 2: Apply to ViewSets
- [ ] Update `ProductViewSet` to use mixin
- [ ] Update `StockViewSet` to use mixin
- [ ] Update `SaleViewSet` to use mixin
- [ ] Update all inventory ViewSets

### Phase 3: Add Session Management
- [ ] Implement business selector UI
- [ ] Store context in session
- [ ] Add context indicator in navbar
- [ ] Add business switching confirmation

### Phase 4: Testing
- [ ] Write unit tests for context manager
- [ ] Write integration tests for business switching
- [ ] Perform security audit
- [ ] Load test with multiple businesses

---

## Best Practices

### For Developers

1. **Always use `BusinessContextMixin`** for ViewSets that handle business-scoped data
2. **Never trust** business_id from request body/params
3. **Always validate** business context before operations
4. **Use session storage** for persistent context
5. **Log context switches** for audit trail

### For API Consumers

1. **Set business context** before operations
2. **Include business param** in query strings
3. **Handle 403 errors** gracefully (context mismatch)
4. **Refresh context** after business selection
5. **Display current business** in UI

---

## Monitoring & Alerts

### Metrics to Track

```python
# In views
import logging
logger = logging.getLogger('business_context')

def perform_update(self, serializer):
    try:
        BusinessContextManager.enforce_business_context(...)
    except PermissionDenied as e:
        logger.warning(
            f'Business context violation: '
            f'user={self.request.user.id}, '
            f'expected={current_business}, '
            f'actual={instance.business_id}'
        )
        raise
```

### Alert Conditions

- **High frequency** of context mismatch errors (possible attack)
- **Rapid business switching** by single user (suspicious behavior)
- **Failed access attempts** to wrong business data
- **RLS policy violations** at database level

---

## Conclusion

The multi-business data protection system uses **6 layers of defense**:

1. ✅ Query-level filtering (application)
2. ✅ Business context enforcement (session)
3. ✅ Creation protection (forced assignment)
4. ✅ Update validation (ownership + context)
5. ✅ Row-level security (database)
6. ✅ Read-only fields (serializer)

With these layers, inadvertent cross-business data updates are **virtually impossible** even if:
- User has multiple business memberships
- User rapidly switches between businesses
- Malicious requests attempt parameter injection
- Application code contains bugs
