from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from rest_framework.authtoken.models import Token
from unittest.mock import patch
from .models import Role, UserProfile, AuditLog, Business, BusinessMembership
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
        Role.objects.create(name='Admin', description='Administrator')
        Role.objects.create(name='Cashier', description='Cashier role')
        Role.objects.create(name='Manager', description='Manager role')
        Role.objects.create(name='Warehouse Staff', description='Warehouse role')
        
        admin_role = Role.objects.get_admin_role()
        self.assertEqual(admin_role.name, 'Admin')
        
        cashier_role = Role.objects.get_cashier_role()
        self.assertEqual(cashier_role.name, 'Cashier')


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
        admin_role = Role.objects.create(name='Admin', description='Administrator')
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
            role=self.role
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


class RoleAPITest(APITestCase):
    """Test cases for Role API endpoints"""
    
    def setUp(self):
        self.client = APIClient()
        self.admin_role = Role.objects.create(name='Admin', description='Administrator')
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
        self.assertEqual(len(response.data['results']), 1)
    
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
        response = self.client.delete(f'/accounts/api/roles/{self.admin_role.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Role.objects.filter(id=self.admin_role.id).exists())


class UserAPITest(APITestCase):
    """Test cases for User API endpoints"""
    
    def setUp(self):
        self.client = APIClient()
        self.admin_role = Role.objects.create(name='Admin', description='Administrator')
        self.cashier_role = Role.objects.create(name='Cashier', description='Cashier role')
        
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
        self.admin_role = Role.objects.create(name='Admin', description='Administrator')
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
    def test_send_welcome_email_task(self):
        """Test send_welcome_email task"""
        from accounts.tasks import send_welcome_email
        
        result = send_welcome_email(self.user.id)
        
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


class BusinessRegistrationAPITest(APITestCase):
    """Tests for business registration workflow"""

    def setUp(self):
        self.client = APIClient()

    def test_register_business_success(self):
        payload = {
            'owner_name': 'New Owner',
            'owner_email': 'newowner@example.com',
            'owner_password': 'strongpass123',
            'business_name': 'New Business',
            'business_tin': 'TIN-NEW-001',
            'business_email': 'contact@newbusiness.com',
            'business_address': '456 Commerce Ave',
            'business_phone_numbers': ['+15551234567'],
            'business_website': 'https://newbusiness.com',
            'business_social_handles': {'instagram': '@newbiz'}
        }

        response = self.client.post('/accounts/api/auth/register-business/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('token', response.data)
        self.assertIn('user', response.data)
        self.assertIn('business', response.data)

        user_id = response.data['user']['id']
        business_id = response.data['business']['id']

        business = Business.objects.get(id=business_id)
        owner = User.objects.get(id=user_id)

        self.assertEqual(business.owner, owner)
        membership = BusinessMembership.objects.get(business=business, user=owner)
        self.assertEqual(membership.role, BusinessMembership.OWNER)
        self.assertTrue(membership.is_admin)

    def test_register_business_duplicate_email(self):
        User.objects.create_user(
            email='duplicate@example.com',
            password='existingpass123',
            name='Existing User'
        )

        payload = {
            'owner_name': 'Another Owner',
            'owner_email': 'duplicate@example.com',
            'owner_password': 'strongpass123',
            'business_name': 'Another Business',
            'business_tin': 'TIN-ANOTHER-001',
            'business_email': 'contact@anotherbusiness.com',
            'business_address': '789 Commerce Ave',
            'business_phone_numbers': ['+15559876543']
        }

        response = self.client.post('/accounts/api/auth/register-business/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('owner_email', response.data)
