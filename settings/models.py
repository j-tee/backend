from django.db import models
import uuid


class BusinessSettings(models.Model):
    """
    Stores user preferences for currency, theme, and other settings.
    Uses JSON fields for maximum flexibility without requiring migrations
    when adding new setting options.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.OneToOneField(
        'accounts.Business',
        on_delete=models.CASCADE,
        related_name='settings',
        help_text='The business these settings belong to'
    )

    # Regional settings (currency, timezone, date/time formats)
    regional = models.JSONField(
        default=dict,
        blank=True,
        help_text='Regional settings including currency, timezone, and number formats'
    )

    # Appearance settings (theme, colors, font size, etc.)
    appearance = models.JSONField(
        default=dict,
        blank=True,
        help_text='Visual appearance settings including theme and display options'
    )

    # Notification preferences
    notifications = models.JSONField(
        default=dict,
        blank=True,
        help_text='Notification preferences for email, SMS, and push notifications'
    )

    # Receipt customization
    receipt = models.JSONField(
        default=dict,
        blank=True,
        help_text='Receipt printing and display preferences'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'business_settings'
        verbose_name = 'Business Settings'
        verbose_name_plural = 'Business Settings'
        ordering = ['-created_at']

    def __str__(self):
        return f"Settings for {self.business.name}"

    @staticmethod
    def get_default_regional():
        """Default regional settings"""
        return {
            'currency': {
                'code': 'USD',
                'symbol': '$',
                'name': 'US Dollar',
                'position': 'before',
                'decimalPlaces': 2
            },
            'timezone': 'UTC',
            'dateFormat': 'MM/DD/YYYY',
            'timeFormat': '12h',
            'firstDayOfWeek': 0,
            'numberFormat': 'en-US'
        }

    @staticmethod
    def get_default_appearance():
        """Default appearance settings"""
        return {
            'colorScheme': 'auto',
            'themePreset': 'default-blue',
            'customColors': None,
            'fontSize': 'medium',
            'compactMode': False,
            'animationsEnabled': True,
            'highContrast': False
        }

    @staticmethod
    def get_default_notifications():
        """Default notification settings"""
        return {
            'emailNotifications': True,
            'pushNotifications': True,
            'smsNotifications': False,
            'lowStockAlerts': True,
            'salesUpdates': True,
            'systemUpdates': True,
            'marketingEmails': False
        }

    @staticmethod
    def get_default_receipt():
        """Default receipt settings"""
        return {
            'showLogo': True,
            'logoUrl': None,
            'headerText': None,
            'footerText': 'Thank you for your business!',
            'showTaxBreakdown': True,
            'showBarcode': True,
            'paperSize': 'thermal-80mm'
        }
