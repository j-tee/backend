"""
Management command to create the platform owner account with complete system access
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import User


class Command(BaseCommand):
    help = 'Create platform owner account with complete system access'

    def handle(self, *args, **options):
        email = 'alphalogiquetechnologies@gmail.com'
        
        # Check if user already exists
        if User.objects.filter(email=email).exists():
            self.stdout.write(
                self.style.WARNING(f'User with email {email} already exists!')
            )
            user = User.objects.get(email=email)
            self.stdout.write(self.style.SUCCESS(f'User ID: {user.id}'))
            self.stdout.write(self.style.SUCCESS(f'Name: {user.name}'))
            self.stdout.write(self.style.SUCCESS(f'Is Superuser: {user.is_superuser}'))
            self.stdout.write(self.style.SUCCESS(f'Platform Role: {user.platform_role}'))
            
            # Ask if they want to update the user
            update = input('Do you want to update this user to platform owner? (yes/no): ')
            if update.lower() not in ['yes', 'y']:
                self.stdout.write(self.style.WARNING('Operation cancelled'))
                return
            
            # Update existing user
            with transaction.atomic():
                user.is_staff = True
                user.is_superuser = True
                user.is_active = True
                user.platform_role = User.PLATFORM_SUPER_ADMIN
                user.account_type = User.ACCOUNT_OWNER
                user.name = user.name or 'AlphaLogique Platform Owner'
                user.save()
                
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully updated platform owner account!')
                )
        else:
            # Create new user
            password = input('Enter password for platform owner: ')
            if not password:
                self.stdout.write(self.style.ERROR('Password cannot be empty!'))
                return
            
            confirm_password = input('Confirm password: ')
            if password != confirm_password:
                self.stdout.write(self.style.ERROR('Passwords do not match!'))
                return
            
            with transaction.atomic():
                user = User.objects.create_superuser(
                    email=email,
                    password=password,
                    name='AlphaLogique Platform Owner',
                    platform_role=User.PLATFORM_SUPER_ADMIN,
                    account_type=User.ACCOUNT_OWNER
                )
                
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully created platform owner account!')
                )
        
        # Display account details
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('PLATFORM OWNER ACCOUNT DETAILS'))
        self.stdout.write('='*60)
        self.stdout.write(f'User ID: {user.id}')
        self.stdout.write(f'Name: {user.name}')
        self.stdout.write(f'Email: {user.email}')
        self.stdout.write(f'Account Type: {user.get_account_type_display()}')
        self.stdout.write(f'Platform Role: {user.get_platform_role_display()}')
        self.stdout.write(f'Is Superuser: {user.is_superuser}')
        self.stdout.write(f'Is Staff: {user.is_staff}')
        self.stdout.write(f'Is Active: {user.is_active}')
        self.stdout.write('='*60)
        self.stdout.write('\n' + self.style.SUCCESS('Platform owner has complete access to:'))
        self.stdout.write('  ✓ Django Admin Panel')
        self.stdout.write('  ✓ All API Endpoints')
        self.stdout.write('  ✓ User Management')
        self.stdout.write('  ✓ Business Management')
        self.stdout.write('  ✓ Subscription Management')
        self.stdout.write('  ✓ System Configuration')
        self.stdout.write('  ✓ All Database Operations')
        self.stdout.write('='*60 + '\n')
