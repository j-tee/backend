# Subscription Enforcement Analysis - Critical Business Processes

**Date**: November 2, 2025  
**Purpose**: Identify and document all critical business operations that require valid subscription  
**Impact**: Business continuity, revenue protection, compliance

---

## Executive Summary

This document analyzes the POS system to identify critical business processes that **MUST** require an active, valid subscription. The goal is to ensure businesses cannot conduct revenue-generating operations or access premium features without maintaining their subscription.

### Key Principles

1. **No Revenue Without Subscription**: Businesses cannot process sales or accept payments without active subscription
2. **No Reports Without Subscription**: Analytics and reporting features are premium, subscription-only features
3. **Read-Only Access**: Expired subscriptions allow view-only access to historical data, no new transactions
4. **Grace Period**: Consider implementing a grace period (3-7 days) for payment processing delays
5. **Graduated Access**: Different subscription tiers may have different feature access

---

## Critical Business Processes Requiring Active Subscription

### Category 1: Revenue-Generating Operations (HIGHEST PRIORITY)

These operations directly generate business revenue and **MUST** be blocked without active subscription:

#### 1.1 Sales Processing ✅ CRITICAL

**Affected Endpoints**:
```
POST   /sales/api/sales/                          # Create new sale
POST   /sales/api/sales/{id}/add-item/           # Add items to sale
POST   /sales/api/sales/{id}/complete/           # Complete sale (checkout)
POST   /sales/api/sales/{id}/record_payment/     # Record payment
POST   /sales/api/sales/{id}/ar-payment/         # Record AR payment
```

**Why Critical**:
- Direct revenue generation
- Inventory commitments
- Financial transactions
- Customer obligations

**Recommendation**: **BLOCK IMMEDIATELY** when subscription expires or becomes invalid.

**Impact if Not Enforced**:
- Businesses operate indefinitely without paying
- Revenue loss for SaaS platform
- Unfair to paying customers

---

#### 1.2 Payment Recording ✅ CRITICAL

**Affected Endpoints**:
```
POST   /sales/api/payments/                       # Create payment record
POST   /sales/api/sales/{id}/record_payment/     # Record payment against sale
POST   /sales/api/sales/{id}/ar-payment/         # Record AR payment
```

**Why Critical**:
- Money collection
- Accounts receivable management
- Cash flow tracking

**Recommendation**: **BLOCK IMMEDIATELY** - Cannot accept payments without subscription.

---

#### 1.3 Credit Sales & AR Management ✅ CRITICAL

**Affected Endpoints**:
```
POST   /sales/api/sales/{id}/complete/           # Complete credit sale
POST   /sales/api/sales/{id}/ar-payment/         # AR payment recording
GET    /sales/api/customers/                      # Customer credit management
POST   /sales/api/customers/                      # Create credit customers
```

**Why Critical**:
- Extends credit to customers
- Creates financial obligations
- Affects business cash flow

**Recommendation**: **BLOCK IMMEDIATELY** - No new credit sales without subscription.

---

### Category 2: Inventory Management Operations (HIGH PRIORITY)

These operations manage inventory, which directly impacts business operations:

#### 2.1 Stock Adjustments ✅ HIGH PRIORITY

**Affected Endpoints**:
```
POST   /inventory/api/stock-adjustments/         # Create stock adjustment
POST   /inventory/api/stock-products/{id}/adjust/ # Adjust stock levels
POST   /inventory/api/stock-products/             # Add new stock
PUT    /inventory/api/stock-products/{id}/        # Update stock
```

**Why Critical**:
- Inventory value changes
- Stock level management
- COGS calculations
- Financial reporting accuracy

**Recommendation**: **BLOCK** - Allow view-only access to existing stock during grace period.

---

#### 2.2 Product Management ✅ HIGH PRIORITY

**Affected Endpoints**:
```
POST   /inventory/api/products/                   # Create products
PUT    /inventory/api/products/{id}/              # Update products
DELETE /inventory/api/products/{id}/              # Delete products
POST   /inventory/api/products/bulk-create/       # Bulk product creation
```

**Why Critical**:
- Catalog management
- Sales dependencies
- Pricing changes

**Recommendation**: **BLOCK** - Read-only catalog during grace period.

---

#### 2.3 Stock Transfers ✅ HIGH PRIORITY

