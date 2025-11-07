from django.contrib import admin
from .models import BusinessAICredits, AITransaction, AICreditPurchase, AIUsageAlert


@admin.register(BusinessAICredits)
class BusinessAICreditsAdmin(admin.ModelAdmin):
    list_display = ['business', 'balance', 'expires_at', 'is_active', 'purchased_at']
    list_filter = ['is_active', 'expires_at']
    search_fields = ['business__name']
    readonly_fields = ['id', 'purchased_at', 'updated_at']
    ordering = ['-purchased_at']


@admin.register(AITransaction)
class AITransactionAdmin(admin.ModelAdmin):
    list_display = ['business', 'feature', 'credits_used', 'success', 'timestamp']
    list_filter = ['feature', 'success', 'timestamp']
    search_fields = ['business__name', 'feature']
    readonly_fields = ['id', 'timestamp']
    ordering = ['-timestamp']
    
    def has_add_permission(self, request):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AICreditPurchase)
class AICreditPurchaseAdmin(admin.ModelAdmin):
    list_display = ['business', 'amount_paid', 'credits_purchased', 'payment_status', 'purchased_at']
    list_filter = ['payment_status', 'payment_method', 'purchased_at']
    search_fields = ['business__name', 'payment_reference']
    readonly_fields = ['id', 'purchased_at', 'completed_at']
    ordering = ['-purchased_at']


@admin.register(AIUsageAlert)
class AIUsageAlertAdmin(admin.ModelAdmin):
    list_display = ['business', 'alert_type', 'current_balance', 'sent_at', 'acknowledged']
    list_filter = ['alert_type', 'acknowledged', 'sent_at']
    search_fields = ['business__name']
    readonly_fields = ['id', 'sent_at']
    ordering = ['-sent_at']
