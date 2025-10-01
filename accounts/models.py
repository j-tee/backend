import secrets
import uuid
from datetime import timedelta

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class RoleManager(models.Manager):
    def get_admin_role(self):
        return self.get(name='Admin')
    
    def get_cashier_role(self):
        return self.get(name='Cashier')
    
    def get_manager_role(self):
        return self.get(name='Manager')
    
    def get_warehouse_staff_role(self):
        return self.get(name='Warehouse Staff')


class Role(models.Model):
    """User roles for role-based access control"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = RoleManager()
    
    class Meta:
        db_table = 'roles'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class UserManager(BaseUserManager):
    """Custom user manager for UUID primary keys"""
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user model with UUID primary key"""
    ACCOUNT_OWNER = 'OWNER'
    ACCOUNT_EMPLOYEE = 'EMPLOYEE'
    ACCOUNT_TYPE_CHOICES = [
        (ACCOUNT_OWNER, 'Business Owner'),
        (ACCOUNT_EMPLOYEE, 'Employee'),
    ]
    SUBSCRIPTION_STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
        ('Cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    role = models.ForeignKey(Role, on_delete=models.PROTECT, null=True, blank=True)
    picture_url = models.URLField(blank=True, null=True)
    subscription_status = models.CharField(
        max_length=50, 
        choices=SUBSCRIPTION_STATUS_CHOICES, 
        default='Inactive'
    )
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES, default=ACCOUNT_OWNER)
    email_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']
    
    class Meta:
        db_table = 'users'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.email})"
    
    def has_role(self, role_name):
        """Check if user has a specific role"""
        return self.role and self.role.name == role_name
    
    def is_admin(self):
        return self.has_role('Admin')
    
    def is_cashier(self):
        return self.has_role('Cashier')
    
    def is_manager(self):
        return self.has_role('Manager')
    
    def is_warehouse_staff(self):
        return self.has_role('Warehouse Staff')

    def active_business_memberships(self):
        """Return queryset of active business memberships."""
        return self.business_memberships.filter(is_active=True)

    @property
    def primary_business(self):
        """Return the first active business membership's business, if any."""
        membership = self.active_business_memberships().order_by('created_at').first()
        return membership.business if membership else None

    def add_business_membership(self, business, role='STAFF', is_admin=False, invited_by=None):
        """Helper to create or update a business membership for this user."""
        membership, _ = BusinessMembership.objects.update_or_create(
            business=business,
            user=self,
            defaults={
                'role': role,
                'is_admin': is_admin or role == BusinessMembership.OWNER,
                'invited_by': invited_by,
                'is_active': True,
            }
        )
        return membership


class EmailVerificationToken(models.Model):
    """Verification token for user email confirmation."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='verification_tokens')
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'email_verification_tokens'
        indexes = [models.Index(fields=['token'])]

    def __str__(self):
        return f"Verification token for {self.user.email}"

    @staticmethod
    def generate_token() -> str:
        return secrets.token_urlsafe(32)

    @classmethod
    def create_for_user(cls, user, validity_hours: int = 48):
        token_value = cls.generate_unique_token()
        expires_at = timezone.now() + timedelta(hours=validity_hours)
        return cls.objects.create(user=user, token=token_value, expires_at=expires_at)

    @classmethod
    def generate_unique_token(cls) -> str:
        while True:
            candidate = cls.generate_token()
            if not cls.objects.filter(token=candidate).exists():
                return candidate

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    @property
    def is_consumed(self) -> bool:
        return self.consumed_at is not None

    def mark_consumed(self):
        self.consumed_at = timezone.now()
        self.save(update_fields=['consumed_at'])


class PasswordResetToken(models.Model):
    """Token used to reset user passwords securely."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_reset_tokens')
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'password_reset_tokens'
        indexes = [models.Index(fields=['token'])]

    def __str__(self):
        return f"Password reset token for {self.user.email}"

    @staticmethod
    def generate_token() -> str:
        return secrets.token_urlsafe(32)

    @classmethod
    def generate_unique_token(cls) -> str:
        while True:
            candidate = cls.generate_token()
            if not cls.objects.filter(token=candidate).exists():
                return candidate

    @classmethod
    def create_for_user(cls, user, validity_hours: int = 2):
        token_value = cls.generate_unique_token()
        expires_at = timezone.now() + timedelta(hours=validity_hours)
        return cls.objects.create(user=user, token=token_value, expires_at=expires_at)

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at

    @property
    def is_consumed(self) -> bool:
        return self.consumed_at is not None

    def mark_consumed(self):
        self.consumed_at = timezone.now()
        self.save(update_fields=['consumed_at'])


