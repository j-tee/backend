"""Centralized role-based access control definitions using django-rules."""

from __future__ import annotations

import rules

from django.db.models import Model

from accounts.models import User, BusinessMembership, Business


def _get_business_from_object(obj: Model | None) -> Business | None:
    """Return the related business for supported inventory/account objects."""
    if obj is None:
        return None

    if isinstance(obj, Business):
        return obj

    if isinstance(obj, BusinessMembership):
        return obj.business

    from accounts.models import BusinessInvitation  # Local import to avoid cycles
    if isinstance(obj, BusinessInvitation):
        return obj.business

    try:
        from inventory.models import (
            StoreFront,
            BusinessStoreFront,
            StoreFrontEmployee,
            Warehouse,
            BusinessWarehouse,
            WarehouseEmployee,
            Inventory,
            StoreFrontInventory,
            Transfer,
            TransferLineItem,
            TransferAuditEntry,
        )
    except Exception:  # pragma: no cover - during migrations inventory may be unavailable
        return None

    if isinstance(obj, BusinessStoreFront):
        return obj.business

    if isinstance(obj, StoreFrontEmployee):
        return obj.business

    if isinstance(obj, WarehouseEmployee):
        return obj.business

    if isinstance(obj, BusinessWarehouse):
        return obj.business

    if isinstance(obj, StoreFront):
        link = getattr(obj, 'business_link', None)
        if link:
            return link.business
        return None

    if isinstance(obj, Warehouse):
        link = getattr(obj, 'business_link', None)
        if link:
            return link.business
        return None

    if isinstance(obj, Inventory):
        warehouse = getattr(obj, 'warehouse', None)
        if warehouse:
            return _get_business_from_object(warehouse)
        return None

    if isinstance(obj, Transfer):
        if obj.business_id:
            return obj.business
        storefront = getattr(obj, 'destination_storefront', None)
        if storefront:
            return _get_business_from_object(storefront)
        warehouse = getattr(obj, 'source_warehouse', None)
        if warehouse:
            return _get_business_from_object(warehouse)
        return None

    if isinstance(obj, TransferLineItem):
        return _get_business_from_object(getattr(obj, 'transfer', None))

    if isinstance(obj, TransferAuditEntry):
        return _get_business_from_object(getattr(obj, 'transfer', None))

    if isinstance(obj, StoreFrontInventory):
        return _get_business_from_object(getattr(obj, 'storefront', None))

    return None


def _user_has_business_role(user: User, role: str, business: Business | None = None) -> bool:
    if not user.is_authenticated:
        return False
    memberships = BusinessMembership.objects.filter(user=user, is_active=True, role=role)
    if business is not None:
        memberships = memberships.filter(business=business)
    return memberships.exists()


@rules.predicate
def is_authenticated(user: User):  # pragma: no cover - thin wrapper
    return user.is_authenticated


@rules.predicate
def is_super_admin(user: User):
    return user.is_authenticated and user.is_platform_super_admin


@rules.predicate
def is_saas_admin(user: User):
    return user.is_authenticated and user.has_platform_role(User.PLATFORM_SAAS_ADMIN)


@rules.predicate
def is_saas_staff(user: User):
    return user.is_authenticated and user.has_platform_role(User.PLATFORM_SAAS_STAFF)


@rules.predicate
def is_business_owner(user: User, obj=None):
    business = _get_business_from_object(obj)
    return _user_has_business_role(user, BusinessMembership.OWNER, business)


@rules.predicate
def is_business_admin(user: User, obj=None):
    business = _get_business_from_object(obj)
    return _user_has_business_role(user, BusinessMembership.ADMIN, business)


@rules.predicate
def is_business_manager(user: User, obj=None):
    business = _get_business_from_object(obj)
    return _user_has_business_role(user, BusinessMembership.MANAGER, business)


@rules.predicate
def is_business_staff(user: User, obj=None):
    business = _get_business_from_object(obj)
    return _user_has_business_role(user, BusinessMembership.STAFF, business)


@rules.predicate
def is_business_member(user: User, obj=None):
    business = _get_business_from_object(obj)
    qs = BusinessMembership.objects.filter(user=user, is_active=True)
    if business is not None:
        qs = qs.filter(business=business)
    return qs.exists()


