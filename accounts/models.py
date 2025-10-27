import secrets
import uuid
from datetime import timedelta

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from guardian.mixins import GuardianUserMixin


class Permission(models.Model):
    """
    Fine-grained permissions that can be assigned to roles.
    Similar to Rails CanCanCan abilities.
    """
    PERMISSION_CATEGORIES = [
        ('SALES', 'Sales & POS'),
        ('INVENTORY', 'Inventory Management'),
        ('CUSTOMERS', 'Customer Management'),
        ('REPORTS', 'Reports & Analytics'),
        ('USERS', 'User Management'),
        ('SETTINGS', 'Settings & Configuration'),
        ('PLATFORM', 'Platform Administration'),
        ('FINANCE', 'Financial Operations'),
    ]
    
    ACTION_TYPES = [
        ('CREATE', 'Create'),
        ('READ', 'Read/View'),
        ('UPDATE', 'Update/Edit'),
        ('DELETE', 'Delete'),
        ('APPROVE', 'Approve'),
        ('EXPORT', 'Export'),
        ('IMPORT', 'Import'),
        ('MANAGE', 'Full Management'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    codename = models.CharField(max_length=100, unique=True, 
                                help_text="Machine-readable permission code (e.g., 'can_approve_sales')")
    description = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=20, choices=PERMISSION_CATEGORIES)
    action = models.CharField(max_length=20, choices=ACTION_TYPES)
    resource = models.CharField(max_length=50, 
                               help_text="Resource this permission applies to (e.g., 'sale', 'product')")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'permissions'
        ordering = ['category', 'resource', 'action']
        indexes = [
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['codename']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.codename})"


class RoleManager(models.Manager):
    def get_owner_role(self):
        return self.get(name='OWNER')
    
    def get_admin_role(self):
        return self.get(name='Admin')
    
    def get_cashier_role(self):
        return self.get(name='Cashier')
    
    def get_manager_role(self):
        return self.get(name='Manager')
    
    def get_warehouse_staff_role(self):
        return self.get(name='Warehouse Staff')
    
    def get_super_user_role(self):
        return self.get(name='SUPER_USER')


