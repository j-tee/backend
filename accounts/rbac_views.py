"""
RBAC Views (Updated)
API views for Role-Based Access Control management with pagination
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404

from .models import Permission, Role, UserRole, User
from .rbac_serializers import (
    PermissionSerializer,
    RoleSerializer,
    RoleListSerializer,
    CreateRoleSerializer,
    AssignPermissionsSerializer,
    UserRoleSerializer,
    AssignUserRoleSerializer,
    UserWithRolesSerializer
)


class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination configuration"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class IsSuperAdmin(IsAuthenticated):
    """Permission class for super admin only"""
    
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        
        user = request.user
        # Check if user has SUPER_USER role
        return user.has_role_new('SUPER_USER')


class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing permissions
    Read-only - permissions are managed in code/migrations
    """
    queryset = Permission.objects.filter(is_active=True)
    serializer_class = PermissionSerializer
    permission_classes = [IsSuperAdmin]
    pagination_class = StandardResultsSetPagination
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by category
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        # Filter by action
        action = self.request.query_params.get('action')
        if action:
            queryset = queryset.filter(action=action)
        
        return queryset.order_by('category', 'name')


class RoleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing roles
    """
    queryset = Role.objects.all()
    permission_classes = [IsSuperAdmin]
    pagination_class = StandardResultsSetPagination
    
    def get_serializer_class(self):
        if self.action == 'list':
            return RoleListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return CreateRoleSerializer
        return RoleSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by level
        level = self.request.query_params.get('level')
        if level:
            queryset = queryset.filter(level=level)
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset.order_by('level', 'name')
    
    def destroy(self, request, *args, **kwargs):
        """Prevent deletion of system roles"""
        role = self.get_object()
        
        if role.is_system_role:
            return Response(
                {'error': 'System roles cannot be deleted'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return super().destroy(request, *args, **kwargs)
    
    @action(detail=True, methods=['post'])
    def permissions(self, request, pk=None):
        """Assign permissions to a role"""
        role = self.get_object()
        serializer = AssignPermissionsSerializer(data=request.data)
        
        if serializer.is_valid():
            permission_ids = serializer.validated_data['permission_ids']
            permissions = Permission.objects.filter(id__in=permission_ids)
            role.permissions.set(permissions)
            
            # Return updated role
            role_serializer = RoleSerializer(role)
            return Response(role_serializer.data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserRoleViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing user role assignments
    """
    queryset = UserRole.objects.all()
    permission_classes = [IsSuperAdmin]
    pagination_class = StandardResultsSetPagination
    
    def get_serializer_class(self):
        if self.action == 'create':
            return AssignUserRoleSerializer
        return UserRoleSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by user
        user_id = self.request.query_params.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        # Filter by role
        role_id = self.request.query_params.get('role_id')
        if role_id:
            queryset = queryset.filter(role_id=role_id)
        
        # Filter by scope
        scope = self.request.query_params.get('scope')
        if scope:
            queryset = queryset.filter(scope=scope)
        
        # Filter active only
        active_only = self.request.query_params.get('active_only')
        if active_only and active_only.lower() == 'true':
            queryset = queryset.filter(is_active=True)
        
        return queryset.select_related('user', 'role', 'assigned_by').order_by('-assigned_at')
    
    def perform_create(self, serializer):
        """Set assigned_by to current user"""
        serializer.save()


class UserWithRolesViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing users with their roles and permissions
    """
    queryset = User.objects.all()
    serializer_class = UserWithRolesSerializer
    permission_classes = [IsSuperAdmin]
    pagination_class = StandardResultsSetPagination
    
    @action(detail=True, methods=['get'])
    def roles(self, request, pk=None):
        """Get all roles for a specific user"""
        user = self.get_object()
        user_roles = UserRole.objects.filter(user=user, is_active=True)
        serializer = UserRoleSerializer(user_roles, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def permissions(self, request, pk=None):
        """Get all permissions for a specific user (across all roles)"""
        user = self.get_object()
        permissions = user.get_all_permissions()
        serializer = PermissionSerializer(permissions, many=True)
        return Response({'permissions': serializer.data})
