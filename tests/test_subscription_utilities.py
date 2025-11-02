"""
Test Subscription Utilities

This script tests the subscription enforcement utilities:
- SubscriptionChecker class
- Permission classes
- Subscription status endpoint
"""

import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from django.contrib.auth import get_user_model
from subscriptions.models import Subscription, SubscriptionPricingTier
from subscriptions.utils import SubscriptionChecker, has_active_subscription, check_storefront_limit
from inventory.models import StoreFront
from accounts.models import Business
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


def print_header(message):
    """Print a formatted header."""
    print(f"\n{'='*80}")
    print(f"{message}")
    print(f"{'='*80}\n")


def print_success(message):
    """Print a success message."""
    print(f"✓ {message}")


def print_error(message):
    """Print an error message."""
    print(f"✗ {message}")


def print_info(message):
    """Print an info message."""
    print(f"ℹ {message}")


def test_subscription_checker():
    """Test the SubscriptionChecker utility class."""
    print_header("Testing SubscriptionChecker Utility")
    
    # Get or create a test business
    business = Business.objects.first()
    if not business:
        print_error("No business found in database. Please create a business first.")
        return
    
    print_info(f"Testing with business: {business.name}")
    
    # Test 1: Get active subscription
    print("\n1. Testing get_active_subscription()...")
    subscription = SubscriptionChecker.get_active_subscription(business)
    if subscription:
        print_success(f"Found active subscription: {subscription.pricing_tier.tier_name if subscription.pricing_tier else 'No tier'}")
        print_info(f"   Status: {subscription.status}")
        print_info(f"   Start: {subscription.start_date}")
        print_info(f"   End: {subscription.end_date}")
    else:
        print_error("No active subscription found")
    
    # Test 2: Check subscription required
    print("\n2. Testing check_subscription_required()...")
    try:
        result = SubscriptionChecker.check_subscription_required(
            business=business,
            feature_name="sales processing",
            raise_exception=False
        )
        print_success("Subscription check completed:")
        print_info(f"   Has subscription: {result['has_subscription']}")
        print_info(f"   Is active: {result['is_active']}")
        print_info(f"   In grace period: {result['in_grace_period']}")
        if result['grace_period_end']:
            print_info(f"   Grace period ends: {result['grace_period_end']}")
    except Exception as e:
        print_error(f"Error checking subscription: {e}")
    
    # Test 3: Check storefront limit
    print("\n3. Testing check_storefront_limit()...")
    try:
        result = SubscriptionChecker.check_storefront_limit(
            business=business,
            raise_exception=False
        )
        print_success("Storefront limit check completed:")
        print_info(f"   Max storefronts: {result['max_storefronts']}")
        print_info(f"   Current count: {result['current_count']}")
        print_info(f"   Can add more: {result['can_add_more']}")
        print_info(f"   Remaining: {result['remaining']}")
    except Exception as e:
        print_error(f"Error checking storefront limit: {e}")
    
    # Test 4: Get comprehensive subscription status
    print("\n4. Testing get_subscription_status()...")
    try:
        status_info = SubscriptionChecker.get_subscription_status(business)
        print_success("Subscription status retrieved:")
        print_info(f"   Business: {status_info['business_name']}")
        print_info(f"   Has active subscription: {status_info['has_active_subscription']}")
        print_info(f"   Status: {status_info['subscription_status']}")
        if status_info['tier_name']:
            print_info(f"   Tier: {status_info['tier_name']} ({status_info['tier_code']})")
        print_info(f"   Max storefronts: {status_info['max_storefronts']}")
        print_info(f"   Can process sales: {status_info['can_process_sales']}")
        print_info(f"   Can view reports: {status_info['can_view_reports']}")
        print_info(f"   Can export data: {status_info['can_export_data']}")
        print_info(f"   Features available: {', '.join(status_info['features_available'])}")
    except Exception as e:
        print_error(f"Error getting subscription status: {e}")
    
    # Test 5: Convenience functions
    print("\n5. Testing convenience functions...")
    try:
        has_sub = has_active_subscription(business)
        print_success(f"has_active_subscription(): {has_sub}")
        
        storefront_info = check_storefront_limit(business)
        print_success(f"check_storefront_limit(): {storefront_info['can_add_more']}")
    except Exception as e:
        print_error(f"Error with convenience functions: {e}")


