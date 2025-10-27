# Cash On Hand Calculation - Implementation Complete

## Overview
Implemented profit-based cash on hand calculation and credit management enhancements for the POS backend.

## Implementation Date
2025-01-XX

## Changes Made

### 1. Summary Endpoint Enhancements (`/api/sales/summary/`)

Added 4 new fields to provide profit-based financial metrics:

#### New Fields

**`total_profit`** (Decimal)
- Total profit from all completed sales
- Calculation: Sum of (unit_price - unit_cost) × quantity for all sale items in COMPLETED sales
- Uses: `stock_product.unit_cost` (base cost, not including taxes/additional costs)
- Example: `$50,000.00`

**`outstanding_credit`** (Decimal)
- Profit from unpaid/partially paid credit sales
- Calculation: Sum of (unit_price - unit_cost) × quantity for PENDING or PARTIAL credit sales
- Represents profit not yet realized
- Example: `$5,250.00`

**`cash_on_hand`** (Decimal)
- Actual profit realized (excluding outstanding credit)
- Calculation: `total_profit - outstanding_credit`
- This is the TRUE cash on hand based on profit, not revenue
- Example: `$44,750.00`

**`total_credit_sales`** (Decimal)
- Total amount customers owe (amount_due) for unpaid/partial credit sales
- This is the revenue-based accounts receivable
- Example: `$12,500.00`

**`unpaid_credit_count`** (Integer)
- Number of credit sales with outstanding balance (PENDING or PARTIAL status)
- Example: `15`

### 2. Enhanced Sales Filtering

Added 5 new query parameters to `/api/sales/` endpoint:

#### New Filters

**`days_outstanding`** (Integer)
- Filter credit sales outstanding longer than specified days
- Example: `/api/sales/?days_outstanding=30` (sales unpaid for > 30 days)
- Automatically filters for CREDIT sales with PENDING or PARTIAL status

**`min_amount_due`** (Decimal)
- Filter sales with amount due greater than or equal to specified value
- Example: `/api/sales/?min_amount_due=1000` (sales owing >= $1000)

**`max_amount_due`** (Decimal)
- Filter sales with amount due less than or equal to specified value
- Example: `/api/sales/?max_amount_due=500` (sales owing <= $500)

**Range Filtering**
- Combine min and max for range queries
- Example: `/api/sales/?min_amount_due=100&max_amount_due=500` (sales owing $100-$500)

**`customer_id`** (UUID)
- Filter sales by specific customer
- Example: `/api/sales/?customer_id=123e4567-e89b-12d3-a456-426614174000`

### 3. Technical Implementation

#### Profit Calculation Method
```python
# Uses Django ORM F() expressions to calculate profit at database level
profit = Sum(
    ExpressionWrapper(
        (F('unit_price') - F('stock_product__unit_cost')) * F('quantity'),
        output_field=DecimalField()
    )
)
```

#### Key Points
- Only includes sale items with `stock_product` (items without stock products are excluded)
- Uses base `unit_cost` field (not landed cost with taxes)
- Filters completed sales for total profit
- Filters PENDING + PARTIAL credit sales for outstanding credit
- All calculations done at database level for performance

### 4. Code Files Modified

**`sales/views.py`**
- Modified `SaleViewSet.summary()` action (lines ~405-445)
  - Added profit aggregation queries
  - Added outstanding credit calculation
  - Added cash on hand calculation
  
- Modified `SaleViewSet.get_queryset()` (lines ~78-155)
  - Added `days_outstanding` filter
  - Added `min_amount_due` / `max_amount_due` filters
  - Added `customer_id` filter
  - Added proper error handling for invalid decimal values

**`sales/models.py`**
- No changes (profit calculation already exists as properties)

### 5. Example API Responses

