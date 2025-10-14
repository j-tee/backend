"""
RBAC URLs
URL patterns for RBAC API endpoints
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .rbac_views import (
    PermissionViewSet,
    RoleViewSet,
    UserRoleViewSet,
    UserWithRolesViewSet
)

router = DefaultRouter()
router.register(r'rbac/permissions', PermissionViewSet, basename='rbac-permission')
router.register(r'rbac/roles', RoleViewSet, basename='rbac-role')
router.register(r'rbac/user-roles', UserRoleViewSet, basename='rbac-user-role')
router.register(r'rbac/users', UserWithRolesViewSet, basename='rbac-user-with-roles')

urlpatterns = router.urls
