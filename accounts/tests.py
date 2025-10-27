from datetime import timedelta
from unittest import skip

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework.authtoken.models import Token
from unittest.mock import patch
from .models import Role, UserProfile, AuditLog, Business, BusinessMembership, BusinessInvitation
from inventory.models import (
    Warehouse,
    StoreFront,
    BusinessWarehouse,
    BusinessStoreFront,
    StoreFrontEmployee,
    WarehouseEmployee,
)
from .signals import ensure_default_roles, promote_platform_owner
from .utils import log_user_action, track_model_changes

User = get_user_model()


class RoleModelTest(TestCase):
    """Test cases for Role model"""
    
    def setUp(self):
        self.role_data = {
            'name': 'Test Role',
            'description': 'A test role for testing'
        }
    
    def test_role_creation(self):
        """Test role creation"""
        role = Role.objects.create(**self.role_data)
        self.assertEqual(role.name, 'Test Role')
        self.assertEqual(role.description, 'A test role for testing')
        self.assertTrue(role.id)
        self.assertTrue(role.created_at)
        self.assertTrue(role.updated_at)
    
    def test_role_string_representation(self):
        """Test role string representation"""
        role = Role.objects.create(**self.role_data)
        self.assertEqual(str(role), 'Test Role')
    
    def test_role_manager_methods(self):
        """Test role manager custom methods"""
        # Create default roles
        Role.objects.get_or_create(name='Admin', defaults={'description': 'Administrator'})
        Role.objects.get_or_create(name='Cashier', defaults={'description': 'Cashier role'})
        Role.objects.get_or_create(name='Manager', defaults={'description': 'Manager role'})
        Role.objects.get_or_create(name='Warehouse Staff', defaults={'description': 'Warehouse role'})
        
        admin_role = Role.objects.get_admin_role()
        self.assertEqual(admin_role.name, 'Admin')
        
        cashier_role = Role.objects.get_cashier_role()
        self.assertEqual(cashier_role.name, 'Cashier')


class PlatformOwnerPromotionTest(TestCase):
    """Verify platform owner promotion logic."""

    def setUp(self):
        ensure_default_roles()

    @override_settings(PLATFORM_OWNER_EMAIL='owner@example.com')
    def test_promote_existing_platform_owner(self):
        user = User.objects.create_user(
            email='owner@example.com',
            password='testpass123',
            name='Platform Owner'
        )

        changed = promote_platform_owner()
        user.refresh_from_db()

        self.assertTrue(changed)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_staff)
        self.assertEqual(user.role.name, 'Admin')

    @override_settings(PLATFORM_OWNER_EMAIL='missing@example.com')
    def test_no_user_no_promotion(self):
        changed = promote_platform_owner()
        self.assertFalse(changed)


class UserModelTest(TestCase):
    """Test cases for User model"""
    
    def setUp(self):
        self.role = Role.objects.create(name='Test Role', description='Test role')
        self.user_data = {
            'name': 'Test User',
            'email': 'test@example.com',
            'role': self.role
        }
    
    def test_user_creation(self):
        """Test user creation"""
        user = User.objects.create_user(
            email=self.user_data['email'],
            password='testpass123',
            name=self.user_data['name'],
            role=self.user_data['role']
        )
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.name, 'Test User')
        self.assertEqual(user.role, self.role)
        self.assertTrue(user.check_password('testpass123'))
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
    
    def test_superuser_creation(self):
        """Test superuser creation"""
        admin_user = User.objects.create_superuser(
            email='admin@example.com',
            password='adminpass123',
            name='Admin User'
        )
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)
        self.assertTrue(admin_user.is_active)
    
    def test_user_role_methods(self):
        """Test user role checking methods"""
        admin_role, _ = Role.objects.get_or_create(name='Admin', defaults={'description': 'Administrator'})
        admin_user = User.objects.create_user(
            email='admin@example.com',
            password='pass123',
            name='Admin User',
            role=admin_role
        )
        
        self.assertTrue(admin_user.is_admin())
        self.assertFalse(admin_user.is_cashier())
        self.assertTrue(admin_user.has_role('Admin'))
    
    def test_user_string_representation(self):
        """Test user string representation"""
        user = User.objects.create_user(
            email=self.user_data['email'],
            password='testpass123',
            name=self.user_data['name']
        )
        expected_str = f"{user.name} ({user.email})"
        self.assertEqual(str(user), expected_str)


