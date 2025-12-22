"""
Celery tasks for AI Features
Handles async processing of payment webhooks and notifications
"""

from celery import shared_task
from django.utils import timezone
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


@shared_task(name='ai_features.process_payment_webhook')
def process_payment_webhook(payment_reference: str, amount_paid: str, payment_provider: str = 'paystack'):
    """
    Process payment webhook asynchronously to avoid blocking webhook endpoint.
    
    This task handles credit purchases from payment gateway webhooks,
    ensuring idempotent processing even if webhook is sent multiple times.
    
    Args:
        payment_reference: Unique payment reference from gateway
        amount_paid: Amount paid in GHS (as string to avoid float precision issues)
        payment_provider: Payment gateway used ('paystack' or 'flutterwave')
        
    Returns:
        dict: Processing results
    """
    from ai_features.models import AICreditPurchase
    from ai_features.services import AIBillingService
    
    logger.info(f"Processing payment webhook for reference: {payment_reference}")
    
    try:
        # Get purchase record
        purchase = AICreditPurchase.objects.select_for_update().get(
            payment_reference=payment_reference
        )
        
        # Idempotency check - already processed?
        if purchase.payment_status == 'completed':
            logger.info(f"Payment {payment_reference} already processed, skipping")
            return {
                'status': 'already_processed',
                'reference': payment_reference,
                'message': 'Payment already credited to account'
            }
        
        # Convert amount to Decimal
        amount_ghs = Decimal(amount_paid)
        
        # Credit the account (idempotent operation)
        AIBillingService.purchase_credits(
            business_id=str(purchase.business_id),
            amount_paid=amount_ghs,
            credits_purchased=purchase.credits_purchased,
            payment_reference=payment_reference,
            payment_method=purchase.payment_method,
            user_id=str(purchase.user_id),
            bonus_credits=purchase.bonus_credits
        )
        
        # Update purchase status
        purchase.payment_status = 'completed'
        purchase.completed_at = timezone.now()
        purchase.save()
        
        logger.info(
            f"Payment {payment_reference} processed successfully: "
            f"{purchase.credits_purchased + purchase.bonus_credits} credits added"
        )
        
        # Send notification email
        send_credit_purchase_notification.delay(str(purchase.id))
        
        return {
            'status': 'success',
            'reference': payment_reference,
            'credits_added': float(purchase.credits_purchased + purchase.bonus_credits),
            'business_id': str(purchase.business_id)
        }
        
    except AICreditPurchase.DoesNotExist:
        logger.warning(f"Purchase record not found for reference: {payment_reference}")
        return {
            'status': 'not_found',
            'reference': payment_reference,
            'message': 'Purchase record not found (might not be an AI credit purchase)'
        }
    except Exception as e:
        logger.error(f"Error processing payment webhook {payment_reference}: {str(e)}", exc_info=True)
        raise


@shared_task(name='ai_features.send_credit_purchase_notification')
def send_credit_purchase_notification(purchase_id: str):
    """
    Send email notification after successful credit purchase.
    
    Args:
        purchase_id: UUID of the AICreditPurchase record
    """
    from ai_features.models import AICreditPurchase
    from ai_features.services import AIBillingService
    from django.core.mail import send_mail
    from django.conf import settings
    
    logger.info(f"Sending credit purchase notification for purchase {purchase_id}")
    
    try:
        purchase = AICreditPurchase.objects.select_related('business', 'user').get(id=purchase_id)
        
        # Get current balance
        balance = AIBillingService.get_credit_balance(str(purchase.business_id))
        
        subject = f"AI Credits Purchased - {purchase.business.name}"
        message = f"""
Hello {purchase.user.name if purchase.user else 'there'},

Your AI credit purchase has been completed successfully!

Purchase Details:
- Credits Purchased: {purchase.credits_purchased}
- Bonus Credits: {purchase.bonus_credits}
- Total Credits Added: {purchase.credits_purchased + purchase.bonus_credits}
- Amount Paid: ₵{purchase.amount_paid}
- Payment Reference: {purchase.payment_reference}

Current Balance: {balance} credits

Thank you for your purchase!

Best regards,
POS Backend Team
"""
        
        # Send to business owner/purchaser
        recipient = purchase.user.email if purchase.user else purchase.business.owner.email
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [recipient],
            fail_silently=False,
        )
        
        logger.info(f"Credit purchase notification sent to {recipient}")
        
        return {
            'status': 'sent',
            'recipient': recipient,
            'purchase_id': purchase_id
        }
        
    except AICreditPurchase.DoesNotExist:
        logger.error(f"Purchase {purchase_id} not found")
        raise
    except Exception as e:
        logger.error(f"Error sending notification for purchase {purchase_id}: {str(e)}", exc_info=True)
        raise


@shared_task(name='ai_features.send_low_credit_alert')
def send_low_credit_alert(business_id: str, current_balance: float, threshold: float = 10.0):
    """
    Send alert when AI credits are running low.
    
    Args:
        business_id: UUID of the business
        current_balance: Current credit balance
        threshold: Alert threshold (default: 10 credits)
    """
    from accounts.models import Business
    from django.core.mail import send_mail
    from django.conf import settings
    
    logger.info(f"Sending low credit alert for business {business_id}")
    
    try:
        business = Business.objects.select_related('owner').get(id=business_id)
        
        subject = f"Low AI Credits Alert - {business.name}"
        message = f"""
Hello {business.owner.name},

Your AI credit balance is running low.

Current Balance: {current_balance} credits
Alert Threshold: {threshold} credits

To continue using AI features without interruption, please purchase more credits.

Best regards,
POS Backend Team
"""
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [business.owner.email],
            fail_silently=False,
        )
        
        logger.info(f"Low credit alert sent to {business.owner.email}")
        
        return {
            'status': 'sent',
            'business_id': business_id,
            'balance': current_balance
        }
        
    except Business.DoesNotExist:
        logger.error(f"Business {business_id} not found")
        raise
    except Exception as e:
        logger.error(f"Error sending low credit alert: {str(e)}", exc_info=True)
        raise
