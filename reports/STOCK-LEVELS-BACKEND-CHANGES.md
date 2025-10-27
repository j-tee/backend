# Backend Stock Levels API - Code Changes
**File**: `backend/reports/views/inventory_reports.py`  
**Class**: `StockLevelsSummaryReportView`

## Changes Overview
Update the Stock Levels Summary endpoint to match frontend expectations with proper structure and additional fields.

## 1. Update `_build_summary()` Method

### Current Issues:
- Field names don't match frontend expectations
- Missing some required calculations

### Required Changes:
```python
def _build_summary(self, queryset) -> Dict[str, Any]:
    """Build overall summary statistics"""
    # Get unique products
    products = queryset.values('product').distinct()
    total_products = products.count()
    
    # Get warehouse count
    warehouses_count = queryset.values('warehouse').distinct().count()
    
    # Aggregate totals
    totals = queryset.aggregate(
        total_units=Sum('quantity'),
        total_value=Sum(
            F('quantity') * F('landed_unit_cost'),
            output_field=DecimalField()
        )
    )
    
    # Count stock statuses BY PRODUCT (not by stock entries)
    # A product is "in stock" if it has ANY location with quantity > reorder_point
    # A product is "low stock" if ALL locations have 0 < quantity < reorder_point  
    # A product is "out of stock" if ALL locations have quantity == 0
    
    product_statuses = {}
    for stock in queryset:
        prod_id = str(stock.product.id)
        if prod_id not in product_statuses:
            product_statuses[prod_id] = {
                'has_stock': False,
                'all_low': True,
                'all_out': True
            }
        
        # If any location has good stock, product is in stock
        if stock.quantity > 10:  # Using 10 as default reorder point
            product_statuses[prod_id]['has_stock'] = True
            product_statuses[prod_id]['all_low'] = False
            product_statuses[prod_id]['all_out'] = False
        # If any location has some stock, not all out
        elif stock.quantity > 0:
            product_statuses[prod_id]['all_out'] = False
    
    in_stock = sum(1 for p in product_statuses.values() if p['has_stock'])
    low_stock = sum(1 for p in product_statuses.values() if p['all_low'] and not p['all_out'])
    out_of_stock = sum(1 for p in product_statuses.values() if p['all_out'])
    
    # Total variants
    total_variants = queryset.count()
    
    return {
        'total_products': total_products,
        'total_variants': total_variants,
        'in_stock': in_stock,
        'low_stock': low_stock,
        'out_of_stock': out_of_stock,
        'total_stock_value': str(totals['total_value'] or Decimal('0.00')),
        'warehouses_count': warehouses_count
    }
```

## 2. Update `_build_stock_levels()` Method

### Current Issues:
- Returns `warehouses` array instead of `locations`
- Missing `reserved`, `available`, `reorder_point`, `status` fields
- Missing `total_available`, `last_restocked`, `days_until_stockout` at product level

