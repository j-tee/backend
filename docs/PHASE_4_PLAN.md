# Phase 4: Inventory Reports - Implementation Plan

**Timeline:** Weeks 9-11 (approx 3 weeks)  
**Reports:** 4 Inventory Analytical Reports  
**Status:** In Progress

---

## Overview

Phase 4 focuses on inventory management and warehouse analytics. These reports help track stock levels, identify low stock situations, analyze stock movements, and optimize warehouse operations.

### Data Sources

**Primary Models:**
- `Product` - Product master data
- `StockProduct` - Stock batches with quantities and costs
- `Warehouse` - Warehouse locations
- `StockAdjustment` - Stock movements (theft, damage, returns, corrections)
- `Sale` & `SaleItem` - Sales impact on inventory
- `Category` - Product categorization
- `Supplier` - Supplier information

**Key Fields:**
- `StockProduct.quantity` - Current stock level
- `StockProduct.landed_unit_cost` - Total cost per unit
- `StockProduct.retail_price` - Selling price
- `StockProduct.expiry_date` - Product expiration
- `StockAdjustment.adjustment_type` - Type of stock movement
- `StockAdjustment.quantity` - Adjustment amount
- `StockAdjustment.total_cost` - Financial impact

---

## Report Specifications

### 1. Stock Levels Summary Report

**Purpose:** Real-time overview of inventory across all warehouses

**Endpoint:** `GET /reports/api/inventory/stock-levels/`

**Key Features:**
- Current stock quantities by product
- Stock value (quantity × unit cost)
- Warehouse-level breakdown
- Category-level aggregation
- Low stock indicators
- Multi-warehouse comparison

**Query Parameters:**
- `warehouse_id`: int (optional - filter by warehouse)
- `category_id`: UUID (optional - filter by category)
- `product_id`: UUID (optional - specific product)
- `supplier_id`: UUID (optional - filter by supplier)
- `min_quantity`: int (optional - filter products above threshold)
- `max_quantity`: int (optional - filter products below threshold)
- `include_zero_stock`: boolean (default: false)
- `page`: int (pagination)
- `page_size`: int (pagination)

**Response Structure:**
```json
{
  "success": true,
  "data": {
    "summary": {
      "total_products": 250,
      "total_stock_units": 15000,
      "total_stock_value": "750000.00",
      "warehouses_count": 3,
      "low_stock_products": 15,
      "out_of_stock_products": 5,
      "products_with_stock": 245
    },
    "by_warehouse": [
      {
        "warehouse_id": "uuid",
        "warehouse_name": "Main Warehouse",
        "total_products": 200,
        "total_units": 12000,
        "total_value": "600000.00",
        "low_stock_count": 10
      }
    ],
    "by_category": [
      {
        "category_id": "uuid",
        "category_name": "Electronics",
        "total_products": 50,
        "total_units": 3000,
        "total_value": "300000.00"
      }
    ],
    "stock_levels": [
      {
        "product_id": "uuid",
        "product_name": "Product A",
        "sku": "SKU001",
        "category": "Electronics",
        "total_quantity": 500,
        "total_value": "25000.00",
        "warehouses": [
          {
            "warehouse_id": "uuid",
            "warehouse_name": "Main Warehouse",
            "quantity": 300,
            "unit_cost": "50.00",
            "value": "15000.00"
          }
        ],
        "is_low_stock": false,
        "is_out_of_stock": false
      }
    ]
  },
  "meta": {
    "warehouse_id": null,
    "category_id": null,
    "include_zero_stock": false,
    "pagination": {...}
  }
}
```

**Calculations:**
- **Stock Value:** `quantity × landed_unit_cost`
- **Low Stock:** Based on reorder point (if available) or < 10 units
- **Out of Stock:** `quantity = 0`

---

### 2. Low Stock Alerts Report

**Purpose:** Identify products that need reordering

**Endpoint:** `GET /reports/api/inventory/low-stock-alerts/`

**Key Features:**
- Products below reorder threshold
- Days until out of stock (estimated)
- Reorder recommendations
- Supplier information
- Historical sales velocity
- Priority levels (critical, high, medium)

**Query Parameters:**
- `warehouse_id`: int (optional - filter by warehouse)
- `category_id`: UUID (optional - filter by category)
- `priority`: critical|high|medium (optional)
- `days_threshold`: int (default: 30 - days of stock remaining)
- `page`: int (pagination)
- `page_size`: int (pagination)

**Response Structure:**
```json
{
  "success": true,
  "data": {
    "summary": {
      "total_low_stock_products": 15,
      "critical_alerts": 3,
      "high_priority": 7,
      "medium_priority": 5,
      "estimated_reorder_cost": "125000.00"
    },
    "alerts": [
      {
        "product_id": "uuid",
        "product_name": "Product A",
        "sku": "SKU001",
        "category": "Electronics",
        "warehouse_id": "uuid",
        "warehouse_name": "Main Warehouse",
        "current_quantity": 5,
        "reorder_point": 20,
        "recommended_order_quantity": 50,
        "supplier_id": "uuid",
        "supplier_name": "Supplier Inc.",
        "unit_cost": "50.00",
        "estimated_order_cost": "2500.00",
        "priority": "critical",
        "days_until_stockout": 3,
        "average_daily_sales": 1.5,
        "last_restock_date": "2024-10-01"
      }
    ]
  },
  "meta": {
    "warehouse_id": null,
    "category_id": null,
    "priority": null,
    "days_threshold": 30
  }
}
```

