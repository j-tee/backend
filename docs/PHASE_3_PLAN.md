# Phase 3: Financial Reports Module

**Status:** 🔨 IN PROGRESS  
**Started:** October 12, 2025  
**Timeline:** Weeks 5-8 (3-4 weeks)  

---

## Objectives

### Primary Goals:
1. Implement 4 financial analytical reports
2. Use existing sales/payment/credit data (no complex accounting needed)
3. Provide actionable financial insights
4. Leave room for future bookkeeping integration

### Reports to Implement:
1. 🔨 Revenue & Profit Analysis Report
2. 🔨 Accounts Receivable (AR) Aging Report
3. 🔨 Payment Collection Rates Report
4. 🔨 Cash Flow Report

---

## Implementation Strategy

### Tier 1: Current Implementation (Phase 3)
**Using Existing Data:**
- Revenue: FROM `Sale.total_amount` ✅
- Cost of Goods Sold (COGS): FROM `SaleItem` cost calculations ✅
- Profit: FROM `Sale.total_profit` ✅
- Accounts Receivable: FROM `Customer` credit transactions ✅
- Payments: FROM `Payment` model ✅
- Cash Flow: FROM sales and payments ✅

### Tier 2: Future Enhancement (Later)
**When Bookkeeping Matures:**
- Detailed expense tracking
- Full P&L statements
- Balance sheet integration
- Complete accrual accounting
- Budget vs actual analysis

---

## Report Specifications

### 1. Revenue & Profit Analysis Report
**Endpoint:** `GET /reports/api/financial/revenue-profit/`

**Purpose:** Analyze revenue sources, profit margins, and profitability trends

**Data Sources:**
- `Sale` model: total_amount, total_profit, sale_type
- `SaleItem` model: product-level margins
- `Payment` model: payment methods

**Features:**
- Total revenue and profit
- Gross profit margin
- Revenue by sale type (retail vs wholesale)
- Revenue by payment method
- Top profitable products/categories
- Monthly revenue and profit trends
- Profit margin analysis

**Query Parameters:**
- `start_date`, `end_date`
- `storefront_id` (optional)
- `sale_type` (optional)
- `grouping`: daily, weekly, monthly

**Response:**
```json
{
  "summary": {
    "total_revenue": 450000.00,
    "total_cost": 300000.00,
    "gross_profit": 150000.00,
    "gross_margin": 33.33,
    "net_profit": 150000.00,  // Same as gross for now
    "net_margin": 33.33,
    "revenue_by_type": {
      "RETAIL": 360000.00,
      "WHOLESALE": 90000.00
    },
    "top_profit_margin": 45.5
  },
  "results": [
    {
      "period": "2025-10",
      "revenue": 45000.00,
      "cost": 30000.00,
      "profit": 15000.00,
      "margin": 33.33,
      "order_count": 150
    }
  ]
}
```

---

### 2. Accounts Receivable (AR) Aging Report
**Endpoint:** `GET /reports/api/financial/ar-aging/`

**Purpose:** Track outstanding customer credit and identify overdue accounts

**Data Sources:**
- `Customer` model: credit_balance, credit_limit
- `Sale` model: sales on credit
- `Payment` model: credit payments

**Features:**
- Total AR outstanding
- AR aging buckets (Current, 1-30 days, 31-60 days, 61-90 days, 90+ days)
- Customer-level aging breakdown
- Credit utilization percentage
- Days sales outstanding (DSO)
- At-risk customers (high balance, overdue)

**Aging Buckets:**
- **Current:** 0-30 days
- **31-60 days:** Slightly overdue
- **61-90 days:** Overdue
- **90+ days:** Seriously overdue

**Query Parameters:**
- `as_of_date` (default: today)
- `customer_id` (optional)
- `min_balance` (optional - filter small balances)
- `page`, `page_size`

