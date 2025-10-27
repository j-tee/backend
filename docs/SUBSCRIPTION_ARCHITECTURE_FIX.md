# Subscription Architecture Fix

## ❌ CRITICAL ISSUE IDENTIFIED

### Problem:
The current subscription system is **USER-CENTRIC** but should be **BUSINESS-CENTRIC**.

### Current Wrong Setup:
```python
class Subscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions')
    business = models.OneToOneField('accounts.Business', on_delete=models.CASCADE, 
                                   related_name='subscription', null=True, blank=True)
```

**Issues:**
1. ✗ Subscription is linked to `user` (WRONG - users can have multiple businesses)
2. ✗ Business is optional (`null=True, blank=True`)
3. ✗ User.subscription_status field exists (WRONG - status belongs to business)
4. ✗ User.has_active_subscription() method checks user subscriptions (WRONG)
5. ✗ A user with 2 businesses would need 2 separate user accounts (MAJOR FLAW)

### Correct Architecture:
```python
class Subscription(models.Model):
    business = models.OneToOneField('accounts.Business', on_delete=models.CASCADE, 
                                   related_name='subscription')  # REQUIRED, not optional
    # user field removed or changed to created_by for audit trail only
```

**Benefits:**
1. ✓ One subscription per business
2. ✓ User can own/access multiple businesses, each with its own subscription
3. ✓ Subscription status tied to business (business.subscription.status)
4. ✓ Access control: Check if user's business has active subscription
5. ✓ Business can change owner without losing subscription

---

## 🔧 REQUIRED CHANGES

### 1. Database Model Changes

#### subscriptions/models.py
```python
class Subscription(models.Model):
    # PRIMARY CHANGE: Make business the main relationship
    business = models.OneToOneField(
        'accounts.Business', 
        on_delete=models.CASCADE, 
        related_name='subscription',
        # NO null=True, blank=True - Business is REQUIRED
    )
    
    # Keep user for audit trail (who created the subscription)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='created_subscriptions',
        help_text='User who created this subscription'
    )
    
    # Remove: user = models.ForeignKey(User, ...)
```

#### accounts/models.py - Business Model
```python
class Business(models.Model):
    # ADD: Subscription status tracking
    subscription_status = models.CharField(
        max_length=20,
        choices=[
            ('ACTIVE', 'Active'),
            ('INACTIVE', 'Inactive'),
            ('TRIAL', 'Trial'),
            ('EXPIRED', 'Expired'),
            ('SUSPENDED', 'Suspended'),
        ],
        default='INACTIVE'
    )
    
    def has_active_subscription(self):
        """Check if business has active subscription"""
        try:
            return self.subscription.is_active()
        except Subscription.DoesNotExist:
            return False
    
    def get_subscription_limits(self):
        """Get subscription plan limits"""
        try:
            return {
                'max_users': self.subscription.plan.max_users,
                'max_storefronts': self.subscription.plan.max_storefronts,
                'max_products': self.subscription.plan.max_products,
                'max_transactions': self.subscription.plan.max_transactions_per_month,
            }
        except Subscription.DoesNotExist:
            return None
```

#### accounts/models.py - User Model Changes
```python
class User(AbstractBaseUser, PermissionsMixin):
    # REMOVE: subscription_status field (moved to Business)
    # subscription_status = models.CharField(...)  # DELETE THIS
    
    def has_active_subscription(self):
        """
        Check if user has access to any business with active subscription.
        Returns True if user is member of at least one business with active subscription.
        """
        from django.conf import settings
        
        # Bypass for development
        if getattr(settings, 'BYPASS_SUBSCRIPTION_CHECK', False):
            return True
        
        # Check if user has membership in any business with active subscription
        return self.business_memberships.filter(
            is_active=True,
            business__subscription__status__in=['ACTIVE', 'TRIAL']
        ).exists()
    
    def get_businesses_with_active_subscriptions(self):
        """Get all businesses user has access to with active subscriptions"""
        return self.business_memberships.filter(
            is_active=True,
            business__subscription__status__in=['ACTIVE', 'TRIAL']
        ).values_list('business', flat=True)
```

### 2. Migration Strategy

#### Option A: Fresh Installation (Recommended if no production data)
```bash
# Delete existing subscription tables
python manage.py migrate subscriptions zero

# Delete migration file
rm subscriptions/migrations/0002_*.py

# Recreate with correct structure
python manage.py makemigrations subscriptions
python manage.py migrate subscriptions
```

