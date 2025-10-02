import logging
from smtplib import SMTPException

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.urls import reverse

from .models import AuditLog, BusinessInvitation

logger = logging.getLogger(__name__)


class EmailDeliveryError(Exception):
    """Raised when sending transactional email fails."""



User = get_user_model()


def log_user_action(user, action, model_name, object_id=None, changes=None, request=None):
    """
    Log user actions for audit trail
    
    Args:
        user: User instance performing the action
        action: Action type (CREATE, UPDATE, DELETE, etc.)
        model_name: Name of the model being affected
        object_id: ID of the object being affected
        changes: Dictionary of changes made
        request: HTTP request object (optional)
    """
    audit_data = {
        'user': user,
        'action': action,
        'model_name': model_name,
        'object_id': object_id,
        'changes': changes or {},
    }
    
    if request:
        # Extract IP address
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        audit_data['ip_address'] = ip
        audit_data['user_agent'] = request.META.get('HTTP_USER_AGENT', '')
    
    AuditLog.objects.create(**audit_data)


def track_model_changes(old_instance, new_instance):
    """
    Track changes between two model instances
    
    Args:
        old_instance: Original model instance
        new_instance: Updated model instance
    
    Returns:
        dict: Dictionary of changes
    """
    changes = {}
    
    if not old_instance:
        return changes
    
    for field in new_instance._meta.fields:
        field_name = field.name
        old_value = getattr(old_instance, field_name, None)
        new_value = getattr(new_instance, field_name, None)
        
        if old_value != new_value:
            # Convert non-serializable values to strings
            if hasattr(old_value, 'pk'):
                old_value = str(old_value)
            if hasattr(new_value, 'pk'):
                new_value = str(new_value)
            
            changes[field_name] = {
                'old': old_value,
                'new': new_value
            }
    
    return changes


class AuditMiddleware:
    """
    Middleware to automatically log certain actions
    """
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Log authentication events
        if hasattr(request, 'user') and request.user.is_authenticated:
            if request.path.endswith('/login/') and response.status_code == 200:
                log_user_action(
                    user=request.user,
                    action='LOGIN',
                    model_name='User',
                    object_id=request.user.pk,
                    request=request
                )
            elif request.path.endswith('/logout/') and response.status_code == 200:
                log_user_action(
                    user=request.user,
                    action='LOGOUT',
                    model_name='User',
                    object_id=request.user.pk,
                    request=request
                )
        
        return response


def get_client_ip(request):
    """
    Get client IP address from request
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def mask_sensitive_data(data, sensitive_fields=None):
    """
    Mask sensitive data in audit logs
    
    Args:
        data: Dictionary containing data to mask
        sensitive_fields: List of field names to mask
    
    Returns:
        dict: Data with sensitive fields masked
    """
    if sensitive_fields is None:
        sensitive_fields = ['password', 'password_hash', 'secret_key', 'token']
    
    masked_data = data.copy()
    
    for field in sensitive_fields:
        if field in masked_data:
            masked_data[field] = '***MASKED***'
    
    return masked_data


def send_verification_email(user, token):
    """Send an email verification link to the given user."""

    frontend_base = getattr(settings, 'FRONTEND_URL', '').rstrip('/') or 'http://localhost:3000'
    backend_base = getattr(settings, 'BACKEND_URL', '').rstrip('/') or 'http://localhost:8000'

    verify_url = f"{frontend_base}/verify-email?token={token}"

    subject = 'Verify your POS account email'
    message = (
        f"Hello {user.name},\n\n"
        "Thanks for signing up. Please confirm your email address to activate your account.\n\n"
    f"Verification link: {verify_url}\n\n"
    "If the link above doesn't work, copy the token below and paste it into the verification form:\n"
    f"Token: {token}\n\n"
        "If you did not initiate this request, please ignore this email.\n\n"
        "Best regards,\n"
        "POS Platform Team"
    )

    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
    except SMTPException as exc:
        logger.exception("Failed to send verification email to %s", user.email)
        raise EmailDeliveryError("Unable to send verification email at this time.") from exc


def send_password_reset_email(user, token):
    """Send password reset instructions with both frontend and backend links."""

    frontend_base = getattr(settings, 'FRONTEND_URL', '').rstrip('/') or 'http://localhost:3000'
    backend_base = getattr(settings, 'BACKEND_URL', '').rstrip('/') or 'http://localhost:8000'

    reset_url = f"{frontend_base}/reset-password?token={token}"
    direct_reset_url = f"{backend_base}/accounts/api/auth/password-reset/confirm/"  # Expect POST

    subject = 'Reset your POS account password'
    message = (
        f"Hello {user.name},\n\n"
        "A password reset request was received for your account.\n\n"
        f"Reset link: {reset_url}\n\n"
        "If the button above doesn't work, share this token with the password reset form:"
        f"\nToken: {token}\n\n"
        "Alternatively, you can send a POST request directly to:"
        f"\n{direct_reset_url}\n\n"
        "If you did not request this change, please ignore this email.\n\n"
        "Best regards,\n"
        "POS Platform Team"
    )

    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
    except SMTPException as exc:
        logger.exception("Failed to send password reset email to %s", user.email)
        raise EmailDeliveryError("Unable to send password reset email at this time.") from exc


def send_business_invitation_email(invitation: BusinessInvitation):
    """Send an invitation email to join a business."""

    if not invitation.token:
        invitation.initialize_token()
        invitation.save(update_fields=["token", "expires_at", "updated_at"])

    frontend_base = getattr(settings, "FRONTEND_URL", "").rstrip('/') or 'http://localhost:3000'
    accept_url = f"{frontend_base}/accept-invite?token={invitation.token}"

    subject = f"You're invited to join {invitation.business.name}"
    message = (
        f"Hello,\n\n"
        f"You've been invited to join {invitation.business.name} on the POS platform as {invitation.role}.\n\n"
        f"Accept invitation: {accept_url}\n\n"
        f"If the link above doesn't work, copy this token: {invitation.token}\n\n"
        "If you weren't expecting this invitation, you can ignore this email.\n\n"
        "Best regards,\nPOS Platform Team"
    )

    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [invitation.email], fail_silently=False)
    except SMTPException as exc:
        logger.exception("Failed to send business invitation email to %s", invitation.email)
        raise EmailDeliveryError("Unable to send the invitation email at this time.") from exc