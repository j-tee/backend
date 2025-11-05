# API Endpoints Quick Reference

**Backend Base URL:** `/reports/api/`  
**Total Endpoints:** 16  
**Authentication:** Required (Bearer Token)  
**Response Format:** JSON

---

## Endpoint Index

### Sales Reports (4)

| # | Endpoint | Method | Purpose |
|---|----------|--------|---------|
| 1 | `/sales/summary/` | GET | Sales overview with daily/weekly/monthly breakdown |
| 2 | `/sales/product-performance/` | GET | Top-selling products by revenue/quantity/profit |
| 3 | `/sales/customer-analytics/` | GET | Customer purchasing behavior analysis |
| 4 | `/sales/revenue-trends/` | GET | Revenue patterns and growth analysis |

### Financial Reports (4)

| # | Endpoint | Method | Purpose |
|---|----------|--------|---------|
| 5 | `/financial/revenue-profit/` | GET | Profit margin analysis over time |
| 6 | `/financial/ar-aging/` | GET | Accounts receivable aging buckets |
| 7 | `/financial/collection-rates/` | GET | Credit collection efficiency metrics |
| 8 | `/financial/cash-flow/` | GET | Cash on hand movements |

> **Storefront scope:** Sales and financial analytics endpoints accept `storefront_id` (and optional `storefront_ids`) to constrain dashboards and exports to specific storefronts. Omit the parameter to retain current all-storefront totals.

### Inventory Reports (4)

| # | Endpoint | Method | Purpose |
|---|----------|--------|---------|
| 9 | `/inventory/stock-levels/` | GET | Current inventory status by warehouse |
| 10 | `/inventory/low-stock-alerts/` | GET | Products needing reorder |
| 11 | `/inventory/stock-movements/` | GET | Inventory changes history |
| 12 | `/inventory/warehouse-analytics/` | GET | Warehouse performance and turnover |

### Customer Reports (4)

| # | Endpoint | Method | Purpose |
|---|----------|--------|---------|
| 13 | `/customer/lifetime-value/` | GET | Customer value rankings (CLV) |
| 14 | `/customer/segmentation/` | GET | RFM analysis and customer tiers |
| 15 | `/customer/purchase-patterns/` | GET | Buying behavior and preferences |
| 16 | `/customer/retention/` | GET | Retention, churn, and cohort analysis |

---

## Quick Start Examples

### 1. Get Sales Summary (Last 30 Days)

```bash
GET /reports/api/sales/summary/
Authorization: Bearer YOUR_TOKEN
```

**Response:**
```json
{
  "report_name": "Sales Summary Report",
  "summary": {
    "total_revenue": "125000.00",
    "total_transactions": 450
  },
  "data": [...]
}
```

### 2. Get Low Stock Alerts

```bash
GET /reports/api/inventory/low-stock-alerts/?urgency=critical
Authorization: Bearer YOUR_TOKEN
```

**Response:**
```json
{
  "summary": {
    "critical_alerts": 5
  },
  "data": [
    {
      "product_name": "iPhone 15",
      "current_quantity": 0,
      "urgency": "CRITICAL"
    }
  ]
}
```

### 3. Get Customer Segmentation

```bash
GET /reports/api/customer/segmentation/?segment_type=rfm
Authorization: Bearer YOUR_TOKEN
```

**Response:**
```json
{
  "rfm_segments": [
    {
      "segment_name": "Champions",
      "customer_count": 50,
      "avg_revenue": "8000.00"
    }
  ]
}
```

### 4. Get Revenue Trends (Monthly, Last 12 Months)

```bash
GET /reports/api/sales/revenue-trends/?grouping=monthly&start_date=2023-11-01&end_date=2024-10-31
Authorization: Bearer YOUR_TOKEN
```

---

## Common Patterns

### Pagination

All list endpoints support pagination:

```bash
GET /reports/api/sales/product-performance/?page=1&page_size=50
```

**Response includes:**
```json
{
  "pagination": {
    "count": 150,
    "next": "http://.../api/sales/product-performance/?page=2",
    "previous": null,
    "page_size": 50,
    "total_pages": 3
  }
}
```

### Date Filtering

Format: `YYYY-MM-DD`

```bash
GET /reports/api/sales/summary/?start_date=2024-10-01&end_date=2024-10-12
```

### Grouping (Time Series)

Available for: Sales, Financial reports

```bash
GET /reports/api/sales/summary/?grouping=weekly
# Options: daily, weekly, monthly
```

### Filtering by Entity

```bash
# By warehouse
GET /reports/api/sales/summary/?warehouse_id=uuid-here

# By customer type
GET /reports/api/customer/lifetime-value/?customer_type=WHOLESALE

# By category
GET /reports/api/sales/product-performance/?category=Electronics

# By payment method
GET /reports/api/sales/summary/?payment_method=cash
```

