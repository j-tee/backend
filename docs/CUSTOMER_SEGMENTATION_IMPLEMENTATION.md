# Customer Segmentation API Implementation

## Overview
Complete implementation of the RFM (Recency-Frequency-Monetary) customer segmentation endpoint matching the frontend contract specified in `CustomerSegmentationPage.tsx`.

## Endpoint
```
GET /api/reports/customers/segmentation/
```

## Implementation Details

### 1. RFM Segmentation Algorithm

#### Core Methodology
- **Recency (R)**: Days since last purchase (lower is better)
- **Frequency (F)**: Total number of orders (higher is better)
- **Monetary (M)**: Total revenue generated (higher is better)

Each metric is scored on a 1-5 scale using quintile distribution:
- **Score 5**: Top 20% (best performers)
- **Score 4**: Next 20%
- **Score 3**: Middle 20%
- **Score 2**: Next 20%
- **Score 1**: Bottom 20% (worst performers)

#### Segment Classification
8 customer segments based on RFM scores:

| Segment | Code | R | F | M | Description |
|---------|------|---|---|---|-------------|
| Champions | R5F5M5 | ≥4 | ≥4 | ≥4 | Recent, frequent, high spenders |
| Loyal Customers | R4F4M4 | ≥4 | ≥4 | ≥3 | Consistent high-value customers |
| Potential Loyalists | R4F2M3 | ≥3 | ≥2 | ≥3 | Growing customers with potential |
| Promising | R3F2M2 | ≥3 | ≥2 | ≥2 | New customers showing promise |
| At Risk | R2F2M3 | ≤2 | ≥2 | ≥3 | Previously good customers fading |
| Need Attention | R2F3M3 | ≤3 | ≥3 | ≥3 | Declining engagement |
| New Customers | R5F1M1 | ≥4 | ≤2 | ≤2 | Very recent first-time buyers |
| Hibernating | R1F1M2 | ≤2 | ≤2 | Any | Inactive, low engagement |

### 2. API Contract

#### Request Parameters
- `segmentation_method` (required): Segmentation method
  - Valid values: `rfm`, `value`, `behavior`
  - Default: `rfm`
- `days` (optional): Lookback period in days
  - Default: 90
- `storefront_id` (optional): Filter by specific storefront
- `segment_name` (optional): Filter to specific segment name
- `segment_code` (optional): Filter to specific segment code
- `export_format` (optional): Export format
  - Valid values: `csv`, `pdf`

#### Response Structure
```json
{
  "success": true,
  "data": {
    "method": "rfm",
    "insights": {
      "highest_revenue_segment": "Champions",
      "largest_segment": "Promising",
      "fastest_growing_segment": "Potential Loyalists",
      "needs_attention": "At Risk"
    },
    "segments": [
      {
        "segment_name": "Champions",
        "segment_code": "R5F5M5",
        "description": "Recent, frequent, high spenders",
        "customer_count": 184,
        "total_revenue": 245678.50,
        "average_order_value": 256.34,
        "recency_score": 5,
        "frequency_score": 5,
        "monetary_score": 5,
        "characteristics": {
          "avg_days_since_last_purchase": 5,
          "avg_purchase_frequency": 12.3,
          "avg_total_spend": 1335.21
        },
        "recommended_actions": [
          "Offer VIP loyalty perks",
          "Invite to referral programs",
          "Early access to new products"
        ]
      }
      // ... more segments
    ]
  }
}
```

### 3. Key Features

#### Caching
- Results cached for 600 seconds (10 minutes)
- Cache key includes: business_id, date range, method, storefront_id
- Improves performance for repeated queries

#### Business Logic
- Only includes customers with activity in the specified date range
- Filters by business_id (automatic from user context)
- Optional storefront filtering
- Handles partial sales and refunds correctly
- Excludes cancelled/pending sales

#### Insights Calculation
- **Highest Revenue Segment**: Segment with highest total_revenue
- **Largest Segment**: Segment with most customers
- **Fastest Growing**: Prioritizes "Potential Loyalists", "Promising", "New Customers"
- **Needs Attention**: Highest count from "At Risk", "Need Attention", "Hibernating"

#### Export Formats
- **CSV**: Spreadsheet with insights and segment details
- **PDF**: Formatted report with tables and styling

### 4. Recommended Actions by Segment

Each segment includes 3+ recommended actions:

**Champions**
- Offer VIP loyalty perks
- Invite to referral programs
- Early access to new products

**Loyal Customers**
- Maintain engagement with personalized offers
- Request reviews and testimonials
- Exclusive member benefits

**Potential Loyalists**
- Encourage repeat purchases with incentives
- Upsell complementary products
- Build brand loyalty programs

**Promising**
- Nurture with targeted campaigns
- Offer onboarding discounts
- Collect feedback

