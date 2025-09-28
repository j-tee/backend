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
    billing_cycle = models.CharField(max_length=20, choices=BILLING_CYCLE_CHOICES)
    max_users = models.PositiveIntegerField(default=1)
    max_storefronts = models.PositiveIntegerField(default=1)
    max_products = models.PositiveIntegerField(default=100)
    max_transactions_per_month = models.PositiveIntegerField(default=1000)
    features = models.JSONField(default=list, blank=True)  # List of feature names
    is_active = models.BooleanField(default=True)
    is_trial = models.BooleanField(default=False)
    trial_days = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'subscription_plans'
        ordering = ['price']
    
    def __str__(self):
        return f"{self.name} - {self.price}/{self.billing_cycle}"
    
    def get_billing_days(self):
        """Get number of days in billing cycle"""
        if self.billing_cycle == 'MONTHLY':
            return 30
        elif self.billing_cycle == 'QUARTERLY':
            return 90
        elif self.billing_cycle == 'YEARLY':
            return 365
        return 30


class Subscription(models.Model):
    """User subscriptions"""
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
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('CANCELLED', 'Cancelled'),
        ('SUSPENDED', 'Suspended'),
        ('EXPIRED', 'Expired'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name='subscriptions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='INACTIVE')
    start_date = models.DateField()
    end_date = models.DateField()
    auto_renew = models.BooleanField(default=True)
    next_billing_date = models.DateField(null=True, blank=True)
    is_trial = models.BooleanField(default=False)
    trial_end_date = models.DateField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'subscriptions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['status', 'end_date']),
            models.Index(fields=['next_billing_date']),
        ]
    
    def __str__(self):
        return f"{self.user.name} - {self.plan.name} - {self.status}"
    
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
        return f"{self.subscription.user.name} - {self.amount} - {self.status}"


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
        return f"{self.subscription.user.name} - {self.metric_type} - {self.current_usage}/{self.limit_value}"
    
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
        return f"Invoice {self.invoice_number} - {self.subscription.user.name}"
    
    def is_overdue(self):
        """Check if invoice is overdue"""
        return (self.status in ['SENT', 'OVERDUE'] and 
                self.due_date < timezone.now().date())
    
    def days_overdue(self):
        """Get number of days overdue"""
        if not self.is_overdue():
            return 0
        return (timezone.now().date() - self.due_date).days
