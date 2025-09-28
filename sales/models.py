import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from decimal import Decimal
from inventory.models import StoreFront, Product, Batch


User = get_user_model()


class Customer(models.Model):
    """Customer information and credit management"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    credit_limit = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), validators=[MinValueValidator(Decimal('0.00'))])
    outstanding_balance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_customers')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'customers'
        ordering = ['name']
        indexes = [
            models.Index(fields=['phone']),
            models.Index(fields=['email']),
            models.Index(fields=['outstanding_balance']),
        ]
    
    def __str__(self):
        return self.name
    
    @property
    def available_credit(self):
        """Calculate available credit"""
        return self.credit_limit - self.outstanding_balance
    
    def can_purchase(self, amount):
        """Check if customer can make a purchase on credit"""
        return self.available_credit >= amount


class Sale(models.Model):
    """Sales transactions"""
    PAYMENT_TYPE_CHOICES = [
        ('CASH', 'Cash'),
        ('CARD', 'Card'),
        ('MOBILE', 'Mobile Money'),
        ('CREDIT', 'Credit'),
        ('MIXED', 'Mixed Payment'),
    ]
    
    STATUS_CHOICES = [
        ('COMPLETED', 'Completed'),
        ('PENDING', 'Pending'),
        ('REFUNDED', 'Refunded'),
        ('PARTIAL', 'Partial'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    TYPE_CHOICES = [
        ('RETAIL', 'Retail'),
        ('WHOLESALE', 'Wholesale'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    storefront = models.ForeignKey(StoreFront, on_delete=models.CASCADE, related_name='sales')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sales')  # Cashier
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='sales')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='COMPLETED')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='RETAIL')
    amount_due = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    receipt_number = models.CharField(max_length=100, unique=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'sales'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['storefront', 'created_at']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['customer', 'status']),
            models.Index(fields=['receipt_number']),
            models.Index(fields=['type', 'created_at']),
        ]
    
    def __str__(self):
        return f"Sale {self.receipt_number} - {self.total_amount}"
    
    @property
    def subtotal(self):
        """Calculate subtotal before discount and tax"""
        return sum(item.total_price for item in self.sale_items.all())
    
    def calculate_total(self):
        """Calculate final total with discount and tax"""
        subtotal = self.subtotal
        discounted_total = subtotal - self.discount_amount
        final_total = discounted_total + self.tax_amount
        return final_total


class SaleItem(models.Model):
    """Individual items in a sale"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='sale_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='sale_items')
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, null=True, blank=True, related_name='sale_items')
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    
    class Meta:
        db_table = 'sales_items'
        indexes = [
            models.Index(fields=['sale', 'product']),
            models.Index(fields=['product', 'batch']),
        ]
    
    def __str__(self):
        return f"{self.product.name} x {self.quantity} - {self.total_price}"
    
    def save(self, *args, **kwargs):
        """Calculate total price before saving"""
        if not self.total_price:
            self.total_price = (self.unit_price * self.quantity) - self.discount_amount
        super().save(*args, **kwargs)


class Payment(models.Model):
    """Payments made against sales or customer accounts"""
    PAYMENT_METHOD_CHOICES = [
        ('CASH', 'Cash'),
        ('MOMO', 'Mobile Money'),
        ('CARD', 'Card'),
        ('PAYSTACK', 'Paystack'),
        ('STRIPE', 'Stripe'),
        ('BANK_TRANSFER', 'Bank Transfer'),
    ]
    
    STATUS_CHOICES = [
        ('SUCCESSFUL', 'Successful'),
        ('PENDING', 'Pending'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, null=True, blank=True, related_name='payments')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='payments')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    payment_date = models.DateTimeField(auto_now_add=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SUCCESSFUL')
    transaction_id = models.CharField(max_length=255, blank=True, null=True)
    reference_number = models.CharField(max_length=100, blank=True, null=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='processed_payments')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'payments'
        ordering = ['-payment_date']
        indexes = [
            models.Index(fields=['sale', 'status']),
            models.Index(fields=['customer', 'payment_date']),
            models.Index(fields=['payment_method', 'status']),
            models.Index(fields=['transaction_id']),
        ]
    
    def __str__(self):
        return f"Payment {self.amount_paid} - {self.payment_method} - {self.customer.name}"


class Refund(models.Model):
    """Refunds for returned items"""
    REFUND_TYPE_CHOICES = [
        ('FULL', 'Full Refund'),
        ('PARTIAL', 'Partial Refund'),
        ('EXCHANGE', 'Exchange'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('PROCESSED', 'Processed'),
        ('REJECTED', 'Rejected'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='refunds')
    refund_type = models.CharField(max_length=20, choices=REFUND_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    reason = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='requested_refunds')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_refunds')
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_refunds')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'refunds'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['sale', 'status']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"Refund {self.amount} for Sale {self.sale.receipt_number}"


class RefundItem(models.Model):
    """Individual items being refunded"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    refund = models.ForeignKey(Refund, on_delete=models.CASCADE, related_name='refund_items')
    sale_item = models.ForeignKey(SaleItem, on_delete=models.CASCADE, related_name='refund_items')
    quantity = models.PositiveIntegerField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        db_table = 'refund_items'
        indexes = [
            models.Index(fields=['refund', 'sale_item']),
        ]
    
    def __str__(self):
        return f"Refund {self.quantity} x {self.sale_item.product.name}"


class CreditTransaction(models.Model):
    """Credit transactions for customer credit management"""
    TRANSACTION_TYPE_CHOICES = [
        ('CREDIT_SALE', 'Credit Sale'),
        ('PAYMENT', 'Payment'),
        ('ADJUSTMENT', 'Adjustment'),
        ('REFUND', 'Refund'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='credit_transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    balance_before = models.DecimalField(max_digits=10, decimal_places=2)
    balance_after = models.DecimalField(max_digits=10, decimal_places=2)
    reference_id = models.UUIDField(null=True, blank=True)  # Sale ID, Payment ID, etc.
    description = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='credit_transactions')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'credit_transactions'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['customer', 'created_at']),
            models.Index(fields=['transaction_type', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.customer.name} - {self.transaction_type} - {self.amount}"
