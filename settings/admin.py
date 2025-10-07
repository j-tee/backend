from django.contrib import admin
from .models import BusinessSettings


@admin.register(BusinessSettings)
class BusinessSettingsAdmin(admin.ModelAdmin):
    """Admin interface for business settings"""
    
    list_display = [
        'business',
        'get_currency',
        'get_theme',
        'updated_at',
    ]
    list_filter = ['updated_at', 'created_at']
    search_fields = ['business__name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    fieldsets = (
        ('Business', {
            'fields': ('id', 'business')
        }),
        ('Regional Settings', {
            'fields': ('regional',),
            'description': 'Currency, timezone, and regional preferences'
        }),
        ('Appearance Settings', {
            'fields': ('appearance',),
            'description': 'Theme, colors, and display options'
        }),
        ('Notification Settings', {
            'fields': ('notifications',),
            'description': 'Email, SMS, and push notification preferences'
        }),
        ('Receipt Settings', {
            'fields': ('receipt',),
            'description': 'Receipt printing and display preferences'
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def get_currency(self, obj):
        """Display currency code in list view"""
        currency = obj.regional.get('currency', {})
        return f"{currency.get('code', 'N/A')} ({currency.get('symbol', '')})"
    get_currency.short_description = 'Currency'

    def get_theme(self, obj):
        """Display theme preset in list view"""
        return obj.appearance.get('themePreset', 'default-blue')
    get_theme.short_description = 'Theme'

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of settings through admin"""
        return False
