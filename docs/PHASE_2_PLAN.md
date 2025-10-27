# Phase 2: Complete Sales Reports Module

**Status:** 🔨 IN PROGRESS  
**Started:** October 12, 2025  
**Timeline:** Weeks 2-4  

---

## Objectives

### Primary Goals:
1. Complete remaining 2 sales analytical reports
2. Add export functionality (Excel/CSV) to analytical reports
3. Implement comparison period analysis
4. Add trend analysis with growth rates

### Reports to Implement:
- ✅ Sales Summary Report (Phase 1)
- ✅ Product Performance Report (Phase 1)
- 🔨 Customer Analytics Report (via Sales)
- 🔨 Revenue Trends Report

---

## Implementation Plan

### Week 2: Customer Analytics & Revenue Trends Reports

#### Day 1-2: Customer Analytics Report
**Endpoint:** `GET /reports/api/sales/customer-analytics/`

**Features:**
- Top customers by total purchase amount
- Customer purchase frequency (number of orders)
- Average order value per customer
- Customer contribution percentage
- Recency analysis (days since last purchase)
- Customer ranking and segmentation

**Query Parameters:**
- `start_date`, `end_date`
- `storefront_id` (optional)
- `limit` (default: 50)
- `sort_by` (revenue, frequency, avg_order - default: revenue)
- `page`, `page_size`

**Response:**
```json
{
  "summary": {
    "total_customers": 150,
    "total_revenue": 45000.00,
    "average_revenue_per_customer": 300.00,
    "average_orders_per_customer": 3.5,
    "repeat_customer_rate": 65.5
  },
  "results": [
    {
      "rank": 1,
      "customer_id": "uuid",
      "customer_name": "John Doe",
      "total_spent": 5000.00,
      "order_count": 15,
      "average_order_value": 333.33,
      "contribution_percentage": 11.11,
      "days_since_last_purchase": 5,
      "first_purchase_date": "2025-01-15",
      "last_purchase_date": "2025-10-07"
    },
    ...
  ]
}
```

#### Day 3-4: Revenue Trends Report
**Endpoint:** `GET /reports/api/sales/revenue-trends/`

**Features:**
- Time-series revenue data (daily, weekly, monthly)
- Growth rate calculations (day-over-day, week-over-week, month-over-month)
- Comparison with previous period
- Trend indicators (up/down/stable)
- Moving averages
- Peak performance dates

**Query Parameters:**
- `start_date`, `end_date`
- `storefront_id` (optional)
- `grouping` (daily, weekly, monthly - default: daily)
- `compare_to_previous` (boolean - default: false)
- `include_moving_average` (boolean - default: false)

**Response:**
```json
{
  "summary": {
    "total_revenue": 45000.00,
    "period_revenue": 45000.00,
    "previous_period_revenue": 38000.00,
    "growth_amount": 7000.00,
    "growth_rate": 18.42,
    "average_daily_revenue": 1500.00,
    "peak_day": "2025-10-05",
    "peak_revenue": 2500.00
  },
  "results": [
    {
      "period": "2025-10-01",
      "revenue": 1500.00,
      "order_count": 5,
      "previous_period_revenue": 1200.00,
      "growth_rate": 25.00,
      "trend": "up",
      "moving_average_7d": 1450.00
    },
    ...
  ]
}
```

### Week 3: Export Functionality

#### Day 1-2: Export Service for Analytical Reports
Create `reports/services/analytics_exporter.py`:
- Convert JSON analytics to Excel format
- Convert JSON analytics to CSV format
- Reuse existing EXPORTER_MAP infrastructure
- Support exporting both summary and detailed results

**Features:**
- Multi-sheet Excel exports (Summary + Details)
- Formatted headers with metadata
- Date range and filters info in export
- Chart-ready data formatting

#### Day 3: Add Export Actions to Existing Reports
Update all 4 sales reports to support:
```python
GET /reports/api/sales/summary/?export=excel
GET /reports/api/sales/products/?export=csv
GET /reports/api/sales/customer-analytics/?export=excel
GET /reports/api/sales/revenue-trends/?export=excel
```

When `export` parameter is present:
- Return file download instead of JSON
- Include all metadata in file
- Proper formatting for readability

### Week 4: Comparison Periods & Polish

#### Day 1-2: Comparison Period Functionality
Add to all sales reports:
```python
GET /reports/api/sales/summary/?start_date=2025-10-01&end_date=2025-10-12&compare=true
```

When `compare=true`:
- Automatically calculate previous period (same duration)
- Add comparison metrics to summary
- Add growth rates to results
- Visual indicators for improvements/declines

