"""
Permissions for subscription endpoints and subscription-based access control
"""
from rest_framework import permissions
from rest_framework.permissions import BasePermission
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from .utils import SubscriptionChecker


class IsPlatformAdmin(BasePermission):
    """
    Permission check for platform administrators.
    Allows SUPER_ADMIN and ADMIN roles.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check if user has platform_role attribute
        platform_role = getattr(request.user, 'platform_role', None)
        
        # Map platform roles from User model
        # User.PLATFORM_SUPER_ADMIN = 'SUPER_ADMIN'
        # User.PLATFORM_SAAS_ADMIN = 'SAAS_ADMIN'
        return platform_role in ['SUPER_ADMIN', 'SAAS_ADMIN']


class IsSuperAdmin(BasePermission):
    """
    Permission check for super administrators only.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        platform_role = getattr(request.user, 'platform_role', None)
        return platform_role == 'SUPER_ADMIN'


# ============================================================================
# Subscription-Based Permission Classes
# ============================================================================


class RequiresActiveSubscription(permissions.BasePermission):
    """
    Permission class that requires an active subscription for access.
    
    Used for CRITICAL features:
    - Sales processing
    - Payment recording
    - Inventory modifications
    
    This permission checks:
    1. User is authenticated
    2. User has an associated business
    3. Business has an active subscription
    
    Grace period is NOT allowed for these critical operations.
    """
    
    message = "Active subscription required to perform this action."
    
    def has_permission(self, request, view):
        """
        Check if the user's business has an active subscription.
        """
        # Must be authenticated
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Get business from user's active membership
        from accounts.models import BusinessMembership
        
        membership = BusinessMembership.objects.filter(
            user=request.user,
            is_active=True
        ).first()
        
        if not membership:
            self.message = "User must be associated with a business."
            return False
        
        business = membership.business
        
        # Check for active subscription
        try:
            result = SubscriptionChecker.check_subscription_required(
                business=business,
                feature_name="this feature",
                raise_exception=False
            )
            
            # Only allow if subscription is active (not grace period)
            if not result['is_active']:
                if result['in_grace_period']:
                    self.message = (
                        "Active subscription required. Your subscription has expired. "
                        f"Grace period ends on {result['grace_period_end']}. "
                        "Please renew to continue processing transactions."
                    )
                else:
                    self.message = (
                        "Active subscription required. Please subscribe to continue "
                        "processing transactions."
                    )
                return False
            
            return True
            
        except Exception as e:
            self.message = str(e)
            return False
    
    def has_object_permission(self, request, view, obj):
        """
        Object-level permission check.
        For most cases, the global permission is sufficient.
        """
        return self.has_permission(request, view)


class RequiresSubscriptionForReports(permissions.BasePermission):
    """
    Permission class for analytics and reporting features.
    
    Used for HIGH priority features:
    - Sales reports
    - Financial reports
    - Inventory reports
    - Customer analytics
    
    This permission allows:
    - Active subscriptions: Full access
    - Grace period: Read-only access (GET requests only)
    - No subscription: No access
    """
    
    message = "Subscription required to access reports."
    
    def has_permission(self, request, view):
        """
        Check subscription status for report access.
        """
        # Must be authenticated
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Get business from user's active membership
        from accounts.models import BusinessMembership
        
        membership = BusinessMembership.objects.filter(
            user=request.user,
            is_active=True
        ).first()
        
        if not membership:
            self.message = "User must be associated with a business."
            return False
        
        business = membership.business
        
        # Check subscription status
        try:
            result = SubscriptionChecker.check_subscription_required(
                business=business,
                feature_name="reports",
                raise_exception=False
            )
            
            # Active subscription - full access
            if result['is_active']:
                return True
            
            # Grace period - read-only access
            if result['in_grace_period']:
                if request.method in permissions.SAFE_METHODS:
                    # Allow GET, HEAD, OPTIONS during grace period
                    return True
                else:
                    self.message = (
                        f"Subscription expired. Grace period active until "
                        f"{result['grace_period_end']}. Read-only access granted. "
                        "Please renew for full access."
                    )
                    return False
            
            # No subscription
            self.message = "Active subscription required to access reports."
            return False
            
        except Exception as e:
            self.message = str(e)
            return False


