# AI Features as Optional Add-Ons - Implementation Guide

**Document Status:** Ready for Implementation  
**Date:** November 7, 2025  
**For:** Backend Development Team  
**Priority:** Medium - Strategic Feature Enhancement

---

## 🎯 Executive Summary

This document outlines how to add AI features as **optional add-ons** to your existing storefront-based subscription pricing model. AI features will be:

✅ **Entirely optional** - Users keep full POS functionality without AI  
✅ **Pay-as-you-go** - Users buy AI credits only when needed  
✅ **Non-disruptive** - Current pricing tiers remain unchanged  
✅ **High margin** - 50-95% profit margins on AI features  

---

## 📊 Your Current Pricing Model (Preserved)

```
┌─────────────────────────────────────────────────────────┐
│ CURRENT SYSTEM (No Changes)                            │
├─────────────────────────────────────────────────────────┤
│ 1 storefront:   GHS 100.00/month                       │
│ 2 storefronts:  GHS 150.00/month                       │
│ 3 storefronts:  GHS 180.00/month                       │
│ 4 storefronts:  GHS 200.00/month                       │
│ 5+ storefronts: GHS 200.00 + GHS 50.00/extra          │
│                                                         │
│ ✅ Full POS features (inventory, sales, reports, etc.) │
│ ✅ Multi-tenant isolation                              │
│ ✅ Customer credit management                          │
│ ✅ RFM customer segmentation                           │
│ ✅ All existing reports                                │
└─────────────────────────────────────────────────────────┘
```

**No changes to your existing subscription model!**

---

## 🚀 New AI Add-On Model

### Option 1: Pure Prepaid Credits (Recommended for Ghana Market)

```
┌─────────────────────────────────────────────────────────┐
│ AI CREDITS - OPTIONAL ADD-ON                            │
├─────────────────────────────────────────────────────────┤
│ Starter Pack:  GHS 30 = 30 credits                     │
│ Value Pack:    GHS 80 = 100 credits (20% bonus!)       │
│ Pro Pack:      GHS 180 = 250 credits (39% bonus!)      │
│                                                         │
│ ✅ Buy anytime via Mobile Money (Paystack)             │
│ ✅ Credits never expire                                │
│ ✅ Use only when you need AI help                      │
│ ✅ No recurring charges                                │
└─────────────────────────────────────────────────────────┘
```

**Why prepaid works in Ghana:**
- Familiar model (like airtime, electricity)
- No subscription fatigue
- Psychological control ("I'm not locked in")
- Clear value exchange ("I pay, I get credits")

---

### Option 2: Hybrid Model (Alternative)

```
┌─────────────────────────────────────────────────────────┐
│ BASE SUBSCRIPTION (Current)                             │
│ GHS 100-200/month (based on storefronts)               │
│ + 5 FREE AI credits/month to try features              │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ AI POWER-UP ADD-ON (Optional)                           │
│ + GHS 50/month = 100 extra credits/month               │
│ ✅ Auto-renews with subscription                        │
│ ✅ Cancel anytime                                       │
│ ✅ Unused credits roll over (max 50)                    │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│ TOP-UP PACKS (When add-on runs out)                     │
│ Quick Pack: GHS 30 = 30 credits                        │
│ Value Pack: GHS 80 = 100 credits                       │
└─────────────────────────────────────────────────────────┘
```

---

## 💳 AI Credit Costs Per Feature

| AI Feature | Credits | GHS Cost | Your Cost | Your Profit | Margin |
|-----------|---------|----------|-----------|-------------|---------|
| **BASIC FEATURES (High Volume, High Margin)** |
| Product Description | 0.1 | 0.10 | 0.005 | 0.095 | 95% ✅ |
| Report Summary | 0.2 | 0.20 | 0.015 | 0.185 | 92% ✅ |
| Customer Insight Query | 0.5 | 0.50 | 0.008 | 0.492 | 98% ✅ |
| Collection Message | 0.5 | 0.50 | 0.005 | 0.495 | 99% ✅ |
| **ADVANCED FEATURES (Lower Volume, Good Margin)** |
| Credit Risk Assessment | 3.0 | 3.00 | 0.640 | 2.36 | 79% ✅ |
| Collection Priority Analysis | 5.0 | 5.00 | 3.200 | 1.80 | 36% ✅ |
| Inventory Forecast | 4.0 | 4.00 | 2.000 | 2.00 | 50% ✅ |
| Portfolio Health Dashboard | 5.0 | 5.00 | 8.000 | -3.00 | -60% ⚠️ |

**Note on Portfolio Dashboard:** This feature is expensive (complex analysis). Consider making it a premium feature or bundling it with a monthly AI subscription add-on.

---

## 🏗️ Technical Implementation

### 1. New Database Models

Add these models to your existing `subscriptions/models.py`:

