"""
Account Management Views (Updated)
API views for user account management with real 2FA implementation
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .account_serializers import (
    UpdateProfileSerializer,
    ProfilePictureSerializer,
    ChangePasswordSerializer,
    UserPreferencesSerializer,
    NotificationSettingsSerializer,
    UserProfileSerializer,
    Enable2FASerializer,
    Disable2FASerializer,
    Verify2FASerializer
)
from .models import User
import pyotp


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def user_profile(request):
    """
    Get or update user profile
    """
    if request.method == 'GET':
        serializer = UserProfileSerializer(request.user, context={'request': request})
        return Response(serializer.data)
    
    elif request.method == 'POST':
        serializer = UpdateProfileSerializer(
            request.user,
            data=request.data,
            partial=True
        )
        if serializer.is_valid():
            serializer.save()
            profile_serializer = UserProfileSerializer(request.user, context={'request': request})
            return Response({
                'message': 'Profile updated successfully',
                'user': profile_serializer.data
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_profile_picture(request):
    """
    Upload profile picture
    """
    serializer = ProfilePictureSerializer(data=request.data)
    if serializer.is_valid():
        user = request.user
        user.profile_picture = serializer.validated_data['profile_picture']
        user.save()
        
        profile_serializer = UserProfileSerializer(user, context={'request': request})
        return Response({
            'message': 'Profile picture uploaded successfully',
            'user': profile_serializer.data
        })
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """
    Change user password
    """
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
    """
    Enable two-factor authentication with QR code
    """
    user = request.user
    
    # Check if 2FA is already enabled
    if user.two_factor_enabled:
        return Response(
            {'message': '2FA is already enabled'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Generate QR code and secret
    serializer = Enable2FASerializer()
    data = serializer.generate_qr_code(user)
    
    # Save secret and backup codes (but don't enable yet)
    user.two_factor_secret = data['secret']
    user.backup_codes = data['backup_codes']
    user.save()
    
    return Response({
        'message': '2FA setup initiated. Please scan the QR code and verify with a code.',
        'qr_code': data['qr_code'],
        'secret': data['secret'],
        'backup_codes': data['backup_codes']
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def verify_2fa_setup(request):
    """
    Verify 2FA setup by validating the first code
    """
    user = request.user
    
    if user.two_factor_enabled:
        return Response(
            {'message': '2FA is already enabled'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    serializer = Verify2FASerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    code = serializer.validated_data['code']
    
    # Verify the code
    totp = pyotp.TOTP(user.two_factor_secret)
    if totp.verify(code, valid_window=1):
        user.two_factor_enabled = True
        user.save()
        return Response({
            'message': '2FA enabled successfully'
        })
    else:
        return Response(
            {'error': 'Invalid verification code'},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def disable_2fa(request):
    """
    Disable two-factor authentication
    """
    user = request.user
    
    if not user.two_factor_enabled:
        return Response(
            {'message': '2FA is not enabled'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    serializer = Disable2FASerializer(
        data=request.data,
        context={'request': request}
    )
    if serializer.is_valid():
        user.two_factor_enabled = False
        user.two_factor_secret = None
        user.backup_codes = []
        user.save()
        
        return Response({
            'message': '2FA disabled successfully'
        })
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def user_preferences(request):
    """
    Get or update user preferences
    """
    user = request.user
    
    if request.method == 'GET':
        return Response({
            'language': user.language,
            'timezone': user.timezone,
            'date_format': user.date_format,
            'time_format': user.time_format,
            'currency': user.currency,
            'enable_email_notifications': user.preferences.get('enable_email_notifications', True),
            'enable_push_notifications': user.preferences.get('enable_push_notifications', True),
            'enable_sms_notifications': user.preferences.get('enable_sms_notifications', False),
        })
    
    elif request.method == 'PATCH':
        serializer = UserPreferencesSerializer(data=request.data, partial=True)
        if serializer.is_valid():
            data = serializer.validated_data
            
            # Update model fields
            if 'language' in data:
                user.language = data['language']
            if 'timezone' in data:
                user.timezone = data['timezone']
            if 'date_format' in data:
                user.date_format = data['date_format']
            if 'time_format' in data:
                user.time_format = data['time_format']
            if 'currency' in data:
                user.currency = data['currency']
            
            # Update preferences JSONField
            preferences = user.preferences or {}
            if 'enable_email_notifications' in data:
                preferences['enable_email_notifications'] = data['enable_email_notifications']
            if 'enable_push_notifications' in data:
                preferences['enable_push_notifications'] = data['enable_push_notifications']
            if 'enable_sms_notifications' in data:
                preferences['enable_sms_notifications'] = data['enable_sms_notifications']
            
            user.preferences = preferences
            user.save()
            
            return Response({
                'message': 'Preferences updated successfully'
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def notification_settings(request):
    """
    Get or update notification settings
    """
    user = request.user
    
    if request.method == 'GET':
        defaults = {
            'sales_email': True, 'sales_push': True, 'sales_sms': False,
            'inventory_email': True, 'inventory_push': True, 'inventory_sms': False,
            'payments_email': True, 'payments_push': True, 'payments_sms': False,
            'users_email': True, 'users_push': False, 'users_sms': False,
            'system_email': True, 'system_push': True, 'system_sms': False,
        }
        settings = {**defaults, **(user.notification_settings or {})}
        return Response(settings)
    
    elif request.method == 'PATCH':
        serializer = NotificationSettingsSerializer(data=request.data, partial=True)
        if serializer.is_valid():
            # Update notification_settings JSONField
            settings = user.notification_settings or {}
            settings.update(serializer.validated_data)
            user.notification_settings = settings
            user.save()
            
            return Response({
                'message': 'Notification settings updated successfully'
            })
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
