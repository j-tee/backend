"""
Management command to set up pricing tiers and tax configurations in production.
Run with: python manage.py setup_pricing_tiers
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from subscriptions.models import SubscriptionPricingTier, TaxConfiguration
from datetime import date


class Command(BaseCommand):
    help = 'Set up pricing tiers and tax configurations for subscription system'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Setting up pricing tiers and tax configurations...'))
        
        # Create Pricing Tiers
        tiers_data = [
            {
                'min_storefronts': 1,
                'max_storefronts': 1,
                'base_price': 100.00,
                'price_per_additional_storefront': 0.00,
                'currency': 'GHS',
                'is_active': True,
                'description': 'Tier for 1 storefront'
            },
            {
                'min_storefronts': 2,
                'max_storefronts': 2,
                'base_price': 150.00,
                'price_per_additional_storefront': 0.00,
                'currency': 'GHS',
                'is_active': True,
                'description': 'Tier for 2 storefronts'
            },
            {
                'min_storefronts': 3,
                'max_storefronts': 3,
                'base_price': 180.00,
                'price_per_additional_storefront': 0.00,
                'currency': 'GHS',
                'is_active': True,
                'description': 'Tier for 3 storefronts'
            },
            {
                'min_storefronts': 4,
                'max_storefronts': 4,
                'base_price': 200.00,
                'price_per_additional_storefront': 0.00,
                'currency': 'GHS',
                'is_active': True,
                'description': 'Tier for 4 storefronts'
            },
            {
                'min_storefronts': 5,
                'max_storefronts': None,
                'base_price': 200.00,
                'price_per_additional_storefront': 50.00,
                'currency': 'GHS',
                'is_active': True,
                'description': 'Tier for 5+ storefronts (base + per additional)'
            },
        ]
        
        created_tiers = 0
        existing_tiers = 0
        
        for tier_data in tiers_data:
            tier, created = SubscriptionPricingTier.objects.get_or_create(
                min_storefronts=tier_data['min_storefronts'],
                max_storefronts=tier_data['max_storefronts'],
                defaults=tier_data
            )
            if created:
                created_tiers += 1
                self.stdout.write(self.style.SUCCESS(
                    f'✓ Created pricing tier: {tier_data["min_storefronts"]}-{tier_data["max_storefronts"]} @ GHS {tier_data["base_price"]}'
                ))
            else:
                existing_tiers += 1
                self.stdout.write(self.style.WARNING(
                    f'  Tier already exists: {tier_data["min_storefronts"]}-{tier_data["max_storefronts"]}'
                ))
        
        # Create Tax Configurations
        taxes_data = [
            {
                'code': 'VAT_GH',
                'name': 'VAT',
                'rate': 3.00,
                'is_percentage': True,
                'applies_to_subscriptions': True,
                'is_active': True,
                'calculation_order': 1,
                'effective_from': date(2024, 1, 1),
                'description': 'Value Added Tax (Ghana)'
            },
            {
                'code': 'NHIL_GH',
                'name': 'NHIL',
                'rate': 2.50,
                'is_percentage': True,
                'applies_to_subscriptions': True,
                'is_active': True,
                'calculation_order': 2,
                'effective_from': date(2024, 1, 1),
                'description': 'National Health Insurance Levy (Ghana)'
            },
            {
                'code': 'GETFUND_GH',
                'name': 'GETFund Levy',
                'rate': 2.50,
                'is_percentage': True,
                'applies_to_subscriptions': True,
                'is_active': True,
                'calculation_order': 3,
                'effective_from': date(2024, 1, 1),
                'description': 'Ghana Education Trust Fund Levy'
            },
            {
                'code': 'COVID19_GH',
                'name': 'COVID-19 Health Recovery Levy',
                'rate': 1.00,
                'is_percentage': True,
                'applies_to_subscriptions': True,
                'is_active': True,
                'calculation_order': 4,
                'effective_from': date(2024, 1, 1),
                'description': 'COVID-19 Health Recovery Levy (Ghana)'
            },
        ]
        
        created_taxes = 0
        existing_taxes = 0
        
        for tax_data in taxes_data:
            tax, created = TaxConfiguration.objects.get_or_create(
                code=tax_data['code'],
                defaults=tax_data
            )
            if created:
                created_taxes += 1
                self.stdout.write(self.style.SUCCESS(
                    f'✓ Created tax: {tax_data["name"]} ({tax_data["code"]}) @ {tax_data["rate"]}%'
                ))
            else:
                existing_taxes += 1
                self.stdout.write(self.style.WARNING(
                    f'  Tax already exists: {tax_data["name"]} ({tax_data["code"]})'
                ))
        
        # Summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('✓ Setup complete!'))
        self.stdout.write(f'  Pricing Tiers: {created_tiers} created, {existing_tiers} already existed')
        self.stdout.write(f'  Tax Configurations: {created_taxes} created, {existing_taxes} already existed')
        self.stdout.write('='*60)
