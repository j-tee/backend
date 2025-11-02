"""
Unit tests for flexible pricing system models
"""
from django.test import TestCase
from decimal import Decimal
from datetime import date, timedelta
from subscriptions.models import (
    SubscriptionPricingTier,
    TaxConfiguration,
    ServiceCharge,
)
from django.contrib.auth import get_user_model

User = get_user_model()


class PricingTierTestCase(TestCase):
    """Test cases for SubscriptionPricingTier model"""
    
    def setUp(self):
        """Set up test data"""
        # Create test pricing tiers
        self.tier_1 = SubscriptionPricingTier.objects.create(
            min_storefronts=1,
            max_storefronts=1,
            base_price=Decimal('100.00'),
            price_per_additional_storefront=Decimal('0.00'),
            currency='GHS',
            is_active=True
        )
        
        self.tier_2_4 = SubscriptionPricingTier.objects.create(
            min_storefronts=2,
            max_storefronts=4,
            base_price=Decimal('150.00'),
            price_per_additional_storefront=Decimal('0.00'),
            currency='GHS',
            is_active=True
        )
        
        self.tier_5_plus = SubscriptionPricingTier.objects.create(
            min_storefronts=5,
            max_storefronts=None,  # Unlimited
            base_price=Decimal('200.00'),
            price_per_additional_storefront=Decimal('50.00'),
            currency='GHS',
            is_active=True
        )
    
    def test_tier_applies_to_count(self):
        """Test if tier correctly identifies applicable storefront counts"""
        # Test tier 1
        self.assertTrue(self.tier_1.applies_to_storefront_count(1))
        self.assertFalse(self.tier_1.applies_to_storefront_count(2))
        self.assertFalse(self.tier_1.applies_to_storefront_count(0))
        
        # Test tier 2-4
        self.assertFalse(self.tier_2_4.applies_to_storefront_count(1))
        self.assertTrue(self.tier_2_4.applies_to_storefront_count(2))
        self.assertTrue(self.tier_2_4.applies_to_storefront_count(3))
        self.assertTrue(self.tier_2_4.applies_to_storefront_count(4))
        self.assertFalse(self.tier_2_4.applies_to_storefront_count(5))
        
        # Test tier 5+ (unlimited)
        self.assertTrue(self.tier_5_plus.applies_to_storefront_count(5))
        self.assertTrue(self.tier_5_plus.applies_to_storefront_count(10))
        self.assertTrue(self.tier_5_plus.applies_to_storefront_count(100))
        self.assertFalse(self.tier_5_plus.applies_to_storefront_count(4))
    
    def test_price_calculation_fixed_tier(self):
        """Test price calculation for fixed-price tiers"""
        # 1 storefront
        self.assertEqual(self.tier_1.calculate_price(1), Decimal('100.00'))
        
        # 2-4 storefronts
        self.assertEqual(self.tier_2_4.calculate_price(2), Decimal('150.00'))
        self.assertEqual(self.tier_2_4.calculate_price(3), Decimal('150.00'))
        self.assertEqual(self.tier_2_4.calculate_price(4), Decimal('150.00'))
    
    def test_price_calculation_incremental_tier(self):
        """Test price calculation for incremental pricing (5+ tier)"""
        # 5 storefronts (base price only)
        self.assertEqual(self.tier_5_plus.calculate_price(5), Decimal('200.00'))
        
        # 7 storefronts (5 base + 2 additional @ 50 each = 200 + 100)
        self.assertEqual(self.tier_5_plus.calculate_price(7), Decimal('300.00'))
        
        # 10 storefronts (5 base + 5 additional @ 50 each = 200 + 250)
        self.assertEqual(self.tier_5_plus.calculate_price(10), Decimal('450.00'))
        
        # 15 storefronts (5 base + 10 additional @ 50 each = 200 + 500)
        self.assertEqual(self.tier_5_plus.calculate_price(15), Decimal('700.00'))
    
    def test_price_calculation_invalid_count(self):
        """Test that ValueError is raised for invalid storefront counts"""
        with self.assertRaises(ValueError):
            self.tier_1.calculate_price(2)  # Tier 1 only applies to 1 storefront
        
        with self.assertRaises(ValueError):
            self.tier_2_4.calculate_price(5)  # Tier 2-4 doesn't apply to 5
    
    def test_tier_string_representation(self):
        """Test __str__ method for tiers"""
        self.assertIn('1-1 storefronts', str(self.tier_1))
        self.assertIn('GHS 100.00', str(self.tier_1))
        
        self.assertIn('5+ storefronts', str(self.tier_5_plus))
        self.assertIn('GHS 200.00', str(self.tier_5_plus))
        self.assertIn('50.00/extra', str(self.tier_5_plus))