**At Risk**
- Send re-engagement campaigns
- Offer win-back incentives
- Request feedback on experience

**Need Attention**
- Personalized outreach
- Special recovery discounts
- Survey to understand issues

**New Customers**
- Welcome series emails
- First purchase follow-up
- Educational content

**Hibernating**
- Strong win-back offers
- Survey for churn reasons
- Consider sunsetting if unresponsive

### 5. Implementation Files

#### Modified Files
- `reports/views/customer_reports.py` (CustomerSegmentationReportView class)
  - Added RFM_SEGMENTS dictionary with all 8 segments
  - Implemented `get()` method with validation and routing
  - Implemented `_calculate_segmentation()` dispatcher
  - Implemented `_calculate_rfm_segmentation()` core algorithm
  - Implemented `_calculate_quintile_score()` for scoring
  - Implemented `_classify_rfm_segment()` for segment assignment
  - Implemented `_calculate_insights()` for insights generation
  - Implemented `_empty_insights()` helper
  - Implemented `_build_cache_key()` for cache management
  - Implemented `_export_csv()` for CSV export
  - Implemented `_export_pdf()` for PDF export

#### New Files
- `reports/tests/test_customer_segmentation.py`
  - 25 comprehensive test cases covering:
    - RFM scoring accuracy
    - Segment classification
    - Insights calculation
    - Date range filtering
    - Storefront filtering
    - Segment filtering
    - Export formats (CSV, PDF)
    - Caching behavior
    - Revenue calculations
    - Empty dataset handling
    - Authentication
    - Edge cases

### 6. Testing

#### Test Coverage
```bash
# Run all customer segmentation tests
python manage.py test reports.tests.test_customer_segmentation

# Run specific test
python manage.py test reports.tests.test_customer_segmentation.CustomerSegmentationReportTestCase.test_rfm_scoring_accuracy
```

#### Test Scenarios
- ✅ Default RFM method
- ✅ Insights structure validation
- ✅ Segment structure validation
- ✅ RFM scoring accuracy
- ✅ Customer count accuracy
- ✅ Date range filtering
- ✅ Storefront filtering
- ✅ Segment name/code filtering
- ✅ Invalid method error handling
- ✅ CSV export format
- ✅ PDF export format
- ✅ Caching behavior
- ✅ Revenue calculation accuracy
- ✅ Empty dataset handling
- ✅ Authentication requirement
- ✅ Revenue-based sorting
- ✅ Value/Behavior method placeholders

### 7. Performance Considerations

#### Query Optimization
- Filters applied at database level
- Uses `select_related()` for customer data
- Aggregates in Python to avoid multiple queries
- Cache results to minimize recalculation

#### Scalability
- Handles large customer bases efficiently
- Quintile calculation is O(n log n)
- Segment classification is O(n)
- Total complexity: O(n log n) where n = number of customers

### 8. Future Enhancements

#### Planned Methods
- **Value Segmentation**: High/Medium/Low value tiers
- **Behavior Segmentation**: Product category affinity, channel preference

#### Potential Improvements
- Real-time segment transitions tracking
- Segment trend analysis over time
- Customer journey mapping
- Predictive churn modeling
- Automated campaign triggers

## Usage Examples

### Basic RFM Analysis
```bash
GET /api/reports/customers/segmentation/?segmentation_method=rfm
```

### Last 30 Days
```bash
GET /api/reports/customers/segmentation/?segmentation_method=rfm&days=30
```

### Specific Storefront
```bash
GET /api/reports/customers/segmentation/?segmentation_method=rfm&storefront_id=123
```

### Filter to Champions Only
```bash
GET /api/reports/customers/segmentation/?segmentation_method=rfm&segment_name=Champions
```

### Export as CSV
```bash
GET /api/reports/customers/segmentation/?segmentation_method=rfm&export_format=csv
```

### Export as PDF
```bash
GET /api/reports/customers/segmentation/?segmentation_method=rfm&export_format=pdf
```

## Integration Notes

### Frontend Contract
This implementation matches the exact contract expected by:
- `CustomerSegmentationPage.tsx`
- Field names, data types, and structure are 1:1 compatible
- All required fields are present
- Recommended actions are actionable and business-relevant

### Business Value
- Identify high-value customers for retention
- Target at-risk customers with win-back campaigns
- Nurture promising customers into loyalists
- Optimize marketing spend by segment
- Track customer lifecycle progression
- Data-driven customer engagement strategies

## Status
✅ **COMPLETE** - Fully implemented and ready for production use
- Core RFM algorithm implemented
- All 8 segments defined with business logic
- Comprehensive test suite (25 tests)
- CSV and PDF export functionality
- Caching for performance
- Full frontend contract compliance
