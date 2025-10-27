# CRITICAL: Stock Adjustment Data Integrity Implementation

**Date:** 2025-10-09  
**Priority:** 🔴 URGENT - Data Integrity Issue  
**Status:** 🚧 Requires Immediate Implementation

---

## 🚨 Problem Statement

### Current Issue
Stock adjustments (shrinkage, damage, corrections) are **not automatically reflected** in the warehouse on-hand quantity. This creates a critical data integrity problem:

1. **Recorded Batch Size** = Initial quantity received from supplier
2. **Stock Adjustments** = Damage, theft, corrections (±)
3. **Warehouse On Hand** = Should be `Recorded - Storefront Transfers ± Adjustments`

**Current Behavior:**
- Adjustments are only applied when manually "completed"
- Warehouse on-hand calculation ignores pending/approved adjustments
- Risk of overselling warehouse stock that has been damaged/stolen
- Data integrity breach: Numbers don't match reality

**Critical Scenario:**
```
Recorded Batch: 100 units
Damage Adjustment: -10 units (APPROVED but not completed)
Storefront Request: 95 units

Current System: ✅ Allows (100 - 0 = 100 available)
Correct System: ❌ Should reject (100 - 10 = 90 available)
```

---

## ✅ Proposed Solution

### Option 1: Database-Level Constraints (RECOMMENDED)

Use PostgreSQL CHECK constraints and triggers to ensure data integrity at the database level.

#### Advantages:
- ✅ Atomic operations (no race conditions)
- ✅ Works across all application layers
- ✅ Cannot be bypassed by code bugs
- ✅ Optimal performance (no additional queries)
- ✅ Audit trail with trigger functions

#### Implementation:

**Step 1: Add Computed Column for Available Quantity**
```sql
-- Add virtual column that accounts for adjustments
ALTER TABLE stock_products 
ADD COLUMN available_quantity INTEGER GENERATED ALWAYS AS (
    quantity - COALESCE(
        (SELECT COALESCE(SUM(sa.quantity), 0)
         FROM stock_adjustments sa
         WHERE sa.stock_product_id = stock_products.id
         AND sa.status IN ('APPROVED', 'COMPLETED')
         AND sa.quantity < 0), -- Only count negative adjustments
    0)
) STORED;

-- Create index for performance
CREATE INDEX idx_stock_products_available_qty 
ON stock_products(available_quantity) 
WHERE available_quantity > 0;
```

**Step 2: Constraint to Prevent Over-Allocation**
```sql
-- Ensure transfers don't exceed available quantity
CREATE OR REPLACE FUNCTION check_stock_transfer_availability()
RETURNS TRIGGER AS $$
DECLARE
    v_stock_product_id UUID;
    v_current_available INTEGER;
    v_total_allocated INTEGER;
    v_new_allocation INTEGER;
BEGIN
    -- Get stock product ID from the transfer
    v_stock_product_id := NEW.stock_product_id;
    
    -- Get current available quantity
    SELECT available_quantity INTO v_current_available
    FROM stock_products
    WHERE id = v_stock_product_id;
    
    -- Calculate total allocated (including this new transfer)
    SELECT COALESCE(SUM(quantity), 0) INTO v_total_allocated
    FROM storefront_inventory
    WHERE stock_product_id = v_stock_product_id;
    
    v_new_allocation := v_total_allocated + NEW.quantity;
    
    -- Prevent over-allocation
    IF v_new_allocation > v_current_available THEN
        RAISE EXCEPTION 'Insufficient stock available. Available: %, Requested: %, Already Allocated: %',
            v_current_available, NEW.quantity, v_total_allocated
        USING ERRCODE = '23514'; -- check_violation
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Attach trigger to storefront inventory
CREATE TRIGGER ensure_stock_availability
    BEFORE INSERT OR UPDATE ON storefront_inventory
    FOR EACH ROW
    EXECUTE FUNCTION check_stock_transfer_availability();
```

