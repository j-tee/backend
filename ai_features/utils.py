"""
AI Features Utilities
Handles credit management, GDPR compliance, and safe AI processing
"""

from decimal import Decimal
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from datetime import timedelta
import logging
import hashlib

logger = logging.getLogger(__name__)


class InsufficientCreditsError(Exception):
    """Raised when business doesn't have enough AI credits"""
    pass


class AIBudgetCapReachedError(Exception):
    """Raised when business reaches daily/monthly budget cap"""
    pass


def sanitize_ai_request_data(data):
    """
    Remove PII from AI request data before storing (GDPR compliance)
    
    Args:
        data: Dictionary containing request data
    
    Returns:
        Sanitized dictionary with PII removed
    """
    if not isinstance(data, dict):
        return data
    
    # List of sensitive fields to redact
    sensitive_fields = [
        'name', 'full_name', 'first_name', 'last_name',
        'email', 'phone', 'phone_number', 'mobile',
        'address', 'street', 'city', 'postal_code',
        'ssn', 'national_id', 'passport',
        'credit_card', 'bank_account',
        'password', 'token', 'api_key'
    ]
    
    sanitized = {}
    for key, value in data.items():
        # Check if key contains sensitive information
        key_lower = key.lower()
        is_sensitive = any(field in key_lower for field in sensitive_fields)
        
        if is_sensitive:
            sanitized[key] = '[REDACTED]'
        elif isinstance(value, dict):
            # Recursively sanitize nested dictionaries
            sanitized[key] = sanitize_ai_request_data(value)
        elif isinstance(value, list):
            # Sanitize lists
            sanitized[key] = [
                sanitize_ai_request_data(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            sanitized[key] = value
    
    return sanitized


def anonymize_user_identifier(user_id):
    """
    Create pseudonymous identifier for GDPR compliance
    
    Args:
        user_id: User UUID
    
    Returns:
        Anonymized hash string
    """
    from django.conf import settings
    
    # Use secret salt for hashing
    salt = getattr(settings, 'ANONYMIZATION_SALT', settings.SECRET_KEY)
    combined = f"{user_id}{salt}".encode()
    return hashlib.sha256(combined).hexdigest()[:16]


def process_ai_request_with_reservation(business, feature, estimated_cost, processor_func):
    """
    Safely process AI request with credit reservation and rollback
    
    Args:
        business: Business model instance
        feature: AI feature name (e.g., 'customer_insight')
        estimated_cost: Estimated cost in credits
        processor_func: Function that processes the AI request
    
    Returns:
        AI response from processor_func
    
    Raises:
        InsufficientCreditsError: Not enough credits
        AIBudgetCapReachedError: Budget cap reached
    """
    from ai_features.models import BusinessAICredits, AITransaction
    from django.conf import settings
    
    # Check daily budget cap
    today = timezone.now().date()
    daily_usage = AITransaction.objects.filter(
        business=business,
        timestamp__date=today,
        success=True
    ).aggregate(total=models.Sum('credits_used'))['total'] or Decimal('0')
    
    daily_cap = settings.AI_BUDGET_CAPS.get('per_business_daily', Decimal('10.0'))
    if daily_usage + estimated_cost > daily_cap:
        raise AIBudgetCapReachedError(
            f"Daily budget cap reached. Used: {daily_usage}, Cap: {daily_cap}"
        )
    
    # Reserve credits with pessimistic locking
    with transaction.atomic():
        try:
            credits = BusinessAICredits.objects.select_for_update().get(
                business=business,
                is_active=True,
                expires_at__gt=timezone.now()
            )
        except BusinessAICredits.DoesNotExist:
            raise InsufficientCreditsError("No active credits found for business")
        
        # Add 20% buffer for estimation errors
        reserved_amount = estimated_cost * Decimal('1.2')
        
        if credits.balance < reserved_amount:
            raise InsufficientCreditsError(
                f"Insufficient credits. Have {credits.balance}, need {reserved_amount}"
            )
        
        # Reserve credits
        credits.balance = F('balance') - reserved_amount
        credits.save()
        credits.refresh_from_db()
    
    # Process AI request outside transaction
    try:
        start_time = timezone.now()
        response = processor_func()
        processing_time = (timezone.now() - start_time).total_seconds() * 1000
        
        # Calculate actual cost
        actual_cost = response.get('credits_used', estimated_cost)
        
        # Refund difference
        with transaction.atomic():
            credits = BusinessAICredits.objects.select_for_update().get(
                business=business,
                is_active=True
            )
            refund = reserved_amount - actual_cost
            credits.balance = F('balance') + refund
            credits.save()
        
        # Log successful transaction
        AITransaction.objects.create(
            business=business,
            user=response.get('user'),
            feature=feature,
            credits_used=actual_cost,
            cost_to_us=response.get('cost_to_us', Decimal('0')),
            tokens_used=response.get('tokens_used', 0),
            success=True,
            request_data=sanitize_ai_request_data(response.get('request_data', {})),
            response_summary=response.get('response_summary', '')[:500],  # Limit size
            processing_time_ms=int(processing_time)
        )
        
        return response
    
    except Exception as e:
        # Rollback reservation
        with transaction.atomic():
            credits = BusinessAICredits.objects.select_for_update().get(
                business=business,
                is_active=True
            )
            credits.balance = F('balance') + reserved_amount
            credits.save()
        
        # Log failed transaction
        AITransaction.objects.create(
            business=business,
            feature=feature,
            credits_used=Decimal('0'),
            cost_to_us=Decimal('0'),
            success=False,
            error_message=str(e)[:1000],
            request_data={}
        )
        
        raise


def check_and_alert_low_credits(business):
    """
    Check credit balance and send alerts if low
    
    Args:
        business: Business model instance
    """
    from ai_features.models import BusinessAICredits, AIUsageAlert
    
    try:
        credits = BusinessAICredits.objects.filter(
            business=business,
            is_active=True,
            expires_at__gt=timezone.now()
        ).first()
        
        if not credits:
            return
        
        # Define thresholds
        thresholds = {
            'depleted': Decimal('0'),
            'low_balance': Decimal('10.0'),
        }
        
        for alert_type, threshold in thresholds.items():
            if credits.balance <= threshold:
                # Check if alert already sent recently
                recent_alert = AIUsageAlert.objects.filter(
                    business=business,
                    alert_type=alert_type,
                    sent_at__gte=timezone.now() - timedelta(days=1)
                ).exists()
                
                if not recent_alert:
                    AIUsageAlert.objects.create(
                        business=business,
                        alert_type=alert_type,
                        current_balance=credits.balance,
                        threshold=threshold
                    )
                    
                    # Send notification (implement based on your notification system)
                    logger.warning(
                        f"AI Credits {alert_type} for business {business.name}. "
                        f"Balance: {credits.balance}"
                    )
    
    except Exception as e:
        logger.error(f"Error checking AI credits: {e}")


def cleanup_expired_ai_data():
    """
    Cleanup expired AI transaction data for GDPR compliance
    Run as periodic Celery task
    """
    from ai_features.models import AITransaction
    
    # Delete transactions older than 90 days
    retention_date = timezone.now() - timedelta(days=90)
    
    expired = AITransaction.objects.filter(
        timestamp__lt=retention_date
    )
    
    count = expired.count()
    if count > 0:
        expired.delete()
        logger.info(f"Deleted {count} expired AI transactions (GDPR retention)")
    
    return count


def handle_gdpr_deletion_request(business):
    """
    Handle GDPR right to erasure request
    
    Args:
        business: Business model instance
    """
    from ai_features.models import AITransaction, BusinessAICredits, AICreditPurchase
    
    with transaction.atomic():
        # Anonymize AI transactions (keep for billing/audit)
        AITransaction.objects.filter(business=business).update(
            user=None,
            request_data={'redacted': True, 'reason': 'GDPR_DELETION'},
            response_summary='[DELETED PER GDPR REQUEST]'
        )
        
        # Keep credit balances for financial records
        # But anonymize user references in purchases
        AICreditPurchase.objects.filter(business=business).update(
            user=None,
            notes=F('notes') + ' [USER DATA DELETED PER GDPR]'
        )
        
        logger.info(f"Processed GDPR deletion for business {business.id}")
