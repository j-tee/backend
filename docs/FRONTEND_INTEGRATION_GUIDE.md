# Frontend Integration Guide - Analytical Reports API

**Version:** 1.0  
**Date:** October 12, 2025  
**Backend Status:** All 16 reports implemented and tested  
**Base URL:** `/reports/api/`

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication & Permissions](#authentication--permissions)
3. [Common Patterns](#common-patterns)
4. [Sales Reports](#sales-reports)
5. [Financial Reports](#financial-reports)
6. [Inventory Reports](#inventory-reports)
7. [Customer Reports](#customer-reports)
8. [Error Handling](#error-handling)
9. [Best Practices](#best-practices)
10. [Example Implementations](#example-implementations)

---

## Overview

### Report Categories

All 16 analytical reports are organized into 4 categories:

| Category | Endpoints | Purpose |
|----------|-----------|---------|
| **Sales** | 4 reports | Revenue tracking, product performance, customer behavior |
| **Financial** | 4 reports | Profit analysis, AR aging, collections, cash flow |
| **Inventory** | 4 reports | Stock levels, alerts, movements, warehouse analytics |
| **Customer** | 4 reports | Lifetime value, segmentation, patterns, retention |

### Standard Response Format

All reports follow this consistent structure:

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
    "customer_type": "RETAIL",
    "warehouse_id": "uuid-here"
  },
  "summary": {
    // High-level KPIs
  },
  "data": [
    // Detailed records (paginated)
  ],
  "pagination": {
    "count": 150,
    "next": "http://api.example.com/reports/api/sales/summary/?page=2",
    "previous": null,
    "page_size": 100,
    "total_pages": 2
  }
}
```

---

## Authentication & Permissions

### Required Headers

```javascript
const headers = {
  'Authorization': 'Bearer YOUR_ACCESS_TOKEN',
  'Content-Type': 'application/json'
};
```

### Permissions

**Required:** User must be authenticated  
**Role-based access:** Coming in future updates (currently all authenticated users have access)

**Important:** Always check the response status:
- `200 OK` - Success
- `400 Bad Request` - Invalid parameters
- `401 Unauthorized` - Not authenticated
- `403 Forbidden` - No permission
- `500 Internal Server Error` - Server error

---

## Common Patterns

### Date Filtering

**All reports** support `start_date` and `end_date` parameters:

```javascript
// Format: YYYY-MM-DD
const params = {
  start_date: '2024-01-01',
  end_date: '2024-12-31'
};
```

**Default behavior if not provided:**
- Sales Reports: Last 30 days
- Financial Reports: Current month
- Inventory Reports: Current state (or 30 days for movements)
- Customer Reports: Last 90 days (varies by report)

### Pagination

**Default page size:** 100 records  
**Custom page size:** Use `page_size` parameter (max: 1000)

```javascript
const params = {
  page: 1,
  page_size: 50
};
```

**Frontend pagination handling:**
```javascript
// Check if more pages exist
if (response.pagination.next) {
  // Load next page
  fetchNextPage(response.pagination.next);
}
```

### Filtering by Entity Type

Many reports support filtering by:
- **Customer Type:** `customer_type=RETAIL` or `WHOLESALE`
- **Payment Method:** `payment_method=cash`, `credit_card`, `bank_transfer`, `mobile_money`, `credit`
- **Warehouse:** `warehouse_id=uuid-here`
- **Product Category:** `category=Electronics`

---

## Sales Reports

### 1. Sales Summary Report

**Endpoint:** `GET /reports/api/sales/summary/`

**Purpose:** High-level sales overview with daily/weekly/monthly breakdowns

**Query Parameters:**
```javascript
{
  start_date: 'YYYY-MM-DD',      // Optional, default: 30 days ago
  end_date: 'YYYY-MM-DD',        // Optional, default: today
  warehouse_id: 'uuid',          // Optional, filter by warehouse
  customer_type: 'RETAIL|WHOLESALE', // Optional
  payment_method: 'cash|credit_card|...', // Optional
  grouping: 'daily|weekly|monthly', // Optional, default: daily
  page: 1,                       // Optional
  page_size: 100                 // Optional
}
```

**Response Structure:**
```json
{
  "report_name": "Sales Summary Report",
  "generated_at": "2025-10-12T10:30:00Z",
  "period": {
    "start_date": "2024-10-01",
    "end_date": "2024-10-12",
    "days": 12
  },
  "summary": {
    "total_revenue": "125000.00",
    "total_transactions": 450,
    "total_items_sold": 1200,
    "average_transaction_value": "277.78",
    "total_tax": "15000.00",
    "total_discount": "5000.00",
    "cash_sales": "75000.00",
    "credit_sales": "50000.00",
    "cash_percentage": 60.0,
    "credit_percentage": 40.0
  },
  "data": [
    {
      "period": "2024-10-12",
      "revenue": "12500.00",
      "transactions": 45,
      "items_sold": 120,
      "average_value": "277.78",
      "tax": "1500.00",
      "discount": "500.00"
    }
    // ... more periods
  ],
  "pagination": { /* standard pagination */ }
}
```

**Frontend Implementation Tips:**
- Use `grouping` parameter to switch between daily/weekly/monthly views
- Display summary metrics as KPI cards
- Use `data` array for charts (line/bar charts)
- Show cash vs credit breakdown with pie chart

---

### 2. Product Performance Report

**Endpoint:** `GET /reports/api/sales/product-performance/`

**Purpose:** Analyze which products are selling well

**Query Parameters:**
```javascript
{
  start_date: 'YYYY-MM-DD',
  end_date: 'YYYY-MM-DD',
  warehouse_id: 'uuid',
  category: 'string',           // Filter by product category
  min_quantity: 10,             // Minimum units sold
  sort_by: 'revenue|quantity|profit', // Default: revenue
  page: 1,
  page_size: 100
}
```

**Response Structure:**
```json
{
  "summary": {
    "total_products_sold": 150,
    "total_revenue": "500000.00",
    "total_profit": "150000.00",
    "total_quantity_sold": 5000,
    "average_profit_margin": 30.5,
    "top_product": "Product Name",
    "top_category": "Electronics"
  },
  "data": [
    {
      "product_name": "iPhone 15 Pro",
      "sku": "IPH15PRO",
      "category": "Electronics",
      "quantity_sold": 50,
      "revenue": "75000.00",
      "profit": "22500.00",
      "profit_margin": 30.0,
      "average_price": "1500.00",
      "rank": 1
    }
    // ... more products
  ]
}
```

**Frontend Implementation Tips:**
- Show top 10 products in a data table
- Use `rank` field to display position
- Color-code profit margin (green > 30%, yellow 15-30%, red < 15%)
- Display category filter as dropdown
- Use `sort_by` to allow user sorting

---

### 3. Customer Analytics Report

**Endpoint:** `GET /reports/api/sales/customer-analytics/`

**Purpose:** Analyze customer purchasing behavior

**Query Parameters:**
```javascript
{
  start_date: 'YYYY-MM-DD',
  end_date: 'YYYY-MM-DD',
  customer_type: 'RETAIL|WHOLESALE',
  storefront_id: 'uuid',        // optional single storefront scope
  storefront_ids: 'uuid,uuid',  // optional multi-storefront scope
  min_purchases: 5,             // Minimum number of purchases
  sort_by: 'revenue|purchases|average_value', // Default: revenue
  export_format: 'csv|pdf',     // optional export
  page: 1,
  page_size: 100
}
```

**Response Structure:**
```json
{
  "summary": {
    "total_customers": 250,
    "total_revenue": "1000000.00",
    "average_revenue_per_customer": "4000.00",
    "total_transactions": 1500,
    "average_transactions_per_customer": 6.0,
    "retail_customers": 200,
    "wholesale_customers": 50,
    "retail_revenue_percentage": 60.0,
    "wholesale_revenue_percentage": 40.0
  },
  "data": [
    {
      "customer_name": "ABC Corp",
      "customer_type": "WHOLESALE",
      "total_revenue": "50000.00",
      "total_purchases": 25,
      "average_purchase_value": "2000.00",
      "last_purchase_date": "2024-10-10",
      "days_since_last_purchase": 2,
      "rank": 1
    }
    // ... more customers
  ]
}
```

**Frontend Implementation Tips:**
- Highlight customers who haven't purchased recently (days_since_last_purchase > 30)
- Show retail vs wholesale split with donut chart
- Allow filtering by customer type
- Display top customers in a leaderboard style
- Surface storefront scope when filtering so teams know which locations feed the leaderboard

---

### 4. Revenue Trends Report

**Endpoint:** `GET /reports/api/sales/revenue-trends/`

**Purpose:** Track revenue patterns over time with growth analysis

**Query Parameters:**
```javascript
{
  start_date: 'YYYY-MM-DD',
  end_date: 'YYYY-MM-DD',
  grouping: 'daily|weekly|monthly', // Default: daily
  compare_previous_period: true,    // Include comparison data
  warehouse_id: 'uuid',
  customer_type: 'RETAIL|WHOLESALE'
}
```

**Response Structure:**
```json
{
  "summary": {
    "total_revenue": "500000.00",
    "average_daily_revenue": "16129.03",
    "highest_revenue_day": "2024-10-05",
    "highest_revenue_amount": "25000.00",
    "lowest_revenue_day": "2024-10-01",
    "lowest_revenue_amount": "8000.00",
    "revenue_growth": 15.5,        // Percentage growth
    "trend": "INCREASING"           // INCREASING|DECREASING|STABLE
  },
  "data": [
    {
      "period": "2024-10-12",
      "revenue": "18000.00",
      "transactions": 50,
      "growth_from_previous": 12.5,  // % change from previous period
      "trend_indicator": "↑"         // ↑ or ↓ or →
    }
    // ... more periods
  ],
  "comparison": {
    "current_period_revenue": "500000.00",
    "previous_period_revenue": "435000.00",
    "change_amount": "65000.00",
    "change_percentage": 15.0,
    "trend": "INCREASING"
  }
}
```

**Frontend Implementation Tips:**
- Use line chart with trend indicators
- Show growth percentages with color coding (green positive, red negative)
- Display comparison period data in tooltip
- Add trend arrows (↑↓→) for quick visual feedback
- Highlight highest/lowest revenue days

---

## Financial Reports

### 1. Revenue & Profit Analysis Report

**Endpoint:** `GET /reports/api/financial/revenue-profit/`

**Purpose:** Detailed profit margin analysis

**Query Parameters:**
```javascript
{
  start_date: 'YYYY-MM-DD',
  end_date: 'YYYY-MM-DD',
  grouping: 'daily|weekly|monthly',
  warehouse_id: 'uuid',
  min_profit_margin: 10.0        // Filter by minimum margin %
}
```

**Response Structure:**
```json
{
  "summary": {
    "total_revenue": "1000000.00",
    "total_profit": "300000.00",
    "overall_profit_margin": 30.0,
    "total_cost": "700000.00",
    "highest_margin_period": "2024-10-05",
    "highest_margin_percentage": 35.5,
    "lowest_margin_period": "2024-10-01",
    "lowest_margin_percentage": 22.0
  },
  "data": [
    {
      "period": "2024-10-12",
      "revenue": "50000.00",
      "cost": "32000.00",
      "profit": "18000.00",
      "profit_margin": 36.0,
      "margin_trend": "↑"
    }
    // ... more periods
  ]
}
```

**Frontend Implementation Tips:**
- Display dual-axis chart (revenue bars + margin line)
- Color-code margins: green > 30%, yellow 15-30%, red < 15%
- Show margin trend with arrows
- Add goal line for target profit margin

---

### 2. Accounts Receivable (AR) Aging Report

**Endpoint:** `GET /reports/api/financial/ar-aging/`

**Purpose:** Track outstanding customer credit balances

**Query Parameters:**
```javascript
{
  as_of_date: 'YYYY-MM-DD',      // Optional, default: today
  customer_type: 'RETAIL|WHOLESALE',
  min_balance: 1000.00,          // Minimum outstanding balance
  include_zero_balance: false,   // Include customers with no balance
  page: 1,
  page_size: 100
}
```

**Response Structure:**
```json
{
  "summary": {
    "total_outstanding": "250000.00",
    "total_customers_with_balance": 75,
    "average_balance": "3333.33",
    "current_0_30_days": "100000.00",
    "days_31_60": "75000.00",
    "days_61_90": "50000.00",
    "over_90_days": "25000.00",
    "percentage_current": 40.0,
    "percentage_overdue": 60.0
  },
  "aging_buckets": [
    {
      "bucket": "0-30 days",
      "amount": "100000.00",
      "percentage": 40.0,
      "customer_count": 30
    },
    {
      "bucket": "31-60 days",
      "amount": "75000.00",
      "percentage": 30.0,
      "customer_count": 25
    },
    {
      "bucket": "61-90 days",
      "amount": "50000.00",
      "percentage": 20.0,
      "customer_count": 15
    },
    {
      "bucket": "Over 90 days",
      "amount": "25000.00",
      "percentage": 10.0,
      "customer_count": 5
    }
  ],
  "data": [
    {
      "customer_name": "ABC Corp",
      "customer_type": "WHOLESALE",
      "total_credit_limit": "100000.00",
      "total_outstanding": "75000.00",
      "available_credit": "25000.00",
      "utilization_percentage": 75.0,
      "current_0_30": "50000.00",
      "days_31_60": "20000.00",
      "days_61_90": "5000.00",
      "over_90": "0.00",
      "oldest_invoice_days": 45,
      "risk_level": "MEDIUM"        // LOW|MEDIUM|HIGH
    }
    // ... more customers
  ]
}
```

**Frontend Implementation Tips:**
- Use stacked bar chart for aging buckets
- Color-code risk levels: green (LOW), yellow (MEDIUM), red (HIGH)
- Show credit utilization with progress bar
- Highlight customers over 90 days in red
- Add filter for risk level
- Display utilization percentage with visual indicator

---

### 3. Collection Rates Report

**Endpoint:** `GET /reports/api/financial/collection-rates/`

**Purpose:** Track credit payment collection efficiency

**Query Parameters:**
```javascript
{
  start_date: 'YYYY-MM-DD',
  end_date: 'YYYY-MM-DD',
  grouping: 'daily|weekly|monthly',
  storefront_id: 'uuid',        // optional single storefront scope
  storefront_ids: 'uuid,uuid',  // optional multi-storefront scope
  export_format: 'csv|pdf'      // optional export (CSV available)
}
```

**Response Structure:**
```json
{
  "success": true,
  "data": {
    "summary": {
      "total_credit_sales_amount": "500000.00",
      "total_collected_amount": "420000.00",
      "outstanding_amount": "80000.00",
      "overall_collection_rate": 84.0,
      "average_collection_period_days": 25.5,
      "retail": {
        "credit_sales_amount": 320000.0,
        "collected_amount": 280000.0,
        "collection_rate": 87.5,
        "average_collection_period_days": 23.1
      },
      "wholesale": {
        "credit_sales_amount": 180000.0,
        "collected_amount": 140000.0,
        "collection_rate": 77.8,
        "average_collection_period_days": 29.4
      }
    },
    "results": [
      {
        "period": "2024-10",
        "period_start": "2024-10-01",
        "period_end": "2024-11-01",
        "credit_sales_amount": "150000.00",
        "collected_amount": "120000.00",
        "collection_rate": 80.0,
        "average_days_to_collect": 22.3,
        "retail": {
          "collection_rate": 82.5
        },
        "wholesale": {
          "collection_rate": 75.5
        }
      }
    ],
    "metadata": {
      "filters_applied": {
        "storefront_id": "uuid-primary",
        "storefront_ids": ["uuid-primary"],
        "storefront_names": ["Flagship Store"],
        "grouping": "monthly"
      }
    }
  }
}
```

**Frontend Implementation Tips:**
- Show collection rate trend with line chart
- Display target collection rate (e.g., 90%) as reference line
- Color-code rates: green > 80%, yellow 60-80%, red < 60%
- Show average days to collect as KPI

---

### 4. Cash Flow Report

**Endpoint:** `GET /reports/api/financial/cash-flow/`

**Purpose:** Track cash movements (cash on hand)

**Query Parameters:**
```javascript
{
  start_date: 'YYYY-MM-DD',
  end_date: 'YYYY-MM-DD',
  grouping: 'daily|weekly|monthly',
  storefront_id: 'uuid',        // optional single storefront scope
  storefront_ids: 'uuid,uuid',  // optional multi-storefront scope
  payment_method: 'cash|card|bank_transfer|mobile_money|momo',
  export_format: 'csv|pdf'      // optional export (CSV available)
}
```

**Response Structure:**
```json
{
  "success": true,
  "data": {
    "summary": {
      "total_inflows": "125000.00",
      "total_outflows": "0.00",
      "net_cash_flow": "125000.00",
      "opening_balance": "0.00",
      "closing_balance": "125000.00",
      "inflow_by_method": {
        "CASH": "80000.00",
        "CARD": "30000.00",
        "BANK_TRANSFER": "15000.00",
        "MOBILE_MONEY": "0.00"
      },
      "retail": {
        "inflows": 90000.0,
        "transaction_count": 45,
        "average_transaction": 2000.0
      },
      "wholesale": {
        "inflows": 35000.0,
        "transaction_count": 5,
        "average_transaction": 7000.0
      }
    },
    "results": [
      {
        "period": "2024-10-12",
        "period_start": "2024-10-12",
        "period_end": "2024-10-13",
        "inflows": "5000.00",
        "outflows": "0.00",
        "net_flow": "5000.00",
        "running_balance": "5000.00",
        "transaction_count": 12
      }
    ],
    "metadata": {
      "filters_applied": {
        "storefront_id": "uuid-primary",
        "storefront_ids": ["uuid-primary"],
        "storefront_names": ["Flagship Store"],
        "grouping": "daily",
        "payment_method": "CASH"
      },
      "note": "Tier 1: Only tracking inflows (payments). Outflows will be added in Tier 2."
    }
  }
}
```

**Frontend Implementation Tips:**
- Use waterfall chart to show cash flow
- Display opening/closing balance prominently
- Color-code net flow: green (positive), red (negative)
- Show cash in vs cash out with separate lines

---

## Inventory Reports

### 1. Stock Levels Summary Report

**Endpoint:** `GET /reports/api/inventory/stock-levels/`

**Purpose:** Current inventory status across warehouses

**Query Parameters:**
```javascript
{
  warehouse_id: 'uuid',          // Optional, filter by warehouse
  category: 'string',            // Optional, filter by category
  low_stock_only: false,         // Show only low stock items
  min_quantity: 0,               // Minimum quantity threshold
  page: 1,
  page_size: 100
}
```

**Response Structure:**
```json
{
  "summary": {
    "total_products": 500,
    "total_quantity": 15000,
    "total_value": "1500000.00",
    "low_stock_items": 25,
    "out_of_stock_items": 5,
    "overstocked_items": 10
  },
  "data": [
    {
      "product_name": "iPhone 15 Pro",
      "sku": "IPH15PRO",
      "warehouse_name": "Main Warehouse",
      "category": "Electronics",
      "current_quantity": 50,
      "unit_cost": "1200.00",
      "total_value": "60000.00",
      "reorder_level": 10,
      "reorder_quantity": 20,
      "max_stock_level": 100,
      "stock_status": "ADEQUATE"     // LOW|OUT|ADEQUATE|OVERSTOCKED
    }
    // ... more products
  ]
}
```

**Frontend Implementation Tips:**
- Color-code stock status: red (OUT/LOW), yellow (ADEQUATE), green (overstocked)
- Show stock level as progress bar (current/max)
- Add badge for low stock items
- Display total value prominently
- Allow filtering by warehouse and category

---

### 2. Low Stock Alerts Report

**Endpoint:** `GET /reports/api/inventory/low-stock-alerts/`

**Purpose:** Products needing reorder

**Query Parameters:**
```javascript
{
  warehouse_id: 'uuid',
  category: 'string',
  urgency: 'critical|high|medium', // Filter by urgency level
  page: 1,
  page_size: 100
}
```

**Response Structure:**
```json
{
  "summary": {
    "total_alerts": 30,
    "critical_alerts": 5,          // Out of stock
    "high_priority_alerts": 10,    // Below reorder level
    "medium_priority_alerts": 15,  // Near reorder level
    "estimated_reorder_cost": "150000.00"
  },
  "data": [
    {
      "product_name": "MacBook Pro",
      "sku": "MBP16",
      "warehouse_name": "Main Warehouse",
      "current_quantity": 0,
      "reorder_level": 5,
      "reorder_quantity": 10,
      "days_of_stock_remaining": 0,
      "sales_velocity": 2.5,         // Units per day (30-day avg)
      "suggested_order_quantity": 15,
      "estimated_cost": "30000.00",
      "urgency": "CRITICAL",         // CRITICAL|HIGH|MEDIUM
      "last_restock_date": "2024-09-15"
    }
    // ... more alerts
  ]
}
```

**Frontend Implementation Tips:**
- Sort by urgency (critical first)
- Color-code urgency: red (CRITICAL), orange (HIGH), yellow (MEDIUM)
- Show days of stock remaining with countdown
- Display suggested order quantity
- Add "Create PO" button for each item
- Show total estimated reorder cost

---

### 3. Stock Movement History Report

**Endpoint:** `GET /reports/api/inventory/stock-movements/`

**Purpose:** Track inventory changes (additions, sales, adjustments)

**Query Parameters:**
```javascript
{
  start_date: 'YYYY-MM-DD',
  end_date: 'YYYY-MM-DD',
  warehouse_id: 'uuid',
  product_id: 'uuid',            // Filter by specific product
  movement_type: 'ADDITION|SALE|ADJUSTMENT', // Filter by type
  adjustment_type: 'THEFT|DAMAGE|EXPIRED|...', // For adjustments only
  page: 1,
  page_size: 100
}
```

**Response Structure:**
```json
{
  "summary": {
    "total_movements": 5000,
    "total_additions": 2000,
    "total_sales": 2500,
    "total_adjustments": 500,
    "total_shrinkage": 100,        // THEFT + DAMAGE + EXPIRED + etc.
    "shrinkage_value": "25000.00",
    "net_quantity_change": -600
  },
  "data": [
    {
      "date": "2024-10-12",
      "product_name": "iPhone 15",
      "warehouse_name": "Main Warehouse",
      "movement_type": "SALE",
      "quantity": -5,                // Negative for outbound
      "reference": "SALE-12345",
      "notes": "Customer purchase",
      "performed_by": "John Doe"
    },
    {
      "date": "2024-10-11",
      "product_name": "iPhone 15",
      "warehouse_name": "Main Warehouse",
      "movement_type": "ADJUSTMENT",
      "adjustment_type": "DAMAGE",
      "quantity": -2,
      "reference": "ADJ-6789",
      "notes": "Water damage",
      "performed_by": "Jane Smith"
    }
    // ... more movements
  ]
}
```

**Frontend Implementation Tips:**
- Use different icons for movement types (📥 addition, 📤 sale, ⚙️ adjustment)
- Color-code adjustments: red for shrinkage (THEFT, DAMAGE, etc.), blue for corrections
- Show quantity with +/- prefix
- Display reference as clickable link
- Add filter chips for movement types
- Show shrinkage percentage of total inventory

---

### 4. Warehouse Analytics Report

**Endpoint:** `GET /reports/api/inventory/warehouse-analytics/`

**Purpose:** Warehouse performance and inventory turnover

**Query Parameters:**
```javascript
{
  start_date: 'YYYY-MM-DD',      // For turnover calculations
  end_date: 'YYYY-MM-DD',
  warehouse_id: 'uuid',          // Optional, compare all if not provided
  category: 'string'
}
```

**Response Structure:**
```json
{
  "summary": {
    "total_warehouses": 3,
    "total_inventory_value": "2000000.00",
    "average_turnover_rate": 8.5,
    "total_products_tracked": 500,
    "total_quantity_on_hand": 20000
  },
  "data": [
    {
      "warehouse_name": "Main Warehouse",
      "warehouse_location": "Downtown",
      "total_products": 300,
      "total_quantity": 12000,
      "inventory_value": "1200000.00",
      "turnover_rate": 10.5,        // Times per year
      "avg_days_to_sell": 35,
      "fast_moving_items": 50,       // Velocity > 6 units/month
      "slow_moving_items": 30,       // Velocity 0.5-2 units/month
      "dead_stock_items": 5,         // Velocity < 0.5 units/month
      "utilization_percentage": 85.0 // Stock vs capacity
    }
    // ... more warehouses
  ]
}
```

**Frontend Implementation Tips:**
- Display warehouses as comparison cards
- Show turnover rate with gauge chart
- Color-code turnover: green (>8), yellow (4-8), red (<4)
- Display fast/slow/dead stock breakdown with donut chart
- Show utilization as progress bar
- Add warehouse comparison table

---

## Customer Reports

### 1. Customer Lifetime Value (CLV) Report

**Endpoint:** `GET /reports/api/customer/lifetime-value/`

**Purpose:** Identify most valuable customers

**Query Parameters:**
```javascript
{
  start_date: 'YYYY-MM-DD',      // Customer creation date filter
  end_date: 'YYYY-MM-DD',
  customer_type: 'RETAIL|WHOLESALE',
  min_revenue: 10000.00,         // Minimum total revenue
  min_profit: 5000.00,           // Minimum total profit
  sort_by: 'revenue|profit|orders|aov', // Default: revenue
  page: 1,
  page_size: 100
}
```

**Response Structure:**
```json
{
  "summary": {
    "total_customers": 500,
    "total_revenue": "5000000.00",
    "total_profit": "1500000.00",
    "average_clv": "10000.00",
    "average_profit_per_customer": "3000.00",
    "top_10_percent_contribution": 45.5  // % of revenue from top 10%
  },
  "data": [
    {
      "customer_name": "ABC Corporation",
      "customer_type": "WHOLESALE",
      "total_revenue": "250000.00",
      "total_profit": "75000.00",
      "profit_margin": 30.0,
      "total_orders": 50,
      "average_order_value": "5000.00",
      "days_as_customer": 365,
      "purchase_frequency_days": 7.3,  // Avg days between purchases
      "last_purchase_date": "2024-10-10",
      "rank": 1
    }
    // ... more customers
  ]
}
```

**Frontend Implementation Tips:**
- Display top 10 customers in VIP list
- Show rank with medal icons (🥇🥈🥉)
- Display CLV trend over time
- Show profit margin with color coding
- Add "Top 10% Club" badge for elite customers
- Display purchase frequency as timeline

---

### 2. Customer Segmentation Report

**Endpoint:** `GET /reports/api/customer/segmentation/`

**Purpose:** Group customers by behavior and value (RFM Analysis)

**Query Parameters:**
```javascript
{
  segment_type: 'rfm|tier|credit|all', // Default: all
  customer_type: 'RETAIL|WHOLESALE',
  include_inactive: false        // Include customers with no recent purchases
}
```

**Response Structure:**
```json
{
  "summary": {
    "total_customers": 500,
    "total_segments": 8,
    "largest_segment": "Loyal Customers",
    "smallest_segment": "Lost"
  },
  "rfm_segments": [
    {
      "segment_name": "Champions",
      "description": "Recent, frequent, high-value customers",
      "customer_count": 50,
      "percentage": 10.0,
      "avg_revenue": "8000.00",
      "avg_recency_days": 5,
      "avg_frequency": 20,
      "avg_monetary_value": "8000.00",
      "recommended_action": "Reward and retain with VIP treatment"
    },
    {
      "segment_name": "Loyal Customers",
      "description": "Consistent buyers with good value",
      "customer_count": 100,
      "percentage": 20.0,
      "avg_revenue": "5000.00",
      "avg_recency_days": 15,
      "avg_frequency": 12,
      "avg_monetary_value": "5000.00",
      "recommended_action": "Upsell and cross-sell opportunities"
    },
    {
      "segment_name": "At Risk",
      "description": "Previously valuable, now inactive",
      "customer_count": 30,
      "percentage": 6.0,
      "avg_revenue": "6000.00",
      "avg_recency_days": 60,
      "avg_frequency": 15,
      "avg_monetary_value": "6000.00",
      "recommended_action": "Win-back campaign with special offers"
    }
    // ... 8 segments total
  ],
  "tier_segments": [
    {
      "tier": "VIP",
      "description": "Top 20% by revenue",
      "customer_count": 100,
      "percentage": 20.0,
      "total_revenue": "2250000.00",
      "avg_revenue": "22500.00",
      "revenue_contribution": 45.0
    },
    {
      "tier": "Regular",
      "description": "Active customers (middle 60%)",
      "customer_count": 300,
      "percentage": 60.0,
      "total_revenue": "2250000.00",
      "avg_revenue": "7500.00",
      "revenue_contribution": 45.0
    },
    {
      "tier": "New",
      "description": "Customers acquired in last 30 days",
      "customer_count": 50,
      "percentage": 10.0,
      "total_revenue": "250000.00",
      "avg_revenue": "5000.00",
      "revenue_contribution": 5.0
    },
    {
      "tier": "At-Risk",
      "description": "No purchase in 90+ days",
      "customer_count": 50,
      "percentage": 10.0,
      "total_revenue": "250000.00",
      "avg_revenue": "5000.00",
      "revenue_contribution": 5.0
    }
  ],
  "credit_segments": [
    {
      "segment": "High Credit Users",
      "description": "80-100% credit limit utilization",
      "customer_count": 20,
      "avg_utilization": 90.0,
      "total_outstanding": "180000.00",
      "risk_level": "HIGH"
    },
    {
      "segment": "Moderate Credit Users",
      "description": "50-80% credit limit utilization",
      "customer_count": 40,
      "avg_utilization": 65.0,
      "total_outstanding": "260000.00",
      "risk_level": "MEDIUM"
    },
    {
      "segment": "Low Credit Users",
      "description": "1-50% credit limit utilization",
      "customer_count": 60,
      "avg_utilization": 25.0,
      "total_outstanding": "150000.00",
      "risk_level": "LOW"
    },
    {
      "segment": "No Credit Used",
      "description": "0-1% credit limit utilization",
      "customer_count": 380,
      "avg_utilization": 0.0,
      "total_outstanding": "0.00",
      "risk_level": "NONE"
    }
  ]
}
```

**RFM Segments Explained:**
- **Champions:** R=5, F=5, M=5 (Best customers)
- **Loyal Customers:** R=4-5, F=4-5, M=4-5 (Consistent value)
- **Potential Loyalists:** R=4-5, F=2-3, M=3-4 (Can be developed)
- **New Customers:** R=5, F=1-2, M=1-3 (Recent first-timers)
- **At Risk:** R=2-3, F=3-4, M=4-5 (Valuable but slipping)
- **Can't Lose Them:** R=1-2, F=4-5, M=4-5 (Critical to win back)
- **Hibernating:** R=1-2, F=1-2, M=1-3 (Dormant)
- **Lost:** R=1, F=1-2, M=1-2 (Churned)

**Frontend Implementation Tips:**
- Display RFM segments as cards with recommended actions
- Use donut chart for segment distribution
- Color-code segments by value/risk
- Show tier breakdown with horizontal bar chart
- Display credit utilization with risk indicators
- Add action buttons for each segment (e.g., "Send Win-Back Email")
- Create customer lists filtered by segment

---

### 3. Purchase Pattern Analysis Report

**Endpoint:** `GET /reports/api/customer/purchase-patterns/`

**Purpose:** Understand buying behavior and preferences

**Query Parameters:**
```javascript
{
  start_date: 'YYYY-MM-DD',      // Default: 90 days ago
  end_date: 'YYYY-MM-DD',
  customer_id: 'uuid',           // Analyze specific customer
  customer_type: 'RETAIL|WHOLESALE',
  grouping: 'daily|weekly|monthly'
}
```

**Response Structure:**
```json
{
  "summary": {
    "total_transactions": 5000,
    "unique_customers": 450,
    "avg_basket_size": "250.00",
    "avg_items_per_transaction": 3.5,
    "most_popular_payment_method": "cash",
    "busiest_day_of_week": "Friday",
    "busiest_hour": 14              // 2 PM
  },
  "frequency_analysis": {
    "daily_purchases": 166.7,
    "weekly_purchases": 1166.7,
    "monthly_purchases": 5000,
    "avg_days_between_purchases": 0.18
  },
  "basket_analysis": [
    {
      "size_range": "$0-$100",
      "transaction_count": 1500,
      "percentage": 30.0,
      "avg_items": 2.1
    },
    {
      "size_range": "$100-$250",
      "transaction_count": 1750,
      "percentage": 35.0,
      "avg_items": 3.5
    },
    {
      "size_range": "$250-$500",
      "transaction_count": 1000,
      "percentage": 20.0,
      "avg_items": 5.2
    },
    {
      "size_range": "$500-$1000",
      "transaction_count": 500,
      "percentage": 10.0,
      "avg_items": 8.5
    },
    {
      "size_range": "$1000+",
      "transaction_count": 250,
      "percentage": 5.0,
      "avg_items": 15.0
    }
  ],
  "time_patterns": {
    "by_day_of_week": [
      {
        "day": "Monday",
        "transaction_count": 650,
        "avg_value": "240.00"
      },
      {
        "day": "Friday",
        "transaction_count": 900,
        "avg_value": "280.00"
      }
      // ... other days
    ],
    "by_hour": [
      {
        "hour": 9,
        "transaction_count": 150,
        "avg_value": "220.00"
      },
      {
        "hour": 14,
        "transaction_count": 320,
        "avg_value": "270.00"
      }
      // ... other hours
    ]
  },
  "payment_preferences": [
    {
      "payment_method": "cash",
      "transaction_count": 2500,
      "percentage": 50.0,
      "avg_value": "200.00"
    },
    {
      "payment_method": "credit_card",
      "transaction_count": 1500,
      "percentage": 30.0,
      "avg_value": "350.00"
    }
    // ... other payment methods
  ],
  "category_preferences": [
    {
      "category": "Electronics",
      "purchase_count": 800,
      "total_spent": "500000.00",
      "avg_spent": "625.00"
    },
    {
      "category": "Clothing",
      "purchase_count": 1200,
      "total_spent": "180000.00",
      "avg_spent": "150.00"
    }
    // ... top 10 categories
  ]
}
```

**Frontend Implementation Tips:**
- Use heatmap for day/hour patterns (darker = busier)
- Display basket size distribution with histogram
- Show payment method breakdown with pie chart
- Create day-of-week bar chart
- Display category preferences as horizontal bars
- Highlight peak times for staffing optimization
- Show "typical customer" profile based on averages

---

### 4. Customer Retention Metrics Report

**Endpoint:** `GET /reports/api/customer/retention/`

**Purpose:** Track customer loyalty and churn

**Query Parameters:**
```javascript
{
  start_date: 'YYYY-MM-DD',      // Default: 12 months ago
  end_date: 'YYYY-MM-DD',
  cohort_period: 'month|quarter|year', // Default: month
  customer_type: 'RETAIL|WHOLESALE'
}
```

**Response Structure:**
```json
{
  "summary": {
    "total_customers": 500,
    "active_customers": 450,       // Purchased in last 90 days
    "churned_customers": 50,
    "retention_rate": 90.0,
    "churn_rate": 10.0,
    "repeat_purchase_rate": 65.5,  // Customers with 2+ purchases
    "avg_customer_lifespan_days": 180,
    "new_customers_this_period": 100,
    "returning_customers": 400
  },
  "cohort_analysis": [
    {
      "cohort": "2024-01",
      "cohort_label": "January 2024",
      "initial_customers": 50,
      "current_active": 38,
      "churned": 12,
      "retention_rate": 76.0,
      "months_tracked": 10
    },
    {
      "cohort": "2024-02",
      "cohort_label": "February 2024",
      "initial_customers": 45,
      "current_active": 40,
      "churned": 5,
      "retention_rate": 88.9,
      "months_tracked": 9
    }
    // ... more cohorts
  ],
  "retention_trends": [
    {
      "month": "2024-10",
      "starting_customers": 480,
      "new_customers": 20,
      "churned_customers": 0,
      "ending_customers": 500,
      "retention_rate": 100.0,
      "churn_rate": 0.0
    },
    {
      "month": "2024-09",
      "starting_customers": 475,
      "new_customers": 15,
      "churned_customers": 10,
      "ending_customers": 480,
      "retention_rate": 97.9,
      "churn_rate": 2.1
    }
    // ... more months
  ],
  "repeat_purchase_analysis": {
    "one_time_buyers": 172,
    "repeat_buyers": 328,
    "one_time_percentage": 34.5,
    "repeat_percentage": 65.5,
    "avg_purchases_per_customer": 3.8
  }
}
```

**Retention Rate Calculation:**
```
Retention Rate = ((Ending Customers - New Customers) / Starting Customers) × 100
```

**Active Customer Definition:** Made a purchase in the last 90 days

**Frontend Implementation Tips:**
- Display retention rate trend with line chart
- Show cohort retention matrix (heatmap style)
- Color-code retention rates: green (>80%), yellow (60-80%), red (<60%)
- Display churn vs retention with dual gauge
- Show repeat buyer percentage prominently
- Create cohort comparison table
- Add "At Risk" customer list (no purchase in 60+ days)
- Display customer lifespan distribution

---

## Error Handling

### Standard Error Response

```json
{
  "error": "Invalid date format",
  "detail": "start_date must be in YYYY-MM-DD format",
  "status_code": 400
}
```

### Common Error Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| 400 | Bad Request | Invalid parameters, wrong date format, invalid filter values |
| 401 | Unauthorized | Missing or expired authentication token |
| 403 | Forbidden | User doesn't have permission to access this report |
| 404 | Not Found | Invalid endpoint or resource doesn't exist |
| 500 | Internal Server Error | Backend error, contact support |

### Frontend Error Handling Example

```javascript
async function fetchReport(endpoint, params) {
  try {
    const response = await fetch(`/reports/api/${endpoint}/`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      params: new URLSearchParams(params)
    });
    
    if (!response.ok) {
      const error = await response.json();
      
      switch (response.status) {
        case 400:
          showError(`Invalid request: ${error.detail}`);
          break;
        case 401:
          redirectToLogin();
          break;
        case 403:
          showError('You don\'t have permission to view this report');
          break;
        case 404:
          showError('Report not found');
          break;
        default:
          showError('An error occurred. Please try again.');
      }
      
      return null;
    }
    
    return await response.json();
  } catch (error) {
    console.error('Network error:', error);
    showError('Network error. Please check your connection.');
    return null;
  }
}
```

---

## Best Practices

### 1. Performance Optimization

**Use Date Ranges Wisely:**
```javascript
// ✅ Good - Specific date range
const params = {
  start_date: '2024-10-01',
  end_date: '2024-10-12'
};

// ❌ Avoid - Very large date ranges
const params = {
  start_date: '2020-01-01',
  end_date: '2024-12-31'  // 5 years of data!
};
```

**Implement Pagination:**
```javascript
// ✅ Load data progressively
const loadReportData = async (page = 1) => {
  const data = await fetchReport('sales/summary', {
    start_date: '2024-10-01',
    end_date: '2024-10-12',
    page: page,
    page_size: 50  // Reasonable page size
  });
  
  if (data.pagination.next) {
    // Load more when user scrolls or clicks "Load More"
  }
};

// ❌ Avoid - Loading everything at once
const data = await fetchReport('sales/summary', {
  page_size: 10000  // Too large!
});
```

### 2. Caching Strategy

**Cache Report Data:**
```javascript
const CACHE_DURATION = 5 * 60 * 1000; // 5 minutes

const cachedFetch = async (endpoint, params) => {
  const cacheKey = `${endpoint}-${JSON.stringify(params)}`;
  const cached = localStorage.getItem(cacheKey);
  
  if (cached) {
    const { data, timestamp } = JSON.parse(cached);
    if (Date.now() - timestamp < CACHE_DURATION) {
      return data;
    }
  }
  
  const data = await fetchReport(endpoint, params);
  localStorage.setItem(cacheKey, JSON.stringify({
    data,
    timestamp: Date.now()
  }));
  
  return data;
};
```

### 3. Date Range Validation

**Validate Before Sending:**
```javascript
const validateDateRange = (startDate, endDate) => {
  const start = new Date(startDate);
  const end = new Date(endDate);
  
  if (start > end) {
    showError('Start date must be before end date');
    return false;
  }
  
  const daysDiff = (end - start) / (1000 * 60 * 60 * 24);
  if (daysDiff > 365) {
    showWarning('Large date range may take longer to load');
  }
  
  return true;
};
```

### 4. Loading States

**Show Loading Indicators:**
```javascript
const ReportComponent = () => {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  
  const loadReport = async () => {
    setLoading(true);
    try {
      const result = await fetchReport('sales/summary', params);
      setData(result);
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div>
      {loading && <LoadingSpinner />}
      {data && <ReportDisplay data={data} />}
    </div>
  );
};
```

### 5. Export Functionality

**Generate CSV from Report Data:**
```javascript
const exportToCSV = (data, filename) => {
  const headers = Object.keys(data[0]).join(',');
  const rows = data.map(row => 
    Object.values(row).map(val => `"${val}"`).join(',')
  );
  
  const csv = [headers, ...rows].join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = window.URL.createObjectURL(blob);
  
  const a = document.createElement('a');
  a.href = url;
  a.download = `${filename}-${new Date().toISOString()}.csv`;
  a.click();
};
```

---

## Example Implementations

### React Component Example

```jsx
import React, { useState, useEffect } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, Legend } from 'recharts';

const SalesSummaryReport = () => {
  const [loading, setLoading] = useState(false);
  const [reportData, setReportData] = useState(null);
  const [filters, setFilters] = useState({
    start_date: '2024-10-01',
    end_date: '2024-10-12',
    grouping: 'daily'
  });

  useEffect(() => {
    loadReport();
  }, [filters]);

  const loadReport = async () => {
    setLoading(true);
    try {
      const response = await fetch(
        `/reports/api/sales/summary/?${new URLSearchParams(filters)}`,
        {
          headers: {
            'Authorization': `Bearer ${getAuthToken()}`,
            'Content-Type': 'application/json'
          }
        }
      );

      if (response.ok) {
        const data = await response.json();
        setReportData(data);
      } else {
        console.error('Failed to load report');
      }
    } catch (error) {
      console.error('Error loading report:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <div>Loading report...</div>;
  }

  if (!reportData) {
    return <div>No data available</div>;
  }

  return (
    <div className="sales-summary-report">
      {/* Summary KPIs */}
      <div className="kpi-cards">
        <div className="kpi-card">
          <h3>Total Revenue</h3>
          <p>${reportData.summary.total_revenue}</p>
        </div>
        <div className="kpi-card">
          <h3>Transactions</h3>
          <p>{reportData.summary.total_transactions}</p>
        </div>
        <div className="kpi-card">
          <h3>Avg Transaction</h3>
          <p>${reportData.summary.average_transaction_value}</p>
        </div>
      </div>

      {/* Chart */}
      <div className="chart-container">
        <LineChart width={800} height={400} data={reportData.data}>
          <XAxis dataKey="period" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Line type="monotone" dataKey="revenue" stroke="#8884d8" />
          <Line type="monotone" dataKey="transactions" stroke="#82ca9d" />
        </LineChart>
      </div>

      {/* Filters */}
      <div className="filters">
        <select 
          value={filters.grouping}
          onChange={(e) => setFilters({...filters, grouping: e.target.value})}
        >
          <option value="daily">Daily</option>
          <option value="weekly">Weekly</option>
          <option value="monthly">Monthly</option>
        </select>
      </div>
    </div>
  );
};
```

### Vue.js Component Example

```vue
<template>
  <div class="customer-segmentation-report">
    <h2>Customer Segmentation</h2>
    
    <!-- Loading State -->
    <div v-if="loading" class="loading">
      Loading segmentation data...
    </div>
    
    <!-- RFM Segments -->
    <div v-else-if="reportData" class="segments">
      <div 
        v-for="segment in reportData.rfm_segments" 
        :key="segment.segment_name"
        class="segment-card"
        :class="getSegmentClass(segment.segment_name)"
      >
        <h3>{{ segment.segment_name }}</h3>
        <p class="description">{{ segment.description }}</p>
        <div class="metrics">
          <div class="metric">
            <span class="label">Customers:</span>
            <span class="value">{{ segment.customer_count }}</span>
          </div>
          <div class="metric">
            <span class="label">Avg Revenue:</span>
            <span class="value">${{ segment.avg_revenue }}</span>
          </div>
          <div class="metric">
            <span class="label">Percentage:</span>
            <span class="value">{{ segment.percentage }}%</span>
          </div>
        </div>
        <div class="action">
          <strong>Action:</strong> {{ segment.recommended_action }}
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'CustomerSegmentationReport',
  data() {
    return {
      loading: false,
      reportData: null,
      filters: {
        segment_type: 'rfm',
        customer_type: null
      }
    };
  },
  mounted() {
    this.loadReport();
  },
  methods: {
    async loadReport() {
      this.loading = true;
      try {
        const params = new URLSearchParams(this.filters);
        const response = await fetch(
          `/reports/api/customer/segmentation/?${params}`,
          {
            headers: {
              'Authorization': `Bearer ${this.getAuthToken()}`,
              'Content-Type': 'application/json'
            }
          }
        );
        
        if (response.ok) {
          this.reportData = await response.json();
        }
      } catch (error) {
        console.error('Error loading report:', error);
      } finally {
        this.loading = false;
      }
    },
    getSegmentClass(segmentName) {
      const classMap = {
        'Champions': 'segment-champions',
        'Loyal Customers': 'segment-loyal',
        'At Risk': 'segment-at-risk',
        'Lost': 'segment-lost'
      };
      return classMap[segmentName] || 'segment-default';
    },
    getAuthToken() {
      return localStorage.getItem('auth_token');
    }
  }
};
</script>

<style scoped>
.segment-card {
  border: 2px solid #ddd;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}

.segment-champions {
  border-color: #4CAF50;
  background-color: #E8F5E9;
}

.segment-at-risk {
  border-color: #FF9800;
  background-color: #FFF3E0;
}

.segment-lost {
  border-color: #F44336;
  background-color: #FFEBEE;
}
</style>
```

### Angular Service Example

```typescript
import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

interface ReportFilters {
  start_date?: string;
  end_date?: string;
  warehouse_id?: string;
  customer_type?: 'RETAIL' | 'WHOLESALE';
  page?: number;
  page_size?: number;
}

@Injectable({
  providedIn: 'root'
})
export class ReportsService {
  private baseUrl = '/reports/api';

  constructor(private http: HttpClient) {}

  getSalesSummary(filters: ReportFilters = {}): Observable<any> {
    let params = new HttpParams();
    Object.keys(filters).forEach(key => {
      if (filters[key]) {
        params = params.set(key, filters[key].toString());
      }
    });

    return this.http.get(`${this.baseUrl}/sales/summary/`, { params });
  }

  getProductPerformance(filters: ReportFilters = {}): Observable<any> {
    let params = new HttpParams();
    Object.keys(filters).forEach(key => {
      if (filters[key]) {
        params = params.set(key, filters[key].toString());
      }
    });

    return this.http.get(`${this.baseUrl}/sales/product-performance/`, { params });
  }

  getCustomerLifetimeValue(filters: ReportFilters = {}): Observable<any> {
    let params = new HttpParams();
    Object.keys(filters).forEach(key => {
      if (filters[key]) {
        params = params.set(key, filters[key].toString());
      }
    });

    return this.http.get(`${this.baseUrl}/customer/lifetime-value/`, { params });
  }

  getInventoryStockLevels(filters: ReportFilters = {}): Observable<any> {
    let params = new HttpParams();
    Object.keys(filters).forEach(key => {
      if (filters[key]) {
        params = params.set(key, filters[key].toString());
      }
    });

    return this.http.get(`${this.baseUrl}/inventory/stock-levels/`, { params });
  }

  // Add more report methods as needed
}
```

---

## Quick Reference

### All Report Endpoints

```
Sales Reports:
├── GET /reports/api/sales/summary/
├── GET /reports/api/sales/product-performance/
├── GET /reports/api/sales/customer-analytics/
└── GET /reports/api/sales/revenue-trends/

Financial Reports:
├── GET /reports/api/financial/revenue-profit/
├── GET /reports/api/financial/ar-aging/
├── GET /reports/api/financial/collection-rates/
└── GET /reports/api/financial/cash-flow/

Inventory Reports:
├── GET /reports/api/inventory/stock-levels/
├── GET /reports/api/inventory/low-stock-alerts/
├── GET /reports/api/inventory/stock-movements/
└── GET /reports/api/inventory/warehouse-analytics/

Customer Reports:
├── GET /reports/api/customer/lifetime-value/
├── GET /reports/api/customer/segmentation/
├── GET /reports/api/customer/purchase-patterns/
└── GET /reports/api/customer/retention/
```

### Common Query Parameters

| Parameter | Type | Used In | Description |
|-----------|------|---------|-------------|
| `start_date` | string (YYYY-MM-DD) | All reports | Filter start date |
| `end_date` | string (YYYY-MM-DD) | All reports | Filter end date |
| `page` | integer | All reports | Page number (pagination) |
| `page_size` | integer | All reports | Records per page (max: 1000) |
| `warehouse_id` | UUID | Sales, Inventory | Filter by warehouse |
| `customer_type` | enum | Sales, Financial, Customer | RETAIL or WHOLESALE |
| `grouping` | enum | Sales, Financial | daily, weekly, or monthly |
| `payment_method` | enum | Sales | cash, credit_card, etc. |
| `category` | string | Sales, Inventory | Product category |
| `sort_by` | enum | Various | Sorting field |

---

## Support & Questions

**Backend Developer:** Available for questions  
**Documentation Version:** 1.0  
**Last Updated:** October 12, 2025

**Common Questions:**

**Q: What's the maximum page size?**  
A: 1000 records. Default is 100. Use pagination for better performance.

**Q: Are dates inclusive or exclusive?**  
A: Inclusive. `start_date=2024-10-01&end_date=2024-10-12` includes both Oct 1 and Oct 12.

**Q: What timezone are dates in?**  
A: Server timezone (UTC). Frontend should convert to local timezone for display.

**Q: Can I filter by multiple warehouses?**  
A: Not currently. You can make multiple API calls or omit `warehouse_id` to get all warehouses.

**Q: How often is data updated?**  
A: Real-time. Reports reflect the current database state when the API is called.

**Q: Are there rate limits?**  
A: Not currently implemented. Use responsibly and implement caching on frontend.

---

**Happy Coding! 🚀**
