from django.contrib.auth import get_user_model
from .models import AuditLog
import json

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