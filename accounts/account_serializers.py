"""
Account Management Serializers (Updated)
Serializers for user account management with database persistence
"""

from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from .models import User
import pyotp
import qrcode
import qrcode.image.svg
from io import BytesIO
import base64


class UpdateProfileSerializer(serializers.ModelSerializer):
    """Serializer for updating user profile"""
    
    class Meta:
        model = User
        fields = ['name']
    
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
        choices=[('en', 'English'), ('fr', 'French'), ('es', 'Spanish')],
        required=False
    )
    timezone = serializers.CharField(max_length=50, required=False)
    date_format = serializers.ChoiceField(
        choices=[('DD/MM/YYYY', 'DD/MM/YYYY'), ('MM/DD/YYYY', 'MM/DD/YYYY'), ('YYYY-MM-DD', 'YYYY-MM-DD')],
        required=False
    )
    time_format = serializers.ChoiceField(
        choices=[('12h', '12 Hour'), ('24h', '24 Hour')],
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
    """Complete user profile serializer with database fields"""
    preferences = serializers.SerializerMethodField()
    notification_settings = serializers.SerializerMethodField()
    profile_picture_url = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'name', 'profile_picture', 'profile_picture_url', 
            'platform_role', 'is_active', 'created_at', 
            'preferences', 'notification_settings', 'two_factor_enabled'
        ]
        read_only_fields = ['id', 'email', 'platform_role', 'is_active', 'created_at', 'two_factor_enabled']
    
    def get_profile_picture_url(self, obj):
        if obj.profile_picture:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile_picture.url)
            return obj.profile_picture.url
        elif obj.picture_url:
            return obj.picture_url
        return None
    
    def get_preferences(self, obj):
        return {
            'language': obj.language,
            'timezone': obj.timezone,
            'date_format': obj.date_format,
            'time_format': obj.time_format,
            'currency': obj.currency,
            'enable_email_notifications': obj.preferences.get('enable_email_notifications', True),
            'enable_push_notifications': obj.preferences.get('enable_push_notifications', True),
            'enable_sms_notifications': obj.preferences.get('enable_sms_notifications', False),
        }
    
    def get_notification_settings(self, obj):
        defaults = {
            'sales_email': True, 'sales_push': True, 'sales_sms': False,
            'inventory_email': True, 'inventory_push': True, 'inventory_sms': False,
            'payments_email': True, 'payments_push': True, 'payments_sms': False,
            'users_email': True, 'users_push': False, 'users_sms': False,
            'system_email': True, 'system_push': True, 'system_sms': False,
        }
        return {**defaults, **obj.notification_settings}


class Enable2FASerializer(serializers.Serializer):
    """Serializer for enabling 2FA with QR code generation"""
    
    def generate_qr_code(self, user):
        """Generate TOTP secret and QR code"""
        # Generate secret
        secret = pyotp.random_base32()
        
        # Generate provisioning URI
        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(
            name=user.email,
            issuer_name='POS System'
        )
        
        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        # Generate backup codes
        import secrets
        backup_codes = [
            '-'.join([secrets.token_hex(2) for _ in range(2)])
            for _ in range(8)
        ]
        
        return {
            'secret': secret,
            'qr_code': f'data:image/png;base64,{qr_code_base64}',
            'backup_codes': backup_codes
        }


class Disable2FASerializer(serializers.Serializer):
    """Serializer for disabling 2FA"""
    password = serializers.CharField(required=True, write_only=True)
    
    def validate_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Password is incorrect")
        return value


class Verify2FASerializer(serializers.Serializer):
    """Serializer for verifying 2FA code"""
    code = serializers.CharField(required=True, max_length=6, min_length=6)
    
    def validate_code(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("Code must be 6 digits")
        return value