```python
class BusinessAICredits(models.Model):
    """AI credit balance per business (separate from subscription)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.OneToOneField(
        'accounts.Business',
        on_delete=models.CASCADE,
        related_name='ai_credits'
    )
    balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Current AI credit balance"
    )
    total_purchased = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Lifetime AI credits purchased"
    )
    total_used = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Lifetime AI credits used"
    )
    
    # Optional: Monthly AI subscription add-on
    has_monthly_ai_addon = models.BooleanField(
        default=False,
        help_text="Whether business subscribed to monthly AI credits add-on"
    )
    monthly_ai_addon_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Monthly AI add-on price (e.g., GHS 50)"
    )
    monthly_ai_credits = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Monthly AI credits included in add-on (e.g., 100)"
    )
    next_ai_addon_renewal = models.DateField(
        null=True,
        blank=True,
        help_text="Next date monthly AI credits will be added"
    )
    
    # Free trial
    free_trial_credits_given = models.BooleanField(
        default=False,
        help_text="Whether business received initial free AI credits"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'business_ai_credits'
        verbose_name = 'Business AI Credits'
        verbose_name_plural = 'Business AI Credits'
    
    def __str__(self):
        return f"{self.business.name} - {self.balance} credits"
    
    def has_sufficient_credits(self, required: Decimal) -> bool:
        """Check if business has enough credits"""
        return self.balance >= required
    
    def deduct_credits(self, amount: Decimal, feature: str) -> Decimal:
        """Deduct credits and return new balance"""
        if not self.has_sufficient_credits(amount):
            raise InsufficientCreditsError(
                f"Insufficient credits. Required: {amount}, Available: {self.balance}"
            )
        
        self.balance -= amount
        self.total_used += amount
        self.save()
        
        return self.balance
    
    def add_credits(self, amount: Decimal) -> Decimal:
        """Add credits and return new balance"""
        self.balance += amount
        self.total_purchased += amount
        self.save()
        
        return self.balance


class AITransaction(models.Model):
    """Log every AI feature usage for billing and analytics"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        'accounts.Business',
        on_delete=models.CASCADE,
        related_name='ai_transactions'
    )
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='ai_transactions',
        help_text="User who initiated the AI request"
    )
    
    # Feature details
    feature = models.CharField(
        max_length=100,
        choices=[
            ('product_description', 'Product Description Generator'),
            ('report_summary', 'Report Summary'),
            ('customer_insight', 'Customer Insight Query'),
            ('collection_message', 'Collection Message Generator'),
            ('credit_assessment', 'Credit Risk Assessment'),
            ('collection_analysis', 'Collection Priority Analysis'),
            ('inventory_forecast', 'Inventory Forecast'),
            ('portfolio_dashboard', 'Portfolio Health Dashboard'),
        ]
    )
    feature_display_name = models.CharField(max_length=200)
    
    # Cost tracking
    credits_charged = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        help_text="Credits charged to business"
    )
    actual_openai_cost = models.DecimalField(
        max_digits=8,
        decimal_places=6,
        help_text="Actual cost from OpenAI in USD"
    )
    actual_openai_cost_ghs = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        help_text="Actual cost from OpenAI in GHS"
    )
    
    # Token usage
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)
    total_tokens = models.IntegerField(default=0)
    
    # Status
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    
    # Request/Response (for debugging, audit)
    request_data = models.JSONField(
        default=dict,
        help_text="Sanitized request parameters (NO PII)"
    )
    response_summary = models.JSONField(
        default=dict,
        help_text="Response metadata (NO full content for privacy)"
    )
    
    # Performance
    response_time_ms = models.IntegerField(
        help_text="API response time in milliseconds"
    )
    
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'ai_transactions'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['business', 'feature', 'timestamp']),
            models.Index(fields=['success', 'timestamp']),
            models.Index(fields=['timestamp']),
        ]
    
    def __str__(self):
        return f"{self.business.name} - {self.feature} - {self.credits_charged} credits"


class AICreditPurchase(models.Model):
    """Track AI credit purchases"""
    PAYMENT_METHOD_CHOICES = [
        ('MOMO', 'Mobile Money'),
        ('PAYSTACK', 'Paystack'),
        ('STRIPE', 'Stripe'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SUCCESSFUL', 'Successful'),
        ('FAILED', 'Failed'),
        ('REFUNDED', 'Refunded'),
    ]
    
    PACK_TYPE_CHOICES = [
        ('STARTER', 'Starter Pack - GHS 30 (30 credits)'),
        ('VALUE', 'Value Pack - GHS 80 (100 credits)'),
        ('PRO', 'Pro Pack - GHS 180 (250 credits)'),
        ('CUSTOM', 'Custom Amount'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        'accounts.Business',
        on_delete=models.CASCADE,
        related_name='ai_credit_purchases'
    )
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='ai_credit_purchases'
    )
    
    # Purchase details
    pack_type = models.CharField(max_length=20, choices=PACK_TYPE_CHOICES)
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Amount paid in GHS"
    )
    credits_purchased = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="AI credits purchased"
    )
    bonus_credits = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Bonus credits (e.g., 20% extra for Value Pack)"
    )
    total_credits = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Total credits = purchased + bonus"
    )
    
    # Payment
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    payment_reference = models.CharField(max_length=255, unique=True)
    transaction_id = models.CharField(max_length=255, blank=True)
    gateway_reference = models.CharField(max_length=255, blank=True)
    gateway_response = models.JSONField(default=dict)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    payment_date = models.DateTimeField(null=True, blank=True)
    
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'ai_credit_purchases'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['business', 'status']),
            models.Index(fields=['payment_reference']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.business.name} - {self.pack_type} - GHS {self.amount_paid}"
    
    def mark_as_successful(self):
        """Mark purchase as successful and add credits to business"""
        self.status = 'SUCCESSFUL'
        self.payment_date = timezone.now()
        self.save()
        
        # Add credits to business
        ai_credits, created = BusinessAICredits.objects.get_or_create(
            business=self.business,
            defaults={'balance': Decimal('0.00')}
        )
        ai_credits.add_credits(self.total_credits)
        
        return ai_credits.balance


class AIMonthlyAddon(models.Model):
    """Optional monthly AI subscription add-on"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        'accounts.Business',
        on_delete=models.CASCADE,
        related_name='ai_monthly_addons'
    )
    
    # Addon details
    monthly_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Monthly recurring price (e.g., GHS 50)"
    )
    monthly_credits = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Monthly credits included (e.g., 100)"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    next_renewal_date = models.DateField()
    auto_renew = models.BooleanField(default=True)
    
    # Cancellation
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'ai_monthly_addons'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.business.name} - GHS {self.monthly_price}/month"
    
    def renew(self):
        """Renew monthly add-on and credit AI credits"""
        from dateutil.relativedelta import relativedelta
        
        # Add credits to business
        ai_credits, created = BusinessAICredits.objects.get_or_create(
            business=self.business,
            defaults={'balance': Decimal('0.00')}
        )
        ai_credits.add_credits(self.monthly_credits)
        
        # Update next renewal
        self.next_renewal_date = self.next_renewal_date + relativedelta(months=1)
        self.save()
        
        return ai_credits.balance


class InsufficientCreditsError(Exception):
    """Raised when business doesn't have enough AI credits"""
    pass
```