**Response:**
```json
{
  "summary": {
    "total_ar_outstanding": 125000.00,
    "total_customers_with_balance": 45,
    "average_days_outstanding": 32.5,
    "aging_buckets": {
      "current": 85000.00,
      "1_30_days": 25000.00,
      "31_60_days": 10000.00,
      "61_90_days": 3000.00,
      "over_90_days": 2000.00
    },
    "percentage_overdue": 12.0,
    "at_risk_amount": 5000.00
  },
  "results": [
    {
      "customer_id": "uuid",
      "customer_name": "ABC Corp",
      "total_balance": 15000.00,
      "credit_limit": 20000.00,
      "utilization": 75.0,
      "current": 10000.00,
      "1_30_days": 3000.00,
      "31_60_days": 2000.00,
      "61_90_days": 0.00,
      "over_90_days": 0.00,
      "oldest_invoice_days": 45,
      "risk_level": "medium"
    }
  ]
}
```

---

### 3. Payment Collection Rates Report
**Endpoint:** `GET /reports/api/financial/collection-rates/`

**Purpose:** Track payment collection efficiency and patterns

**Data Sources:**
- `Payment` model: payment amounts, methods, dates
- `Sale` model: sales on credit
- Customer credit transactions

**Features:**
- Collection rate percentage (collected / total credit sales)
- Average collection period (days)
- Collection by payment method
- Monthly collection trends
- Outstanding vs collected comparison
- Collection efficiency score

**Query Parameters:**
- `start_date`, `end_date`
- `payment_method` (optional)
- `grouping`: daily, weekly, monthly

**Response:**
```json
{
  "summary": {
    "total_credit_sales": 200000.00,
    "total_collected": 175000.00,
    "collection_rate": 87.5,
    "outstanding": 25000.00,
    "average_collection_days": 28.5,
    "collection_by_method": {
      "CASH": 85000.00,
      "BANK_TRANSFER": 60000.00,
      "MOBILE_MONEY": 30000.00
    },
    "collection_efficiency": "Good"
  },
  "results": [
    {
      "period": "2025-10",
      "credit_issued": 45000.00,
      "collected": 38000.00,
      "collection_rate": 84.44,
      "outstanding": 7000.00,
      "avg_days_to_collect": 25
    }
  ]
}
```

---

### 4. Cash Flow Report
**Endpoint:** `GET /reports/api/financial/cash-flow/`

**Purpose:** Track cash inflows and outflows

**Data Sources:**
- `Payment` model: cash inflows
- `Sale` model: sales transactions
- Future: Expense tracking for outflows

**Features:**
- Cash inflows (from sales/payments)
- Cash balance trends
- Inflows by payment method
- Daily/weekly/monthly cash flow
- Net cash flow calculation

**Note:** Initial implementation focuses on **inflows only**. Outflows (expenses) will be added when expense tracking is available.

**Query Parameters:**
- `start_date`, `end_date`
- `storefront_id` (optional)
- `grouping`: daily, weekly, monthly

**Response:**
```json
{
  "summary": {
    "total_inflows": 450000.00,
    "total_outflows": 0.00,  // Not tracked yet
    "net_cash_flow": 450000.00,
    "opening_balance": 50000.00,
    "closing_balance": 500000.00,
    "inflows_by_method": {
      "CASH": 200000.00,
      "CARD": 150000.00,
      "BANK_TRANSFER": 100000.00
    }
  },
  "results": [
    {
      "period": "2025-10-01",
      "inflows": 15000.00,
      "outflows": 0.00,
      "net_flow": 15000.00,
      "running_balance": 515000.00
    }
  ]
}
```

---

## Implementation Plan

### Week 5: Revenue & Profit + AR Aging

#### Days 1-2: Revenue & Profit Analysis Report
**File:** `reports/views/financial_reports.py`

**Implementation:**
```python
class RevenueProfitReportView(BaseReportView):
    """Revenue and Profit Analysis"""
    
    def get(self, request):
        # Get business, date range
        # Query sales with profit calculations
        # Group by period (daily/weekly/monthly)
        # Calculate margins
        # Build summary and results
```

**Key Calculations:**
- Gross Profit = Revenue - COGS
- Gross Margin = (Gross Profit / Revenue) × 100
- Group by sale_type, payment_method
- Trend analysis over time

#### Days 3-4: AR Aging Report
**File:** `reports/views/financial_reports.py`

**Implementation:**
```python
class ARAgingReportView(BaseReportView):
    """Accounts Receivable Aging Analysis"""
    
    def get(self, request):
        # Get customers with credit balances
        # Calculate days outstanding for each
        # Bucket into aging categories
        # Calculate risk levels
        # Build aging summary
```

