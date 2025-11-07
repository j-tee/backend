"""
AI Features Serializers
Serializers for AI credit management and usage tracking.
"""

from rest_framework import serializers
from decimal import Decimal
from .models import BusinessAICredits, AITransaction, AICreditPurchase, AIUsageAlert


class BusinessAICreditsSerializer(serializers.ModelSerializer):
    """Serializer for AI credits balance"""
    
    is_expired = serializers.BooleanField(read_only=True)
    days_until_expiry = serializers.SerializerMethodField()
    
    class Meta:
        model = BusinessAICredits
        fields = [
            'id', 'business', 'balance', 'purchased_at', 'updated_at',
            'expires_at', 'is_active', 'is_expired', 'days_until_expiry'
        ]
        read_only_fields = ['id', 'purchased_at', 'updated_at']
    
    def get_days_until_expiry(self, obj):
        """Calculate days until credits expire"""
        from django.utils import timezone
        if obj.expires_at > timezone.now():
            delta = obj.expires_at - timezone.now()
            return delta.days
        return 0


class AITransactionSerializer(serializers.ModelSerializer):
    """Serializer for AI transaction history"""
    
    feature_display = serializers.CharField(source='get_feature_display', read_only=True)
    
    class Meta:
        model = AITransaction
        fields = [
            'id', 'business', 'user', 'feature', 'feature_display',
            'credits_used', 'cost_to_us', 'tokens_used', 'timestamp',
            'success', 'error_message', 'processing_time_ms'
        ]
        read_only_fields = fields


class AICreditPurchaseSerializer(serializers.ModelSerializer):
    """Serializer for AI credit purchases"""
    
    total_credits = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    payment_status_display = serializers.CharField(
        source='get_payment_status_display',
        read_only=True
    )
    
    class Meta:
        model = AICreditPurchase
        fields = [
            'id', 'business', 'user', 'amount_paid', 'credits_purchased',
            'bonus_credits', 'total_credits', 'payment_reference',
            'payment_method', 'payment_status', 'payment_status_display',
            'purchased_at', 'completed_at', 'notes'
        ]
        read_only_fields = [
            'id', 'total_credits', 'payment_status_display',
            'purchased_at', 'completed_at'
        ]


class CreditPurchaseRequestSerializer(serializers.Serializer):
    """Serializer for credit purchase request"""
    
    package = serializers.ChoiceField(
        choices=['starter', 'value', 'premium', 'custom'],
        required=True
    )
    custom_amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        min_value=Decimal('10.00')
    )
    payment_method = serializers.ChoiceField(
        choices=['mobile_money', 'card'],
        default='mobile_money'
    )
    callback_url = serializers.URLField(
        required=False,
        allow_blank=True,
        help_text="Frontend callback URL for payment redirect (e.g., https://frontend.com/payment/callback)"
    )


class NaturalLanguageQuerySerializer(serializers.Serializer):
    """Serializer for natural language query requests"""
    
    query = serializers.CharField(
        required=True,
        min_length=3,
        max_length=500,
        help_text="Natural language question about your business"
    )
    storefront_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        help_text="Optional: Filter results to specific storefront"
    )


class ProductDescriptionRequestSerializer(serializers.Serializer):
    """Serializer for product description generation"""
    
    product_id = serializers.UUIDField(required=True)
    tone = serializers.ChoiceField(
        choices=['professional', 'casual', 'technical', 'marketing'],
        default='professional'
    )
    language = serializers.ChoiceField(
        choices=['en', 'tw'],
        default='en'
    )
    include_seo = serializers.BooleanField(default=True)


class CreditAssessmentRequestSerializer(serializers.Serializer):
    """Serializer for credit risk assessment request"""
    
    customer_id = serializers.UUIDField(required=True)
    requested_credit_limit = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal('0.00')
    )
    assessment_type = serializers.ChoiceField(
        choices=['new_credit', 'increase', 'renewal'],
        default='new_credit'
    )


class CollectionMessageRequestSerializer(serializers.Serializer):
    """Serializer for collection message generation"""
    
    customer_id = serializers.UUIDField(required=True)
    message_type = serializers.ChoiceField(
        choices=['first_reminder', 'second_reminder', 'final_notice', 'payment_plan_offer'],
        required=True
    )
    tone = serializers.ChoiceField(
        choices=['professional_friendly', 'firm', 'formal_legal'],
        default='professional_friendly'
    )
    language = serializers.ChoiceField(
        choices=['en', 'tw'],
        default='en'
    )
    include_payment_plan = serializers.BooleanField(default=False)


class InventoryForecastRequestSerializer(serializers.Serializer):
    """Serializer for inventory forecasting request"""
    
    product_id = serializers.UUIDField(required=True)
    forecast_days = serializers.IntegerField(
        default=30,
        min_value=7,
        max_value=90
    )
    include_seasonality = serializers.BooleanField(default=True)
    include_recommendations = serializers.BooleanField(default=True)


class AIUsageStatsSerializer(serializers.Serializer):
    """Serializer for AI usage statistics response"""
    
    period_days = serializers.IntegerField()
    current_balance = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_requests = serializers.IntegerField()
    successful_requests = serializers.IntegerField()
    failed_requests = serializers.IntegerField()
    total_credits_used = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_cost_ghs = serializers.DecimalField(max_digits=10, decimal_places=4)
    avg_processing_time_ms = serializers.IntegerField()
    feature_breakdown = serializers.ListField()