class UserProfileModelTest(TestCase):
    """Test cases for UserProfile model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            name='Test User'
        )
    
    def test_user_profile_creation(self):
        """Test user profile creation"""
        profile = UserProfile.objects.create(
            user=self.user,
            phone='+1234567890',
            address='123 Test St, Test City',
            emergency_contact='Jane Doe +1234567891'
        )
        self.assertEqual(profile.user, self.user)
        self.assertEqual(profile.phone, '+1234567890')
        self.assertEqual(profile.address, '123 Test St, Test City')
        
    def test_user_profile_string_representation(self):
        """Test user profile string representation"""
        profile = UserProfile.objects.create(user=self.user)
        expected_str = f"{self.user.name}'s Profile"
        self.assertEqual(str(profile), expected_str)


class AuditLogModelTest(TestCase):
    """Test cases for AuditLog model"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            name='Test User'
        )
    
    def test_audit_log_creation(self):
        """Test audit log creation"""
        audit_log = AuditLog.objects.create(
            user=self.user,
            action='CREATE',
            model_name='TestModel',
            object_id=self.user.id,
            changes={'field': {'old': 'old_value', 'new': 'new_value'}},
            ip_address='127.0.0.1'
        )
        self.assertEqual(audit_log.user, self.user)
        self.assertEqual(audit_log.action, 'CREATE')
        self.assertEqual(audit_log.model_name, 'TestModel')
        self.assertEqual(audit_log.changes['field']['old'], 'old_value')


