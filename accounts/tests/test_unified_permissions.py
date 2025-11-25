"""
Tests for Unified Permission System

Run with: python manage.py test accounts.tests.test_unified_permissions
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from accounts.permissions import (
    UnifiedPermissionService,
    PermissionDenied,
    check_permission,
    filter_accessible,
)
from accounts.models import Business, BusinessMembership, Permission, Role

User = get_user_model()


class UnifiedPermissionServiceTests(TestCase):
    """Test cases for the UnifiedPermissionService"""
    
    def setUp(self):
        """Set up test data"""
        # Create users
        self.owner_user = User.objects.create(
            email='owner@test.com',
            name='Owner User'
        )
        self.admin_user = User.objects.create(
            email='admin@test.com',
            name='Admin User'
        )
        self.staff_user = User.objects.create(
            email='staff@test.com',
            name='Staff User'
        )
        self.super_admin = User.objects.create(
            email='super@test.com',
            name='Super Admin',
            platform_role='SUPER_ADMIN'
        )
        
        # Create business
        self.business = Business.objects.create(
            name='Test Business',
            email='business@test.com'
        )
        
        # Create memberships
        BusinessMembership.objects.create(
            business=self.business,
            user=self.owner_user,
            role=BusinessMembership.OWNER,
            is_active=True
        )
        BusinessMembership.objects.create(
            business=self.business,
            user=self.admin_user,
            role=BusinessMembership.ADMIN,
            is_active=True
        )
        BusinessMembership.objects.create(
            business=self.business,
            user=self.staff_user,
            role=BusinessMembership.STAFF,
            is_active=True
        )
    
    def test_super_admin_has_all_permissions(self):
        """Super admin should have all permissions"""
        service = UnifiedPermissionService(self.super_admin)
        
        # Should have any permission
        self.assertTrue(service.check('inventory.view_storefront'))
        self.assertTrue(service.check('inventory.delete_storefront'))
        self.assertTrue(service.check('sales.create_sale'))
        self.assertTrue(service.check('reports.view_financial_reports'))
    
    def test_business_member_has_view_access(self):
        """Business members should have basic view access"""
        service = UnifiedPermissionService(self.staff_user)
        
        # Staff can view (through rules or RBAC)
        # Note: Actual permission depends on your rules setup
        # This test assumes basic view access for members
        self.assertTrue(service.check_business_access(self.business))
    
    def test_non_member_has_no_access(self):
        """Non-members should not have business access"""
        non_member = User.objects.create(
            email='outsider@test.com',
            name='Outsider'
        )
        service = UnifiedPermissionService(non_member)
        
        self.assertFalse(service.check_business_access(self.business))
    
    def test_get_user_role_in_business(self):
        """Should correctly identify user's role in business"""
        # Test owner
        service = UnifiedPermissionService(self.owner_user)
        self.assertEqual(
            service.get_user_role_in_business(self.business),
            BusinessMembership.OWNER
        )
        
        # Test admin
        service = UnifiedPermissionService(self.admin_user)
        self.assertEqual(
            service.get_user_role_in_business(self.business),
            BusinessMembership.ADMIN
        )
        
        # Test staff
        service = UnifiedPermissionService(self.staff_user)
        self.assertEqual(
            service.get_user_role_in_business(self.business),
            BusinessMembership.STAFF
        )
        
        # Test non-member
        non_member = User.objects.create(email='other@test.com', name='Other')
        service = UnifiedPermissionService(non_member)
        self.assertIsNone(service.get_user_role_in_business(self.business))
    
    def test_permission_denied_exception(self):
        """Should raise PermissionDenied with raise_exception=True"""
        non_member = User.objects.create(
            email='outsider@test.com',
            name='Outsider'
        )
        service = UnifiedPermissionService(non_member)
        
        with self.assertRaises(PermissionDenied) as cm:
            service.check(
                'inventory.delete_storefront',
                raise_exception=True
            )
        
        self.assertIn('permission', str(cm.exception.message).lower())
    
    def test_permission_caching(self):
        """Should cache permission checks"""
        service = UnifiedPermissionService(self.owner_user)
        
        # First check
        result1 = service.check('inventory.view_storefront')
        
        # Second check should use cache
        result2 = service.check('inventory.view_storefront')
        
        self.assertEqual(result1, result2)
        
        # Cache should have the entry
        self.assertGreater(len(service._cache), 0)
    
    def test_cache_clearing(self):
        """Should clear cache when requested"""
        service = UnifiedPermissionService(self.owner_user)
        
        # Make a check to populate cache
        service.check('inventory.view_storefront')
        self.assertGreater(len(service._cache), 0)
        
        # Clear cache
        service.clear_cache()
        self.assertEqual(len(service._cache), 0)
    
    def test_anonymous_user_has_no_permissions(self):
        """Anonymous users should have no permissions"""
        from django.contrib.auth.models import AnonymousUser
        
        service = UnifiedPermissionService(AnonymousUser())
        
        self.assertFalse(service.check('inventory.view_storefront'))
        self.assertFalse(service.check('sales.create_sale'))


