# Stock Data Integrity: Signals vs Database Triggers Analysis

## Overview
We need to ensure data integrity during stock operations to prevent:
1. **Negative stock situations** - Adjustments/transfers that exceed available stock
2. **Calculation inconsistencies** - Available stock = quantity + adjustments - transfers - sales
3. **Concurrent transaction issues** - Race conditions in stock operations

## Option 1: Django Signals (Current Approach)

### Pros ✅
- **Python-based** - Easy to write, test, and debug
- **Portable** - Works across different databases (PostgreSQL, MySQL, SQLite)
- **Integrated with Django** - Access to ORM, models, and business logic
- **Testable** - Can write unit tests easily
- **Maintainable** - Code lives in Python, visible in codebase
- **Flexible** - Can add complex business logic, logging, notifications
- **Already implemented** - We have signals preventing quantity edits

### Cons ❌
- **Not true database-level enforcement** - Can be bypassed by raw SQL
- **Transaction timing** - Runs in application layer, not database layer
- **Performance** - Slight overhead compared to database triggers
- **Race conditions** - Possible in high-concurrency scenarios (though rare in POS)

### Current Implementation
```python
# inventory/signals.py
@receiver(pre_save, sender=StockProduct)
def prevent_quantity_edit_after_movements(sender, instance, **kwargs):
    """Prevent editing quantity after movements occur"""
    if instance.pk:
        original = StockProduct.objects.get(pk=instance.pk)
        if original.quantity != instance.quantity:
            # Check if movements exist
            has_movements = (
                adjustments.count() > 0 or
                transfers.count() > 0 or
                sales.count() > 0
            )
            if has_movements:
                raise ValidationError("Cannot edit quantity after movements")
```

## Option 2: Database Triggers

### Pros ✅
- **True database-level enforcement** - Cannot be bypassed
- **Performance** - Executes directly in database
- **ACID guarantees** - Part of database transaction
- **No race conditions** - Database handles locking automatically
- **Always enforced** - Even if Django app bypassed

### Cons ❌
- **Database-specific** - Different syntax for PostgreSQL, MySQL, SQLite
- **Not portable** - Harder to migrate between databases
- **Testing complexity** - Requires database-specific testing
- **Debugging difficulty** - Errors less clear, harder to trace
- **Migration challenges** - Must write custom migrations
- **Version control** - Trigger code in migrations, not Python files
- **Limited logic** - Cannot access Django models, send emails, etc.

### Example (PostgreSQL)
```sql
CREATE OR REPLACE FUNCTION check_stock_availability()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.quantity < 0 THEN
        RAISE EXCEPTION 'Stock quantity cannot be negative';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER prevent_negative_stock
    BEFORE INSERT OR UPDATE ON stock_products
    FOR EACH ROW
    EXECUTE FUNCTION check_stock_availability();
```

## Recommendation: **Hybrid Approach** 🎯

Use **Django Signals as primary method** + **Database Constraints as safety net**

### Why Hybrid?

1. **Signals for business logic** (90% of cases)
   - Validation with clear error messages
   - Complex calculations
   - Audit logging
   - Notifications

2. **Database constraints for safety** (edge cases)
   - Prevent negative quantities
   - Ensure referential integrity
   - Catch bypassed operations

## Implementation Plan

### Phase 1: Enhanced Django Signals ✅ (Already Started)

**What we have:**
- ✅ Prevent quantity edits after movements
- ✅ Clear validation errors

**What we need to add:**
```python
# Additional validations needed:

1. validate_adjustment_wont_cause_negative_stock()
   - Before creating adjustment
   - Check: quantity + sum(adjustments) + new_adjustment >= 0
   
2. validate_transfer_has_sufficient_stock()
   - Before creating transfer
   - Check: available_stock >= transfer_quantity
   
3. validate_sale_has_sufficient_inventory()
   - Before creating sale
   - Check: storefront_inventory >= sale_quantity
   
4. validate_storefront_inventory_consistency()
   - On inventory updates
   - Check: quantity >= 0
```

### Phase 2: Database Constraints (Safety Net)

```python
# In migrations or model Meta

class StockProduct(models.Model):
    quantity = models.DecimalField(...)
    
    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(quantity__gte=0),
                name='stock_quantity_non_negative'
            )
        ]

class StoreFrontInventory(models.Model):
    quantity = models.DecimalField(...)
    
    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(quantity__gte=0),
                name='storefront_inventory_non_negative'
            )
        ]
```

### Phase 3: Transaction Locking (For Concurrency)

```python
from django.db import transaction
from django.db.models import F

def process_sale(sale_items):
    with transaction.atomic():
        for item in sale_items:
            # Use select_for_update to lock the row
            inventory = StoreFrontInventory.objects.select_for_update().get(
                product=item.product,
                storefront=item.storefront
            )
            
            # Validate
            if inventory.quantity < item.quantity:
                raise ValidationError("Insufficient stock")
            
            # Update using F() expression (atomic)
            inventory.quantity = F('quantity') - item.quantity
            inventory.save()
```

