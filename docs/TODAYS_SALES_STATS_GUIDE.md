# Today's Sales Stats Integration Guide

This note explains how the frontend can populate the **Today's Stats** widget on the new sale screen by using the dedicated `todays-stats` endpoint (with the legacy summary endpoint available for deeper analytics). Use it to fetch real-time totals for the current business, storefront, and day without custom backend work.

## Endpoint overview

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `GET` | `/sales/api/sales/summary/`<br/>_deployments may expose this at `/api/sales/summary/` via a proxy rewrite_ | Required (`IsAuthenticated`) | Returns aggregated sales metrics for the filtered dataset.
| `GET` | `/sales/api/sales/todays-stats/` | Required (`IsAuthenticated`) | Purpose-built snapshot for the Today's Stats widget. Defaults to today's completed sales across all payment types.

The view applies the same business/storefront permissions as other sales endpoints. The authenticated user must belong to the business whose data you want to display.

## Query parameters

### Parameters for `todays-stats`

| Parameter | Type | Example | Purpose |
| --- | --- | --- | --- |
| `date` | `YYYY-MM-DD` | `2025-10-08` | Optional. Overrides the auto-detected "today" (based on server timezone). |
| `storefront` | UUID | `7f7e5e4d-18c7-4f5d-8ad8-1ef4d02b7e88` | Optional. Limits stats to a storefront the user can access. |
| `status` | repeated enum | `status=COMPLETED&status=PARTIAL` | Optional. Defaults to `COMPLETED`. Send multiple values to include partially paid or pending credit sales. |

> The snapshot endpoint intentionally ignores `payment_type`, `customer`, and other advanced filters; it is scoped to daily, storefront-level totals. Use the summary fallback if you need those filters.

### Additional filters via `summary`

The summary endpoint still exposes the full `SaleFilter` surface for dashboards that need historical comparisons or advanced search:

| Parameter | Type | Example | Purpose |
| --- | --- | --- | --- |
| `date_range` | enum | `today`, `yesterday`, `this_week`, `last_week`, `this_month`, `last_month`, `last_30_days`, `last_90_days`, `this_year`, `last_year` | Quickly scope results to a preset range. Internally the filter uses `timezone.now()`. |
| `date_from` | ISO8601 datetime | `2025-10-08T00:00:00Z` | Custom start (UTC). Optional when `date_range` is provided. |
| `date_to` | ISO8601 datetime | `2025-10-08T23:59:59Z` | Custom end (UTC). Optional when `date_range` is provided. |
| `storefront` | UUID | `7f7e5e4d-18c7-4f5d-8ad8-1ef4d02b7e88` | Limit stats to a storefront. Requires access via `user.can_access_storefront`. |
| `status` | repeated enum | `status=COMPLETED&status=PARTIAL` | Filter by sale status. Use at least `status=COMPLETED` for revenue numbers that reflect finished transactions. |
| `payment_type` | enum | `CASH`, `CARD`, `MOBILE`, `CREDIT`, `MIXED` | Optional extra filter when you need totals for a specific payment method. |
| `customer`, `user`, `type`, `search`, etc. | — | — | Additional filters remain available for drill-down views. |

### Recommended flow for the widget

1. **Call the dedicated endpoint**

  ```
  GET /sales/api/sales/todays-stats/?storefront=<ACTIVE_STOREFRONT_ID>
  ```

  - Defaults: `date=today`, `status=COMPLETED`, all payment types.
  - To include additional statuses (e.g. partial credit sales), send multiple `status` parameters: `status=COMPLETED&status=PARTIAL`.
  - **Do not send a `payment_type` filter unless intentionally narrowing the results.** Leaving it out returns all payment types.

2. **(Optional) Fallback to `summary`** if you need the richer analytics payload. Use the original combo:

  ```
  GET /sales/api/sales/summary/?date_range=today&status=COMPLETED&storefront=<ACTIVE_STOREFRONT_ID>
  ```

  - `date_range=today` ensures only sales created today are included.
  - `status=COMPLETED` keeps key metrics aligned with finished transactions. Add extra `status` params when you want to include open credit sales.
  - Include `storefront` when the operator has selected a specific location (see the "Focus" button in the UI). Omit it to aggregate across all accessible storefronts.

## Response shape

### `todays-stats` snapshot

```json
{
  "date": "2025-10-08",
  "storefront": "7f7e5e4d-18c7-4f5d-8ad8-1ef4d02b7e88",
  "statuses": ["COMPLETED"],
  "transactions": 5,
  "total_sales": 824.75,
  "avg_transaction": 164.95,
  "cash_at_hand": 799.75,
  "accounts_receivable": 25.0,
  "partial_transactions": 1,
  "pending_transactions": 0,
  "status_breakdown": [
    { "status": "COMPLETED", "count": 5, "total": 824.75 },
    { "status": "PARTIAL", "count": 1, "total": 120.0 }
  ],
  "payment_breakdown": [
    { "payment_type": "CASH", "count": 3, "total": 654.75 },
    { "payment_type": "MOBILE", "count": 2, "total": 170.0 }
  ],
  "credit_snapshot": {
    "total_credit_sales": 120.0,
    "amount_paid": 95.0,
    "outstanding_amount": 25.0
  }
}
```

