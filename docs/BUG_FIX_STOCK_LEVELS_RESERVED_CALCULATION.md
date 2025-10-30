# 🔧 Stock Levels Reserved Quantity Bug Fix

## Issue Summary

**Bug Location:** `reports/views/inventory_reports.py` - Line 293-296  
**Severity:** HIGH - Data Integrity Issue  
**Impact:** Incorrect stock availability calculations in Stock Levels Report

## Root Cause

The `reserved_qty` calculation queries **ALL reservations for a product across the entire system**, then incorrectly applies that same total to **EACH individual warehouse location**.

### Buggy Code (Current):

```python
# Line 293-296 - WRONG!
reserved_qty = SaleItem.objects.filter(
    product=stock.product,
    sale__status__in=['DRAFT', 'PENDING']
).aggregate(total=Sum('quantity'))['total'] or 0
```

### Problem Breakdown:

Given Samsung TV with:
- Location A: 150 units
- Location B: 334 units  
- Total reservations (system-wide): 323 units

**What happens:**

| Iteration | Warehouse | Query Result | Reserved Assigned | Available Calc | Result |
|-----------|-----------|--------------|-------------------|----------------|--------|
| 1 | Location A (150 units) | 323 (global) | 323 | max(0, 150-323) = 0 | ✗ WRONG |
| 2 | Location B (334 units) | 323 (global) | 323 | max(0, 334-323) = 11 | ✗ WRONG |

**Total Available:** 0 + 11 = **11 units** (Should be 174!)

**Frontend sees:**
- `total_available`: 174 (from different calculation path)
- `SUM(location.reserved)`: 323 + 323 = **646 units** (double-counted!)
- `total_quantity`: 484
- Math doesn't add up: 174 + 646 ≠ 484

## The Fix

### Option 1: Per-Warehouse Reservations (Recommended if supported)

If your `SaleItem` or `Sale` model has a warehouse reference:

```python
# Get reserved quantity for THIS specific warehouse
reserved_qty = SaleItem.objects.filter(
    product=stock.product,
    sale__status__in=['DRAFT', 'PENDING'],
    sale__warehouse=stock.warehouse  # or wherever warehouse is tracked
).aggregate(total=Sum('quantity'))['total'] or 0
```

### Option 2: Storefront-Based Distribution

If reservations are tracked at storefront level, map storefronts to warehouses:

```python
# Get storefronts served by this warehouse
from inventory.models import BusinessStoreFront, StoreFront

storefronts_for_warehouse = StoreFront.objects.filter(
    # Add your logic to link storefronts to warehouses
    # This depends on your business model
)

reserved_qty = SaleItem.objects.filter(
    product=stock.product,
    sale__status__in=['DRAFT', 'PENDING'],
    sale__storefront__in=storefronts_for_warehouse
).aggregate(total=Sum('quantity'))['total'] or 0
```

### Option 3: Proportional Distribution (If no direct link)

Distribute total reservations proportionally based on stock quantity:

```python
# Calculate total stock across all warehouses for this product
from inventory.models import StockProduct

total_stock_for_product = StockProduct.objects.filter(
    product=stock.product
).aggregate(total=Sum('quantity'))['total'] or 1  # Avoid division by zero

# Get global reservations
global_reserved = SaleItem.objects.filter(
    product=stock.product,
    sale__status__in=['DRAFT', 'PENDING']
).aggregate(total=Sum('quantity'))['total'] or 0

# Distribute proportionally based on this warehouse's share
proportion = stock.quantity / total_stock_for_product
reserved_qty = int(global_reserved * proportion)
```

### Option 4: Calculate Reservations Once (Performance optimization)

Pre-calculate ALL reservations, then distribute:

```python
def _build_stock_levels(self, queryset, request) -> tuple:
    from django.db.models import Sum
    from sales.models import SaleItem
    
    # PRE-CALCULATE: Get all reservations grouped by product
    reservations_by_product = {}
    all_product_ids = queryset.values_list('product_id', flat=True).distinct()
    
    reservation_data = SaleItem.objects.filter(
        product_id__in=all_product_ids,
        sale__status__in=['DRAFT', 'PENDING']
    ).values('product_id').annotate(
        total_reserved=Sum('quantity')
    )
    
    for item in reservation_data:
        reservations_by_product[str(item['product_id'])] = item['total_reserved']
    
    # Now in the loop, use pre-calculated value ONCE per product
    product_stocks = {}
    
    for stock in queryset:
        product_id = str(stock.product.id)
        
        if product_id not in product_stocks:
            # Initialize product entry
            # ...
            
            # Get total reserved for this product (calculated once)
            total_reserved_for_product = reservations_by_product.get(product_id, 0)
            product_stocks[product_id]['_total_reserved'] = total_reserved_for_product
            product_stocks[product_id]['_total_stock'] = 0
        
        # Track total stock for proportional calculation
        product_stocks[product_id]['_total_stock'] += stock.quantity
        
        # Add location WITHOUT reserved yet
        product_stocks[product_id]['locations'].append({
            'warehouse_id': str(stock.warehouse.id),
            'warehouse_name': stock.warehouse.name,
            'quantity': stock.quantity,
            'reserved': 0,  # Will calculate after loop
            # ...
        })
    
    # SECOND PASS: Distribute reservations proportionally
    for product_data in product_stocks.values():
        total_reserved = product_data['_total_reserved']
        total_stock = product_data['_total_stock']
        
        if total_stock > 0:
            for location in product_data['locations']:
                proportion = location['quantity'] / total_stock
                location['reserved'] = int(total_reserved * proportion)
                location['available'] = max(0, location['quantity'] - location['reserved'])
                product_data['total_available'] += location['available']
    
    # Continue with rest of logic...
```

## Recommended Solution

**Use Option 4** (pre-calculate and distribute proportionally) because:

1. ✅ **Performance**: Calculates reservations once instead of N times
2. ✅ **Accuracy**: Ensures total reserved matches across locations
3. ✅ **Math consistency**: `total_quantity = total_available + total_reserved`
4. ✅ **Works regardless of architecture**: Doesn't require warehouse-sale linkage

## Verification

After fixing, verify with Samsung TV example:

```python
# Expected after fix:
Total Stock: 484 units
Total Reserved: 323 units
Total Available: 484 - 323 = 161 units

Location A (150 units, 31% of total):
  Reserved: 323 * 0.31 = 100 units
  Available: 150 - 100 = 50 units

Location B (334 units, 69% of total):
  Reserved: 323 * 0.69 = 223 units
  Available: 334 - 223 = 111 units

Verification:
  50 + 111 = 161 ✓
  100 + 223 = 323 ✓
  161 + 323 = 484 ✓
```

## Testing Checklist

- [ ] Run stock levels report for Samsung TV
- [ ] Verify: `total_quantity = total_available + SUM(location.reserved)`
- [ ] Verify: No location shows negative available
- [ ] Verify: SUM(location.available) == total_available
- [ ] Verify: SUM(location.reserved) matches actual DRAFT/PENDING sales
- [ ] Test with products in single warehouse
- [ ] Test with products in multiple warehouses
- [ ] Test with products with zero reservations
- [ ] Test with products with zero stock

## Implementation Priority

**CRITICAL** - Fix immediately before users lose trust in inventory data.

## Related Files

- `reports/views/inventory_reports.py` (Line 293-328)
- `sales/models.py` (SaleItem, Sale models)
- `inventory/models.py` (StockProduct, Warehouse models)

---

**Author:** Backend Team  
**Date:** October 30, 2025  
**Status:** 🔴 BUG CONFIRMED - FIX REQUIRED
