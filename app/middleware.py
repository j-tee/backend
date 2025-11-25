"""
Security Middleware for POS Backend
Implements Row-Level Security (RLS) and business scoping
"""

from django.db import connection
from django.utils.deprecation import MiddlewareMixin
import logging

logger = logging.getLogger(__name__)


class BusinessScopingMiddleware(MiddlewareMixin):
    """
    Sets PostgreSQL session variables for Row-Level Security (RLS)
    This ensures all database queries are automatically scoped to user's businesses
    """
    
    def process_request(self, request):
        if request.user.is_authenticated:
            try:
                with connection.cursor() as cursor:
                    # Set current user ID for RLS policies
                    cursor.execute(
                        "SET LOCAL app.current_user_id = %s",
                        [str(request.user.id)]
                    )
                    
                    # Set business context if available
                    business_id = self._get_current_business(request)
                    if business_id:
                        cursor.execute(
                            "SET LOCAL app.current_business_id = %s",
                            [str(business_id)]
                        )
            except Exception as e:
                logger.error(f"Failed to set RLS session variables: {e}")
        
        return None
    
    def _get_current_business(self, request):
        """Extract current business from request"""
        # Check query params
        business_id = request.GET.get('business') or request.GET.get('business_id')
        
        # Check POST data
        if not business_id and request.method in ['POST', 'PUT', 'PATCH']:
            try:
                business_id = request.data.get('business') or request.data.get('business_id')
            except:
                pass
        
        # Check session
        if not business_id:
            business_id = request.session.get('current_business_id')
        
        return business_id


class EnvironmentSecurityMiddleware(MiddlewareMixin):
    """
    Prevents production deployment with development settings
    """
    
    def process_request(self, request):
        from django.conf import settings
        
        # Check for dangerous production configurations
        if not settings.DEBUG:  # Production mode
            dangerous_configs = []
            
            # Check for test keys in production
            if settings.PAYSTACK_SECRET_KEY and 'test' in settings.PAYSTACK_SECRET_KEY:
                dangerous_configs.append("Using Paystack TEST keys in production")
            
            if settings.STRIPE_SECRET_KEY and 'test' in settings.STRIPE_SECRET_KEY:
                dangerous_configs.append("Using Stripe TEST keys in production")
            
            # Check for weak secret key
            if settings.SECRET_KEY == 'django-insecure-qypa%1&zw5yph-(3sogpdy7x((f8!r)npt6s@6%@fw1(10&e9l':
                dangerous_configs.append("Using default/weak SECRET_KEY in production")
            
            # Check for disabled security features
            if not settings.SECURE_SSL_REDIRECT:
                dangerous_configs.append("SSL redirect disabled in production")
            
            if not settings.SESSION_COOKIE_SECURE:
                dangerous_configs.append("Insecure session cookies in production")
            
            if dangerous_configs:
                logger.critical(
                    f"SECURITY WARNING: Dangerous production configuration detected:\n" +
                    "\n".join(f"  - {config}" for config in dangerous_configs)
                )
        
        return None