---

### 2. AI Billing Service

Create `subscriptions/ai_billing.py`:

```python
from decimal import Decimal
from django.db import transaction
from subscriptions.models import (
    BusinessAICredits,
    AITransaction,
    InsufficientCreditsError
)


class AIBillingService:
    """Handle AI credit validation and charging"""
    
    # Credit costs for each feature
    FEATURE_COSTS = {
        'product_description': Decimal('0.1'),
        'report_summary': Decimal('0.2'),
        'customer_insight': Decimal('0.5'),
        'collection_message': Decimal('0.5'),
        'credit_assessment': Decimal('3.0'),
        'collection_analysis': Decimal('5.0'),
        'inventory_forecast': Decimal('4.0'),
        'portfolio_dashboard': Decimal('5.0'),
    }
    
    # Display names
    FEATURE_NAMES = {
        'product_description': 'Product Description Generator',
        'report_summary': 'AI Report Summary',
        'customer_insight': 'Customer Insight Query',
        'collection_message': 'Smart Collection Message',
        'credit_assessment': 'Credit Risk Assessment',
        'collection_analysis': 'Collection Priority Analysis',
        'inventory_forecast': 'Inventory Forecast',
        'portfolio_dashboard': 'Portfolio Health Dashboard',
    }
    
    @classmethod
    def check_credits(cls, business_id, feature: str) -> dict:
        """
        Check if business has enough credits for feature.
        Returns dict with status and balance info.
        """
        cost = cls.FEATURE_COSTS.get(feature)
        if not cost:
            raise ValueError(f"Unknown AI feature: {feature}")
        
        try:
            ai_credits = BusinessAICredits.objects.get(business_id=business_id)
            has_credits = ai_credits.has_sufficient_credits(cost)
            
            return {
                'has_credits': has_credits,
                'required': float(cost),
                'current_balance': float(ai_credits.balance),
                'shortfall': float(max(0, cost - ai_credits.balance)),
                'feature_name': cls.FEATURE_NAMES[feature]
            }
        except BusinessAICredits.DoesNotExist:
            return {
                'has_credits': False,
                'required': float(cost),
                'current_balance': 0.0,
                'shortfall': float(cost),
                'feature_name': cls.FEATURE_NAMES[feature]
            }
    
    @classmethod
    @transaction.atomic
    def charge_credits(
        cls,
        business_id,
        user_id,
        feature: str,
        actual_openai_cost_usd: float,
        input_tokens: int = 0,
        output_tokens: int = 0,
        response_time_ms: int = 0,
        request_data: dict = None,
        response_summary: dict = None
    ) -> dict:
        """
        Charge AI credits after successful API call.
        Returns transaction details.
        """
        cost = cls.FEATURE_COSTS.get(feature)
        if not cost:
            raise ValueError(f"Unknown AI feature: {feature}")
        
        # Get or create AI credits record
        ai_credits, created = BusinessAICredits.objects.select_for_update().get_or_create(
            business_id=business_id,
            defaults={'balance': Decimal('0.00')}
        )
        
        # Check sufficient credits
        if not ai_credits.has_sufficient_credits(cost):
            raise InsufficientCreditsError(
                f"Insufficient credits for {cls.FEATURE_NAMES[feature]}. "
                f"Required: {cost}, Available: {ai_credits.balance}"
            )
        
        # Deduct credits
        new_balance = ai_credits.deduct_credits(cost, feature)
        
        # Convert USD to GHS (approximate, use live rate in production)
        USD_TO_GHS = Decimal('16.00')  # Update with live rate
        actual_cost_ghs = Decimal(str(actual_openai_cost_usd)) * USD_TO_GHS
        
        # Log transaction
        transaction = AITransaction.objects.create(
            business_id=business_id,
            user_id=user_id,
            feature=feature,
            feature_display_name=cls.FEATURE_NAMES[feature],
            credits_charged=cost,
            actual_openai_cost=Decimal(str(actual_openai_cost_usd)),
            actual_openai_cost_ghs=actual_cost_ghs,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            response_time_ms=response_time_ms,
            request_data=request_data or {},
            response_summary=response_summary or {},
            success=True
        )
        
        # Check if balance is low
        low_credit_threshold = Decimal('10.0')
        send_low_credit_alert = new_balance < low_credit_threshold
        
        return {
            'success': True,
            'credits_charged': float(cost),
            'new_balance': float(new_balance),
            'transaction_id': str(transaction.id),
            'low_credit_warning': send_low_credit_alert,
            'profit_margin': float((cost - actual_cost_ghs) / cost * 100) if cost > 0 else 0
        }
    
    @classmethod
    def log_failed_transaction(
        cls,
        business_id,
        user_id,
        feature: str,
        error_message: str,
        request_data: dict = None
    ):
        """Log failed AI transaction (don't charge credits)"""
        cost = cls.FEATURE_COSTS.get(feature, Decimal('0.0'))
        
        AITransaction.objects.create(
            business_id=business_id,
            user_id=user_id,
            feature=feature,
            feature_display_name=cls.FEATURE_NAMES.get(feature, feature),
            credits_charged=Decimal('0.0'),  # No charge for failures
            actual_openai_cost=Decimal('0.0'),
            actual_openai_cost_ghs=Decimal('0.0'),
            success=False,
            error_message=error_message,
            request_data=request_data or {},
            response_time_ms=0
        )
    
    @classmethod
    def get_usage_stats(cls, business_id, days: int = 30):
        """Get AI usage statistics for business"""
        from datetime import timedelta
        from django.utils import timezone
        from django.db.models import Sum, Count, Avg
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        transactions = AITransaction.objects.filter(
            business_id=business_id,
            timestamp__gte=cutoff_date
        )
        
        stats = transactions.aggregate(
            total_credits_used=Sum('credits_charged'),
            total_requests=Count('id'),
            successful_requests=Count('id', filter=models.Q(success=True)),
            total_cost_ghs=Sum('actual_openai_cost_ghs'),
            avg_response_time=Avg('response_time_ms')
        )
        
        # Feature breakdown
        feature_usage = transactions.values('feature', 'feature_display_name').annotate(
            count=Count('id'),
            credits=Sum('credits_charged')
        ).order_by('-count')
        
        # Current balance
        try:
            ai_credits = BusinessAICredits.objects.get(business_id=business_id)
            current_balance = float(ai_credits.balance)
        except BusinessAICredits.DoesNotExist:
            current_balance = 0.0
        
        return {
            'period_days': days,
            'current_balance': current_balance,
            'total_credits_used': float(stats['total_credits_used'] or 0),
            'total_requests': stats['total_requests'] or 0,
            'successful_requests': stats['successful_requests'] or 0,
            'success_rate': (
                (stats['successful_requests'] / stats['total_requests'] * 100)
                if stats['total_requests'] else 0
            ),
            'total_cost_ghs': float(stats['total_cost_ghs'] or 0),
            'avg_response_time_ms': int(stats['avg_response_time'] or 0),
            'feature_breakdown': list(feature_usage),
            'most_used_feature': feature_usage[0] if feature_usage else None
        }
```