## Specific Solutions for Your Use Cases

### 1. Stock Adjustments

**Problem:** Prevent adjustments that cause negative available stock

**Solution: Django Signal**
```python
@receiver(pre_save, sender=StockAdjustment)
def validate_adjustment_wont_cause_negative_stock(sender, instance, **kwargs):
    """Ensure adjustment won't cause negative available stock"""
    if instance.status == 'COMPLETED':
        stock_product = instance.stock_product
        
        # Calculate what available stock would be after this adjustment
        current_adjustments = stock_product.adjustments.filter(
            status='COMPLETED'
        ).aggregate(total=Sum('quantity'))['total'] or Decimal('0')
        
        new_total = stock_product.quantity + current_adjustments + instance.quantity
        
        # Check transfers and sales
        transferred = get_transferred_quantity(stock_product)
        sold = get_sold_quantity(stock_product)
        
        available_after = new_total - transferred - sold
        
        if available_after < 0:
            raise ValidationError(
                f"This adjustment would result in negative available stock. "
                f"Current: {current_adjustments}, New: {instance.quantity}, "
                f"Would result in: {available_after} units available."
            )
```

### 2. Stock Transfers

**Problem:** Prevent transfers exceeding available warehouse stock

**Solution: Django Signal**
```python
@receiver(pre_save, sender=TransferRequestLineItem)
def validate_transfer_has_sufficient_stock(sender, instance, **kwargs):
    """Ensure warehouse has enough stock for transfer"""
    if instance.transfer_request.status == 'FULFILLED':
        stock_product = instance.stock_product
        available = stock_product.available_quantity  # Uses property
        
        if available < instance.quantity_fulfilled:
            raise ValidationError(
                f"Insufficient stock to fulfill transfer. "
                f"Available: {available}, Requested: {instance.quantity_fulfilled}"
            )
```

### 3. Database Constraints (Safety Net)

**Add to models:**
```python
# inventory/models.py

class StockProduct(models.Model):
    # ... fields ...
    
    class Meta:
        db_table = 'stock_products'
        constraints = [
            # Prevent negative quantity
            models.CheckConstraint(
                check=models.Q(quantity__gte=0),
                name='stock_product_quantity_non_negative',
                violation_error_message='Stock quantity cannot be negative'
            ),
        ]

class StoreFrontInventory(models.Model):
    # ... fields ...
    
    class Meta:
        db_table = 'storefront_inventory'
        constraints = [
            # Prevent negative inventory
            models.CheckConstraint(
                check=models.Q(quantity__gte=0),
                name='storefront_inventory_quantity_non_negative',
                violation_error_message='Storefront inventory cannot be negative'
            ),
        ]
```

## Best Practice: Defensive Programming

```python
# Always use this pattern for stock operations:

from django.db import transaction

@transaction.atomic
def create_stock_adjustment(stock_product, quantity, reason):
    """Safely create stock adjustment with validation"""
    
    # 1. Lock the stock product row
    stock_product = StockProduct.objects.select_for_update().get(
        pk=stock_product.pk
    )
    
    # 2. Calculate impact
    available_after = calculate_available_stock(stock_product, quantity)
    
    # 3. Validate
    if available_after < 0:
        raise ValidationError(
            f"Insufficient stock. Available: {available_after}"
        )
    
    # 4. Create adjustment
    adjustment = StockAdjustment.objects.create(
        stock_product=stock_product,
        quantity=quantity,
        reason=reason,
        status='COMPLETED'
    )
    
    # Signal automatically validates before save
    
    return adjustment
```

## Migration Strategy

### Step 1: Add Database Constraints
```bash
python manage.py makemigrations --name add_stock_constraints
python manage.py migrate
```

### Step 2: Add Enhanced Signals
- Validate adjustments
- Validate transfers
- Validate sales

### Step 3: Add Transaction Locking
- Use select_for_update() in critical operations
- Use F() expressions for atomic updates

### Step 4: Test Everything
- Unit tests for each signal
- Integration tests for workflows
- Load tests for concurrency

## Conclusion

**Recommended Approach: Django Signals + Database Constraints**

✅ **Primary:** Django signals for all business logic validation  
✅ **Secondary:** Database check constraints as safety net  
✅ **Tertiary:** Transaction locking for concurrency  

**Why:**
- Maintainable (Python code)
- Testable (unit tests)
- Portable (works on all databases)
- Safe (database constraints as backup)
- Clear errors (Django validation messages)
- Auditable (can log violations)

**Database triggers:** Only if you have:
- Extremely high concurrency requirements
- Need to prevent bypassing via raw SQL
- Database-specific features needed
- Team expertise in database programming

For a POS system like yours, **Django signals are the right choice** with database constraints as safety net.

---

**Next Steps:**
1. Implement enhanced validation signals
2. Add database check constraints
3. Add transaction locking to critical operations
4. Write comprehensive tests
5. Deploy with confidence! 🚀