**Response Enhancement:**
```json
{
  "summary": {
    "current_period": {
      "total_sales": 150,
      "total_revenue": 45000.00,
      ...
    },
    "previous_period": {
      "total_sales": 120,
      "total_revenue": 38000.00,
      ...
    },
    "comparison": {
      "sales_growth": 25.00,
      "revenue_growth": 18.42,
      "profit_growth": 22.15
    }
  },
  ...
}
```

#### Day 3-4: Testing & Documentation
- Unit tests for all 4 sales reports
- Integration tests for comparison periods
- Export functionality tests
- Update documentation
- Performance optimization

---

## Technical Implementation Details

### 1. Customer Analytics Implementation

**File:** `reports/views/sales_reports.py`

Add `CustomerAnalyticsReportView` class:
```python
class CustomerAnalyticsReportView(BaseReportView):
    """
    Customer Analytics Report via Sales Data
    
    Analyzes customer purchase behavior and contribution
    """
    
    def get(self, request):
        # Get business and dates
        # Query Sale model grouped by customer
        # Calculate metrics per customer
        # Rank and paginate
        # Return response
```

**Database Queries:**
```python
# Get sales grouped by customer
sales_by_customer = Sale.objects.filter(
    business_id=business_id,
    status='COMPLETED',
    created_at__date__gte=start_date,
    created_at__date__lte=end_date
).values('customer_id', 'customer__name').annotate(
    total_spent=Sum('total_amount'),
    order_count=Count('id'),
    first_purchase=Min('created_at'),
    last_purchase=Max('created_at')
)
```

### 2. Revenue Trends Implementation

**File:** `reports/views/sales_reports.py`

Add `RevenueTrendsReportView` class:
```python
class RevenueTrendsReportView(BaseReportView):
    """
    Revenue Trends Report with Time-Series Analysis
    
    Shows revenue trends over time with growth calculations
    """
    
    def get(self, request):
        # Get grouping parameter (daily/weekly/monthly)
        # Group sales by time period
        # Calculate growth rates
        # Add moving averages if requested
        # Compare to previous period if requested
        # Return time-series data
```

### 3. Analytics Exporter Service

**File:** `reports/services/analytics_exporter.py`

```python
class AnalyticsExporter:
    """Export analytical reports to Excel/CSV"""
    
    def export_to_excel(self, report_data, report_name):
        """
        Create multi-sheet Excel file
        Sheet 1: Summary metrics
        Sheet 2: Detailed results
        Sheet 3: Metadata
        """
        
    def export_to_csv(self, report_data, report_name):
        """
        Create CSV file with results
        Include summary as header rows
        """
```

### 4. Comparison Period Mixin

**File:** `reports/services/report_base.py`

Add new mixin:
```python
class ComparisonPeriodMixin:
    """Add comparison period functionality to reports"""
    
    def get_comparison_period(self, start_date, end_date):
        """Calculate previous period of same duration"""
        duration = (end_date - start_date).days
        prev_end = start_date - timedelta(days=1)
        prev_start = prev_end - timedelta(days=duration)
        return prev_start, prev_end
    
    def calculate_growth_rate(self, current, previous):
        """Calculate percentage growth"""
        if not previous or previous == 0:
            return Decimal('100.00') if current > 0 else Decimal('0.00')
        return ((current - previous) / previous) * 100
```

---

## File Structure After Phase 2

```
reports/
├── views/
│   ├── __init__.py
│   ├── exports.py                     # Existing data exports
│   ├── automation.py                  # Existing automation
│   └── sales_reports.py               # Updated with 4 complete reports
│
├── services/
│   ├── report_base.py                 # Updated with ComparisonPeriodMixin
│   ├── analytics_exporter.py          # NEW - Export analytics to Excel/CSV
│   ├── sales_analytics.py             # NEW - Complex sales calculations (optional)
│   └── ... (existing services)
│
├── utils/
│   ├── __init__.py
│   ├── response.py
│   ├── date_utils.py
│   ├── aggregation.py
│   └── trend_analysis.py              # NEW - Trend calculations
│
└── ... (existing files)
```

---

## Success Criteria

By end of Phase 2, we should have:

- ✅ 4/4 Sales reports fully functional
- ✅ All sales reports support Excel/CSV export
- ✅ Comparison period analysis working
- ✅ Growth rate calculations accurate
- ✅ Comprehensive testing
- ✅ Updated documentation
- ✅ Performance optimized

**Progress:** 4/16 total reports (25%)

---

## Next Steps

After Phase 2 completion:
- **Phase 3:** Financial Reports (4 reports)
- **Phase 4:** Inventory Reports (4 reports)
- **Phase 5:** Customer Reports (4 reports)
- **Phase 6:** Testing & Optimization

---

**Ready to implement Customer Analytics Report first!**
