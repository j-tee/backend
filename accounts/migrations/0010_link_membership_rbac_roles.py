# Generated manually to link existing BusinessMemberships to RBAC roles

from django.db import migrations


def link_membership_roles(apps, schema_editor):
    """Link existing BusinessMemberships to their corresponding RBAC roles."""
    BusinessMembership = apps.get_model('accounts', 'BusinessMembership')
    Role = apps.get_model('accounts', 'Role')
    
    # Role mapping from BusinessMembership.role to RBAC Role.name
    role_mapping = {
        'OWNER': 'OWNER',
        'ADMIN': 'Admin',
        'MANAGER': 'Manager',
        'STAFF': 'Cashier',
    }
    
    updated_count = 0
    for membership in BusinessMembership.objects.all():
        role_name = role_mapping.get(membership.role)
        if role_name:
            try:
                role = Role.objects.get(name=role_name)
                membership.rbac_role = role
                membership.save(update_fields=['rbac_role'])
                updated_count += 1
            except Role.DoesNotExist:
                print(f"Warning: Role '{role_name}' not found for membership {membership.id}")
    
    print(f"✅ Linked {updated_count} memberships to RBAC roles")


def reverse_link(apps, schema_editor):
    """Remove RBAC role links."""
    BusinessMembership = apps.get_model('accounts', 'BusinessMembership')
    BusinessMembership.objects.all().update(rbac_role=None)


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0009_add_rbac_role_to_membership'),
    ]

    operations = [
        migrations.RunPython(link_membership_roles, reverse_link),
    ]
