from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import (
    Role,
    User,
    UserRole,
    UserProfile,
    AuditLog,
    Business,
    BusinessMembership,
    BusinessInvitation,
    EmailVerificationToken,
    Permission,
    RoleTemplate,
)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'level', 'description', 'is_system_role', 'is_active', 'created_at']
    list_filter = ['level', 'is_system_role', 'is_active']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']
    filter_horizontal = ['permissions']
    ordering = ['level', 'name']
    
    fieldsets = (
        (None, {'fields': ('name', 'description', 'level')}),
        ('Permissions', {'fields': ('permissions',)}),
        ('Status', {'fields': ('is_system_role', 'is_active')}),
        ('Metadata', {'fields': ('id', 'created_at', 'updated_at')}),
    )


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ['name', 'codename', 'category', 'action', 'resource', 'is_active']
    list_filter = ['category', 'action', 'is_active']
    search_fields = ['name', 'codename', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['category', 'resource', 'action']
    
    fieldsets = (
        (None, {'fields': ('name', 'codename', 'description')}),
        ('Classification', {'fields': ('category', 'action', 'resource')}),
        ('Status', {'fields': ('is_active',)}),
        ('Metadata', {'fields': ('id', 'created_at', 'updated_at')}),
    )


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'scope', 'business', 'storefront', 'is_active', 'assigned_at', 'expires_at']
    list_filter = ['scope', 'is_active', 'role__name', 'assigned_at']
    search_fields = ['user__email', 'user__name', 'role__name', 'business__name']
    readonly_fields = ['id', 'assigned_at', 'is_expired']
    autocomplete_fields = ['user', 'role', 'business', 'storefront', 'assigned_by']
    ordering = ['-assigned_at']
    
    fieldsets = (
        (None, {'fields': ('user', 'role')}),
        ('Scope', {'fields': ('scope', 'business', 'storefront')}),
        ('Status', {'fields': ('is_active', 'assigned_at', 'expires_at', 'is_expired')}),
        ('Assignment', {'fields': ('assigned_by',)}),
        ('Metadata', {'fields': ('id',)}),
    )
    
    def is_expired(self, obj):
        return obj.is_expired
    is_expired.boolean = True
    is_expired.short_description = 'Expired'


@admin.register(RoleTemplate)
class RoleTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'level', 'is_active', 'created_at']
    list_filter = ['level', 'is_active']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['name']
    
    fieldsets = (
        (None, {'fields': ('name', 'description', 'level')}),
        ('Permissions', {'fields': ('permission_codenames',)}),
        ('Status', {'fields': ('is_active',)}),
        ('Metadata', {'fields': ('id', 'created_at', 'updated_at')}),
    )
    
    actions = ['create_roles_from_templates']
    
    def create_roles_from_templates(self, request, queryset):
        """Action to create roles from selected templates"""
        created = 0
        for template in queryset:
            role = template.create_role()
            created += 1
        self.message_user(request, f"Successfully created {created} roles from templates.")
    create_roles_from_templates.short_description = "Create roles from selected templates"


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]
    list_display = ['name', 'email', 'role', 'account_type', 'platform_role', 'is_active', 'created_at']
    list_filter = ['role', 'account_type', 'platform_role', 'is_active', 'is_staff', 'created_at']
    search_fields = ['name', 'email']
    readonly_fields = ['id', 'created_at', 'updated_at', 'last_login']
    ordering = ['-created_at']
    
    fieldsets = (
        (None, {'fields': ('id', 'email', 'password')}),
        ('Personal info', {'fields': ('name', 'picture_url')}),
        ('Business & Platform', {'fields': ('account_type', 'platform_role', 'role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('name', 'email', 'password1', 'password2', 'role', 'account_type', 'platform_role'),
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ('email',)
        return self.readonly_fields


@admin.register(BusinessInvitation)
class BusinessInvitationAdmin(admin.ModelAdmin):
    list_display = ['email', 'business', 'role', 'status', 'created_at', 'expires_at']
    list_filter = ['status', 'role', 'created_at']
    search_fields = ['email', 'business__name']
    readonly_fields = ['id', 'token', 'accepted_at', 'accepted_by', 'created_at', 'updated_at']
    ordering = ['-created_at']


@admin.register(EmailVerificationToken)
class EmailVerificationTokenAdmin(admin.ModelAdmin):
    list_display = ['user', 'token', 'created_at', 'expires_at', 'consumed_at']
    search_fields = ['user__email', 'token']
    readonly_fields = ['id', 'user', 'token', 'created_at', 'expires_at', 'consumed_at']
    ordering = ['-created_at']


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'action', 'model_name', 'object_id', 'timestamp']
    list_filter = ['action', 'model_name', 'timestamp']
    search_fields = ['user__name', 'user__email', 'model_name', 'object_id']
    readonly_fields = ['id', 'user', 'action', 'model_name', 'object_id', 'changes', 'ip_address', 'user_agent', 'timestamp']
    ordering = ['-timestamp']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'email', 'tin', 'subscription_status', 'is_active', 'created_at']
    search_fields = ['name', 'tin', 'email', 'owner__name', 'owner__email']
    list_filter = ['subscription_status', 'is_active', 'created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['name']
    
    fieldsets = (
        (None, {'fields': ('id', 'name', 'tin', 'owner')}),
        ('Contact', {'fields': ('email', 'phone_numbers', 'website', 'social_handles')}),
        ('Address', {'fields': ('address',)}),
        ('Status', {'fields': ('subscription_status', 'is_active')}),
        ('Dates', {'fields': ('created_at', 'updated_at')}),
    )


@admin.register(BusinessMembership)
class BusinessMembershipAdmin(admin.ModelAdmin):
    list_display = ['business', 'user', 'role', 'is_admin', 'is_active', 'created_at']
    list_filter = ['role', 'is_admin', 'is_active', 'created_at']
    search_fields = ['business__name', 'user__name', 'user__email']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['business__name', 'user__name']
