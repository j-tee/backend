from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import Role

User = get_user_model()


class Command(BaseCommand):
    help = 'Initialize default roles and create admin user'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--admin-email',
            type=str,
            default='admin@example.com',
            help='Admin user email address'
        )
        parser.add_argument(
            '--admin-password',
            type=str,
            default='admin123',
            help='Admin user password'
        )
    
    def handle(self, *args, **options):
        # Create default roles
        roles_data = [
            {'name': 'Admin', 'description': 'System administrator with full access'},
            {'name': 'Manager', 'description': 'Store manager with management privileges'},
            {'name': 'Cashier', 'description': 'Point of sale operator'},
            {'name': 'Warehouse Staff', 'description': 'Inventory and warehouse management'},
        ]
        
        created_roles = []
        for role_data in roles_data:
            role, created = Role.objects.get_or_create(
                name=role_data['name'],
                defaults={'description': role_data['description']}
            )
            if created:
                created_roles.append(role.name)
                self.stdout.write(
                    self.style.SUCCESS(f'Created role: {role.name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Role already exists: {role.name}')
                )
        
        # Create admin user
        admin_email = options['admin_email']
        admin_password = options['admin_password']
        
        try:
            admin_role = Role.objects.get(name='Admin')
            
            if not User.objects.filter(email=admin_email).exists():
                admin_user = User.objects.create_user(
                    email=admin_email,
                    password=admin_password,
                    name='System Administrator',
                    role=admin_role,
                    is_staff=True,
                    is_superuser=True,
                    subscription_status='Active'
                )
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Created admin user: {admin_email} with password: {admin_password}'
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Admin user already exists: {admin_email}')
                )
        
        except Role.DoesNotExist:
            self.stdout.write(
                self.style.ERROR('Admin role does not exist. Cannot create admin user.')
            )
        
        self.stdout.write(
            self.style.SUCCESS('Initialization completed successfully!')
        )