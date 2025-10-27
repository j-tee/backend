"""
Celery Tasks for Subscription Management
Automated background tasks for renewals, expirations, and notifications
"""
from celery import shared_task
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta
from decimal import Decimal
import logging

from .models import Subscription, Alert, Invoice, SubscriptionPayment
from .payment_gateways import get_payment_gateway, PaymentGatewayError

logger = logging.getLogger(__name__)


@shared_task
def check_trial_expirations():
    """
    Check for trials expiring in 3 days and send alerts
    Run daily
    """
    today = timezone.now().date()
    three_days = today + timedelta(days=3)
    
    expiring_trials = Subscription.objects.filter(
        is_trial=True,
        trial_end_date=three_days,
        status='TRIAL'
    )
    
    for subscription in expiring_trials:
        # Create alert
        Alert.objects.get_or_create(
            subscription=subscription,
            alert_type='TRIAL_ENDING',
            defaults={
                'priority': 'HIGH',
                'title': 'Trial Ending Soon',
                'message': f'Your trial will end in 3 days on {subscription.trial_end_date}. Please add a payment method to continue using the service.',
                'metadata': {
                    'trial_end_date': str(subscription.trial_end_date),
                    'plan_name': subscription.plan.name
                }
            }
        )
    
    logger.info(f"Checked {expiring_trials.count()} expiring trials")
    return expiring_trials.count()


@shared_task
def process_trial_expirations():
    """
    Convert expired trials to inactive or paid subscriptions
    Run daily
    """
    today = timezone.now().date()
    
    expired_trials = Subscription.objects.filter(
        is_trial=True,
        trial_end_date__lt=today,
        status='TRIAL'
    )
    
    converted = 0
    for subscription in expired_trials:
        # Check if payment was made
        recent_payment = subscription.payments.filter(
            status='SUCCESSFUL',
            payment_date__gte=subscription.trial_end_date
        ).exists()
        
        if recent_payment:
            subscription.status = 'ACTIVE'
            subscription.is_trial = False
        else:
            subscription.status = 'INACTIVE'
        
        subscription.save()
        
        # Create alert
        Alert.objects.create(
            subscription=subscription,
            alert_type='TRIAL_ENDING' if subscription.status == 'INACTIVE' else 'SUBSCRIPTION_ACTIVATED',
            priority='CRITICAL' if subscription.status == 'INACTIVE' else 'HIGH',
            title='Trial Expired' if subscription.status == 'INACTIVE' else 'Subscription Activated',
            message=f'Your trial has expired. {"Please subscribe to continue." if subscription.status == "INACTIVE" else "Your subscription is now active."}',
        )
        converted += 1
    
    logger.info(f"Processed {converted} expired trials")
    return converted


@shared_task
def check_subscription_expirations():
    """
    Check for subscriptions expiring in 7 days and send reminders
    Run daily
    """
    today = timezone.now().date()
    seven_days = today + timedelta(days=7)
    
    expiring_soon = Subscription.objects.filter(
        end_date__range=[today + timedelta(days=6), seven_days],
        status__in=['ACTIVE', 'PAST_DUE'],
        auto_renew=False
    )
    
    for subscription in expiring_soon:
        days_left = (subscription.end_date - today).days
        
        # Create alert
        Alert.objects.get_or_create(
            subscription=subscription,
            alert_type='SUBSCRIPTION_EXPIRING',
            defaults={
                'priority': 'HIGH',
                'title': 'Subscription Expiring Soon',
                'message': f'Your subscription will expire in {days_left} days on {subscription.end_date}. {"Enable auto-renewal or make a payment to continue." if not subscription.auto_renew else ""}',
                'metadata': {
                    'days_left': days_left,
                    'end_date': str(subscription.end_date)
                }
            }
        )
    
    logger.info(f"Checked {expiring_soon.count()} expiring subscriptions")
    return expiring_soon.count()