---

## Response Structure

All reports follow this standard format:

```json
{
  "report_name": "Report Title",
  "generated_at": "2025-10-12T10:30:00Z",
  "period": {
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "days": 365
  },
  "filters": {
    "warehouse_id": "uuid",
    "customer_type": "RETAIL"
  },
  "summary": {
    // High-level KPIs
    "total_revenue": "1000000.00",
    "total_transactions": 5000
  },
  "data": [
    // Detailed records
    {
      "period": "2024-10-12",
      "revenue": "10000.00"
    }
  ],
  "pagination": {
    "count": 100,
    "next": "url-to-next-page",
    "previous": null,
    "page_size": 100,
    "total_pages": 1
  }
}
```

---

## Parameter Reference

### Global Parameters (All Endpoints)

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `page` | integer | No | 1 | Page number for pagination |
| `page_size` | integer | No | 100 | Records per page (max: 1000) |

### Sales Report Parameters

**Sales Summary:**
- `start_date`, `end_date`: Date range (default: 30 days)
- `warehouse_id`: Filter by warehouse
- `customer_type`: RETAIL or WHOLESALE
- `payment_method`: cash, credit_card, bank_transfer, mobile_money, credit
- `grouping`: daily, weekly, monthly (default: daily)

**Product Performance:**
- `start_date`, `end_date`: Date range
- `warehouse_id`: Filter by warehouse
- `category`: Product category filter
- `min_quantity`: Minimum units sold
- `sort_by`: revenue, quantity, profit (default: revenue)

**Customer Analytics:**
- `start_date`, `end_date`: Date range
- `customer_type`: RETAIL or WHOLESALE
- `min_purchases`: Minimum number of purchases
- `sort_by`: revenue, purchases, average_value (default: revenue)

**Revenue Trends:**
- `start_date`, `end_date`: Date range
- `grouping`: daily, weekly, monthly (default: daily)
- `compare_previous_period`: boolean (include comparison)
- `warehouse_id`: Filter by warehouse
- `customer_type`: RETAIL or WHOLESALE

### Financial Report Parameters

**Revenue & Profit:**
- `start_date`, `end_date`: Date range
- `grouping`: daily, weekly, monthly
- `warehouse_id`: Filter by warehouse
- `min_profit_margin`: Minimum margin % threshold

**AR Aging:**
- `as_of_date`: Date for aging calculation (default: today)
- `customer_type`: RETAIL or WHOLESALE
- `min_balance`: Minimum outstanding balance
- `include_zero_balance`: Include customers with no balance (default: false)

**Collection Rates:**
- `start_date`, `end_date`: Date range
- `grouping`: daily, weekly, monthly
- `customer_type`: RETAIL or WHOLESALE

**Cash Flow:**
- `start_date`, `end_date`: Date range
- `grouping`: daily, weekly, monthly
- `warehouse_id`: Filter by warehouse

### Inventory Report Parameters

**Stock Levels:**
- `warehouse_id`: Filter by warehouse
- `category`: Product category filter
- `low_stock_only`: Show only low stock items (default: false)
- `min_quantity`: Minimum quantity threshold

**Low Stock Alerts:**
- `warehouse_id`: Filter by warehouse
- `category`: Product category filter
- `urgency`: critical, high, medium

**Stock Movements:**
- `start_date`, `end_date`: Date range (default: 30 days)
- `warehouse_id`: Filter by warehouse
- `product_id`: Filter by specific product
- `movement_type`: ADDITION, SALE, ADJUSTMENT
- `adjustment_type`: For adjustments: THEFT, DAMAGE, EXPIRED, etc.

**Warehouse Analytics:**
- `start_date`, `end_date`: For turnover calculations
- `warehouse_id`: Filter by specific warehouse
- `category`: Product category filter

### Customer Report Parameters

**Lifetime Value:**
- `start_date`, `end_date`: Customer creation date filter
- `customer_type`: RETAIL or WHOLESALE
- `min_revenue`: Minimum total revenue threshold
- `min_profit`: Minimum total profit threshold
- `sort_by`: revenue, profit, orders, aov (default: revenue)

**Segmentation:**
- `segment_type`: rfm, tier, credit, all (default: all)
- `customer_type`: RETAIL or WHOLESALE
- `include_inactive`: Include inactive customers (default: false)

**Purchase Patterns:**
- `start_date`, `end_date`: Date range (default: 90 days)
- `customer_id`: Analyze specific customer
- `customer_type`: RETAIL or WHOLESALE
- `grouping`: daily, weekly, monthly

**Retention:**
- `start_date`, `end_date`: Date range (default: 12 months)
- `cohort_period`: month, quarter, year (default: month)
- `customer_type`: RETAIL or WHOLESALE

