"""
Inventory Signal Handlers

Database triggers to maintain data integrity for stock movements.

CRITICAL DESIGN RULES:
====================
1. StockProduct.quantity is the INITIAL INTAKE AMOUNT and NEVER CHANGES after creation
2. StockProduct.quantity can ONLY be edited:
   - During creation (intake)
   - Before ANY stock movements occur (to fix intake errors)
3. Once ANY movement exists, StockProduct.quantity is PERMANENTLY LOCKED
4. All stock changes are tracked separately in:
   - StockAdjustment (damage, theft, corrections, etc.)
   - TransferRequest (warehouse → storefront)
   - Sale (storefront → customer)
5. Available quantity is CALCULATED, not stored:
   Available = StockProduct.quantity + SUM(adjustments) - SUM(transfers) - SUM(sales)

WHAT THESE SIGNALS DO:
=====================
✅ Prevent manual editing of StockProduct.quantity after movements
✅ Validate adjustments won't cause negative available stock
✅ Validate transfers have sufficient available stock
❌ DO NOT modify StockProduct.quantity (except to prevent edits)
❌ DO NOT apply adjustments to StockProduct.quantity
❌ DO NOT reduce StockProduct.quantity on transfers
"""

from django.db import transaction
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError


from django.db import transaction
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.core.exceptions import ValidationError


@receiver(pre_save, sender='inventory.StockProduct')
def prevent_quantity_edit_after_movements(sender, instance, **kwargs):
    """
    CRITICAL: Prevent ANY editing of StockProduct.quantity after stock movements.
    
    StockProduct.quantity represents the INITIAL INTAKE AMOUNT and must NEVER change
    once stock movements have occurred. This ensures data integrity and audit trails.
    
    Allowed:
    - Setting quantity on creation (intake)
    - Editing quantity BEFORE any movements (to fix intake errors)
    
    Blocked:
    - ANY edits to quantity after adjustments exist
    - ANY edits to quantity after transfers exist
    - ANY edits to quantity after sales exist
    
    Why: Available stock is calculated as:
         Available = StockProduct.quantity + SUM(adjustments) - SUM(transfers) - SUM(sales)
         
    If we modify StockProduct.quantity, we break this calculation and lose audit trail.
    """
    from inventory.models import StockProduct
    
    # Allow changes on new objects (intake)
    if not instance.pk:
        return
    
    # Get the existing object from database
    try:
        old_instance = StockProduct.objects.get(pk=instance.pk)
    except StockProduct.DoesNotExist:
        return
    
    # Check if quantity is being changed
    if old_instance.quantity == instance.quantity:
        # No change to quantity, allow other field updates
        return
    
    # CRITICAL CHECK: Has ANY stock movement occurred?
    has_movements = False
    movement_details = []
    
    # Check for completed adjustments
    adjustment_count = instance.adjustments.filter(status='COMPLETED').count()
    if adjustment_count > 0:
        has_movements = True
        movement_details.append(f"{adjustment_count} completed adjustment(s)")
    
    # Check for fulfilled transfers
    if not has_movements:
        from inventory.models import StoreFrontInventory
        storefront_count = StoreFrontInventory.objects.filter(
            product=instance.product,
            quantity__gt=0
        ).count()
        if storefront_count > 0:
            has_movements = True
            movement_details.append(f"{storefront_count} storefront(s) with inventory")
    
    # Check for completed sales
    if not has_movements:
        from sales.models import SaleItem
        sale_count = SaleItem.objects.filter(
            product=instance.product,
            sale__status='COMPLETED'
        ).count()
        if sale_count > 0:
            has_movements = True
            movement_details.append(f"{sale_count} completed sale(s)")
    
    # BLOCK the change if any movements exist
    if has_movements:
        details = ', '.join(movement_details)
        raise ValidationError(
            f'BLOCKED: Cannot modify StockProduct.quantity for {instance.product.name} '
            f'because stock movements have occurred ({details}). '
            f'StockProduct.quantity represents the initial intake amount and must remain '
            f'unchanged at {old_instance.quantity} units. '
            f'Use Stock Adjustments to record corrections - they will be reflected in '
            f'available stock calculations without modifying the intake record.'
        )


