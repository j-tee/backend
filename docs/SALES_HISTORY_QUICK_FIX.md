# 🚨 Sales History Fix - Quick Summary

**For Frontend Developer**

---

## The Problem (What You're Seeing)

Your Sales History page shows:
- ❌ Receipt #: **N/A**
- ❌ Items: **0 items**  
- ❌ Amount: **$0.00**
- ❌ Status: **DRAFT**

**This is because you're showing DRAFT sales (empty shopping carts) instead of COMPLETED sales!**

---

## The Solution (One Line Fix)

### Current Code (WRONG):
```typescript
// This returns ALL sales including empty drafts
const response = await api.get('/sales/api/sales/')
```

### Fixed Code (CORRECT):
```typescript
// This returns only COMPLETED sales with real data
const response = await api.get('/sales/api/sales/?status=COMPLETED')
```

---

## Expected Results After Fix

### Before:
```
Receipt #: N/A
Items: 0 items
Amount: $0.00
Status: DRAFT
```

### After:
```
Receipt #: REC-202501-10009
Items: 1 items
Amount: $7.40
Status: COMPLETED
```

---

## Sale Status Meanings

| Status | What It Means | Show in History? |
|--------|---------------|------------------|
| DRAFT | Empty cart (not completed) | ❌ NO |
| COMPLETED | Real sale (fully paid) | ✅ YES |
| PARTIAL | Sale with balance due | ✅ YES (optional) |
| PENDING | Awaiting payment | ✅ YES (optional) |

> 💡 **Credit lines update:** Credit customers still generate real receipts. A credit invoice that is fully paid settles as `COMPLETED`, while invoices with money outstanding now surface as `PARTIAL` (some money received) or `PENDING` (no payment yet). Use these statuses plus the new fields below to highlight outstanding balances in the UI.

---

## New Credit Tracking Fields (Frontend must surface)

Every sale payload now includes credit-friendly metadata:

- `payment_type` – `'CREDIT'` identifies invoices on a credit line.
- `amount_due` – numeric remaining balance (0 when fully paid).
- `payment_status` – helper string (`"Fully Paid"`, `"Partially Paid"`, `"Unpaid"`).
- `payment_completion_percentage` – number between 0–100 for progress indicators.
- `payments[]` – history of cash collections (method, amount, timestamp).

### Example response slice

```json
{
  "receipt_number": "REC-202510-20441",
  "payment_type": "CREDIT",
  "status": "PARTIAL",
  "total_amount": 1825.50,
  "amount_paid": 725.50,
  "amount_due": 1100.00,
  "payment_status": "Partially Paid (725.50/1825.50)",
  "payment_completion_percentage": 39.75
}
```

> Sample data tip: the seeded dataset now includes 27 fully paid credit invoices (with multi-instalment `BANK_TRANSFER` history) plus partial credit sales that retain outstanding balances—ideal for testing dashboards.

## Financial Summary Metrics (2025-10-07 update)

The `/sales/api/sales/summary/` endpoint now exposes full P&L slices so the summary cards no longer show revenue as profit:

- `total_sales` – revenue from completed sales (still accrual-based).
- `total_cogs` – cost of goods sold using each line item’s stock landing cost.
- `total_tax_collected` and `total_discounts` – highlight statutory remittances and give-aways separately.
- `total_profit` and `profit_margin` – gross profit after subtracting COGS and taxes; margin is based on net revenue (ex-tax).
- `realized_revenue` / `outstanding_revenue` – cash collected vs amounts still on credit lines.
- `realized_profit` / `outstanding_profit` – profit attributable to payments received vs the profit tied up in receivables.
- `credit_health` – enriched with `amount_paid`, `amount_due`, plus `realized_profit` / `outstanding_profit` for the credit portfolio.

### Sample summary response slice

```json
{
  "total_sales": 54760.97,
  "total_cogs": 31840.55,
  "total_tax_collected": 2740.00,
  "total_profit": 20180.42,
  "profit_margin": 38.75,
  "realized_revenue": 43290.22,
  "outstanding_revenue": 11470.75,
  "realized_profit": 15234.18,
  "outstanding_profit": 4946.24,
  "credit_health": {
    "amount_paid": 22180.50,
    "amount_due": 11470.75,
    "realized_profit": 8120.37,
    "outstanding_profit": 4946.24
  }
}
```