def test_grace_period_logic():
    """Test grace period functionality."""
    print_header("Testing Grace Period Logic")
    
    # Get a business
    business = Business.objects.first()
    if not business:
        print_error("No business found in database.")
        return
    
    print_info(f"Testing with business: {business.name}")
    
    # Create an expired subscription
    print("\n1. Creating expired subscription...")
    expired_date = timezone.now().date() - timedelta(days=3)
    
    # Get or create a subscription plan (use SubscriptionPlan, not SubscriptionPricingTier)
    from subscriptions.models import SubscriptionPlan
    plan = SubscriptionPlan.objects.filter(is_active=True).first()
    if not plan:
        print_error("No active subscription plan found. Create a subscription plan first.")
        return
    
    # Check if subscription exists
    subscription = Subscription.objects.filter(business=business).first()
    if subscription:
        # Update existing subscription to expired
        subscription.status = 'expired'
        subscription.end_date = expired_date
        subscription.save()
        print_success(f"Updated subscription to expired (end date: {expired_date})")
    else:
        print_error("No subscription found to test with")
        return
    
    # Test grace period detection
    print("\n2. Testing grace period detection...")
    result = SubscriptionChecker.check_subscription_required(
        business=business,
        raise_exception=False
    )
    
    if result['in_grace_period']:
        print_success("Grace period detected!")
        print_info(f"   Grace period ends: {result['grace_period_end']}")
        print_info(f"   Days remaining in grace: {(result['grace_period_end'] - timezone.now().date()).days}")
    else:
        print_error("Grace period NOT detected (might be outside 7-day window)")
    
    # Test feature access during grace period
    print("\n3. Testing feature access during grace period...")
    can_access_reports = SubscriptionChecker.can_access_feature(business, 'reports')
    can_access_sales = SubscriptionChecker.can_access_feature(business, 'sales')
    
    print_info(f"   Can access reports (should be True): {can_access_reports}")
    print_info(f"   Can access sales (should be False): {can_access_sales}")
    
    if can_access_reports and not can_access_sales:
        print_success("Grace period feature restrictions working correctly!")
    else:
        print_error("Grace period feature restrictions not working as expected")


def test_subscription_import():
    """Test that permissions can import utilities without circular dependencies."""
    print_header("Testing Imports")
    
    print("\n1. Testing utility imports...")
    try:
        from subscriptions.utils import SubscriptionChecker
        print_success("SubscriptionChecker imported successfully")
    except Exception as e:
        print_error(f"Failed to import SubscriptionChecker: {e}")
    
    print("\n2. Testing permission imports...")
    try:
        from subscriptions.permissions import (
            RequiresActiveSubscription,
            RequiresSubscriptionForReports,
            RequiresSubscriptionForExports,
            RequiresSubscriptionForAutomation,
            RequiresSubscriptionForInventoryModification
        )
        print_success("All permission classes imported successfully")
    except Exception as e:
        print_error(f"Failed to import permissions: {e}")
    
    print("\n3. Testing middleware imports...")
    try:
        from subscriptions.middleware import SubscriptionStatusMiddleware
        print_success("Middleware imported successfully")
    except Exception as e:
        print_error(f"Failed to import middleware: {e}")


def main():
    """Run all tests."""
    print_header("Subscription Utilities Test Suite")
    
    try:
        # Test imports first
        test_subscription_import()
        
        # Test subscription checker
        test_subscription_checker()
        
        # Test grace period
        test_grace_period_logic()
        
        print_header("All Tests Completed")
        
    except Exception as e:
        print_error(f"Test suite failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