---

### 3. API Endpoints

Create `subscriptions/ai_views.py`:

```python
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from decimal import Decimal
from subscriptions.models import (
    BusinessAICredits,
    AICreditPurchase,
    AIMonthlyAddon
)
from subscriptions.ai_billing import AIBillingService


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_ai_credits(request):
    """Get AI credit balance for user's business"""
    business = request.user.business
    
    try:
        ai_credits = BusinessAICredits.objects.get(business=business)
        return Response({
            'balance': float(ai_credits.balance),
            'total_purchased': float(ai_credits.total_purchased),
            'total_used': float(ai_credits.total_used),
            'has_monthly_addon': ai_credits.has_monthly_ai_addon,
            'monthly_addon_details': {
                'price': float(ai_credits.monthly_ai_addon_amount),
                'credits': float(ai_credits.monthly_ai_credits),
                'next_renewal': ai_credits.next_ai_addon_renewal.isoformat() if ai_credits.next_ai_addon_renewal else None
            } if ai_credits.has_monthly_ai_addon else None
        })
    except BusinessAICredits.DoesNotExist:
        return Response({
            'balance': 0.0,
            'total_purchased': 0.0,
            'total_used': 0.0,
            'has_monthly_addon': False,
            'monthly_addon_details': None
        })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_ai_pricing(request):
    """Get AI credit pricing and feature costs"""
    return Response({
        'credit_packs': [
            {
                'type': 'STARTER',
                'name': 'Starter Pack',
                'price': 30.0,
                'credits': 30.0,
                'bonus_credits': 0.0,
                'total_credits': 30.0,
                'cost_per_credit': 1.0
            },
            {
                'type': 'VALUE',
                'name': 'Value Pack',
                'price': 80.0,
                'credits': 83.33,
                'bonus_credits': 16.67,
                'total_credits': 100.0,
                'cost_per_credit': 0.8,
                'savings': '20%',
                'recommended': True
            },
            {
                'type': 'PRO',
                'name': 'Pro Pack',
                'price': 180.0,
                'credits': 180.0,
                'bonus_credits': 70.0,
                'total_credits': 250.0,
                'cost_per_credit': 0.72,
                'savings': '39%'
            }
        ],
        'feature_costs': [
            {
                'feature': 'product_description',
                'name': 'Product Description Generator',
                'credits': 0.1,
                'description': 'Generate compelling product descriptions',
                'category': 'basic'
            },
            {
                'feature': 'report_summary',
                'name': 'AI Report Summary',
                'credits': 0.2,
                'description': 'Get AI insights from your reports',
                'category': 'basic'
            },
            {
                'feature': 'customer_insight',
                'name': 'Customer Insight Query',
                'credits': 0.5,
                'description': 'Ask questions about your customers',
                'category': 'basic'
            },
            {
                'feature': 'collection_message',
                'name': 'Smart Collection Message',
                'credits': 0.5,
                'description': 'AI-powered collection reminders',
                'category': 'premium',
                'popular': True
            },
            {
                'feature': 'credit_assessment',
                'name': 'Credit Risk Assessment',
                'credits': 3.0,
                'description': 'Analyze customer credit risk',
                'category': 'premium',
                'popular': True
            },
            {
                'feature': 'collection_analysis',
                'name': 'Collection Priority Analysis',
                'credits': 5.0,
                'description': 'Prioritize collections automatically',
                'category': 'premium'
            },
            {
                'feature': 'inventory_forecast',
                'name': 'Inventory Forecast',
                'credits': 4.0,
                'description': 'Predict inventory needs',
                'category': 'premium'
            }
        ],
        'monthly_addon': {
            'available': True,
            'price': 50.0,
            'credits': 100.0,
            'description': 'Add recurring AI credits to your subscription',
            'savings': '50% cheaper than buying individual packs'
        }
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def purchase_ai_credits(request):
    """Initiate AI credit purchase"""
    business = request.user.business
    pack_type = request.data.get('pack_type')  # STARTER, VALUE, PRO
    payment_method = request.data.get('payment_method', 'MOMO')
    
    # Pack configurations
    PACKS = {
        'STARTER': {'price': 30, 'credits': 30, 'bonus': 0},
        'VALUE': {'price': 80, 'credits': 83.33, 'bonus': 16.67},
        'PRO': {'price': 180, 'credits': 180, 'bonus': 70}
    }
    
    if pack_type not in PACKS:
        return Response(
            {'error': 'Invalid pack type'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    pack = PACKS[pack_type]
    
    # Create purchase record
    purchase = AICreditPurchase.objects.create(
        business=business,
        user=request.user,
        pack_type=pack_type,
        amount_paid=Decimal(str(pack['price'])),
        credits_purchased=Decimal(str(pack['credits'])),
        bonus_credits=Decimal(str(pack['bonus'])),
        total_credits=Decimal(str(pack['credits'] + pack['bonus'])),
        payment_method=payment_method,
        payment_reference=f"AI-{business.id}-{timezone.now().timestamp()}",
        status='PENDING'
    )
    
    # Initialize payment with Paystack/gateway
    # (Implementation depends on your payment gateway)
    payment_url = initiate_payment(
        amount=pack['price'],
        reference=purchase.payment_reference,
        callback_url=f"{settings.FRONTEND_URL}/ai-credits/payment-callback"
    )
    
    return Response({
        'purchase_id': str(purchase.id),
        'payment_reference': purchase.payment_reference,
        'payment_url': payment_url,
        'pack_details': {
            'type': pack_type,
            'price': pack['price'],
            'credits': pack['credits'],
            'bonus': pack['bonus'],
            'total_credits': pack['credits'] + pack['bonus']
        }
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_ai_payment(request):
    """Verify AI credit purchase payment"""
    reference = request.data.get('reference')
    
    try:
        purchase = AICreditPurchase.objects.get(payment_reference=reference)
        
        # Verify payment with gateway
        # (Implementation depends on your payment gateway)
        payment_verified = verify_payment_with_gateway(reference)
        
        if payment_verified:
            # Mark as successful and add credits
            new_balance = purchase.mark_as_successful()
            
            return Response({
                'success': True,
                'credits_added': float(purchase.total_credits),
                'new_balance': float(new_balance),
                'message': f'Successfully added {purchase.total_credits} AI credits!'
            })
        else:
            return Response(
                {'error': 'Payment verification failed'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    except AICreditPurchase.DoesNotExist:
        return Response(
            {'error': 'Purchase not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_ai_usage_stats(request):
    """Get AI usage statistics"""
    business = request.user.business
    days = int(request.query_params.get('days', 30))
    
    stats = AIBillingService.get_usage_stats(business.id, days)
    
    return Response(stats)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def subscribe_monthly_ai_addon(request):
    """Subscribe to monthly AI credits add-on"""
    business = request.user.business
    
    # Create monthly add-on
    addon = AIMonthlyAddon.objects.create(
        business=business,
        monthly_price=Decimal('50.00'),
        monthly_credits=Decimal('100.00'),
        start_date=timezone.now().date(),
        next_renewal_date=timezone.now().date() + timedelta(days=30),
        is_active=True
    )
    
    # Update AI credits record
    ai_credits, created = BusinessAICredits.objects.get_or_create(
        business=business,
        defaults={'balance': Decimal('0.00')}
    )
    ai_credits.has_monthly_ai_addon = True
    ai_credits.monthly_ai_addon_amount = addon.monthly_price
    ai_credits.monthly_ai_credits = addon.monthly_credits
    ai_credits.next_ai_addon_renewal = addon.next_renewal_date
    ai_credits.save()
    
    # Add initial credits immediately
    ai_credits.add_credits(addon.monthly_credits)
    
    return Response({
        'success': True,
        'addon_id': str(addon.id),
        'monthly_price': float(addon.monthly_price),
        'monthly_credits': float(addon.monthly_credits),
        'credits_added': float(addon.monthly_credits),
        'new_balance': float(ai_credits.balance),
        'next_renewal': addon.next_renewal_date.isoformat()
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def cancel_monthly_ai_addon(request):
    """Cancel monthly AI credits add-on"""
    business = request.user.business
    cancel_immediately = request.data.get('immediate', False)
    
    try:
        addon = AIMonthlyAddon.objects.get(business=business, is_active=True)
        
        if cancel_immediately:
            addon.is_active = False
            addon.cancelled_at = timezone.now()
            addon.end_date = timezone.now().date()
        else:
            # Cancel at period end
            addon.cancel_at_period_end = True
            addon.auto_renew = False
        
        addon.save()
        
        # Update AI credits record
        ai_credits = BusinessAICredits.objects.get(business=business)
        if cancel_immediately:
            ai_credits.has_monthly_ai_addon = False
            ai_credits.monthly_ai_addon_amount = Decimal('0.00')
            ai_credits.monthly_ai_credits = Decimal('0.00')
            ai_credits.next_ai_addon_renewal = None
            ai_credits.save()
        
        return Response({
            'success': True,
            'cancelled_immediately': cancel_immediately,
            'message': 'Cancelled immediately' if cancel_immediately else 'Will cancel at end of current period'
        })
    
    except AIMonthlyAddon.DoesNotExist:
        return Response(
            {'error': 'No active monthly add-on found'},
            status=status.HTTP_404_NOT_FOUND
        )
```

