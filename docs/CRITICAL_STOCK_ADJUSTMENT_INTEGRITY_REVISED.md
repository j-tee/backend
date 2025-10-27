# REVISED: Stock Adjustment Data Integrity - Preserving Single Source of Truth

**Date:** 2025-10-09  
**Priority:** 🔴 URGENT - Data Integrity Issue  
**Status:** 🚧 Solution Revised - Preserves Architectural Integrity

---

## 🎯 Critical Architectural Principle

### Single Source of Truth: `stock_product.quantity`

**THIS FIELD MUST NEVER BE MODIFIED EXCEPT BY EXPLICIT USER ACTION**

```
stock_product.quantity = Recorded Batch Size
- ✅ Set when stock is received from supplier
- ✅ Modified only through direct user edit (CRUD operations)
- ✅ Updated through physical count corrections
- ❌ NEVER modified by adjustments, transfers, or calculations
- ❌ NEVER modified by triggers or automated processes
```

**Why This Matters:**
- `stock_product.quantity` is the foundation for ALL stock calculations
- Modifying it mid-stream would corrupt the data integrity
- Stock Details Stats depend on this being the reliable baseline
- Breaking single source of truth creates cascading data errors

---

## 🚨 Problem Statement (Unchanged)

### Current Issue
Stock adjustments (shrinkage, damage, corrections) are **not automatically considered** in availability calculations, leading to:

1. **Recorded Batch Size** = `stock_product.quantity` (immutable except by user)
2. **Stock Adjustments** = Damage, theft, corrections (±)
3. **Available Quantity** = Should be `recorded + SUM(adjustments)` **WITHOUT modifying recorded**

**Critical Scenario:**
```
Recorded Batch: 100 units (stock_product.quantity = 100)
Damage Adjustment: -10 units (APPROVED)
Storefront Request: 95 units

Current System: ✅ Allows (checking against 100)
Correct System: ❌ Should reject (available = 100 + (-10) = 90)

IMPORTANT: stock_product.quantity REMAINS 100 throughout
```

---

## ✅ Revised Solution: Calculate, Don't Mutate

### Core Principle

**CALCULATE** available quantity dynamically, **NEVER MUTATE** the recorded quantity.

```sql
-- Available quantity calculation (done at read time)
available_quantity = stock_product.quantity + SUM(approved_adjustments.quantity)

-- Example:
Recorded: 100 (stock_product.quantity = 100, unchanged)
Damage: -10 (stock_adjustment, approved)
Found: +5 (stock_adjustment, approved)
Available: 100 + (-10) + 5 = 95

-- stock_product.quantity STILL = 100 (single source of truth preserved)
```

---

## 🔧 Implementation Strategy

### Option 1: Database-Level Constraints with Calculated Availability (RECOMMENDED)

Use PostgreSQL triggers to **enforce constraints** based on **calculated availability** WITHOUT modifying `stock_product.quantity`.

#### 3 Core Triggers:

**1. Audit Adjustment Approval** (REVISED)
```sql
-- Logs adjustment approvals WITHOUT modifying stock_product.quantity
-- Preserves single source of truth
CREATE TRIGGER audit_adjustment_on_approval
    AFTER UPDATE ON stock_adjustments
    EXECUTE FUNCTION audit_adjustment_approval();
```

**2. Validate Adjustment** (UNCHANGED)
```sql
-- Prevents adjustments that would make available < allocated
-- Calculates: available = recorded + SUM(adjustments)
CREATE TRIGGER validate_adjustment_before_save
    BEFORE INSERT OR UPDATE ON stock_adjustments
    EXECUTE FUNCTION check_adjustment_validity();
```

**3. Check Transfer Availability** (REVISED)
```sql
-- Prevents transfers exceeding calculated available quantity
-- Uses: available = stock_product.quantity + SUM(approved_adjustments)
CREATE TRIGGER ensure_stock_availability
    BEFORE INSERT OR UPDATE ON storefront_inventory
    EXECUTE FUNCTION check_stock_transfer_availability();
```

---

### Option 2: Application-Level with Property Methods (Recommended Alongside)

Implement `available_quantity` as a **calculated property** in Django models.

