from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import BusinessSettings
from .serializers import BusinessSettingsSerializer


class BusinessSettingsViewSet(viewsets.ViewSet):
    """
    ViewSet for managing business settings.
    
    Provides endpoints for:
    - GET: Retrieve settings (auto-creates if not exist)
    - PATCH: Update settings (partial update)
    - POST: Create settings (if not already exist)
    
    Settings are scoped to the user's current business context.
    """
    serializer_class = BusinessSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Get settings for current user's business"""
        user = self.request.user
        business = getattr(user, 'current_business', None)

        if not business:
            # Fallback: get first business membership
            membership = user.business_memberships.first()
            if membership:
                business = membership.business

        if business:
            return BusinessSettings.objects.filter(business=business)
        return BusinessSettings.objects.none()

    def get_object(self):
        """Get or create settings for current business"""
        user = self.request.user
        business = getattr(user, 'current_business', None)

        if not business:
            # Fallback: get first business membership
            membership = user.business_memberships.first()
            if membership:
                business = membership.business

        if not business:
            from rest_framework.exceptions import NotFound
            raise NotFound('No business context found for user')

        settings, created = BusinessSettings.objects.get_or_create(
            business=business,
            defaults={
                'regional': BusinessSettings.get_default_regional(),
                'appearance': BusinessSettings.get_default_appearance(),
                'notifications': BusinessSettings.get_default_notifications(),
                'receipt': BusinessSettings.get_default_receipt(),
            }
        )
        return settings

    def list(self, request, *args, **kwargs):
        """
        GET /settings/api/settings/
        
        Returns the business settings, creating with defaults if they don't exist.
        """
        settings = self.get_object()
        serializer = BusinessSettingsSerializer(settings)
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        """
        PUT /settings/api/settings/ (not used, use partial_update)
        """
        return self.partial_update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        """
        PATCH /settings/api/settings/
        
        Updates business settings (partial update allowed).
        Merges new values with existing settings.
        """
        settings = self.get_object()

        # Deep merge for JSON fields
        data = request.data.copy()
        
        # Merge regional settings
        if 'regional' in data:
            regional = settings.regional.copy()
            regional.update(data['regional'])
            data['regional'] = regional

        # Merge appearance settings
        if 'appearance' in data:
            appearance = settings.appearance.copy()
            appearance.update(data['appearance'])
            data['appearance'] = appearance

        # Merge notification settings
        if 'notifications' in data:
            notifications = settings.notifications.copy()
            notifications.update(data['notifications'])
            data['notifications'] = notifications

        # Merge receipt settings
        if 'receipt' in data:
            receipt = settings.receipt.copy()
            receipt.update(data['receipt'])
            data['receipt'] = receipt

        serializer = BusinessSettingsSerializer(
            settings,
            data=data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        """
        POST /settings/api/settings/
        
        Creates initial settings. Returns error if settings already exist.
        """
        user = request.user
        business = getattr(user, 'current_business', None)

        if not business:
            # Fallback: get first business membership
            membership = user.business_memberships.first()
            if membership:
                business = membership.business

        if not business:
            return Response(
                {'detail': 'No business context found for user'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if settings already exist
        if BusinessSettings.objects.filter(business=business).exists():
            return Response(
                {'detail': 'Settings already exist. Use PATCH to update.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Merge defaults with provided data
        data = {
            'regional': BusinessSettings.get_default_regional(),
            'appearance': BusinessSettings.get_default_appearance(),
            'notifications': BusinessSettings.get_default_notifications(),
            'receipt': BusinessSettings.get_default_receipt(),
        }

        # Update with any provided values
        if 'regional' in request.data:
            data['regional'].update(request.data['regional'])
        if 'appearance' in request.data:
            data['appearance'].update(request.data['appearance'])
        if 'notifications' in request.data:
            data['notifications'].update(request.data['notifications'])
        if 'receipt' in request.data:
            data['receipt'].update(request.data['receipt'])

        serializer = BusinessSettingsSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save(business=business)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def reset_to_defaults(self, request):
        """
        POST /settings/api/settings/reset_to_defaults/
        
        Resets all settings to default values.
        """
        settings = self.get_object()
        settings.regional = BusinessSettings.get_default_regional()
        settings.appearance = BusinessSettings.get_default_appearance()
        settings.notifications = BusinessSettings.get_default_notifications()
        settings.receipt = BusinessSettings.get_default_receipt()
        settings.save()

        serializer = BusinessSettingsSerializer(settings)
        return Response(serializer.data)
