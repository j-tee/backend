"""
Unified Permission Service
==========================

This module consolidates permission checking from multiple sources into a single,
predictable system. It resolves conflicts between:
- Django-rules (rule-based permissions)
- Django Guardian (object-level permissions)
- Custom RBAC (role-based permissions)

Priority Order:
1. Explicit object-level DENY (Guardian) - Highest priority
2. Platform-level roles (SUPER_ADMIN) - Override all business permissions
3. Scope-based RBAC (custom roles + permissions) - Business/storefront context
4. Object-level GRANT (Guardian) - Specific object permissions
5. Default DENY - If none of the above match

Usage Examples:
    from accounts.permissions import UnifiedPermissionService
    
    # Check permission
    service = UnifiedPermissionService(user)
    can_edit = service.check('inventory.change_storefront', obj=storefront)
    
    # Get accessible objects
    storefronts = service.get_accessible_queryset(
        StoreFront.objects.all(),
        'inventory.view_storefront'
    )
"""

from typing import Optional, Any, List, Union
from django.db import models
from django.contrib.auth.models import AnonymousUser
from guardian.shortcuts import get_objects_for_user
import rules


class PermissionDenied(Exception):
    """Custom exception for permission denials with detailed messages"""
    def __init__(self, message: str, reason: str = None):
        self.message = message
        self.reason = reason
        super().__init__(self.message)


