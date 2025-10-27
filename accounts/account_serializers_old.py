"""
Account Management Serializers
Serializers for user account management (profile, security, preferences)
"""

from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User


class UpdateProfileSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile"""
    
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone_number', 'address']
    
    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class ProfilePictureSerializer(serializers.Serializer):
    """Serializer for profile picture upload"""
    profile_picture = serializers.ImageField(required=True)
    
    def validate_profile_picture(self, value):
        # Validate file size (5MB max)
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Image file size cannot exceed 5MB")
        
        # Validate file type
        allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
        if value.content_type not in allowed_types:
            raise serializers.ValidationError(
                "Only JPEG, PNG, GIF, and WebP images are allowed"
            )
        
        return value


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for changing password"""
    current_password = serializers.CharField(required=True, write_only=True)
    new_password = serializers.CharField(required=True, write_only=True)
    confirm_password = serializers.CharField(required=True, write_only=True)
    
    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect")
        return value
    
    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({
                'confirm_password': 'Passwords do not match'
            })
        
        # Validate new password strength
        try:
            validate_password(data['new_password'], self.context['request'].user)
        except Exception as e:
            raise serializers.ValidationError({'new_password': list(e.messages)})
        
        return data
    
    def save(self):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class UserPreferencesSerializer(serializers.Serializer):
    """Serializer for user preferences"""
    language = serializers.ChoiceField(
        choices=['en', 'fr', 'es'],
        required=False
    )
    timezone = serializers.CharField(max_length=50, required=False)
    date_format = serializers.ChoiceField(
        choices=['DD/MM/YYYY', 'MM/DD/YYYY', 'YYYY-MM-DD'],
        required=False
    )
    time_format = serializers.ChoiceField(
        choices=['12h', '24h'],
        required=False
    )
    currency = serializers.CharField(max_length=3, required=False)
    enable_email_notifications = serializers.BooleanField(required=False)
    enable_push_notifications = serializers.BooleanField(required=False)
    enable_sms_notifications = serializers.BooleanField(required=False)


class NotificationSettingsSerializer(serializers.Serializer):
    """Serializer for notification settings"""
    sales_email = serializers.BooleanField(required=False)
    sales_push = serializers.BooleanField(required=False)
    sales_sms = serializers.BooleanField(required=False)
    
    inventory_email = serializers.BooleanField(required=False)
    inventory_push = serializers.BooleanField(required=False)
    inventory_sms = serializers.BooleanField(required=False)
    
    payments_email = serializers.BooleanField(required=False)
    payments_push = serializers.BooleanField(required=False)
    payments_sms = serializers.BooleanField(required=False)
    
    users_email = serializers.BooleanField(required=False)
    users_push = serializers.BooleanField(required=False)
    users_sms = serializers.BooleanField(required=False)
    
    system_email = serializers.BooleanField(required=False)
    system_push = serializers.BooleanField(required=False)
    system_sms = serializers.BooleanField(required=False)


class UserProfileSerializer(serializers.ModelSerializer):
    """Complete user profile serializer"""
    preferences = serializers.SerializerMethodField()
    notification_settings = serializers.SerializerMethodField()
    profile_picture = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'phone_number',
            'address', 'profile_picture', 'platform_role', 'is_active',
            'date_joined', 'preferences', 'notification_settings'
        ]
        read_only_fields = ['id', 'email', 'platform_role', 'is_active', 'date_joined']
    
    def get_profile_picture(self, obj):
        # Return None for now since User model doesn't have this field yet
        return None
    
    def get_preferences(self, obj):
        # Get preferences from user's metadata or settings
        return {
            'language': getattr(obj, 'language', 'en'),
            'timezone': getattr(obj, 'timezone', 'Africa/Accra'),
            'date_format': getattr(obj, 'date_format', 'DD/MM/YYYY'),
            'time_format': getattr(obj, 'time_format', '24h'),
            'currency': getattr(obj, 'currency', 'GHS'),
            'enable_email_notifications': True,
            'enable_push_notifications': True,
            'enable_sms_notifications': False,
        }
    
    def get_notification_settings(self, obj):
        # Get notification settings - default values for now
        return {
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


class Enable2FASerializer(serializers.Serializer):
    """Serializer for enabling 2FA"""
    pass  # Will return QR code data


class Disable2FASerializer(serializers.Serializer):
    """Serializer for disabling 2FA"""
    password = serializers.CharField(required=True, write_only=True)
    
    def validate_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Password is incorrect")
        return value
