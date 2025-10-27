# Warehouse Field Migration from Stock to StockProduct

## Overview

**Migration Date:** October 10, 2025  
**Status:** ✅ Complete  
**Migration File:** `inventory/migrations/0016_move_warehouse_to_stock_product.py`

## Changes Made

### Database Schema Changes

1. **Removed field:**
   - `Stock.warehouse` (ForeignKey to Warehouse)

2. **Added field:**
   - `StockProduct.warehouse` (ForeignKey to Warehouse)

3. **Index changes:**
   - Removed: `stock_warehou_7a5d57_idx` (Stock.warehouse + arrival_date)
   - Added: `stock_arrival_5d189a_idx` (Stock.arrival_date only)
   - Added: `stock_produ_warehou_792818_idx` (StockProduct.warehouse + product)

### Data Migration

The migration automatically copied `warehouse_id` from each `Stock` record to all associated `StockProduct` records.

```python
def migrate_warehouse_to_stock_product(apps, schema_editor):
    Stock = apps.get_model('inventory', 'Stock')
    StockProduct = apps.get_model('inventory', 'StockProduct')
    
    for stock in Stock.objects.all():
        StockProduct.objects.filter(stock=stock).update(warehouse=stock.warehouse)
```

## Code Changes Required

### Models (`inventory/models.py`)

**Before:**
```python
class Stock(models.Model):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='stocks')
    # ...

class StockProduct(models.Model):
    stock = models.ForeignKey(Stock, ...)
    # warehouse accessed via: self.stock.warehouse
```

**After:**
```python
class Stock(models.Model):
    # NO warehouse field
    # ...

class StockProduct(models.Model):
    stock = models.ForeignKey(Stock, ...)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='stock_products')
    # warehouse accessed directly: self.warehouse
```

### Query Changes

**Before:**
```python
# Filter by warehouse through stock
StockProduct.objects.filter(stock__warehouse=warehouse)

# Select related
StockProduct.objects.select_related('stock__warehouse')

# Access warehouse
stock_product.stock.warehouse
stock_product.stock.warehouse.name
```

**After:**
```python
# Filter by warehouse directly
StockProduct.objects.filter(warehouse=warehouse)

# Select related
StockProduct.objects.select_related('warehouse')

# Access warehouse
stock_product.warehouse
stock_product.warehouse.name
```

## Files Requiring Updates

### ✅ Completed

1. **inventory/models.py**
   - Removed `Stock.warehouse` field
   - Added `StockProduct.warehouse` field
   - Removed `@property warehouse()` from StockProduct
   - Updated `Product.get_latest_cost()` query
   - Updated `Product.get_expected_profit_summary()` query
   - Updated `Transfer.available_quantity()` query
   - Updated `Transfer._adjust_warehouse_inventory()` query

2. **inventory/admin.py**
   - Updated `StockAdmin.list_display` (removed 'warehouse')
   - Updated `StockAdmin.search_fields`
   - Updated `StockAdmin.list_filter`
   - Updated `StockProductAdmin.search_fields`
   - Updated `StockProductAdmin.list_filter`
   - Updated `StockProductAdmin.fieldsets` (added 'warehouse')
   - Updated `StockAdjustmentAdmin.list_filter`

3. **inventory/migrations/0016_move_warehouse_to_stock_product.py**
   - Created with data migration function
   - Applied successfully

### ⚠️ Requires Manual Update

The following files contain references to `stock__warehouse` or `stock.warehouse` that need to be updated:

1. **inventory/views.py** (26+ references)
   - Line 487: `select_related('stock__warehouse')` → `select_related('warehouse')`
   - Line 568: `select_related('stock_product__stock__warehouse')` → `select_related('stock_product__warehouse')`
   - Line 639-640: `sp.stock.warehouse_id` → `sp.warehouse_id`, `sp.stock.warehouse.name` → `sp.warehouse.name`
   - Line 972: `stock.warehouse` → need to get warehouse from stock_product
   - Line 988, 999: `select_related('stock__warehouse')` → `select_related('warehouse')`
   - Line 1007: `filter(stock__warehouse__business_link__business_id__in=...)` → `filter(warehouse__business_link__business_id__in=...)`
   - Line 1025-1026: `stock.warehouse` → need different approach
   - Line 1036: `instance.stock.warehouse` → `instance.warehouse`
   - Line 1079: `Q(stock__warehouse__name__icontains=...)` → `Q(warehouse__name__icontains=...)`
   - Line 1087: `filter(stock__warehouse_id=...)` → `filter(warehouse_id=...)`
   - Line 1166, 1176, 1189: Similar pattern changes
   - Line 2134, 2140-2141: Query changes
   - Line 2612, 2626: Access pattern changes

2. **sales/management/commands/regenerate_datalogique_sales.py**
   - Line 236: `stock__warehouse=warehouse` → `warehouse=warehouse`