class Role(models.Model):
    """
    User roles with many-to-many relationship to permissions.
    Supports multiple roles per user for flexible access control.
    """
    ROLE_LEVELS = [
        ('PLATFORM', 'Platform Level'),  # Platform-wide roles (SUPER_USER, SAAS_ADMIN)
        ('BUSINESS', 'Business Level'),  # Business-specific roles (Admin, Manager)
        ('STOREFRONT', 'Storefront Level'),  # Storefront-specific roles (Cashier)
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
    level = models.CharField(max_length=20, choices=ROLE_LEVELS, default='BUSINESS')
    permissions = models.ManyToManyField(Permission, related_name='roles', blank=True)
    is_system_role = models.BooleanField(default=False, 
                                        help_text="System roles cannot be deleted")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    objects = RoleManager()
    
    class Meta:
        db_table = 'roles'
        ordering = ['level', 'name']
        indexes = [
            models.Index(fields=['level', 'is_active']),
        ]
    
    def __str__(self):
        return self.name
    
    def add_permission(self, permission_codename):
        """Add a permission to this role by codename"""
        try:
            permission = Permission.objects.get(codename=permission_codename)
            self.permissions.add(permission)
            return True
        except Permission.DoesNotExist:
            return False
    
    def remove_permission(self, permission_codename):
        """Remove a permission from this role by codename"""
        try:
            permission = Permission.objects.get(codename=permission_codename)
            self.permissions.remove(permission)
            return True
        except Permission.DoesNotExist:
            return False
    
    def has_permission(self, permission_codename):
        """Check if role has a specific permission"""
        return self.permissions.filter(codename=permission_codename, is_active=True).exists()
    
    def get_permissions_by_category(self, category):
        """Get all permissions for a specific category"""
        return self.permissions.filter(category=category, is_active=True)


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


class User(AbstractBaseUser, PermissionsMixin, GuardianUserMixin):
    """Custom user model with UUID primary key and RBAC support"""
    ACCOUNT_OWNER = 'OWNER'
    ACCOUNT_EMPLOYEE = 'EMPLOYEE'
    ACCOUNT_TYPE_CHOICES = [
        (ACCOUNT_OWNER, 'Business Owner'),
        (ACCOUNT_EMPLOYEE, 'Employee'),
    ]
    PLATFORM_SUPER_ADMIN = 'SUPER_ADMIN'
    PLATFORM_SAAS_ADMIN = 'SAAS_ADMIN'
    PLATFORM_SAAS_STAFF = 'SAAS_STAFF'
    PLATFORM_NONE = 'NONE'
    PLATFORM_ROLE_CHOICES = [
        (PLATFORM_NONE, 'None'),
        (PLATFORM_SUPER_ADMIN, 'Super Admin'),
        (PLATFORM_SAAS_ADMIN, 'SaaS Admin'),
        (PLATFORM_SAAS_STAFF, 'SaaS Staff'),
    ]
    # REMOVED: SUBSCRIPTION_STATUS_CHOICES - Subscription status now belongs to Business
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    role = models.ForeignKey(Role, on_delete=models.PROTECT, null=True, blank=True, 
                             help_text="DEPRECATED: Use roles (many-to-many) instead")
    roles = models.ManyToManyField(Role, through='UserRole', through_fields=('user', 'role'),
                                   related_name='users', blank=True,
                                   help_text="User roles with scope (Platform/Business/Storefront)")
    picture_url = models.URLField(blank=True, null=True)
    
    # User profile picture
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)
    
    # User preference fields
    LANGUAGE_CHOICES = [
        ('en', 'English'),
        ('fr', 'French'),
        ('es', 'Spanish'),
    ]
    DATE_FORMAT_CHOICES = [
        ('DD/MM/YYYY', 'DD/MM/YYYY'),
        ('MM/DD/YYYY', 'MM/DD/YYYY'),
        ('YYYY-MM-DD', 'YYYY-MM-DD'),
    ]
    TIME_FORMAT_CHOICES = [
        ('12h', '12 Hour'),
        ('24h', '24 Hour'),
    ]
    
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, default='en')
    timezone = models.CharField(max_length=50, default='Africa/Accra')
    date_format = models.CharField(max_length=20, choices=DATE_FORMAT_CHOICES, default='DD/MM/YYYY')
    time_format = models.CharField(max_length=10, choices=TIME_FORMAT_CHOICES, default='24h')
    currency = models.CharField(max_length=3, default='GHS')
    
    # JSON fields for flexible preferences and notifications
    preferences = models.JSONField(default=dict, blank=True)
    notification_settings = models.JSONField(default=dict, blank=True)
    
    # Two-factor authentication fields
    two_factor_enabled = models.BooleanField(default=False)
    two_factor_secret = models.CharField(max_length=32, null=True, blank=True)
    backup_codes = models.JSONField(default=list, blank=True)
    
    # REMOVED: subscription_status - Moved to Business model
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES, default=ACCOUNT_OWNER)
    platform_role = models.CharField(max_length=20, choices=PLATFORM_ROLE_CHOICES, default=PLATFORM_NONE)
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
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.email})"
    
    def get_accessible_storefronts(self):
        """Return QuerySet of storefronts user can access based on role and assignments."""
        from inventory.models import StoreFront, StoreFrontEmployee, BusinessStoreFront
        
        # Super admins can access all storefronts
        if self.is_superuser or self.platform_role == self.PLATFORM_SUPER_ADMIN:
            return StoreFront.objects.all()
        
        # Get user's active business membership
        membership = self.business_memberships.filter(is_active=True).first()
        if not membership:
            return StoreFront.objects.none()
        
        business = membership.business
        
        # Business owners and admins can access all business storefronts
        if membership.role in [BusinessMembership.OWNER, BusinessMembership.ADMIN]:
            # Get all storefronts for this business
            business_storefronts = BusinessStoreFront.objects.filter(
                business=business,
                is_active=True
            ).values_list('storefront', flat=True)
            return StoreFront.objects.filter(id__in=business_storefronts)
        
        # Managers and staff see their assigned storefronts
        assigned_storefronts = StoreFrontEmployee.objects.filter(
            user=self,
            business=business,
            is_active=True
        ).values_list('storefront', flat=True)
        
        return StoreFront.objects.filter(id__in=assigned_storefronts)
    
    def can_access_storefront(self, storefront_id):
        """Check if user can access a specific storefront."""
        return self.get_accessible_storefronts().filter(id=storefront_id).exists()
    
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
        """Return the most recently updated active business membership's business, if any."""
        membership = (
            self.active_business_memberships()
            .order_by('-updated_at', '-created_at')
            .first()
        )
        return membership.business if membership else None

    def has_platform_role(self, *roles):
        if not self.platform_role:
            return False
        return self.platform_role in roles

    @property
    def is_platform_super_admin(self):
        return self.has_platform_role(self.PLATFORM_SUPER_ADMIN) or self.is_superuser

    @property
    def is_platform_admin(self):
        return self.has_platform_role(self.PLATFORM_SUPER_ADMIN, self.PLATFORM_SAAS_ADMIN)

    @property
    def is_platform_staff(self):
        return self.has_platform_role(
            self.PLATFORM_SUPER_ADMIN,
            self.PLATFORM_SAAS_ADMIN,
            self.PLATFORM_SAAS_STAFF,
        )

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
    
    def has_active_subscription(self):
        """
        Check if user has access to any business with active subscription.
        Returns True if user is member of at least one business with active subscription.
        """
        from django.conf import settings
        
        # Bypass check if setting is enabled (typically in DEBUG mode)
        if getattr(settings, 'BYPASS_SUBSCRIPTION_CHECK', False):
            return True
        
        # Platform admins always have access
        if self.is_platform_admin:
            return True
        
        # Check if user has membership in any business with active subscription
        try:
            return self.business_memberships.filter(
                is_active=True,
                business__subscription__status__in=['ACTIVE', 'TRIAL']
            ).exists()
        except:
            # If subscriptions app isn't available or error occurs, allow access
            return True
    
    def get_businesses_with_active_subscriptions(self):
        """Get all businesses user has access to with active subscriptions"""
        memberships = self.business_memberships.filter(
            is_active=True,
            business__subscription__status__in=['ACTIVE', 'TRIAL']
        )
        return [m.business for m in memberships]
    
    # ============================================================================
    # RBAC Methods (Many-to-Many Roles Support)
    # ============================================================================
    
    def get_roles(self, business=None, storefront=None, active_only=True):
        """
        Get all roles assigned to user, optionally filtered by scope.
        
        Args:
            business: Filter by business (None for all)
            storefront: Filter by storefront (None for all)
            active_only: Only return active, non-expired roles
        """
        qs = self.user_roles.select_related('role')
        
        if active_only:
            qs = qs.filter(is_active=True)
            # Filter out expired roles
            now = timezone.now()
            qs = qs.filter(models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now))
        
        if business:
            qs = qs.filter(models.Q(business=business) | models.Q(scope='PLATFORM'))
        
        if storefront:
            qs = qs.filter(models.Q(storefront=storefront) | models.Q(scope='PLATFORM'))
        
        return qs
    
    def has_role_new(self, role_name, business=None, storefront=None):
        """Check if user has a specific role (new many-to-many version)"""
        return self.get_roles(business, storefront).filter(role__name=role_name).exists()
    
    def has_any_role(self, role_names, business=None, storefront=None):
        """Check if user has any of the specified roles"""
        return self.get_roles(business, storefront).filter(role__name__in=role_names).exists()
    
    def has_permission(self, permission_codename, business=None, storefront=None):
        """
        Check if user has a specific permission through any of their roles.
        
        Args:
            permission_codename: The permission codename (e.g., 'can_approve_sales')
            business: Optional business scope
            storefront: Optional storefront scope
        """
        # Platform super admins have all permissions
        if self.platform_role == 'SUPER_ADMIN' or self.is_superuser:
            return True
        
        # Check through assigned roles
        roles = self.get_roles(business, storefront)
        for user_role in roles:
            if user_role.role.has_permission(permission_codename):
                return True
        
        return False
    
    def has_any_permission(self, permission_codenames, business=None, storefront=None):
        """Check if user has any of the specified permissions"""
        for codename in permission_codenames:
            if self.has_permission(codename, business, storefront):
                return True
        return False
    
    def has_all_permissions(self, permission_codenames, business=None, storefront=None):
        """Check if user has all of the specified permissions"""
        for codename in permission_codenames:
            if not self.has_permission(codename, business, storefront):
                return False
        return True
    
    def assign_role(self, role, scope='BUSINESS', business=None, storefront=None, 
                   assigned_by=None, expires_at=None):
        """
        Assign a role to user.
        
        Args:
            role: Role instance or role name (str)
            scope: 'PLATFORM', 'BUSINESS', or 'STOREFRONT'
            business: Business instance (required for BUSINESS scope)
            storefront: StoreFront instance (required for STOREFRONT scope)
            assigned_by: User who assigned the role
            expires_at: Optional expiry datetime
        """
        if isinstance(role, str):
            role = Role.objects.get(name=role)
        
        # Validate scope
        if scope == 'BUSINESS' and not business:
            raise ValueError("Business is required for BUSINESS scope")
        if scope == 'STOREFRONT' and not storefront:
            raise ValueError("Storefront is required for STOREFRONT scope")
        
        # Import UserRole here to avoid circular import
        from accounts.models import UserRole
        
        # Create or update user role assignment
        user_role, created = UserRole.objects.update_or_create(
            user=self,
            role=role,
            business=business,
            storefront=storefront,
            defaults={
                'scope': scope,
                'assigned_by': assigned_by,
                'expires_at': expires_at,
                'is_active': True,
            }
        )
        
        return user_role
    
    def remove_role(self, role, business=None, storefront=None):
        """Remove a role from user"""
        if isinstance(role, str):
            role = Role.objects.get(name=role)
        
        # Import UserRole here to avoid circular import
        from accounts.models import UserRole
        
        UserRole.objects.filter(
            user=self,
            role=role,
            business=business,
            storefront=storefront
        ).delete()
    
    def get_all_permissions(self, business=None, storefront=None):
        """Get all permissions user has through their roles"""
        roles = self.get_roles(business, storefront)
        permission_ids = set()
        
        for user_role in roles:
            permission_ids.update(
                user_role.role.permissions.filter(is_active=True).values_list('id', flat=True)
            )
        
        return Permission.objects.filter(id__in=permission_ids)


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
    SUBSCRIPTION_STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('TRIAL', 'Trial'),
        ('EXPIRED', 'Expired'),
        ('SUSPENDED', 'Suspended'),
    ]
    
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
    subscription_status = models.CharField(
        max_length=20,
        choices=SUBSCRIPTION_STATUS_CHOICES,
        default='INACTIVE',
        help_text='Current subscription status of this business'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'businesses'
        ordering = ['name']

    def __str__(self):
        return self.name
    
    def has_active_subscription(self):
        """Check if business has active subscription"""
        from django.conf import settings
        
        # Bypass for development
        if getattr(settings, 'BYPASS_SUBSCRIPTION_CHECK', False):
            return True
        
        try:
            return self.subscription.is_active()
        except AttributeError:  # No subscription attribute
            return False
    
    def get_subscription_limits(self):
        """Get subscription plan limits for this business"""
        try:
            return {
                'max_users': self.subscription.plan.max_users,
                'max_storefronts': self.subscription.plan.max_storefronts,
                'max_products': self.subscription.plan.max_products,
                'max_transactions': self.subscription.plan.max_transactions_per_month,
                'features': self.subscription.plan.features,
            }
        except AttributeError:  # No subscription
            return None
    
    def sync_subscription_status(self):
        """Sync subscription_status field with actual subscription status"""
        try:
            self.subscription_status = self.subscription.status
            self.save(update_fields=['subscription_status'])
        except AttributeError:  # No subscription
            if self.subscription_status != 'INACTIVE':
                self.subscription_status = 'INACTIVE'
                self.save(update_fields=['subscription_status'])

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        if is_new:
            self.owner.add_business_membership(
                business=self,
                role=BusinessMembership.OWNER,
                is_admin=True
            )


class UserRole(models.Model):
    """
    Junction table for User-Role many-to-many relationship.
    Allows users to have multiple roles with scope (business/storefront).
    """
    SCOPE_TYPES = [
        ('PLATFORM', 'Platform-wide'),
        ('BUSINESS', 'Business-specific'),
        ('STOREFRONT', 'Storefront-specific'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_roles')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='user_assignments')
    scope = models.CharField(max_length=20, choices=SCOPE_TYPES, default='BUSINESS')
    
    # Optional: scope to specific business or storefront
    business = models.ForeignKey('Business', on_delete=models.CASCADE, null=True, blank=True,
                                 help_text="If set, role applies only to this business")
    storefront = models.ForeignKey('inventory.StoreFront', on_delete=models.CASCADE, 
                                   null=True, blank=True,
                                   help_text="If set, role applies only to this storefront")
    
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='assigned_roles')
    is_active = models.BooleanField(default=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True,
                                     help_text="Optional expiry for temporary role assignments")
    
    class Meta:
        db_table = 'user_roles'
        unique_together = ['user', 'role', 'business', 'storefront']
        ordering = ['-assigned_at']
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['role', 'is_active']),
            models.Index(fields=['business', 'is_active']),
        ]
    
    def __str__(self):
        scope_str = ""
        if self.business:
            scope_str = f" @ {self.business.name}"
        elif self.storefront:
            scope_str = f" @ {self.storefront.name}"
        return f"{self.user.email} - {self.role.name}{scope_str}"
    
    @property
    def is_expired(self):
        """Check if role assignment has expired"""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at


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
    rbac_role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='business_memberships',
        help_text='RBAC role for permission management'
    )
    is_admin = models.BooleanField(default=False)
    invited_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='invited_business_memberships')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'business_memberships'
        unique_together = ['business', 'user']
        ordering = ['business__name', 'user__name']
        constraints = [
            models.UniqueConstraint(
                fields=['user'],
                name='one_user_one_business',
                violation_error_message='A user can only belong to one business. This email is already registered with another business.'
            )
        ]

    def __str__(self):
        return f"{self.user.name} - {self.business.name} ({self.role})"

    def clean(self):
        """Validate that user doesn't already belong to another business."""
        from django.core.exceptions import ValidationError
        
        # Check if this user already has a membership in a different business
        if self.user_id and self.business_id:
            existing = BusinessMembership.objects.filter(
                user=self.user
            ).exclude(
                id=self.id
            ).exclude(
                business=self.business
            )
            if existing.exists():
                existing_business = existing.first().business.name
                raise ValidationError(
                    f"This user is already registered with {existing_business}. "
                    f"A user can only belong to one business."
                )

    def save(self, *args, **kwargs):
        # Validate before saving
        self.clean()
        
        if self.role == self.OWNER:
            self.is_admin = True
        
        # Auto-assign RBAC role based on membership role if not set
        if not self.rbac_role_id:
            try:
                role_mapping = {
                    self.OWNER: 'OWNER',
                    self.ADMIN: 'Admin',
                    self.MANAGER: 'Manager',
                    self.STAFF: 'Cashier',
                }
                role_name = role_mapping.get(self.role)
                if role_name:
                    self.rbac_role = Role.objects.get(name=role_name)
            except Role.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)


