from django.core.management.base import BaseCommand
from accounts.models import Permission, Role, RoleTemplate


class Command(BaseCommand):
    help = 'Seed RBAC permissions and roles'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('🌱 Seeding RBAC System...'))
        self.stdout.write('=' * 60)
        
        # Create Permissions
        self.stdout.write('\n📋 Creating Permissions...')
        permissions_data = [
            # SALES
            {'name': 'Create Sales', 'codename': 'can_create_sales', 'category': 'SALES', 
             'action': 'CREATE', 'resource': 'sale'},
            {'name': 'View Sales', 'codename': 'can_view_sales', 'category': 'SALES', 
             'action': 'READ', 'resource': 'sale'},
            {'name': 'Approve Sales', 'codename': 'can_approve_sales', 'category': 'SALES', 
             'action': 'APPROVE', 'resource': 'sale'},
            {'name': 'Delete Sales', 'codename': 'can_delete_sales', 'category': 'SALES', 
             'action': 'DELETE', 'resource': 'sale'},
            
            # INVENTORY
            {'name': 'Manage Products', 'codename': 'can_manage_products', 'category': 'INVENTORY', 
             'action': 'MANAGE', 'resource': 'product'},
            {'name': 'View Inventory', 'codename': 'can_view_inventory', 'category': 'INVENTORY', 
             'action': 'READ', 'resource': 'inventory'},
            {'name': 'Update Stock', 'codename': 'can_update_stock', 'category': 'INVENTORY', 
             'action': 'UPDATE', 'resource': 'stock'},
            {'name': 'View Products', 'codename': 'can_view_products', 'category': 'INVENTORY', 
             'action': 'READ', 'resource': 'product'},
            
            # CUSTOMERS
            {'name': 'Manage Customers', 'codename': 'can_manage_customers', 'category': 'CUSTOMERS', 
             'action': 'MANAGE', 'resource': 'customer'},
            {'name': 'View Customers', 'codename': 'can_view_customers', 'category': 'CUSTOMERS', 
             'action': 'READ', 'resource': 'customer'},
            
            # REPORTS
            {'name': 'View Reports', 'codename': 'can_view_reports', 'category': 'REPORTS', 
             'action': 'READ', 'resource': 'report'},
            {'name': 'Export Reports', 'codename': 'can_export_reports', 'category': 'REPORTS', 
             'action': 'EXPORT', 'resource': 'report'},
            
            # USERS
            {'name': 'Manage Users', 'codename': 'can_manage_users', 'category': 'USERS', 
             'action': 'MANAGE', 'resource': 'user'},
            {'name': 'Invite Users', 'codename': 'can_invite_users', 'category': 'USERS', 
             'action': 'CREATE', 'resource': 'user'},
            
            # SETTINGS
            {'name': 'Manage Settings', 'codename': 'can_manage_settings', 'category': 'SETTINGS', 
             'action': 'MANAGE', 'resource': 'settings'},
            
            # PLATFORM
            {'name': 'Manage Platform', 'codename': 'can_manage_platform', 'category': 'PLATFORM', 
             'action': 'MANAGE', 'resource': 'platform'},
            {'name': 'Manage Subscriptions', 'codename': 'can_manage_subscriptions', 'category': 'PLATFORM', 
             'action': 'MANAGE', 'resource': 'subscription'},
            {'name': 'View Platform Stats', 'codename': 'can_view_platform_stats', 'category': 'PLATFORM', 
             'action': 'READ', 'resource': 'platform_stats'},
            {'name': 'Manage Plans', 'codename': 'can_manage_plans', 'category': 'PLATFORM', 
             'action': 'MANAGE', 'resource': 'plan'},
            
            # FINANCE
            {'name': 'View Financial Data', 'codename': 'can_view_financial_data', 'category': 'FINANCE', 
             'action': 'READ', 'resource': 'financial'},
            {'name': 'Manage Payments', 'codename': 'can_manage_payments', 'category': 'FINANCE', 
             'action': 'MANAGE', 'resource': 'payment'},
        ]
        
        created_count = 0
        for perm_data in permissions_data:
            perm, created = Permission.objects.get_or_create(
                codename=perm_data['codename'],
                defaults={
                    'name': perm_data['name'],
                    'category': perm_data['category'],
                    'action': perm_data['action'],
                    'resource': perm_data['resource'],
                    'description': f"{perm_data['action']} permission for {perm_data['resource']}"
                }
            )
            if created:
                created_count += 1
                self.stdout.write(f"  ✅ Created: {perm.name}")
        
        self.stdout.write(self.style.SUCCESS(f'\n✓ {created_count} permissions created, {len(permissions_data) - created_count} already existed'))
        
        # Create Role Templates
        self.stdout.write('\n👥 Creating Role Templates...')
        role_templates = [
            {
                'name': 'SUPER_USER',
                'description': 'Platform super administrator with full system access',
                'level': 'PLATFORM',
                'permission_codenames': [p['codename'] for p in permissions_data],  # All permissions
            },
            {
                'name': 'OWNER',
                'description': 'Business owner with full business access',
                'level': 'BUSINESS',
                'permission_codenames': [
                    'can_create_sales', 'can_view_sales', 'can_approve_sales', 'can_delete_sales',
                    'can_manage_products', 'can_view_inventory', 'can_update_stock', 'can_view_products',
                    'can_manage_customers', 'can_view_customers',
                    'can_view_reports', 'can_export_reports',
                    'can_manage_users', 'can_invite_users',
                    'can_manage_settings',
                    'can_view_financial_data', 'can_manage_payments',
                ],
            },
            {
                'name': 'Admin',
                'description': 'Business administrator with full access to business modules',
                'level': 'BUSINESS',
                'permission_codenames': [
                    'can_create_sales', 'can_view_sales', 'can_approve_sales', 'can_delete_sales',
                    'can_manage_products', 'can_view_inventory', 'can_update_stock', 'can_view_products',
                    'can_manage_customers', 'can_view_customers',
                    'can_view_reports', 'can_export_reports',
                    'can_manage_users', 'can_invite_users',
                    'can_manage_settings',
                    'can_view_financial_data', 'can_manage_payments',
                ],
            },
            {
                'name': 'Manager',
                'description': 'Business manager with oversight permissions',
                'level': 'BUSINESS',
                'permission_codenames': [
                    'can_create_sales', 'can_view_sales', 'can_approve_sales',
                    'can_view_inventory', 'can_update_stock', 'can_view_products',
                    'can_view_customers',
                    'can_view_reports', 'can_export_reports',
                    'can_view_financial_data',
                ],
            },
            {
                'name': 'Cashier',
                'description': 'Point-of-sale cashier role with sales permissions',
                'level': 'STOREFRONT',
                'permission_codenames': [
                    'can_create_sales', 'can_view_sales',
                    'can_view_inventory', 'can_view_products',
                    'can_view_customers',
                ],
            },
            {
                'name': 'Warehouse Staff',
                'description': 'Warehouse operator responsible for inventory handling',
                'level': 'BUSINESS',
                'permission_codenames': [
                    'can_view_inventory', 'can_update_stock', 'can_view_products',
                ],
            },
        ]
        
        roles_created = 0
        for template_data in role_templates:
            template, created = RoleTemplate.objects.get_or_create(
                name=template_data['name'],
                defaults={
                    'description': template_data['description'],
                    'level': template_data['level'],
                    'permission_codenames': template_data['permission_codenames'],
                }
            )
            
            # Create actual role from template
            role = template.create_role()
            if created:
                roles_created += 1
                self.stdout.write(f"  ✅ Created role: {role.name} with {role.permissions.count()} permissions")
            else:
                # Update permissions for existing role
                role.permissions.clear()
                for codename in template_data['permission_codenames']:
                    try:
                        permission = Permission.objects.get(codename=codename)
                        role.permissions.add(permission)
                    except Permission.DoesNotExist:
                        pass
                self.stdout.write(f"  ♻️  Updated role: {role.name} with {role.permissions.count()} permissions")
        
        self.stdout.write(self.style.SUCCESS(f'\n✓ {roles_created} roles created, {len(role_templates) - roles_created} updated'))
        
        # Summary
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('✅ RBAC System Seeded Successfully!'))
        self.stdout.write('\n📊 Summary:')
        self.stdout.write(f'  Permissions: {Permission.objects.count()}')
        self.stdout.write(f'  Roles: {Role.objects.count()}')
        self.stdout.write(f'  Role Templates: {RoleTemplate.objects.count()}')
        
        self.stdout.write('\n🎯 Available Roles:')
        for role in Role.objects.all().order_by('level', 'name'):
            self.stdout.write(f'  - {role.name} ({role.level}): {role.permissions.count()} permissions')
        
        self.stdout.write('\n' + '=' * 60)