**Step 3: Constraint on Adjustments**
```sql
-- Prevent adjustments that would make available quantity negative
CREATE OR REPLACE FUNCTION check_adjustment_validity()
RETURNS TRIGGER AS $$
DECLARE
    v_current_qty INTEGER;
    v_allocated_qty INTEGER;
    v_pending_adjustments INTEGER;
    v_new_available INTEGER;
BEGIN
    -- Get current quantity and allocations
    SELECT sp.quantity,
           COALESCE(SUM(sfi.quantity), 0)
    INTO v_current_qty, v_allocated_qty
    FROM stock_products sp
    LEFT JOIN storefront_inventory sfi ON sfi.stock_product_id = sp.id
    WHERE sp.id = NEW.stock_product_id
    GROUP BY sp.quantity;
    
    -- Get sum of other pending/approved negative adjustments
    SELECT COALESCE(SUM(quantity), 0) INTO v_pending_adjustments
    FROM stock_adjustments
    WHERE stock_product_id = NEW.stock_product_id
    AND id != NEW.id
    AND status IN ('APPROVED', 'COMPLETED')
    AND quantity < 0;
    
    -- Calculate what available would be with this adjustment
    v_new_available := v_current_qty + v_pending_adjustments + NEW.quantity;
    
    -- Ensure we don't go below allocated quantity
    IF v_new_available < v_allocated_qty THEN
        RAISE EXCEPTION 'Adjustment would reduce stock below allocated quantity. Current: %, Allocated to Stores: %, Adjustment: %',
            v_current_qty, v_allocated_qty, NEW.quantity
        USING ERRCODE = '23514';
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Attach trigger
CREATE TRIGGER validate_adjustment_before_save
    BEFORE INSERT OR UPDATE ON stock_adjustments
    FOR EACH ROW
    WHEN (NEW.status IN ('APPROVED', 'COMPLETED'))
    EXECUTE FUNCTION check_adjustment_validity();
```

**Step 4: Auto-Apply Approved Adjustments**
```sql
-- Automatically update stock quantity when adjustment is approved
CREATE OR REPLACE FUNCTION auto_apply_approved_adjustment()
RETURNS TRIGGER AS $$
BEGIN
    -- Only apply when transitioning to APPROVED or COMPLETED
    IF NEW.status IN ('APPROVED', 'COMPLETED') AND OLD.status = 'PENDING' THEN
        -- Update stock product quantity
        UPDATE stock_products
        SET quantity = quantity + NEW.quantity
        WHERE id = NEW.stock_product_id;
        
        -- Log the change
        INSERT INTO inventory_audit_log (
            table_name,
            record_id,
            action,
            old_value,
            new_value,
            changed_by,
            changed_at
        ) VALUES (
            'stock_products',
            NEW.stock_product_id,
            'ADJUSTMENT_APPLIED',
            (SELECT quantity - NEW.quantity FROM stock_products WHERE id = NEW.stock_product_id),
            (SELECT quantity FROM stock_products WHERE id = NEW.stock_product_id),
            NEW.approved_by,
            NOW()
        );
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Attach trigger
CREATE TRIGGER apply_adjustment_on_approval
    AFTER UPDATE ON stock_adjustments
    FOR EACH ROW
    WHEN (NEW.status IN ('APPROVED', 'COMPLETED') AND OLD.status != NEW.status)
    EXECUTE FUNCTION auto_apply_approved_adjustment();
```

---

### Option 2: Application-Level Enforcement (Backup)

If database triggers are not immediately feasible, implement in Django model layer.

**Implementation:**