#### Option B: Data Migration (If production data exists)
```python
# Create migration to:
# 1. Add created_by field (nullable)
# 2. Copy user -> created_by
# 3. Make business required (remove null=True)
# 4. Remove user field
# 5. Add Business.subscription_status
# 6. Sync Business.subscription_status from Subscription.status
# 7. Remove User.subscription_status
```

### 3. API/View Changes

#### subscriptions/views.py
```python
class SubscriptionViewSet(viewsets.ModelViewSet):
    def create(self, request, *args, **kwargs):
        # OLD: subscription.user = request.user
        # NEW: subscription.business = business (from request)
        
        business_id = request.data.get('business_id')
        business = get_object_or_404(Business, id=business_id)
        
        # Check user has permission to create subscription for this business
        if not business.memberships.filter(
            user=request.user, 
            role__in=['OWNER', 'ADMIN']
        ).exists():
            return Response({'error': 'Not authorized'}, status=403)
        
        # Create subscription for business
        subscription = Subscription.objects.create(
            business=business,
            created_by=request.user,
            plan=plan,
            ...
        )
```

#### Permission Checks - Update ALL views
```python
# OLD: Check user subscription
if not request.user.has_active_subscription():
    return Response({'error': 'No active subscription'}, status=403)

# NEW: Check business subscription
business = get_user_business(request)  # Get current working business
if not business.has_active_subscription():
    return Response({'error': 'Business subscription inactive'}, status=403)
```

### 4. Serializer Changes

```python
class SubscriptionSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(source='business.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.name', read_only=True)
    
    class Meta:
        model = Subscription
        fields = [
            'id', 'business', 'business_name', 
            'created_by', 'created_by_name',
            'plan', 'status', ...
        ]
        read_only_fields = ['created_by']
```

---

## 🎯 WORKFLOW CHANGES

### Before (WRONG):
1. User registers → Creates user account
2. User subscribes → Subscription linked to user
3. User creates business → Business has no subscription link
4. **PROBLEM:** User wants second business → Must create new email/account

### After (CORRECT):
1. User registers → Creates user account
2. User creates business → Business created
3. **Business subscribes** → Subscription linked to business
4. User creates second business → Creates another business
5. **Second business subscribes** → Separate subscription for business #2
6. **Same user** now has access to 2 businesses, each with own subscription

---

## 📊 ACCESS CONTROL LOGIC

### Check Business Access + Subscription
```python
def can_perform_action(user, business_id, action):
    # 1. Check user is member of business
    membership = BusinessMembership.objects.filter(
        user=user,
        business_id=business_id,
        is_active=True
    ).first()
    
    if not membership:
        return False, "Not a member of this business"
    
    # 2. Check business has active subscription
    try:
        subscription = membership.business.subscription
        if not subscription.is_active():
            return False, "Business subscription inactive"
    except Subscription.DoesNotExist:
        return False, "No subscription for this business"
    
    # 3. Check subscription limits
    limits = subscription.plan
    if action == 'create_user' and membership.business.memberships.count() >= limits.max_users:
        return False, "User limit reached"
    
    return True, "OK"
```

---

## ✅ IMPLEMENTATION CHECKLIST

- [ ] Update Subscription model (business required, add created_by)
- [ ] Update Business model (add subscription_status, helper methods)
- [ ] Update User model (remove subscription_status, update has_active_subscription)
- [ ] Create/Run migrations
- [ ] Update SubscriptionViewSet (business-centric creation)
- [ ] Update all serializers
- [ ] Update permission checks across all apps
- [ ] Update tasks.py (check_expiring_subscriptions, etc.)
- [ ] Update alerts to use business instead of user
- [ ] Update admin interface
- [ ] Update all API documentation
- [ ] Test subscription creation for business
- [ ] Test user with multiple businesses
- [ ] Test subscription limits per business
- [ ] Test business owner transfer

---

## 🚀 RECOMMENDED APPROACH

Given the current state, I recommend:

1. **STOP** - Don't apply current migrations yet
2. **FIX** the models first (business-centric)
3. **DELETE** the 0002 migration file
4. **RECREATE** migrations with correct structure
5. **UPDATE** all related code (views, serializers, permissions)
6. **THEN** migrate and test

This prevents the need for complex data migrations later.

---

## ❓ QUESTIONS TO CONFIRM

1. **Can we reset subscriptions?** (No production subscription data yet?)
   - YES → Use fresh migration approach
   - NO → Need data migration script

2. **Business creation flow:**
   - Should business start with trial subscription automatically?
   - Or require explicit subscription creation?

3. **Multiple businesses per user:**
   - Confirmed: Same user can own/access multiple businesses
   - Each business has separate subscription
   - Correct?

---

**STATUS:** Awaiting confirmation before proceeding with fixes.