```python
# inventory/models.py

class StockProduct(models.Model):
    # ... existing fields ...
    quantity = models.PositiveIntegerField()  # SINGLE SOURCE OF TRUTH
    
    @property
    def available_quantity(self) -> int:
        """
        Calculate available quantity dynamically.
        NEVER modifies self.quantity.
        
        Formula: recorded + SUM(approved_adjustments)
        """
        from inventory.stock_adjustments import StockAdjustment
        
        adjustments_total = StockAdjustment.objects.filter(
            stock_product=self,
            status__in=['APPROVED', 'COMPLETED']
        ).aggregate(
            total=models.Sum('quantity')
        )['total'] or 0
        
        return self.quantity + adjustments_total
    
    @property
    def allocated_quantity(self) -> int:
        """Total quantity allocated to storefronts"""
        from inventory.models import StoreFrontInventory
        
        return StoreFrontInventory.objects.filter(
            stock_product=self
        ).aggregate(
            total=models.Sum('quantity')
        )['total'] or 0
    
    @property
    def warehouse_available(self) -> int:
        """
        Quantity available in warehouse for allocation.
        This is what matters for transfer requests.
        """
        return self.available_quantity - self.allocated_quantity
    
    def can_allocate(self, quantity: int) -> tuple[bool, str]:
        """
        Check if quantity can be allocated to storefront.
        Returns (can_allocate, reason)
        """
        available = self.available_quantity
        allocated = self.allocated_quantity
        warehouse_available = available - allocated
        
        if quantity > warehouse_available:
            return False, (
                f"Insufficient stock available. "
                f"Recorded: {self.quantity}, "
                f"Adjustments: {self.available_quantity - self.quantity}, "
                f"Available: {available}, "
                f"Already allocated: {allocated}, "
                f"Warehouse available: {warehouse_available}, "
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
            # For negative adjustments, ensure available won't go below allocated
            stock = self.stock_product
            
            # Calculate what available would be after this adjustment
            other_adjustments = StockAdjustment.objects.filter(
                stock_product=stock,
                status__in=['APPROVED', 'COMPLETED']
            ).exclude(id=self.id).aggregate(
                total=models.Sum('quantity')
            )['total'] or 0
            
            # Calculate new available (WITHOUT modifying stock.quantity)
            new_available = stock.quantity + other_adjustments + self.quantity
            allocated = stock.allocated_quantity
            
            if new_available < allocated:
                raise ValidationError(
                    f"Cannot approve adjustment. Would reduce available stock below allocated quantity. "
                    f"Recorded: {stock.quantity}, "
                    f"Current adjustments: {other_adjustments}, "
                    f"This adjustment: {self.quantity}, "
                    f"Resulting available: {new_available}, "
                    f"Already allocated: {allocated}"
                )
            
            if new_available < 0:
                raise ValidationError(
                    f"Cannot approve adjustment. Would make available quantity negative. "
                    f"Recorded: {stock.quantity}, "
                    f"Adjustments total: {other_adjustments + self.quantity}"
                )
```

---

## 📊 Data Flow Diagram

```
┌─────────────────────────────────────────────────────────┐
│ STOCK RECEIVING (User Action)                          │
│ stock_product.quantity = 100                            │
│ ✓ Single source of truth set                           │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STOCK ADJUSTMENTS (Approved)                            │
│ - Damage: -10 units                                     │
│ - Found: +5 units                                       │
│ ✓ stock_product.quantity REMAINS 100                    │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ AVAILABILITY CALCULATION (Dynamic)                      │
│ available = 100 + (-10) + 5 = 95                        │
│ ✓ Calculated at read time                               │
│ ✓ stock_product.quantity STILL 100                      │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ STOREFRONT TRANSFER REQUEST                             │
│ Requested: 90 units                                     │
│ Check: 90 <= 95? ✓ ALLOWED                             │
│ ✓ stock_product.quantity STILL 100                      │
└─────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ RECONCILIATION VIEW                                     │
│ Recorded: 100 (stock_product.quantity)                  │
│ Adjustments: -5 (sum of approved)                       │
│ Available: 95 (calculated)                              │
│ Allocated: 90 (storefront transfers)                    │
│ Warehouse: 5 (available - allocated)                    │
└─────────────────────────────────────────────────────────┘
```

---

## 🔄 Reconciliation Endpoint Update

The stock reconciliation endpoint already uses the correct approach:

