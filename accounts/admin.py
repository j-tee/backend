from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import Role, User, UserProfile, AuditLog, Business, BusinessMembership


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['name']


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]
    list_display = ['name', 'email', 'role', 'subscription_status', 'is_active', 'created_at']
    list_filter = ['role', 'subscription_status', 'is_active', 'is_staff', 'created_at']
    search_fields = ['name', 'email']
    readonly_fields = ['id', 'created_at', 'updated_at', 'last_login']
    ordering = ['-created_at']
    
    fieldsets = (
        (None, {'fields': ('id', 'email', 'password')}),
        ('Personal info', {'fields': ('name', 'picture_url')}),
        ('Permissions', {'fields': ('role', 'subscription_status', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('name', 'email', 'password1', 'password2', 'role'),
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ('email',)
        return self.readonly_fields


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
    list_display = ['name', 'owner', 'email', 'tin', 'is_active', 'created_at']
    search_fields = ['name', 'tin', 'email', 'owner__name', 'owner__email']
    list_filter = ['is_active', 'created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['name']


@admin.register(BusinessMembership)
class BusinessMembershipAdmin(admin.ModelAdmin):
    list_display = ['business', 'user', 'role', 'is_admin', 'is_active', 'created_at']
    list_filter = ['role', 'is_admin', 'is_active', 'created_at']
    search_fields = ['business__name', 'user__name', 'user__email']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['business__name', 'user__name']