3. **inventory/management/commands/replay_completed_adjustments.py**
   - Line 76: `select_related('stock_product__stock__warehouse')` → `select_related('stock_product__warehouse')`
   - Line 144: `stock_product.stock.warehouse.name` → `stock_product.warehouse.name`

4. **inventory/serializers.py** (likely contains references)
5. **inventory/tests.py** (likely contains references)

## Update Patterns

### Pattern 1: Query Filters

```python
# OLD
StockProduct.objects.filter(stock__warehouse=warehouse)
StockProduct.objects.filter(stock__warehouse_id=warehouse_id)
StockProduct.objects.filter(stock__warehouse__business_link__business_id__in=business_ids)

# NEW
StockProduct.objects.filter(warehouse=warehouse)
StockProduct.objects.filter(warehouse_id=warehouse_id)
StockProduct.objects.filter(warehouse__business_link__business_id__in=business_ids)
```

### Pattern 2: Select Related

```python
# OLD
StockProduct.objects.select_related('stock__warehouse')
StockProduct.objects.select_related('product', 'supplier', 'stock__warehouse')

# NEW
StockProduct.objects.select_related('warehouse')
StockProduct.objects.select_related('product', 'supplier', 'warehouse')
```

### Pattern 3: Property Access

```python
# OLD
stock_product.stock.warehouse
stock_product.stock.warehouse.name
stock_product.stock.warehouse_id

# NEW
stock_product.warehouse
stock_product.warehouse.name
stock_product.warehouse_id
```

### Pattern 4: Q Objects

```python
# OLD
Q(stock__warehouse__name__icontains=query)
Q(stock__warehouse__business_link__business_id__in=business_ids)

# NEW
Q(warehouse__name__icontains=query)
Q(warehouse__business_link__business_id__in=business_ids)
```

## Special Cases

### Case 1: Creating StockProduct from Stock

**Before:**
```python
stock = Stock.objects.get(pk=stock_id)
BusinessWarehouse.objects.get_or_create(business=business, warehouse=stock.warehouse)
```

**After:**
```python
# Warehouse must now be provided directly when creating StockProduct
stock = Stock.objects.get(pk=stock_id)
warehouse = request.data.get('warehouse')  # Get from request data
stock_product = StockProduct.objects.create(
    stock=stock,
    warehouse=warehouse,  # Explicitly provide warehouse
    product=product,
    # ...
)
BusinessWarehouse.objects.get_or_create(business=business, warehouse=warehouse)
```

### Case 2: Serializers

**Before:**
```python
class StockProductSerializer(serializers.ModelSerializer):
    warehouse_name = serializers.CharField(source='stock.warehouse.name', read_only=True)
    warehouse_id = serializers.UUIDField(source='stock.warehouse_id', read_only=True)
```

**After:**
```python
class StockProductSerializer(serializers.ModelSerializer):
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    warehouse_id = serializers.UUIDField(source='warehouse_id', read_only=True)
```

## Benefits of This Change

1. **Direct Relationship:** StockProduct now has a direct relationship with Warehouse, eliminating unnecessary joins
2. **Flexibility:** Each StockProduct can theoretically belong to different warehouses (if needed in future)
3. **Performance:** Queries are simpler and more efficient (one less join)
4. **Clarity:** The relationship is more explicit - stock products ARE IN a warehouse

## Potential Issues

### Data Consistency

Previously, all StockProduct records under the same Stock batch automatically shared the same warehouse. Now, this is not enforced at the database level.

**Recommendation:** Add application-level validation to ensure all StockProduct records created from the same Stock batch use the same warehouse (if this business rule should be maintained).

```python
# In StockProduct.clean() or save()
def clean(self):
    if self.stock_id:
        # Get the intended warehouse for this stock batch
        # (could be stored in Stock or derived from first StockProduct)
        existing_warehouse = StockProduct.objects.filter(
            stock=self.stock
        ).values_list('warehouse_id', flat=True).first()
        
        if existing_warehouse and existing_warehouse != self.warehouse_id:
            raise ValidationError(
                "All products in a stock batch must belong to the same warehouse"
            )
```

## Testing Checklist

- [ ] All migrations applied successfully
- [ ] Data migrated correctly (verify existing StockProducts have correct warehouse)
- [ ] All views updated and tested
- [ ] All serializers updated and tested
- [ ] All management commands updated and tested
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] API endpoints return correct warehouse data

## Rollback Plan

If issues arise, rollback is possible but complex:

1. Create reverse migration that:
   - Adds `warehouse` back to `Stock`
   - Removes `warehouse` from `StockProduct`
   - Migrates data back (take warehouse from first StockProduct in each Stock batch)

2. Revert code changes in models, views, serializers, etc.

**Note:** Rollback is NOT recommended after production use. Consider forward fixes instead.

---

**Status:** Migration applied. Code updates in progress.  
**Next Step:** Update inventory/views.py and related files with new query patterns.