@receiver(pre_save, sender='inventory.StockAdjustment')
def validate_adjustment_wont_cause_negative_stock(sender, instance, **kwargs):
    """
    Validate that a stock adjustment won't cause negative available stock.
    
    Since StockProduct.quantity never changes, we need to calculate available stock:
    Available = StockProduct.quantity + SUM(completed adjustments) - SUM(transfers) - SUM(sales)
    
    This validates BEFORE the adjustment is marked complete to prevent errors.
    """
    from inventory.stock_adjustments import StockAdjustment
    
    # Only validate when transitioning to COMPLETED
    if instance.status != 'COMPLETED':
        return
    
    # Check if this is a status change to COMPLETED
    if instance.pk:
        try:
            old_instance = StockAdjustment.objects.get(pk=instance.pk)
            if old_instance.status == 'COMPLETED':
                # Already completed, skip validation
                return
        except StockAdjustment.DoesNotExist:
            pass
    
    # Only validate negative adjustments
    if instance.quantity >= 0:
        return
    
    # Calculate current available stock
    stock_product = instance.stock_product
    if not stock_product:
        return
    
    from inventory.models import StoreFrontInventory
    from sales.models import SaleItem
    
    # Start with initial intake
    available = stock_product.quantity
    
    # Add completed adjustments (excluding this one)
    adjustments_sum = stock_product.adjustments.filter(
        status='COMPLETED'
    ).exclude(pk=instance.pk).aggregate(
        total=transaction.models.Sum('quantity')
    )['total'] or 0
    available += adjustments_sum
    
    # Subtract transferred stock (storefront inventory for this product)
    transferred = StoreFrontInventory.objects.filter(
        product=stock_product.product
    ).aggregate(total=transaction.models.Sum('quantity'))['total'] or 0
    available -= transferred
    
    # Subtract completed sales
    sold = SaleItem.objects.filter(
        product=stock_product.product,
        sale__status='COMPLETED'
    ).aggregate(total=transaction.models.Sum('quantity'))['total'] or 0
    available -= sold
    
    # Check if this adjustment would make it negative
    new_available = available + instance.quantity
    
    if new_available < 0:
        raise ValidationError(
            f'Cannot complete adjustment: would result in negative available stock. '
            f'Current available: {available} units, Adjustment: {instance.quantity} units, '
            f'Would result in: {new_available} units. '
            f'(Initial intake: {stock_product.quantity}, Adjustments: {adjustments_sum}, '
            f'Transferred: {transferred}, Sold: {sold})'
        )


@receiver(pre_save, sender='inventory.TransferRequest')
def validate_transfer_has_sufficient_stock(sender, instance, **kwargs):
    """
    Validate that a transfer request has sufficient available warehouse stock.
    
    Checks BEFORE marking as fulfilled to prevent errors.
    """
    from inventory.models import TransferRequest
    
    # Only validate when transitioning to FULFILLED
    if instance.status != TransferRequest.STATUS_FULFILLED:
        return
    
    # Check if this is a status change to FULFILLED
    if instance.pk:
        try:
            old_instance = TransferRequest.objects.get(pk=instance.pk)
            if old_instance.status == TransferRequest.STATUS_FULFILLED:
                # Already fulfilled, skip
                return
        except TransferRequest.DoesNotExist:
            pass
    
    # Validate each line item has sufficient stock
    from inventory.models import StockProduct, StoreFrontInventory
    from sales.models import SaleItem
    
    for line in instance.line_items.select_related('product'):
        product = line.product
        requested = line.requested_quantity
        
        # Get all warehouse batches for this product
        batches = StockProduct.objects.filter(
            product=product,
            business=instance.business
        )
        
        if not batches.exists():
            raise ValidationError(
                f'No warehouse stock found for {product.name} (SKU: {product.sku})'
            )
        
        # Calculate available stock across all batches
        total_intake = sum(batch.quantity for batch in batches)
        
        # Add adjustments
        adjustments_sum = 0
        for batch in batches:
            batch_adjustments = batch.adjustments.filter(
                status='COMPLETED'
            ).aggregate(total=transaction.models.Sum('quantity'))['total'] or 0
            adjustments_sum += batch_adjustments
        
        # Subtract already transferred
        transferred = StoreFrontInventory.objects.filter(
            product=product
        ).aggregate(total=transaction.models.Sum('quantity'))['total'] or 0
        
        # Subtract sold
        sold = SaleItem.objects.filter(
            product=product,
            sale__status='COMPLETED'
        ).aggregate(total=transaction.models.Sum('quantity'))['total'] or 0
        
        available = total_intake + adjustments_sum - transferred - sold
        
        if available < requested:
            raise ValidationError(
                f'Insufficient warehouse stock for {product.name}: '
                f'requested {requested} units, only {available} available. '
                f'(Intake: {total_intake}, Adjustments: {adjustments_sum}, '
                f'Transferred: {transferred}, Sold: {sold})'
            )


# Import models to ensure signals are registered
def ready():
    """Called when Django app is ready."""
    from inventory.stock_adjustments import StockAdjustment
    from inventory.models import TransferRequest, StockProduct