### `summary` analytics payload

The original summary endpoint returns the full analytics document:

```json
{
  "summary": {
    "total_transactions": 5,
    "completed_transactions": 5,
    "total_sales": 824.75,
    "avg_transaction": 164.95,
    "cash_at_hand": 799.75,
    "accounts_receivable": 25.0,
    "net_sales": 780.12,
    "total_profit": 153.44,
    "profit_margin": 19.67,
    "financial_position": {
      "cash_at_hand": 799.75,
      "accounts_receivable": 25.0,
      "total_assets": 824.75,
      "cash_percentage": 96.97,
      "receivables_percentage": 3.03
    },
    "credit_health": {
      "total_credit_sales": 120.0,
      "amount_due": 25.0,
      "collection_rate": 79.17,
      "realized_profit": 18.4,
      "outstanding_profit": 4.1,
      "partially_paid_amount": 25.0,
      "unpaid_amount": 0.0,
      "fully_paid_amount": 95.0
    },
    "cash_sales": 654.75,
    "card_sales": 0.0,
    "mobile_sales": 170.0,
    "total_discounts": 45.23,
    "total_tax_collected": 89.86
    // ...additional aggregates omitted for brevity
  },
  "status_breakdown": [
    { "status": "COMPLETED", "count": 5, "total": 824.75 }
  ],
  "daily_trend": [
    { "date": "2025-10-08", "sales": 824.75, "transactions": 5 }
  ],
  "top_customers": [
    { "customer__id": "...", "customer__name": "Acme Retail", "total_spent": 350.0, "transaction_count": 2 }
  ],
  "payment_breakdown": [
    { "payment_type": "CASH", "count": 3, "total": 654.75 },
    { "payment_type": "MOBILE", "count": 2, "total": 170.0 }
  ],
  "type_breakdown": [
    { "type": "RETAIL", "count": 5, "total": 824.75 }
  ]
}
```

> **Note:** Numeric fields are returned as native numbers (no string coercion) thanks to serializer configuration. `avg_transaction` is `null` when no completed sales match the filter—handle this gracefully on the frontend.

## Mapping to the UI widget

| Widget label | Response path (todays-stats) | Fallback path (summary) | Formatting tips |
| --- | --- | --- | --- |
| Transactions | `transactions` | `summary.total_transactions` | Integer count. Defaults to completed sales only; pass extra `status` params to include partials. |
| Total Sales | `total_sales` | `summary.total_sales` | Currency; already restricted to the requested statuses. |
| Avg Transaction | `avg_transaction` | `summary.avg_transaction` | Currency. The snapshot returns `0.0` when no sales exist; the summary returns `null`. |

Supporting numbers such as cash vs receivables live at `cash_at_hand` and `accounts_receivable` (or `summary.cash_at_hand` / `summary.accounts_receivable` when using the older endpoint).

## Integration walkthrough

1. **Fetch storefront ID**: The locations sidebar already loads storefronts. Reuse the UUID from the selected item as the `storefront` query parameter.
2. **Call `/sales/api/sales/todays-stats/`** when the New Sale tab mounts and whenever the operator switches storefronts. Append `storefront=<UUID>` and any extra `status` parameters you need.
3. **Handle loading and empty states**: The snapshot returns `avg_transaction: 0.0` when no sales exist; show `0`/`—` in the widget and optionally display "No sales yet today". (If you fall back to `summary`, remember it returns `null`.)
4. **(Optional) Pull advanced analytics**: If the view also needs historical trends or filterable lists, call the summary endpoint with the filters from the previous section.
5. **Timezone awareness**: The backend treats "today" using server-local time (`timezone.now()`). If the UI needs to anchor to the operator's local timezone, send a `date=YYYY-MM-DD` override or compute `date_from`/`date_to` for the summary.
6. **Caching**: For live dashboards, refresh every few minutes or after completing a sale. The endpoint is optimized with database aggregates and selective prefetching.

## Troubleshooting checklist

- Ensure the authenticated user belongs to the business that owns the storefront (`BusinessMembership` check). Otherwise the response will be zeroed because the queryset is empty.
- If the snapshot keeps returning zeros, double-check the base path (`/sales/api/sales/todays-stats/`) and that you're passing a storefront ID the user can access.
- Add `status=PARTIAL` (and/or `status=PENDING`) when you want in-progress credit sales reflected; the default `COMPLETED` filter hides them.
- When relying on the summary endpoint, remember it has no implicit date filter. Always send `date_range=today` or explicit `date_from`/`date_to` values to avoid loading an entire history.

With these filters applied, the widget will show real numbers instead of zeros using the current backend implementation.
