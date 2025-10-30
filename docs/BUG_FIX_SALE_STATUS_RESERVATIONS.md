# Bug Fix: Sale Status and Reserved Quantities

## Problem Summary
Reserved quantities were incorrectly including `PENDING` and `PARTIAL` sales in addition to `DRAFT` sales, causing inventory reports to show inflated reserved quantities that never cleared.

## Root Cause Analysis

### The Sale Status Lifecycle
1. **DRAFT** - Sale in cart, stock NOT committed (reservation only)
2. **PENDING** - Sale completed, stock COMMITTED, awaiting payment (credit sales)
3. **PARTIAL** - Sale completed, stock COMMITTED, partially paid
4. **COMPLETED** - Sale completed, stock COMMITTED, fully paid
5. **CANCELLED** - Sale cancelled, stock released
6. **REFUNDED** - Sale refunded, stock returned

### The Bug
Reserved quantity calculations were querying:
```python
SaleItem.objects.filter(
    sale__status__in=['DRAFT', 'PENDING']  # ❌ WRONG
)
```

**The Problem:**
- When `complete_sale()` is called, it:
  1. Calls `commit_stock()` - **deducts inventory from warehouse**
  2. Sets status to `PENDING` (if credit sale) or `COMPLETED` (if fully paid)
  3. Calls `release_reservations(delete=True)` - clears reservation records

- However, reports were still counting `PENDING` sales as reservations
- This caused **double-counting**: inventory already reduced + still showing as reserved

### Evidence from Code

**sales/models.py** (line 877-890):
```python
def complete_sale(self):
    # Commit stock (reduces warehouse inventory)
    self.commit_stock()
    
    # Release reservations
    self.release_reservations(delete=True)
    
    # Update status based on payment
    if self.amount_due == Decimal('0.00'):
        self.status = 'COMPLETED'
    elif self.amount_paid > Decimal('0.00'):
        self.status = 'PARTIAL'
    else:
        self.status = 'PENDING'  # ← Stock already committed!
```

**sales/views.py** (line 680):
```python
def _complete_credit_sale(self, sale, request, data):
    # Commit stock
    sale.commit_stock()
    
    # Release reservations
    sale.release_reservations(delete=True)
    
    # Set status to PENDING (awaiting payment)
    sale.status = 'PENDING'  # ← Inventory already deducted
```

## User Impact
> "DRAFT and PENDING figures seem to stick around forever even when sales transactions are completed"

**Example Scenario:**
1. Customer places order on credit for 100 units (status: DRAFT, reserved: 100)
2. Order is completed/fulfilled (status: PENDING, inventory reduced by 100)
3. Report shows:
   - Warehouse: 900 units (1000 - 100 committed)
   - Reserved: 100 units (incorrectly counting PENDING sale)
   - Available: 800 units (900 - 100 = **WRONG**)
4. Actual available should be 900 units (PENDING sale already committed)

**Impact:**
- Inventory appears unavailable when it's actually sellable
- Reserved quantities never clear for credit sales until payment received
- Frontend shows incorrect "available to sell" quantities
- Business loses sales due to false stock-out indicators

## The Fix

### Changed Files
1. **reports/views/inventory_reports.py** (line 272-277)
2. **inventory/views.py** (line 872-875)
3. **scripts/update_build_stock_levels.py** (line 53-56)

### Before (Incorrect)
```python
# ❌ WRONG - Counts committed sales as reservations
reservation_data = SaleItem.objects.filter(
    product_id__in=all_product_ids,
    sale__status__in=['DRAFT', 'PENDING']
).values('product_id').annotate(
    total_reserved=Sum('quantity')
)
```

### After (Correct)
```python
# ✅ CORRECT - Only DRAFT sales are true reservations
reservation_data = SaleItem.objects.filter(
    product_id__in=all_product_ids,
    sale__status='DRAFT'  # Only uncommitted cart items
).values('product_id').annotate(
    total_reserved=Sum('quantity')
)
```

## Why This is Correct

### Sale Status = Stock State Mapping
| Status | Stock State | Reservation State | Should Count as Reserved? |
|--------|-------------|-------------------|---------------------------|
| DRAFT | NOT committed | Active reservation | ✅ YES |
| PENDING | COMMITTED | Released (deleted) | ❌ NO |
| PARTIAL | COMMITTED | Released (deleted) | ❌ NO |
| COMPLETED | COMMITTED | Released (deleted) | ❌ NO |
| CANCELLED | Released back | Cancelled | ❌ NO |
| REFUNDED | Returned | Cancelled | ❌ NO |

**Key Insight:** 
Once `complete_sale()` is called:
1. Stock is committed (inventory reduced)
2. Reservations are released (deleted from StoreFrontInventory)
3. Status changes from DRAFT → (PENDING|PARTIAL|COMPLETED)