class UtilsTest(TestCase):
    """Test cases for utility functions"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            name='Test User'
        )
    
    def test_log_user_action(self):
        """Test log_user_action utility function"""
        log_user_action(
            user=self.user,
            action='CREATE',
            model_name='TestModel',
            object_id=self.user.id,
            changes={'test': 'data'}
        )
        
        audit_log = AuditLog.objects.get(user=self.user)
        self.assertEqual(audit_log.action, 'CREATE')
        self.assertEqual(audit_log.model_name, 'TestModel')
        self.assertEqual(audit_log.changes['test'], 'data')
    
    def test_track_model_changes(self):
        """Test track_model_changes utility function"""
        old_user = User.objects.create_user(
            email='old@example.com',
            password='oldpass123',
            name='Old Name'
        )
        
        new_user = User.objects.create_user(
            email='new@example.com',
            password='newpass123',
            name='New Name'
        )
        
        changes = track_model_changes(old_user, new_user)
        
        self.assertIn('name', changes)
        self.assertIn('email', changes)
        self.assertEqual(changes['name']['old'], 'Old Name')
        self.assertEqual(changes['name']['new'], 'New Name')


class AuthenticationAPITest(APITestCase):
    """Test cases for authentication API endpoints"""
    
    def setUp(self):
        self.client = APIClient()
        self.role = Role.objects.create(name='Test Role', description='Test role')
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            name='Test User',
            role=self.role,
            email_verified=True
        )
    
    def test_login_success(self):
        """Test successful login"""
        login_data = {
            'email': 'test@example.com',
            'password': 'testpass123'
        }
        response = self.client.post('/accounts/api/auth/login/', login_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)
        self.assertIn('user', response.data)
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        login_data = {
            'email': 'test@example.com',
            'password': 'wrongpassword'
        }
        response = self.client.post('/accounts/api/auth/login/', login_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_login_inactive_user(self):
        """Test login with inactive user"""
        self.user.is_active = False
        self.user.save()
        
        login_data = {
            'email': 'test@example.com',
            'password': 'testpass123'
        }
        response = self.client.post('/accounts/api/auth/login/', login_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_logout_success(self):
        """Test successful logout"""
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)
        
        response = self.client.post('/accounts/api/auth/logout/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify token is deleted
        self.assertFalse(Token.objects.filter(user=self.user).exists())
    
    def test_change_password_success(self):
        """Test successful password change"""
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)
        
        password_data = {
            'old_password': 'testpass123',
            'new_password': 'newtestpass123'
        }
        response = self.client.post('/accounts/api/auth/change-password/', password_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify password was changed
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newtestpass123'))
        
        # Verify token was deleted (forcing re-login)
        self.assertFalse(Token.objects.filter(user=self.user).exists())
    
    def test_change_password_wrong_old_password(self):
        """Test password change with wrong old password"""
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)
        
        password_data = {
            'old_password': 'wrongoldpassword',
            'new_password': 'newtestpass123'
        }
        response = self.client.post('/accounts/api/auth/change-password/', password_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_employee_includes_business_context(self):
        owner = User.objects.create_user(
            email='owner@example.com',
            password='ownerpass123',
            name='Owner User',
            account_type=User.ACCOUNT_OWNER,
            email_verified=True,
        )

        business = Business.objects.create(
            owner=owner,
            name='Context Biz',
            tin='TIN-CONTEXT-001',
            email='biz@example.com',
            address='123 Market Street',
            phone_numbers=['+233123456789'],
            website='https://context.example.com',
            social_handles={'instagram': '@contextbiz'},
        )

        employee = User.objects.create_user(
            email='employee@example.com',
            password='employeepass123',
            name='Employee User',
            account_type=User.ACCOUNT_EMPLOYEE,
            email_verified=True,
        )

        BusinessMembership.objects.create(
            business=business,
            user=employee,
            role=BusinessMembership.STAFF,
            is_admin=False,
            is_active=True,
        )

        login_data = {
            'email': 'employee@example.com',
            'password': 'employeepass123',
        }
        response = self.client.post('/accounts/api/auth/login/', login_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('employment', response.data)
        employment = response.data['employment']
        self.assertIsNotNone(employment)
        self.assertEqual(employment['role'], BusinessMembership.STAFF)
        self.assertEqual(employment['business']['id'], str(business.id))
        self.assertEqual(employment['business']['name'], business.name)

    def test_login_employee_includes_location_assignments(self):
        owner = User.objects.create_user(
            email='owner@example.com',
            password='ownerpass123',
            name='Owner User',
            account_type=User.ACCOUNT_OWNER,
            email_verified=True,
        )

        business = Business.objects.create(
            owner=owner,
            name='Assignment Biz',
            tin='TIN-ASSIGN-001',
            email='biz@example.com',
            address='123 Market Street',
            phone_numbers=['+233123456789'],
        )

        warehouse = Warehouse.objects.create(
            name='Central Warehouse',
            location='Industrial Zone',
            manager=owner,
        )
        BusinessWarehouse.objects.create(business=business, warehouse=warehouse)

        storefront = StoreFront.objects.create(
            user=owner,
            name='Downtown Store',
            location='Central Avenue',
            manager=owner,
        )
        BusinessStoreFront.objects.create(business=business, storefront=storefront)

        employee = User.objects.create_user(
            email='employee@example.com',
            password='employeepass123',
            name='Employee User',
            account_type=User.ACCOUNT_EMPLOYEE,
            email_verified=True,
        )

        membership = BusinessMembership.objects.create(
            business=business,
            user=employee,
            role=BusinessMembership.STAFF,
            is_admin=False,
            is_active=True,
        )

        StoreFrontEmployee.objects.create(
            business=business,
            storefront=storefront,
            user=employee,
            role=membership.role,
            is_active=True,
        )
        WarehouseEmployee.objects.create(
            business=business,
            warehouse=warehouse,
            user=employee,
            role=membership.role,
            is_active=True,
        )

        login_data = {
            'email': 'employee@example.com',
            'password': 'employeepass123',
        }
        response = self.client.post('/accounts/api/auth/login/', login_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        employment = response.data['employment']
        self.assertEqual(len(employment['storefronts']), 1)
        self.assertEqual(employment['storefronts'][0]['id'], str(storefront.id))
        self.assertEqual(employment['storefronts'][0]['name'], storefront.name)
        self.assertEqual(len(employment['warehouses']), 1)
        self.assertEqual(employment['warehouses'][0]['id'], str(warehouse.id))
        self.assertEqual(employment['warehouses'][0]['name'], warehouse.name)

    @skip("Disabled: Current system enforces one user one business constraint")
    def test_login_employee_prefers_most_recent_membership(self):
        owner = User.objects.create_user(
            email='owner@example.com',
            password='ownerpass123',
            name='Owner User',
            account_type=User.ACCOUNT_OWNER,
            email_verified=True,
        )

        older_business = Business.objects.create(
            owner=owner,
            name='API Biz 07d7a8',
            tin='TIN-OLD-001',
            email='oldbiz@example.com',
            address='Old Address',
            phone_numbers=['+233101010101'],
        )

        newer_business = Business.objects.create(
            owner=owner,
            name='DataLogique System',
            tin='TIN-NEW-002',
            email='newbiz@example.com',
            address='New Address',
            phone_numbers=['+233202020202'],
        )

        employee = User.objects.create_user(
            email='employee2@example.com',
            password='employeePass321',
            name='Employee Two',
            account_type=User.ACCOUNT_EMPLOYEE,
            email_verified=True,
        )

        old_membership = BusinessMembership.objects.create(
            business=older_business,
            user=employee,
            role=BusinessMembership.STAFF,
            is_admin=False,
            is_active=True,
        )

        # Simulate an older membership by adjusting timestamps
        BusinessMembership.objects.filter(id=old_membership.id).update(
            created_at=timezone.now() - timedelta(days=30),
            updated_at=timezone.now() - timedelta(days=30),
        )

        BusinessMembership.objects.create(
            business=newer_business,
            user=employee,
            role=BusinessMembership.STAFF,
            is_admin=False,
            is_active=True,
        )

        login_data = {
            'email': 'employee2@example.com',
            'password': 'employeePass321',
        }
        response = self.client.post('/accounts/api/auth/login/', login_data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        employment = response.data['employment']
        self.assertIsNotNone(employment)
        self.assertEqual(employment['business']['name'], 'DataLogique System')


class RoleAPITest(APITestCase):
    """Test cases for Role API endpoints"""
    
    def setUp(self):
        self.client = APIClient()
        self.admin_role, _ = Role.objects.get_or_create(name='Admin', defaults={'description': 'Administrator'})
        self.admin_user = User.objects.create_user(
            email='admin@example.com',
            password='adminpass123',
            name='Admin User',
            role=self.admin_role
        )
        self.token = Token.objects.create(user=self.admin_user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
    
    def test_list_roles(self):
        """Test listing roles"""
        response = self.client.get('/accounts/api/roles/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data['results']), 1)
        role_names = [role['name'] for role in response.data['results']]
        self.assertIn('Admin', role_names)
    
    def test_create_role(self):
        """Test creating a role"""
        role_data = {
            'name': 'New Role',
            'description': 'A new test role'
        }
        response = self.client.post('/accounts/api/roles/', role_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Role.objects.filter(name='New Role').exists())
    
    def test_retrieve_role(self):
        """Test retrieving a specific role"""
        response = self.client.get(f'/accounts/api/roles/{self.admin_role.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Admin')
    
    def test_update_role(self):
        """Test updating a role"""
        update_data = {
            'name': 'Updated Admin',
            'description': 'Updated description'
        }
        response = self.client.put(f'/accounts/api/roles/{self.admin_role.id}/', update_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.admin_role.refresh_from_db()
        self.assertEqual(self.admin_role.name, 'Updated Admin')
    
    def test_delete_role(self):
        """Test deleting a role"""
        temp_role = Role.objects.create(name='Temp Role', description='Temporary')
        response = self.client.delete(f'/accounts/api/roles/{temp_role.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Role.objects.filter(id=temp_role.id).exists())

    def test_delete_role_in_use_returns_error(self):
        """Deleting a role tied to users should fail with a helpful error."""
        response = self.client.delete(f'/accounts/api/roles/{self.admin_role.id}/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Role.objects.filter(id=self.admin_role.id).exists())


class UserAPITest(APITestCase):
    """Test cases for User API endpoints"""
    
    def setUp(self):
        self.client = APIClient()
        self.admin_role, _ = Role.objects.get_or_create(name='Admin', defaults={'description': 'Administrator'})
        self.cashier_role, _ = Role.objects.get_or_create(name='Cashier', defaults={'description': 'Cashier role'})
        
        self.admin_user = User.objects.create_user(
            email='admin@example.com',
            password='adminpass123',
            name='Admin User',
            role=self.admin_role
        )
        
        self.cashier_user = User.objects.create_user(
            email='cashier@example.com',
            password='cashierpass123',
            name='Cashier User',
            role=self.cashier_role
        )
        
        self.admin_token = Token.objects.create(user=self.admin_user)
        self.cashier_token = Token.objects.create(user=self.cashier_user)
    
    def test_admin_can_list_all_users(self):
        """Test that admin can list all users"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.admin_token.key)
        response = self.client.get('/accounts/api/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_cashier_can_only_see_own_profile(self):
        """Test that non-admin users can only see their own profile"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.cashier_token.key)
        response = self.client.get('/accounts/api/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['email'], 'cashier@example.com')
    
    def test_get_current_user_profile(self):
        """Test getting current user profile"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.cashier_token.key)
        response = self.client.get('/accounts/api/users/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'cashier@example.com')
    
    def test_create_user(self):
        """Test creating a new user"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.admin_token.key)
        user_data = {
            'name': 'New User',
            'email': 'newuser@example.com',
            'password': 'newuserpass123',
            'role': self.cashier_role.id
        }
        response = self.client.post('/accounts/api/users/', user_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email='newuser@example.com').exists())
    
    def test_activate_user(self):
        """Test activating a user"""
        self.cashier_user.is_active = False
        self.cashier_user.save()
        
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.admin_token.key)
        response = self.client.post(f'/accounts/api/users/{self.cashier_user.id}/activate/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.cashier_user.refresh_from_db()
        self.assertTrue(self.cashier_user.is_active)
    
    def test_deactivate_user(self):
        """Test deactivating a user"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.admin_token.key)
        response = self.client.post(f'/accounts/api/users/{self.cashier_user.id}/deactivate/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.cashier_user.refresh_from_db()
        self.assertFalse(self.cashier_user.is_active)


class AuditLogAPITest(APITestCase):
    """Test cases for AuditLog API endpoints"""
    
    def setUp(self):
        self.client = APIClient()
        self.admin_role, _ = Role.objects.get_or_create(name='Admin', defaults={'description': 'Administrator'})
        self.admin_user = User.objects.create_user(
            email='admin@example.com',
            password='adminpass123',
            name='Admin User',
            role=self.admin_role
        )
        self.token = Token.objects.create(user=self.admin_user)
        
        # Create some audit logs
        AuditLog.objects.create(
            user=self.admin_user,
            action='CREATE',
            model_name='User',
            object_id=self.admin_user.id
        )
        AuditLog.objects.create(
            user=self.admin_user,
            action='UPDATE',
            model_name='User',
            object_id=self.admin_user.id
        )
    
    def test_list_audit_logs(self):
        """Test listing audit logs"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        response = self.client.get('/accounts/api/audit-logs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_audit_logs_read_only(self):
        """Test that audit logs are read-only"""
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        
        # Try to create
        response = self.client.post('/accounts/api/audit-logs/', {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        
        # Try to update
        audit_log = AuditLog.objects.first()
        response = self.client.put(f'/accounts/api/audit-logs/{audit_log.id}/', {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        
        # Try to delete
        response = self.client.delete(f'/accounts/api/audit-logs/{audit_log.id}/')
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class TasksTest(TestCase):
    """Test cases for Celery tasks"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            name='Test User'
        )
    
    @patch('accounts.tasks.send_mail')
    def test_send_welcome_email_task(self, mock_send_mail):
        """Test send_welcome_email task"""
        from accounts.tasks import send_welcome_email
        
        result = send_welcome_email(self.user.id)
        
        mock_send_mail.assert_called_once()
        self.assertIn('Welcome email sent', str(result))
    
    def test_cleanup_inactive_users_task(self):
        """Test cleanup_inactive_users task"""
        from accounts.tasks import cleanup_inactive_users
        
        # Create inactive user
        inactive_user = User.objects.create_user(
            email='inactive@example.com',
            password='testpass123',
            name='Inactive User',
            is_active=False
        )
        # Set updated_at to 91 days ago
        from django.utils import timezone
        from datetime import timedelta
        inactive_user.updated_at = timezone.now() - timedelta(days=91)
        inactive_user.save()
        
        result = cleanup_inactive_users()
        
        self.assertIn('Processed', str(result))
    
    def test_generate_user_activity_report_task(self):
        """Test generate_user_activity_report task"""
        from accounts.tasks import generate_user_activity_report
        
        # Create some audit logs
        AuditLog.objects.create(
            user=self.user,
            action='LOGIN',
            model_name='User',
            object_id=self.user.id
        )
        
        result = generate_user_activity_report()
        
        self.assertIsInstance(result, dict)
        self.assertIn('total_logins', result)


class RegistrationWorkflowAPITest(APITestCase):
    """End-to-end tests for the new registration workflow."""

    def setUp(self):
        self.client = APIClient()
        ensure_default_roles()

    def test_owner_registration_and_business_creation(self):
        register_payload = {
            'name': 'Owner User',
            'email': 'owner@example.com',
            'password': 'StrongPass123',
            'account_type': User.ACCOUNT_OWNER,
        }

        response = self.client.post('/accounts/api/auth/register/', register_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('user_id', response.data)

        user = User.objects.get(email='owner@example.com')
        self.assertFalse(user.email_verified)
        self.assertFalse(user.is_active)

        verification = user.verification_tokens.first()
        verify_response = self.client.post('/accounts/api/auth/verify-email/', {'token': verification.token}, format='json')
        self.assertEqual(verify_response.status_code, status.HTTP_200_OK)

        user.refresh_from_db()
        self.assertTrue(user.email_verified)
        self.assertTrue(user.is_active)

        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)

        business_payload = {
            'name': 'Owner Business',
            'tin': 'TIN-OWNER-001',
            'email': 'ownerbiz@example.com',
            'address': '123 Owner St',
            'phone_numbers': ['+10000000000'],
            'social_handles': {'instagram': '@ownerbiz'},
        }

        business_response = self.client.post('/accounts/api/auth/register-business/', business_payload, format='json')
        self.assertEqual(business_response.status_code, status.HTTP_201_CREATED)
        self.assertIn('business', business_response.data)

        business = Business.objects.get(tin='TIN-OWNER-001')
        self.assertEqual(business.owner, user)
        membership = BusinessMembership.objects.get(business=business, user=user)
        self.assertEqual(membership.role, BusinessMembership.OWNER)
        self.assertTrue(membership.is_admin)

    def test_employee_registration_requires_invitation(self):
        payload = {
            'name': 'Employee User',
            'email': 'employee@example.com',
            'password': 'EmployeePass123',
            'account_type': User.ACCOUNT_EMPLOYEE,
        }

        response = self.client.post('/accounts/api/auth/register/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_employee_registration_with_invitation(self):
        owner = User.objects.create_user(
            email='owner2@example.com',
            password='StrongPass123',
            name='Owner Two',
            account_type=User.ACCOUNT_OWNER,
            email_verified=True,
        )

        business = Business.objects.create(
            owner=owner,
            name='Business Two',
            tin='TIN-BIZ-002',
            email='biz2@example.com',
            address='456 Market Ave',
            phone_numbers=['+15550000000'],
        )

        invitation = BusinessInvitation.objects.create(
            business=business,
            email='employee@example.com',
            role=BusinessMembership.STAFF,
            invited_by=owner,
        )
        invitation.initialize_token()
        invitation.save()

        register_payload = {
            'name': 'Employee User',
            'email': 'employee@example.com',
            'password': 'EmployeePass123',
            'account_type': User.ACCOUNT_EMPLOYEE,
        }

        response = self.client.post('/accounts/api/auth/register/', register_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(email='employee@example.com')
        verification = user.verification_tokens.first()
        verify_response = self.client.post('/accounts/api/auth/verify-email/', {'token': verification.token}, format='json')
        self.assertEqual(verify_response.status_code, status.HTTP_200_OK)

        membership = BusinessMembership.objects.get(business=business, user=user)
        self.assertEqual(membership.role, BusinessMembership.STAFF)
        self.assertTrue(membership.is_active)

        # Employees cannot register businesses
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)
        business_payload = {
            'name': 'Should Fail',
            'tin': 'TIN-FAIL-001',
            'email': 'fail@example.com',
            'address': 'Fail Street',
            'phone_numbers': ['+19999999999'],
        }
        deny_response = self.client.post('/accounts/api/auth/register-business/', business_payload, format='json')
        self.assertEqual(deny_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_verify_email_via_get_redirect(self):
        payload = {
            'name': 'Owner User',
            'email': 'owner-get@example.com',
            'password': 'StrongPass123',
            'account_type': User.ACCOUNT_OWNER,
        }

        response = self.client.post('/accounts/api/auth/register/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = User.objects.get(email='owner-get@example.com')
        token = user.verification_tokens.first().token

        redirect_response = self.client.get(f'/accounts/api/auth/verify-email/?token={token}', follow=False)
        self.assertEqual(redirect_response.status_code, status.HTTP_302_FOUND)
        self.assertIn('status=success', redirect_response['Location'])

        user.refresh_from_db()
        self.assertTrue(user.email_verified)
        self.assertTrue(user.is_active)
