from rest_framework import serializers
from django.contrib.auth import authenticate
from django.utils import timezone
from django.db import transaction

from .models import (
    Role,
    User,
    UserProfile,
    AuditLog,
    Business,
    BusinessMembership,
    BusinessInvitation,
    EmailVerificationToken,
    PasswordResetToken,
)
from rest_framework.authtoken.models import Token

from .utils import send_verification_email, send_password_reset_email, EmailDeliveryError


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ['id', 'name', 'description', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ['id', 'phone', 'address', 'date_of_birth', 'emergency_contact', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class UserSerializer(serializers.ModelSerializer):
    profile = UserProfileSerializer(read_only=True)
    role_name = serializers.CharField(source='role.name', read_only=True)
    password = serializers.CharField(write_only=True, min_length=8, required=False)
    
    class Meta:
        model = User
        fields = [
            'id', 'name', 'email', 'role', 'role_name', 'picture_url',
            'subscription_status', 'account_type', 'email_verified', 'is_active',
            'profile', 'password', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'email_verified', 'created_at', 'updated_at']
        extra_kwargs = {
            'password': {'write_only': True},
        }
    
    def create(self, validated_data):
        password = validated_data.pop('password', None)
        if not password:
            raise serializers.ValidationError({'password': 'Password is required when creating a user.'})
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user
    
    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        if password:
            instance.set_password(password)
        
        instance.save()
        return instance


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()
    
    def validate(self, data):
        email = data.get('email')
        password = data.get('password')
        
        if not (email and password):
            raise serializers.ValidationError('Must include email and password.')

        user = authenticate(email=email, password=password)

        if user:
            if not user.email_verified:
                raise serializers.ValidationError('Email not verified. Please check your inbox for the verification link.')
            if not user.is_active:
                raise serializers.ValidationError('User account is disabled.')
            data['user'] = user
            return data

        try:
            existing_user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise serializers.ValidationError('Invalid email or password.')

        if not existing_user.email_verified:
            raise serializers.ValidationError('Email not verified. Please check your inbox for the verification link.')
        if not existing_user.is_active:
            raise serializers.ValidationError('User account is disabled.')

        raise serializers.ValidationError('Invalid email or password.')
        
        return data


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)
    
    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Old password is incorrect.')
        return value

    def validate(self, attrs):
        if attrs['old_password'] == attrs['new_password']:
            raise serializers.ValidationError({'new_password': 'The new password must be different from the current password.'})
        return attrs


class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.name', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id', 'user', 'user_name', 'action', 'model_name', 'object_id',
            'changes', 'ip_address', 'user_agent', 'timestamp'
        ]
        read_only_fields = ['id', 'timestamp']


class BusinessMembershipSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.name', read_only=True)
    business_name = serializers.CharField(source='business.name', read_only=True)
    
    class Meta:
        model = BusinessMembership
        fields = [
            'id', 'business', 'business_name', 'user', 'user_name',
            'role', 'is_admin', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'business_name', 'user_name']


class BusinessSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.name', read_only=True)
    memberships = BusinessMembershipSerializer(many=True, read_only=True)
    
    class Meta:
        model = Business
        fields = [
            'id', 'name', 'tin', 'email', 'address', 'website', 'phone_numbers',
            'social_handles', 'is_active', 'owner', 'owner_name',
            'memberships', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'owner', 'owner_name', 'memberships', 'created_at', 'updated_at']


class UserRegistrationSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    account_type = serializers.ChoiceField(choices=User.ACCOUNT_TYPE_CHOICES, default=User.ACCOUNT_OWNER)

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value.lower()

    def validate(self, attrs):
        email = attrs['email']
        account_type = attrs['account_type']

        if account_type == User.ACCOUNT_EMPLOYEE:
            invitation = BusinessInvitation.objects.filter(
                email__iexact=email,
                status=BusinessInvitation.STATUS_PENDING,
            ).order_by('-created_at').first()

            if not invitation:
                raise serializers.ValidationError({
                    'email': 'No pending employee invitation found for this email. Contact your business administrator.'
                })

            if invitation.is_expired:
                invitation.mark_expired()
                raise serializers.ValidationError({
                    'email': 'The invitation for this email has expired. Request a new invitation from your administrator.'
                })

            attrs['invitation'] = invitation

        return attrs

    def create(self, validated_data):
        invitation = validated_data.pop('invitation', None)
        password = validated_data.pop('password')

        with transaction.atomic():
            user = User.objects.create_user(
                password=password,
                is_active=False,
                email_verified=False,
                **validated_data,
            )

            verification = EmailVerificationToken.create_for_user(user)

            try:
                send_verification_email(user, verification.token)
            except EmailDeliveryError as exc:
                raise serializers.ValidationError({
                    'email': 'Unable to send verification email. Please try again later.'
                }) from exc

        self.verification = verification
        self.invitation = invitation

        return user