**Key Calculations:**
- Days Outstanding = Today - Last Credit Transaction Date
- Aging Buckets: Current, 1-30, 31-60, 61-90, 90+
- Credit Utilization = Balance / Credit Limit
- Risk Level: low, medium, high based on age and amount

### Week 6: Collection Rates + Cash Flow

#### Days 1-2: Collection Rates Report
**File:** `reports/views/financial_reports.py`

**Implementation:**
```python
class CollectionRatesReportView(BaseReportView):
    """Payment Collection Analysis"""
    
    def get(self, request):
        # Get credit sales in period
        # Get payments against credit
        # Calculate collection rates
        # Track average collection time
        # Group by period
```

**Key Calculations:**
- Collection Rate = (Collected / Credit Issued) × 100
- Avg Collection Days = Sum(days_to_collect) / Count(payments)
- Collection Efficiency: Excellent (>95%), Good (85-95%), Fair (75-85%), Poor (<75%)

#### Days 3-4: Cash Flow Report
**File:** `reports/views/financial_reports.py`

**Implementation:**
```python
class CashFlowReportView(BaseReportView):
    """Cash Flow Analysis (Inflows)"""
    
    def get(self, request):
        # Get all payments (inflows)
        # Group by period
        # Calculate running balance
        # Track by payment method
        # Build cash flow statement
```

**Key Calculations:**
- Total Inflows = Sum(all payments)
- Net Cash Flow = Inflows - Outflows (outflows = 0 for now)
- Running Balance = Previous Balance + Net Flow
- Group by payment method

### Week 7-8: Testing, Polish & Integration

#### Testing:
- Unit tests for all 4 reports
- Edge cases (no data, negative margins, etc.)
- Performance testing with large datasets
- Validation of calculations

#### Polish:
- Error messages and validation
- Documentation updates
- Code review and refactoring
- Query optimization

#### Integration:
- Update URLs
- Test all endpoints
- Frontend documentation
- API examples

---

## File Structure After Phase 3

```
reports/
├── views/
│   ├── __init__.py
│   ├── exports.py                     # Data exports
│   ├── automation.py                  # Automation
│   ├── sales_reports.py               # 4 sales reports (Phase 2)
│   └── financial_reports.py           # NEW - 4 financial reports (Phase 3)
│
├── services/
│   ├── report_base.py
│   ├── analytics_exporter.py          # (future)
│   └── financial_analytics.py         # NEW - Financial calculations
│
├── utils/
│   ├── __init__.py
│   ├── response.py
│   ├── date_utils.py
│   ├── aggregation.py
│   └── financial_calcs.py             # NEW - Financial formulas
│
└── urls.py                            # Updated with financial endpoints
```

---

## URL Updates

Add to `reports/urls.py`:

```python
# Financial Reports (Phase 3)
path('api/financial/revenue-profit/', RevenueProfitReportView.as_view(), name='revenue-profit-report'),
path('api/financial/ar-aging/', ARAgingReportView.as_view(), name='ar-aging-report'),
path('api/financial/collection-rates/', CollectionRatesReportView.as_view(), name='collection-rates-report'),
path('api/financial/cash-flow/', CashFlowReportView.as_view(), name='cash-flow-report'),
```

---

## Success Criteria

By end of Phase 3:
- ✅ 4/4 Financial reports functional
- ✅ AR aging with proper bucketing
- ✅ Collection rates calculated correctly
- ✅ Cash flow tracking (inflows)
- ✅ Revenue and profit analysis complete
- ✅ All tests passing
- ✅ Documentation updated

**Progress:** 8/16 total reports (50%)

---

## Key Decisions Made

### 1. Simplified Approach
- Focus on sales/payment data (exists)
- Skip expense tracking initially (can add later)
- Cash flow = inflows only for now

### 2. AR Aging Methodology
- Use customer credit balance
- Calculate from last transaction date
- 5 aging buckets (industry standard)

### 3. Collection Rates
- Track credit sales vs payments
- Calculate average collection period
- Provide efficiency scoring

### 4. Future-Proof Design
- Easy to add expense tracking later
- Room for full P&L statements
- Can integrate with bookkeeping module

---

## Ready to Start Implementation!

**First up: Revenue & Profit Analysis Report**

Shall I proceed? 🚀
