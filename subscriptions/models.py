import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone


User = get_user_model()


class SubscriptionPlan(models.Model):
    """Subscription plans for the SaaS"""
    BILLING_CYCLE_CHOICES = [
        ('MONTHLY', 'Monthly'),
        ('QUARTERLY', 'Quarterly'),
        ('YEARLY', 'Yearly'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    currency = models.CharField(max_length=3, default='GHS')  # Currency code
    billing_cycle = models.CharField(max_length=20, choices=BILLING_CYCLE_CHOICES)
    max_users = models.PositiveIntegerField(null=True, blank=True)  # None = unlimited
    max_storefronts = models.PositiveIntegerField(null=True, blank=True)
    max_products = models.PositiveIntegerField(null=True, blank=True)
    max_transactions_per_month = models.PositiveIntegerField(null=True, blank=True)
    features = models.JSONField(default=list, blank=True)  # List of feature names
    is_active = models.BooleanField(default=True)
    is_popular = models.BooleanField(default=False)  # Mark as popular plan
    sort_order = models.PositiveIntegerField(default=0)  # For custom ordering
    trial_period_days = models.PositiveIntegerField(default=14)  # Trial period in days
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'subscription_plans'
        ordering = ['sort_order', 'price']
    
    def __str__(self):
        return f"{self.name} - {self.currency} {self.price}/{self.billing_cycle}"
    
    def billing_cycle_days(self):
        """Get number of days in billing cycle"""
        if self.billing_cycle == 'MONTHLY':
            return 30
        elif self.billing_cycle == 'QUARTERLY':
            return 90
        elif self.billing_cycle == 'YEARLY':
            return 365
        return 30
        return 30


class Subscription(models.Model):
    """Business subscriptions - Each business has ONE subscription"""
    PAYMENT_METHOD_CHOICES = [
        ('MOMO', 'Mobile Money'),
        ('PAYSTACK', 'Paystack'),
        ('STRIPE', 'Stripe'),
        ('BANK_TRANSFER', 'Bank Transfer'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('PAID', 'Paid'),
        ('PENDING', 'Pending'),
        ('FAILED', 'Failed'),
        ('OVERDUE', 'Overdue'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    STATUS_CHOICES = [
        ('TRIAL', 'Trial'),  # Initial trial period
        ('ACTIVE', 'Active'),  # Paid and active
        ('PAST_DUE', 'Past Due'),  # Payment failed but in grace period
        ('INACTIVE', 'Inactive'),
        ('CANCELLED', 'Cancelled'),
        ('SUSPENDED', 'Suspended'),  # Manually suspended by platform
        ('EXPIRED', 'Expired'),  # Not renewed after grace period
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # PRIMARY: Subscription belongs to a business (ONE-TO-ONE)
    business = models.OneToOneField('accounts.Business', on_delete=models.CASCADE, related_name='subscription')
    # Audit trail: Who created this subscription
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_subscriptions', help_text='User who created this subscription')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name='subscriptions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, blank=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='PENDING')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='TRIAL')
    
    # Billing periods
    start_date = models.DateField()
    end_date = models.DateField()
    current_period_start = models.DateTimeField(default=timezone.now)
    current_period_end = models.DateTimeField(default=timezone.now)
    
    # Renewal settings
    auto_renew = models.BooleanField(default=True)
    cancel_at_period_end = models.BooleanField(default=False)
    next_billing_date = models.DateField(null=True, blank=True)
    
    # Trial settings
    is_trial = models.BooleanField(default=False)
    trial_end_date = models.DateField(null=True, blank=True)
    
    # Grace period (days to pay after expiry)
    grace_period_days = models.PositiveIntegerField(default=3)
    
    # Cancellation
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='cancelled_subscriptions')
    
    # Admin notes
    notes = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'subscriptions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['business', 'status']),
            models.Index(fields=['status', 'end_date']),
            models.Index(fields=['next_billing_date']),
        ]
    
    def __str__(self):
        return f"{self.business.name} - {self.plan.name} - {self.status}"
    
    def is_active(self):
        """Check if subscription is active"""
        return self.status in ['TRIAL', 'ACTIVE']
    
    def is_expired(self):
        """Check if subscription is expired"""
        return self.end_date < timezone.now().date()
    
    def days_until_expiry(self):
        """Get number of days until subscription expires"""
        if self.is_expired():
            return 0
        return (self.end_date - timezone.now().date()).days
    
    def is_in_trial(self):
        """Check if subscription is in trial period"""
        return self.is_trial and self.trial_end_date and self.trial_end_date >= timezone.now().date()
    
    def can_renew(self):
        """Check if subscription can be renewed"""
        return self.status not in ['CANCELLED', 'SUSPENDED'] and not self.cancel_at_period_end
    
    def check_usage_limits(self):
        """Check all usage limits and return status"""
        from .models import UsageTracking
        limits = {}
        
        # Check users limit
        if self.business:
            current_users = self.business.members.count()
            limits['users'] = {
                'current': current_users,
                'limit': self.plan.max_users,
                'exceeded': current_users > self.plan.max_users if self.plan.max_users else False
            }
            
            # Check storefronts limit
            current_storefronts = self.business.storefronts.count()
            limits['storefronts'] = {
                'current': current_storefronts,
                'limit': self.plan.max_storefronts,
                'exceeded': current_storefronts > self.plan.max_storefronts if self.plan.max_storefronts else False
            }
            
            # Check products limit
            current_products = self.business.products.count()
            limits['products'] = {
                'current': current_products,
                'limit': self.plan.max_products,
                'exceeded': current_products > self.plan.max_products if self.plan.max_products else False
            }
        
        return limits
    
    def activate(self):
        """Activate subscription"""
        self.status = 'ACTIVE'
        self.payment_status = 'PAID'
        self.save()
    
    def suspend(self, reason=''):
        """Suspend subscription"""
        self.status = 'SUSPENDED'
        if reason:
            self.notes = f"{self.notes}\nSuspended: {reason}" if self.notes else f"Suspended: {reason}"
        self.save()
    
    def cancel(self, user=None, immediately=False):
        """Cancel subscription"""
        self.cancelled_at = timezone.now()
        if user:
            self.cancelled_by = user
        
        if immediately:
            self.status = 'CANCELLED'
            self.auto_renew = False
        else:
            # Cancel at period end
            self.cancel_at_period_end = True
        
        self.save()
    
    def renew(self, payment_method=None):
        """Renew subscription for next period"""
        from datetime import timedelta
        from dateutil.relativedelta import relativedelta
        
        # Update billing period
        self.start_date = self.end_date
        self.current_period_start = timezone.now()
        
        # Calculate new end date based on billing cycle
        if self.plan.billing_cycle == 'MONTHLY':
            self.end_date = self.start_date + relativedelta(months=1)
            self.current_period_end = self.current_period_start + relativedelta(months=1)
        elif self.plan.billing_cycle == 'QUARTERLY':
            self.end_date = self.start_date + relativedelta(months=3)
            self.current_period_end = self.current_period_start + relativedelta(months=3)
        elif self.plan.billing_cycle == 'YEARLY':
            self.end_date = self.start_date + relativedelta(years=1)
            self.current_period_end = self.current_period_start + relativedelta(years=1)
        
        self.next_billing_date = self.end_date
        self.is_trial = False
        self.payment_status = 'PENDING'
        
        if payment_method:
            self.payment_method = payment_method
        
        self.save()
    
    def is_active(self):
        """Check if subscription is currently active"""
        return (self.status == 'ACTIVE' and 
                self.end_date >= timezone.now().date())
    
    def is_expired(self):
        """Check if subscription has expired"""
        return self.end_date < timezone.now().date()
    
    def days_until_expiry(self):
        """Get days until subscription expires"""
        if self.is_expired():
            return 0
        return (self.end_date - timezone.now().date()).days
    
    def extend_subscription(self, days=None):
        """Extend subscription by billing cycle or specified days"""
        if days is None:
            days = self.plan.get_billing_days()
        
        self.end_date += timedelta(days=days)
        if self.auto_renew:
            self.next_billing_date = self.end_date
        self.save()


class SubscriptionPayment(models.Model):
    """Payments for subscriptions"""
    PAYMENT_METHOD_CHOICES = [
        ('MOMO', 'Mobile Money'),
        ('PAYSTACK', 'Paystack'),
        ('STRIPE', 'Stripe'),
        ('BANK_TRANSFER', 'Bank Transfer'),
    ]
    
    STATUS_CHOICES = [
        ('SUCCESSFUL', 'Successful'),
        ('PENDING', 'Pending'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
        ('REFUNDED', 'Refunded'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    transaction_id = models.CharField(max_length=255, blank=True, null=True)
    gateway_reference = models.CharField(max_length=255, blank=True, null=True)
    gateway_response = models.JSONField(default=dict, blank=True)
    payment_date = models.DateTimeField(null=True, blank=True)
    billing_period_start = models.DateField()
    billing_period_end = models.DateField()
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'subscription_payments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['subscription', 'status']),
            models.Index(fields=['transaction_id']),
            models.Index(fields=['payment_date']),
        ]
    
    def __str__(self):
        return f"{self.subscription.business.name} - {self.amount} - {self.status}"


class PaymentGatewayConfig(models.Model):
    """Payment gateway configurations"""
    GATEWAY_CHOICES = [
        ('PAYSTACK', 'Paystack'),
        ('STRIPE', 'Stripe'),
        ('MOMO', 'Mobile Money'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gateway = models.CharField(max_length=20, choices=GATEWAY_CHOICES, unique=True)
    is_active = models.BooleanField(default=False)
    public_key = models.CharField(max_length=255, blank=True, null=True)
    secret_key = models.CharField(max_length=255, blank=True, null=True)
    webhook_secret = models.CharField(max_length=255, blank=True, null=True)
    api_url = models.URLField(blank=True, null=True)
    test_mode = models.BooleanField(default=True)
    supported_currencies = models.JSONField(default=list, blank=True)
    config = models.JSONField(default=dict, blank=True)  # Additional gateway-specific config
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'payment_gateway_configs'
        ordering = ['gateway']
    
    def __str__(self):
        return f"{self.gateway} - {'Active' if self.is_active else 'Inactive'}"


class WebhookEvent(models.Model):
    """Webhook events from payment gateways"""
    EVENT_TYPE_CHOICES = [
        ('PAYMENT_SUCCESS', 'Payment Success'),
        ('PAYMENT_FAILED', 'Payment Failed'),
        ('SUBSCRIPTION_CREATED', 'Subscription Created'),
        ('SUBSCRIPTION_CANCELLED', 'Subscription Cancelled'),
        ('REFUND_PROCESSED', 'Refund Processed'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSED', 'Processed'),
        ('FAILED', 'Failed'),
        ('IGNORED', 'Ignored'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gateway = models.CharField(max_length=20)
    event_type = models.CharField(max_length=50, choices=EVENT_TYPE_CHOICES)
    event_id = models.CharField(max_length=255)  # Gateway's event ID
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    payload = models.JSONField(default=dict)
    processed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)
    retry_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'webhook_events'
        ordering = ['-created_at']
        unique_together = ['gateway', 'event_id']
        indexes = [
            models.Index(fields=['gateway', 'event_type']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.gateway} - {self.event_type} - {self.status}"


class UsageTracking(models.Model):
    """Track usage metrics for billing and limits"""
    METRIC_TYPE_CHOICES = [
        ('USERS', 'Users'),
        ('STOREFRONTS', 'Storefronts'),
        ('PRODUCTS', 'Products'),
        ('TRANSACTIONS', 'Transactions'),
        ('STORAGE', 'Storage'),
        ('API_CALLS', 'API Calls'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='usage_tracking')
    metric_type = models.CharField(max_length=20, choices=METRIC_TYPE_CHOICES)
    current_usage = models.PositiveIntegerField(default=0)
    limit_value = models.PositiveIntegerField()
    period_start = models.DateField()
    period_end = models.DateField()
    is_exceeded = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'usage_tracking'
        unique_together = ['subscription', 'metric_type', 'period_start', 'period_end']
        indexes = [
            models.Index(fields=['subscription', 'metric_type']),
            models.Index(fields=['is_exceeded', 'period_end']),
        ]
    
    def __str__(self):
        return f"{self.subscription.business.name} - {self.metric_type} - {self.current_usage}/{self.limit_value}"
    
    def check_limit(self):
        """Check if usage exceeds limit"""
        self.is_exceeded = self.current_usage >= self.limit_value
        return self.is_exceeded
    
    def usage_percentage(self):
        """Get usage as percentage of limit"""
        if self.limit_value == 0:
            return 0
        return min(100, (self.current_usage / self.limit_value) * 100)


class Invoice(models.Model):
    """Invoices for subscription payments"""
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('SENT', 'Sent'),
        ('PAID', 'Paid'),
        ('OVERDUE', 'Overdue'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='invoices')
    invoice_number = models.CharField(max_length=50, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    issue_date = models.DateField()
    due_date = models.DateField()
    paid_date = models.DateField(null=True, blank=True)
    billing_period_start = models.DateField()
    billing_period_end = models.DateField()
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'invoices'
        ordering = ['-issue_date']
        indexes = [
            models.Index(fields=['subscription', 'status']),
            models.Index(fields=['invoice_number']),
            models.Index(fields=['due_date', 'status']),
        ]
    
    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.subscription.business.name}"
    
    def is_overdue(self):
        """Check if invoice is overdue"""
        return (self.status in ['SENT', 'OVERDUE'] and 
                self.due_date < timezone.now().date())
    
    def days_overdue(self):
        """Get number of days overdue"""
        if not self.is_overdue():
            return 0
        return (timezone.now().date() - self.due_date).days
    
    def mark_as_paid(self):
        """Mark invoice as paid"""
        self.status = 'PAID'
        self.paid_date = timezone.now().date()
        self.save()


class Alert(models.Model):
    """Subscription alerts and notifications"""
    ALERT_TYPE_CHOICES = [
        ('PAYMENT_DUE', 'Payment Due'),
        ('PAYMENT_FAILED', 'Payment Failed'),
        ('TRIAL_ENDING', 'Trial Ending'),
        ('SUBSCRIPTION_EXPIRING', 'Subscription Expiring'),
        ('SUBSCRIPTION_EXPIRED', 'Subscription Expired'),
        ('USAGE_LIMIT_WARNING', 'Usage Limit Warning'),
        ('USAGE_LIMIT_REACHED', 'Usage Limit Reached'),
        ('SUBSCRIPTION_CANCELLED', 'Subscription Cancelled'),
        ('PAYMENT_SUCCESS', 'Payment Success'),
        ('SUBSCRIPTION_SUSPENDED', 'Subscription Suspended'),
        ('SUBSCRIPTION_ACTIVATED', 'Subscription Activated'),
    ]
    
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='alerts')
    alert_type = models.CharField(max_length=30, choices=ALERT_TYPE_CHOICES)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='MEDIUM')
    title = models.CharField(max_length=200)
    message = models.TextField()
    
    # Notification channels
    email_sent = models.BooleanField(default=False)
    sms_sent = models.BooleanField(default=False)
    in_app_shown = models.BooleanField(default=False)
    
    # Action tracking
    is_read = models.BooleanField(default=False)
    is_dismissed = models.BooleanField(default=False)
    action_taken = models.BooleanField(default=False)
    action_taken_at = models.DateTimeField(null=True, blank=True)
    
    # Additional data
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    dismissed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'subscription_alerts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['subscription', 'alert_type']),
            models.Index(fields=['is_read', 'priority']),
            models.Index(fields=['created_at']),
        ]
        
    def __str__(self):
        business_name = self.subscription.business.name if self.subscription.business else "Unknown Business"
        return f"{self.alert_type} - {business_name}"
    
    def mark_as_read(self):
        """Mark alert as read"""
        self.is_read = True
        self.read_at = timezone.now()
        self.save()
    
    def dismiss(self):
        """Dismiss the alert"""
        self.is_dismissed = True
        self.dismissed_at = timezone.now()
        self.save()
    
    def mark_action_taken(self):
        """Mark that user took action on this alert"""
        self.action_taken = True
        self.action_taken_at = timezone.now()
        self.save()
