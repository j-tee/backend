from django.core.management.base import BaseCommand
from accounts.models import Business
from settings.models import BusinessSettings


class Command(BaseCommand):
    help = 'Create default settings for businesses without settings'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # Find businesses without settings
        businesses = Business.objects.filter(settings__isnull=True)
        count = businesses.count()

        if count == 0:
            self.stdout.write(
                self.style.SUCCESS('All businesses already have settings!')
            )
            return

        self.stdout.write(
            self.style.WARNING(f'Found {count} businesses without settings')
        )

        if dry_run:
            self.stdout.write(
                self.style.NOTICE('\n--- DRY RUN MODE (no changes will be made) ---\n')
            )
            for business in businesses:
                self.stdout.write(f'  Would create settings for: {business.name}')
            return

        # Create settings for each business
        created_count = 0
        for business in businesses:
            try:
                settings, created = BusinessSettings.objects.get_or_create(
                    business=business,
                    defaults={
                        'regional': BusinessSettings.get_default_regional(),
                        'appearance': BusinessSettings.get_default_appearance(),
                        'notifications': BusinessSettings.get_default_notifications(),
                        'receipt': BusinessSettings.get_default_receipt(),
                    }
                )
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'✓ Created settings for: {business.name}')
                    )
                else:
                    self.stdout.write(
                        self.style.NOTICE(f'  Settings already exist for: {business.name}')
                    )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'✗ Error creating settings for {business.name}: {str(e)}')
                )

        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(
            self.style.SUCCESS(
                f'\nSuccessfully created settings for {created_count} businesses'
            )
        )
        self.stdout.write('=' * 60 + '\n')