class TaxConfigurationTestCase(TestCase):
    """Test cases for TaxConfiguration model"""
    
    def setUp(self):
        """Set up test data"""
        self.vat = TaxConfiguration.objects.create(
            name='VAT',
            code='VAT_GH',
            description='Value Added Tax',
            rate=Decimal('15.00'),
            country='GH',
            applies_to_subscriptions=True,
            is_mandatory=True,
            calculation_order=0,
            applies_to='SUBTOTAL',
            is_active=True,
            effective_from=date.today() - timedelta(days=30)
        )
        
        self.nhil = TaxConfiguration.objects.create(
            name='NHIL',
            code='NHIL_GH',
            description='National Health Insurance Levy',
            rate=Decimal('2.50'),
            country='GH',
            applies_to_subscriptions=True,
            is_mandatory=True,
            calculation_order=1,
            applies_to='SUBTOTAL',
            is_active=True,
            effective_from=date.today() - timedelta(days=30)
        )
        
        # Future tax (not yet effective)
        self.future_tax = TaxConfiguration.objects.create(
            name='Future Tax',
            code='FUTURE_GH',
            rate=Decimal('5.00'),
            country='GH',
            is_active=True,
            effective_from=date.today() + timedelta(days=30)
        )
        
        # Expired tax
        self.expired_tax = TaxConfiguration.objects.create(
            name='Expired Tax',
            code='EXPIRED_GH',
            rate=Decimal('10.00'),
            country='GH',
            is_active=True,
            effective_from=date.today() - timedelta(days=60),
            effective_until=date.today() - timedelta(days=1)
        )
    
    def test_is_effective_current_taxes(self):
        """Test is_effective for currently effective taxes"""
        self.assertTrue(self.vat.is_effective())
        self.assertTrue(self.nhil.is_effective())
    
    def test_is_effective_future_tax(self):
        """Test is_effective for future taxes"""
        self.assertFalse(self.future_tax.is_effective())
        
        # Test with specific date
        future_date = date.today() + timedelta(days=31)
        self.assertTrue(self.future_tax.is_effective(future_date))
    
    def test_is_effective_expired_tax(self):
        """Test is_effective for expired taxes"""
        self.assertFalse(self.expired_tax.is_effective())
        
        # Test with date when it was effective
        past_date = date.today() - timedelta(days=30)
        self.assertTrue(self.expired_tax.is_effective(past_date))
    
    def test_calculate_amount(self):
        """Test tax amount calculation"""
        base_amount = Decimal('100.00')
        
        # VAT 15%
        vat_amount = self.vat.calculate_amount(base_amount)
        self.assertEqual(vat_amount, Decimal('15.00'))
        
        # NHIL 2.5%
        nhil_amount = self.nhil.calculate_amount(base_amount)
        self.assertEqual(nhil_amount, Decimal('2.50'))
        
        # Test with different base amounts
        self.assertEqual(self.vat.calculate_amount(Decimal('200.00')), Decimal('30.00'))
        self.assertEqual(self.nhil.calculate_amount(Decimal('500.00')), Decimal('12.50'))
    
    def test_tax_string_representation(self):
        """Test __str__ method for taxes"""
        self.assertIn('VAT', str(self.vat))
        self.assertIn('15.00', str(self.vat))
        self.assertIn('GH', str(self.vat))