---

### 4. URL Configuration

Add to `subscriptions/urls.py`:

```python
from django.urls import path
from subscriptions import ai_views

urlpatterns = [
    # ... existing urls ...
    
    # AI Credits Management
    path('ai/credits/', ai_views.get_ai_credits, name='get_ai_credits'),
    path('ai/pricing/', ai_views.get_ai_pricing, name='get_ai_pricing'),
    path('ai/purchase/', ai_views.purchase_ai_credits, name='purchase_ai_credits'),
    path('ai/verify-payment/', ai_views.verify_ai_payment, name='verify_ai_payment'),
    path('ai/usage-stats/', ai_views.get_ai_usage_stats, name='get_ai_usage_stats'),
    
    # Monthly AI Add-on
    path('ai/addon/subscribe/', ai_views.subscribe_monthly_ai_addon, name='subscribe_monthly_ai_addon'),
    path('ai/addon/cancel/', ai_views.cancel_monthly_ai_addon, name='cancel_monthly_ai_addon'),
]
```

---

## 🎨 User Experience Flow

### First-Time AI User

```
1. User logs in → Sees "Try AI Features" banner
2. Clicks banner → Modal explains AI features with examples
3. "Start with 5 FREE credits" button → User gets free trial credits
4. User tries "Generate product description" → Sees result, loves it!
5. Credits depleted → Prompt: "Buy 30 more credits for GHS 30?"
6. User clicks "Buy Now" → Paystack MOMO payment
7. Payment success → Credits added instantly
8. User continues using AI features
```

