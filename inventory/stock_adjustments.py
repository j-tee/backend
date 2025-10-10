"""
Stock Adjustment Models

Tracks all real-world stock changes beyond sales:
- Theft
- Damage/Breakage
- Expiration
- Returns (customer returns)
- Supplier Returns (returning to supplier)
- Adjustments (inventory count corrections)
- Transfers (between locations)
- Samples/Promotional use
"""

from django.db import models
from django.core.validators import MinValueValidator
from django.contrib.auth import get_user_model
from decimal import Decimal
import uuid

from accounts.models import Business

User = get_user_model()


class StockAdjustment(models.Model):
    """
    Tracks all stock level changes that are not sales.
    
    This provides a complete audit trail of why stock levels change,
    enabling accurate inventory management and loss prevention.
    """
    
    ADJUSTMENT_TYPES = [
        # Negative adjustments (reduce stock)
        ('THEFT', 'Theft/Shrinkage'),
        ('DAMAGE', 'Damage/Breakage'),
        ('EXPIRED', 'Expired Product'),
        ('SPOILAGE', 'Spoilage'),
        ('LOSS', 'Lost/Missing'),
        ('SAMPLE', 'Sample/Promotional Use'),
        ('WRITE_OFF', 'Write-off'),
        ('SUPPLIER_RETURN', 'Return to Supplier'),
        
        # Positive adjustments (increase stock)
        ('CUSTOMER_RETURN', 'Customer Return'),
        ('FOUND', 'Found Item'),
        ('CORRECTION_INCREASE', 'Inventory Count Correction (Increase)'),
        
        # Can be either
        ('CORRECTION', 'Inventory Count Correction'),
        ('RECOUNT', 'Physical Count Adjustment'),
        ('TRANSFER_OUT', 'Transfer Out'),
        ('TRANSFER_IN', 'Transfer In'),
        ('OTHER', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('COMPLETED', 'Completed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='stock_adjustments')
    
    # What is being adjusted
    stock_product = models.ForeignKey(
        'inventory.StockProduct',
        on_delete=models.CASCADE,
        related_name='adjustments',
        help_text='The stock batch being adjusted'
    )
    
    # Adjustment details
    adjustment_type = models.CharField(max_length=50, choices=ADJUSTMENT_TYPES)
    quantity = models.IntegerField(
        help_text='Positive for increases, negative for decreases'
    )
    quantity_before = models.IntegerField(
        null=True,
        blank=True,
        help_text='Stock product quantity before this adjustment (snapshot at creation)'
    )
    
    # Financial impact
    unit_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text='Cost per unit at time of adjustment'
    )
    total_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text='Total financial impact (auto-calculated)'
    )
    
    # Documentation
    reason = models.TextField(help_text='Detailed reason for adjustment')
    reference_number = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text='External reference (e.g., police report number, supplier RMA)'
    )
    
    # Approval workflow
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    requires_approval = models.BooleanField(
        default=True,
        help_text='Whether this adjustment needs manager approval'
    )
    
    # Audit trail
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='stock_adjustments_created'
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_adjustments_approved'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Supporting evidence
    has_photos = models.BooleanField(default=False)
    has_documents = models.BooleanField(default=False)
    
    # Linked transactions
    related_sale = models.ForeignKey(
        'sales.Sale',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_adjustments',
        help_text='Related sale for customer returns'
    )
    related_transfer = models.ForeignKey(
        'inventory.Transfer',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_adjustments',
        help_text='Related transfer for transfer adjustments'
    )
    
    class Meta:
        db_table = 'stock_adjustments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['business', 'adjustment_type']),
            models.Index(fields=['stock_product', 'status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['status', 'requires_approval']),
        ]
    
    def __str__(self):
        return f"{self.get_adjustment_type_display()} - {self.quantity} units - {self.stock_product.product.name}"
    
    def save(self, *args, **kwargs):
        # Capture quantity before on creation (historical snapshot)
        if not self.pk and self.stock_product:  # New object
            self.quantity_before = self.stock_product.quantity
        
        # Auto-calculate total cost
        if self.unit_cost and self.quantity:
            self.total_cost = abs(self.unit_cost * Decimal(str(abs(self.quantity))))
        
        # Set business from stock_product if not provided
        if not self.business and self.stock_product:
            # Get business from the product (products belong to businesses)
            self.business = self.stock_product.product.business
        
        super().save(*args, **kwargs)
    
    @property
    def is_increase(self):
        """Check if this adjustment increases stock"""
        return self.quantity > 0
    
    @property
    def is_decrease(self):
        """Check if this adjustment decreases stock"""
        return self.quantity < 0
    
    @property
    def financial_impact(self):
        """Get the financial impact (loss or gain)"""
        if self.quantity < 0:
            return -self.total_cost  # Loss
        return self.total_cost  # Gain (unusual but possible)
    
    def approve(self, user):
        """Approve the adjustment"""
        from django.utils import timezone
        
        self.status = 'APPROVED'
        self.approved_by = user
        self.approved_at = timezone.now()
        self.save()
    
    def reject(self, user):
        """Reject the adjustment"""
        self.status = 'REJECTED'
        self.approved_by = user
        self.save()
    
    def complete(self):
        """
        Mark adjustment as completed.
        
        IMPORTANT: This does NOT modify StockProduct.quantity!
        StockProduct.quantity is the initial intake amount and never changes.
        Adjustments are tracked separately and reflected in available stock calculations.
        
        The pre_save signal validates this won't cause negative available stock.
        """
        from django.utils import timezone
        
        if self.status != 'APPROVED':
            raise ValueError('Only approved adjustments can be completed')
        
        # The pre_save signal will validate this won't cause negative stock
        # We do NOT modify stock_product.quantity here
        
        self.status = 'COMPLETED'
        self.completed_at = timezone.now()
        self.save()


class StockAdjustmentPhoto(models.Model):
    """Photos documenting stock adjustments (damage, theft, etc.)"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    adjustment = models.ForeignKey(
        StockAdjustment,
        on_delete=models.CASCADE,
        related_name='photos'
    )
    photo = models.ImageField(upload_to='stock_adjustments/%Y/%m/')
    description = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        db_table = 'stock_adjustment_photos'
        ordering = ['uploaded_at']
    
    def __str__(self):
        return f"Photo for {self.adjustment}"


class StockAdjustmentDocument(models.Model):
    """Documents supporting stock adjustments (receipts, reports, etc.)"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    adjustment = models.ForeignKey(
        StockAdjustment,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    document = models.FileField(upload_to='stock_adjustments/docs/%Y/%m/')
    document_type = models.CharField(
        max_length=50,
        choices=[
            ('RECEIPT', 'Receipt'),
            ('INVOICE', 'Invoice'),
            ('POLICE_REPORT', 'Police Report'),
            ('INSURANCE_CLAIM', 'Insurance Claim'),
            ('SUPPLIER_RMA', 'Supplier RMA'),
            ('COUNT_SHEET', 'Physical Count Sheet'),
            ('OTHER', 'Other'),
        ]
    )
    description = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        db_table = 'stock_adjustment_documents'
        ordering = ['uploaded_at']
    
    def __str__(self):
        return f"{self.get_document_type_display()} for {self.adjustment}"


class StockCount(models.Model):
    """
    Physical stock count sessions for inventory reconciliation.
    
    Used to identify discrepancies between system and actual stock,
    triggering adjustments as needed.
    """
    
    STATUS_CHOICES = [
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='stock_counts')
    
    # Scope
    storefront = models.ForeignKey(
        'inventory.StoreFront',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='stock_counts',
        help_text='If specified, count only this storefront'
    )
    warehouse = models.ForeignKey(
        'inventory.Warehouse',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='stock_counts',
        help_text='If specified, count only this warehouse'
    )
    
    # Count details
    count_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='IN_PROGRESS')
    notes = models.TextField(blank=True)
    
    # Audit
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='stock_counts_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'stock_counts'
        ordering = ['-count_date']
        indexes = [
            models.Index(fields=['business', 'status']),
            models.Index(fields=['count_date']),
        ]
    
    def __str__(self):
        location = self.storefront or self.warehouse or 'All Locations'
        return f"Stock Count - {location} - {self.count_date}"
    
    def complete(self):
        """Mark count as completed"""
        from django.utils import timezone
        
        self.status = 'COMPLETED'
        self.completed_at = timezone.now()
        self.save()


