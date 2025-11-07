"""
Django management command to setup AI credit packages and grant test credits

Usage:
    python manage.py setup_ai_credits                    # Info about packages
    python manage.py setup_ai_credits --grant-test       # Grant 50 test credits to all businesses
    python manage.py setup_ai_credits --grant-test --business-id=123  # Grant to specific business
    python manage.py setup_ai_credits --grant-starter    # Grant starter package to all businesses
    python manage.py setup_ai_credits --reset            # Reset all AI credits (WARNING: deletes all)
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from datetime import timedelta
from ai_features.models import BusinessAICredits, AICreditPurchase
from accounts.models import Business


class Command(BaseCommand):
    help = 'Setup AI credit packages and grant test credits to businesses'

    # Credit package definitions (must match views.py)
    CREDIT_PACKAGES = {
        'starter': {
            'amount': Decimal('30.00'),
            'credits': Decimal('30.00'),
            'bonus': Decimal('0.00'),
            'description': 'Starter Package - 30 credits for GHS 30'
        },
        'value': {
            'amount': Decimal('80.00'),
            'credits': Decimal('80.00'),
            'bonus': Decimal('20.00'),
            'description': 'Value Package - 100 credits (80 + 20 bonus) for GHS 80'
        },
        'premium': {
            'amount': Decimal('180.00'),
            'credits': Decimal('180.00'),
            'bonus': Decimal('70.00'),
            'description': 'Premium Package - 250 credits (180 + 70 bonus) for GHS 180'
        },
        'test': {
            'amount': Decimal('0.00'),
            'credits': Decimal('50.00'),
            'bonus': Decimal('0.00'),
            'description': 'Test Credits - 50 free credits for testing'
        }
    }

    def add_arguments(self, parser):
        parser.add_argument(
            '--grant-test',
            action='store_true',
            help='Grant 50 test credits to businesses',
        )
        parser.add_argument(
            '--grant-starter',
            action='store_true',
            help='Grant starter package (30 credits) to all businesses',
        )
        parser.add_argument(
            '--grant-value',
            action='store_true',
            help='Grant value package (100 credits) to all businesses',
        )
        parser.add_argument(
            '--grant-premium',
            action='store_true',
            help='Grant premium package (250 credits) to all businesses',
        )
        parser.add_argument(
            '--business-id',
            type=int,
            help='Grant credits to specific business ID only',
        )
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset all AI credits (WARNING: deletes all credit data)',
        )
        parser.add_argument(
            '--list-businesses',
            action='store_true',
            help='List all businesses with their current credit balances',
        )

    def handle(self, *args, **options):
        # Display package information
        if not any([
            options['grant_test'],
            options['grant_starter'],
            options['grant_value'],
            options['grant_premium'],
            options['reset'],
            options['list_businesses']
        ]):
            self.display_packages()
            return

        # List businesses
        if options['list_businesses']:
            self.list_businesses()
            return

        # Reset credits
        if options['reset']:
            self.reset_credits()
            return

        # Grant credits
        if options['grant_test']:
            self.grant_credits('test', options['business_id'])
        elif options['grant_starter']:
            self.grant_credits('starter', options['business_id'])
        elif options['grant_value']:
            self.grant_credits('value', options['business_id'])
        elif options['grant_premium']:
            self.grant_credits('premium', options['business_id'])

    def display_packages(self):
        """Display information about available credit packages"""
        self.stdout.write(self.style.SUCCESS('\n' + '='*80))
        self.stdout.write(self.style.SUCCESS('AI CREDIT PACKAGES'))
        self.stdout.write(self.style.SUCCESS('='*80 + '\n'))

        for package_name, package_info in self.CREDIT_PACKAGES.items():
            if package_name == 'test':
                continue
            
            total_credits = package_info['credits'] + package_info['bonus']
            
            self.stdout.write(self.style.HTTP_INFO(f"\n📦 {package_name.upper()} PACKAGE"))
            self.stdout.write(f"   Price:        GHS {package_info['amount']}")
            self.stdout.write(f"   Base Credits: {package_info['credits']}")
            self.stdout.write(f"   Bonus:        {package_info['bonus']}")
            self.stdout.write(self.style.SUCCESS(f"   Total:        {total_credits} credits"))
            
            if package_info['bonus'] > 0:
                bonus_percent = (package_info['bonus'] / package_info['credits']) * 100
                self.stdout.write(self.style.WARNING(f"   Bonus:        {bonus_percent:.0f}% extra"))

        self.stdout.write(self.style.SUCCESS('\n' + '='*80))
        self.stdout.write('\nUSAGE EXAMPLES:')
        self.stdout.write('  python manage.py setup_ai_credits --grant-test')
        self.stdout.write('  python manage.py setup_ai_credits --grant-starter --business-id=1')
        self.stdout.write('  python manage.py setup_ai_credits --list-businesses')
        self.stdout.write('  python manage.py setup_ai_credits --reset')
        self.stdout.write('')

    def list_businesses(self):
        """List all businesses with their credit balances"""
        self.stdout.write(self.style.SUCCESS('\n' + '='*80))
        self.stdout.write(self.style.SUCCESS('BUSINESS AI CREDIT BALANCES'))
        self.stdout.write(self.style.SUCCESS('='*80 + '\n'))

        businesses = Business.objects.all()
        
        if not businesses.exists():
            self.stdout.write(self.style.WARNING('No businesses found.'))
            return

        for business in businesses:
            # Get active credits
            active_credits = BusinessAICredits.objects.filter(
                business=business,
                is_active=True
            ).first()

            balance = active_credits.balance if active_credits else Decimal('0.00')
            expires_at = active_credits.expires_at if active_credits else None

            self.stdout.write(f"\n🏢 {business.name} (ID: {business.id})")
            self.stdout.write(f"   Balance: {balance} credits")
            
            if expires_at:
                self.stdout.write(f"   Expires: {expires_at.strftime('%Y-%m-%d %H:%M')}")
            else:
                self.stdout.write(self.style.WARNING(f"   Status:  No active credits"))

            # Get purchase history
            purchases = AICreditPurchase.objects.filter(
                business=business,
                payment_status='completed'
            ).count()
            
            if purchases > 0:
                self.stdout.write(f"   Purchases: {purchases} completed")

        self.stdout.write(self.style.SUCCESS('\n' + '='*80 + '\n'))

    @transaction.atomic
    def grant_credits(self, package_name, business_id=None):
        """Grant credits to businesses"""
        package = self.CREDIT_PACKAGES[package_name]
        
        # Get businesses to grant credits to
        if business_id:
            businesses = Business.objects.filter(id=business_id)
            if not businesses.exists():
                raise CommandError(f'Business with ID {business_id} not found')
        else:
            businesses = Business.objects.all()
            if not businesses.exists():
                self.stdout.write(self.style.WARNING('No businesses found.'))
                return

        self.stdout.write(self.style.SUCCESS(f'\nGranting {package["description"]}...\n'))

        total_granted = 0
        for business in businesses:
            try:
                # Calculate total credits (base + bonus)
                total_credits = package['credits'] + package['bonus']
                
                # Create or update BusinessAICredits
                credit_record, created = BusinessAICredits.objects.get_or_create(
                    business=business,
                    is_active=True,
                    defaults={
                        'balance': total_credits,
                        'expires_at': timezone.now() + timedelta(days=180)  # 6 months
                    }
                )
                
                if not created:
                    # Add to existing balance
                    credit_record.balance += total_credits
                    credit_record.expires_at = timezone.now() + timedelta(days=180)
                    credit_record.save()

                # Create purchase record
                payment_method = 'free_trial' if package_name == 'test' else 'admin_grant'
                reference = f"GRANT-{package_name.upper()}-{business.id}-{timezone.now().timestamp()}"
                
                AICreditPurchase.objects.create(
                    business=business,
                    amount_paid=package['amount'],
                    credits_purchased=package['credits'],
                    bonus_credits=package['bonus'],
                    payment_reference=reference,
                    payment_method=payment_method,
                    payment_status='completed',
                    completed_at=timezone.now(),
                    notes=f"Admin granted {package['description']}"
                )

                action = "Created" if created else "Updated"
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ {action} credits for {business.name}: '
                        f'+{total_credits} credits (new balance: {credit_record.balance})'
                    )
                )
                total_granted += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Failed to grant credits to {business.name}: {str(e)}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'\n✓ Successfully granted credits to {total_granted} business(es)\n')
        )

    @transaction.atomic
    def reset_credits(self):
        """Reset all AI credit data (WARNING: deletes everything)"""
        self.stdout.write(
            self.style.WARNING('\n⚠️  WARNING: This will delete ALL AI credit data!\n')
        )
        
        # Count records
        credits_count = BusinessAICredits.objects.count()
        purchases_count = AICreditPurchase.objects.count()
        
        self.stdout.write(f'Records to be deleted:')
        self.stdout.write(f'  - {credits_count} BusinessAICredits records')
        self.stdout.write(f'  - {purchases_count} AICreditPurchase records')
        
        confirm = input('\nType "DELETE" to confirm: ')
        
        if confirm != 'DELETE':
            self.stdout.write(self.style.ERROR('\nAborted. No data was deleted.\n'))
            return

        # Delete all records
        BusinessAICredits.objects.all().delete()
        AICreditPurchase.objects.all().delete()
        
        self.stdout.write(
            self.style.SUCCESS('\n✓ All AI credit data has been deleted.\n')
        )