class ConvenienceFunctionTests(TestCase):
    """Test convenience functions"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create(
            email='test@test.com',
            name='Test User',
            platform_role='SUPER_ADMIN'
        )
        self.business = Business.objects.create(
            name='Test Business',
            email='biz@test.com'
        )
    
    def test_check_permission_function(self):
        """Test standalone check_permission function"""
        # Should work like service.check()
        result = check_permission(
            self.user,
            'inventory.view_storefront'
        )
        self.assertTrue(result)
    
    def test_check_permission_with_exception(self):
        """Test check_permission with raise_exception"""
        non_admin = User.objects.create(
            email='regular@test.com',
            name='Regular'
        )
        
        with self.assertRaises(PermissionDenied):
            check_permission(
                non_admin,
                'inventory.delete_storefront',
                raise_exception=True
            )
    
    def test_filter_accessible_returns_queryset(self):
        """Test filter_accessible returns correct queryset type"""
        from django.db.models import QuerySet
        
        result = filter_accessible(
            self.user,
            Business.objects.all(),
            'accounts.view_business'
        )
        
        self.assertIsInstance(result, QuerySet)


class PermissionPriorityTests(TestCase):
    """Test permission priority hierarchy"""
    
    def setUp(self):
        """Set up test data"""
        self.super_admin = User.objects.create(
            email='super@test.com',
            name='Super Admin',
            platform_role='SUPER_ADMIN'
        )
        self.saas_admin = User.objects.create(
            email='saas@test.com',
            name='SaaS Admin',
            platform_role='SAAS_ADMIN'
        )
        self.regular_user = User.objects.create(
            email='user@test.com',
            name='Regular User'
        )
    
    def test_super_admin_highest_priority(self):
        """Super admin should override all other checks"""
        service = UnifiedPermissionService(self.super_admin)
        
        # Even without explicit grants, super admin has access
        self.assertTrue(service.check('any.permission'))
        self.assertTrue(service.check('inventory.delete_storefront'))
        self.assertTrue(service.check('sales.approve_sale'))
    
    def test_saas_admin_view_and_change(self):
        """SaaS admin should have view and change permissions"""
        service = UnifiedPermissionService(self.saas_admin)
        
        # SaaS admin can view and change
        self.assertTrue(service.check('inventory.view_storefront'))
        self.assertTrue(service.check('inventory.change_storefront'))
        
        # But not delete (except through explicit grants)
        # Note: This depends on your implementation
        # Adjust based on actual SAAS_ADMIN permissions
    
    def test_regular_user_needs_explicit_permissions(self):
        """Regular users need explicit role/permission grants"""
        service = UnifiedPermissionService(self.regular_user)
        
        # Without any roles or permissions, should be denied
        self.assertFalse(service.check('inventory.delete_storefront'))


class BusinessScopedPermissionTests(TestCase):
    """Test business-scoped permission checking"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create(
            email='test@test.com',
            name='Test User'
        )
        self.business1 = Business.objects.create(
            name='Business 1',
            email='biz1@test.com'
        )
        self.business2 = Business.objects.create(
            name='Business 2',
            email='biz2@test.com'
        )
        
        # User is member of business1 only
        BusinessMembership.objects.create(
            business=self.business1,
            user=self.user,
            role=BusinessMembership.OWNER,
            is_active=True
        )
    
    def test_user_has_access_to_own_business(self):
        """User should have access to businesses they're member of"""
        service = UnifiedPermissionService(self.user)
        
        self.assertTrue(service.check_business_access(self.business1))
        self.assertEqual(
            service.get_user_role_in_business(self.business1),
            BusinessMembership.OWNER
        )
    
    def test_user_no_access_to_other_business(self):
        """User should not have access to businesses they're not member of"""
        service = UnifiedPermissionService(self.user)
        
        self.assertFalse(service.check_business_access(self.business2))
        self.assertIsNone(service.get_user_role_in_business(self.business2))


class PerformanceTests(TestCase):
    """Test performance optimizations"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create(
            email='test@test.com',
            name='Test User',
            platform_role='SUPER_ADMIN'
        )
        
        # Create multiple businesses
        self.businesses = [
            Business.objects.create(
                name=f'Business {i}',
                email=f'biz{i}@test.com'
            )
            for i in range(10)
        ]
    
    def test_filter_accessible_efficient(self):
        """filter_accessible should use efficient queries"""
        from django.test.utils import override_settings
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        
        with CaptureQueriesContext(connection) as queries:
            result = filter_accessible(
                self.user,
                Business.objects.all(),
                'accounts.view_business'
            )
            # Force query execution
            list(result)
        
        # Should be efficient (not N+1)
        # Exact number depends on implementation
        # but should be small (<10 queries)
        self.assertLess(len(queries), 10)


# Integration test example (requires actual ViewSet)
class DRFIntegrationTestExample(TestCase):
    """
    Example integration test for DRF ViewSets
    
    Note: This requires actual ViewSets with UnifiedObjectPermission
    """
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create(
            email='test@test.com',
            name='Test User'
        )
        self.business = Business.objects.create(
            name='Test Business',
            email='biz@test.com'
        )
        BusinessMembership.objects.create(
            business=self.business,
            user=self.user,
            role=BusinessMembership.OWNER,
            is_active=True
        )
    
    # Example test (requires actual API endpoints)
    # def test_viewset_permission_integration(self):
    #     """Test that ViewSet respects unified permissions"""
    #     from rest_framework.test import APIClient
    #     
    #     client = APIClient()
    #     client.force_authenticate(user=self.user)
    #     
    #     response = client.get('/api/storefronts/')
    #     self.assertEqual(response.status_code, 200)


if __name__ == '__main__':
    import django
    import os
    
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
    django.setup()
    
    from django.test.runner import DiscoverRunner
    
    runner = DiscoverRunner(verbosity=2)
    runner.run_tests(['accounts.tests.test_unified_permissions'])
