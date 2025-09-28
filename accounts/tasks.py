from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


@shared_task
def send_welcome_email(user_id):
    """
    Send welcome email to new users
    """
    try:
        user = User.objects.get(id=user_id)
        
        subject = 'Welcome to SaaS POS System'
        message = f"""
        Hello {user.name},
        
        Welcome to our SaaS POS System! Your account has been created successfully.
        
        Email: {user.email}
        Role: {user.role.name if user.role else 'No role assigned'}
        
        Please log in to start using the system.
        
        Best regards,
        SaaS POS Team
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        
        logger.info(f"Welcome email sent to {user.email}")
        return f"Welcome email sent to {user.email}"
        
    except User.DoesNotExist:
        logger.error(f"User with ID {user_id} does not exist")
        return f"User with ID {user_id} does not exist"
    except Exception as e:
        logger.error(f"Failed to send welcome email to user {user_id}: {str(e)}")
        return f"Failed to send welcome email: {str(e)}"


@shared_task
def cleanup_inactive_users():
    """
    Clean up inactive users after a certain period
    """
    try:
        # Find users inactive for more than 90 days
        cutoff_date = timezone.now() - timedelta(days=90)
        inactive_users = User.objects.filter(
            is_active=False,
            updated_at__lt=cutoff_date
        )
        
        count = inactive_users.count()
        if count > 0:
            # For now, just log. In production, you might want to anonymize or delete
            logger.info(f"Found {count} inactive users for cleanup")
            
            # Example: anonymize user data instead of deleting
            for user in inactive_users:
                user.name = f"Deleted User {user.id}"
                user.email = f"deleted_{user.id}@example.com"
                user.save()
        
        return f"Processed {count} inactive users"
        
    except Exception as e:
        logger.error(f"Failed to cleanup inactive users: {str(e)}")
        return f"Failed to cleanup inactive users: {str(e)}"


@shared_task
def generate_user_activity_report():
    """
    Generate periodic user activity reports
    """
    try:
        # Get activity data for the last 7 days
        week_ago = timezone.now() - timedelta(days=7)
        
        from accounts.models import AuditLog
        
        activity_stats = {
            'total_logins': AuditLog.objects.filter(
                action='LOGIN',
                timestamp__gte=week_ago
            ).count(),
            'unique_users': AuditLog.objects.filter(
                timestamp__gte=week_ago
            ).values('user').distinct().count(),
            'total_actions': AuditLog.objects.filter(
                timestamp__gte=week_ago
            ).count(),
        }
        
        logger.info(f"Weekly activity report: {activity_stats}")
        return activity_stats
        
    except Exception as e:
        logger.error(f"Failed to generate user activity report: {str(e)}")
        return f"Failed to generate report: {str(e)}"


@shared_task
def check_subscription_renewals():
    """
    Check for subscription renewals and send notifications
    """
    try:
        # Find users with subscriptions expiring in 7 days
        week_from_now = timezone.now().date() + timedelta(days=7)
        
        from subscriptions.models import Subscription
        
        expiring_subscriptions = Subscription.objects.filter(
            end_date=week_from_now,
            status='ACTIVE',
            auto_renew=True
        ).select_related('user', 'plan')
        
        count = 0
        for subscription in expiring_subscriptions:
            # Send renewal notification
            subject = 'Subscription Renewal Reminder'
            message = f"""
            Hello {subscription.user.name},
            
            Your subscription to {subscription.plan.name} will expire on {subscription.end_date}.
            
            Your subscription will be automatically renewed for ${subscription.amount}.
            
            If you wish to cancel, please contact support.
            
            Best regards,
            SaaS POS Team
            """
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [subscription.user.email],
                fail_silently=True,
            )
            count += 1
        
        logger.info(f"Sent {count} subscription renewal reminders")
        return f"Sent {count} subscription renewal reminders"
        
    except Exception as e:
        logger.error(f"Failed to check subscription renewals: {str(e)}")
        return f"Failed to check subscription renewals: {str(e)}"