**Affected Endpoints**:
```
POST   /inventory/api/transfers/                  # Create transfer
POST   /inventory/api/transfers/{id}/approve/     # Approve transfer
POST   /inventory/api/transfers/{id}/complete/    # Complete transfer
POST   /inventory/api/transfer-requests/          # Request transfer
```

**Why Critical**:
- Multi-location inventory management
- Stock movement tracking
- Inventory accuracy

**Recommendation**: **BLOCK** - No new transfers without subscription.

---

### Category 3: Analytics & Reporting (HIGH PRIORITY)

Premium features that provide business intelligence:

#### 3.1 Financial Reports ✅ HIGH PRIORITY

**Affected Endpoints**:
```
GET    /reports/api/financial/revenue-profit/     # Revenue & profit analysis
GET    /reports/api/financial/ar-aging/           # AR aging report
GET    /reports/api/financial/collection-rates/   # Collection rates
GET    /reports/api/financial/cash-flow/          # Cash flow report
```

**Why Critical**:
- Business intelligence
- Financial planning
- Decision-making tools
- Premium SaaS feature

**Recommendation**: **BLOCK** - Premium analytics require active subscription.

**Exception**: Allow access to last 30 days during grace period for operational continuity.

---

#### 3.2 Sales Reports ✅ HIGH PRIORITY

**Affected Endpoints**:
```
GET    /reports/api/sales/summary/                # Sales summary
GET    /reports/api/sales/product-performance/    # Product performance
GET    /reports/api/sales/customer-analytics/     # Customer analytics
GET    /reports/api/sales/revenue-trends/         # Revenue trends
GET    /sales/api/sales/export/                   # Export sales data
```

**Why Critical**:
- Sales analytics
- Performance tracking
- Business insights

**Recommendation**: **BLOCK** - Premium feature, subscription required.

---

#### 3.3 Inventory Reports ✅ HIGH PRIORITY

**Affected Endpoints**:
```
GET    /reports/api/inventory/stock-levels/       # Stock levels summary
GET    /reports/api/inventory/low-stock-alerts/   # Low stock alerts
GET    /reports/api/inventory/movement-history/   # Stock movements
GET    /reports/api/inventory/warehouse-analytics/ # Warehouse analytics
```

**Why Critical**:
- Inventory intelligence
- Reorder planning
- Warehouse optimization

**Recommendation**: **BLOCK** - Premium analytics require subscription.

---

#### 3.4 Customer Reports ✅ HIGH PRIORITY

**Affected Endpoints**:
```
GET    /reports/api/customer/lifetime-value/      # Customer LTV
GET    /reports/api/customer/segmentation/        # Customer segments
GET    /reports/api/customer/purchase-patterns/   # Purchase patterns
GET    /reports/api/customer/retention-metrics/   # Retention metrics
GET    /reports/api/customer/credit-utilization/  # Credit utilization
```

**Why Critical**:
- Customer intelligence
- Marketing insights
- Relationship management

**Recommendation**: **BLOCK** - Premium CRM features require subscription.

---

### Category 4: Multi-Storefront Operations (MEDIUM-HIGH PRIORITY)

Operations that depend on subscription tier (storefront count):

#### 4.1 Storefront Management ✅ TIER-DEPENDENT

**Affected Endpoints**:
```
POST   /inventory/api/storefronts/                # Create storefront
PUT    /inventory/api/storefronts/{id}/           # Update storefront
GET    /inventory/api/storefronts/                # List storefronts
```

**Why Critical**:
- Subscription based on storefront count
- Multi-location pricing
- Tier enforcement

**Recommendation**: **ENFORCE TIER LIMITS** - Block creation if exceeds subscription tier.

**Logic**:
```python
subscription = business.active_subscription
if subscription:
    max_storefronts = subscription.storefront_count
    current_storefronts = business.storefronts.filter(is_active=True).count()
    
    if current_storefronts >= max_storefronts:
        raise PermissionDenied(
            f"Subscription tier allows {max_storefronts} storefronts. "
            f"Upgrade subscription to add more."
        )
```

---

#### 4.2 Warehouse Management ✅ TIER-DEPENDENT

**Affected Endpoints**:
```
POST   /inventory/api/warehouses/                 # Create warehouse
PUT    /inventory/api/warehouses/{id}/            # Update warehouse
```

**Why Critical**:
- May be tier-limited
- Multi-location operations
- Inventory distribution

**Recommendation**: **ENFORCE TIER LIMITS** if warehouse count is part of pricing.

---

### Category 5: Export & Automation (MEDIUM PRIORITY)

Data export and automation features:

#### 5.1 Data Exports ✅ PREMIUM FEATURE

**Affected Endpoints**:
```
POST   /reports/api/exports/sales/                # Export sales
POST   /reports/api/exports/inventory/            # Export inventory
POST   /reports/api/exports/customers/            # Export customers
POST   /reports/api/exports/audit/                # Export audit logs
GET    /sales/api/sales/export/                   # Sales CSV export
```

**Why Critical**:
- Data portability
- Backup functionality
- Premium feature

**Recommendation**: **BLOCK** or **LIMIT** - Allow limited exports during grace period.

**Suggested Limits**:
- Free tier: No exports
- Expired subscription: Last 30 days only
- Active subscription: Unlimited

---

#### 5.2 Export Automation ✅ PREMIUM FEATURE

**Affected Endpoints**:
```
POST   /reports/api/automation/schedules/         # Schedule exports
GET    /reports/api/automation/schedules/         # List schedules
PUT    /reports/api/automation/schedules/{id}/    # Update schedule
```

**Why Critical**:
- Advanced automation
- Premium SaaS feature
- Resource-intensive

**Recommendation**: **BLOCK** - Premium feature requires active subscription.

---

### Category 6: Customer & Credit Management (MEDIUM PRIORITY)

#### 6.1 Customer Creation ✅ CONDITIONAL

**Affected Endpoints**:
```
POST   /sales/api/customers/                      # Create customer
PUT    /sales/api/customers/{id}/                 # Update customer
```

**Why Critical**:
- Required for sales
- Credit management
- Customer relationship

**Recommendation**: **ALLOW LIMITED** - Allow viewing during grace period, block new customers.

---

#### 6.2 Credit Limit Management ✅ HIGH PRIORITY

**Affected Endpoints**:
```
PUT    /sales/api/customers/{id}/                 # Update credit limit
POST   /sales/api/customers/{id}/adjust-credit/   # Adjust credit
```

**Why Critical**:
- Financial risk management
- Credit exposure
- Business liability

**Recommendation**: **BLOCK** - No credit extensions without subscription.

---

### Category 7: Business Configuration (LOW PRIORITY)

Basic settings that may be allowed during grace period:

#### 7.1 Business Settings ✅ ALLOW WITH LIMITS

**Affected Endpoints**:
```
GET    /accounts/api/business/                    # View business
PUT    /accounts/api/business/                    # Update business
GET    /settings/api/business-settings/           # View settings
```

**Why Not Critical**:
- Basic information
- Allows payment update
- Customer service

**Recommendation**: **ALLOW READONLY** - Allow viewing during grace period to update payment.

---

#### 7.2 User Management ✅ CONDITIONAL

**Affected Endpoints**:
```
GET    /accounts/api/users/                       # List users
POST   /accounts/api/users/                       # Add users
DELETE /accounts/api/users/{id}/                  # Remove users
```

**Recommendation**: **BLOCK NEW USERS** - Can't add users without subscription, but allow management of existing users.

---

## Implementation Strategy

### Phase 1: Create Subscription Checker Utility

**File**: `subscriptions/utils.py`