class UnifiedPermissionService:
    """
    Unified service for checking permissions across all systems.
    
    This service provides a single interface for permission checking that
    intelligently combines rules, Guardian, and custom RBAC.
    """
    
    def __init__(self, user):
        """
        Initialize permission service for a user.
        
        Args:
            user: User instance or AnonymousUser
        """
        self.user = user
        self._cache = {}  # Cache permission checks for performance
    
    def check(
        self, 
        permission: str, 
        obj: Optional[Any] = None,
        business: Optional[Any] = None,
        storefront: Optional[Any] = None,
        raise_exception: bool = False
    ) -> bool:
        """
        Check if user has a specific permission.
        
        Args:
            permission: Permission codename (e.g., 'inventory.change_storefront')
            obj: Optional object to check permission against
            business: Optional business context
            storefront: Optional storefront context
            raise_exception: If True, raise PermissionDenied instead of returning False
        
        Returns:
            bool: True if user has permission, False otherwise
        
        Raises:
            PermissionDenied: If raise_exception=True and permission denied
        
        Examples:
            >>> service = UnifiedPermissionService(user)
            >>> service.check('inventory.view_storefront', obj=storefront)
            True
            >>> service.check('inventory.delete_storefront', obj=storefront, raise_exception=True)
            PermissionDenied: You do not have permission to delete this storefront
        """
        # Anonymous users have no permissions
        if not self.user or not self.user.is_authenticated:
            if raise_exception:
                raise PermissionDenied("Authentication required")
            return False
        
        # Cache key for performance
        cache_key = f"{permission}:{id(obj)}:{id(business)}:{id(storefront)}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Check permission in priority order
        result = self._check_permission_hierarchy(permission, obj, business, storefront)
        
        # Cache result
        self._cache[cache_key] = result
        
        if not result and raise_exception:
            raise PermissionDenied(
                f"You do not have permission: {permission}",
                reason=self._get_denial_reason(permission, obj)
            )
        
        return result
    
    def _check_permission_hierarchy(
        self, 
        permission: str, 
        obj: Optional[Any],
        business: Optional[Any],
        storefront: Optional[Any]
    ) -> bool:
        """
        Check permission following priority hierarchy.
        
        Priority Order:
        1. Explicit object-level DENY (Guardian deny rules)
        2. Platform-level roles (SUPER_ADMIN, SAAS_ADMIN)
        3. Scope-based RBAC (Business/Storefront roles)
        4. Rule-based permissions (django-rules)
        5. Object-level GRANT (Guardian allow)
        6. Default DENY
        """
        # 1. Check for explicit denials (Guardian)
        if obj and self._check_explicit_denial(permission, obj):
            return False
        
        # 2. Platform-level permissions (SUPER_ADMIN overrides everything)
        if self._check_platform_permission(permission):
            return True
        
        # 3. RBAC permissions (custom roles + permissions)
        if self._check_rbac_permission(permission, business, storefront):
            return True
        
        # 4. Rule-based permissions (django-rules)
        if self._check_rules_permission(permission, obj):
            return True
        
        # 5. Object-level grants (Guardian)
        if obj and self._check_guardian_permission(permission, obj):
            return True
        
        # 6. Default deny
        return False
    
    def _check_explicit_denial(self, permission: str, obj: Any) -> bool:
        """
        Check for explicit denial in Guardian.
        
        This allows administrators to explicitly deny permissions even when
        they would normally be granted through roles.
        
        Note: Guardian doesn't have built-in deny rules by default.
        This can be implemented using a custom DenialRecord model if needed.
        """
        # TODO: Implement explicit denial system if needed
        # For now, no explicit denials exist
        return False
    
    def _check_platform_permission(self, permission: str) -> bool:
        """
        Check platform-level permissions.
        
        Platform roles (SUPER_ADMIN, SAAS_ADMIN) override business permissions.
        """
        # Superuser has all permissions
        if self.user.is_superuser:
            return True
        
        # SUPER_ADMIN has all permissions
        if hasattr(self.user, 'platform_role'):
            if self.user.platform_role == 'SUPER_ADMIN':
                return True
            
            # SAAS_ADMIN has view/change permissions but not delete
            if self.user.platform_role == 'SAAS_ADMIN':
                # Allow most operations except deletion
                if not permission.endswith('.delete'):
                    return True
        
        return False
    
    def _check_rbac_permission(
        self, 
        permission: str, 
        business: Optional[Any],
        storefront: Optional[Any]
    ) -> bool:
        """
        Check RBAC permissions through user roles.
        
        This checks the custom Permission and Role system.
        """
        if not hasattr(self.user, 'has_permission'):
            return False
        
        # Extract permission codename (handle both 'app.perm' and 'perm' formats)
        if '.' in permission:
            app_label, codename = permission.split('.', 1)
        else:
            codename = permission
        
        return self.user.has_permission(codename, business, storefront)
    
    def _check_rules_permission(self, permission: str, obj: Optional[Any]) -> bool:
        """
        Check django-rules permissions.
        
        Rules provide declarative permission definitions using predicates.
        """
        try:
            return rules.has_perm(permission, self.user, obj)
        except Exception:
            # If rule doesn't exist or error occurs, fall through
            return False
    
    def _check_guardian_permission(self, permission: str, obj: Any) -> bool:
        """
        Check Guardian object-level permissions.
        
        Guardian allows granting permissions to specific objects.
        """
        try:
            return self.user.has_perm(permission, obj)
        except Exception:
            return False
    
    def _get_denial_reason(self, permission: str, obj: Optional[Any]) -> str:
        """Get human-readable reason for permission denial"""
        if not self.user.is_authenticated:
            return "You must be logged in"
        
        if obj:
            return f"You do not have '{permission}' permission for this specific object"
        
        return f"You do not have the required role or permission: {permission}"
    
    def get_accessible_queryset(
        self,
        queryset: models.QuerySet,
        permission: str,
        use_guardian: bool = True
    ) -> models.QuerySet:
        """
        Filter queryset to only objects user has permission to access.
        
        Args:
            queryset: Base queryset to filter
            permission: Permission to check (e.g., 'inventory.view_storefront')
            use_guardian: Whether to include Guardian object-level permissions
        
        Returns:
            Filtered queryset
        
        Examples:
            >>> service = UnifiedPermissionService(user)
            >>> storefronts = service.get_accessible_queryset(
            ...     StoreFront.objects.all(),
            ...     'inventory.view_storefront'
            ... )
        """
        # Anonymous users get empty queryset
        if not self.user or not self.user.is_authenticated:
            return queryset.none()
        
        # Platform admins see everything
        if self._check_platform_permission(permission):
            return queryset
        
        # Get objects through Guardian if enabled
        if use_guardian:
            try:
                guardian_objects = get_objects_for_user(
                    self.user,
                    permission,
                    queryset.model
                )
                # Combine with business-scoped objects
                business_filtered = self._filter_by_business_access(queryset)
                return (guardian_objects | business_filtered).distinct()
            except Exception:
                pass
        
        # Fall back to business-based filtering
        return self._filter_by_business_access(queryset)
    
    def _filter_by_business_access(self, queryset: models.QuerySet) -> models.QuerySet:
        """
        Filter queryset based on user's business memberships.
        
        This is a fallback when Guardian isn't available or applicable.
        """
        from accounts.models import BusinessMembership
        
        # Get businesses user has access to
        business_ids = BusinessMembership.objects.filter(
            user=self.user,
            is_active=True
        ).values_list('business_id', flat=True)
        
        if not business_ids:
            return queryset.none()
        
        # Try to filter by business (most models have a business field)
        model = queryset.model
        
        # Direct business field
        if hasattr(model, 'business'):
            return queryset.filter(business_id__in=business_ids)
        
        # Business through link (StoreFront, Warehouse)
        if hasattr(model, 'business_link'):
            return queryset.filter(business_link__business_id__in=business_ids)
        
        # If we can't filter, return empty (safe default)
        return queryset.none()
    
    def check_business_access(self, business) -> bool:
        """
        Check if user has any access to a business.
        
        Args:
            business: Business instance or ID
        
        Returns:
            bool: True if user is a member of the business
        """
        from accounts.models import BusinessMembership
        
        if not self.user or not self.user.is_authenticated:
            return False
        
        if self._check_platform_permission('accounts.view_business'):
            return True
        
        return BusinessMembership.objects.filter(
            user=self.user,
            business=business,
            is_active=True
        ).exists()
    
    def get_user_role_in_business(self, business) -> Optional[str]:
        """
        Get user's role within a specific business.
        
        Args:
            business: Business instance or ID
        
        Returns:
            str: Role name (e.g., 'OWNER', 'ADMIN', 'MANAGER') or None
        """
        from accounts.models import BusinessMembership
        
        if not self.user or not self.user.is_authenticated:
            return None
        
        membership = BusinessMembership.objects.filter(
            user=self.user,
            business=business,
            is_active=True
        ).first()
        
        return membership.role if membership else None
    
    def clear_cache(self):
        """Clear permission cache (call after role changes)"""
        self._cache.clear()


