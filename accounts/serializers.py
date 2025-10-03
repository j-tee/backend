import rules  # type: ignore[import]

from rest_framework import serializers
from django.contrib.auth import authenticate
from django.utils import timezone
from django.db import transaction
from rest_framework.exceptions import PermissionDenied

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
from inventory.models import (
    BusinessStoreFront,
    StoreFront,
    StoreFrontEmployee,
    WarehouseEmployee,
)


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
            'subscription_status', 'account_type', 'platform_role', 'email_verified', 'is_active',
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
    ip_address = serializers.CharField(read_only=True, allow_blank=True, allow_null=True)
    
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
    platform_role = serializers.CharField(source='user.platform_role', read_only=True)
    
    class Meta:
        model = BusinessMembership
        fields = [
            'id', 'business', 'business_name', 'user', 'user_name',
            'role', 'is_admin', 'is_active', 'platform_role', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'business_name', 'user_name', 'platform_role']


class BusinessSummarySerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.name', read_only=True)

    class Meta:
        model = Business
        fields = [
            'id', 'name', 'tin', 'email', 'address', 'website', 'phone_numbers',
            'social_handles', 'is_active', 'owner', 'owner_name', 'created_at', 'updated_at'
        ]
        read_only_fields = fields


class BusinessMembershipSummarySerializer(serializers.ModelSerializer):
    business = BusinessSummarySerializer(read_only=True)
    storefronts = serializers.SerializerMethodField()
    warehouses = serializers.SerializerMethodField()

    class Meta:
        model = BusinessMembership
        fields = [
            'id',
            'role',
            'is_admin',
            'is_active',
            'business',
            'storefronts',
            'warehouses',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_storefronts(self, obj):
        assignments = (
            StoreFrontEmployee.objects.filter(
                business=obj.business,
                user=obj.user,
                is_active=True,
            )
            .select_related('storefront')
        )
        return [
            {
                'id': str(assignment.storefront.id),
                'name': assignment.storefront.name,
                'location': assignment.storefront.location,
            }
            for assignment in assignments
        ]

    def get_warehouses(self, obj):
        assignments = (
            WarehouseEmployee.objects.filter(
                business=obj.business,
                user=obj.user,
                is_active=True,
            )
            .select_related('warehouse')
        )
        return [
            {
                'id': str(assignment.warehouse.id),
                'name': assignment.warehouse.name,
                'location': assignment.warehouse.location,
            }
            for assignment in assignments
        ]


class MembershipUserSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'name', 'email', 'is_active', 'platform_role']
        read_only_fields = fields


class BusinessMembershipDetailSerializer(serializers.ModelSerializer):
    user = MembershipUserSummarySerializer(read_only=True)
    assigned_storefronts = serializers.SerializerMethodField()
    assigned_warehouses = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    platform_role = serializers.CharField(source='user.platform_role', read_only=True)
    role_matrix = serializers.SerializerMethodField()

    class Meta:
        model = BusinessMembership
        fields = [
            'id', 'business', 'user', 'role', 'is_admin', 'is_active', 'status',
            'platform_role', 'role_matrix', 'assigned_storefronts', 'assigned_warehouses',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id',
            'business',
            'user',
            'is_admin',
            'created_at',
            'updated_at',
            'status',
            'platform_role',
            'role_matrix',
            'assigned_storefronts',
            'assigned_warehouses',
        ]

    def get_assigned_storefronts(self, obj):
        assignments = StoreFrontEmployee.objects.filter(
            business=obj.business,
            user=obj.user,
            is_active=True,
        ).select_related('storefront')

        return [
            {
                'id': assignment.storefront.id,
                'name': assignment.storefront.name,
                'location': assignment.storefront.location,
            }
            for assignment in assignments
        ]

    def get_assigned_warehouses(self, obj):
        assignments = WarehouseEmployee.objects.filter(
            business=obj.business,
            user=obj.user,
            is_active=True,
        ).select_related('warehouse')

        return [
            {
                'id': assignment.warehouse.id,
                'name': assignment.warehouse.name,
                'location': assignment.warehouse.location,
            }
            for assignment in assignments
        ]

    def get_status(self, obj):
        return 'ACTIVE' if obj.is_active else 'SUSPENDED'

    def get_role_matrix(self, obj):
        user = obj.user
        business_role = obj.role
        return {
            'business': {
                'role': business_role,
                'is_owner': business_role == BusinessMembership.OWNER,
                'is_admin': obj.is_admin,
                'is_manager': business_role == BusinessMembership.MANAGER,
                'is_staff': business_role == BusinessMembership.STAFF,
            },
            'platform': {
                'role': user.platform_role,
                'is_platform_super_admin': user.is_platform_super_admin,
                'is_platform_admin': user.is_platform_admin,
                'is_platform_staff': user.is_platform_staff,
            }
        }