class EmailVerificationSerializer(serializers.Serializer):
    token = serializers.CharField()

    def validate_token(self, value):
        try:
            verification = EmailVerificationToken.objects.select_related('user').get(token=value)
        except EmailVerificationToken.DoesNotExist as exc:
            raise serializers.ValidationError('Invalid or expired verification token.') from exc

        if verification.is_consumed:
            raise serializers.ValidationError('This verification token has already been used.')

        if verification.is_expired:
            raise serializers.ValidationError('This verification token has expired. Please register again to receive a new link.')

        self.verification = verification
        return value

    def save(self, **kwargs):
        verification = self.verification
        user = verification.user
        invitation = None

        if user.account_type == User.ACCOUNT_EMPLOYEE:
            invitation = BusinessInvitation.objects.filter(
                email__iexact=user.email,
                status=BusinessInvitation.STATUS_PENDING,
            ).order_by('-created_at').first()

            if not invitation or invitation.is_expired:
                raise serializers.ValidationError('No valid employee invitation is available for this account.')

        verification.mark_consumed()
        user.email_verified = True
        user.is_active = True
        user.save(update_fields=['email_verified', 'is_active', 'updated_at'])

        if invitation:
            membership_defaults = {
                'role': invitation.role,
                'is_admin': invitation.role in {BusinessMembership.OWNER, BusinessMembership.ADMIN},
                'invited_by': invitation.invited_by,
                'is_active': True,
            }

            membership, _ = BusinessMembership.objects.update_or_create(
                business=invitation.business,
                user=user,
                defaults=membership_defaults,
            )

            invitation.mark_accepted(user)
            self.membership = membership

        return user


class OwnerBusinessRegistrationSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    tin = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    address = serializers.CharField()
    phone_numbers = serializers.ListField(child=serializers.CharField(), allow_empty=False)
    website = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    social_handles = serializers.DictField(child=serializers.CharField(), required=False)

    def validate_tin(self, value):
        if Business.objects.filter(tin=value).exists():
            raise serializers.ValidationError('A business with this TIN already exists.')
        return value

    def create(self, validated_data):
        request = self.context['request']
        user = request.user

        business = Business.objects.create(
            owner=user,
            name=validated_data['name'],
            tin=validated_data['tin'],
            email=validated_data['email'],
            address=validated_data['address'],
            phone_numbers=validated_data['phone_numbers'],
            social_handles=validated_data.get('social_handles', {}),
            website=validated_data.get('website'),
        )

        return business


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            user = User.objects.get(email__iexact=value)
        except User.DoesNotExist:
            self.user = None
            return value

        if not user.email_verified:
            raise serializers.ValidationError('Email is not verified. Please verify your email before requesting a password reset.')
        if not user.is_active:
            raise serializers.ValidationError('Account is inactive. Contact your administrator.')

        self.user = user
        return value

    def save(self, **kwargs):
        user = getattr(self, 'user', None)
        if not user:
            return None

        with transaction.atomic():
            reset_token = PasswordResetToken.create_for_user(user)
            try:
                send_password_reset_email(user, reset_token.token)
            except EmailDeliveryError as exc:
                raise serializers.ValidationError({
                    'email': 'Unable to send password reset email. Please try again later.'
                }) from exc

        return reset_token


class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=8)

    def validate_token(self, value):
        try:
            reset_token = PasswordResetToken.objects.select_related('user').get(token=value)
        except PasswordResetToken.DoesNotExist as exc:
            raise serializers.ValidationError('Invalid or expired password reset token.') from exc

        if reset_token.is_consumed:
            raise serializers.ValidationError('This password reset token has already been used.')
        if reset_token.is_expired:
            raise serializers.ValidationError('This password reset token has expired. Please request a new one.')

        self.reset_token = reset_token
        return value

    def validate(self, attrs):
        token = getattr(self, 'reset_token', None)
        if token and token.user.check_password(attrs['new_password']):
            raise serializers.ValidationError({'new_password': 'The new password must be different from the current password.'})
        return attrs

    def save(self, **kwargs):
        reset_token = self.reset_token
        user = reset_token.user
        new_password = self.validated_data['new_password']

        user.set_password(new_password)
        user.save(update_fields=['password', 'updated_at'])

        reset_token.mark_consumed()
        Token.objects.filter(user=user).delete()

        return user