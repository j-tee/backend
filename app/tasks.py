"""
Celery tasks for POS Backend
Includes periodic tasks for GDPR compliance and maintenance
"""

from celery import shared_task
from celery.schedules import crontab
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task
def cleanup_expired_ai_transactions():
    """
    GDPR Compliance: Delete AI transactions older than 90 days
    Runs daily at 2 AM
    """
    from ai_features.models import AITransaction
    
    cutoff_date = timezone.now()
    expired = AITransaction.objects.filter(retention_until__lt=cutoff_date)
    
    count = expired.count()
    if count > 0:
        expired.delete()
        logger.info(f"[GDPR] Deleted {count} expired AI transactions")
    else:
        logger.debug("[GDPR] No expired AI transactions to delete")
    
    return count


@shared_task
def check_low_ai_credits():
    """
    Check for businesses with low AI credits and send alerts
    Runs every 6 hours
    """
    from ai_features.utils import check_and_alert_low_credits
    from accounts.models import Business
    
    businesses = Business.objects.filter(is_active=True)
    alerts_sent = 0
    
    for business in businesses:
        try:
            check_and_alert_low_credits(business)
            alerts_sent += 1
        except Exception as e:
            logger.error(f"Error checking credits for {business.name}: {e}")
    
    logger.info(f"Checked AI credits for {businesses.count()} businesses, sent {alerts_sent} alerts")
    return alerts_sent


@shared_task
def cleanup_expired_subscriptions():
    """
    Update expired subscriptions status
    Runs daily at 3 AM
    """
    from subscriptions.models import Subscription
    
    expired = Subscription.objects.filter(
        status__in=['ACTIVE', 'TRIAL'],
        end_date__lt=timezone.now().date()
    )
    
    count = expired.update(status='EXPIRED')
    logger.info(f"Marked {count} subscriptions as expired")
    
    return count


@shared_task
def cleanup_expired_stock_reservations():
    """
    Release expired stock reservations (older than 30 minutes)
    Runs every 15 minutes
    """
    from sales.models import StockReservation
    
    cutoff = timezone.now() - timedelta(minutes=30)
    expired = StockReservation.objects.filter(
        reserved_until__lt=cutoff,
        released=False
    )
    
    count = 0
    for reservation in expired:
        try:
            reservation.release()
            count += 1
        except Exception as e:
            logger.error(f"Error releasing reservation {reservation.id}: {e}")
    
    logger.info(f"Released {count} expired stock reservations")
    return count


@shared_task
def check_payment_gateway_health():
    """
    Check payment gateway circuit breaker status
    Runs every 5 minutes
    """
    from subscriptions.payment_gateway import circuit_breaker
    
    gateways = ['paystack', 'stripe']
    status = {}
    
    for gateway in gateways:
        is_available = circuit_breaker.is_available(gateway)
        failures = circuit_breaker.failures.get(gateway, 0)
        
        status[gateway] = {
            'available': is_available,
            'failures': failures
        }
        
        if not is_available:
            logger.warning(
                f"Payment gateway {gateway} circuit breaker OPEN "
                f"({failures} failures)"
            )
    
    return status


@shared_task
def send_subscription_expiry_reminders():
    """
    Send reminders for subscriptions expiring in 3, 7, and 14 days
    Runs daily at 9 AM
    """
    from subscriptions.models import Subscription, Alert
    from datetime import date, timedelta
    
    reminder_days = [3, 7, 14]
    alerts_created = 0
    
    for days in reminder_days:
        expiry_date = date.today() + timedelta(days=days)
        
        subscriptions = Subscription.objects.filter(
            status='ACTIVE',
            end_date=expiry_date,
            auto_renew=False  # Only alert non-auto-renewing
        )
        
        for subscription in subscriptions:
            # Check if alert already sent
            existing = Alert.objects.filter(
                subscription=subscription,
                alert_type='SUBSCRIPTION_EXPIRING',
                created_at__date=date.today()
            ).exists()
            
            if not existing:
                Alert.objects.create(
                    subscription=subscription,
                    alert_type='SUBSCRIPTION_EXPIRING',
                    priority='HIGH' if days <= 3 else 'MEDIUM',
                    title=f'Subscription Expiring in {days} Days',
                    message=f'Your subscription will expire on {expiry_date}. Please renew to continue using POS features.'
                )
                alerts_created += 1
    
    logger.info(f"Created {alerts_created} subscription expiry reminders")
    return alerts_created


# Celery Beat Schedule
# Add to app/celery.py:
"""
from celery.schedules import crontab

app.conf.beat_schedule = {
    'cleanup-expired-ai-transactions': {
        'task': 'app.tasks.cleanup_expired_ai_transactions',
        'schedule': crontab(hour=2, minute=0),  # 2 AM daily
    },
    'check-low-ai-credits': {
        'task': 'app.tasks.check_low_ai_credits',
        'schedule': crontab(hour='*/6'),  # Every 6 hours
    },
    'cleanup-expired-subscriptions': {
        'task': 'app.tasks.cleanup_expired_subscriptions',
        'schedule': crontab(hour=3, minute=0),  # 3 AM daily
    },
    'cleanup-expired-stock-reservations': {
        'task': 'app.tasks.cleanup_expired_stock_reservations',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
    'check-payment-gateway-health': {
        'task': 'app.tasks.check_payment_gateway_health',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
    },
    'send-subscription-expiry-reminders': {
        'task': 'app.tasks.send_subscription_expiry_reminders',
        'schedule': crontab(hour=9, minute=0),  # 9 AM daily
    },
}
"""