class Business(models.Model):
    """Represents a business registered on the platform."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey('User', on_delete=models.CASCADE, related_name='owned_businesses')
    name = models.CharField(max_length=255, unique=True)
    tin = models.CharField(max_length=100, unique=True)
    website = models.URLField(blank=True, null=True)
    email = models.EmailField()
    social_handles = models.JSONField(default=dict, blank=True)
    address = models.TextField()
    phone_numbers = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'businesses'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new:
            self.owner.add_business_membership(
                business=self,
                role=BusinessMembership.OWNER,
                is_admin=True
            )


class BusinessMembership(models.Model):
    """Associates users with businesses and roles."""
    OWNER = 'OWNER'
    ADMIN = 'ADMIN'
    MANAGER = 'MANAGER'
    STAFF = 'STAFF'
    ROLE_CHOICES = [
        (OWNER, 'Owner'),
        (ADMIN, 'Administrator'),
        (MANAGER, 'Manager'),
        (STAFF, 'Staff'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='business_memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=STAFF)
    is_admin = models.BooleanField(default=False)
    invited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='invited_business_memberships')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'business_memberships'
        unique_together = ['business', 'user']
        ordering = ['business__name', 'user__name']

    def __str__(self):
        return f"{self.user.name} - {self.business.name} ({self.role})"

    def save(self, *args, **kwargs):
        if self.role == self.OWNER:
            self.is_admin = True
        super().save(*args, **kwargs)


class BusinessInvitation(models.Model):
    """Represents a pending invitation for an employee to join a business."""

    STATUS_PENDING = 'PENDING'
    STATUS_ACCEPTED = 'ACCEPTED'
    STATUS_EXPIRED = 'EXPIRED'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_EXPIRED, 'Expired'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey('accounts.Business', on_delete=models.CASCADE, related_name='invitations')
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=BusinessMembership.ROLE_CHOICES, default=BusinessMembership.STAFF)
    invited_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_business_invitations')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    token = models.CharField(max_length=64, unique=True, blank=True, null=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='accepted_business_invitations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'business_invitations'
        indexes = [
            models.Index(fields=['email', 'status']),
            models.Index(fields=['business', 'status']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f"Invitation for {self.email} to {self.business.name} ({self.role})"

    @staticmethod
    def generate_token() -> str:
        return secrets.token_urlsafe(32)

    def initialize_token(self, validity_hours: int = 168):
        """Assign a fresh token + expiry if not already present."""
        if not self.token:
            self.token = self.generate_token()
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=validity_hours)

    @property
    def is_expired(self) -> bool:
        return self.status == self.STATUS_EXPIRED or (self.expires_at and timezone.now() > self.expires_at)

    def mark_accepted(self, accepted_by: 'User'):
        self.status = self.STATUS_ACCEPTED
        self.accepted_at = timezone.now()
        self.accepted_by = accepted_by
        self.save(update_fields=['status', 'accepted_at', 'accepted_by', 'updated_at'])

    def mark_expired(self):
        self.status = self.STATUS_EXPIRED
        self.save(update_fields=['status', 'updated_at'])


class UserProfile(models.Model):
    """Extended user profile information"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    emergency_contact = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_profiles'
    
    def __str__(self):
        return f"{self.user.name}'s Profile"


class AuditLog(models.Model):
    """Audit trail for all critical operations"""
    ACTION_CHOICES = [
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('SALE', 'Sale'),
        ('TRANSFER', 'Transfer'),
        ('PAYMENT', 'Payment'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100)
    object_id = models.UUIDField(null=True, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'audit_logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['model_name', 'object_id']),
            models.Index(fields=['action', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user} - {self.action} - {self.model_name} - {self.timestamp}"