# Convenience functions for common operations
def check_permission(
    user,
    permission: str,
    obj: Optional[Any] = None,
    raise_exception: bool = False
) -> bool:
    """
    Quick permission check without creating service instance.
    
    Args:
        user: User instance
        permission: Permission codename
        obj: Optional object to check against
        raise_exception: Raise PermissionDenied if False
    
    Returns:
        bool: True if user has permission
    
    Examples:
        >>> from accounts.permissions import check_permission
        >>> if check_permission(request.user, 'inventory.change_storefront', storefront):
        ...     storefront.save()
    """
    service = UnifiedPermissionService(user)
    return service.check(permission, obj=obj, raise_exception=raise_exception)


def filter_accessible(user, queryset: models.QuerySet, permission: str) -> models.QuerySet:
    """
    Filter queryset to accessible objects.
    
    Args:
        user: User instance
        queryset: Base queryset
        permission: Permission to check
    
    Returns:
        Filtered queryset
    
    Examples:
        >>> from accounts.permissions import filter_accessible
        >>> storefronts = filter_accessible(
        ...     request.user,
        ...     StoreFront.objects.all(),
        ...     'inventory.view_storefront'
        ... )
    """
    service = UnifiedPermissionService(user)
    return service.get_accessible_queryset(queryset, permission)


def require_permission(permission: str, obj_param: str = None):
    """
    Decorator for view methods to enforce permissions.
    
    Args:
        permission: Permission codename
        obj_param: Name of parameter containing object to check
    
    Examples:
        class StoreFrontViewSet(viewsets.ModelViewSet):
            @require_permission('inventory.change_storefront', obj_param='instance')
            def perform_update(self, instance):
                super().perform_update(instance)
    """
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            user = getattr(self.request if hasattr(self, 'request') else self, 'user', None)
            
            if not user:
                raise PermissionDenied("No user found in request")
            
            # Get object if specified
            obj = kwargs.get(obj_param) if obj_param else None
            
            # Check permission
            service = UnifiedPermissionService(user)
            service.check(permission, obj=obj, raise_exception=True)
            
            return func(self, *args, **kwargs)
        return wrapper
    return decorator


# DRF Permission Classes
from rest_framework import permissions as drf_permissions


class UnifiedObjectPermission(drf_permissions.BasePermission):
    """
    DRF permission class using unified permission service.
    
    Usage:
        class StoreFrontViewSet(viewsets.ModelViewSet):
            permission_classes = [UnifiedObjectPermission]
            
            def get_permissions_required(self, action):
                '''Override to specify permissions per action'''
                return {
                    'list': ['inventory.view_storefront'],
                    'retrieve': ['inventory.view_storefront'],
                    'create': ['inventory.add_storefront'],
                    'update': ['inventory.change_storefront'],
                    'destroy': ['inventory.delete_storefront'],
                }.get(action, [])
    """
    
    def has_permission(self, request, view):
        """Check if user has permission for this action"""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Get required permissions from view
        if hasattr(view, 'get_permissions_required'):
            required_perms = view.get_permissions_required(view.action)
        else:
            # Default mapping
            action_map = {
                'list': 'view',
                'retrieve': 'view',
                'create': 'add',
                'update': 'change',
                'partial_update': 'change',
                'destroy': 'delete',
            }
            action = action_map.get(view.action, 'view')
            
            # Get model permission
            model = view.queryset.model if hasattr(view, 'queryset') else None
            if not model:
                return False
            
            app_label = model._meta.app_label
            model_name = model._meta.model_name
            required_perms = [f'{app_label}.{action}_{model_name}']
        
        # Check all required permissions
        service = UnifiedPermissionService(request.user)
        for perm in required_perms:
            if not service.check(perm):
                return False
        
        return True
    
    def has_object_permission(self, request, view, obj):
        """Check if user has permission for this specific object"""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Get permission for this action
        action_map = {
            'retrieve': 'view',
            'update': 'change',
            'partial_update': 'change',
            'destroy': 'delete',
        }
        action = action_map.get(view.action, 'view')
        
        # Build permission string
        app_label = obj._meta.app_label
        model_name = obj._meta.model_name
        permission = f'{app_label}.{action}_{model_name}'
        
        # Check permission
        service = UnifiedPermissionService(request.user)
        return service.check(permission, obj=obj)
