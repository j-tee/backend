"""
RBAC Serializers
Serializers for Role-Based Access Control models
"""

from rest_framework import serializers
from .models import Permission, Role, UserRole, User


class PermissionSerializer(serializers.ModelSerializer):
    """Serializer for Permission model"""
    
    class Meta:
        model = Permission
        fields = [
            'id', 'name', 'codename', 'description', 'category',
            'action', 'resource', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class RoleSerializer(serializers.ModelSerializer):
    """Serializer for Role model with permissions"""
    permissions = PermissionSerializer(many=True, read_only=True)
    permission_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Role
        fields = [
            'id', 'name', 'description', 'level', 'permissions',
            'permission_count', 'is_system_role', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'is_system_role']
    
    def get_permission_count(self, obj):
        return obj.permissions.count()


class RoleListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing roles"""
    permission_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Role
        fields = [
            'id', 'name', 'description', 'level', 'permission_count',
            'is_system_role', 'is_active'
        ]
    
    def get_permission_count(self, obj):
        return obj.permissions.count()


class CreateRoleSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating roles"""
    permission_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = Role
        fields = ['name', 'description', 'level', 'permission_ids', 'is_active']
    
    def create(self, validated_data):
        permission_ids = validated_data.pop('permission_ids', [])
        role = Role.objects.create(**validated_data)
        
        if permission_ids:
            permissions = Permission.objects.filter(id__in=permission_ids)
            role.permissions.set(permissions)
        
        return role
    
    def update(self, instance, validated_data):
        permission_ids = validated_data.pop('permission_ids', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if permission_ids is not None:
            permissions = Permission.objects.filter(id__in=permission_ids)
            instance.permissions.set(permissions)
        
        return instance


class AssignPermissionsSerializer(serializers.Serializer):
    """Serializer for assigning permissions to a role"""
    permission_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True
    )
    
    def validate_permission_ids(self, value):
        if not value:
            raise serializers.ValidationError("At least one permission ID is required")
        
        # Verify all permission IDs exist
        existing_perms = Permission.objects.filter(id__in=value)
        if existing_perms.count() != len(value):
            raise serializers.ValidationError("One or more invalid permission IDs")
        
        return value


class UserRoleSerializer(serializers.ModelSerializer):
    """Serializer for UserRole assignments"""
    role_details = RoleListSerializer(source='role', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    assigned_by_email = serializers.EmailField(source='assigned_by.email', read_only=True)
    
    class Meta:
        model = UserRole
        fields = [
            'id', 'user', 'user_email', 'role', 'role_details', 'scope',
            'business', 'storefront', 'assigned_by', 'assigned_by_email',
            'assigned_at', 'expires_at', 'is_active'
        ]
        read_only_fields = ['assigned_at', 'assigned_by']


class AssignUserRoleSerializer(serializers.ModelSerializer):
    """Serializer for assigning roles to users"""
    
    class Meta:
        model = UserRole
        fields = [
            'user_id', 'role_id', 'scope', 'business_id',
            'storefront_id', 'expires_at'
        ]
    
    user_id = serializers.IntegerField(write_only=True)
    role_id = serializers.IntegerField(write_only=True)
    business_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)
    storefront_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)
    
    def validate(self, data):
        # Validate user exists
        try:
            user = User.objects.get(id=data['user_id'])
        except User.DoesNotExist:
            raise serializers.ValidationError({'user_id': 'User not found'})
        
        # Validate role exists
        try:
            role = Role.objects.get(id=data['role_id'])
        except Role.DoesNotExist:
            raise serializers.ValidationError({'role_id': 'Role not found'})
        
        # Validate scope-specific requirements
        scope = data.get('scope')
        if scope == 'BUSINESS' and not data.get('business_id'):
            raise serializers.ValidationError({
                'business_id': 'Business ID is required for BUSINESS scope'
            })
        
        if scope == 'STOREFRONT' and not data.get('storefront_id'):
            raise serializers.ValidationError({
                'storefront_id': 'Storefront ID is required for STOREFRONT scope'
            })
        
        data['user'] = user
        data['role'] = role
        
        return data
    
    def create(self, validated_data):
        user = validated_data.pop('user')
        role = validated_data.pop('role')
        validated_data.pop('user_id', None)
        validated_data.pop('role_id', None)
        business_id = validated_data.pop('business_id', None)
        storefront_id = validated_data.pop('storefront_id', None)
        
        user_role = UserRole.objects.create(
            user=user,
            role=role,
            business_id=business_id,
            storefront_id=storefront_id,
            assigned_by=self.context['request'].user,
            **validated_data
        )
        
        return user_role


class UserWithRolesSerializer(serializers.ModelSerializer):
    """Serializer for User with all roles and permissions"""
    roles = RoleListSerializer(many=True, read_only=True)
    user_roles = UserRoleSerializer(many=True, read_only=True)
    all_permissions = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'platform_role',
            'roles', 'user_roles', 'all_permissions'
        ]
    
    def get_all_permissions(self, obj):
        permissions = obj.get_all_permissions()
        return PermissionSerializer(permissions, many=True).data
