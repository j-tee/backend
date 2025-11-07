"""
AI Billing Service
Handles AI credit checking, charging, and validation for all AI features.
"""

from decimal import Decimal
from typing import Optional, Dict, Any
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Count, Avg, Q
from django.core.cache import cache
from ai_features.models import BusinessAICredits, AITransaction, AICreditPurchase, AIUsageAlert
from accounts.models import Business


class InsufficientCreditsException(Exception):
    """Raised when business doesn't have enough AI credits"""
    pass


class AIBillingService:
    """Handle AI credit charging and validation"""
    
    # Credit costs for each feature
    FEATURE_COSTS = {
        # Smart Collections (Priority 1)
        'credit_assessment': Decimal('3.00'),
        'collection_priority': Decimal('5.00'),
        'collection_message': Decimal('0.50'),
        'portfolio_dashboard': Decimal('5.00'),
        'payment_prediction': Decimal('1.00'),
        
        # Customer Insights (Priority 2)
        'customer_insight': Decimal('0.50'),
        'natural_language_query': Decimal('0.50'),
        
        # Product Features (Priority 3)
        'product_description': Decimal('0.10'),
        
        # Reports (Priority 4)
        'report_narrative': Decimal('0.20'),
        
        # Inventory (Priority 5)
        'inventory_forecast': Decimal('4.00'),
    }
    
    # Low credit alert thresholds
    LOW_CREDIT_THRESHOLD = Decimal('10.00')
    DEPLETED_THRESHOLD = Decimal('1.00')
    
    @classmethod
    def get_feature_cost(cls, feature: str) -> Decimal:
        """Get the credit cost for a feature"""
        return cls.FEATURE_COSTS.get(feature, Decimal('0.50'))
    
    @classmethod
    def get_credit_balance(cls, business_id: str) -> Decimal:
        """Get current credit balance for a business"""
        # Check cache first
        cache_key = f"ai_credits_balance_{business_id}"
        cached_balance = cache.get(cache_key)
        if cached_balance is not None:
            return Decimal(str(cached_balance))
        
        # Get active credits
        credits = BusinessAICredits.objects.filter(
            business_id=business_id,
            is_active=True,
            expires_at__gt=timezone.now()
        ).first()
        
        balance = credits.balance if credits else Decimal('0.00')
        
        # Cache for 5 minutes
        cache.set(cache_key, str(balance), 300)
        
        return balance
    
    @classmethod
    def check_credits(cls, business_id: str, feature: str) -> Dict[str, Any]:
        """
        Check if business has enough credits for a feature
        Returns dict with status and details
        """
        balance = cls.get_credit_balance(business_id)
        cost = cls.get_feature_cost(feature)
        
        has_enough = balance >= cost
        
        return {
            'has_sufficient_credits': has_enough,
            'current_balance': float(balance),
            'required_credits': float(cost),
            'shortage': float(cost - balance) if not has_enough else 0.0
        }
    
    @classmethod
    @transaction.atomic
    def charge_credits(
        cls, 
        business_id: str, 
        feature: str, 
        actual_openai_cost: Decimal,
        tokens_used: int = 0,
        user_id: Optional[str] = None,
        request_data: Optional[Dict] = None,
        response_summary: str = "",
        processing_time_ms: int = 0
    ) -> Dict[str, Any]:
        """
        Deduct credits after successful AI call
        Returns dict with transaction details and updated balance
        """
        # Get active credits (lock for update)
        credits = BusinessAICredits.objects.select_for_update().filter(
            business_id=business_id,
            is_active=True,
            expires_at__gt=timezone.now()
        ).first()
        
        if not credits:
            raise InsufficientCreditsException("No active AI credits found")
        
        cost = cls.get_feature_cost(feature)
        
        if credits.balance < cost:
            raise InsufficientCreditsException(
                f"Insufficient credits. Required: {cost}, Available: {credits.balance}"
            )
        
        # Deduct credits
        old_balance = credits.balance
        credits.balance -= cost
        credits.save()
        
        # Clear cache
        cache_key = f"ai_credits_balance_{business_id}"
        cache.delete(cache_key)
        
        # Log transaction
        transaction_record = AITransaction.objects.create(
            business_id=business_id,
            user_id=user_id,
            feature=feature,
            credits_used=cost,
            cost_to_us=actual_openai_cost,
            tokens_used=tokens_used,
            success=True,
            request_data=request_data or {},
            response_summary=response_summary[:500],  # Limit to 500 chars
            processing_time_ms=processing_time_ms
        )
        
        # Check if we need to send low credit alert
        cls._check_and_send_alerts(business_id, credits.balance)
        
        return {
            'transaction_id': str(transaction_record.id),
            'old_balance': float(old_balance),
            'new_balance': float(credits.balance),
            'credits_charged': float(cost),
            'actual_cost_ghs': float(actual_openai_cost)
        }
    
    @classmethod
    def log_failed_transaction(
        cls,
        business_id: str,
        feature: str,
        error_message: str,
        user_id: Optional[str] = None,
        request_data: Optional[Dict] = None
    ) -> None:
        """Log a failed AI transaction (no credit charge)"""
        AITransaction.objects.create(
            business_id=business_id,
            user_id=user_id,
            feature=feature,
            credits_used=Decimal('0.00'),
            cost_to_us=Decimal('0.00'),
            tokens_used=0,
            success=False,
            error_message=error_message[:1000],
            request_data=request_data or {}
        )
    
    @classmethod
    @transaction.atomic
    def purchase_credits(
        cls,
        business_id: str,
        amount_paid: Decimal,
        credits_purchased: Decimal,
        payment_reference: str,
        payment_method: str = 'mobile_money',
        user_id: Optional[str] = None,
        bonus_credits: Decimal = Decimal('0.00')
    ) -> Dict[str, Any]:
        """
        Process credit purchase and add to business balance
        Returns purchase record and updated balance
        """
        # Calculate expiry (6 months from now)
        expires_at = timezone.now() + timedelta(days=180)
        
        # Create purchase record
        purchase = AICreditPurchase.objects.create(
            business_id=business_id,
            user_id=user_id,
            amount_paid=amount_paid,
            credits_purchased=credits_purchased,
            bonus_credits=bonus_credits,
            payment_reference=payment_reference,
            payment_method=payment_method,
            payment_status='completed',
            completed_at=timezone.now()
        )
        
        # Add credits to business
        total_credits = credits_purchased + bonus_credits
        
        # Get or create credit record
        credits, created = BusinessAICredits.objects.get_or_create(
            business_id=business_id,
            is_active=True,
            defaults={
                'balance': Decimal('0.00'),
                'expires_at': expires_at
            }
        )
        
        # Add new credits
        credits.balance += total_credits
        credits.expires_at = max(credits.expires_at, expires_at)  # Extend expiry if needed
        credits.save()
        
        # Clear cache
        cache_key = f"ai_credits_balance_{business_id}"
        cache.delete(cache_key)
        
        return {
            'purchase_id': str(purchase.id),
            'credits_added': float(total_credits),
            'new_balance': float(credits.balance),
            'expires_at': credits.expires_at.isoformat()
        }
    
    @classmethod
    def get_usage_stats(cls, business_id: str, days: int = 30) -> Dict[str, Any]:
        """Get AI usage statistics for a business"""
        from datetime import timedelta
        from django.db.models import Sum, Count, Avg
        
        since_date = timezone.now() - timedelta(days=days)
        
        transactions = AITransaction.objects.filter(
            business_id=business_id,
            timestamp__gte=since_date
        )
        
        # Aggregate stats
        stats = transactions.aggregate(
            total_requests=Count('id'),
            successful_requests=Count('id', filter=Q(success=True)),
            total_credits_used=Sum('credits_used'),
            total_cost_to_us=Sum('cost_to_us'),
            avg_processing_time=Avg('processing_time_ms')
        )
        
        # Feature breakdown
        feature_usage = transactions.values('feature').annotate(
            count=Count('id'),
            credits=Sum('credits_used')
        ).order_by('-count')
        
        # Current balance
        current_balance = cls.get_credit_balance(business_id)
        
        return {
            'period_days': days,
            'current_balance': float(current_balance),
            'total_requests': stats['total_requests'] or 0,
            'successful_requests': stats['successful_requests'] or 0,
            'failed_requests': (stats['total_requests'] or 0) - (stats['successful_requests'] or 0),
            'total_credits_used': float(stats['total_credits_used'] or 0),
            'total_cost_ghs': float(stats['total_cost_to_us'] or 0),
            'avg_processing_time_ms': int(stats['avg_processing_time'] or 0),
            'feature_breakdown': [
                {
                    'feature': item['feature'],
                    'count': item['count'],
                    'credits_used': float(item['credits'])
                }
                for item in feature_usage
            ]
        }
    
    @classmethod
    def _check_and_send_alerts(cls, business_id: str, current_balance: Decimal) -> None:
        """Check if we need to send low credit alerts"""
        from django.db import models as django_models
        
        # Check if we already sent an alert recently (within 24 hours)
        recent_alert = AIUsageAlert.objects.filter(
            business_id=business_id,
            sent_at__gte=timezone.now() - timedelta(hours=24)
        ).first()
        
        if recent_alert:
            return  # Don't spam alerts
        
        # Determine alert type
        alert_type = None
        threshold = None
        
        if current_balance <= cls.DEPLETED_THRESHOLD:
            alert_type = 'depleted'
            threshold = cls.DEPLETED_THRESHOLD
        elif current_balance <= cls.LOW_CREDIT_THRESHOLD:
            alert_type = 'low_balance'
            threshold = cls.LOW_CREDIT_THRESHOLD
        
        if alert_type:
            AIUsageAlert.objects.create(
                business_id=business_id,
                alert_type=alert_type,
                current_balance=current_balance,
                threshold=threshold
            )
            
            # TODO: Send actual notification (email/SMS)
            # This would integrate with your notification system