**Priority Levels:**
- **Critical:** < 5 days of stock OR already out of stock
- **High:** 5-14 days of stock remaining
- **Medium:** 15-30 days of stock remaining

**Calculations:**
- **Average Daily Sales:** Total sales last 30 days / 30
- **Days Until Stockout:** `current_quantity / average_daily_sales`
- **Recommended Order Quantity:** Based on lead time and safety stock

---

### 3. Stock Movement History Report

**Purpose:** Track all inventory changes over time

**Endpoint:** `GET /reports/api/inventory/stock-movements/`

**Key Features:**
- All stock adjustments by type
- Sales impact on inventory
- Movement trends over time
- Loss/shrinkage analysis
- Returns tracking
- Transfer history

**Query Parameters:**
- `start_date`: YYYY-MM-DD (default: 30 days ago)
- `end_date`: YYYY-MM-DD (default: today)
- `warehouse_id`: int (optional)
- `product_id`: UUID (optional)
- `movement_type`: all|sales|adjustments|returns|transfers (default: all)
- `adjustment_type`: theft|damage|expired|... (optional - specific adjustment type)
- `grouping`: daily|weekly|monthly (default: daily)
- `page`: int (pagination)
- `page_size`: int (pagination)

**Response Structure:**
```json
{
  "success": true,
  "data": {
    "summary": {
      "total_movements": 500,
      "total_units_in": 3000,
      "total_units_out": 2500,
      "net_change": 500,
      "value_in": "150000.00",
      "value_out": "125000.00",
      "net_value_change": "25000.00",
      "movement_breakdown": {
        "sales": 2000,
        "theft": -50,
        "damage": -30,
        "returns": 100,
        "adjustments": 80
      },
      "shrinkage": {
        "total_units": 120,
        "total_value": "6000.00",
        "percentage_of_stock": 2.4
      }
    },
    "time_series": [
      {
        "period": "2024-10-12",
        "period_start": "2024-10-12",
        "period_end": "2024-10-13",
        "units_in": 150,
        "units_out": 100,
        "net_change": 50,
        "value_in": "7500.00",
        "value_out": "5000.00",
        "movements_count": 25
      }
    ],
    "movements": [
      {
        "movement_id": "uuid",
        "movement_type": "adjustment",
        "adjustment_type": "THEFT",
        "product_id": "uuid",
        "product_name": "Product A",
        "warehouse_id": "uuid",
        "warehouse_name": "Main Warehouse",
        "quantity_change": -10,
        "unit_cost": "50.00",
        "total_value": "-500.00",
        "reason": "Inventory theft detected",
        "created_by": "John Doe",
        "created_at": "2024-10-12T10:30:00Z"
      }
    ]
  },
  "meta": {
    "date_range": {...},
    "movement_type": "all",
    "grouping": "daily",
    "pagination": {...}
  }
}
```

**Movement Types:**
- **Sales:** From SaleItem records (quantity sold)
- **Adjustments:** From StockAdjustment records
- **Returns:** Customer returns (positive adjustment)
- **Transfers:** Between warehouses

**Shrinkage Calculation:**
Shrinkage = Sum of (THEFT + DAMAGE + EXPIRED + SPOILAGE + LOSS + WRITE_OFF)

---

### 4. Warehouse Analytics Report

**Purpose:** Warehouse performance and utilization metrics

**Endpoint:** `GET /reports/api/inventory/warehouse-analytics/`

**Key Features:**
- Stock turnover rate
- Warehouse capacity utilization
- Product diversity
- Dead stock identification
- Fast vs slow-moving products
- Warehouse comparison

**Query Parameters:**
- `warehouse_id`: int (optional - specific warehouse)
- `start_date`: YYYY-MM-DD (default: 90 days ago)
- `end_date`: YYYY-MM-DD (default: today)
- `min_turnover_rate`: float (optional)
- `max_turnover_rate`: float (optional)