class StockCountItem(models.Model):
    """Individual item counts within a stock count session"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stock_count = models.ForeignKey(
        StockCount,
        on_delete=models.CASCADE,
        related_name='items'
    )
    stock_product = models.ForeignKey(
        'inventory.StockProduct',
        on_delete=models.CASCADE,
        related_name='count_items'
    )
    
    # Count results
    system_quantity = models.IntegerField(help_text='Quantity in system')
    counted_quantity = models.IntegerField(help_text='Actual counted quantity')
    discrepancy = models.IntegerField(help_text='Difference (counted - system)')
    
    # Notes
    counter_name = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    counted_at = models.DateTimeField(auto_now_add=True)
    
    # Linked adjustment if discrepancy exists
    adjustment_created = models.ForeignKey(
        StockAdjustment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='count_items'
    )
    
    class Meta:
        db_table = 'stock_count_items'
        ordering = ['stock_count', 'stock_product']
        unique_together = ['stock_count', 'stock_product']
    
    def __str__(self):
        return f"{self.stock_product.product.name} - System: {self.system_quantity}, Counted: {self.counted_quantity}"
    
    def save(self, *args, **kwargs):
        # Auto-calculate discrepancy
        self.discrepancy = self.counted_quantity - self.system_quantity
        super().save(*args, **kwargs)
    
    @property
    def has_discrepancy(self):
        """Check if there's a variance"""
        return self.discrepancy != 0
    
    @property
    def discrepancy_percentage(self):
        """Calculate variance as percentage"""
        if self.system_quantity == 0:
            return 0 if self.counted_quantity == 0 else 100
        return (abs(self.discrepancy) / self.system_quantity) * 100
    
    def create_adjustment(self, user):
        """Create a stock adjustment for the discrepancy"""
        if not self.has_discrepancy:
            return None
        
        if self.adjustment_created:
            return self.adjustment_created
        
        # Determine adjustment type based on discrepancy
        if self.discrepancy > 0:
            adjustment_type = 'CORRECTION_INCREASE'
            reason = f'Physical count found {self.discrepancy} more units than system'
        else:
            adjustment_type = 'CORRECTION'
            reason = f'Physical count found {abs(self.discrepancy)} fewer units than system'
        
        adjustment = StockAdjustment.objects.create(
            business=self.stock_count.business,
            stock_product=self.stock_product,
            adjustment_type=adjustment_type,
            quantity=self.discrepancy,
            unit_cost=self.stock_product.landed_unit_cost,
            reason=reason,
            reference_number=f'COUNT-{self.stock_count.id}',
            status='PENDING',
            requires_approval=True,
            created_by=user
        )
        
        self.adjustment_created = adjustment
        self.save()
        
        return adjustment
