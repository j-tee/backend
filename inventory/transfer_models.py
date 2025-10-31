"""
Transfer Models - New unified transfer system for warehouse-to-warehouse 
and warehouse-to-storefront transfers.

This replaces the legacy StockAdjustment TRANSFER_IN/TRANSFER_OUT pairs 
with a single Transfer record containing multiple TransferItem records.
"""
from decimal import Decimal
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from accounts.models import Business, User
import uuid


class Transfer(models.Model):
    """
    Unified transfer record for moving inventory between locations.
    
    Supports:
    - Warehouse to Warehouse transfers
    - Warehouse to Storefront transfers
    
    Status workflow:
    - pending: Transfer created, awaiting completion
    - in_transit: (Optional) Transfer shipped but not received
    - completed: Transfer finalized, inventory moved
    - cancelled: Transfer cancelled, no inventory movement
    """
    
    # Transfer Types
    TYPE_WAREHOUSE_TO_WAREHOUSE = 'W2W'
    TYPE_WAREHOUSE_TO_STOREFRONT = 'W2S'
    
    TRANSFER_TYPE_CHOICES = [
        (TYPE_WAREHOUSE_TO_WAREHOUSE, 'Warehouse to Warehouse'),
        (TYPE_WAREHOUSE_TO_STOREFRONT, 'Warehouse to Storefront'),
    ]
    
    # Transfer Status
    STATUS_PENDING = 'pending'
    STATUS_IN_TRANSIT = 'in_transit'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_IN_TRANSIT, 'In Transit'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]
    
    # Primary fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='transfers'
    )
    
    # Transfer classification
    transfer_type = models.CharField(
        max_length=3,
        choices=TRANSFER_TYPE_CHOICES,
        db_index=True
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True
    )
    
    # Source location (always a warehouse)
    source_warehouse = models.ForeignKey(
        'inventory.Warehouse',
        on_delete=models.PROTECT,
        related_name='outbound_transfers'
    )
    
    # Destination location (warehouse OR storefront)
    destination_warehouse = models.ForeignKey(
        'inventory.Warehouse',
        on_delete=models.PROTECT,
        related_name='inbound_transfers',
        null=True,
        blank=True,
        help_text="For W2W transfers"
    )
    destination_storefront = models.ForeignKey(
        'inventory.StoreFront',
        on_delete=models.PROTECT,
        related_name='inbound_transfers',
        null=True,
        blank=True,
        help_text="For W2S transfers"
    )
    
    # Transfer tracking
    reference_number = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Auto-generated if not provided: TRF-YYYYMMDDHHMMSS"
    )
    expected_arrival_date = models.DateField(
        null=True,
        blank=True,
        help_text="Expected arrival date at destination"
    )
    notes = models.TextField(blank=True, null=True)
    
    # Audit fields
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_transfers'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Completion tracking
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='completed_transfers'
    )
    
    # Reception tracking (optional, for in_transit workflow)
    received_at = models.DateTimeField(null=True, blank=True)
    received_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='received_transfers'
    )
    
    class Meta:
        db_table = 'inventory_transfer'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['business', 'status']),
            models.Index(fields=['business', 'created_at']),
            models.Index(fields=['source_warehouse', 'status']),
            models.Index(fields=['destination_warehouse', 'status']),
            models.Index(fields=['reference_number']),
        ]
    
    def __str__(self):
        return f"{self.reference_number} ({self.get_transfer_type_display()})"
    
    def clean(self):
        """Validate transfer before saving."""
        super().clean()
        
        # Validate transfer type matches destination
        if self.transfer_type == self.TYPE_WAREHOUSE_TO_WAREHOUSE:
            if not self.destination_warehouse:
                raise ValidationError({
                    'destination_warehouse': 'Warehouse-to-Warehouse transfers require destination_warehouse'
                })
            if self.destination_storefront:
                raise ValidationError({
                    'destination_storefront': 'Warehouse-to-Warehouse transfers cannot have destination_storefront'
                })
        
        elif self.transfer_type == self.TYPE_WAREHOUSE_TO_STOREFRONT:
            if not self.destination_storefront:
                raise ValidationError({
                    'destination_storefront': 'Warehouse-to-Storefront transfers require destination_storefront'
                })
            if self.destination_warehouse:
                raise ValidationError({
                    'destination_warehouse': 'Warehouse-to-Storefront transfers cannot have destination_warehouse'
                })
        
        # Prevent self-transfer for W2W
        if self.transfer_type == self.TYPE_WAREHOUSE_TO_WAREHOUSE:
            if self.source_warehouse == self.destination_warehouse:
                raise ValidationError({
                    'destination_warehouse': 'Cannot transfer to the same warehouse as source'
                })
        
        # Validate status transitions (only for updates, not new records)
        if self.pk and Transfer.objects.filter(pk=self.pk).exists():  # Record exists in DB
            old_status = Transfer.objects.get(pk=self.pk).status
            if old_status == self.STATUS_COMPLETED and self.status != self.STATUS_COMPLETED:
                raise ValidationError({
                    'status': 'Cannot change status of completed transfer'
                })
            if old_status == self.STATUS_CANCELLED:
                raise ValidationError({
                    'status': 'Cannot change status of cancelled transfer'
                })
    
    def save(self, *args, **kwargs):
        """Auto-generate reference number if not provided."""
        if not self.reference_number:
            self.reference_number = self._generate_reference_number()
        
        self.full_clean()
        super().save(*args, **kwargs)
    
    def _generate_reference_number(self):
        """Generate unique reference number: TRF-YYYYMMDDHHMMSS"""
        now = timezone.now()
        base_reference = f"TRF-{now.strftime('%Y%m%d%H%M%S')}"
        
        # Ensure uniqueness by appending counter if needed
        reference = base_reference
        counter = 1
        while Transfer.objects.filter(reference_number=reference).exists():
            reference = f"{base_reference}-{counter}"
            counter += 1
        
        return reference
    
    @transaction.atomic
    def complete_transfer(self, completed_by=None):
        """
        Complete the transfer by moving inventory atomically.
        
        Args:
            completed_by: User who completed the transfer
        
        Raises:
            ValidationError: If transfer cannot be completed (insufficient stock, already completed, etc.)
        """
        # Validate current status
        if self.status == self.STATUS_COMPLETED:
            return  # Idempotent - already completed
        
        if self.status == self.STATUS_CANCELLED:
            raise ValidationError('Cannot complete a cancelled transfer')
        
        # Import here to avoid circular dependency
        from inventory.models import StockProduct, Stock
        
        # Process each transfer item
        errors = []
        for item in self.items.all():
            try:
                # Get source stock
                source_stock = StockProduct.objects.select_for_update().filter(
                    warehouse=self.source_warehouse,
                    product=item.product,
                    stock__business=self.business
                ).first()
                
                if not source_stock:
                    errors.append(
                        f"Product '{item.product.name}' not found in source warehouse"
                    )
                    continue
                
                # Check sufficient quantity
                if source_stock.quantity < item.quantity:
                    errors.append(
                        f"Product '{item.product.name}': Insufficient stock. "
                        f"Available: {source_stock.quantity}, Required: {item.quantity}"
                    )
                    continue
                
                # Deduct from source (use update to bypass signals)
                new_quantity = source_stock.quantity - item.quantity
                StockProduct.objects.filter(pk=source_stock.pk).update(
                    quantity=new_quantity
                )
                
                # Add to destination
                if self.transfer_type == self.TYPE_WAREHOUSE_TO_WAREHOUSE:
                    # Get or create destination stock
                    destination_stock, created = StockProduct.objects.select_for_update().get_or_create(
                        warehouse=self.destination_warehouse,
                        product=item.product,
                        stock=source_stock.stock,  # Same stock record
                        defaults={
                            'quantity': 0,
                            'calculated_quantity': 0,
                            'unit_cost': item.unit_cost,
                            'supplier': item.supplier or source_stock.supplier,
                            'expiry_date': item.expiry_date or source_stock.expiry_date,
                            'unit_tax_rate': item.unit_tax_rate or source_stock.unit_tax_rate,
                            'unit_tax_amount': item.unit_tax_amount or source_stock.unit_tax_amount,
                            'unit_additional_cost': item.unit_additional_cost or source_stock.unit_additional_cost,
                            'retail_price': item.retail_price or source_stock.retail_price,
                            'wholesale_price': item.wholesale_price or source_stock.wholesale_price,
                        }
                    )
                    
                    # Update quantities (use update to bypass signals)
                    if created:
                        # New record, set initial quantities
                        StockProduct.objects.filter(pk=destination_stock.pk).update(
                            quantity=item.quantity,
                            calculated_quantity=item.quantity
                        )
                    else:
                        # Existing record, increment quantities
                        StockProduct.objects.filter(pk=destination_stock.pk).update(
                            quantity=destination_stock.quantity + item.quantity,
                            calculated_quantity=destination_stock.calculated_quantity + item.quantity
                        )
                
                elif self.transfer_type == self.TYPE_WAREHOUSE_TO_STOREFRONT:
                    # For storefront transfers, update storefront inventory records
                    from inventory.models import StoreFrontInventory

                    if not self.destination_storefront_id:
                        errors.append(
                            f"Transfer destination storefront missing for product '{item.product.name}'"
                        )
                        continue

                    storefront_entry, created = StoreFrontInventory.objects.select_for_update().get_or_create(
                        storefront=self.destination_storefront,
                        product=item.product,
                        defaults={'quantity': 0},
                    )

                    new_quantity = storefront_entry.quantity + item.quantity
                    StoreFrontInventory.objects.filter(pk=storefront_entry.pk).update(
                        quantity=new_quantity,
                        updated_at=timezone.now()
                    )
            
            except Exception as e:
                errors.append(f"Product '{item.product.name}': {str(e)}")
        
        # If any errors occurred, rollback via transaction.atomic
        if errors:
            raise ValidationError({
                'items': errors
            })
        
        # Update transfer status
        self.status = self.STATUS_COMPLETED
        self.completed_at = timezone.now()
        self.completed_by = completed_by
        
        # Also set received_at if not already set
        if not self.received_at:
            self.received_at = timezone.now()
            self.received_by = completed_by
        
        self.save()
    
    @transaction.atomic
    def cancel_transfer(self):
        """
        Cancel the transfer.
        
        Raises:
            ValidationError: If transfer is already completed
        """
        if self.status == self.STATUS_COMPLETED:
            raise ValidationError('Cannot cancel a completed transfer. Inventory has already been moved.')
        
        if self.status == self.STATUS_CANCELLED:
            return  # Idempotent - already cancelled
        
        self.status = self.STATUS_CANCELLED
        self.save()
    
    @property
    def total_items(self):
        """Get total number of items in transfer."""
        return self.items.count()
    
    @property
    def total_quantity(self):
        """Get total quantity across all items."""
        return self.items.aggregate(
            total=models.Sum('quantity')
        )['total'] or 0
    
    @property
    def total_value(self):
        """Get total value of transfer (sum of item total_cost)."""
        return self.items.aggregate(
            total=models.Sum('total_cost')
        )['total'] or Decimal('0.00')
    
    def get_items_detail(self):
        """Return detail payload for frontend movement view consumption."""
        from typing import List, Dict, Any
        
        transfer_items_qs = self.items.select_related(
            'product',
            'product__category',
            'supplier'
        ).all()
        
        payload: List[Dict[str, Any]] = []
        for item in transfer_items_qs:
            product = item.product
            supplier = item.supplier
            source_warehouse = self.source_warehouse
            destination_warehouse = self.destination_warehouse
            destination_storefront = self.destination_storefront
            
            payload.append({
                'transfer_item_id': str(item.id),
                'product_id': str(product.id) if product else None,
                'product_name': getattr(product, 'name', None),
                'product_sku': getattr(product, 'sku', None),
                'supplier_id': str(supplier.id) if supplier else None,
                'supplier_name': getattr(supplier, 'name', None),
                'source_warehouse_id': str(source_warehouse.id) if source_warehouse else None,
                'source_warehouse_name': getattr(source_warehouse, 'name', None),
                'destination_warehouse_id': str(destination_warehouse.id) if destination_warehouse else None,
                'destination_warehouse_name': getattr(destination_warehouse, 'name', None),
                'destination_storefront_id': str(destination_storefront.id) if destination_storefront else None,
                'destination_storefront_name': getattr(destination_storefront, 'name', None),
                'quantity': int(item.quantity) if item.quantity is not None else None,
                'unit_cost': str(item.unit_cost) if item.unit_cost is not None else None,
                'total_cost': str(item.total_cost) if item.total_cost is not None else None,
                'expiry_date': item.expiry_date.isoformat() if item.expiry_date else None,
                'retail_price': str(item.retail_price) if item.retail_price is not None else None,
                'wholesale_price': str(item.wholesale_price) if item.wholesale_price is not None else None,
            })
        
        return payload


