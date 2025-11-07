"""
AI Features Models
Manages AI credit system, transactions, and purchases for AI-powered features.
"""

import uuid
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from accounts.models import Business, User


class BusinessAICredits(models.Model):
    """Track AI credit balance per business"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        Business, 
        on_delete=models.CASCADE, 
        related_name='ai_credits'
    )
    balance = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Current AI credit balance"
    )
    purchased_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(
        help_text="Credits expire date (typically 6 months from purchase)"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether these credits are still valid"
    )
    
    class Meta:
        db_table = 'business_ai_credits'
        ordering = ['-purchased_at']
        verbose_name = 'Business AI Credits'
        verbose_name_plural = 'Business AI Credits'
        indexes = [
            models.Index(fields=['business', 'is_active']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"{self.business.name} - {self.balance} credits"
    
    def is_expired(self):
        """Check if credits have expired"""
        return timezone.now() > self.expires_at
    
    def save(self, *args, **kwargs):
        """Auto-deactivate if expired"""
        if self.is_expired():
            self.is_active = False
        super().save(*args, **kwargs)


class AITransaction(models.Model):
    """Log every AI request for billing and analytics"""
    
    FEATURE_CHOICES = [
        # Smart Collections
        ('credit_assessment', 'Credit Risk Assessment'),
        ('collection_priority', 'Collection Priority Analysis'),
        ('collection_message', 'Collection Message Generator'),
        ('portfolio_dashboard', 'Portfolio Health Dashboard'),
        ('payment_prediction', 'Payment Prediction'),
        
        # Customer Insights
        ('customer_insight', 'Customer Insight Query'),
        ('natural_language_query', 'Natural Language Query'),
        
        # Product Features
        ('product_description', 'Product Description Generator'),
        
        # Reports
        ('report_narrative', 'Report AI Narrative'),
        
        # Inventory
        ('inventory_forecast', 'Inventory Forecasting'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        Business, 
        on_delete=models.CASCADE, 
        related_name='ai_transactions'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ai_transactions',
        help_text="User who initiated the AI request"
    )
    feature = models.CharField(
        max_length=50, 
        choices=FEATURE_CHOICES,
        help_text="AI feature that was used"
    )
    credits_used = models.DecimalField(
        max_digits=6, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    cost_to_us = models.DecimalField(
        max_digits=6, 
        decimal_places=4,
        help_text="Actual OpenAI API cost in GHS"
    )
    tokens_used = models.IntegerField(
        default=0,
        help_text="Total tokens used (input + output)"
    )
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    request_data = models.JSONField(
        default=dict,
        help_text="Store request parameters (for debugging)"
    )
    response_summary = models.TextField(
        blank=True,
        help_text="Brief summary of AI response"
    )
    processing_time_ms = models.IntegerField(
        default=0,
        help_text="Time taken to process request in milliseconds"
    )
    
    class Meta:
        db_table = 'ai_transactions'
        ordering = ['-timestamp']
        verbose_name = 'AI Transaction'
        verbose_name_plural = 'AI Transactions'
        indexes = [
            models.Index(fields=['business', 'feature', '-timestamp']),
            models.Index(fields=['business', 'success']),
            models.Index(fields=['-timestamp']),
        ]
    
    def __str__(self):
        status = "✓" if self.success else "✗"
        return f"{status} {self.business.name} - {self.get_feature_display()} - {self.credits_used} credits"


class AICreditPurchase(models.Model):
    """Track credit purchases"""
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('mobile_money', 'Mobile Money'),
        ('card', 'Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('free_trial', 'Free Trial'),
        ('admin_grant', 'Admin Grant'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        Business, 
        on_delete=models.CASCADE, 
        related_name='ai_purchases'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="User who made the purchase"
    )
    amount_paid = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    credits_purchased = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    bonus_credits = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Bonus credits for bulk purchases"
    )
    payment_reference = models.CharField(
        max_length=255,
        unique=True,
        help_text="Payment gateway reference"
    )
    payment_method = models.CharField(
        max_length=50, 
        choices=PAYMENT_METHOD_CHOICES
    )
    payment_status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending'
    )
    gateway_response = models.JSONField(
        default=dict,
        blank=True,
        help_text="Payment gateway response data including tax breakdown"
    )
    purchased_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'ai_credit_purchases'
        ordering = ['-purchased_at']
        verbose_name = 'AI Credit Purchase'
        verbose_name_plural = 'AI Credit Purchases'
        indexes = [
            models.Index(fields=['business', '-purchased_at']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['payment_reference']),
        ]
    
    def __str__(self):
        return f"{self.business.name} - {self.credits_purchased} credits - {self.payment_status}"
    
    def total_credits(self):
        """Return total credits including bonus"""
        return self.credits_purchased + self.bonus_credits


class AIUsageAlert(models.Model):
    """Track low credit alerts sent to businesses"""
    
    ALERT_TYPE_CHOICES = [
        ('low_balance', 'Low Balance'),
        ('depleted', 'Depleted'),
        ('expired', 'Expired'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='ai_alerts'
    )
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPE_CHOICES)
    current_balance = models.DecimalField(max_digits=10, decimal_places=2)
    threshold = models.DecimalField(max_digits=10, decimal_places=2)
    sent_at = models.DateTimeField(auto_now_add=True)
    acknowledged = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'ai_usage_alerts'
        ordering = ['-sent_at']
        verbose_name = 'AI Usage Alert'
        verbose_name_plural = 'AI Usage Alerts'
    
    def __str__(self):
        return f"{self.business.name} - {self.get_alert_type_display()}"