class ServiceChargeTestCase(TestCase):
    """Test cases for ServiceCharge model"""
    
    def setUp(self):
        """Set up test data"""
        self.percentage_charge = ServiceCharge.objects.create(
            name='Payment Gateway Fee',
            code='GATEWAY_FEE',
            charge_type='PERCENTAGE',
            amount=Decimal('2.00'),  # 2%
            currency='GHS',
            applies_to='SUBTOTAL',
            payment_gateway='PAYSTACK',
            is_active=True
        )
        
        self.fixed_charge = ServiceCharge.objects.create(
            name='Processing Fee',
            code='PROCESSING_FEE',
            charge_type='FIXED',
            amount=Decimal('5.00'),  # Fixed GHS 5
            currency='GHS',
            applies_to='TOTAL',
            payment_gateway='ALL',
            is_active=True
        )
    
    def test_calculate_percentage_charge(self):
        """Test calculation for percentage-based charges"""
        base_amount = Decimal('100.00')
        
        charge = self.percentage_charge.calculate_amount(base_amount)
        self.assertEqual(charge, Decimal('2.00'))  # 2% of 100
        
        # Test with different amounts
        self.assertEqual(
            self.percentage_charge.calculate_amount(Decimal('500.00')),
            Decimal('10.00')
        )
    
    def test_calculate_fixed_charge(self):
        """Test calculation for fixed charges"""
        # Fixed charge should return same amount regardless of base
        self.assertEqual(
            self.fixed_charge.calculate_amount(Decimal('100.00')),
            Decimal('5.00')
        )
        self.assertEqual(
            self.fixed_charge.calculate_amount(Decimal('1000.00')),
            Decimal('5.00')
        )
    
    def test_charge_string_representation(self):
        """Test __str__ method for service charges"""
        percentage_str = str(self.percentage_charge)
        self.assertIn('Payment Gateway Fee', percentage_str)
        self.assertIn('2.00%', percentage_str)
        
        fixed_str = str(self.fixed_charge)
        self.assertIn('Processing Fee', fixed_str)
        self.assertIn('GHS 5.00', fixed_str)


class IntegratedPricingTestCase(TestCase):
    """Integration tests for complete pricing calculation"""
    
    def setUp(self):
        """Set up complete pricing scenario"""
        # Pricing tier
        self.tier = SubscriptionPricingTier.objects.create(
            min_storefronts=5,
            max_storefronts=None,
            base_price=Decimal('200.00'),
            price_per_additional_storefront=Decimal('50.00'),
            currency='GHS'
        )
        
        # Taxes
        self.vat = TaxConfiguration.objects.create(
            name='VAT',
            code='VAT_GH',
            rate=Decimal('15.00'),
            country='GH',
            applies_to='SUBTOTAL',
            calculation_order=0,
            is_active=True,
            effective_from=date.today()
        )
        
        self.nhil = TaxConfiguration.objects.create(
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
        self.gateway_fee = ServiceCharge.objects.create(
            name='Gateway Fee',
            code='GATEWAY',
            charge_type='PERCENTAGE',
            amount=Decimal('2.00'),
            applies_to='TOTAL',
            payment_gateway='ALL',
            is_active=True
        )
    
    def test_complete_pricing_calculation(self):
        """Test complete pricing calculation for 7 storefronts"""
        storefront_count = 7
        
        # Calculate base price
        base_price = self.tier.calculate_price(storefront_count)
        self.assertEqual(base_price, Decimal('300.00'))  # 200 + (2 * 50)
        
        # Calculate taxes
        vat_amount = self.vat.calculate_amount(base_price)
        self.assertEqual(vat_amount, Decimal('45.00'))  # 15% of 300
        
        nhil_amount = self.nhil.calculate_amount(base_price)
        self.assertEqual(nhil_amount, Decimal('7.50'))  # 2.5% of 300
        
        total_tax = vat_amount + nhil_amount
        self.assertEqual(total_tax, Decimal('52.50'))
        
        # Calculate service charge on total (base + tax)
        subtotal_with_tax = base_price + total_tax
        self.assertEqual(subtotal_with_tax, Decimal('352.50'))
        
        gateway_fee = self.gateway_fee.calculate_amount(subtotal_with_tax)
        self.assertEqual(gateway_fee, Decimal('7.05'))  # 2% of 352.50
        
        # Final total
        total = base_price + total_tax + gateway_fee
        self.assertEqual(total, Decimal('359.55'))