@rules.predicate
def manages_storefront(user: User, obj=None):
    if not user.is_authenticated:
        return False
    try:
        from inventory.models import StoreFront, StoreFrontEmployee
    except Exception:  # pragma: no cover
        return False

    if not isinstance(obj, StoreFront):
        return False

    return StoreFrontEmployee.objects.filter(
        storefront=obj,
        user=user,
        is_active=True,
    ).exists()


@rules.predicate
def manages_warehouse(user: User, obj=None):
    if not user.is_authenticated:
        return False
    try:
        from inventory.models import Warehouse, WarehouseEmployee
    except Exception:  # pragma: no cover
        return False

    if not isinstance(obj, Warehouse):
        return False

    return WarehouseEmployee.objects.filter(
        warehouse=obj,
        user=user,
        is_active=True,
    ).exists()


# View permissions ---------------------------------------------------------

rules.add_perm(
    'inventory.view_storefront',
    is_super_admin | is_saas_admin | is_saas_staff | is_business_member,
)

rules.add_perm(
    'inventory.add_storefront',
    is_super_admin | is_saas_admin | is_business_owner | is_business_admin,
)

rules.add_perm(
    'inventory.change_storefront',
    is_super_admin | is_saas_admin | is_business_owner | is_business_admin | manages_storefront,
)

rules.add_perm(
    'inventory.delete_storefront',
    is_super_admin | is_saas_admin | is_business_owner | is_business_admin,
)

rules.add_perm(
    'inventory.view_storefrontemployee',
    is_super_admin | is_saas_admin | is_saas_staff | is_business_owner | is_business_admin | is_business_manager,
)

rules.add_perm(
    'inventory.add_storefrontemployee',
    is_super_admin | is_saas_admin | is_business_owner | is_business_admin | is_business_manager,
)

rules.add_perm(
    'inventory.change_storefrontemployee',
    is_super_admin | is_saas_admin | is_business_owner | is_business_admin | is_business_manager,
)

rules.add_perm(
    'inventory.delete_storefrontemployee',
    is_super_admin | is_saas_admin | is_business_owner | is_business_admin,
)

rules.add_perm(
    'inventory.view_warehouse',
    is_super_admin | is_saas_admin | is_saas_staff | is_business_member,
)

rules.add_perm(
    'inventory.add_warehouse',
    is_super_admin | is_saas_admin | is_business_owner | is_business_admin,
)

rules.add_perm(
    'inventory.change_warehouse',
    is_super_admin | is_saas_admin | is_business_owner | is_business_admin | manages_warehouse,
)

rules.add_perm(
    'inventory.delete_warehouse',
    is_super_admin | is_saas_admin | is_business_owner | is_business_admin,
)

TRANSFER_VIEWERS = is_super_admin | is_saas_admin | is_saas_staff | is_business_member
TRANSFER_CREATORS = is_super_admin | is_saas_admin | is_business_owner | is_business_admin | is_business_manager | is_business_staff
TRANSFER_APPROVERS = is_super_admin | is_saas_admin | is_business_owner | is_business_admin | is_business_manager

rules.add_perm('inventory.view_transfer', TRANSFER_VIEWERS)
rules.add_perm('inventory.add_transfer', TRANSFER_CREATORS)
rules.add_perm('inventory.change_transfer', TRANSFER_APPROVERS)
rules.add_perm('inventory.delete_transfer', TRANSFER_APPROVERS)

# Business invitation / membership management -----------------------------

BUSINESS_INVITATION_MANAGERS = is_super_admin | is_saas_admin | is_business_owner | is_business_admin
BUSINESS_INVITATION_VIEWERS = BUSINESS_INVITATION_MANAGERS | is_saas_staff

rules.add_perm('accounts.view_business_invitations', BUSINESS_INVITATION_VIEWERS)
rules.add_perm('accounts.manage_business_invitations', BUSINESS_INVITATION_MANAGERS)

BUSINESS_MEMBERSHIP_MANAGERS = is_super_admin | is_saas_admin | is_business_owner | is_business_admin
BUSINESS_MEMBERSHIP_VIEWERS = BUSINESS_MEMBERSHIP_MANAGERS | is_saas_staff | is_business_manager

rules.add_perm('accounts.view_business_memberships', BUSINESS_MEMBERSHIP_VIEWERS)
rules.add_perm('accounts.manage_business_memberships', BUSINESS_MEMBERSHIP_MANAGERS)
rules.add_perm('accounts.assign_storefronts', BUSINESS_MEMBERSHIP_MANAGERS)
rules.add_perm('accounts.assign_platform_roles', is_super_admin)