@shared_task
def process_subscription_expirations():
    """
    Mark expired subscriptions as EXPIRED
    Run daily
    """
    today = timezone.now().date()
    grace_period_end = today - timedelta(days=3)
    
    # Expire subscriptions that are past grace period
    expired = Subscription.objects.filter(
        Q(end_date__lt=grace_period_end) |
        Q(end_date__lt=today, status='PAST_DUE'),
        status__in=['ACTIVE', 'PAST_DUE'],
        auto_renew=False
    )
    
    count = 0
    for subscription in expired:
        subscription.status = 'EXPIRED'
        subscription.save()
        
        # Create alert
        Alert.objects.create(
            subscription=subscription,
            alert_type='SUBSCRIPTION_EXPIRED',
            priority='CRITICAL',
            title='Subscription Expired',
            message='Your subscription has expired. Please renew to regain access.',
            metadata={'expired_date': str(subscription.end_date)}
        )
        count += 1
    
    logger.info(f"Expired {count} subscriptions")
    return count


@shared_task
def process_auto_renewals():
    """
    Process automatic subscription renewals
    Run daily
    """
    today = timezone.now().date()
    tomorrow = today + timedelta(days=1)
    
    # Get subscriptions due for renewal
    renewals = Subscription.objects.filter(
        next_billing_date__lte=tomorrow,
        auto_renew=True,
        status__in=['ACTIVE', 'TRIAL'],
        cancel_at_period_end=False
    )
    
    processed = 0
    failed = 0
    
    for subscription in renewals:
        try:
            # Try to process payment automatically
            if subscription.payment_method in ['PAYSTACK', 'STRIPE']:
                # Attempt automatic payment
                # Note: This requires saved payment methods (card tokenization)
                # For now, we'll just create an invoice and send notification
                
                # Create invoice
                invoice_number = f"INV-{subscription.id}-{timezone.now().strftime('%Y%m%d%H%M%S')}"
                Invoice.objects.create(
                    subscription=subscription,
                    invoice_number=invoice_number,
                    amount=subscription.amount,
                    tax_amount=Decimal('0.00'),
                    total_amount=subscription.amount,
                    status='SENT',
                    issue_date=today,
                    due_date=subscription.next_billing_date,
                    billing_period_start=subscription.end_date,
                    billing_period_end=subscription.end_date + timedelta(days=subscription.plan.billing_cycle_days())
                )
                
                # Renew subscription period
                subscription.renew()
                
                # Create alert for payment due
                Alert.objects.create(
                    subscription=subscription,
                    alert_type='PAYMENT_DUE',
                    priority='HIGH',
                    title='Payment Due',
                    message=f'Your subscription renewal payment of {subscription.plan.currency} {subscription.amount} is due on {subscription.next_billing_date}.',
                    metadata={
                        'amount': str(subscription.amount),
                        'due_date': str(subscription.next_billing_date),
                        'invoice_number': invoice_number
                    }
                )
                
                processed += 1
            else:
                # No auto-payment method, send reminder
                Alert.objects.create(
                    subscription=subscription,
                    alert_type='PAYMENT_DUE',
                    priority='HIGH',
                    title='Manual Payment Required',
                    message=f'Your subscription is due for renewal. Please make a payment of {subscription.plan.currency} {subscription.amount}.',
                    metadata={
                        'amount': str(subscription.amount),
                        'due_date': str(subscription.next_billing_date)
                    }
                )
                subscription.status = 'PAST_DUE'
                subscription.save()
                failed += 1
        
        except Exception as e:
            logger.error(f"Auto-renewal failed for subscription {subscription.id}: {str(e)}")
            subscription.status = 'PAST_DUE'
            subscription.save()
            
            Alert.objects.create(
                subscription=subscription,
                alert_type='PAYMENT_FAILED',
                priority='CRITICAL',
                title='Payment Failed',
                message='Automatic renewal payment failed. Please update your payment method.',
                metadata={'error': str(e)}
            )
            failed += 1
    
    logger.info(f"Processed {processed} auto-renewals, {failed} failed")
    return {'processed': processed, 'failed': failed}