class RequiresSubscriptionForExports(permissions.BasePermission):
    """
    Permission class for data export features.
    
    Used for MEDIUM priority features:
    - Sales exports
    - Inventory exports
    - Report exports
    - CSV/Excel downloads
    
    This permission allows:
    - Active subscriptions: Full access
    - Grace period: Limited exports (basic formats only)
    - No subscription: No access
    """
    
    message = "Active subscription required to export data."
    
    def has_permission(self, request, view):
        """
        Check subscription status for export access.
        """
        # Must be authenticated
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Get business from user's active membership
        from accounts.models import BusinessMembership
        
        membership = BusinessMembership.objects.filter(
            user=request.user,
            is_active=True
        ).first()
        
        if not membership:
            self.message = "User must be associated with a business."
            return False
        
        business = membership.business
        
        # Check subscription status
        try:
            result = SubscriptionChecker.check_subscription_required(
                business=business,
                feature_name="data exports",
                raise_exception=False
            )
            
            # Active subscription - full access
            if result['is_active']:
                return True
            
            # Grace period - limited access
            if result['in_grace_period']:
                # Could add logic here to limit export format or size
                # For now, allow basic exports during grace period
                self.message = (
                    f"Subscription expired. Limited export access during grace period "
                    f"(ends {result['grace_period_end']}). Please renew for full access."
                )
                # Allow limited exports
                return True
            
            # No subscription
            self.message = "Active subscription required to export data."
            return False
            
        except Exception as e:
            self.message = str(e)
            return False


class RequiresSubscriptionForAutomation(permissions.BasePermission):
    """
    Permission class for automation features.
    
    Used for MEDIUM priority features:
    - Scheduled exports
    - Automated reports
    - Scheduled tasks
    - Email notifications
    
    This permission requires active subscription (no grace period).
    """
    
    message = "Active subscription required for automation features."
    
    def has_permission(self, request, view):
        """
        Check subscription status for automation access.
        """
        # Must be authenticated
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Get business from user's active membership
        from accounts.models import BusinessMembership
        
        membership = BusinessMembership.objects.filter(
            user=request.user,
            is_active=True
        ).first()
        
        if not membership:
            self.message = "User must be associated with a business."
            return False
        
        business = membership.business
        
        # Check subscription status
        try:
            result = SubscriptionChecker.check_subscription_required(
                business=business,
                feature_name="automation features",
                raise_exception=False
            )
            
            # Only allow if subscription is active (not grace period)
            if not result['is_active']:
                if result['in_grace_period']:
                    self.message = (
                        "Automation features require an active subscription. "
                        f"Your subscription expired. Grace period ends on {result['grace_period_end']}. "
                        "Please renew to continue using automation."
                    )
                else:
                    self.message = "Active subscription required for automation features."
                return False
            
            return True
            
        except Exception as e:
            self.message = str(e)
            return False


class RequiresSubscriptionForInventoryModification(permissions.BasePermission):
    """
    Permission class for inventory modification operations.
    
    Used for HIGH priority features:
    - Stock adjustments
    - Product creation/editing
    - Stock transfers
    - Warehouse operations
    
    This permission allows:
    - Active subscriptions: Full access
    - Grace period: Read-only access
    - No subscription: Read-only access
    """
    
    message = "Active subscription required to modify inventory."
    
    def has_permission(self, request, view):
        """
        Check subscription status for inventory modifications.
        """
        # Must be authenticated
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Must have a business
        business = getattr(request.user, 'business', None)
        if not business:
            self.message = "User must be associated with a business."
            return False
        
        # Allow read-only access without subscription
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Check subscription for write operations
        try:
            result = SubscriptionChecker.check_subscription_required(
                business=business,
                feature_name="inventory modifications",
                raise_exception=False
            )
            
            # Only allow modifications with active subscription
            if not result['is_active']:
                if result['in_grace_period']:
                    self.message = (
                        f"Active subscription required to modify inventory. "
                        f"Grace period ends on {result['grace_period_end']}. "
                        "Read-only access granted. Please renew to continue modifications."
                    )
                else:
                    self.message = (
                        "Active subscription required to modify inventory. "
                        "Read-only access granted."
                    )
                return False
            
            return True
            
        except Exception as e:
            self.message = str(e)
            return False


# ============================================================================
# Convenience Permission Combinations
# ============================================================================


class SalesPermissions(permissions.BasePermission):
    """Combined permissions for sales operations."""
    
    def has_permission(self, request, view):
        """Check both authentication and subscription."""
        return RequiresActiveSubscription().has_permission(request, view)


class ReportsPermissions(permissions.BasePermission):
    """Combined permissions for reports."""
    
    def has_permission(self, request, view):
        """Check both authentication and subscription for reports."""
        return RequiresSubscriptionForReports().has_permission(request, view)
