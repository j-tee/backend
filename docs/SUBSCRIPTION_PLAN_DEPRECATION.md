# Subscription Plan System Deprecation

**Date:** November 3, 2025  
**Status:** DEPRECATED  
**Migration:** 0004_deprecate_old_subscription_plans  

---

## 🚨 WHAT WAS REMOVED

The old `SubscriptionPlan` model and its associated infrastructure have been deprecated and removed from the public API.

### Removed Components

1. **Admin Interface**
   - `SubscriptionPlanAdmin` - Removed from Django admin
   - No longer visible in `/admin/subscriptions/`

2. **API Endpoints**
   - `GET /api/subscriptions/api/plans/` - REMOVED
   - `POST /api/subscriptions/api/plans/` - REMOVED
   - `PUT/PATCH /api/subscriptions/api/plans/{id}/` - REMOVED
   - `DELETE /api/subscriptions/api/plans/{id}/` - REMOVED
   - `GET /api/subscriptions/api/plans/popular/` - REMOVED
   - `GET /api/subscriptions/api/plans/{id}/features/` - REMOVED

3. **Serializers** (Deprecated but kept)
   - `SubscriptionPlanSerializer` - Marked as deprecated

4. **Views**
   - `SubscriptionPlanViewSet` - Removed entirely

---

## ✅ WHAT REPLACES IT

Use the new **SubscriptionPricingTier** system:

### New Components

1. **Models**
   - `SubscriptionPricingTier` - Dynamic storefront-based pricing
   - `TaxConfiguration` - Flexible tax configuration
   - `ServiceCharge` - Flexible service charges

2. **Admin Interface**
   - `SubscriptionPricingTierAdmin`
   - `TaxConfigurationAdmin`
   - `ServiceChargeAdmin`

3. **API Endpoints**
   - `GET /api/subscriptions/api/pricing-tiers/` - Manage pricing tiers
   - `GET /api/subscriptions/api/tax-config/` - Manage taxes
   - `GET /api/subscriptions/api/service-charges/` - Manage charges
   - **NEW:** `GET /api/subscriptions/my-pricing/` - Auto-calculated pricing

---

## 📊 DATABASE CHANGES

### Migration 0004_deprecate_old_subscription_plans

**Changes Applied:**
```python
# Made Subscription.plan field nullable and optional
plan = models.ForeignKey(
    SubscriptionPlan,
    on_delete=models.PROTECT,
    related_name='subscriptions',
    null=True,
    blank=True,
    help_text='DEPRECATED: Use SubscriptionPricingTier instead'
)
```

**Why:**
- Allows existing subscriptions with plans to continue working
- New subscriptions won't require a plan
- Prepares for complete removal in future migration

---

## 🔄 MIGRATION PATH

### For Existing Subscriptions

**Before (Old System):**
```python
subscription = Subscription.objects.create(
    user=user,
    business=business,
    plan=selected_plan,  # User selected from dropdown
    amount=selected_plan.price,
    ...
)
```

**After (New System):**
```python
# 1. Get storefront count automatically
storefront_count = business.business_storefronts.filter(is_active=True).count()

# 2. Find pricing tier
tier = SubscriptionPricingTier.objects.filter(
    is_active=True,
    min_storefronts__lte=storefront_count
).filter(
    Q(max_storefronts__gte=storefront_count) | Q(max_storefronts__isnull=True)
).first()

# 3. Calculate price
base_price = tier.calculate_price(storefront_count)

# 4. Calculate taxes
taxes = TaxConfiguration.objects.filter(
    is_active=True,
    applies_to_subscriptions=True
)
total_tax = sum(tax.calculate_amount(base_price) for tax in taxes)

# 5. Create subscription (no plan needed)
subscription = Subscription.objects.create(
    user=user,
    business=business,
    plan=None,  # No plan!
    amount=base_price + total_tax,
    ...
)
```

---

## 🗑️ CLEANUP TASKS

### Completed
- ✅ Made `plan` field nullable
- ✅ Removed `SubscriptionPlanAdmin` from admin
- ✅ Removed `SubscriptionPlanViewSet` from API
- ✅ Removed `/plans/` URL endpoint
- ✅ Marked serializers as deprecated
- ✅ Updated documentation

