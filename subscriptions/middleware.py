"""
Subscription Middleware

This middleware adds subscription status information to response headers,
allowing the frontend to check subscription status on every request.
"""

from django.utils.deprecation import MiddlewareMixin
from .utils import SubscriptionChecker


class SubscriptionStatusMiddleware(MiddlewareMixin):
    """
    Middleware that adds subscription status headers to all API responses.
    
    Headers added:
    - X-Subscription-Status: active|expired|grace_period|none
    - X-Subscription-Tier: Tier name (if available)
    - X-Subscription-Expires: End date (if available)
    - X-Grace-Period-End: Grace period end date (if applicable)
    - X-Max-Storefronts: Maximum storefronts allowed
    """
    
    def process_response(self, request, response):
        """
        Add subscription status headers to the response.
        """
        # Only add headers for authenticated users
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return response
        
        # Get user's business
        business = getattr(request.user, 'business', None)
        if not business:
            return response
        
        try:
            # Get subscription status
            status_info = SubscriptionChecker.get_subscription_status(business)
            
            # Add headers
            response['X-Subscription-Status'] = status_info.get('subscription_status', 'none')
            
            if status_info.get('tier_code'):
                response['X-Subscription-Tier'] = status_info.get('tier_code')
            
            if status_info.get('end_date'):
                response['X-Subscription-Expires'] = str(status_info.get('end_date'))
            
            if status_info.get('grace_period_end'):
                response['X-Grace-Period-End'] = str(status_info.get('grace_period_end'))
            
            response['X-Max-Storefronts'] = str(status_info.get('max_storefronts', 1))
            
            # Add feature flags
            response['X-Can-Process-Sales'] = str(status_info.get('can_process_sales', False)).lower()
            response['X-Can-View-Reports'] = str(status_info.get('can_view_reports', False)).lower()
            response['X-Can-Export-Data'] = str(status_info.get('can_export_data', False)).lower()
            
        except Exception as e:
            # Log error but don't break the request
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error adding subscription headers: {e}")
        
        return response


class SubscriptionEnforcementMiddleware(MiddlewareMixin):
    """
    Optional middleware for global subscription enforcement.
    
    WARNING: This middleware will block ALL requests if subscription is invalid.
    Use with caution and ensure proper exemptions for login, subscription pages, etc.
    
    This is currently NOT recommended. Use permission classes instead for
    granular control over which endpoints require subscriptions.
    """
    
    # Paths that should be accessible without subscription
    EXEMPT_PATHS = [
        '/api/accounts/login/',
        '/api/accounts/register/',
        '/api/accounts/logout/',
        '/api/subscriptions/',
        '/admin/',
        '/static/',
        '/media/',
    ]
    
    def process_request(self, request):
        """
        Check subscription status before processing request.
        
        NOTE: Currently disabled. Use permission classes instead.
        """
        # This middleware is disabled by default
        # To enable, add to MIDDLEWARE in settings.py
        return None  # Allow all requests