class TransferItem(models.Model):
    """
    Individual product item within a transfer.
    Includes all fields needed to create StockProduct at destination.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transfer = models.ForeignKey(
        Transfer,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        'inventory.Product',
        on_delete=models.PROTECT
    )
    
    # Quantity and cost
    quantity = models.IntegerField(
        help_text="Quantity to transfer"
    )
    unit_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Cost per unit (auto-detected from source if not provided)"
    )
    total_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Calculated: quantity * unit_cost"
    )
    
    # Stock batch fields (needed for destination StockProduct creation)
    supplier = models.ForeignKey(
        'inventory.Supplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Original supplier (copied from source stock)"
    )
    expiry_date = models.DateField(
        null=True,
        blank=True,
        help_text="Expiration date for perishable items"
    )
    unit_tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        null=True,
        blank=True,
        help_text="Tax rate percentage (0-100)"
    )
    unit_tax_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        null=True,
        blank=True,
        help_text="Tax amount per unit"
    )
    unit_additional_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        null=True,
        blank=True,
        help_text="Additional costs per unit (shipping, handling, etc.)"
    )
    retail_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Retail selling price"
    )
    wholesale_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Wholesale selling price"
    )
    
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'inventory_transfer_item'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['transfer', 'product']),
        ]
        # Prevent duplicate products in same transfer
        constraints = [
            models.UniqueConstraint(
                fields=['transfer', 'product'],
                name='unique_product_per_transfer'
            )
        ]
    
    def __str__(self):
        return f"{self.product.name} x{self.quantity}"
    
    def clean(self):
        """Validate transfer item before saving."""
        super().clean()
        
        # Validate quantity > 0
        if self.quantity <= 0:
            raise ValidationError({
                'quantity': 'Quantity must be greater than zero'
            })
        
        # Validate unit_cost > 0 (only if provided)
        if self.unit_cost is not None and self.unit_cost <= 0:
            raise ValidationError({
                'unit_cost': 'Unit cost must be greater than zero'
            })
    
    def save(self, *args, **kwargs):
        """Auto-calculate total_cost before saving."""
        # Only calculate total_cost if we have a unit_cost
        if self.unit_cost is not None:
            self.total_cost = self.quantity * self.unit_cost
        else:
            self.total_cost = Decimal('0.00')
        
        # Skip full_clean during creation to allow None values
        # The serializer will populate missing fields before save
        if not kwargs.pop('skip_validation', False):
            self.full_clean()
        
        super().save(*args, **kwargs)