```python
# inventory/views.py - ProductViewSet.stock_reconciliation

# Warehouse calculation (already correct!)
recorded_quantity = StockProduct.objects.filter(...).aggregate(
    total=Sum('quantity')
)['total'] or 0

# Get adjustments
shrinkage = StockAdjustment.objects.filter(
    ..., quantity__lt=0
).aggregate(total=Sum('quantity'))['total'] or 0

corrections = StockAdjustment.objects.filter(
    ..., quantity__gt=0
).aggregate(total=Sum('quantity'))['total'] or 0

# Calculate available (doesn't modify recorded!)
warehouse_available = recorded_quantity + shrinkage + corrections - storefront_total
```

**This is already preserving single source of truth! ✅**

---

## 📝 Updated Migration Plan

### Phase 1: Audit Current State (Day 1)
```sql
-- Find stock products where available < allocated
WITH stock_available AS (
    SELECT 
        sp.id,
        sp.quantity AS recorded,
        COALESCE(SUM(sa.quantity), 0) AS adjustments,
        sp.quantity + COALESCE(SUM(sa.quantity), 0) AS available
    FROM stock_products sp
    LEFT JOIN stock_adjustments sa ON sa.stock_product_id = sp.id 
        AND sa.status IN ('APPROVED', 'COMPLETED')
    GROUP BY sp.id, sp.quantity
),
stock_allocated AS (
    SELECT 
        stock_product_id,
        COALESCE(SUM(quantity), 0) AS allocated
    FROM storefront_inventory
    GROUP BY stock_product_id
)
SELECT 
    p.name,
    sa.recorded,
    sa.adjustments,
    sa.available,
    COALESCE(sal.allocated, 0) AS allocated,
    sa.available - COALESCE(sal.allocated, 0) AS warehouse_available
FROM stock_available sa
JOIN stock_products sp ON sp.id = sa.id
JOIN products p ON p.id = sp.product_id
LEFT JOIN stock_allocated sal ON sal.stock_product_id = sa.id
WHERE sa.available < COALESCE(sal.allocated, 0);
```

### Phase 2: Create Django Migration (Day 1-2)
```python
# inventory/migrations/XXXX_add_stock_integrity_constraints.py

from django.db import migrations
import os

class Migration(migrations.Migration):
    dependencies = [
        ('inventory', 'XXXX_previous_migration'),
    ]

    operations = [
        # Add audit log table
        migrations.RunSQL(
            sql=open('inventory/sql/triggers/create_audit_log.sql').read(),
            reverse_sql="DROP TABLE IF EXISTS inventory_audit_log CASCADE;"
        ),
        
        # Add constraint for adjustments
        migrations.RunSQL(
            sql=open('inventory/sql/triggers/check_adjustment_validity.sql').read(),
            reverse_sql="DROP TRIGGER IF EXISTS validate_adjustment_before_save ON stock_adjustments CASCADE;"
        ),
        
        # Add audit trigger (REVISED - no mutation)
        migrations.RunSQL(
            sql=open('inventory/sql/triggers/auto_apply_adjustment.sql').read(),
            reverse_sql="DROP TRIGGER IF EXISTS audit_adjustment_on_approval ON stock_adjustments CASCADE;"
        ),
        
        # Add constraint for storefront allocations (REVISED - uses calculation)
        migrations.RunSQL(
            sql=open('inventory/sql/triggers/check_stock_availability.sql').read(),
            reverse_sql="DROP TRIGGER IF EXISTS ensure_stock_availability ON storefront_inventory CASCADE;"
        ),
    ]
```

### Phase 3: Update Application Code (Day 2-3)

**Update StockProduct model:**
- Add `available_quantity` property (calculation only)
- Add `warehouse_available` property
- Add `can_allocate()` method
- **DO NOT add any .save() hooks that modify quantity**

**Update views/serializers:**
- Use `available_quantity` for allocation checks
- Display both `recorded` and `available` in responses
- Clear error messages referencing both values

**Update reconciliation endpoint:**
- Already correct! Just verify calculations
- Ensure frontend docs explain the difference

---

## ✅ Success Criteria (Updated)