### Existing User Discovery

```
1. User in Reports section → Sees "✨ Get AI Insights (0.2 credits)" button
2. Clicks → Modal: "You need AI credits to use this feature"
3. Shows pricing: Starter GHS 30, Value GHS 80 (recommended)
4. User buys Value Pack → 100 credits added
5. Uses AI Report Summary → "That's helpful!"
6. Uses AI Collection Messages → "This saves me hours!"
7. Becomes regular AI user
```

---

## 📊 Revenue Projections

### Conservative Scenario (10% AI Adoption)

```
Assumptions:
- 100 active subscribers
- 10 subscribers buy AI credits monthly
- Average: GHS 80/month (Value Pack)

Monthly AI Revenue:
10 × GHS 80 = GHS 800

Monthly AI Costs (optimized):
10 × GHS 24 (30% of revenue) = GHS 240

Monthly AI Profit:
GHS 800 - GHS 240 = GHS 560 (70% margin) ✅

Annual Additional Profit:
GHS 560 × 12 = GHS 6,720
```

### Optimistic Scenario (30% AI Adoption + Monthly Add-ons)

```
Assumptions:
- 100 active subscribers
- 20 buy prepaid credits (avg GHS 80/month)
- 10 subscribe to monthly add-on (GHS 50/month)

Monthly AI Revenue:
(20 × GHS 80) + (10 × GHS 50) = GHS 2,100

Monthly AI Costs:
(20 × GHS 24) + (10 × GHS 15) = GHS 630

Monthly AI Profit:
GHS 2,100 - GHS 630 = GHS 1,470 (70% margin) ✅

Annual Additional Profit:
GHS 1,470 × 12 = GHS 17,640
```

