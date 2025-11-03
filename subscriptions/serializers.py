"""
Subscription Serializers
Handles serialization/deserialization of subscription data
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from decimal import Decimal
import logging

from .models import (
    SubscriptionPlan,  # DEPRECATED - kept for backward compatibility
    Subscription,
    SubscriptionPayment,
    PaymentGatewayConfig,
    WebhookEvent,
    UsageTracking,
    Invoice,
    Alert,
    SubscriptionPricingTier,
    TaxConfiguration,
    ServiceCharge,
)

User = get_user_model()
logger = logging.getLogger(__name__)


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """
    DEPRECATED: This serializer is deprecated.
    Use SubscriptionPricingTier for dynamic pricing instead.
    Kept only for backward compatibility.
    """
    billing_cycle_display = serializers.SerializerMethodField()
    features_display = serializers.SerializerMethodField()
    is_popular = serializers.BooleanField(read_only=True)
    active_subscriptions_count = serializers.SerializerMethodField()
    
    class Meta:
        model = SubscriptionPlan
        fields = [
            'id', 'name', 'description', 'price', 'currency',
            'billing_cycle', 'billing_cycle_display',
            'max_users', 'max_storefronts', 'max_products',
            'features', 'features_display',
            'is_active', 'is_popular', 'sort_order',
            'trial_period_days', 'active_subscriptions_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_billing_cycle_display(self, obj):
        """Get human-readable billing cycle"""
        return obj.get_billing_cycle_display()
    
    def get_features_display(self, obj):
        """Get formatted features for display"""
        if not obj.features:
            return []
        return obj.features if isinstance(obj.features, list) else []
    
    def get_active_subscriptions_count(self, obj):
        """Get count of active subscriptions for this plan"""
        return obj.subscriptions.filter(status__in=['ACTIVE', 'TRIAL']).count()


class SubscriptionListSerializer(serializers.ModelSerializer):
    """Serializer for subscription listings shown to platform admins."""
    plan = SubscriptionPlanSerializer(read_only=True)
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    plan_details = serializers.SerializerMethodField()
    business_id = serializers.UUIDField(source='business.id', read_only=True)
    business_name = serializers.CharField(source='business.name', read_only=True)
    business_email = serializers.EmailField(source='business.email', read_only=True)
    business_owner = serializers.CharField(source='business.owner.name', read_only=True)
    days_until_expiry = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()
    
    class Meta:
        model = Subscription
        fields = [
            'id', 'business_id', 'business_name', 'business_email',
            'business_owner', 'plan', 'plan_name', 'plan_details',
            'status', 'payment_status', 'start_date', 'end_date',
            'current_period_start', 'current_period_end',
            'next_billing_date', 'is_trial', 'days_until_expiry',
            'is_active', 'auto_renew', 'cancel_at_period_end',
            'created_at', 'updated_at'
        ]
        read_only_fields = fields
    
    def get_days_until_expiry(self, obj):
        return obj.days_until_expiry()
    
    def get_is_active(self, obj):
        return obj.is_active()

    def get_plan_details(self, obj):
        plan = obj.plan
        if not plan:
            return None
        return {
            'id': str(plan.id),
            'name': plan.name,
            'price': str(plan.price),
            'currency': plan.currency,
            'billing_cycle': plan.billing_cycle,
            'interval': plan.get_billing_cycle_display(),
        }


class SubscriptionDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for individual subscription"""
    plan = SubscriptionPlanSerializer(read_only=True)
    plan_id = serializers.UUIDField(write_only=True, required=False)
    business_name = serializers.CharField(source='business.name', read_only=True)
    business_id = serializers.UUIDField(source='business.id', read_only=True)
    
    # Computed fields
    days_until_expiry = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()
    usage_limits = serializers.SerializerMethodField()
    latest_payment = serializers.SerializerMethodField()
    
    class Meta:
        model = Subscription
        fields = [
            'id', 'business_id', 'business_name',
            'plan', 'plan_id', 'amount', 'payment_method', 'payment_status',
            'status', 'start_date', 'end_date',
            'current_period_start', 'current_period_end',
            'auto_renew', 'cancel_at_period_end', 'next_billing_date',
            'is_trial', 'trial_end_date', 'grace_period_days',
            'cancelled_at', 'cancelled_by', 'notes',
            'days_until_expiry', 'is_active', 'is_expired', 'usage_limits',
            'latest_payment', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'cancelled_at',
            'current_period_start', 'current_period_end'
        ]
    
    def get_days_until_expiry(self, obj):
        return obj.days_until_expiry()
    
    def get_is_active(self, obj):
        return obj.is_active()
    
    def get_is_expired(self, obj):
        return obj.is_expired()
    
    def get_usage_limits(self, obj):
        return obj.check_usage_limits()
    
    def get_latest_payment(self, obj):
        latest = obj.payments.filter(status='SUCCESSFUL').order_by('-payment_date').first()
        if latest:
            return {
                'id': str(latest.id),
                'amount': str(latest.amount),
                'payment_date': latest.payment_date,
                'payment_method': latest.payment_method
            }
        return None


class SubscriptionCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new subscriptions with auto-calculated pricing.
    
    NEW SECURE SYSTEM:
    - plan_id is OPTIONAL (deprecated, kept for backward compatibility)
    - If plan_id is provided, it's IGNORED
    - System auto-detects storefront count
    - System auto-calculates price from SubscriptionPricingTier
    - User CANNOT manipulate pricing
    
    Request body can be EMPTY {} - backend does everything.
    """
    plan_id = serializers.UUIDField(required=False, write_only=True, allow_null=True)
    business_id = serializers.UUIDField(required=False, write_only=True, allow_null=True)
    
    class Meta:
        model = Subscription
        fields = [
            'id', 'plan_id', 'business_id', 'payment_method',
            'is_trial', 'trial_end_date', 'status', 'payment_status',
            'amount', 'start_date', 'end_date'
        ]
        read_only_fields = ['id', 'status', 'payment_status', 'amount', 'start_date', 'end_date']
    
    def validate_plan_id(self, value):
        """
        DEPRECATED: plan_id is ignored.
        Kept for backward compatibility but does nothing.
        """
        if value:
            logger.warning(f"plan_id {value} provided but will be ignored - using auto-calculated pricing")
        return None  # Always return None to ignore plan selection
    
    def validate_business_id(self, value):
        """
        Validate that business exists and user is a member.
        If not provided, auto-detect from user's memberships.
        """
        from accounts.models import Business
        
        request = self.context.get('request')
        
        # If business_id not provided, get from user's memberships
        if not value:
            if not request or not request.user:
                raise serializers.ValidationError("Authentication required")
            
            user_business_ids = request.user.business_memberships.values_list('business_id', flat=True)
            if not user_business_ids:
                raise serializers.ValidationError("You must be a member of a business to subscribe")
            
            # Use first business (users typically belong to one)
            value = user_business_ids[0]
        
        try:
            business = Business.objects.get(id=value)
            
            # Check if user is a member of the business
            if request and not business.memberships.filter(user=request.user).exists() and not request.user.is_staff:
                raise serializers.ValidationError("You don't have permission to subscribe for this business")
            
            # Check if business already has an ACTIVE or PAID subscription
            if hasattr(business, 'subscription') and business.subscription:
                existing_sub = business.subscription
                
                # If subscription is ACTIVE and PAID, don't allow duplicate
                if existing_sub.status == 'ACTIVE' and existing_sub.payment_status == 'PAID':
                    raise serializers.ValidationError({
                        'business_id': "This business already has an active subscription.",
                        'detail': "You already have an active subscription. Please go to 'My Subscriptions' to manage or upgrade your plan.",
                        'existing_subscription_id': str(existing_sub.id),
                        'plan_name': existing_sub.plan.name if existing_sub.plan else 'Auto-calculated'
                    })
                
                # If subscription exists but is not ACTIVE+PAID, delete it to allow new attempt
                if existing_sub.payment_status in ['PENDING', 'FAILED', 'OVERDUE', 'CANCELLED']:
                    logger.warning(
                        f"Deleting incomplete subscription {existing_sub.id} for business {business.id} "
                        f"(status: {existing_sub.status}, payment: {existing_sub.payment_status})"
                    )
                    existing_sub.delete()
                elif existing_sub.status in ['INACTIVE', 'CANCELLED', 'SUSPENDED', 'EXPIRED', 'PAST_DUE']:
                    logger.warning(
                        f"Deleting non-active subscription {existing_sub.id} for business {business.id} "
                        f"(status: {existing_sub.status}, payment: {existing_sub.payment_status})"
                    )
                    existing_sub.delete()
            
            return value
        except Business.DoesNotExist:
            raise serializers.ValidationError("Invalid business selected")
    
    def create(self, validated_data):
        """
        Create subscription with AUTO-CALCULATED pricing.
        
        NEW SECURE SYSTEM:
        1. Get user's business (from validated business_id)
        2. Count active storefronts
        3. Find matching SubscriptionPricingTier
        4. Calculate price automatically
        5. Set plan=None (old system deprecated)
        6. Create subscription with correct amount
        
        User CANNOT manipulate pricing - it's all server-side.
        """
        from django.utils import timezone
        from datetime import timedelta, date
        from dateutil.relativedelta import relativedelta
        from accounts.models import Business
        from django.db.models import Q
        
        # Get plan_id and business_id (may be None)
        plan_id = validated_data.pop('plan_id', None)
        business_id = validated_data.pop('business_id', None)
        
        user = self.context['request'].user
        
        # If business_id not provided, get from user
        if not business_id:
            user_business_ids = user.business_memberships.values_list('business_id', flat=True)
            if not user_business_ids:
                raise serializers.ValidationError("You must be a member of a business to subscribe")
            business_id = user_business_ids[0]
        
        business = Business.objects.get(id=business_id)
        
        # 1. Count active storefronts
        storefront_count = business.business_storefronts.filter(is_active=True).count()
        
        if storefront_count == 0:
            raise serializers.ValidationError({
                'storefront_count': 'You must have at least one active storefront to subscribe'
            })
        
        # 2. Find applicable pricing tier
        tier = SubscriptionPricingTier.objects.filter(
            is_active=True,
            min_storefronts__lte=storefront_count
        ).filter(
            Q(max_storefronts__gte=storefront_count) | Q(max_storefronts__isnull=True)
        ).first()
        
        if not tier:
            raise serializers.ValidationError({
                'pricing': f'No pricing tier found for {storefront_count} storefronts'
            })
        
        # 3. Calculate price
        base_price = tier.calculate_price(storefront_count)
        
        # 4. Calculate taxes
        total_tax = Decimal('0.00')
        active_taxes = TaxConfiguration.objects.filter(
            is_active=True,
            applies_to_subscriptions=True,
            effective_from__lte=date.today()
        ).filter(
            Q(effective_until__gte=date.today()) | Q(effective_until__isnull=True)
        ).order_by('calculation_order')
        
        for tax in active_taxes:
            tax_amount = tax.calculate_amount(base_price)
            total_tax += tax_amount
        
        total_amount = base_price + total_tax
        
        # 5. Set subscription dates
        start_date = timezone.now().date()
        end_date = start_date + relativedelta(months=1)  # Always monthly for now
        
        # 6. Create subscription (plan=None - using new pricing tier system)
        subscription = Subscription.objects.create(
            business=business,
            created_by=user,
            plan=None,  # DEPRECATED - using SubscriptionPricingTier instead
            amount=total_amount,
            payment_method=validated_data.get('payment_method', ''),
            payment_status='PENDING',
            status='INACTIVE',  # Will be ACTIVE after payment
            start_date=start_date,
            end_date=end_date,
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
            is_trial=False,
            trial_end_date=None,
            next_billing_date=end_date,
            notes=f"Auto-calculated: {storefront_count} storefronts @ {tier.currency} {base_price} + taxes {total_tax}"
        )
        
        logger.info(
            f"Created subscription {subscription.id} for business {business.name}: "
            f"{storefront_count} storefronts, {tier.currency} {total_amount}"
        )
        
        return subscription


class SubscriptionPaymentSerializer(serializers.ModelSerializer):
    """Serializer for subscription payments"""
    subscription_plan_name = serializers.CharField(source='subscription.plan.name', read_only=True)
    subscription_business_name = serializers.CharField(source='subscription.business.name', read_only=True)
    
    class Meta:
        model = SubscriptionPayment
        fields = [
            'id', 'subscription', 'subscription_plan_name', 'subscription_business_name',
            'amount', 'payment_method', 'status', 'transaction_id',
            'gateway_reference', 'gateway_response', 'payment_date',
            'billing_period_start', 'billing_period_end', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'gateway_response', 'payment_date', 'created_at', 'updated_at'
        ]


class PaymentGatewayConfigSerializer(serializers.ModelSerializer):
    """Serializer for payment gateway configurations"""
    
    class Meta:
        model = PaymentGatewayConfig
        fields = [
            'id', 'gateway', 'is_active', 'public_key',
            'test_mode', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'secret_key': {'write_only': True},
            'webhook_secret': {'write_only': True}
        }


class WebhookEventSerializer(serializers.ModelSerializer):
    """Serializer for webhook events"""
    
    class Meta:
        model = WebhookEvent
        fields = [
            'id', 'gateway', 'event_type', 'event_id', 'status',
            'payload', 'processed_at', 'error_message',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class UsageTrackingSerializer(serializers.ModelSerializer):
    """Serializer for usage tracking"""
    usage_percentage = serializers.SerializerMethodField()
    is_exceeded = serializers.SerializerMethodField()
    
    class Meta:
        model = UsageTracking
        fields = [
            'id', 'subscription', 'metric_type', 'current_usage',
            'limit_value', 'usage_percentage', 'is_exceeded',
            'period_start', 'period_end', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_usage_percentage(self, obj):
        return obj.usage_percentage()
    
    def get_is_exceeded(self, obj):
        return obj.is_exceeded()


class InvoiceSerializer(serializers.ModelSerializer):
    """Serializer for invoices"""
    subscription_plan_name = serializers.CharField(source='subscription.plan.name', read_only=True)
    subscription_business_name = serializers.CharField(source='subscription.business.name', read_only=True)
    is_overdue = serializers.SerializerMethodField()
    days_overdue = serializers.SerializerMethodField()
    
    class Meta:
        model = Invoice
        fields = [
            'id', 'subscription', 'subscription_plan_name', 'subscription_business_name',
            'invoice_number', 'amount', 'tax_amount', 'total_amount',
            'status', 'issue_date', 'due_date', 'paid_date',
            'billing_period_start', 'billing_period_end', 'notes',
            'is_overdue', 'days_overdue', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'invoice_number', 'total_amount', 'paid_date',
            'created_at', 'updated_at'
        ]
    
    def get_is_overdue(self, obj):
        return obj.is_overdue()
    
    def get_days_overdue(self, obj):
        return obj.days_overdue()


class AlertSerializer(serializers.ModelSerializer):
    """Serializer for subscription alerts"""
    subscription_business_name = serializers.CharField(source='subscription.business.name', read_only=True)
    subscription_plan_name = serializers.CharField(source='subscription.plan.name', read_only=True)
    
    class Meta:
        model = Alert
        fields = [
            'id', 'subscription', 'subscription_business_name', 'subscription_plan_name',
            'alert_type', 'priority', 'title', 'message',
            'email_sent', 'sms_sent', 'in_app_shown',
            'is_read', 'is_dismissed', 'action_taken', 'action_taken_at',
            'metadata', 'created_at', 'read_at', 'dismissed_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'read_at', 'dismissed_at', 'action_taken_at'
        ]


class SubscriptionStatsSerializer(serializers.Serializer):
    """Serializer for subscription statistics"""
    total_subscriptions = serializers.IntegerField()
    active_subscriptions = serializers.IntegerField()
    trial_subscriptions = serializers.IntegerField()
    expired_subscriptions = serializers.IntegerField()
    cancelled_subscriptions = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    monthly_recurring_revenue = serializers.DecimalField(max_digits=12, decimal_places=2)
    average_subscription_value = serializers.DecimalField(max_digits=10, decimal_places=2)
    churn_rate = serializers.FloatField()


# New Serializers for Flexible Pricing System

class SubscriptionPricingTierSerializer(serializers.ModelSerializer):
    """Serializer for subscription pricing tiers"""
    
    class Meta:
        model = SubscriptionPricingTier
        fields = [
            'id', 'min_storefronts', 'max_storefronts',
            'base_price', 'price_per_additional_storefront', 'currency',
            'is_active', 'description', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TaxConfigurationSerializer(serializers.ModelSerializer):
    """Serializer for tax configurations"""
    is_effective_now = serializers.SerializerMethodField()
    
    class Meta:
        model = TaxConfiguration
        fields = [
            'id', 'name', 'code', 'description', 'rate', 'country',
            'applies_to_subscriptions', 'is_mandatory', 'calculation_order',
            'applies_to', 'is_active', 'effective_from', 'effective_until',
            'is_effective_now', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_is_effective_now(self, obj):
        return obj.is_effective()


class ServiceChargeSerializer(serializers.ModelSerializer):
    """Serializer for service charges"""
    
    class Meta:
        model = ServiceCharge
        fields = [
            'id', 'name', 'code', 'description', 'charge_type', 'amount',
            'currency', 'applies_to', 'payment_gateway', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class EnhancedSubscriptionPaymentSerializer(serializers.ModelSerializer):
    """Enhanced serializer with full pricing breakdown"""
    subscription_plan_name = serializers.CharField(source='subscription.plan.name', read_only=True)
    subscription_business_name = serializers.CharField(source='subscription.business.name', read_only=True)
    
    class Meta:
        model = SubscriptionPayment
        fields = [
            'id', 'subscription', 'subscription_plan_name', 'subscription_business_name',
            'amount', 'currency', 'payment_method', 'status',
            'transaction_id', 'transaction_reference', 'gateway_reference', 'gateway_response',
            'payment_date', 'billing_period_start', 'billing_period_end',
            # Enhanced fields
            'base_amount', 'storefront_count', 'pricing_tier_snapshot',
            'tax_breakdown', 'total_tax_amount',
            'service_charges_breakdown', 'total_service_charges',
            'attempt_number', 'previous_attempt', 'failure_reason',
            'gateway_error_code', 'gateway_error_message', 'status_history',
            'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