class BusinessInvitation(models.Model):
    """Represents a pending invitation for an employee to join a business."""

    STATUS_PENDING = 'PENDING'
    STATUS_ACCEPTED = 'ACCEPTED'
    STATUS_EXPIRED = 'EXPIRED'
    STATUS_REVOKED = 'REVOKED'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_EXPIRED, 'Expired'),
        (STATUS_REVOKED, 'Revoked'),
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
    payload = models.JSONField(default=dict, blank=True)
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
        return self.status in {self.STATUS_EXPIRED, self.STATUS_REVOKED} or (self.expires_at and timezone.now() > self.expires_at)

    def mark_accepted(self, accepted_by: 'User'):
        self.status = self.STATUS_ACCEPTED
        self.accepted_at = timezone.now()
        self.accepted_by = accepted_by
        self.save(update_fields=['status', 'accepted_at', 'accepted_by', 'updated_at'])

    def mark_expired(self):
        self.status = self.STATUS_EXPIRED
        self.save(update_fields=['status', 'updated_at'])

    def mark_revoked(self):
        self.status = self.STATUS_REVOKED
        self.save(update_fields=['status', 'updated_at'])

    def get_storefront_ids(self):
        return self.payload.get('storefront_ids', [])

    def set_storefront_ids(self, storefront_ids):
        payload = dict(self.payload or {})
        payload['storefront_ids'] = list(storefront_ids)
        self.payload = payload
        self.save(update_fields=['payload', 'updated_at'])


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


class RoleTemplate(models.Model):
    """
    Pre-defined role templates for quick role creation.
    Similar to Rails seed data for roles.
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    level = models.CharField(max_length=20, choices=Role.ROLE_LEVELS)
    permission_codenames = models.JSONField(default=list, 
                                           help_text="List of permission codenames to assign")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'role_templates'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.level})"
    
    def create_role(self):
        """Create a Role from this template"""
        role, created = Role.objects.get_or_create(
            name=self.name,
            defaults={
                'description': self.description,
                'level': self.level,
                'is_system_role': True,
            }
        )
        
        # Assign permissions
        for codename in self.permission_codenames:
            try:
                permission = Permission.objects.get(codename=codename)
                role.permissions.add(permission)
            except Permission.DoesNotExist:
                continue
        
        return role
