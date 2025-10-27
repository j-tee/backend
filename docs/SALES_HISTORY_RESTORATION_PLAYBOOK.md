# 🛠️ Sales History Restoration Playbook

**Audience:** Frontend developers fixing the Sales History page  
**Scope:** Consolidated guidance from all prior sales-history docs + new debugging notes (updated Oct 7, 2025)

---

## 🎯 Mission

Restore the Sales History page so it:
- Shows real completed sales with receipt numbers, item counts, and dollar amounts
- Displays accurate financial summaries (no `$NaN`, no `$0.00` when data exists)
- Uses the backend API correctly with working filters and pagination

---

## 🔍 Quick Symptom Checklist

| Symptom | What you see on screen | Root cause | Section to fix |
|---------|-----------------------|------------|----------------|
| All rows show `Receipt #: N/A`, `0 items`, `$0.00`, `DRAFT` | Fetching draft carts instead of real sales | Missing status filter | [Step 2](#step-2-apply-the-status-filter) |
| Financial summary shows `$NaN` or stays `$0.00` forever | Client-side math divides by zero / missing data guards | Unsafe calculations | [Step 3](#step-3-make-summary-calculations-safe) |
| Browser console logs `FILTER FAILURE – Backend filter is NOT working!` with request URL `/sales/api/sales/` | Request is hitting the frontend dev server (5173) instead of the Django backend or URL is missing `/api` prefix | API base URL misconfiguration | [Step 1](#step-1-point-your-api-client-at-the-backend) |
| Network tab shows 200 responses with `results: []` | Backend never received `status=COMPLETED` or filter parameter spelled wrong | Incorrect query params | [Step 2](#step-2-apply-the-status-filter) |

> ✅ **Good news:** The backend is healthy. There are **375 completed sales** worth **$992,411.28** waiting to be displayed.

---

## ⚡ Five-Minute Rescue Plan

1. [Point your API client at the backend](#step-1-point-your-api-client-at-the-backend) (ensure requests hit `http://localhost:8000`).
2. [Append `status=COMPLETED` to the sales API call](#step-2-apply-the-status-filter).
3. [Guard division/number conversions to prevent `$NaN`](#step-3-make-summary-calculations-safe`).
4. [Verify the page end-to-end](#step-4-verify-and-regression-test).

---

## Step 1. Point Your API Client at the Backend

The screenshot below shows the console complaining about a backend filter, but the **Actual request URL** is `/sales/api/sales/`. That relative path is served by the Vite dev server (`http://localhost:5173`) unless you configured a proxy.

✅ **Fix:** Ensure every request is sent to the Django backend base URL (`http://localhost:8000`).

```typescript
// api.ts (Axios example)
import axios from 'axios'

export const api = axios.create({
  baseURL: 'http://localhost:8000', // ← absolute backend URL
  withCredentials: true
})
```

### Sanity check

```bash
curl "http://localhost:8000/api/sales/?status=COMPLETED&page_size=1" | jq '.results[0].receipt_number'
```
Should print something like `"REC-202510-10483"`.

If the curl command returns data but the browser call does not, your frontend is still pointing at the wrong host.

---

## Step 2. Apply the Status Filter

The backend returns drafts first when no filter is supplied. Add the status query parameter.

```typescript
// services/salesService.ts
export const getSalesHistory = async (page = 1, pageSize = 20) => {
  const response = await api.get('/api/sales/', {
    params: {
      status: 'COMPLETED',   // ← REQUIRED default filter
      page,
      page_size: pageSize,
      ordering: '-completed_at'
    }
  })
  return response.data
}
```

### Optional: allow multiple statuses but exclude DRAFT

```typescript
const DEFAULT_STATUSES = ['COMPLETED']

export const getSalesHistory = async (filters: { statuses?: string[] } = {}) => {
  const statuses = filters.statuses?.length ? filters.statuses : DEFAULT_STATUSES
  const params = new URLSearchParams()
  statuses.forEach(status => params.append('status', status))
  params.append('ordering', '-completed_at')

  const { data } = await api.get(`/api/sales/?${params.toString()}`)
  return data
}
```

### Database reality check

| Status | Count | Decision |
|--------|-------|----------|
| COMPLETED | 375 | ✅ Show by default |
| PARTIAL | 21 | ⚠️ Optional (show with due balance) |
| PENDING | 91 | ⚠️ Optional |
| DRAFT | 21 | ❌ Hide |

---

## Step 3. Make Summary Calculations Safe

The `$NaN` flood starts when you divide by zero or convert `undefined` to `Number` without guards.

```typescript
// summary.ts helpers
const sumBy = (items: any[], accessor: (item: any) => number): number =>
  items.reduce((total, item) => total + (Number(accessor(item)) || 0), 0)

const safeAverage = (total: number, count: number): number =>
  count > 0 ? total / count : 0

export const buildSalesSummary = (sales: Sale[]): SalesSummary => {
  const totalRevenue = sumBy(sales, sale => sale.total_amount)
  const totalProfit = sumBy(sales, sale => sale.profit_amount)
  const totalTax = sumBy(sales, sale => sale.tax_amount)
  const totalDiscounts = sumBy(sales, sale => sale.discount_amount)
  const count = sales.length

  return {
    totalRevenue,
    totalProfit,
    totalTax,
    totalDiscounts,
    avgTransaction: safeAverage(totalRevenue, count),
    totalTransactions: count
  }
}
```

Drop this into whatever hook/component produces the summary and remove raw divisions such as `total / sales.length`.

---

## Step 4. Verify and Regression-Test

1. Open DevTools → Network tab → `api/sales/` request.
2. Confirm the URL is `http://localhost:8000/api/sales/?status=COMPLETED&page=1&page_size=20` (or similar).
3. Response should show `count: 375` and the first result with a real receipt number.
4. UI expectations:
   - Receipts like `REC-202510-10483`
   - Item counts > 0
   - Amounts > $0.00
   - Status badge = `COMPLETED`
5. Financial summary shows real numbers (no `$NaN`).
6. Filters/search/pagination still work.

### Smoke tests

```bash
# Completed sales
curl "http://localhost:8000/api/sales/?status=COMPLETED&page_size=3" | jq '.results[].status'
# Summary endpoint (optional)
curl "http://localhost:8000/api/sales/summary/" | jq '.summary'
```

---

## 🧾 Full React Example

```typescript
import { useEffect, useState } from 'react'
import { api } from '@/services/api'

interface Sale {
  id: string
  receipt_number: string
  customer_name: string
  total_amount: number
  profit_amount: number
  discount_amount: number
  tax_amount: number
  status: 'COMPLETED' | 'PARTIAL' | 'PENDING' | 'DRAFT'
  payment_type: string
  completed_at: string | null
  created_at: string
}

interface Summary {
  totalRevenue: number
  totalProfit: number
  totalTax: number
  totalDiscounts: number
  avgTransaction: number
  totalTransactions: number
}

const DEFAULT_SUMMARY: Summary = {
  totalRevenue: 0,
  totalProfit: 0,
  totalTax: 0,
  totalDiscounts: 0,
  avgTransaction: 0,
  totalTransactions: 0
}

const buildSummary = (sales: Sale[]): Summary => {
  const sumBy = (fn: (sale: Sale) => number) =>
    sales.reduce((total, sale) => total + (Number(fn(sale)) || 0), 0)

  const totalRevenue = sumBy(sale => sale.total_amount)
  const totalProfit = sumBy(sale => sale.profit_amount)
  const totalTax = sumBy(sale => sale.tax_amount)
  const totalDiscounts = sumBy(sale => sale.discount_amount)
  const count = sales.length

  return {
    totalRevenue,
    totalProfit,
    totalTax,
    totalDiscounts,
    avgTransaction: count > 0 ? totalRevenue / count : 0,
    totalTransactions: count
  }
}

export const SalesHistory = () => {
  const [sales, setSales] = useState<Sale[]>([])
  const [summary, setSummary] = useState<Summary>(DEFAULT_SUMMARY)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    const fetchSales = async () => {
      setLoading(true)
      try {
        const { data } = await api.get('/api/sales/', {
          params: {
            status: 'COMPLETED',
            page,
            page_size: 20,
            ordering: '-completed_at'
          }
        })
        const results = data.results ?? []
        setSales(results)
        setSummary(buildSummary(results))
      } catch (error) {
        console.error('Error fetching sales history', error)
        setSales([])
        setSummary(DEFAULT_SUMMARY)
      } finally {
        setLoading(false)
      }
    }

    fetchSales()
  }, [page])

  // ...render table + summary cards...
}
```

---

## 🛡️ Troubleshooting Checklist (Map to Console Logs)

| Console log text | Meaning | Fix |
|------------------|---------|-----|
| `Backend filter is NOT working!` | Frontend request never reached Django (wrong base URL) | Check `api.baseURL` and proxy configuration |
| `Requested status: COMPLETED` but response `results: []` | Parameter not actually sent or spelled wrong | Inspect Network → Params → confirm status values |
| `Response results length: 0` with status 200 | Same as above | Ensure `status` query exists and backend reachable |
| `$NaN` in UI | Calculation on empty array | Use `safeAverage`/`Number(... ) || 0` guards |

---

## 📚 Appendix

### API reference
- `GET /api/sales/` – paginated list. Supports repeated `status` params, `page`, `page_size`, `ordering`, `search`, `date_range`.
- `GET /api/sales/summary/` – totals already computed on the backend.

### Useful counts
- Completed: 375
- Partial: 21
- Pending: 91
- Draft: 21

### Verification script

```bash
python manage.py shell <<'PY'
from sales.models import Sale
print('Total sales:', Sale.objects.count())
print('Completed:', Sale.objects.filter(status='COMPLETED').count())
print('Draft:', Sale.objects.filter(status='DRAFT').count())
PY
```

---

## ✅ Final Acceptance Criteria

- [ ] API requests go to `http://localhost:8000/api/sales/`
- [ ] Default filter includes `status=COMPLETED`
- [ ] Summary calculations never produce `$NaN`
- [ ] UI shows real sales data (receipts, amounts, items)
- [ ] Console/Network tab clear of filter failure messages
- [ ] QA sign-off with screenshots comparing before/after

✨ Once these boxes are checked, the Sales History page is officially restored.