- [ ] `stock_product.quantity` **NEVER** modified by adjustments
- [ ] Available quantity **calculated dynamically** from recorded + adjustments
- [ ] Triggers prevent over-allocation using **calculated** availability
- [ ] Audit log tracks adjustment approvals (not quantity mutations)
- [ ] All tests verify single source of truth preserved
- [ ] Reconciliation endpoint shows both recorded and available
- [ ] Frontend displays both values clearly

---

## 🎯 Key Differences from Original Approach

| Aspect | ❌ Original (Wrong) | ✅ Revised (Correct) |
|--------|-------------------|---------------------|
| `stock_product.quantity` | Modified by trigger | Never modified automatically |
| Adjustments | Applied to quantity field | Stored separately, summed for calculation |
| Available calculation | Direct field read | Dynamic: recorded + SUM(adjustments) |
| Single source of truth | Violated | Preserved |
| Data integrity | Compromised | Maintained |
| Audit trail | Quantity mutations | Adjustment approvals only |

---

## 📊 Example Scenarios

### Scenario 1: Damage After Receiving
```
Day 1: Receive 100 units
  stock_product.quantity = 100 ✓

Day 2: Approve damage adjustment -10
  stock_product.quantity = 100 ✓ (unchanged!)
  adjustment.quantity = -10
  available = 100 + (-10) = 90

Day 3: Request 95 for storefront
  Check: 95 <= 90? ❌ REJECTED
  Error: "Available: 90 (Recorded: 100, Adjustments: -10)"
```

### Scenario 2: Found Inventory
```
Initial: 100 units recorded
  stock_product.quantity = 100

Approve: Found +5 units
  stock_product.quantity = 100 ✓ (unchanged!)
  adjustment.quantity = +5
  available = 100 + 5 = 105

Request: 103 for storefront
  Check: 103 <= 105? ✓ ALLOWED
```

### Scenario 3: Physical Count Correction
```
System: 100 units (stock_product.quantity = 100)
Physical count: Actually 95 units

USER ACTION REQUIRED:
  Edit stock_product.quantity = 95 (via CRUD)
  ✓ This is the ONLY way to modify quantity
  
Create adjustment record for audit:
  Type: CORRECTION
  Quantity: -5
  Status: COMPLETED (for audit trail)
```

---

## 🚀 Immediate Actions Required

### For Backend Team:
1. ✅ **Review revised approach** - ensures single source of truth
2. ✅ **Use provided SQL trigger files** - already updated
3. ✅ **Create migration** with revised triggers
4. ✅ **Add model properties** for calculated values
5. ✅ **Never add hooks** that modify quantity automatically
6. ✅ **Test thoroughly** - verify quantity never mutates

### For Frontend Team:
1. **Display both values:**
   ```typescript
   interface StockDetails {
     recorded_quantity: number;    // stock_product.quantity
     adjustments_total: number;    // sum of adjustments
     available_quantity: number;   // recorded + adjustments
     allocated_quantity: number;   // sum of transfers
     warehouse_available: number;  // available - allocated
   }
   ```

2. **Clarify in UI:**
   ```
   Recorded Batch Size: 100 units (original receipt)
   Adjustments: -10 units (5 damage, -15 theft, +10 found)
   Available: 90 units (recorded + adjustments)
   Allocated to Stores: 80 units
   Warehouse Available: 10 units (ready for new transfers)
   ```

---

## 📞 Questions & Concerns

### Q: How do we handle physical count corrections?
**A:** Physical count corrections require **explicit user action** to modify `stock_product.quantity`. Create a UI for physical count with:
1. Display current `quantity`
2. User enters actual counted value
3. System calculates difference
4. User confirms update
5. `stock_product.quantity` updated via CRUD
6. Adjustment record created for audit trail

### Q: Won't calculating on every read be slow?
**A:** No, with proper indexes the SUM() query is very fast (~1ms). We can add caching if needed, but **never cache by modifying the source field**.

### Q: What about the "complete" action on adjustments?
**A:** The "complete" action can remain for workflow purposes, but it should NOT modify `stock_product.quantity`. It just changes the adjustment status for audit purposes.

---

**This revised approach preserves the critical architectural principle of single source of truth while still enforcing data integrity constraints at the database level.**

**Timeline: 5 days (unchanged)**
**Priority: URGENT (unchanged)**
**Risk: MITIGATED (by preserving single source of truth)**
