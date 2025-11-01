# Customer Segmentation API - Quick Reference

## Endpoint
```
GET /api/reports/customers/segmentation/
```

## Authentication
**Required**: Yes (Bearer token)

## Query Parameters

| Parameter | Type | Required | Default | Valid Values | Description |
|-----------|------|----------|---------|--------------|-------------|
| `segmentation_method` | string | No | `rfm` | `rfm`, `value`, `behavior` | Segmentation algorithm to use |
| `days` | integer | No | `90` | 1-9999 | Lookback period in days |
| `storefront_id` | integer | No | `null` | Valid storefront ID | Filter by specific storefront |
| `segment_name` | string | No | `null` | Segment name | Filter to specific segment |
| `segment_code` | string | No | `null` | Segment code | Filter to specific segment code |
| `export_format` | string | No | `null` | `csv`, `pdf` | Export format (returns file) |

## Response Format

### Success Response (200 OK)
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
          "Early access to new collections"
        ]
      }
    ]
  }
}
```

### Error Response (400 Bad Request)
```json
{
  "success": false,
  "error": "Invalid segmentation_method. Must be one of: rfm, value, behavior"
}
```

### Error Response (401 Unauthorized)
```json
{
  "detail": "Authentication credentials were not provided."
}
```

## RFM Segments

| Segment Name | Code | Description | Customer Profile |
|--------------|------|-------------|------------------|
| Champions | R5F5M5 | Recent, frequent, high spenders | Best customers - high value, highly engaged |
| Loyal Customers | R4F4M4 | Consistent, reliable purchasers | Regular high-value customers |
| Potential Loyalists | R4F2M3 | Recent customers with growth potential | Growing engagement, medium-high value |
| Promising | R3F2M2 | Moderate engagement, can be developed | Moderate activity, development opportunity |
| At Risk | R2F2M3 | Previously loyal but recent activity dipping | Was valuable, now declining |
| Need Attention | R2F3M3 | Valuable customers showing warning signs | Regular customers with warning signs |
| New Customers | R5F1M1 | Recently acquired, low frequency | Very recent first-time buyers |
| Hibernating | R1F1M2 | Low engagement across all metrics | Inactive, low engagement |

## RFM Scores

Each customer receives a score of 1-5 for each metric:

### Recency (R)
- **5**: Purchased within last 20% of timeframe (most recent)
- **4**: Purchased within 20-40% of timeframe
- **3**: Purchased within 40-60% of timeframe
- **2**: Purchased within 60-80% of timeframe
- **1**: Purchased within last 80-100% of timeframe (least recent)

### Frequency (F)
- **5**: Top 20% most orders
- **4**: 20-40% most orders
- **3**: 40-60% most orders
- **2**: 60-80% most orders
- **1**: Bottom 20% fewest orders

### Monetary (M)
- **5**: Top 20% highest spend
- **4**: 20-40% highest spend
- **3**: 40-60% highest spend
- **2**: 60-80% highest spend
- **1**: Bottom 20% lowest spend

## Usage Examples

### Example 1: Get all RFM segments for last 90 days
```bash
curl -X GET "https://api.example.com/api/reports/customers/segmentation/" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Example 2: Get at-risk customers for last 30 days
```bash
curl -X GET "https://api.example.com/api/reports/customers/segmentation/?days=30&segment_name=At%20Risk" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Example 3: Export PDF report for specific storefront
```bash
curl -X GET "https://api.example.com/api/reports/customers/segmentation/?storefront_id=5&export_format=pdf" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  --output segmentation-report.pdf
```

### Example 4: Get champions only for last 60 days
```bash
curl -X GET "https://api.example.com/api/reports/customers/segmentation/?days=60&segment_code=R5F5M5" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Example 5: Export CSV for all segments
```bash
curl -X GET "https://api.example.com/api/reports/customers/segmentation/?export_format=csv" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  --output segmentation-report.csv
```

## Insights Explained

### `highest_revenue_segment`
The segment that generates the most total revenue. Focus retention efforts here.

**Example**: "Champions" - These customers drive the highest revenue.

### `largest_segment`
The segment with the most customers by count. Indicates where most of your customer base sits.

**Example**: "Promising" - Most customers are in moderate engagement phase.

### `fastest_growing_segment`
The segment with the most growth potential or recent activity. Prioritizes:
1. Potential Loyalists
2. Promising
3. New Customers

**Example**: "Potential Loyalists" - These customers are growing their engagement.

### `needs_attention`
The segment with concerning metrics that needs intervention. Prioritizes:
1. At Risk
2. Need Attention
3. Hibernating

**Example**: "At Risk" - Previously valuable customers now declining.

## Recommended Actions by Segment

### Champions (R5F5M5)
1. Offer VIP loyalty perks
2. Invite to referral programs
3. Early access to new collections

### Loyal Customers (R4F4M4)
1. Cross-sell complementary products
2. Provide exclusive deals
3. Gather feedback for product development

### Potential Loyalists (R4F2M3)
1. Onboarding nurture campaigns
2. Educational content series
3. Limited-time incentives

### Promising (R3F2M2)
1. Encourage repeat purchases
2. Highlight popular items
3. Moderate discount offers

### At Risk (R2F2M3)
1. Send win-back offers
2. Trigger churn prevention drip
3. Survey to understand drop-off

### Need Attention (R2F3M3)
1. Personalized re-engagement emails
2. Loyalty program reminders
3. Special occasion outreach

### New Customers (R5F1M1)
1. Welcome series automation
2. First-purchase follow-up
3. Product recommendations

### Hibernating (R1F1M2)
1. Deep discount win-back
2. Re-activation campaign
3. Sunset messaging if unresponsive

## Caching

- **Cache Duration**: 600 seconds (10 minutes)
- **Cache Key Format**: `customer_segmentation:{business_id}:{start_date}:{end_date}:{method}:{storefront_id}`
- **Cache Invalidation**: Automatic time-based expiration

## Performance

- **Typical Response Time**: < 500ms (cached)
- **Typical Response Time**: 1-3s (uncached, 10k customers)
- **Recommended**: Use with reasonable date ranges (30-365 days)
- **Scalability**: Handles 100k+ customers efficiently

## Error Codes

| Status Code | Meaning | Solution |
|-------------|---------|----------|
| 200 | Success | Request processed successfully |
| 400 | Bad Request | Check parameter values and format |
| 401 | Unauthorized | Provide valid authentication token |
| 500 | Server Error | Contact support with request details |

## Data Freshness

- Calculations based on sales data in the database at query time
- Results cached for 10 minutes
- To get fresh data, wait for cache expiration or use different filter parameters

## Limitations

1. **RFM Only**: Currently only RFM segmentation is implemented
2. **Single Business**: Results scoped to authenticated user's business
3. **Completed Sales Only**: Only includes completed/partial sales, excludes pending/cancelled
4. **Memory-based Calculation**: Large datasets (>100k customers) may be slow on first run

## Future Methods

### Value Segmentation (Coming Soon)
- High Value (Top 20%)
- Medium Value (Middle 60%)
- Low Value (Bottom 20%)

### Behavior Segmentation (Planned)
- Product category affinity
- Shopping channel preference
- Seasonal buying patterns

---

**Version**: 1.0  
**Last Updated**: December 2024  
**Status**: Production Ready
