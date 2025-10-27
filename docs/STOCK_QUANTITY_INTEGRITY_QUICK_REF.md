# Stock Quantity Integrity - Quick Reference

## The Golden Rule

```
StockProduct.quantity = INITIAL INTAKE (never changes after movements)
Available Stock = CALCULATED (intake + adjustments - transfers - sales)
```

## What Changed

### 1. `inventory/signals.py` (NEW)
- **Prevents** manual editing of `StockProduct.quantity` after movements
- **Validates** adjustments won't cause negative stock
- **Validates** transfers have sufficient available stock

### 2. `inventory/stock_adjustments.py`
- **Removed** quantity modification from `complete()` method
- Adjustments now **only** track changes, don't modify intake quantity

### 3. `inventory/apps.py`
- **Registered** signals on app startup

## What This Means

| Action | Before | After |
|--------|--------|-------|
| Create stock intake | Sets `quantity=100` | Same (no change) |
| Fix intake typo (no movements) | Edit `quantity=105` | Same (allowed before movements) |
| Fix intake typo (after movements) | Edit `quantity=105` ✅ | ❌ **BLOCKED** - use adjustment instead |
| Record damage | Creates adjustment, modifies `quantity` ❌ | Creates adjustment, **NO quantity change** ✅ |
| Check available stock | Read `quantity` ❌ | **Calculate** from intake + adjustments - transfers - sales ✅ |

## Quick Actions

### Check if quantity can be edited:
```python
stock = StockProduct.objects.get(pk=id)

# Has movements?
has_adjustments = stock.adjustments.filter(status='COMPLETED').exists()
has_transfers = StoreFrontInventory.objects.filter(product=stock.product, quantity__gt=0).exists()
has_sales = SaleItem.objects.filter(product=stock.product, sale__status='COMPLETED').exists()

if has_adjustments or has_transfers or has_sales:
    print("❌ Quantity is LOCKED - use adjustment to fix")
else:
    print("✅ Quantity can be edited (no movements yet)")
```

### Calculate available stock:
```python
available = (
    stock.quantity +  # Initial intake
    sum(stock.adjustments.filter(status='COMPLETED').values_list('quantity', flat=True)) -
    sum(StoreFrontInventory.objects.filter(product=stock.product).values_list('quantity', flat=True)) -
    sum(SaleItem.objects.filter(product=stock.product, sale__status='COMPLETED').values_list('quantity', flat=True))
)
```

### Fix "wrong quantity at intake":
```python
# If NO movements occurred yet:
stock.quantity = correct_amount
stock.save()  # ✅ Works

# If movements occurred:
# Create correction adjustment instead:
adjustment = StockAdjustment.objects.create(
    stock_product=stock,
    adjustment_type='CORRECTION_INCREASE',  # or CORRECTION
    quantity=difference,  # +10 or -10
    reason="Correcting intake error: should have been X not Y"
)
adjustment.status = 'APPROVED'
adjustment.save()
adjustment.complete()
```

## ELEC-0007 Status

**RESOLVED ✅**

- Showing 46 units in warehouse is **CORRECT** (that's the initial intake)
- Available = 46 + 2 (adjustments) - 43 (transfers) = **5 units** (correct!)
- The confusion was thinking quantity should have been updated
- Now we understand: quantity = intake (never changes), availability = calculated

## Files to Update

Still need to update reconciliation endpoints to use **calculated availability** instead of reading `quantity` directly.

See: `STOCK_QUANTITY_INTEGRITY_IMPLEMENTATION.md` for full details.
