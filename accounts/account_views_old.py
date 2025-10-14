"""
Account Management Views
API views for user account management (profile, security, preferences)
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import os

from .account_serializers import (
    UpdateProfileSerializer,
    ProfilePictureSerializer,
    ChangePasswordSerializer,
    UserPreferencesSerializer,
    NotificationSettingsSerializer,
    UserProfileSerializer,
    Enable2FASerializer,
    Disable2FASerializer
)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """
    GET: Retrieve current user's profile
    POST: Update current user's profile
    """
    user = request.user
    
    if request.method == 'GET':
        serializer = UserProfileSerializer(user)
        return Response(serializer.data)
    
    elif request.method == 'POST':
        serializer = UpdateProfileSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            # Return full profile
            profile_serializer = UserProfileSerializer(user)
            return Response(profile_serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_profile_picture(request):
    """Upload and update user's profile picture"""
    serializer = ProfilePictureSerializer(data=request.data)
    
    if serializer.is_valid():
        user = request.user
        profile_picture = serializer.validated_data['profile_picture']
        
        # Delete old profile picture if exists
        if user.profile_picture:
            try:
                default_storage.delete(user.profile_picture.name)
            except Exception:
                pass  # Ignore errors when deleting old file
        
        # Generate unique filename
        ext = os.path.splitext(profile_picture.name)[1]
        filename = f'profile_pictures/{user.id}/profile{ext}'
        
        # Save new file
        path = default_storage.save(filename, ContentFile(profile_picture.read()))
        user.profile_picture = path
        user.save()
        
        return Response({
            'message': 'Profile picture uploaded successfully',
            'profile_picture_url': user.profile_picture.url if user.profile_picture else None
        })
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """Change user's password"""
    serializer = ChangePasswordSerializer(
        data=request.data,
        context={'request': request}
    )
    
    if serializer.is_valid():
        serializer.save()
        return Response({
            'message': 'Password changed successfully'
        })
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def enable_2fa(request):
    """Enable two-factor authentication"""
    user = request.user
    
    # TODO: Implement actual 2FA setup with TOTP
    # For now, just return a placeholder response
    
    return Response({
        'message': '2FA enabled successfully',
        'qr_code': 'data:image/png;base64,...',  # Placeholder
        'secret': 'JBSWY3DPEHPK3PXP',  # Placeholder
        'backup_codes': [
            '12345678', '23456789', '34567890', '45678901',
            '56789012', '67890123', '78901234', '89012345'
        ]
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def disable_2fa(request):
    """Disable two-factor authentication"""
    serializer = Disable2FASerializer(
        data=request.data,
        context={'request': request}
    )
    
    if serializer.is_valid():
        user = request.user
        # TODO: Implement actual 2FA disable logic
        
        return Response({
            'message': '2FA disabled successfully'
        })
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def user_preferences(request):
    """
    GET: Retrieve user preferences
    PATCH: Update user preferences
    """
    user = request.user
    
    if request.method == 'GET':
        # Get preferences from user object or defaults
        preferences = {
            'language': getattr(user, 'language', 'en'),
            'timezone': getattr(user, 'timezone', 'Africa/Accra'),
            'date_format': getattr(user, 'date_format', 'DD/MM/YYYY'),
            'time_format': getattr(user, 'time_format', '24h'),
            'currency': getattr(user, 'currency', 'GHS'),
            'enable_email_notifications': True,
            'enable_push_notifications': True,
            'enable_sms_notifications': False,
        }
        return Response(preferences)
    
    elif request.method == 'PATCH':
        serializer = UserPreferencesSerializer(data=request.data, partial=True)
        if serializer.is_valid():
            # TODO: Save preferences to user profile or separate model
            # For now, just return success
            return Response({
                'message': 'Preferences updated successfully',
                'preferences': serializer.validated_data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def notification_settings(request):
    """
    GET: Retrieve notification settings
    PATCH: Update notification settings
    """
    user = request.user
    
    if request.method == 'GET':
        # Get notification settings - defaults for now
        settings = {
            'sales_email': True,
            'sales_push': True,
            'sales_sms': False,
            'inventory_email': True,
            'inventory_push': True,
            'inventory_sms': False,
            'payments_email': True,
            'payments_push': True,
            'payments_sms': False,
            'users_email': True,
            'users_push': False,
            'users_sms': False,
            'system_email': True,
            'system_push': True,
            'system_sms': False,
        }
        return Response(settings)
    
    elif request.method == 'PATCH':
        serializer = NotificationSettingsSerializer(data=request.data, partial=True)
        if serializer.is_valid():
            # TODO: Save notification settings to user profile or separate model
            # For now, just return success
            return Response({
                'message': 'Notification settings updated successfully',
                'settings': serializer.validated_data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