> Frontend tip: use the new `total_cogs`, `total_tax_collected`, and `total_profit` values to render a stacked insight (Revenue → COGS/Tax/Discounts → Profit). Pair `realized_*` vs `outstanding_*` to emphasise cash position versus receivables.

### UI recommendations

- Show an **Outstanding** badge when `payment_type === 'CREDIT'` and `amount_due > 0`.
- Display `amount_due` beside the main total (e.g., “Paid 40% · GHS 1,100 due”).
- Use `payment_completion_percentage` to render a progress bar or chip.
- Expand the `payments` array in a drawer/table so finance teams can see installment history without leaving the page.

---

## Querying credit portfolios from the frontend

The sales endpoint accepts extra filters designed specifically for credit lines:

| Query Param | Example | Purpose |
|-------------|---------|---------|
| `has_outstanding_balance` | `true` | Return only invoices with `amount_due > 0`. |
| `payment_status` | `partial` / `unpaid` / `paid` | Slice credit sales by collection state. |
| `days_outstanding` | `30` | Credit invoices older than _N_ days without full payment. |
| `min_amount_due` / `max_amount_due` | `min_amount_due=500` | Filter by balance size. |
| `customer_id` | UUID | Pull a specific account’s statement. |
| `payment_type` | `payment_type=MOBILE` | Restrict to a tender (valid values: `CASH`, `CARD`, `MOBILE`, `CREDIT`). |

### Sample service call

```typescript
export const getOutstandingCredit = (filters: { minAmountDue?: number; daysOutstanding?: number } = {}) => {
  return api.get('/sales/api/sales/', {
    params: {
      status: ['PARTIAL', 'PENDING'],
      payment_type: 'CREDIT',
      has_outstanding_balance: true,
      min_amount_due: filters.minAmountDue,
      days_outstanding: filters.daysOutstanding,
      ordering: '-completed_at'
    }
  })
}
```

> ✅ Tip: Default to `status=COMPLETED` for regular sales history, but offer a “Credit Invoices” tab that swaps to `status=['PARTIAL','PENDING']` plus `has_outstanding_balance=true`.

---

## Frontend typings quick patch

Extend your existing sale interface so TypeScript knows about the new fields:

```typescript
export interface SaleSummary {
  id: string
  receipt_number: string
  status: 'COMPLETED' | 'PARTIAL' | 'PENDING' | 'DRAFT'
  payment_type: 'CASH' | 'CARD' | 'MOBILE' | 'CREDIT'
  total_amount: number
  amount_paid: number
  amount_due: number
  payment_status?: string | null
  payment_completion_percentage?: number
}
```

Use these types inside tables, badges, or charts so designers can clearly distinguish between cash sales and invoices on credit.

---

## Test Your Fix

After adding `?status=COMPLETED`:

1. ✅ Receipt numbers should appear (REC-202510-xxxx)
2. ✅ Item counts should be > 0
3. ✅ Amounts should show real values
4. ✅ Total should show ~375 sales (not 508)

---

## Full Example (React/TypeScript)

```typescript
// services/salesService.ts
export const getSalesHistory = async (page = 1) => {
  const response = await api.get('/sales/api/sales/', {
    params: {
      status: 'COMPLETED',  // ← ADD THIS LINE
      page,
      page_size: 20,
      ordering: '-completed_at'
    }
  })
  return response.data
}
```

---

## Database Facts

- **Total records in DB:** 508 sales
- **COMPLETED (real sales):** 375 ← **Show these**
- **DRAFT (empty carts):** 23 ← **Hide these**
- **PARTIAL/PENDING:** 112 ← **Optional**

---

## More Info

See detailed documentation:
- `docs/FRONTEND_SALES_HISTORY_FIX.md` - Complete fix guide
- `docs/SALES_API_ENHANCEMENTS_COMPLETE.md` - Full API docs

---

**TL;DR: Add `?status=COMPLETED` to your API call and everything will work! 🚀**
