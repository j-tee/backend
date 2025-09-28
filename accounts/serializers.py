from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import Role, User, UserProfile, AuditLog, Business, BusinessMembership
from rest_framework.authtoken.models import Token


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
    password = serializers.CharField(write_only=True, min_length=8)
    
    class Meta:
        model = User
        fields = [
            'id', 'name', 'email', 'role', 'role_name', 'picture_url', 
            'subscription_status', 'is_active', 'profile', 'password',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'password': {'write_only': True},
        }
    
    def create(self, validated_data):
        password = validated_data.pop('password')
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
        
        if email and password:
            user = authenticate(email=email, password=password)
            if not user:
                raise serializers.ValidationError('Invalid email or password.')
            if not user.is_active:
                raise serializers.ValidationError('User account is disabled.')
            data['user'] = user
        else:
            raise serializers.ValidationError('Must include email and password.')
        
        return data


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)
    
    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('Old password is incorrect.')
        return value


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


class BusinessRegistrationSerializer(serializers.Serializer):
    owner_name = serializers.CharField(max_length=255)
    owner_email = serializers.EmailField()
    owner_password = serializers.CharField(write_only=True, min_length=8)
    business_name = serializers.CharField(max_length=255)
    business_tin = serializers.CharField(max_length=100)
    business_email = serializers.EmailField()
    business_address = serializers.CharField()
    business_phone_numbers = serializers.ListField(child=serializers.CharField(), allow_empty=False)
    business_website = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    business_social_handles = serializers.DictField(child=serializers.CharField(), required=False)
    generate_token = serializers.BooleanField(default=True)

    def validate_owner_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value

    def validate_business_tin(self, value):
        if Business.objects.filter(tin=value).exists():
            raise serializers.ValidationError('A business with this TIN already exists.')
        return value

    def create(self, validated_data):
        social_handles = validated_data.get('business_social_handles', {})
        business_website = validated_data.get('business_website')
        generate_token = validated_data.pop('generate_token', True)

        owner = User.objects.create_user(
            email=validated_data['owner_email'],
            password=validated_data['owner_password'],
            name=validated_data['owner_name']
        )

        business = Business.objects.create(
            owner=owner,
            name=validated_data['business_name'],
            tin=validated_data['business_tin'],
            email=validated_data['business_email'],
            address=validated_data['business_address'],
            phone_numbers=validated_data['business_phone_numbers'],
            social_handles=social_handles,
            website=business_website
        )

        token = Token.objects.create(user=owner) if generate_token else None

        return {
            'user': owner,
            'business': business,
            'token': token.key if token else None
        }