```python
# inventory/models.py

class StockProduct(models.Model):
    # ... existing fields ...
    
    @property
    def available_quantity(self) -> int:
        """
        Quantity available for storefront allocation.
        Accounts for approved/completed adjustments.
        """
        from inventory.stock_adjustments import StockAdjustment
        
        # Get sum of approved/completed negative adjustments
        adjustments = StockAdjustment.objects.filter(
            stock_product=self,
            status__in=['APPROVED', 'COMPLETED']
        ).aggregate(
            total=models.Sum('quantity')
        )['total'] or 0
        
        return self.quantity + adjustments  # adjustments are negative for losses
    
    @property
    def allocated_quantity(self) -> int:
        """Total quantity allocated to storefronts"""
        from inventory.models import StoreFrontInventory
        
        return StoreFrontInventory.objects.filter(
            stock_product=self
        ).aggregate(
            total=models.Sum('quantity')
        )['total'] or 0
    
    def can_allocate(self, quantity: int) -> tuple[bool, str]:
        """
        Check if quantity can be allocated to storefront.
        Returns (can_allocate, reason)
        """
        available = self.available_quantity
        current_allocated = self.allocated_quantity
        remaining = available - current_allocated
        
        if quantity > remaining:
            return False, (
                f"Insufficient stock available. "
                f"Available: {available}, "
                f"Already allocated: {current_allocated}, "
                f"Remaining: {remaining}, "
                f"Requested: {quantity}"
            )
        
        return True, "OK"


# inventory/stock_adjustments.py

class StockAdjustment(models.Model):
    # ... existing fields ...
    
    def clean(self):
        """Validate adjustment doesn't violate data integrity"""
        super().clean()
        
        if self.status in ['APPROVED', 'COMPLETED'] and self.quantity < 0:
            # For negative adjustments, ensure we don't go below allocated quantity
            stock = self.stock_product
            
            # Calculate what available would be after this adjustment
            other_adjustments = StockAdjustment.objects.filter(
                stock_product=stock,
                status__in=['APPROVED', 'COMPLETED']
            ).exclude(id=self.id).aggregate(
                total=models.Sum('quantity')
            )['total'] or 0
            
            new_available = stock.quantity + other_adjustments + self.quantity
            allocated = stock.allocated_quantity
            
            if new_available < allocated:
                raise ValidationError(
                    f"Cannot approve adjustment. Would reduce stock below allocated quantity. "
                    f"Current: {stock.quantity}, "
                    f"Allocated to stores: {allocated}, "
                    f"Adjustment: {self.quantity}, "
                    f"Resulting available: {new_available}"
                )
    
    def save(self, *args, **kwargs):
        # Run validation
        self.full_clean()
        
        # Auto-apply when approved
        if self.status == 'APPROVED' and self.pk:
            # Check if status just changed to APPROVED
            old_status = StockAdjustment.objects.filter(pk=self.pk).values_list('status', flat=True).first()
            if old_status == 'PENDING':
                # Apply adjustment to stock
                self.stock_product.quantity += self.quantity
                self.stock_product.save()
        
        super().save(*args, **kwargs)


# inventory/views.py (or wherever storefront requests are handled)

@transaction.atomic
def create_storefront_request(stock_product_id, quantity, storefront_id):
    """Create storefront inventory allocation request"""
    stock_product = StockProduct.objects.select_for_update().get(id=stock_product_id)
    
    # Check availability
    can_allocate, reason = stock_product.can_allocate(quantity)
    if not can_allocate:
        raise ValidationError(reason)
    
    # Create allocation
    StoreFrontInventory.objects.create(
        stock_product=stock_product,
        storefront_id=storefront_id,
        quantity=quantity
    )
```

---

## 🔄 Migration Plan

### Phase 1: Audit Current State (Day 1)
```sql
-- Find stock products with integrity issues
SELECT 
    sp.id,
    p.name AS product_name,
    sp.quantity AS recorded_quantity,
    COALESCE(SUM(CASE WHEN sa.quantity < 0 THEN sa.quantity ELSE 0 END), 0) AS total_shrinkage,
    sp.quantity + COALESCE(SUM(CASE WHEN sa.quantity < 0 THEN sa.quantity ELSE 0 END), 0) AS should_be_available,
    COALESCE(SUM(sfi.quantity), 0) AS allocated_to_stores,
    sp.quantity + COALESCE(SUM(CASE WHEN sa.quantity < 0 THEN sa.quantity ELSE 0 END), 0) - COALESCE(SUM(sfi.quantity), 0) AS actual_warehouse_onhand
FROM stock_products sp
JOIN products p ON p.id = sp.product_id
LEFT JOIN stock_adjustments sa ON sa.stock_product_id = sp.id AND sa.status IN ('APPROVED', 'COMPLETED')
LEFT JOIN storefront_inventory sfi ON sfi.stock_product_id = sp.id
GROUP BY sp.id, p.name, sp.quantity
HAVING (sp.quantity + COALESCE(SUM(CASE WHEN sa.quantity < 0 THEN sa.quantity ELSE 0 END), 0)) < COALESCE(SUM(sfi.quantity), 0);
```