**Response Structure:**
```json
{
  "success": true,
  "data": {
    "summary": {
      "total_warehouses": 3,
      "total_products_stored": 250,
      "total_stock_value": "750000.00",
      "average_turnover_rate": 4.5,
      "total_sales_units": 5000,
      "total_dead_stock_value": "25000.00"
    },
    "warehouses": [
      {
        "warehouse_id": "uuid",
        "warehouse_name": "Main Warehouse",
        "location": "Downtown",
        "products_count": 200,
        "total_units": 12000,
        "total_value": "600000.00",
        "turnover_rate": 5.2,
        "capacity_utilization": 75.5,
        "top_products": [
          {
            "product_name": "Product A",
            "sales_units": 500,
            "turnover_rate": 8.5,
            "stock_value": "25000.00"
          }
        ],
        "slow_moving_products": [
          {
            "product_name": "Product Z",
            "days_since_last_sale": 90,
            "current_quantity": 50,
            "stock_value": "2500.00"
          }
        ],
        "dead_stock_value": "5000.00",
        "dead_stock_count": 5
      }
    ],
    "product_velocity": {
      "fast_moving": 100,
      "medium_moving": 120,
      "slow_moving": 25,
      "dead_stock": 5
    }
  },
  "meta": {
    "date_range": {...},
    "warehouse_id": null
  }
}
```

**Calculations:**
- **Turnover Rate:** `Total Sales Units / Average Stock Level` (for period)
- **Capacity Utilization:** `(Current Stock Units / Max Capacity) × 100`
  - Note: Requires max_capacity field (future enhancement)
- **Dead Stock:** Products with no sales in last 90 days
- **Fast Moving:** Turnover rate > 6 (sells more than 6× per period)
- **Medium Moving:** Turnover rate 2-6
- **Slow Moving:** Turnover rate 0.5-2
- **Dead Stock:** Turnover rate < 0.5 or no sales

---

## Implementation Strategy

### Phase 4A: Foundation (Days 1-3)
- [x] Review inventory models structure
- [ ] Create Phase 4 plan document
- [ ] Create `reports/views/inventory_reports.py`
- [ ] Add URL patterns
- [ ] Update views `__init__.py`

### Phase 4B: Core Reports (Days 4-7)
- [ ] Implement Stock Levels Summary Report
- [ ] Implement Low Stock Alerts Report
- [ ] Test basic functionality

### Phase 4C: Advanced Reports (Days 8-11)
- [ ] Implement Stock Movement History Report
- [ ] Implement Warehouse Analytics Report
- [ ] Calculate turnover rates
- [ ] Identify dead stock

### Phase 4D: Testing & Documentation (Days 12-14)
- [ ] Test all endpoints with sample data
- [ ] Verify calculations
- [ ] Performance optimization
- [ ] Create completion summary
- [ ] Git commit and push

---

## Technical Considerations

### Database Queries

**Stock Levels:**
```python
StockProduct.objects.filter(warehouse=warehouse).values('product').annotate(
    total_quantity=Sum('quantity'),
    total_value=Sum(F('quantity') * F('landed_unit_cost'))
)
```

**Sales Velocity:**
```python
SaleItem.objects.filter(
    sale__created_at__gte=start_date,
    product=product
).aggregate(total_sold=Sum('quantity'))
```

**Stock Adjustments:**
```python
StockAdjustment.objects.filter(
    created_at__gte=start_date,
    status='COMPLETED'
).values('adjustment_type').annotate(
    total_quantity=Sum('quantity'),
    total_cost=Sum('total_cost')
)
```

### Performance Optimizations

1. **Aggregations:** Use database aggregations instead of Python loops
2. **Select Related:** Prefetch related objects for nested data
3. **Indexing:** Leverage existing indexes on warehouse, product, created_at
4. **Caching:** Consider caching for frequently accessed warehouse lists
5. **Pagination:** Always paginate product-level results

---

## Success Criteria

- [ ] All 4 inventory reports implemented
- [ ] No Django check errors
- [ ] Efficient ORM queries (no N+1 problems)
- [ ] Accurate stock calculations
- [ ] Proper low stock detection
- [ ] Comprehensive movement tracking
- [ ] Warehouse analytics with turnover rates
- [ ] Follows existing code patterns
- [ ] Complete documentation
- [ ] Standard response format

---

## Future Enhancements (Post-Phase 4)

### Tier 2 Features:
- Reorder point configuration per product
- Automatic purchase order generation
- Warehouse capacity tracking
- ABC analysis (80/20 rule for inventory)
- Seasonal demand forecasting
- Supplier performance metrics
- Multi-location transfer optimization
- Real-time alerts/notifications
- Expiry date tracking and alerts
- Batch/lot tracking

---

## Dependencies

**Models:**
- ✅ Product
- ✅ StockProduct
- ✅ Warehouse
- ✅ StockAdjustment
- ✅ Sale & SaleItem
- ✅ Category
- ✅ Supplier

**Existing Utils:**
- ✅ BaseReportView
- ✅ ReportResponse, ReportError
- ✅ AggregationHelper
- ✅ Date utilities

---

## Timeline

- **Week 9:** Stock Levels & Low Stock Alerts
- **Week 10:** Stock Movement History
- **Week 11:** Warehouse Analytics + Testing

**Total Duration:** ~3 weeks (concurrent with other tasks)

---

## Next Phase Preview

**Phase 5: Customer Reports (4 reports)**
- Customer Lifetime Value
- Customer Segmentation  
- Purchase Pattern Analysis
- Customer Retention Metrics

**Timeline:** Weeks 12-14
