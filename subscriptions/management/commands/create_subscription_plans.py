"""
Management command to create default subscription plans
"""
from django.core.management.base import BaseCommand
from subscriptions.models import SubscriptionPlan
from decimal import Decimal


class Command(BaseCommand):
    help = 'Create default subscription plans'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing plans before creating new ones',
        )

    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write(self.style.WARNING('Deleting existing plans...'))
            SubscriptionPlan.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Existing plans deleted'))

        # Check if plans already exist
        if SubscriptionPlan.objects.exists() and not options['reset']:
            self.stdout.write(self.style.WARNING(
                'Plans already exist. Use --reset to delete and recreate.'
            ))
            return

        self.stdout.write('Creating subscription plans...')

        # Free Plan
        free_plan, created = SubscriptionPlan.objects.get_or_create(
            name='Free Plan',
            defaults={
                'description': 'Perfect for getting started with basic features',
                'price': Decimal('0.00'),
                'currency': 'GHS',
                'billing_cycle': 'MONTHLY',
                'max_users': 1,
                'max_storefronts': 1,
                'max_products': 100,
                'features': {
                    'multi_storefront': False,
                    'advanced_reports': False,
                    'api_access': False,
                    'priority_support': False,
                    'inventory_management': True,
                    'basic_reports': True,
                    'sales_tracking': True,
                },
                'is_active': True,
                'is_popular': False,
                'sort_order': 1,
                'trial_period_days': 0,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'✓ Created: {free_plan.name}'))
        else:
            self.stdout.write(self.style.WARNING(f'Already exists: {free_plan.name}'))

        # Starter Plan
        starter_plan, created = SubscriptionPlan.objects.get_or_create(
            name='Starter Plan',
            defaults={
                'description': 'Great for small businesses starting to grow',
                'price': Decimal('49.99'),
                'currency': 'GHS',
                'billing_cycle': 'MONTHLY',
                'max_users': 3,
                'max_storefronts': 2,
                'max_products': 500,
                'features': {
                    'multi_storefront': True,
                    'advanced_reports': False,
                    'api_access': False,
                    'priority_support': False,
                    'inventory_management': True,
                    'basic_reports': True,
                    'sales_tracking': True,
                    'customer_management': True,
                    'email_support': True,
                },
                'is_active': True,
                'is_popular': False,
                'sort_order': 2,
                'trial_period_days': 14,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'✓ Created: {starter_plan.name}'))
        else:
            self.stdout.write(self.style.WARNING(f'Already exists: {starter_plan.name}'))

        # Professional Plan
        professional_plan, created = SubscriptionPlan.objects.get_or_create(
            name='Professional Plan',
            defaults={
                'description': 'For growing businesses that need more power',
                'price': Decimal('99.99'),
                'currency': 'GHS',
                'billing_cycle': 'MONTHLY',
                'max_users': 10,
                'max_storefronts': 5,
                'max_products': 2000,
                'features': {
                    'multi_storefront': True,
                    'advanced_reports': True,
                    'api_access': True,
                    'priority_support': False,
                    'inventory_management': True,
                    'basic_reports': True,
                    'sales_tracking': True,
                    'customer_management': True,
                    'email_support': True,
                    'analytics_dashboard': True,
                    'data_export': True,
                    'custom_fields': True,
                },
                'is_active': True,
                'is_popular': True,
                'sort_order': 3,
                'trial_period_days': 14,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'✓ Created: {professional_plan.name}'))
        else:
            self.stdout.write(self.style.WARNING(f'Already exists: {professional_plan.name}'))

        # Business Plan
        business_plan, created = SubscriptionPlan.objects.get_or_create(
            name='Business Plan',
            defaults={
                'description': 'Advanced features for established businesses',
                'price': Decimal('199.99'),
                'currency': 'GHS',
                'billing_cycle': 'MONTHLY',
                'max_users': 25,
                'max_storefronts': 10,
                'max_products': 10000,
                'features': {
                    'multi_storefront': True,
                    'advanced_reports': True,
                    'api_access': True,
                    'priority_support': True,
                    'inventory_management': True,
                    'basic_reports': True,
                    'sales_tracking': True,
                    'customer_management': True,
                    'email_support': True,
                    'analytics_dashboard': True,
                    'data_export': True,
                    'custom_fields': True,
                    'dedicated_account_manager': True,
                    'advanced_integrations': True,
                    'white_label': False,
                },
                'is_active': True,
                'is_popular': False,
                'sort_order': 4,
                'trial_period_days': 14,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'✓ Created: {business_plan.name}'))
        else:
            self.stdout.write(self.style.WARNING(f'Already exists: {business_plan.name}'))

        # Enterprise Plan
        enterprise_plan, created = SubscriptionPlan.objects.get_or_create(
            name='Enterprise Plan',
            defaults={
                'description': 'Unlimited power for large organizations',
                'price': Decimal('499.99'),
                'currency': 'GHS',
                'billing_cycle': 'MONTHLY',
                'max_users': 999999,  # Unlimited
                'max_storefronts': 999999,  # Unlimited
                'max_products': 999999,  # Unlimited
                'features': {
                    'multi_storefront': True,
                    'advanced_reports': True,
                    'api_access': True,
                    'priority_support': True,
                    'inventory_management': True,
                    'basic_reports': True,
                    'sales_tracking': True,
                    'customer_management': True,
                    'email_support': True,
                    'analytics_dashboard': True,
                    'data_export': True,
                    'custom_fields': True,
                    'dedicated_account_manager': True,
                    'advanced_integrations': True,
                    'white_label': True,
                    'custom_development': True,
                    'sla_guarantee': True,
                    'unlimited_everything': True,
                },
                'is_active': True,
                'is_popular': False,
                'sort_order': 5,
                'trial_period_days': 30,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'✓ Created: {enterprise_plan.name}'))
        else:
            self.stdout.write(self.style.WARNING(f'Already exists: {enterprise_plan.name}'))

        # Display summary
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('Subscription Plans Summary:'))
        self.stdout.write('=' * 60)
        
        plans = SubscriptionPlan.objects.all().order_by('sort_order')
        for plan in plans:
            status = '✓ ACTIVE' if plan.is_active else '✗ INACTIVE'
            popular = ' ⭐ POPULAR' if plan.is_popular else ''
            self.stdout.write(
                f'{plan.name:20} | {plan.price:>8} {plan.currency} | '
                f'{plan.max_storefronts:>2} storefronts | {status}{popular}'
            )
        
        self.stdout.write('=' * 60)
        self.stdout.write(self.style.SUCCESS(
            f'\n✓ Total plans created: {plans.count()}'
        ))
        self.stdout.write('\nYou can now:')
        self.stdout.write('  1. View plans at: /subscriptions/api/plans/')
        self.stdout.write('  2. Manage in admin: /admin/subscriptions/subscriptionplan/')
        self.stdout.write('  3. Edit via API (platform admin only)')