### Phase 2: Create Django Migration (Day 1-2)
```bash
python manage.py makemigrations --empty inventory --name add_stock_integrity_constraints
```

Edit the migration file:

```python
# inventory/migrations/XXXX_add_stock_integrity_constraints.py

from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('inventory', 'XXXX_previous_migration'),
    ]

    operations = [
        # Add audit log table
        migrations.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS inventory_audit_log (
                id SERIAL PRIMARY KEY,
                table_name VARCHAR(100) NOT NULL,
                record_id UUID NOT NULL,
                action VARCHAR(50) NOT NULL,
                old_value TEXT,
                new_value TEXT,
                changed_by UUID,
                changed_at TIMESTAMP DEFAULT NOW()
            );
            CREATE INDEX idx_audit_log_record ON inventory_audit_log(table_name, record_id);
            CREATE INDEX idx_audit_log_date ON inventory_audit_log(changed_at DESC);
            """,
            reverse_sql="DROP TABLE IF EXISTS inventory_audit_log;"
        ),
        
        # Add check constraint for adjustments
        migrations.RunSQL(
            sql=open('inventory/sql/triggers/check_adjustment_validity.sql').read(),
            reverse_sql="DROP TRIGGER IF EXISTS validate_adjustment_before_save ON stock_adjustments;"
        ),
        
        # Add trigger for auto-applying adjustments
        migrations.RunSQL(
            sql=open('inventory/sql/triggers/auto_apply_adjustment.sql').read(),
            reverse_sql="DROP TRIGGER IF EXISTS apply_adjustment_on_approval ON stock_adjustments;"
        ),
        
        # Add constraint for storefront allocations
        migrations.RunSQL(
            sql=open('inventory/sql/triggers/check_stock_availability.sql').read(),
            reverse_sql="DROP TRIGGER IF EXISTS ensure_stock_availability ON storefront_inventory;"
        ),
    ]
```

### Phase 3: Update Application Code (Day 2-3)

1. **Update StockProduct model:**
   - Add `available_quantity` property
   - Add `can_allocate()` method
   - Update queries to use available_quantity

2. **Update StockAdjustment model:**
   - Add validation in `clean()` method
   - Auto-apply on approval in `save()` method

3. **Update views/serializers:**
   - Use `available_quantity` instead of `quantity` for allocation checks
   - Update reconciliation endpoint to show adjustments impact

4. **Update frontend documentation:**
   - Clarify that adjustments are immediately reflected
   - Update TypeScript interfaces if needed

### Phase 4: Testing (Day 3-4)

```python
# tests/test_stock_integrity.py

class StockIntegrityTests(TestCase):
    def test_adjustment_reduces_available_quantity(self):
        """Approved adjustment should immediately reduce available quantity"""
        stock = StockProduct.objects.create(product=..., quantity=100)
        
        # Create damage adjustment
        adjustment = StockAdjustment.objects.create(
            stock_product=stock,
            quantity=-10,
            adjustment_type='DAMAGE',
            reason='Test',
            status='PENDING'
        )
        
        # Before approval, full quantity available
        self.assertEqual(stock.available_quantity, 100)
        
        # Approve adjustment
        adjustment.status = 'APPROVED'
        adjustment.save()
        
        # After approval, reduced quantity available
        stock.refresh_from_db()
        self.assertEqual(stock.quantity, 90)
        self.assertEqual(stock.available_quantity, 90)
    
    def test_cannot_allocate_more_than_available(self):
        """Cannot allocate to storefront if exceeds available quantity"""
        stock = StockProduct.objects.create(product=..., quantity=100)
        
        # Damage 20 units
        StockAdjustment.objects.create(
            stock_product=stock,
            quantity=-20,
            status='APPROVED',
            ...
        )
        
        # Should only allow 80 units allocation
        can_allocate, msg = stock.can_allocate(90)
        self.assertFalse(can_allocate)
        self.assertIn('Insufficient stock', msg)
        
        # Should allow 80 units
        can_allocate, msg = stock.can_allocate(80)
        self.assertTrue(can_allocate)
    
    def test_adjustment_cannot_reduce_below_allocated(self):
        """Cannot create adjustment that would reduce stock below allocated"""
        stock = StockProduct.objects.create(product=..., quantity=100)
        
        # Allocate 80 to storefront
        StoreFrontInventory.objects.create(
            stock_product=stock,
            quantity=80,
            ...
        )
        
        # Try to create adjustment for -30 (would leave only 70 available)
        adjustment = StockAdjustment(
            stock_product=stock,
            quantity=-30,
            status='APPROVED',
            ...
        )
        
        with self.assertRaises(ValidationError):
            adjustment.full_clean()
```