```python
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from subscriptions.models import Subscription


class SubscriptionChecker:
    """Utility class to check subscription status and enforce access rules."""
    
    @staticmethod
    def get_active_subscription(business):
        """Get active subscription for business."""
        return Subscription.objects.filter(
            user=business.owner,
            status='active',
            end_date__gte=timezone.now().date()
        ).first()
    
    @staticmethod
    def check_subscription_required(business, feature='basic', raise_exception=True):
        """
        Check if business has valid subscription for feature.
        
        Args:
            business: Business object
            feature: Feature level required ('basic', 'analytics', 'exports', 'automation')
            raise_exception: Whether to raise exception or return boolean
            
        Returns:
            bool: True if has access, False otherwise
            
        Raises:
            PermissionDenied: If subscription invalid and raise_exception=True
        """
        subscription = SubscriptionChecker.get_active_subscription(business)
        
        if not subscription:
            if raise_exception:
                raise PermissionDenied(
                    "Active subscription required. Please renew your subscription to continue."
                )
            return False
        
        # Check if subscription is in grace period
        if subscription.status == 'grace_period':
            # Allow limited access
            if feature in ['analytics', 'exports', 'automation']:
                if raise_exception:
                    raise PermissionDenied(
                        "This premium feature requires an active subscription. "
                        "Your subscription is in grace period."
                    )
                return False
        
        return True
    
    @staticmethod
    def check_storefront_limit(business):
        """Check if business can add more storefronts."""
        subscription = SubscriptionChecker.get_active_subscription(business)
        
        if not subscription:
            raise PermissionDenied("Active subscription required to manage storefronts.")
        
        max_storefronts = subscription.storefront_count
        current_count = business.storefronts.filter(is_active=True).count()
        
        if current_count >= max_storefronts:
            raise PermissionDenied(
                f"Your subscription allows {max_storefronts} storefronts. "
                f"You currently have {current_count}. "
                f"Please upgrade your subscription to add more storefronts."
            )
    
    @staticmethod
    def get_subscription_status(business):
        """Get detailed subscription status."""
        subscription = SubscriptionChecker.get_active_subscription(business)
        
        if not subscription:
            return {
                'status': 'expired',
                'message': 'No active subscription found',
                'days_remaining': 0,
                'storefront_limit': 0,
                'features_available': []
            }
        
        days_remaining = (subscription.end_date - timezone.now().date()).days
        
        return {
            'status': subscription.status,
            'message': 'Subscription active',
            'days_remaining': days_remaining,
            'storefront_limit': subscription.storefront_count,
            'features_available': [
                'sales',
                'inventory',
                'reports' if subscription.status == 'active' else 'reports_limited',
                'exports' if subscription.status == 'active' else None,
            ]
        }
```

---

### Phase 2: Create Permission Classes

**File**: `subscriptions/permissions.py`

```python
from rest_framework.permissions import BasePermission
from .utils import SubscriptionChecker


class RequiresActiveSubscription(BasePermission):
    """
    Permission class that requires active subscription.
    Use for revenue-generating operations.
    """
    message = "Active subscription required to perform this action."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Get user's business
        business = getattr(request.user, 'business', None)
        if not business:
            return False
        
        return SubscriptionChecker.check_subscription_required(
            business, 
            feature='basic',
            raise_exception=True
        )


class RequiresSubscriptionForReports(BasePermission):
    """
    Permission class for analytics and reports.
    Premium feature requiring active subscription.
    """
    message = "Active subscription required to access reports and analytics."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        business = getattr(request.user, 'business', None)
        if not business:
            return False
        
        return SubscriptionChecker.check_subscription_required(
            business,
            feature='analytics',
            raise_exception=True
        )


class RequiresSubscriptionForExports(BasePermission):
    """
    Permission class for data exports.
    Premium feature requiring active subscription.
    """
    message = "Active subscription required to export data."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        business = getattr(request.user, 'business', None)
        if not business:
            return False
        
        return SubscriptionChecker.check_subscription_required(
            business,
            feature='exports',
            raise_exception=True
        )


class RequiresSubscriptionForAutomation(BasePermission):
    """
    Permission class for automation features.
    Premium feature requiring active subscription.
    """
    message = "Active subscription required to use automation features."
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        business = getattr(request.user, 'business', None)
        if not business:
            return False
        
        return SubscriptionChecker.check_subscription_required(
            business,
            feature='automation',
            raise_exception=True
        )
```

---

### Phase 3: Apply Permissions to ViewSets

#### Sales ViewSet Updates

**File**: `sales/views.py`

```python
from subscriptions.permissions import RequiresActiveSubscription

class SaleViewSet(viewsets.ModelViewSet):
    """ViewSet for Sale CRUD operations with cart functionality"""
    
    # Add subscription permission
    permission_classes = [IsAuthenticated, RequiresActiveSubscription]
    
    # ... existing code ...
    
    def create(self, request, *args, **kwargs):
        """Block sale creation without subscription."""
        # Permission already enforced by permission_classes
        return super().create(request, *args, **kwargs)
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete sale - requires active subscription."""
        # Permission already enforced
        sale = self.get_object()
        # ... existing code ...
```

#### Reports ViewSet Updates

**File**: `reports/views/financial_reports.py`

```python
from subscriptions.permissions import RequiresSubscriptionForReports

class RevenueProfitReportView(BaseReportView):
    """Revenue & Profit Analysis Report"""
    
    permission_classes = [IsAuthenticated, RequiresSubscriptionForReports]
    
    # ... existing code ...
```

#### Inventory ViewSet Updates

**File**: `inventory/views.py`

