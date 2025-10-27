# Stock Adjustment Data Integrity - Quick Reference (REVISED)

**🚨 URGENT ISSUE: Stock adjustments not reflected in availability calculations**

**✅ SOLUTION: Calculate availability dynamically WITHOUT modifying stock_product.quantity**

---

## ⚡ Critical Principle

### Single Source of Truth: `stock_product.quantity`

```
stock_product.quantity = Recorded Batch Size
✓ ONLY modified by explicit user action (CRUD edit, physical count)
✗ NEVER modified by adjustments, triggers, or automation

Available Quantity = CALCULATED VALUE
✓ Formula: stock_product.quantity + SUM(approved_adjustments)
✓ Computed at read time
✗ NEVER stored or cached in stock_product.quantity
```

---

## The Problem

```
CURRENT STATE (BROKEN):
Warehouse receives: 100 units (stock_product.quantity = 100)
Damage adjustment: -10 units (APPROVED)
Storefront requests: 95 units

❌ System allows transfer (checks against quantity = 100)
✅ Should reject (available = 100 + (-10) = 90)

CRITICAL: stock_product.quantity must STAY 100 (single source of truth)
```

---

## The Solution (REVISED)

### Calculate, Don't Mutate

**Database-Level Enforcement:**

1. **`audit_adjustment_approval`** - Logs approvals WITHOUT modifying quantity
2. **`check_adjustment_validity`** - Validates using CALCULATED availability  
3. **`check_stock_transfer_availability`** - Prevents over-allocation using CALCULATION

**Application-Level:**

```python
@property
def available_quantity(self) -> int:
    """CALCULATE - never modifies self.quantity"""
    adjustments = StockAdjustment.objects.filter(
        stock_product=self,
        status__in=['APPROVED', 'COMPLETED']
    ).aggregate(Sum('quantity'))['total'] or 0
    
    return self.quantity + adjustments  # quantity unchanged!
```

---

## Key Changes (REVISED)

### ❌ WRONG (Original Approach)
```python
# Trigger modifies quantity directly
adjustment.status = 'APPROVED'
stock.quantity += adjustment.quantity  # ❌ Breaks single source of truth!
stock.save()
```

### ✅ CORRECT (Revised Approach)
```python
# Trigger does NOT modify quantity
adjustment.status = 'APPROVED'
# stock.quantity stays unchanged ✓

# Calculate available dynamically
available = stock.quantity + sum(approved_adjustments)  # ✓
```

---

## Files Updated

### Documentation
- `docs/CRITICAL_STOCK_ADJUSTMENT_INTEGRITY_REVISED.md` - Complete revised guide
- `docs/STOCK_INTEGRITY_QUICK_REF.md` - This document (revised)

### SQL Triggers (PostgreSQL) - REVISED
- `inventory/sql/triggers/audit_adjustment_approval.sql` ✓ No quantity mutation
- `inventory/sql/triggers/check_adjustment_validity.sql` ✓ Uses calculation
- `inventory/sql/triggers/check_stock_availability.sql` ✓ Uses calculation
- `inventory/sql/triggers/create_audit_log.sql` (unchanged)

---

## Data Flow (REVISED)

```
RECEIVING: stock_product.quantity = 100 ✓

ADJUSTMENT APPROVED: 
  stock_product.quantity = 100 ✓ (UNCHANGED!)
  adjustment.quantity = -10 ✓ (stored separately)

CALCULATE AVAILABILITY:
  available = 100 + (-10) = 90 ✓ (computed on read)

TRANSFER REQUEST (90 units):
  Check: 90 <= 90? ✓ ALLOWED
  stock_product.quantity = 100 ✓ (STILL UNCHANGED!)

WAREHOUSE ON-HAND:
  Recorded: 100
  Adjustments: -10  
  Available: 90
  Allocated: 90
  Remaining: 0
```

---

## Error Examples (REVISED)

### Insufficient Available Stock
```json
{
  "error": "Stock Availability Error: Insufficient stock available for transfer. Product: 'iPhone 13' at warehouse 'Main'. Recorded Batch Size: 100, Approved Adjustments: -10, Available: 90, Already Allocated: 0, Remaining: 90, Requested: 95"
}
```

### Invalid Adjustment
```json
{
  "error": "Stock Integrity Violation: Adjustment would reduce stock below allocated quantity. Product: 'iPhone 13', Recorded: 100, Current adjustments: -5, This adjustment: -20, Resulting available: 75, Already allocated: 80"
}
```

---

## Testing Checklist (REVISED)

- [ ] `stock_product.quantity` NEVER modified by adjustments ✓
- [ ] Available calculated as: recorded + SUM(approved_adjustments) ✓
- [ ] Cannot allocate more than calculated available
- [ ] Cannot create adjustments that reduce available below allocated
- [ ] Audit log tracks approvals, NOT quantity mutations
- [ ] Reconciliation shows both recorded AND available
- [ ] Frontend displays both values clearly

---

## Implementation Phases

| Phase | Tasks | Status |
|-------|-------|--------|
| **Day 1** | Audit data, review approach | ⏳ Pending |
| **Day 2-3** | Create migration, update models | ⏳ Pending |
| **Day 4** | Staging deployment, testing | ⏳ Pending |
| **Day 5** | Production deployment, monitoring | ⏳ Pending |

---

## Next Steps

1. **Review** `docs/CRITICAL_STOCK_ADJUSTMENT_INTEGRITY_REVISED.md`
2. **Verify** SQL triggers preserve single source of truth
3. **Create migration** using revised approach
4. **Add model properties** (calculation only, no mutation)
5. **Update views** to use available_quantity property
6. **Test thoroughly** - verify quantity NEVER changes automatically

---

## Critical Success Criteria

✅ `stock_product.quantity` is **SINGLE SOURCE OF TRUTH**  
✅ Available quantity is **CALCULATED**, never stored  
✅ Adjustments stored separately, summed dynamically  
✅ Triggers enforce constraints using calculations  
✅ Data integrity maintained at database level  
✅ No automatic mutations of recorded quantity  

---

**READ THE FULL REVISED DOCUMENTATION:**
`docs/CRITICAL_STOCK_ADJUSTMENT_INTEGRITY_REVISED.md`

**This approach preserves architectural integrity while enforcing data consistency.**