### Phase 5: Deployment (Day 5)

1. **Backup database**
2. **Run migration in transaction:**
   ```bash
   BEGIN;
   python manage.py migrate inventory
   -- Verify triggers created
   SELECT * FROM pg_trigger WHERE tgname LIKE '%adjustment%';
   -- Verify no data integrity issues
   [run audit query from Phase 1]
   COMMIT; -- or ROLLBACK if issues found
   ```
3. **Monitor logs for constraint violations**
4. **Update frontend to handle new error messages**

---

## 📊 Impact Assessment

### Data Integrity
- ✅ **Prevents overselling** damaged/stolen stock
- ✅ **Real-time accuracy** in warehouse quantities
- ✅ **Atomic operations** prevent race conditions
- ✅ **Audit trail** for all quantity changes

### Performance
- ✅ **Minimal overhead** - triggers execute in microseconds
- ✅ **Indexed queries** - proper indexes on foreign keys
- ⚠️ **Lock contention** - use `SELECT FOR UPDATE` for allocations

### Business Logic
- ✅ **Enforces reality** - system matches physical inventory
- ✅ **Prevents errors** - can't allocate damaged stock
- ✅ **Clear errors** - descriptive messages when violations occur

---

## 🚀 Immediate Actions Required

### For Backend Team:
1. **Review this document** and approve approach
2. **Create SQL trigger files** in `inventory/sql/triggers/`
3. **Create Django migration** following Phase 2
4. **Update models** with validation logic
5. **Write comprehensive tests** covering all scenarios
6. **Test in staging** environment first

### For Frontend Team:
1. **Be prepared for new error responses:**
   ```json
   {
     "error": "Insufficient stock available. Available: 80, Already allocated: 60, Remaining: 20, Requested: 30"
   }
   ```
2. **Update allocation UI** to show `available_quantity` not `quantity`
3. **Show adjustment impact** in stock details view

### For Operations Team:
1. **Review current adjustments** - identify any pending items
2. **Complete or reject** all pending adjustments before migration
3. **Verify physical counts** match system after migration

---

## 📞 Questions & Concerns

### Q: Will this break existing functionality?
**A:** Potentially yes, if there are existing over-allocations. That's why Phase 1 audit is critical.

### Q: What if we find integrity violations during audit?
**A:** Fix them manually before migration. The triggers will prevent new violations.

### Q: Can we disable triggers temporarily?
**A:** Yes, but NOT RECOMMENDED. Better to fix the root cause.

### Q: What's the performance impact?
**A:** Minimal. Triggers are fast (~0.1ms). Proper indexes are key.

---

## ✅ Success Criteria

- [ ] All stock adjustments auto-apply on approval
- [ ] Cannot allocate more than available quantity
- [ ] Cannot create adjustments that violate integrity
- [ ] Reconciliation endpoint shows correct available quantities
- [ ] All tests passing
- [ ] No existing data integrity violations
- [ ] Frontend handles new error messages
- [ ] Audit log captures all changes

---

**This is a critical data integrity issue that should be prioritized immediately. The current system allows overselling and inventory inaccuracies that can lead to business losses and customer dissatisfaction.**

**Recommended Timeline: 5 days**
- Day 1: Audit + Planning
- Day 2-3: Implementation + Testing
- Day 4: Staging Deployment + Verification
- Day 5: Production Deployment + Monitoring