class BusinessMembershipUpdateSerializer(serializers.ModelSerializer):
    platform_role = serializers.ChoiceField(
        choices=[choice[0] for choice in User.PLATFORM_ROLE_CHOICES],
        required=False,
        allow_null=True,
    )

    class Meta:
        model = BusinessMembership
        fields = ['role', 'is_active', 'platform_role']

    def update(self, instance, validated_data):
        request = self.context.get('request')
        platform_role_value = validated_data.pop('platform_role', serializers.empty)

        if platform_role_value is not serializers.empty:
            if request is None or not rules.has_perm('accounts.assign_platform_roles', request.user):
                raise PermissionDenied('You do not have permission to assign platform roles.')

            target_user = instance.user
            normalized_role = platform_role_value or User.PLATFORM_NONE
            if normalized_role not in dict(User.PLATFORM_ROLE_CHOICES):
                raise serializers.ValidationError({'platform_role': 'Invalid platform role.'})
            target_user.platform_role = normalized_role
            target_user.save(update_fields=['platform_role', 'updated_at'])

        update_fields = []
        if 'role' in validated_data:
            role = validated_data['role']
            instance.role = role
            instance.is_admin = role in {BusinessMembership.OWNER, BusinessMembership.ADMIN}
            update_fields.extend(['role', 'is_admin'])
        if 'is_active' in validated_data:
            instance.is_active = validated_data['is_active']
            update_fields.append('is_active')

        if update_fields:
            update_fields.append('updated_at')
            instance.save(update_fields=update_fields)
        elif platform_role_value is not serializers.empty:
            instance.save(update_fields=['updated_at'])

        return instance


class MembershipStorefrontAssignmentSerializer(serializers.Serializer):
    storefronts = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=True,
    )

    def validate_storefronts(self, value):
        request = self.context.get('request')
        membership: BusinessMembership = self.context['membership']
        allowed_storefront_ids = set(
            BusinessStoreFront.objects.filter(
                business=membership.business,
                is_active=True,
            ).values_list('storefront_id', flat=True)
        )
        invalid_ids = [str(item) for item in value if item not in allowed_storefront_ids]
        if invalid_ids:
            raise serializers.ValidationError(
                f"Storefront(s) {', '.join(invalid_ids)} do not belong to this business."
            )
        return value