@shared_task
def check_usage_limits():
    """
    Check subscription usage against limits and send warnings
    Run hourly
    """
    warnings_sent = 0
    
    active_subscriptions = Subscription.objects.filter(
        status__in=['ACTIVE', 'TRIAL']
    ).select_related('plan', 'business')
    
    for subscription in active_subscriptions:
        usage_limits = subscription.check_usage_limits()
        
        for resource_type, usage_data in usage_limits.items():
            if usage_data.get('exceeded'):
                # Send critical alert for exceeded limit
                Alert.objects.get_or_create(
                    subscription=subscription,
                    alert_type='USAGE_LIMIT_REACHED',
                    metadata__resource_type=resource_type,
                    defaults={
                        'priority': 'CRITICAL',
                        'title': f'{resource_type.capitalize()} Limit Reached',
                        'message': f'You have reached your {resource_type} limit ({usage_data["limit"]}). Please upgrade your plan to add more.',
                        'metadata': {
                            'resource_type': resource_type,
                            'current': usage_data['current'],
                            'limit': usage_data['limit']
                        }
                    }
                )
                warnings_sent += 1
            
            elif usage_data['current'] >= usage_data['limit'] * 0.8:
                # Send warning at 80% usage
                Alert.objects.get_or_create(
                    subscription=subscription,
                    alert_type='USAGE_LIMIT_WARNING',
                    metadata__resource_type=resource_type,
                    defaults={
                        'priority': 'MEDIUM',
                        'title': f'{resource_type.capitalize()} Limit Warning',
                        'message': f'You are using {int((usage_data["current"] / usage_data["limit"]) * 100)}% of your {resource_type} limit. Consider upgrading your plan.',
                        'metadata': {
                            'resource_type': resource_type,
                            'current': usage_data['current'],
                            'limit': usage_data['limit'],
                            'percentage': int((usage_data['current'] / usage_data['limit']) * 100)
                        }
                    }
                )
                warnings_sent += 1
    
    logger.info(f"Sent {warnings_sent} usage limit warnings")
    return warnings_sent


@shared_task
def cleanup_old_webhook_events():
    """
    Clean up webhook events older than 90 days
    Run weekly
    """
    from .models import WebhookEvent
    
    ninety_days_ago = timezone.now() - timedelta(days=90)
    deleted_count, _ = WebhookEvent.objects.filter(
        created_at__lt=ninety_days_ago,
        status='PROCESSED'
    ).delete()
    
    logger.info(f"Cleaned up {deleted_count} old webhook events")
    return deleted_count


@shared_task
def generate_monthly_invoices():
    """
    Generate invoices for monthly subscriptions
    Run on the 1st of each month
    """
    from datetime import date
    today = timezone.now().date()
    
    # Only run on the 1st of the month
    if today.day != 1:
        return 0
    
    # Get all active monthly subscriptions
    monthly_subs = Subscription.objects.filter(
        status='ACTIVE',
        plan__billing_cycle='MONTHLY'
    )
    
    generated = 0
    for subscription in monthly_subs:
        # Check if invoice already exists for this period
        existing = Invoice.objects.filter(
            subscription=subscription,
            billing_period_start=subscription.current_period_start.date(),
            billing_period_end=subscription.current_period_end.date()
        ).exists()
        
        if not existing:
            invoice_number = f"INV-{subscription.id}-{today.strftime('%Y%m')}"
            Invoice.objects.create(
                subscription=subscription,
                invoice_number=invoice_number,
                amount=subscription.amount,
                tax_amount=Decimal('0.00'),
                total_amount=subscription.amount,
                status='SENT',
                issue_date=today,
                due_date=subscription.next_billing_date or today + timedelta(days=30),
                billing_period_start=subscription.current_period_start.date(),
                billing_period_end=subscription.current_period_end.date()
            )
            generated += 1
    
    logger.info(f"Generated {generated} monthly invoices")
    return generated


@shared_task
def send_payment_reminders():
    """
    Send payment reminders for overdue invoices
    Run daily
    """
    today = timezone.now().date()
    
    overdue_invoices = Invoice.objects.filter(
        status__in=['SENT', 'OVERDUE'],
        due_date__lt=today
    ).select_related('subscription', 'subscription__user', 'subscription__business')
    
    reminders_sent = 0
    for invoice in overdue_invoices:
        # Update status to overdue
        if invoice.status != 'OVERDUE':
            invoice.status = 'OVERDUE'
            invoice.save()
        
        days_overdue = invoice.days_overdue()
        
        # Send reminder
        Alert.objects.create(
            subscription=invoice.subscription,
            alert_type='PAYMENT_FAILED',
            priority='CRITICAL',
            title='Payment Overdue',
            message=f'Invoice {invoice.invoice_number} is {days_overdue} days overdue. Please make payment to avoid service interruption.',
            metadata={
                'invoice_number': invoice.invoice_number,
                'amount': str(invoice.total_amount),
                'days_overdue': days_overdue,
                'due_date': str(invoice.due_date)
            }
        )
        reminders_sent += 1
    
    logger.info(f"Sent {reminders_sent} payment reminders")
    return reminders_sent
