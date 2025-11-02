"""
Management command to set up default pricing tiers and tax configurations
"""
from django.core.management.base import BaseCommand
from subscriptions.models import SubscriptionPricingTier, TaxConfiguration
from decimal import Decimal
from datetime import date


class Command(BaseCommand):
    help = 'Set up default pricing tiers and tax configurations for Ghana'
    
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Setting up default pricing tiers...'))
        
        # Create pricing tiers
        tiers_data = [
            (1, 1, Decimal('100.00'), Decimal('0.00')),
            (2, 2, Decimal('150.00'), Decimal('0.00')),
            (3, 3, Decimal('180.00'), Decimal('0.00')),
            (4, 4, Decimal('200.00'), Decimal('0.00')),
            (5, None, Decimal('200.00'), Decimal('50.00')),  # 5+ storefronts
        ]
        
        created_count = 0
        updated_count = 0
        
        for min_sf, max_sf, base, additional in tiers_data:
            tier, created = SubscriptionPricingTier.objects.get_or_create(
                min_storefronts=min_sf,
                max_storefronts=max_sf,
                defaults={
                    'base_price': base,
                    'price_per_additional_storefront': additional,
                    'currency': 'GHS',
                    'is_active': True,
                    'description': f'Tier for {min_sf}{"-" + str(max_sf) if max_sf else "+"} storefronts'
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'  ✓ Created tier: {tier}'))
            else:
                # Update existing tier if values differ
                if tier.base_price != base or tier.price_per_additional_storefront != additional:
                    tier.base_price = base
                    tier.price_per_additional_storefront = additional
                    tier.save()
                    updated_count += 1
                    self.stdout.write(self.style.WARNING(f'  ↻ Updated tier: {tier}'))
                else:
                    self.stdout.write(f'  - Tier already exists: {tier}')
        
        self.stdout.write(self.style.SUCCESS(f'\nPricing tiers setup complete: {created_count} created, {updated_count} updated'))
        
        # Create tax configurations
        self.stdout.write(self.style.SUCCESS('\nSetting up Ghana tax configurations...'))
        
        taxes_data = [
            ('VAT', 'VAT_GH', 'Value Added Tax', Decimal('15.00'), 0),
            ('NHIL', 'NHIL_GH', 'National Health Insurance Levy', Decimal('2.50'), 1),
            ('GETFund Levy', 'GETFUND_GH', 'Ghana Education Trust Fund Levy', Decimal('2.50'), 2),
            ('COVID-19 Health Recovery Levy', 'COVID19_GH', 'COVID-19 Health Recovery Levy', Decimal('1.00'), 3),
        ]
        
        tax_created_count = 0
        tax_updated_count = 0
        
        for name, code, desc, rate, order in taxes_data:
            tax, created = TaxConfiguration.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'description': desc,
                    'rate': rate,
                    'country': 'GH',
                    'applies_to_subscriptions': True,
                    'is_mandatory': True,
                    'calculation_order': order,
                    'applies_to': 'SUBTOTAL',
                    'is_active': True,
                    'effective_from': date.today()
                }
            )
            
            if created:
                tax_created_count += 1
                self.stdout.write(self.style.SUCCESS(f'  ✓ Created tax: {tax}'))
            else:
                # Update existing tax if rate differs
                if tax.rate != rate:
                    tax.rate = rate
                    tax.save()
                    tax_updated_count += 1
                    self.stdout.write(self.style.WARNING(f'  ↻ Updated tax: {tax}'))
                else:
                    self.stdout.write(f'  - Tax already exists: {tax}')
        
        self.stdout.write(self.style.SUCCESS(f'\nTax configurations setup complete: {tax_created_count} created, {tax_updated_count} updated'))
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n' + '='*50))
        self.stdout.write(self.style.SUCCESS('✅ SETUP COMPLETE!'))
        self.stdout.write(self.style.SUCCESS('='*50))
        self.stdout.write(f'\nPricing Tiers: {created_count} created, {updated_count} updated')
        self.stdout.write(f'Tax Configs:   {tax_created_count} created, {tax_updated_count} updated')
        self.stdout.write('\nYou can now use the pricing calculation API:')
        self.stdout.write('  GET /subscriptions/api/pricing-tiers/calculate/?storefronts=5')
