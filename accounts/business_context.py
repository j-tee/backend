"""
Business Context Management
Ensures data operations are scoped to the correct business context
"""

from rest_framework.exceptions import PermissionDenied, ValidationError
from django.core.cache import cache
from uuid import UUID


class BusinessContextManager:
    """
    Manages business context for multi-business users
    Prevents inadvertent cross-business data updates
    """
    
    CACHE_TIMEOUT = 3600  # 1 hour
    
    @staticmethod
    def get_cache_key(user_id, session_key=None):
        """Generate cache key for user's current business context"""
        if session_key:
            return f"business_context:{user_id}:{session_key}"
        return f"business_context:{user_id}"
    
    @staticmethod
    def set_current_business(request, business_id):
        """
        Set current business context for user session
        
        Args:
            request: Django request object
            business_id: UUID of business to set as current
        """
        user = request.user
        
        # Validate user has access to this business
        business_ids = BusinessContextManager.get_accessible_business_ids(user)
        
        if str(business_id) not in [str(bid) for bid in business_ids]:
            raise PermissionDenied(
                f'You do not have access to business {business_id}'
            )
        
        # Store in session
        request.session['current_business_id'] = str(business_id)
        
        # Store in cache for faster access
        cache_key = BusinessContextManager.get_cache_key(
            user.id, 
            request.session.session_key
        )
        cache.set(cache_key, str(business_id), BusinessContextManager.CACHE_TIMEOUT)
        
        return business_id
    
    @staticmethod
    def get_current_business(request):
        """
        Get current business context from request
        
        Priority:
        1. Query parameter (?business=uuid)
        2. Request body (business field)
        3. Session storage
        4. User's primary business
        """
        user = request.user
        
        if not user.is_authenticated:
            return None
        
        # 1. Check query params (for explicit business selection)
        business_id = request.GET.get('business') or request.GET.get('business_id')
        
        if business_id:
            # Validate access
            try:
                UUID(business_id)
                if BusinessContextManager.has_business_access(user, business_id):
                    return business_id
            except (ValueError, TypeError):
                raise ValidationError({'business': 'Invalid business ID format'})
        
        # 2. Check request body (for POST/PUT/PATCH)
        if request.method in ['POST', 'PUT', 'PATCH']:
            try:
                business_id = getattr(request, 'data', {}).get('business')
                if business_id and BusinessContextManager.has_business_access(user, business_id):
                    return business_id
            except:
                pass
        
        # 3. Check session
        business_id = request.session.get('current_business_id')
        if business_id:
            return business_id
        
        # 4. Check cache
        cache_key = BusinessContextManager.get_cache_key(
            user.id,
            request.session.session_key
        )
        business_id = cache.get(cache_key)
        if business_id:
            return business_id
        
        # 5. Fall back to user's primary business
        primary_business = BusinessContextManager.get_primary_business(user)
        if primary_business:
            return str(primary_business.id)
        
        return None
    
    @staticmethod
    def get_accessible_business_ids(user):
        """Get all business IDs user has access to"""
        business_ids = set()
        
        # Add owned businesses
        if hasattr(user, 'owned_businesses'):
            business_ids.update(
                user.owned_businesses.values_list('id', flat=True)
            )
        
        # Add membership businesses
        if hasattr(user, 'business_memberships'):
            business_ids.update(
                user.business_memberships.filter(is_active=True)
                .values_list('business_id', flat=True)
            )
        
        return list(business_ids)
    
    @staticmethod
    def has_business_access(user, business_id):
        """Check if user has access to specific business"""
        try:
            business_uuid = UUID(str(business_id))
            accessible = BusinessContextManager.get_accessible_business_ids(user)
            return business_uuid in [UUID(str(bid)) for bid in accessible]
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def get_primary_business(user):
        """Get user's primary/default business"""
        # Check account type for owners
        if getattr(user, 'account_type', None) == getattr(user, 'ACCOUNT_OWNER', 'OWNER'):
            return user.owned_businesses.first()
        
        # Check most recent membership
        membership = user.business_memberships.filter(
            is_active=True
        ).select_related('business').order_by('-updated_at').first()
        
        return membership.business if membership else None
    
    @staticmethod
    def validate_business_ownership(user, obj, business_field='business_id'):
        """
        Validate that user has access to the business of given object
        
        Args:
            user: User instance
            obj: Model instance to check
            business_field: Name of business field (default: 'business_id')
        
        Raises:
            PermissionDenied: If user doesn't have access
        """
        business_id = getattr(obj, business_field, None)
        
        if not business_id:
            raise ValidationError(f'Object has no {business_field} field')
        
        accessible = BusinessContextManager.get_accessible_business_ids(user)
        
        if business_id not in accessible:
            raise PermissionDenied(
                'You do not have access to this resource. '
                'It belongs to a different business.'
            )
    
    @staticmethod
    def enforce_business_context(request, obj, business_field='business_id'):
        """
        Enforce that operation is within user's current business context
        
        This prevents scenarios like:
        - User viewing Business A's dashboard
        - Making API call that modifies Business B's data
        
        Args:
            request: Django request
            obj: Object being accessed/modified
            business_field: Name of business foreign key field
        """
        current_business = BusinessContextManager.get_current_business(request)
        obj_business = getattr(obj, business_field, None)
        
        if current_business and obj_business:
            if str(current_business) != str(obj_business):
                raise PermissionDenied(
                    f'Business context mismatch. '
                    f'Current context: {current_business}, '
                    f'Resource belongs to: {obj_business}'
                )


class BusinessContextMixin:
    """
    Mixin for ViewSets to enforce business context
    
    Usage:
        class ProductViewSet(BusinessContextMixin, viewsets.ModelViewSet):
            business_field = 'business_id'  # Optional, defaults to 'business_id'
    """
    
    business_field = 'business_id'
    
    def get_queryset(self):
        """Filter queryset by accessible businesses"""
        queryset = super().get_queryset()
        user = self.request.user
        
        if user.is_superuser:
            return queryset
        
        business_ids = BusinessContextManager.get_accessible_business_ids(user)
        if not business_ids:
            return queryset.none()
        
        # Filter by accessible businesses
        filter_kwargs = {f'{self.business_field}__in': business_ids}
        return queryset.filter(**filter_kwargs)
    
    def perform_create(self, serializer):
        """Ensure new objects are created with correct business context"""
        user = self.request.user
        current_business = BusinessContextManager.get_current_business(self.request)
        
        if not current_business:
            raise ValidationError({
                'business': 'No business context available. Please select a business.'
            })
        
        # Validate user has access
        if not BusinessContextManager.has_business_access(user, current_business):
            raise PermissionDenied('You do not have access to this business')
        
        # Force business assignment
        serializer.save(**{self.business_field.replace('_id', ''): current_business})
    
    def perform_update(self, serializer):
        """Validate update is within correct business context"""
        instance = self.get_object()
        
        # Validate ownership
        BusinessContextManager.validate_business_ownership(
            self.request.user,
            instance,
            self.business_field
        )
        
        # Enforce context
        BusinessContextManager.enforce_business_context(
            self.request,
            instance,
            self.business_field
        )
        
        serializer.save()
    
    def perform_destroy(self, instance):
        """Validate delete is within correct business context"""
        # Validate ownership
        BusinessContextManager.validate_business_ownership(
            self.request.user,
            instance,
            self.business_field
        )
        
        # Enforce context
        BusinessContextManager.enforce_business_context(
            self.request,
            instance,
            self.business_field
        )
        
        instance.delete()
