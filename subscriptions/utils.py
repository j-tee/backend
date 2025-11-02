"""
Subscription Utility Functions

This module provides utility functions for checking subscription status,
validating subscription requirements, and enforcing subscription-based
access control throughout the POS system.
"""

from datetime import datetime, timedelta
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError
from .models import Subscription


class SubscriptionChecker:
    """
    Utility class for subscription validation and enforcement.
    
    This class provides methods to:
    - Check if a business has an active subscription
    - Validate subscription requirements for specific features
    - Enforce storefront limits based on subscription tier
    - Get comprehensive subscription status information
    """
    
    # Grace period configuration (7 days)
    GRACE_PERIOD_DAYS = 7
    
    @staticmethod
    def get_active_subscription(business):
        """
        Get the active subscription for a business.
        
        Args:
            business: The Business model instance
            
        Returns:
            Subscription object if active, None otherwise
            
        Note:
            A subscription is considered active if:
            - status is 'ACTIVE' or 'TRIAL'
            - end_date is in the future (or None for lifetime subscriptions)
        """
        if not business:
            return None
            
        try:
            subscription = Subscription.objects.filter(
                business=business,
                status__in=['ACTIVE', 'TRIAL'],
            ).select_related('plan').first()
            
            if subscription:
                # Check if subscription has expired
                if subscription.end_date and subscription.end_date < timezone.now().date():
                    return None
                    
            return subscription
            
        except Subscription.DoesNotExist:
            return None
    
    @classmethod
    def check_subscription_required(cls, business, feature_name=None, raise_exception=True):
        """
        Check if a business has an active subscription for a specific feature.
        
        Args:
            business: The Business model instance
            feature_name: Optional feature name for specific feature checks
            raise_exception: If True, raise PermissionDenied if no active subscription
            
        Returns:
            dict with subscription status information
            
        Raises:
            PermissionDenied: If raise_exception=True and no active subscription
        """
        subscription = cls.get_active_subscription(business)
        
        # Check if in grace period
        in_grace_period = False
        grace_period_end = None
        
        if not subscription:
            # Check if there's a recently expired subscription
            recent_subscription = Subscription.objects.filter(
                business=business,
                status__in=['EXPIRED', 'PAST_DUE', 'CANCELLED']
            ).order_by('-end_date').first()
            
            if recent_subscription and recent_subscription.end_date:
                grace_period_end = recent_subscription.end_date + timedelta(days=cls.GRACE_PERIOD_DAYS)
                if timezone.now().date() <= grace_period_end:
                    in_grace_period = True
                    subscription = recent_subscription
        
        result = {
            'has_subscription': subscription is not None,
            'is_active': subscription is not None and subscription.status in ['ACTIVE', 'TRIAL'],
            'in_grace_period': in_grace_period,
            'grace_period_end': grace_period_end,
            'subscription': subscription,
            'feature_name': feature_name
        }
        
        if raise_exception and not result['is_active'] and not in_grace_period:
            if feature_name:
                raise PermissionDenied(
                    f"Active subscription required to access {feature_name}. "
                    f"Please renew your subscription to continue."
                )
            else:
                raise PermissionDenied(
                    "Active subscription required. Please renew your subscription to continue."
                )
        
        return result
    
    @classmethod
    def check_storefront_limit(cls, business, raise_exception=True):
        """
        Check if a business can create additional storefronts based on their subscription tier.
        
        Args:
            business: The Business model instance
            raise_exception: If True, raise ValidationError if limit exceeded
            
        Returns:
            dict with storefront limit information
            
        Raises:
            ValidationError: If raise_exception=True and limit exceeded
        """
        subscription = cls.get_active_subscription(business)
        
        if not subscription or not subscription.plan:
            # No subscription - only allow 1 storefront (free tier)
            max_storefronts = 1
        else:
            # Use plan's max_storefronts
            max_storefronts = getattr(subscription.plan, 'max_storefronts', 1)
        
        # Count current storefronts for users in this business
        from inventory.models import StoreFront
        from accounts.models import BusinessMembership
        
        # Get all users who are members of this business
        business_users = BusinessMembership.objects.filter(business=business).values_list('user_id', flat=True)
        
        # Count storefronts owned by business members
        current_count = StoreFront.objects.filter(user_id__in=business_users).count()
        
        result = {
            'max_storefronts': max_storefronts,
            'current_count': current_count,
            'can_add_more': current_count < max_storefronts,
            'remaining': max(0, max_storefronts - current_count)
        }
        
        if raise_exception and not result['can_add_more']:
            if max_storefronts == 1:
                raise ValidationError(
                    "Storefront limit reached. Upgrade your subscription to add more storefronts."
                )
            else:
                raise ValidationError(
                    f"Storefront limit reached ({max_storefronts}). "
                    f"Upgrade your subscription to add more storefronts."
                )
        
        return result
    
    @classmethod
    def get_subscription_status(cls, business):
        """
        Get comprehensive subscription status for a business.
        
        Args:
            business: The Business model instance
            
        Returns:
            dict with complete subscription status information
        """
        subscription = cls.get_active_subscription(business)
        
        status = {
            'business_id': business.id,
            'business_name': business.name,
            'has_active_subscription': False,
            'subscription_status': None,
            'tier_name': None,
            'tier_code': None,
            'start_date': None,
            'end_date': None,
            'days_remaining': None,
            'is_trial': False,
            'in_grace_period': False,
            'grace_period_end': None,
            'max_storefronts': 1,  # Default free tier
            'can_process_sales': False,
            'can_view_reports': False,
            'can_export_data': False,
            'features_available': []
        }
        
        if subscription:
            status['has_active_subscription'] = subscription.status in ['ACTIVE', 'TRIAL']
            status['subscription_status'] = subscription.status
            
            if subscription.plan:
                status['tier_name'] = subscription.plan.name
                status['tier_code'] = subscription.plan.name.upper().replace(' ', '_')
                status['max_storefronts'] = getattr(subscription.plan, 'max_storefronts', 1)
            
            status['start_date'] = subscription.start_date
            status['end_date'] = subscription.end_date
            status['is_trial'] = subscription.is_trial
            
            if subscription.end_date:
                days_remaining = (subscription.end_date - timezone.now().date()).days
                status['days_remaining'] = max(0, days_remaining)
            
            # Determine available features
            if subscription.status in ['ACTIVE', 'TRIAL']:
                status['can_process_sales'] = True
                status['can_view_reports'] = True
                status['can_export_data'] = True
                status['features_available'] = [
                    'sales', 'payments', 'inventory', 'reports', 
                    'exports', 'customer_management'
                ]
        else:
            # Check for grace period
            recent_subscription = Subscription.objects.filter(
                business=business,
                status__in=['EXPIRED', 'PAST_DUE', 'CANCELLED']
            ).order_by('-end_date').first()
            
            if recent_subscription and recent_subscription.end_date:
                grace_period_end = recent_subscription.end_date + timedelta(days=cls.GRACE_PERIOD_DAYS)
                if timezone.now().date() <= grace_period_end:
                    status['in_grace_period'] = True
                    status['grace_period_end'] = grace_period_end
                    status['subscription_status'] = 'grace_period'
                    
                    # Limited features during grace period
                    status['can_view_reports'] = True  # Read-only
                    status['features_available'] = ['view_data', 'reports_readonly']
        
        # Get storefront limit info
        storefront_info = cls.check_storefront_limit(business, raise_exception=False)
        status['storefront_limit'] = storefront_info
        
        return status
    
    @classmethod
    def enforce_active_subscription(cls, business, feature_name=None):
        """
        Enforce active subscription requirement.
        Convenience method that always raises exception if no active subscription.
        
        Args:
            business: The Business model instance
            feature_name: Optional feature name for error message
            
        Raises:
            PermissionDenied: If no active subscription
        """
        cls.check_subscription_required(business, feature_name=feature_name, raise_exception=True)
    
    @classmethod
    def can_access_feature(cls, business, feature_type):
        """
        Check if a business can access a specific feature type.
        
        Args:
            business: The Business model instance
            feature_type: Type of feature ('sales', 'reports', 'exports', 'automation')
            
        Returns:
            bool: True if feature is accessible, False otherwise
        """
        subscription = cls.get_active_subscription(business)
        
        if not subscription:
            # Check grace period for read-only features
            recent_subscription = Subscription.objects.filter(
                business=business,
                status__in=['EXPIRED', 'PAST_DUE', 'CANCELLED']
            ).order_by('-end_date').first()
            
            if recent_subscription and recent_subscription.end_date:
                grace_period_end = recent_subscription.end_date + timedelta(days=cls.GRACE_PERIOD_DAYS)
                if timezone.now().date() <= grace_period_end:
                    # During grace period, only reports are accessible (read-only)
                    return feature_type == 'reports'
            
            return False
        
        # Active subscription - all features available
        return subscription is not None and subscription.status in ['ACTIVE', 'TRIAL']


# Convenience functions for quick checks
def get_business_subscription(business):
    """Get active subscription for a business."""
    return SubscriptionChecker.get_active_subscription(business)


def has_active_subscription(business):
    """Check if business has an active subscription (boolean check)."""
    subscription = SubscriptionChecker.get_active_subscription(business)
    return subscription is not None and subscription.status in ['ACTIVE', 'TRIAL']


def enforce_subscription(business, feature_name=None):
    """Enforce subscription requirement (raises exception if not active)."""
    SubscriptionChecker.enforce_active_subscription(business, feature_name)


def check_storefront_limit(business):
    """Check storefront limit for a business."""
    return SubscriptionChecker.check_storefront_limit(business, raise_exception=False)