---

## 🚦 Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
- [ ] Create database models (BusinessAICredits, AITransaction, AICreditPurchase)
- [ ] Implement AIBillingService
- [ ] Create AI credit management API endpoints
- [ ] Set up OpenAI API configuration
- [ ] Write unit tests

### Phase 2: Payment Integration (Week 3)
- [ ] Integrate credit purchase with Paystack/MOMO
- [ ] Implement payment verification
- [ ] Create payment webhook handler
- [ ] Test end-to-end payment flow

### Phase 3: First AI Feature (Week 4)
- [ ] Implement Product Description Generator endpoint
- [ ] Add credit check and charging logic
- [ ] Create caching layer
- [ ] Frontend integration

### Phase 4: Premium AI Features (Week 5-7)
- [ ] Implement Credit Risk Assessment
- [ ] Implement Collection Message Generator
- [ ] Implement Collection Priority Analysis
- [ ] Add comprehensive error handling

### Phase 5: Optimization & Launch (Week 8)
- [ ] Performance optimization (caching, batching)
- [ ] Cost monitoring dashboard
- [ ] Usage analytics
- [ ] Marketing materials
- [ ] Soft launch to beta users

---

## 🎯 Success Metrics

### Technical KPIs
- ✅ AI API response time: < 3 seconds
- ✅ Credit transaction success rate: > 99%
- ✅ Payment integration success rate: > 98%
- ✅ Cache hit rate: > 40%

### Business KPIs
- ✅ AI feature adoption: > 15% of subscribers (Year 1)
- ✅ AI credit purchase rate: > 10% monthly
- ✅ Average revenue per AI user: > GHS 60/month
- ✅ AI profit margin: > 60%

### User Satisfaction
- ✅ Feature usefulness rating: > 4.5/5
- ✅ User retention (AI users vs non-AI): +20%
- ✅ NPS score for AI features: > 50