Therefore, only DRAFT sales should count as reservations.

## Testing Strategy

### 1. Credit Sale Flow
```python
# Create credit sale
sale = Sale.objects.create(
    payment_type='CREDIT',
    status='DRAFT',
    total_amount=100
)
SaleItem.objects.create(sale=sale, product=product, quantity=10)

# Check DRAFT reservation
assert get_reserved_qty(product) == 10  # ✅ Counts

# Complete sale (commits stock, sets status=PENDING)
sale.complete_sale()

# Check PENDING reservation
assert get_reserved_qty(product) == 0  # ✅ No longer counts
assert product.stock.quantity == 90  # ✅ Inventory reduced
```

### 2. Payment Sale Flow
```python
# Create payment sale
sale = Sale.objects.create(
    payment_type='CASH',
    status='DRAFT',
    total_amount=100
)
SaleItem.objects.create(sale=sale, product=product, quantity=10)

# Check DRAFT reservation
assert get_reserved_qty(product) == 10  # ✅ Counts

# Complete sale (commits stock, sets status=COMPLETED)
sale.complete_sale()

# Check COMPLETED reservation
assert get_reserved_qty(product) == 0  # ✅ No longer counts
assert product.stock.quantity == 90  # ✅ Inventory reduced
```

### 3. Stock Levels Report Accuracy
```python
# Given: 1000 units in stock, 100 reserved (DRAFT), 50 committed (PENDING)
stock.quantity = 950  # 1000 - 50 committed
reserved = 100  # Only DRAFT sales

# Report should show:
assert report['total_quantity'] == 950  # Physical inventory
assert report['total_reserved'] == 100  # Only DRAFT reservations
assert report['total_available'] == 850  # 950 - 100 = 850
# NOT 800 (which would be 950 - 100 - 50 double-counting)
```

## Deployment Plan

### Pre-Deployment Checks
```bash
# 1. Run Django checks
python manage.py check

# 2. Run inventory tests
python -m pytest tests/test_inventory_reports.py -v

# 3. Verify no syntax errors
python -m py_compile reports/views/inventory_reports.py
python -m py_compile inventory/views.py
python -m py_compile scripts/update_build_stock_levels.py
```

### Deployment Steps
```bash
# 1. Backup production database
ssh production
pg_dump -U postgres pos_db > backup_before_reservation_fix.sql

# 2. Pull latest changes
cd /var/www/backend
git pull origin main

# 3. Restart services
sudo systemctl restart gunicorn
sudo systemctl restart celery

# 4. Verify fix
curl -X GET "https://api.yourdomain.com/reports/inventory/stock-levels/" \
  -H "Authorization: Bearer $TOKEN"

# Expected: Reserved quantities should drop significantly
```

### Post-Deployment Validation
1. **Check reserved quantities** - Should show only DRAFT sales
2. **Verify credit sales** - PENDING sales should NOT inflate reservations
3. **Monitor performance** - Single status filter vs. __in lookup (faster)
4. **Test frontend** - Stock availability should now be accurate

## Performance Impact

### Query Optimization
**Before:**
```python
sale__status__in=['DRAFT', 'PENDING']  # Requires OR condition in SQL
```

**After:**
```python
sale__status='DRAFT'  # Simple equality check (faster)
```

**Expected Performance:**
- Faster query execution (equality vs. IN clause)
- More accurate results (no PENDING sales to aggregate)
- Reduced database load (fewer rows to scan)

## Related Issues
- [BUG_FIX_STOCK_LEVELS_RESERVED_CALCULATION.md](./BUG_FIX_STOCK_LEVELS_RESERVED_CALCULATION.md) - Proportional distribution fix
- [BUG_FIX_TRANSFER_TRANSACTION_ROLLBACK.md](./BUG_FIX_TRANSFER_TRANSACTION_ROLLBACK.md) - Transaction rollback fix
- [PRODUCTION_CLEANUP_GUIDE.md](./PRODUCTION_CLEANUP_GUIDE.md) - Data cleanup procedures

## Rollback Plan
If issues arise:
```bash
# Revert commit
git revert HEAD
git push origin main

# Restart services
sudo systemctl restart gunicorn

# Re-deploy previous version
```

## Files Changed
- `reports/views/inventory_reports.py` - Stock levels report calculation
- `inventory/views.py` - Stock detail API reserved quantity
- `scripts/update_build_stock_levels.py` - Build stock levels script

## Commit Message
```
fix: Only count DRAFT sales as reservations, not PENDING

PENDING/PARTIAL/COMPLETED sales have already committed stock.
Including them in reserved quantities causes double-counting.

Changes:
- reports: Only query DRAFT sales for reservations
- inventory: Only count DRAFT sales in stock detail API
- scripts: Update build script to match new logic

Fixes: Reserved quantities inflated by committed sales
Impact: Stock availability now accurate for credit sales
```