```python
from subscriptions.permissions import RequiresActiveSubscription
from subscriptions.utils import SubscriptionChecker

class ProductViewSet(viewsets.ModelViewSet):
    """ViewSet for Product CRUD operations"""
    
    def get_permissions(self):
        """Apply subscription check for create/update/delete."""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAuthenticated(), RequiresActiveSubscription()]
        return [IsAuthenticated()]


class StoreFrontViewSet(viewsets.ModelViewSet):
    """ViewSet for StoreFront CRUD operations"""
    
    def create(self, request, *args, **kwargs):
        """Check storefront limit before creation."""
        business = request.user.business
        SubscriptionChecker.check_storefront_limit(business)
        return super().create(request, *args, **kwargs)
```

---

## Subscription Status Response

Add subscription status to all API responses:

**File**: `app/middleware.py`

```python
from subscriptions.utils import SubscriptionChecker


class SubscriptionStatusMiddleware:
    """Middleware to add subscription status to response headers."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        if request.user.is_authenticated:
            business = getattr(request.user, 'business', None)
            if business:
                status = SubscriptionChecker.get_subscription_status(business)
                response['X-Subscription-Status'] = status['status']
                response['X-Subscription-Days-Remaining'] = str(status['days_remaining'])
        
        return response
```

---

## Frontend Integration

The frontend should check subscription status and show appropriate messages:

```javascript
// Check subscription status before critical operations
async function checkSubscription() {
    const response = await fetch('/api/subscriptions/status/');
    const status = await response.json();
    
    if (status.status !== 'active') {
        showSubscriptionWarning(status);
        return false;
    }
    
    return true;
}

// Before creating sale
async function createSale() {
    if (!await checkSubscription()) {
        return;
    }
    
    // Proceed with sale creation
}
```

---

## Testing Checklist

- [ ] Test sale creation with expired subscription (should fail)
- [ ] Test sale completion with expired subscription (should fail)
- [ ] Test payment recording with expired subscription (should fail)
- [ ] Test report access with expired subscription (should fail)
- [ ] Test storefront creation beyond tier limit (should fail)
- [ ] Test read-only access during grace period (should succeed)
- [ ] Test subscription renewal flow
- [ ] Test downgrade scenarios

---

## Recommended Grace Period Policy

```python
GRACE_PERIOD_DAYS = 7  # 7 days grace period after expiration

# During grace period:
# ✅ Allow: View historical data
# ✅ Allow: Update business settings (to fix payment)
# ✅ Allow: Export last 30 days data
# ❌ Block: New sales
# ❌ Block: New payments
# ❌ Block: Stock adjustments
# ❌ Block: New reports
# ❌ Block: New customers
```

---

## Priority Implementation Order

1. **Phase 1 (Immediate)**: Block sales processing and payment recording
2. **Phase 2 (Week 1)**: Block inventory modifications
3. **Phase 3 (Week 2)**: Block reports and analytics
4. **Phase 4 (Week 3)**: Enforce storefront tier limits
5. **Phase 5 (Week 4)**: Block exports and automation

---

## Summary of Critical Blocks

| Operation | Priority | Action | Grace Period |
|-----------|----------|--------|--------------|
| Sales Creation | CRITICAL | BLOCK | NO |
| Payment Recording | CRITICAL | BLOCK | NO |
| Credit Sales | CRITICAL | BLOCK | NO |
| Stock Adjustments | HIGH | BLOCK | 3 days |
| Product Changes | HIGH | BLOCK | 7 days |
| Financial Reports | HIGH | BLOCK | View only |
| Sales Reports | HIGH | BLOCK | View only |
| Inventory Reports | HIGH | BLOCK | View only |
| Customer Reports | HIGH | BLOCK | View only |
| Storefront Creation | MEDIUM | ENFORCE LIMIT | N/A |
| Data Exports | MEDIUM | BLOCK | Last 30 days |
| Automation | LOW | BLOCK | NO |

---

## Conclusion

Implementing subscription enforcement is **CRITICAL** for:

1. **Revenue Protection**: Prevent businesses from operating without payment
2. **Fair Usage**: Ensure paying customers get value for their subscription
3. **Tier Enforcement**: Maintain pricing model integrity
4. **Business Sustainability**: Ensure SaaS platform viability

**Next Steps**:
1. Implement SubscriptionChecker utility
2. Create permission classes
3. Apply to critical endpoints (sales, reports)
4. Test thoroughly
5. Deploy with monitoring
6. Communicate changes to customers

---

**Document Version**: 1.0  
**Last Updated**: November 2, 2025  
**Status**: Ready for Implementation  
