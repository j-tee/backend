import logging
from typing import Sequence, Tuple

from django.apps import apps
from django.conf import settings
from django.db.models.signals import post_migrate, post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)

DEFAULT_ROLES: Sequence[Tuple[str, str]] = (
    ('Admin', 'Platform administrator with full access to all modules.'),
    ('Manager', 'Business manager with oversight permissions.'),
    ('Cashier', 'Point-of-sale cashier role with sales permissions.'),
    ('Warehouse Staff', 'Warehouse operator responsible for inventory handling.'),
)


def ensure_default_roles() -> bool:
    """Ensure baseline role records exist."""
    Role = apps.get_model('accounts', 'Role')
    created_any = False
    for name, description in DEFAULT_ROLES:
        _, created = Role.objects.get_or_create(
            name=name,
            defaults={'description': description},
        )
        created_any = created_any or created
    return created_any


def promote_platform_owner() -> bool:
    """Promote the configured platform owner to superuser status."""
    email = getattr(settings, 'PLATFORM_OWNER_EMAIL', '')
    if not email:
        return False

    Role = apps.get_model('accounts', 'Role')
    User = apps.get_model('accounts', 'User')

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        logger.warning(
            'PLATFORM_OWNER_EMAIL is set to %s, but no matching user was found.',
            email,
        )
        return False

    admin_role, _ = Role.objects.get_or_create(
        name='Admin',
        defaults={'description': 'Platform administrator with full permissions.'},
    )

    updated = False
    if user.role != admin_role:
        user.role = admin_role
        updated = True
    if not user.is_staff:
        user.is_staff = True
        updated = True
    if not user.is_superuser:
        user.is_superuser = True
        updated = True

    if updated:
        user.save()  # updated_at auto-handled by model
        logger.info('Promoted %s to platform superuser.', email)
    else:
        logger.debug('Platform owner %s already has superuser privileges.', email)

    return updated


@receiver(post_migrate)
def bootstrap_accounts(sender, **kwargs):
    """Seed default roles and promote platform owner after migrations."""
    if sender.name != 'accounts':
        return

    ensure_default_roles()
    promote_platform_owner()


@receiver(post_save, sender='accounts.Business')
def create_walk_in_customer(sender, instance, created, **kwargs):
    """Create default walk-in customer when a new business is registered."""
    if not created:
        return
    
    # Import here to avoid circular imports
    from sales.models import Customer
    
    WALK_IN_PHONE = '+233000000000'
    WALK_IN_NAME = 'Walk-In-Customer'
    
    try:
        Customer.objects.get_or_create(
            business=instance,
            phone=WALK_IN_PHONE,
            defaults={
                'name': WALK_IN_NAME,
                'customer_type': 'RETAIL',
                
                'created_by': None,  # System-created, no specific user
            }
        )
        logger.info(f'Created walk-in customer for business: {instance.name}')
    except Exception as e:
        logger.error(f'Failed to create walk-in customer for business {instance.name}: {e}')