---

## ❓ Beginner's AI Integration Guide

### What is OpenAI and Why Use It?

**OpenAI** provides AI models (like GPT-4) that can:
- Understand natural language
- Generate human-like text
- Analyze data and provide insights
- Make predictions based on patterns

You'll use their **API** (Application Programming Interface) to send data and get AI-generated responses.

### How It Works (Simple Explanation)

```
Your Backend → Send Request → OpenAI API
                 ↓
            "Analyze this customer:
             - Payment history: [...]
             - Purchase patterns: [...]
             Should I extend credit?"
                 ↓
         OpenAI processes with GPT-4
                 ↓
Your Backend ← Receive Response ← OpenAI API
                 ↓
            "RECOMMENDATION: Approve GHS 3,000
             REASON: Excellent payment record
             RISK SCORE: 72/100"
```

### Getting Started Checklist

- [ ] **Step 1:** Create OpenAI account at https://platform.openai.com
- [ ] **Step 2:** Add payment method (credit card required)
- [ ] **Step 3:** Get API key from dashboard
- [ ] **Step 4:** Set budget limits (start with $50/month)
- [ ] **Step 5:** Install OpenAI Python library: `pip install openai`
- [ ] **Step 6:** Test basic API call (see example below)

### Basic API Call Example

```python
from openai import OpenAI
import os

# Initialize client
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Simple request
response = client.chat.completions.create(
    model="gpt-4o-mini",  # Cheapest model for testing
    messages=[
        {
            "role": "system",
            "content": "You are a business assistant."
        },
        {
            "role": "user",
            "content": "Generate a product description for: Samsung 55-inch TV"
        }
    ],
    temperature=0.7,
    max_tokens=150
)

# Get response
print(response.choices[0].message.content)

# Check cost
print(f"Tokens used: {response.usage.total_tokens}")
```

### Cost Management Tips

1. **Start small:** Test with gpt-4o-mini ($0.0006/1K tokens) before using GPT-4
2. **Set limits:** Configure budget alerts in OpenAI dashboard
3. **Cache aggressively:** Don't repeat identical requests
4. **Batch requests:** Analyze multiple items in one API call
5. **Monitor usage:** Track costs daily, not monthly

### Common Pitfalls to Avoid

❌ **Don't:** Send full customer database to OpenAI  
✅ **Do:** Send only aggregated, anonymized data

❌ **Don't:** Use GPT-4 for simple tasks  
✅ **Do:** Use gpt-4o-mini (50x cheaper) for basic features

❌ **Don't:** Call API for every button click  
✅ **Do:** Cache results and batch process

❌ **Don't:** Expose your API key in frontend code  
✅ **Do:** Keep API key secret on backend only

### Security Best Practices

```python
# ❌ BAD - Sending sensitive customer data
prompt = f"Analyze customer: {customer.name}, Phone: {customer.phone_number}"

# ✅ GOOD - Anonymized data
prompt = f"""
Analyze customer:
- Customer ID: {hash(customer.id)}
- Payment history: {customer.payment_summary}
- Purchase frequency: {customer.purchase_frequency}
"""

# ❌ BAD - API key in code
client = OpenAI(api_key="sk-proj-abc123...")

# ✅ GOOD - API key from environment
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
```

---

## 🤝 Support & Questions

As a beginner, you'll have questions. Here's how to get help:

### OpenAI Resources
- **Documentation:** https://platform.openai.com/docs
- **Community Forum:** https://community.openai.com
- **Pricing Calculator:** https://openai.com/pricing
- **API Status:** https://status.openai.com

### Common Questions

**Q: How much will this cost me?**  
A: Start with $50/month budget. With optimization, expect $0.20-0.50 per user per month.

**Q: What if OpenAI goes down?**  
A: Implement graceful fallback - show cached results or "AI temporarily unavailable" message.

**Q: Can I use a different AI provider?**  
A: Yes! You can swap to Anthropic (Claude), Google (Gemini), or others with minimal code changes.

**Q: How do I know if I'm being charged correctly?**  
A: OpenAI dashboard shows real-time usage. Cross-check with your AITransaction logs.

**Q: What's the difference between GPT-4 and GPT-4o-mini?**  
A: GPT-4 is smarter (better for complex analysis), GPT-4o-mini is 50x cheaper (good for simple tasks).

---

## 📝 Next Steps

1. **Review this document** with your team
2. **Ask clarifying questions** (no question is stupid!)
3. **Set up OpenAI account** and test basic API call
4. **Start with Phase 1** (database models)
5. **Test with one simple feature** (Product Description Generator)
6. **Gradually add more features** as you gain confidence

---

**Remember:** AI integration is optional, incremental, and profitable. Start small, learn, optimize, scale! 🚀

**Questions?** Schedule a pairing session to walk through implementation together.

---

**END OF DOCUMENT**