### Required Changes:
```python
def _build_stock_levels(self, queryset, request) -> tuple:
    """Build product-level stock details with pagination"""
    from sales.models import SaleItem
    from datetime import timedelta
    
    # Group by product and aggregate across warehouses
    product_stocks = {}
    
    for stock in queryset:
        product_id = str(stock.product.id)
        
        if product_id not in product_stocks:
            product_stocks[product_id] = {
                'product_id': product_id,
                'product_name': stock.product.name,
                'sku': stock.product.sku,
                'category': stock.product.category.name if stock.product.category else None,
                'total_quantity': 0,
                'total_available': 0,  # NEW
                'total_value': Decimal('0.00'),
                'locations': [],  # RENAMED from 'warehouses'
                'last_restocked': None,  # NEW
            }
        
        # Calculate reserved stock for this location
        # Reserved = items in DRAFT/PENDING sales for this product at this warehouse
        reserved_qty = 0  # Simplified - would need proper reservation tracking
        available_qty = stock.quantity - reserved_qty
        
        # Determine reorder point (simplified - could be product-specific)
        reorder_point = 10
        
        # Determine status for this location
        if available_qty == 0:
            status = 'out_of_stock'
        elif available_qty < reorder_point:
            status = 'low_stock'
        else:
            status = 'in_stock'
        
        # Calculate warehouse-level value
        warehouse_value = stock.quantity * stock.landed_unit_cost
        
        # Add location entry
        product_stocks[product_id]['locations'].append({
            'warehouse_id': str(stock.warehouse.id),
            'warehouse_name': stock.warehouse.name,
            'quantity': stock.quantity,
            'reserved': reserved_qty,  # NEW
            'available': available_qty,  # NEW
            'reorder_point': reorder_point,  # NEW
            'status': status,  # NEW
            'unit_cost': str(stock.landed_unit_cost),
            'value': str(warehouse_value),
            'supplier': stock.supplier.name if stock.supplier else None
        })
        
        # Update totals
        product_stocks[product_id]['total_quantity'] += stock.quantity
        product_stocks[product_id]['total_available'] += available_qty  # NEW
        product_stocks[product_id]['total_value'] += warehouse_value
        
        # Track most recent restock date
        if stock.created_at:
            current_date = product_stocks[product_id]['last_restocked']
            if current_date is None or stock.created_at.date() > current_date:
                product_stocks[product_id]['last_restocked'] = stock.created_at.date()
    
    # Finalize products
    stock_levels = []
    thirty_days_ago = timezone.now().date() - timedelta(days=30)
    
    for product_data in product_stocks.values():
        # Convert total_value to string
        product_data['total_value'] = str(product_data['total_value'])
        
        # Add unit_cost (average across locations)
        if product_data['locations']:
            avg_cost = sum(Decimal(loc['unit_cost']) for loc in product_data['locations']) / len(product_data['locations'])
            product_data['unit_cost'] = str(avg_cost)
        else:
            product_data['unit_cost'] = '0.00'
        
        # Calculate days_until_stockout based on sales velocity
        product_id = product_data['product_id']
        
        # Get sales for last 30 days
        sales_stats = SaleItem.objects.filter(
            product_id=product_id,
            sale__created_at__date__gte=thirty_days_ago,
            sale__status__in=['COMPLETED', 'PARTIAL']
        ).aggregate(
            total_sold=Sum('quantity')
        )
        
        units_sold = float(sales_stats['total_sold'] or 0)
        avg_daily_sales = units_sold / 30.0
        
        if avg_daily_sales > 0 and product_data['total_available'] > 0:
            days_until_stockout = int(product_data['total_available'] / avg_daily_sales)
        else:
            days_until_stockout = 999  # No sales or no stock
        
        product_data['days_until_stockout'] = days_until_stockout
        
        # Format last_restocked
        if product_data['last_restocked']:
            product_data['last_restocked'] = product_data['last_restocked'].isoformat()
        else:
            product_data['last_restocked'] = None
        
        stock_levels.append(product_data)
    
    # Sort by total value descending
    stock_levels.sort(key=lambda x: Decimal(x['total_value']), reverse=True)
    
    # Apply pagination
    page, page_size = self.get_pagination_params(request)
    total_count = len(stock_levels)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_data = stock_levels[start_idx:end_idx]
    
    pagination = {
        'page': page,
        'page_size': page_size,
        'total_count': total_count,
        'total_pages': (total_count + page_size - 1) // page_size
    }
    
    return paginated_data, pagination
```

## 3. Update `get()` Method Response

### Current Code:
```python
return ReportResponse.success(summary_data, stock_levels, metadata)
```

### New Code:
```python
# Return response with simplified structure
response_data = {
    'summary': summary,
    'items': stock_levels  # RENAMED from results
}

return ReportResponse.success(response_data, None, metadata)
```

## Summary of Changes

### Field Renames:
- `results` → `items`
- `warehouses` → `locations` (inside each item)

### New Fields Added:

#### Summary Level:
- `in_stock` - count of products with good stock
- `low_stock` - count of products below reorder point
- `out_of_stock` - count of products with zero stock

#### Location Level (per warehouse):
- `reserved` - quantity reserved in pending sales
- `available` - quantity - reserved
- `reorder_point` - threshold for low stock alerts
- `status` - 'in_stock' | 'low_stock' | 'out_of_stock'

#### Product Level:
- `total_available` - sum of available across all locations
- `last_restocked` - most recent stock intake date
- `days_until_stockout` - estimated days based on sales velocity
- `unit_cost` - average unit cost across locations

## Testing the Changes

### 1. Test Empty Database:
```bash
curl -H "Authorization: Token YOUR_TOKEN" \
  "http://localhost:8000/reports/api/inventory/stock-levels/"
```

Expected: Empty items array, zero counts

### 2. Test Single Product:
```bash
curl -H "Authorization: Token YOUR_TOKEN" \
  "http://localhost:8000/reports/api/inventory/stock-levels/?product_id=PRODUCT_UUID"
```

Expected: Single item with all fields populated

### 3. Test Filters:
```bash
# By warehouse
curl -H "Authorization: Token YOUR_TOKEN" \
  "http://localhost:8000/reports/api/inventory/stock-levels/?warehouse_id=WAREHOUSE_UUID"

# By category
curl -H "Authorization: Token YOUR_TOKEN" \
  "http://localhost:8000/reports/api/inventory/stock-levels/?category_id=CATEGORY_UUID"
```

## Implementation Notes

1. **Reserved Stock**: Currently simplified to 0. For proper implementation, would need to track:
   - DRAFT sales items
   - PENDING sales items
   - Transfer requests in transit

2. **Reorder Point**: Currently hardcoded to 10. Should be:
   - Per-product configuration
   - Or calculated based on sales velocity

3. **Sales Velocity**: Uses 30-day window. Could be configurable.

4. **Last Restocked**: Uses StockProduct.created_at. Could also check:
   - StockAdjustment records with type='RESTOCK'
   - Purchase order receipts

5. **Performance**: With 1000+ products, consider:
   - Database query optimization
   - Caching summary statistics
   - Async calculation for days_until_stockout
