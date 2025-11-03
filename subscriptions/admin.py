"""
Django Admin for Subscription Management
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import (
    # SubscriptionPlan - DEPRECATED, removed from admin
    Subscription,
    SubscriptionPayment,
    PaymentGatewayConfig,
    WebhookEvent,
    UsageTracking,
    Invoice,
    Alert,
    SubscriptionPricingTier,
    TaxConfiguration,
    ServiceCharge
)


# SubscriptionPlan admin removed - use SubscriptionPricingTier instead


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['user_link', 'business_link', 'status', 'payment_status', 'amount', 'end_date', 'days_remaining']
    list_filter = ['status', 'payment_status', 'is_trial', 'auto_renew', 'created_at']
    search_fields = ['user__username', 'user__email', 'business__name']
    readonly_fields = ['created_at', 'updated_at', 'current_period_start', 'current_period_end']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Subscription Info', {
            'fields': ('user', 'business', 'amount', 'status', 'payment_status')
        }),
        ('Billing Period', {
            'fields': ('start_date', 'end_date', 'current_period_start', 'current_period_end', 'next_billing_date')
        }),
        ('Payment', {
            'fields': ('payment_method', 'auto_renew', 'cancel_at_period_end')
        }),
        ('Trial', {
            'fields': ('is_trial', 'trial_end_date')
        }),
        ('Settings', {
            'fields': ('grace_period_days', 'notes')
        }),
        ('Cancellation', {
            'fields': ('cancelled_at', 'cancelled_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def user_link(self, obj):
        """Link to user admin"""
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    
    def business_link(self, obj):
        """Link to business if exists"""
        if obj.business:
            return format_html('<strong>{}</strong>', obj.business.name)
        return '-'
    business_link.short_description = 'Business'
    
    def days_remaining(self, obj):
        """Show days until expiry with color coding"""
        days = obj.days_until_expiry()
        if days <= 0:
            color = 'red'
            text = 'Expired'
        elif days <= 7:
            color = 'orange'
            text = f'{days} days'
        else:
            color = 'green'
            text = f'{days} days'
        return format_html('<span style="color: {};">{}</span>', color, text)
    days_remaining.short_description = 'Days Remaining'
    
    actions = ['activate_subscriptions', 'suspend_subscriptions', 'cancel_subscriptions']
    
    def activate_subscriptions(self, request, queryset):
        """Bulk activate subscriptions"""
        updated = queryset.update(status='ACTIVE', payment_status='PAID')
        self.message_user(request, f'{updated} subscriptions activated.')
    activate_subscriptions.short_description = 'Activate selected subscriptions'
    
    def suspend_subscriptions(self, request, queryset):
        """Bulk suspend subscriptions"""
        updated = queryset.update(status='SUSPENDED')
        self.message_user(request, f'{updated} subscriptions suspended.')
    suspend_subscriptions.short_description = 'Suspend selected subscriptions'
    
    def cancel_subscriptions(self, request, queryset):
        """Bulk cancel subscriptions"""
        updated = queryset.update(status='CANCELLED', cancelled_at=timezone.now())
        self.message_user(request, f'{updated} subscriptions cancelled.')
    cancel_subscriptions.short_description = 'Cancel selected subscriptions'


@admin.register(SubscriptionPayment)
class SubscriptionPaymentAdmin(admin.ModelAdmin):
    list_display = ['subscription_link', 'amount', 'payment_method', 'status', 'transaction_id', 'payment_date']
    list_filter = ['status', 'payment_method', 'payment_date', 'created_at']
    search_fields = ['transaction_id', 'gateway_reference', 'subscription__user__username']
    readonly_fields = ['created_at', 'updated_at', 'gateway_response']
    date_hierarchy = 'payment_date'
    
    def subscription_link(self, obj):
        """Link to subscription admin"""
        url = reverse('admin:subscriptions_subscription_change', args=[obj.subscription.id])
        business_name = obj.subscription.business.name if obj.subscription.business else obj.subscription.user.username
        return format_html('<a href="{}">{}</a>', url, f'{obj.subscription.user.username} - {business_name}')
    subscription_link.short_description = 'Subscription'


@admin.register(PaymentGatewayConfig)
class PaymentGatewayConfigAdmin(admin.ModelAdmin):
    list_display = ['gateway', 'is_active', 'test_mode', 'created_at']
    list_filter = ['gateway', 'is_active', 'test_mode']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Gateway Info', {
            'fields': ('gateway', 'is_active', 'test_mode')
        }),
        ('API Keys', {
            'fields': ('public_key', 'secret_key', 'webhook_secret'),
            'description': 'Keep these keys secure!'
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ['event_type', 'gateway', 'status', 'event_id', 'created_at', 'processed_at']
    list_filter = ['gateway', 'status', 'event_type', 'created_at']
    search_fields = ['event_id', 'event_type']
    readonly_fields = ['created_at', 'payload']
    date_hierarchy = 'created_at'
    
    def has_add_permission(self, request):
        """Webhook events are created automatically"""
        return False


@admin.register(UsageTracking)
class UsageTrackingAdmin(admin.ModelAdmin):
    list_display = ['subscription_link', 'metric_type', 'current_usage', 'limit_value', 'usage_percent', 'period_range']
    list_filter = ['metric_type', 'period_start']
    search_fields = ['subscription__user__username', 'subscription__business__name']
    readonly_fields = ['created_at', 'updated_at']
    
    def subscription_link(self, obj):
        """Link to subscription"""
        url = reverse('admin:subscriptions_subscription_change', args=[obj.subscription.id])
        return format_html('<a href="{}">{}</a>', url, obj.subscription.user.username)
    subscription_link.short_description = 'Subscription'
    
    def usage_percent(self, obj):
        """Show usage as percentage"""
        percent = obj.usage_percentage()
        if percent >= 100:
            color = 'red'
        elif percent >= 80:
            color = 'orange'
        else:
            color = 'green'
        return format_html('<span style="color: {};">{:.1f}%</span>', color, percent)
    usage_percent.short_description = 'Usage %'
    
    def period_range(self, obj):
        """Show period range"""
        return f'{obj.period_start} to {obj.period_end}'
    period_range.short_description = 'Period'


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['invoice_number', 'subscription_link', 'amount_display', 'status', 'issue_date', 'due_date', 'overdue_status']
    list_filter = ['status', 'issue_date', 'due_date']
    search_fields = ['invoice_number', 'subscription__user__username', 'subscription__business__name']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'issue_date'
    
    fieldsets = (
        ('Invoice Info', {
            'fields': ('subscription', 'invoice_number', 'status')
        }),
        ('Amounts', {
            'fields': ('amount', 'tax_amount', 'total_amount')
        }),
        ('Dates', {
            'fields': ('issue_date', 'due_date', 'paid_date')
        }),
        ('Billing Period', {
            'fields': ('billing_period_start', 'billing_period_end')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def subscription_link(self, obj):
        """Link to subscription"""
        url = reverse('admin:subscriptions_subscription_change', args=[obj.subscription.id])
        business_name = obj.subscription.business.name if obj.subscription.business else obj.subscription.user.username
        return format_html('<a href="{}">{}</a>', url, business_name)
    subscription_link.short_description = 'Subscription'
    
    def amount_display(self, obj):
        """Display total amount"""
        return format_html('<strong>{}</strong>', obj.total_amount)
    amount_display.short_description = 'Total Amount'
    
    def overdue_status(self, obj):
        """Show if invoice is overdue"""
        if obj.is_overdue():
            days = obj.days_overdue()
            return format_html('<span style="color: red;">{} days overdue</span>', days)
        return format_html('<span style="color: green;">Current</span>')
    overdue_status.short_description = 'Status'
    
    actions = ['mark_as_paid']
    
    def mark_as_paid(self, request, queryset):
        """Mark invoices as paid"""
        for invoice in queryset:
            invoice.mark_as_paid()
        self.message_user(request, f'{queryset.count()} invoices marked as paid.')
    mark_as_paid.short_description = 'Mark selected as paid'


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ['title', 'subscription_link', 'alert_type', 'priority', 'is_read', 'is_dismissed', 'created_at']
    list_filter = ['alert_type', 'priority', 'is_read', 'is_dismissed', 'created_at']
    search_fields = ['title', 'message', 'subscription__user__username', 'subscription__business__name']
    readonly_fields = ['created_at', 'read_at', 'dismissed_at', 'action_taken_at']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Alert Info', {
            'fields': ('subscription', 'alert_type', 'priority', 'title', 'message')
        }),
        ('Notification Status', {
            'fields': ('email_sent', 'sms_sent', 'in_app_shown')
        }),
        ('Action Status', {
            'fields': ('is_read', 'read_at', 'is_dismissed', 'dismissed_at', 'action_taken', 'action_taken_at')
        }),
        ('Metadata', {
            'fields': ('metadata',)
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )
    
    def subscription_link(self, obj):
        """Link to subscription"""
        url = reverse('admin:subscriptions_subscription_change', args=[obj.subscription.id])
        business_name = obj.subscription.business.name if obj.subscription.business else obj.subscription.user.username
        return format_html('<a href="{}">{}</a>', url, business_name)
    subscription_link.short_description = 'Subscription'
    
    actions = ['mark_as_read', 'dismiss_alerts']
    
    def mark_as_read(self, request, queryset):
        """Mark alerts as read"""
        for alert in queryset:
            alert.mark_as_read()
        self.message_user(request, f'{queryset.count()} alerts marked as read.')
    mark_as_read.short_description = 'Mark selected as read'
    
    def dismiss_alerts(self, request, queryset):
        """Dismiss alerts"""
        for alert in queryset:
            alert.dismiss()
        self.message_user(request, f'{queryset.count()} alerts dismissed.')
    dismiss_alerts.short_description = 'Dismiss selected alerts'


@admin.register(SubscriptionPricingTier)
class SubscriptionPricingTierAdmin(admin.ModelAdmin):
    list_display = ['tier_description', 'base_price', 'price_per_additional', 'currency', 'is_active', 'created_at']
    list_filter = ['is_active', 'currency', 'created_at']
    search_fields = ['description']
    ordering = ['min_storefronts']
    
    fieldsets = (
        ('Tier Configuration', {
            'fields': ('min_storefronts', 'max_storefronts', 'description')
        }),
        ('Pricing', {
            'fields': ('base_price', 'price_per_additional_storefront', 'currency')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )
    
    def tier_description(self, obj):
        """Display tier range"""
        if obj.max_storefronts:
            return format_html('<strong>{}-{} storefronts</strong>', obj.min_storefronts, obj.max_storefronts)
        return format_html('<strong>{}+ storefronts</strong>', obj.min_storefronts)
    tier_description.short_description = 'Tier Range'
    
    def price_per_additional(self, obj):
        """Display additional storefront price"""
        if obj.price_per_additional_storefront > 0:
            return format_html('{} {} per additional', obj.currency, obj.price_per_additional_storefront)
        return '-'
    price_per_additional.short_description = 'Additional Price'


@admin.register(TaxConfiguration)
class TaxConfigurationAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'rate_display', 'applies_to_subscriptions', 'is_active', 'effective_from', 'calculation_order']
    list_filter = ['is_active', 'applies_to_subscriptions', 'country', 'effective_from']
    search_fields = ['code', 'name', 'description']
    ordering = ['calculation_order', 'code']
    
    fieldsets = (
        ('Tax Information', {
            'fields': ('code', 'name', 'description', 'country')
        }),
        ('Tax Rate', {
            'fields': ('rate',)
        }),
        ('Application', {
            'fields': ('applies_to_subscriptions', 'applies_to', 'calculation_order', 'is_mandatory')
        }),
        ('Validity Period', {
            'fields': ('effective_from', 'effective_until')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )
    
    def rate_display(self, obj):
        """Display rate with percentage symbol"""
        return format_html('<strong>{}%</strong>', obj.rate)
    rate_display.short_description = 'Rate'


@admin.register(ServiceCharge)
class ServiceChargeAdmin(admin.ModelAdmin):
    list_display = ['code', 'name', 'charge_display', 'applies_to', 'payment_gateway', 'is_active']
    list_filter = ['is_active', 'charge_type', 'applies_to', 'payment_gateway']
    search_fields = ['code', 'name', 'description']
    ordering = ['code']
    
    fieldsets = (
        ('Charge Information', {
            'fields': ('code', 'name', 'description')
        }),
        ('Charge Configuration', {
            'fields': ('charge_type', 'amount', 'applies_to')
        }),
        ('Gateway', {
            'fields': ('payment_gateway',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )
    
    def charge_display(self, obj):
        """Display charge amount"""
        if obj.charge_type == 'PERCENTAGE':
            return format_html('<strong>{}%</strong>', obj.amount)
        return format_html('<strong>{}</strong>', obj.amount)
    charge_display.short_description = 'Charge'