### Pending (Future Migration)
- [ ] Migrate existing subscription data
- [ ] Remove `plan` field from Subscription model
- [ ] Drop `subscription_plans` table
- [ ] Remove `SubscriptionPlan` model entirely
- [ ] Remove deprecated serializers
- [ ] Clean up any remaining references

---

## 📝 EXISTING DATA

**Current State:**
- `subscription_plans` table still exists in database
- Existing subscriptions may have `plan_id` populated
- Table will be dropped in future migration after data migration

**Action Required:**
1. Audit all existing subscriptions
2. Verify they work without plan references
3. Plan data migration strategy
4. Schedule complete removal

---

## 🔧 FOR DEVELOPERS

### If You See Errors About Missing Plans

**Error:**
```python
AttributeError: 'Subscription' object has no attribute 'plan'
```

**Fix:**
```python
# OLD - Will fail if plan is None
plan_name = subscription.plan.name

# NEW - Safe
plan_name = subscription.plan.name if subscription.plan else 'Dynamic Pricing'
```

### Checking if Subscription Uses Old System

```python
if subscription.plan is not None:
    # This is an old subscription with a plan
    logger.warning(f"Subscription {subscription.id} uses deprecated plan system")
else:
    # This is a new subscription with dynamic pricing
    pass
```

---

## 📚 RELATED DOCUMENTATION

- `/docs/CRITICAL_SUBSCRIPTION_FLOW_ISSUE.md` - Why this change was needed
- `/docs/FRONTEND_BACKEND_SUBSCRIPTION_API_CONTRACT.md` - New API specification
- `/docs/QUICK_REFERENCE_SUBSCRIPTION_FIX.md` - Implementation guide

---

## ⚠️ BREAKING CHANGES

### What Breaks

1. **Frontend Code**
   - Any code that fetches `/api/subscriptions/api/plans/` will get 404
   - Any code that displays plan selection dropdowns won't work
   - Any code that sends `plan_id` in subscription creation

2. **Admin Users**
   - Can no longer see "Subscription Plans" in admin
   - Must use "Subscription Pricing Tiers" instead

3. **API Clients**
   - Plan endpoints no longer exist
   - Must use new pricing calculation endpoints

### What Still Works

1. **Existing Subscriptions**
   - Old subscriptions with plans still function
   - Can view existing plan data
   - No immediate impact on active subscriptions

2. **Database**
   - `subscription_plans` table still exists
   - `plan_id` foreign key still works
   - Data preserved for migration

---

## 🎯 WHY THIS CHANGE

### Security Vulnerability

**Problem:**
```
User has 4 storefronts
  ↓
Selects "Business Plan (2 storefronts)" 
  ↓
Pays GHS 163.50 instead of GHS 218
  ↓
Revenue loss: GHS 54.50/month
```

**Solution:**
```
User has 4 storefronts
  ↓
System auto-detects count
  ↓
Calculates: GHS 218 (non-negotiable)
  ↓
User subscribes or cancels
  ↓
No manipulation possible
```

### Business Logic

- **Old:** User selects plan = User controls pricing ❌
- **New:** System detects storefronts = System controls pricing ✅

---

## 📞 SUPPORT

**Questions?**
- Post in #subscription-redesign Slack channel
- Tag @backend-team for technical issues
- Tag @product-owner for business logic questions

**Issues?**
- Check existing subscriptions still work
- Review error logs for plan-related failures
- Report any breaking changes immediately

---

## 📅 TIMELINE

| Date | Action | Status |
|------|--------|--------|
| Nov 3, 2025 | Deprecate plan system | ✅ DONE |
| Nov 3, 2025 | Remove from API | ✅ DONE |
| Nov 3, 2025 | Remove from admin | ✅ DONE |
| Week 1-2 | Frontend updates | 🔄 IN PROGRESS |
| Week 3 | Deploy new system | ⏳ PENDING |
| Week 4 | Audit subscriptions | ⏳ PENDING |
| TBD | Complete removal | ⏳ FUTURE |

---

**Last Updated:** November 3, 2025  
**Migration:** 0004_deprecate_old_subscription_plans  
**Status:** Deprecated (Model kept for backward compatibility)  

---

**END OF DOCUMENT**