class BusinessInvitationSerializer(serializers.ModelSerializer):
    invited_by_name = serializers.CharField(source='invited_by.name', read_only=True)
    storefronts = serializers.SerializerMethodField()
    storefront_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
    )
    send_email = serializers.BooleanField(write_only=True, default=True)

    class Meta:
        model = BusinessInvitation
        fields = [
            'id', 'business', 'email', 'role', 'status', 'token', 'expires_at',
            'invited_by', 'invited_by_name', 'created_at', 'updated_at',
            'storefronts', 'storefront_ids', 'send_email', 'accepted_at'
        ]
        read_only_fields = [
            'id', 'business', 'status', 'token', 'invited_by', 'invited_by_name',
            'created_at', 'updated_at', 'storefronts', 'accepted_at'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._send_email = True
        self._storefront_ids = []

    def validate_email(self, value):
        business = self.context['business']
        normalized = value.lower()
        if BusinessInvitation.objects.filter(
            business=business,
            email__iexact=normalized,
            status=BusinessInvitation.STATUS_PENDING,
        ).exists():
            raise serializers.ValidationError('This email already has a pending invitation for this business.')

        if BusinessMembership.objects.filter(
            business=business,
            user__email__iexact=normalized,
            is_active=True,
        ).exists():
            raise serializers.ValidationError('This user is already a member of the business.')

        return normalized

    def validate_storefront_ids(self, value):
        business = self.context['business']
        if not value:
            return []

        valid_ids = set(
            BusinessStoreFront.objects.filter(
                business=business,
                storefront_id__in=value,
                is_active=True,
            ).values_list('storefront_id', flat=True)
        )
        requested_ids = set(value)
        missing = requested_ids - valid_ids
        if missing:
            missing_str = ', '.join(str(item) for item in missing)
            raise serializers.ValidationError(f"Storefront(s) {missing_str} do not belong to the business or are inactive.")
        return list(requested_ids)

    def create(self, validated_data):
        storefront_ids = validated_data.pop('storefront_ids', [])
        send_email = validated_data.pop('send_email', True)
        business = self.context['business']

        invitation = BusinessInvitation(
            business=business,
            **validated_data,
        )
        invitation.invited_by = self.context['request'].user
        invitation.initialize_token()
        invitation.payload = {'storefront_ids': storefront_ids}
        invitation.save()

        self._send_email = send_email
        self._storefront_ids = storefront_ids

        return invitation

    def get_storefronts(self, obj):
        ids = obj.get_storefront_ids()
        if not ids:
            return []

        storefronts = StoreFront.objects.filter(id__in=ids)
        store_map = {store.id: store for store in storefronts}
        ordered = []
        for identifier in ids:
            store = store_map.get(identifier)
            if store:
                ordered.append({
                    'id': store.id,
                    'name': store.name,
                    'location': store.location,
                })
        return ordered

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        show_token = self.context.get('show_token', False)
        if not show_token:
            if not request or not request.user.is_superuser:
                data['token'] = None
        return data


class BusinessInvitationAcceptSerializer(serializers.Serializer):
    email = serializers.EmailField()
    name = serializers.CharField(max_length=255)
    password = serializers.CharField(write_only=True, min_length=8)
    phone = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate(self, attrs):
        invitation: BusinessInvitation = self.context['invitation']
        supplied_email = attrs['email'].lower()

        if invitation.status == BusinessInvitation.STATUS_REVOKED:
            raise serializers.ValidationError({'email': 'This invitation has been revoked.'})

        if invitation.is_expired:
            invitation.mark_expired()
            raise serializers.ValidationError({'email': 'The invitation for this email has expired. Request a new invitation.'})

        if invitation.email.lower() != supplied_email:
            raise serializers.ValidationError({'email': 'Invitation email does not match the provided address.'})

        if User.objects.filter(email__iexact=supplied_email).exists():
            raise serializers.ValidationError({'email': 'A user with this email already exists.'})

        attrs['email'] = supplied_email
        return attrs

    def save(self, **kwargs):
        invitation: BusinessInvitation = self.context['invitation']
        business = invitation.business
        email = self.validated_data['email']
        name = self.validated_data['name']
        password = self.validated_data['password']
        phone = self.validated_data.get('phone')

        with transaction.atomic():
            user = User.objects.create_user(
                email=email,
                password=password,
                name=name,
                account_type=User.ACCOUNT_EMPLOYEE,
                is_active=True,
            )
            user.email_verified = True
            user.save(update_fields=['email_verified', 'is_active', 'updated_at'])

            if phone:
                UserProfile.objects.update_or_create(user=user, defaults={'phone': phone})

            membership, _ = BusinessMembership.objects.update_or_create(
                business=business,
                user=user,
                defaults={
                    'role': invitation.role,
                    'is_admin': invitation.role in {BusinessMembership.OWNER, BusinessMembership.ADMIN},
                    'invited_by': invitation.invited_by,
                    'is_active': True,
                },
            )

            now = timezone.now()
            storefront_ids = invitation.get_storefront_ids()
            if storefront_ids:
                for storefront_id in storefront_ids:
                    assignment, created = StoreFrontEmployee.objects.get_or_create(
                        business=business,
                        storefront_id=storefront_id,
                        user=user,
                        defaults={
                            'role': invitation.role,
                            'is_active': True,
                        },
                    )
                    if not created:
                        assignment.role = invitation.role
                        assignment.is_active = True
                        assignment.removed_at = None
                        assignment.assigned_at = now
                        assignment.save(update_fields=['role', 'is_active', 'removed_at', 'assigned_at'])

            invitation.mark_accepted(user)
            token, _ = Token.objects.get_or_create(user=user)

        self.user = user
        self.membership = membership
        self.token = token
        return invitation



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