---

## Error Responses

### 400 Bad Request
```json
{
  "error": "Invalid date format",
  "detail": "start_date must be in YYYY-MM-DD format",
  "status_code": 400
}
```

### 401 Unauthorized
```json
{
  "error": "Authentication required",
  "detail": "No valid authentication credentials provided",
  "status_code": 401
}
```

### 403 Forbidden
```json
{
  "error": "Permission denied",
  "detail": "You don't have permission to access this report",
  "status_code": 403
}
```

### 500 Internal Server Error
```json
{
  "error": "Internal server error",
  "detail": "An unexpected error occurred",
  "status_code": 500
}
```

---

## Special Features

### RFM Segmentation (Customer Segmentation Report)

**8 Segments:**
1. **Champions** - R:5, F:5, M:5 (Best customers)
2. **Loyal** - R:4-5, F:4-5, M:4-5 (Consistent value)
3. **Potential Loyalists** - R:4-5, F:2-3, M:3-4 (Growth potential)
4. **New Customers** - R:5, F:1-2, M:1-3 (Recent acquisitions)
5. **At Risk** - R:2-3, F:3-4, M:4-5 (Need attention)
6. **Can't Lose Them** - R:1-2, F:4-5, M:4-5 (Win back!)
7. **Hibernating** - R:1-2, F:1-2, M:1-3 (Dormant)
8. **Lost** - R:1, F:1-2, M:1-2 (Churned)

**Scoring:** 1-5 quintiles (1=worst, 5=best) for Recency, Frequency, Monetary

### AR Aging Buckets

- **0-30 days:** Current
- **31-60 days:** Early overdue
- **61-90 days:** Moderate overdue
- **Over 90 days:** Seriously overdue

### Stock Status Levels

- **OUT:** Quantity = 0
- **LOW:** Quantity ≤ Reorder Level
- **ADEQUATE:** Reorder Level < Quantity < Max Level
- **OVERSTOCKED:** Quantity ≥ Max Level

### Basket Size Ranges (Purchase Patterns)

- **$0-$100:** Small purchases
- **$100-$250:** Medium purchases
- **$250-$500:** Large purchases
- **$500-$1000:** Very large purchases
- **$1000+:** Wholesale/bulk purchases

---

## Testing Endpoints

### Using cURL

```bash
# Sales Summary
curl -H "Authorization: Bearer YOUR_TOKEN" \
     "http://localhost:8000/reports/api/sales/summary/?start_date=2024-10-01&end_date=2024-10-12"

# Product Performance (Top 10)
curl -H "Authorization: Bearer YOUR_TOKEN" \
     "http://localhost:8000/reports/api/sales/product-performance/?page_size=10&sort_by=revenue"

# Low Stock Alerts (Critical Only)
curl -H "Authorization: Bearer YOUR_TOKEN" \
     "http://localhost:8000/reports/api/inventory/low-stock-alerts/?urgency=critical"

# Customer Segmentation (RFM)
curl -H "Authorization: Bearer YOUR_TOKEN" \
     "http://localhost:8000/reports/api/customer/segmentation/?segment_type=rfm"
```

### Using Postman

1. **Set Authorization:**
   - Type: Bearer Token
   - Token: YOUR_ACCESS_TOKEN

2. **Set Base URL:**
   - `http://localhost:8000/reports/api/`

3. **Create Requests:**
   - GET `/sales/summary/`
   - Add query parameters as needed

4. **Save to Collection:**
   - Create "Reports API" collection
   - Add all 16 endpoints

### Using JavaScript Fetch

```javascript
const token = 'YOUR_ACCESS_TOKEN';

// Sales Summary
fetch('/reports/api/sales/summary/?start_date=2024-10-01&end_date=2024-10-12', {
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
})
  .then(res => res.json())
  .then(data => console.log(data));

// Customer Lifetime Value
fetch('/reports/api/customer/lifetime-value/?sort_by=revenue&page_size=10', {
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  }
})
  .then(res => res.json())
  .then(data => console.log(data));
```

---

## Performance Tips

1. **Use specific date ranges** - Avoid queries spanning years
2. **Implement pagination** - Don't fetch all records at once
3. **Cache responses** - Store data for 5-10 minutes
4. **Use appropriate grouping** - Monthly for long periods, daily for short
5. **Filter early** - Use warehouse_id, category filters to reduce data

---

## Next Steps

1. Review **FRONTEND_INTEGRATION_GUIDE.md** for detailed implementation
2. Test endpoints with your authentication token
3. Implement frontend components progressively
4. Add error handling and loading states
5. Implement caching strategy
6. Add export functionality (CSV/PDF)

---

**Documentation Version:** 1.0  
**Last Updated:** October 12, 2025  
**Total Endpoints:** 16/16 ✅
