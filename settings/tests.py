from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from accounts.models import Business
from .models import BusinessSettings

User = get_user_model()


class BusinessSettingsAPITestCase(TestCase):
    """Test cases for Business Settings API"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        
        # Create test user and business
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            name='Test User'
        )
        
        self.business = Business.objects.create(
            name='Test Business',
            owner=self.user
        )
        
        # Set user's current business
        self.user.current_business = self.business
        self.user.save()
        
        # Authenticate
        self.client.force_authenticate(user=self.user)

    def test_get_settings_creates_defaults(self):
        """GET should create settings with defaults if they don't exist"""
        response = self.client.get('/settings/api/settings/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('regional', response.data)
        self.assertIn('appearance', response.data)
        self.assertIn('notifications', response.data)
        self.assertIn('receipt', response.data)
        
        # Verify default currency
        self.assertEqual(response.data['regional']['currency']['code'], 'USD')
        
        # Verify default theme
        self.assertEqual(response.data['appearance']['themePreset'], 'default-blue')

    def test_update_currency(self):
        """PATCH should update currency settings"""
        data = {
            'regional': {
                'currency': {
                    'code': 'GHS',
                    'symbol': '₵',
                    'name': 'Ghanaian Cedi',
                    'position': 'before',
                    'decimalPlaces': 2
                }
            }
        }
        
        response = self.client.patch(
            '/settings/api/settings/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['regional']['currency']['code'], 'GHS')
        self.assertEqual(response.data['regional']['currency']['symbol'], '₵')

    def test_update_theme(self):
        """PATCH should update theme preset"""
        data = {
            'appearance': {
                'themePreset': 'emerald-green'
            }
        }
        
        response = self.client.patch(
            '/settings/api/settings/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['appearance']['themePreset'], 'emerald-green')

    def test_invalid_theme_rejected(self):
        """Invalid theme preset should be rejected"""
        data = {
            'appearance': {
                'themePreset': 'invalid-theme'
            }
        }
        
        response = self.client.patch(
            '/settings/api/settings/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_currency_position_rejected(self):
        """Invalid currency position should be rejected"""
        data = {
            'regional': {
                'currency': {
                    'code': 'USD',
                    'symbol': '$',
                    'name': 'US Dollar',
                    'position': 'invalid',  # Should be 'before' or 'after'
                    'decimalPlaces': 2
                }
            }
        }
        
        response = self.client.patch(
            '/settings/api/settings/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_notifications(self):
        """PATCH should update notification settings"""
        data = {
            'notifications': {
                'emailNotifications': False,
                'lowStockAlerts': True
            }
        }
        
        response = self.client.patch(
            '/settings/api/settings/',
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['notifications']['emailNotifications'])
        self.assertTrue(response.data['notifications']['lowStockAlerts'])

    def test_settings_persist(self):
        """Settings should persist across requests"""
        # Update settings
        data = {
            'appearance': {
                'themePreset': 'purple-galaxy',
                'fontSize': 'large'
            }
        }
        
        self.client.patch('/settings/api/settings/', data, format='json')
        
        # Retrieve settings again
        response = self.client.get('/settings/api/settings/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['appearance']['themePreset'], 'purple-galaxy')
        self.assertEqual(response.data['appearance']['fontSize'], 'large')

    def test_reset_to_defaults(self):
        """POST reset_to_defaults should restore default settings"""
        # First, update settings
        data = {
            'appearance': {
                'themePreset': 'purple-galaxy'
            }
        }
        self.client.patch('/settings/api/settings/', data, format='json')
        
        # Reset to defaults
        response = self.client.post('/settings/api/settings/reset_to_defaults/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['appearance']['themePreset'], 'default-blue')
        self.assertEqual(response.data['regional']['currency']['code'], 'USD')

    def test_unauthorized_access_denied(self):
        """Unauthenticated users should not access settings"""
        self.client.force_authenticate(user=None)
        
        
        response = self.client.get('/settings/api/settings/')
        
        # DRF returns 403 Forbidden for unauthenticated users with this setup
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