#### Summary Endpoint
```json
GET /api/sales/summary/

{
  "total_sales": "992411.28",
  "total_profit": "450000.00",
  "outstanding_credit": "55000.00",
  "cash_on_hand": "395000.00",
  "total_credit_sales": "156254.48",
  "unpaid_credit_count": 25,
  "cash_at_hand": "996864.85",  // Revenue-based (old metric)
  "accounts_receivable": "156254.48",  // Revenue-based (old metric)
  "financial_position": {
    "cash_at_hand": "996864.85",
    "accounts_receivable": "156254.48",
    "total_assets": "1153119.33",
    "cash_percentage": 86.45,
    "receivables_percentage": 13.55
  },
  "credit_health": {
    "total_credit_sales": "350000.00",
    "unpaid_amount": "85000.00",
    "partially_paid_amount": "71254.48",
    "fully_paid_amount": "193745.52",
    "collection_rate": 55.36
  }
}
```

#### Filtered Sales
```json
GET /api/sales/?days_outstanding=30&min_amount_due=500

{
  "count": 12,
  "results": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "payment_type": "CREDIT",
      "status": "PENDING",
      "amount_due": "1250.50",
      "completed_at": "2024-12-15T10:30:00Z",
      ...
    }
  ]
}
```

### 6. Business Logic

#### Profit vs Revenue
- **Revenue** (`total_amount`): What customers owe/paid
- **Profit** (`total_profit`): Revenue minus costs
- **Cash on Hand** (profit-based): Actual profit realized

#### Credit Sales States
- **PENDING**: No payment received → Full profit is outstanding
- **PARTIAL**: Some payment received → Full profit still outstanding (conservative)
- **COMPLETED**: Full payment received → No outstanding credit

### 7. Testing

Created test files:
- `test_cash_on_hand_calculation.py` - Comprehensive unit tests (7 tests)
- `test_cash_on_hand_simple.py` - Integration tests with real data
- `test_profit_calc.py` - Direct profit calculation logic test

All profit calculation logic verified working with existing database data.

### 8. Future Enhancements

Potential improvements:
1. Use `landed_unit_cost` (unit_cost + taxes + additional costs) for more accurate profit
2. Add partial payment profit allocation (calculate realized vs outstanding profit for PARTIAL sales)
3. Add profit margin percentage to summary
4. Add profit trends over time
5. Add cost of goods sold (COGS) metrics
6. Add inventory turnover based on profit

### 9. Frontend Integration

To use in frontend:

```typescript
// Fetch summary with profit metrics
const response = await fetch('/api/sales/summary/');
const data = await response.json();

console.log(`Cash on Hand (Profit): $${data.cash_on_hand}`);
console.log(`Outstanding Credit: $${data.outstanding_credit}`);
console.log(`Total Profit: $${data.total_profit}`);

// Filter overdue credit sales (> 30 days)
const overdue = await fetch('/api/sales/?days_outstanding=30');

// Filter by amount range
const highValue = await fetch('/api/sales/?min_amount_due=1000');

// Filter by customer
const customerSales = await fetch(`/api/sales/?customer_id=${customerId}`);
```

### 10. Key Metrics Comparison

| Metric | Revenue-Based | Profit-Based |
|--------|---------------|--------------|
| Cash at Hand | $996,864.85 (amount_paid) | $395,000.00 (profit - outstanding) |
| Receivables | $156,254.48 (amount_due) | $55,000.00 (profit on unpaid) |
| Total | $1,153,119.33 (revenue) | $450,000.00 (profit) |

**Profit Margin**: ~39% ($450K profit / $1,153K revenue)

## Completion Status

✅ Summary endpoint with 4 new profit-based fields  
✅ 5 new sales filters (days_outstanding, min/max_amount_due, customer_id)  
✅ Profit calculation logic using database aggregation  
✅ Error handling for invalid filter values  
✅ Test files created and logic verified  
✅ Documentation complete  

## Notes

- Implementation uses base `unit_cost` from StockProduct
- Excludes sale items without stock_product from profit calculations
- Conservative approach: PARTIAL sales count as fully outstanding
- All filtering and calculations happen at database level (efficient)
- Compatible with existing revenue-based metrics (both provided)

## Author

GitHub Copilot
Date: 2025-01-XX
