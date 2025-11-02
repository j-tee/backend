"""
API tests for flexible pricing system
"""
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from subscriptions.models import (
    SubscriptionPricingTier,
    TaxConfiguration,
    ServiceCharge,
)
from decimal import Decimal
from datetime import date

User = get_user_model()


class PricingTierAPITestCase(APITestCase):
    """Test cases for Pricing Tier API endpoints"""
    
    def setUp(self):
        """Set up test data and users"""
        # Create platform admin user
        self.admin_user = User.objects.create_user(
            email='admin@example.com',
            password='testpass123',
            first_name='Admin',
            last_name='User'
        )
        self.admin_user.platform_role = 'SUPER_ADMIN'
        self.admin_user.save()
        
        # Create regular user
        self.regular_user = User.objects.create_user(
            email='user@example.com',
            password='testpass123',
            first_name='Regular',
            last_name='User'
        )
        
        # Create pricing tier
        self.tier = SubscriptionPricingTier.objects.create(
            min_storefronts=1,
            max_storefronts=1,
            base_price=Decimal('100.00'),
            currency='GHS',
            is_active=True
        )
        
        self.tier_5_plus = SubscriptionPricingTier.objects.create(
            min_storefronts=5,
            max_storefronts=None,
            base_price=Decimal('200.00'),
            price_per_additional_storefront=Decimal('50.00'),
            currency='GHS',
            is_active=True
        )
    
    def test_list_pricing_tiers_authenticated(self):
        """Any authenticated user can list pricing tiers"""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get('/subscriptions/api/pricing-tiers/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
    
    def test_list_pricing_tiers_unauthenticated(self):
        """Unauthenticated users cannot list pricing tiers"""
        response = self.client.get('/subscriptions/api/pricing-tiers/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_retrieve_pricing_tier(self):
        """Authenticated users can retrieve a single tier"""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(f'/subscriptions/api/pricing-tiers/{self.tier.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['min_storefronts'], 1)
        self.assertEqual(response.data['base_price'], '100.00')
    
    def test_create_tier_requires_admin(self):
        """Only platform admins can create pricing tiers"""
        # Regular user should be denied
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.post('/subscriptions/api/pricing-tiers/', {
            'min_storefronts': 2,
            'max_storefronts': 2,
            'base_price': '150.00',
            'currency': 'GHS'
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Admin should succeed
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post('/subscriptions/api/pricing-tiers/', {
            'min_storefronts': 2,
            'max_storefronts': 2,
            'base_price': '150.00',
            'currency': 'GHS'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['min_storefronts'], 2)
    
    def test_update_tier_requires_admin(self):
        """Only platform admins can update pricing tiers"""
        # Regular user should be denied
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.patch(
            f'/subscriptions/api/pricing-tiers/{self.tier.id}/',
            {'base_price': '120.00'}
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Admin should succeed
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.patch(
            f'/subscriptions/api/pricing-tiers/{self.tier.id}/',
            {'base_price': '120.00'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['base_price'], '120.00')
    
    def test_delete_tier_requires_admin(self):
        """Only platform admins can delete pricing tiers"""
        # Regular user should be denied
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.delete(f'/subscriptions/api/pricing-tiers/{self.tier.id}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Admin should succeed
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.delete(f'/subscriptions/api/pricing-tiers/{self.tier.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
    
    def test_calculate_pricing_basic(self):
        """Test pricing calculation endpoint"""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(
            '/subscriptions/api/pricing-tiers/calculate/?storefronts=1'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['storefronts'], 1)
        self.assertEqual(response.data['base_price'], '100.00')
        self.assertEqual(response.data['additional_storefronts'], 0)
        self.assertEqual(response.data['currency'], 'GHS')
    
    def test_calculate_pricing_with_additional_storefronts(self):
        """Test pricing calculation with additional storefronts"""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(
            '/subscriptions/api/pricing-tiers/calculate/?storefronts=7'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['storefronts'], 7)
        self.assertEqual(response.data['base_price'], '300.00')  # 200 + (2 * 50)
        self.assertEqual(response.data['additional_storefronts'], 2)
        self.assertEqual(response.data['additional_cost'], '100.00')
    
    def test_calculate_pricing_invalid_storefronts(self):
        """Test pricing calculation with invalid parameters"""
        self.client.force_authenticate(user=self.regular_user)
        
        # Zero storefronts
        response = self.client.get(
            '/subscriptions/api/pricing-tiers/calculate/?storefronts=0'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Missing parameter
        response = self.client.get('/subscriptions/api/pricing-tiers/calculate/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Invalid value
        response = self.client.get(
            '/subscriptions/api/pricing-tiers/calculate/?storefronts=abc'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_activate_tier(self):
        """Test tier activation endpoint"""
        # Deactivate first
        self.tier.is_active = False
        self.tier.save()
        
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            f'/subscriptions/api/pricing-tiers/{self.tier.id}/activate/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_active'])
        
        # Verify in database
        self.tier.refresh_from_db()
        self.assertTrue(self.tier.is_active)
    
    def test_deactivate_tier(self):
        """Test tier deactivation endpoint"""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            f'/subscriptions/api/pricing-tiers/{self.tier.id}/deactivate/'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_active'])
        
        # Verify in database
        self.tier.refresh_from_db()
        self.assertFalse(self.tier.is_active)
    
    def test_filter_by_active_status(self):
        """Test filtering tiers by active status"""
        # Deactivate one tier
        self.tier.is_active = False
        self.tier.save()
        
        self.client.force_authenticate(user=self.regular_user)
        
        # Get only active tiers
        response = self.client.get('/subscriptions/api/pricing-tiers/?is_active=true')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        
        # Get only inactive tiers
        response = self.client.get('/subscriptions/api/pricing-tiers/?is_active=false')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)


class TaxConfigurationAPITestCase(APITestCase):
    """Test cases for Tax Configuration API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            email='admin@example.com',
            password='testpass123'
        )
        self.admin_user.platform_role = 'SUPER_ADMIN'
        self.admin_user.save()
        
        self.regular_user = User.objects.create_user(
            email='user@example.com',
            password='testpass123'
        )
        
        self.vat = TaxConfiguration.objects.create(
            name='VAT',
            code='VAT_GH',
            rate=Decimal('15.00'),
            country='GH',
            is_active=True,
            effective_from=date.today()
        )
    
    def test_list_tax_configs(self):
        """Test listing tax configurations"""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get('/subscriptions/api/tax-config/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_create_tax_requires_admin(self):
        """Only admins can create tax configurations"""
        # Regular user denied
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.post('/subscriptions/api/tax-config/', {
            'name': 'NHIL',
            'code': 'NHIL_GH',
            'rate': '2.50',
            'country': 'GH',
            'effective_from': date.today().isoformat()
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Admin succeeds
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post('/subscriptions/api/tax-config/', {
            'name': 'NHIL',
            'code': 'NHIL_GH',
            'rate': '2.50',
            'country': 'GH',
            'effective_from': date.today().isoformat()
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_get_active_taxes(self):
        """Test getting currently active taxes"""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get('/subscriptions/api/tax-config/active/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['code'], 'VAT_GH')


class ServiceChargeAPITestCase(APITestCase):
    """Test cases for Service Charge API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.admin_user = User.objects.create_user(
            email='admin@example.com',
            password='testpass123'
        )
        self.admin_user.platform_role = 'SUPER_ADMIN'
        self.admin_user.save()
        
        self.regular_user = User.objects.create_user(
            email='user@example.com',
            password='testpass123'
        )
        
        self.charge = ServiceCharge.objects.create(
            name='Gateway Fee',
            code='GATEWAY',
            charge_type='PERCENTAGE',
            amount=Decimal('2.00'),
            payment_gateway='PAYSTACK',
            is_active=True
        )
    
    def test_list_service_charges(self):
        """Test listing service charges"""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get('/subscriptions/api/service-charges/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_filter_by_gateway(self):
        """Test filtering charges by payment gateway"""
        # Create charge for all gateways
        ServiceCharge.objects.create(
            name='Processing Fee',
            code='PROCESSING',
            charge_type='FIXED',
            amount=Decimal('5.00'),
            payment_gateway='ALL',
            is_active=True
        )
        
        self.client.force_authenticate(user=self.regular_user)
        
        # Filter for PAYSTACK
        response = self.client.get('/subscriptions/api/service-charges/?gateway=PAYSTACK')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return 2: the PAYSTACK-specific one and the ALL one
        self.assertEqual(len(response.data['results']), 2)


class IntegratedPricingAPITestCase(APITestCase):
    """Integration tests for complete pricing API workflow"""
    
    def setUp(self):
        """Set up complete pricing scenario"""
        self.user = User.objects.create_user(
            email='user@example.com',
            password='testpass123'
        )
        
        # Pricing tier
        SubscriptionPricingTier.objects.create(
            min_storefronts=5,
            max_storefronts=None,
            base_price=Decimal('200.00'),
            price_per_additional_storefront=Decimal('50.00'),
            currency='GHS',
            is_active=True
        )
        
        # Taxes
        TaxConfiguration.objects.create(
            name='VAT',
            code='VAT_GH',
            rate=Decimal('15.00'),
            country='GH',
            applies_to='SUBTOTAL',
            calculation_order=0,
            is_active=True,
            effective_from=date.today()
        )
        
        TaxConfiguration.objects.create(
            name='NHIL',
            code='NHIL_GH',
            rate=Decimal('2.50'),
            country='GH',
            applies_to='SUBTOTAL',
            calculation_order=1,
            is_active=True,
            effective_from=date.today()
        )
        
        # Service charge
        ServiceCharge.objects.create(
            name='Gateway Fee',
            code='GATEWAY',
            charge_type='PERCENTAGE',
            amount=Decimal('2.00'),
            applies_to='TOTAL',
            payment_gateway='ALL',
            is_active=True
        )
    
    def test_complete_pricing_calculation(self):
        """Test complete pricing calculation with all components"""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.get(
            '/subscriptions/api/pricing-tiers/calculate/'
            '?storefronts=7'
            '&include_taxes=true'
            '&include_charges=true'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify structure
        self.assertIn('storefronts', response.data)
        self.assertIn('base_price', response.data)
        self.assertIn('taxes', response.data)
        self.assertIn('service_charges', response.data)
        self.assertIn('total_amount', response.data)
        self.assertIn('breakdown', response.data)
        
        # Verify calculations
        # Base: 200 + (2 * 50) = 300
        self.assertEqual(response.data['base_price'], '300.00')
        
        # Taxes should include VAT and NHIL
        self.assertIn('VAT_GH', response.data['taxes'])
        self.assertIn('NHIL_GH', response.data['taxes'])
        
        # Service charges should include gateway fee
        self.assertIn('GATEWAY', response.data['service_charges'])
        
        # Breakdown should be a list of strings
        self.assertIsInstance(response.data['breakdown'], list)
        self.assertTrue(len(response.data['breakdown']) > 0)
