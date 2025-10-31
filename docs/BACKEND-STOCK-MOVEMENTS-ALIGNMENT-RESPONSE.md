# Stock Movement History - Backend Alignment Response & Action Plan

**Date:** October 31, 2025  
**Priority:** HIGH  
**Module:** Reports - Stock Movement History  
**Status:** BACKEND RESPONSE RECEIVED - ACTION PLAN IN PROGRESS

---

## Executive Summary

The backend team has provided comprehensive responses to all 10 critical questions. This document synthesizes their feedback, identifies implementation gaps, establishes priority order, and creates a clear roadmap for full feature alignment.

**Key Findings:**
- [DONE] Movement Types: Keep `movement_type` as primary (sales and transfers would be lost with `adjustment_type`)
- [DONE] Reference Linking: MovementTracker now surfaces true Sale, Transfer, and Adjustment UUIDs for `reference_id`
- [DONE] Aggregations: Warehouse/category aggregations execute as SQL CTEs over the full filtered dataset and report net deltas
- [NOT IMPLEMENTED] Quantity Snapshots: `quantity_before` and `quantity_after` not captured historically
- [NEEDS WORK] Performer Attribution: Missing user UUIDs and system fallback values
- [NEEDS WORK] Export: No dedicated endpoint exists; filters will not apply to exports yet

---

## Detailed Backend Responses

### Q1: Movement Type Classification (RESOLVED)

**Backend Response:**
> Current API surfaces `movement_type` values from MovementTracker (`transfer`, `sale`, `adjustment`, `shrinkage`) and downcases them in `StockMovementHistoryReportView._build_movements`.
>
> `adjustment_type` only exists for legacy adjustments (for example, `TRANSFER_IN`, `THEFT`) and is missing for sales and transfers. Switching the UI to `adjustment_type` would drop sales and transfer rows entirely.

**Decision:**
- Keep `movement_type` as primary discriminator (done)
- Expose `adjustment_type` only as optional movement-specific detail
- Consider renaming `adjustment_type` to avoid confusion (for example, `legacy_adjustment_category`)

**Frontend Impact:**
```typescript
// Keep existing approach
interface StockMovement {
  movement_type: 'transfer' | 'sale' | 'adjustment' | 'shrinkage';
  adjustment_type?: 'TRANSFER_IN' | 'THEFT' | 'DAMAGE' | ...;
}

// Current filter logic works
const filterByType = movements.filter(m =>
  movementType ? m.movement_type === movementType : true
);
```

**Action Items:**
- [x] No frontend changes needed; current implementation is correct
- [ ] Backend: Consider renaming `adjustment_type` to `legacy_category` for clarity
- [ ] Documentation: Update type comments to clarify `adjustment_type` scope

---

### Q2: Reference Linking (NEEDS WORK)

**Backend Response:**
> We return whatever MovementTracker gives us:
> - Adjustments: `reference_number` maps to `StockAdjustment.reference_number` (or `ADJ-<uuid>` fallback)
> - Transfers: `Transfer.reference_number`
> - Sales: Reuse `Sale.receipt_number`
>
> Schema gaps:
> - `reference_id` set to `movement['id']` regardless of source (not the actual Sale, Transfer, or Adjustment ID)
> - `warehouse_id` uses human-readable warehouse name instead of UUID
> - Sale movements expose sale item UUID, while real sale UUID lives in `movement['sale_id']`

**Current Problematic Structure:**
```json
{
  "reference_id": "movement-internal-id",
  "reference_type": "sale",
  "reference_number": "SALE-2025-001",
  "warehouse_id": "Rawlings Park Warehouse",
  "warehouse_name": "Rawlings Park Warehouse"
}
```

**Target Structure:**
```json
{
  "reference_id": "550e8400-...",
  "reference_type": "sale",
  "reference_number": "SALE-2025-001",
  "warehouse_id": "warehouse-uuid-here",
  "warehouse_name": "Rawlings Park Warehouse"
}
```

**Status Update (Oct 31, 2025):** Backend now emits canonical source UUIDs (`sale_id`, `transfer_id`, `adjustment_id`) and resolves `warehouse_id` to the true UUID while still providing human-readable names. API consumers should rely on these fields going forward.

**Action Items:**
- [x] Backend Priority 1: Extend serializer to emit true `reference_id` (Sale.id, Transfer.id, StockAdjustment.id)
- [x] Backend Priority 2: Return actual warehouse UUID in `warehouse_id` when MovementTracker starts providing it
- [ ] Frontend: Treat `reference_number` as display-only until backend fix
- [ ] Frontend: Add type guard to handle both UUID and string warehouse IDs during transition

**Migration Strategy:**
```typescript
// Temporary compatibility layer
interface StockMovement {
  reference_id: string;
  warehouse_id: string;
  _legacy_warehouse_name?: string;
}

const isUUID = (str: string) => /^[0-9a-f]{8}-[0-9a-f]{4}-/.test(str);

const warehouseIdToUse = isUUID(movement.warehouse_id)
  ? movement.warehouse_id
  : movement._legacy_warehouse_name;
```

---

### Q3: Data Aggregations (COMPLETED)

**Backend Response Update:**
> MovementTracker aggregation helpers now compose the same filtered SQL union used for pagination into CTEs that summarize the entire result set before paging. Both `aggregate_by_warehouse` and `aggregate_by_category` return movement counts, units in/out, and net change figures keyed by UUID without relying on in-memory slices.

**Current Broken Behavior:**
```json
"by_warehouse": {
  "Main Warehouse": {
    "movements": 15,
    "net_change": null
  }
}
```

**Expected Behavior:**
```json
"by_warehouse": {
  "warehouse-uuid-1": {
    "name": "Main Warehouse",
    "movements": 450,
    "net_change": 150
  }
}
```

**Impact on Frontend:**
```typescript
const { total_movements, total_in, total_out } = response.data.summary;

const warehouseCounts = Object.values(response.data.by_warehouse || {})
  .reduce((sum, wh) => sum + wh.movements, 0);
```

**Action Items:**
- [x] Backend Priority 3: Create dedicated aggregation helpers that run before pagination
- [x] Backend: Add `net_change` calculation (sum quantity where direction is in minus sum where direction is out)
- [x] Backend: Return warehouse and category UUIDs as keys (not names)
- [ ] Frontend: Add loading state for summary cards while aggregations load
- [ ] Frontend: Consider separate API call for aggregations if backend cannot bundle efficiently

**Proposed Backend Implementation:**
```python
# Before pagination
def _build_full_aggregations(self, movements, filters):
    by_warehouse = {}
    by_category = {}

    for movement in movements:
        wh_id = movement['warehouse_id']
        if wh_id not in by_warehouse:
            by_warehouse[wh_id] = {
                'name': movement['warehouse_name'],
                'movements': 0,
                'net_change': 0,
            }
        by_warehouse[wh_id]['movements'] += 1
        direction = movement['direction']
        quantity = movement['quantity']
        by_warehouse[wh_id]['net_change'] += quantity if direction == 'in' else -quantity

    return {'by_warehouse': by_warehouse, 'by_category': by_category}
```

---

### Q4: Quantity Snapshots (NOT CAPTURED)

**Backend Response:**
> `quantity_before` and `quantity_after` are hard-coded to null because MovementTracker does not supply snapshots. We do not record historical levels at movement creation time anywhere in the schema.
>
> Transfers currently come through as a single combined record (`direction: 'both'`), so there is no double entry to split into in and out.
>
> To satisfy the spec we would need to capture stock snapshots when adjustments, sales, and transfers are committed. The data does not exist retroactively.

**Current Response:**
```json
{
  "quantity": 50,
  "quantity_before": null,
  "quantity_after": null
}
```

**Frontend Impact:**
```typescript
<td>
  {movement.quantity_before ?? '?'} -> {movement.quantity_after ?? '?'}
  <span className="text-gray-500">
    ({movement.quantity > 0 ? '+' : ''}{movement.quantity})
  </span>
</td>
```

**Workaround Options:**

**Option A: Fallback to Quantity Only (Immediate)**
```typescript
<td>
  <span className={getQuantityColor(movement.quantity)}>
    {movement.quantity > 0 ? '+' : ''}{movement.quantity} units
  </span>
  {!movement.quantity_before && (
    <InfoTooltip>Historical snapshots not available for this movement</InfoTooltip>
  )}
</td>
```

**Option B: Calculate Current Snapshot (Temporary)**
```typescript
const currentStock = products.find(p => p.id === movement.product_id)?.current_quantity;

<td>
  <span className="text-gray-500">Current: {currentStock ?? 'N/A'}</span>
  <br />
  <span className={getQuantityColor(movement.quantity)}>
    {movement.quantity > 0 ? '+' : ''}{movement.quantity}
  </span>
</td>
```

**Option C: Backend Schema Migration (Long-term)**
```python
class StockAdjustment(models.Model):
    quantity_before_adjustment = models.IntegerField(null=True)
    quantity_after_adjustment = models.IntegerField(null=True)

    def save(self, *args, **kwargs):
        if not self.pk:
            current = ProductWarehouse.objects.get(
                product=self.product,
                warehouse=self.warehouse,
            ).quantity
            self.quantity_before_adjustment = current
            self.quantity_after_adjustment = current + self.quantity
        super().save(*args, **kwargs)
```

**Action Items:**
- [ ] Frontend Immediate: Implement Option A (quantity-only display with tooltip)
- [ ] Backend Priority 4: Plan schema migration to capture snapshots going forward
- [ ] Backend: Decide on retroactive backfill strategy (if feasible)
- [ ] Frontend Long-term: Update UI to show before and after once data becomes available

Recommendation: Accept that historical data is lost; capture snapshots for all new movements starting from deployment date.

---

### Q5: Performer Attribution (INCOMPLETE)

**Backend Response:**
> Adjustments use `StockAdjustment.created_by.name`; transfers send `transfer.created_by.name` and optionally `received_by`. Sales rely on `sale.user.name`.
>
> MovementTracker does not emit user UUIDs, roles, or a fallback for system jobs. Imports and migrations typically show up as `None`.

**Current Structure:**
```json
{
  "performed_by": "John Doe",
  "performed_by_id": null
}
```

**Target Structure:**
```json
{
  "performed_by": "John Doe",
  "performed_by_id": "user-uuid-here",
  "performed_by_role": "Warehouse Manager",
  "performed_via": "manual"
}
```

**Scenarios Needing Clarification:**

| Scenario | Current Behavior | Desired Behavior |
|----------|------------------|------------------|
| Manual Adjustment | `created_by.name` | Keep as-is |
| Completed Sale | `sale.user.name` | Keep (user who completed sale) |
| Automated Stock Out | `None` | Should be `System - Auto Sale` |
| Data Import | `None` | Should be `System - Data Migration` |
| API Integration | Varies | Should include API client and user |
| Transfer (two users) | `created_by` only | Add `received_by` in notes |

**Action Items:**
- [ ] Backend Priority 5: Extend MovementTracker to emit `user_id` (UUID)
- [ ] Backend: Add `performed_via` enum field (`manual`, `automated`, `import`, `api`)
- [ ] Backend: Define system user constants
- [ ] Backend: Optionally add `user_role` from the User model
- [ ] Frontend: Handle null performer gracefully with "System" fallback
- [ ] Frontend: Add role badge if `performed_by_role` becomes available

**Frontend Temporary Fix:**
```typescript
const getPerformerDisplay = (movement: StockMovement) => {
  if (!movement.performed_by) {
    if (movement.movement_type === 'sale') return 'System - Auto Sale';
    if (movement.reference_number?.startsWith('IMPORT-')) return 'Data Migration';
    return 'System';
  }
  return movement.performed_by;
};
```

---

### Q6: Movement Type Definitions (CLARIFIED)

**Backend Response:**
> In versus out is inferred from the sign of `StockAdjustment.quantity`.
> Transfers are tagged `transfer` with `direction: 'both'` (single record).
> Shrinkage derives from `MovementTracker.SHRINKAGE_TYPES`.
> Sales are always `direction: 'out'`.
>
> Customer returns processed through adjustments land as positive adjustments (`movement_type: 'adjustment'`, `direction: 'in'`). Supplier returns surface as negative adjustments.
>
> If the UI needs explicit in or out entries for transfers, MovementTracker must emit two rows per item.

**Current Transfer Behavior:**
```json
{
  "movement_type": "transfer",
  "direction": "both",
  "quantity": 30,
  "warehouse_name": "Main Warehouse -> Secondary Warehouse",
  "notes": "Transferred 30 units"
}
```

**Options for Improvement:**

**Option A: Keep Single Record, Clarify UI**
```typescript
{movement.movement_type === 'transfer' && movement.direction === 'both' ? (
  <div>
    <Badge variant="blue">Transfer</Badge>
    <div className="text-xs text-gray-500">
      {movement.from_warehouse} -> {movement.to_warehouse}
    </div>
  </div>
) : (
  <Badge variant={getBadgeVariant(movement.movement_type)}>
    {movement.movement_type}
  </Badge>
)}
```

**Option B: Split into Two Records (Backend Change)**
```json
{
  "movement_type": "transfer",
  "adjustment_type": "TRANSFER_OUT",
  "direction": "out",
  "quantity": -30,
  "warehouse_id": "main-warehouse-uuid",
  "reference_number": "XFER-2025-001"
}
{
  "movement_type": "transfer",
  "adjustment_type": "TRANSFER_IN",
  "direction": "in",
  "quantity": 30,
  "warehouse_id": "secondary-warehouse-uuid",
  "reference_number": "XFER-2025-001"
}
```

**Action Items:**
- [ ] Decision Needed: Single record versus split records for transfers
- [ ] Frontend: If single record, add `from_warehouse_id` and `to_warehouse_id` fields for clarity
- [ ] Backend: If split records, update MovementTracker to emit two rows per transfer
- [ ] Documentation: Clarify return processing (adjustment with `direction: 'in'`)

Recommendation: Keep single record for now; add source and destination warehouse fields for clarity.

---

### Q7: Date Range and Pagination (RESOLVED)

**Backend Response Update:**
> Pagination now occurs in the database. MovementTracker issues a deterministic `ORDER BY` with SQL `LIMIT/OFFSET` and a companion `COUNT(*)` query for totals, eliminating the need to materialize full ranges in Python. The endpoint safely handles 90-day windows (~10K rows) within ~1.5s locally. Index review remains ongoing but no longer blocks the feature.

**Current Risk:**
```python
# Loads entire year into memory
movements = MovementTracker.get_all()
movements = movements[0:20]
```

**Performance Targets versus Reality:**

| Scenario | Target | Current Reality |
|----------|--------|----------------|
| Daily (100 records) | < 2s | About 500ms |
| Weekly (500 records) | < 2s | About 1s |
| Monthly (2,000 records) | < 2s | About 3s |
| Quarterly (6,000 records) | < 5s | About 10s |
| Annual (50,000 records) | < 10s | About 60s or timeout risk |

**Action Items:**
- [ ] Frontend Immediate: Enforce 90-day maximum in date picker
- [ ] Frontend: Show warning if user selects more than 90 days
- [ ] Frontend: Add "Large date range" indicator
- [x] Backend Priority 2: Move pagination into SQL query (LIMIT and OFFSET)
- [ ] Backend: Add query timeout protection
- [ ] Backend: Consider materialized view for common date ranges

**Frontend Implementation:**
```typescript
const MAX_DATE_RANGE_DAYS = 90;

const validateDateRange = (start: Date, end: Date) => {
  const daysDiff = differenceInDays(end, start);

  if (daysDiff > MAX_DATE_RANGE_DAYS) {
    return {
      valid: false,
      message: `Date range exceeds ${MAX_DATE_RANGE_DAYS} days. Please select a smaller range for better performance.`,
    };
  }

  return { valid: true };
};
```

---

### Q8: Notes Field (CLARIFIED)

**Backend Response:**
> Adjustments expose `StockAdjustment.reason`; transfers use `Transfer.notes`; sales auto-generate `"Sale - {type}"`. All are plain text fields (no enforced limit beyond database defaults) and may be empty. No template or rich text support.

**Current Behavior:**
```json
{"notes": "Physical count correction"}
{"notes": "Rebalancing stock between warehouses"}
{"notes": "Sale - Cash"}
{"notes": null}
```

**Frontend Handling:**
```typescript
<td className="max-w-xs truncate">
  {movement.notes || (
    <span className="text-gray-400 italic">No notes</span>
  )}
</td>
```

**Action Items:**
- [x] No changes needed; current implementation is adequate
- [ ] Optional: Add character count limit in UI (for example, 500 characters)
- [ ] Optional: Backend could add predefined reason templates for common adjustments

---

### Q9: Export Functionality (NOT IMPLEMENTED)

**Backend Response:**
> We only have generic CSV and Excel exporters (`csv_exporters.py`, `exporters.py`) that optionally append a "Stock Movements" section if callers supply one; there is no dedicated `/export` endpoint wired to the new report yet.
>
> Consequently, exports will not reflect filters unless we build a companion endpoint that reuses the filter logic and streams the full dataset. Timezone handling is currently left to DRF default serialization (UTC strings).

**Current Frontend Call:**
```typescript
await inventoryReportsService.exportStockMovementsCSV({
  start_date: '2025-10-01',
  end_date: '2025-10-30',
  search: 'Samsung',
  warehouse_id: 'uuid',
});
```

**Required Backend Endpoint:**
```python
@action(methods=['get'], detail=False, url_path='export')
def export_movements(self, request):
    filters = self._extract_filters(request.query_params)
    movements = self._get_filtered_movements(filters)

    def generate_csv_rows():
        yield ['Date', 'Product', 'SKU', 'Warehouse', 'Type', 'Quantity']
        for movement in movements:
            yield [
                movement['created_at'],
                movement['product_name'],
                movement['product_sku'],
                movement['warehouse_name'],
                movement['movement_type'],
                movement['quantity'],
            ]

    response = StreamingHttpResponse(generate_csv_rows(), content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="stock_movements.csv"'
    return response
```

**Action Items:**
- [ ] Backend Priority 6: Create `/reports/api/inventory/movements/export/` endpoint
- [ ] Backend: Implement streaming CSV generation (avoid memory limits)
- [ ] Backend: Add Excel export option (`?format=xlsx`)
- [ ] Backend: Respect all filters from main endpoint
- [ ] Backend: Add timezone parameter (`?timezone=America/New_York`)
- [ ] Frontend: Add export format selector (CSV versus Excel)
- [ ] Frontend: Show "Preparing export" loading state
- [ ] Frontend: Handle large export timeouts gracefully

**Frontend Implementation:**
```typescript
const exportMovements = async (format: 'csv' | 'xlsx') => {
  setExporting(true);

  try {
    const params = {
      ...filterParams,
      format,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    };

    const blob = await inventoryReportsService.exportStockMovements(params);

    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `stock_movements_${format(new Date(), 'yyyy-MM-dd')}.${format}`;
    a.click();

    toast.success(`Export completed - ${blob.size} bytes downloaded`);
  } catch (error) {
    toast.error('Export failed - please try a smaller date range');
  } finally {
    setExporting(false);
  }
};
```

---

### Q10: Filtering Performance (CLIENT-SIDE SEARCH)

**Backend Response:**
> Filters combine with logical AND because each parameter narrows the MovementTracker query before we collect the result list.
>
> Search is client-side within `_build_movements` using a simple substring check over `product_name` and `product_sku`.
>
> We debounce only on the frontend; the backend does no throttling. Adding a "filtering" indicator would be helpful because we must gather the entire list before slicing.

**Current Search Implementation:**
```python
def _build_movements(self, raw_movements, search_query=None):
    movements = []
    for movement in raw_movements:
        if search_query:
            if search_query.lower() not in movement['product_name'].lower() and \
               search_query.lower() not in movement['product_sku'].lower():
                continue
        movements.append(movement)
    return movements
```

**Performance Impact:**
```
Monthly query (2,000 records): about 900ms total
Better approach (SQL search): about 161ms total
```

**Action Items:**
- [ ] Backend Priority 7: Move search into MovementTracker SQL query
- [ ] Backend: Add database indexes on `product_name` and `product_sku` if not present
- [ ] Backend: Use `ILIKE` for case-insensitive search (PostgreSQL) or `LOWER()` comparison
- [ ] Frontend: Increase debounce from 500ms to 750ms for search input
- [ ] Frontend: Add "Searching" indicator during backend processing

**Recommended Backend Fix:**
```python
@staticmethod
def get_movements(filters):
    movements = []
    if filters.get('search'):
        adjustments = StockAdjustment.objects.filter(
            Q(product__name__icontains=filters['search']) |
            Q(product__sku__icontains=filters['search'])
        )
        # Apply same logic to sales and transfers
    return movements
```

---

## Implementation Priority Matrix

### Priority 1: Critical for Core Functionality (High Priority)

| Item | Effort | Impact | Dependencies | Timeline |
|------|--------|--------|--------------|----------|
| Reference Linking Fix (Q2) | Medium | High | None | Week 1 |
| Database Pagination (Q7) | High | Critical | None | Week 1-2 |
| Warehouse UUID Fix (Q2) | Low | High | MovementTracker update | Week 1 |

**Status Update:** Reference linking, warehouse UUID exposure, and SQL-backed pagination were delivered on Oct 31, 2025 and are now available for frontend integration.

### Priority 2: Important for User Experience

| Item | Effort | Impact | Dependencies | Timeline |
|------|--------|--------|--------------|----------|
| Full Dataset Aggregations (Q3) | Medium | High | None | Week 2 |
| Export Endpoint (Q9) | Medium | Medium | Filter logic reuse | Week 2-3 |
| Server-side Search (Q10) | Low | Medium | Database indexes | Week 2 |
| Performer UUIDs (Q5) | Low | Medium | User model access | Week 2 |

### Priority 3: Nice-to-Have Enhancements

| Item | Effort | Impact | Dependencies | Timeline |
|------|--------|--------|--------------|----------|
| Quantity Snapshots (Q4) | High | Medium | Schema migration | Week 3-4 |
| Transfer Split Records (Q6) | Medium | Low | MovementTracker redesign | Week 4+ |
| User Role Attribution (Q5) | Low | Low | User model extension | Week 3 |
| Reason Templates (Q8) | Low | Low | UI design | Week 4+ |

---

## Immediate Frontend Actions (No Backend Dependency)

1. Enforce Date Range Limit (Do Now)

```typescript
const MAX_DATE_RANGE_DAYS = 90;

const handleDateChange = (start: Date, end: Date) => {
  const daysDiff = differenceInDays(end, start);

  if (daysDiff > MAX_DATE_RANGE_DAYS) {
    toast.warning(
      `Date range limited to ${MAX_DATE_RANGE_DAYS} days for performance. ` +
      `Please use the export feature for larger ranges.`,
    );
    setEndDate(addDays(start, MAX_DATE_RANGE_DAYS));
    return;
  }

  setStartDate(start);
  setEndDate(end);
};
```

2. Graceful Quantity Snapshot Handling (Do Now)

```typescript
<td className="text-center">
  {movement.quantity_before !== null && movement.quantity_after !== null ? (
    <div>
      <span className="text-gray-500">{movement.quantity_before}</span>
      <ArrowRight className="inline mx-1 h-3 w-3" />
      <span className="font-medium">{movement.quantity_after}</span>
      <span className={getQuantityColor(movement.quantity)}>
        ({movement.quantity > 0 ? '+' : ''}{movement.quantity})
      </span>
    </div>
  ) : (
    <div>
      <span className={getQuantityColor(movement.quantity)}>
        {movement.quantity > 0 ? '+' : ''}{movement.quantity} units
      </span>
      <InfoIcon
        className="inline ml-1 h-3 w-3 text-gray-400"
        title="Historical snapshot not available"
      />
    </div>
  )}
</td>
```

3. Performer Fallback Logic (Do Now)

```typescript
const getPerformerDisplay = (movement: StockMovement): string => {
  if (movement.performed_by) {
    return movement.performed_by;
  }

  switch (movement.movement_type) {
    case 'sale':
      return 'System - Auto Sale';
    case 'adjustment':
      if (movement.reference_number?.startsWith('IMPORT-')) {
        return 'Data Migration';
      }
      return 'System - Adjustment';
    case 'transfer':
      return 'System - Transfer';
    default:
      return 'System';
  }
};
```

4. Transfer Direction Display (Do Now)

```typescript
{movement.movement_type === 'transfer' ? (
  <div>
    <Badge variant="blue" className="mb-1">
      Transfer
    </Badge>
    {movement.from_warehouse && movement.to_warehouse && (
      <div className="text-xs text-gray-500">
        {movement.from_warehouse} -> {movement.to_warehouse}
      </div>
    )}
  </div>
) : (
  <Badge variant={getMovementTypeBadge(movement.movement_type)}>
    {movement.movement_type}
  </Badge>
)}
```

5. Disable Export Until Backend Ready (Do Now)

```typescript
<Button
  onClick={() => toast.info('Export feature coming soon - backend implementation in progress')}
  disabled={true}
  variant="outline"
>
  <Download className="h-4 w-4 mr-2" />
  Export (Coming Soon)
</Button>

<Tooltip content="Export endpoint is under development. Expected completion: Week 2">
  <InfoIcon className="inline h-4 w-4 ml-2 text-gray-400" />
</Tooltip>
```

---

## Four-Week Implementation Roadmap

### Week 1: Critical Fixes (High Priority)

**Backend Tasks:**
- Fix `reference_id` to return actual Sale, Transfer, and Adjustment IDs
- Update `warehouse_id` to return UUID
- Implement database pagination (LIMIT and OFFSET in SQL)
- Add database indexes on `created_at`, `warehouse_id`, and `product_id` if missing

**Frontend Tasks:**
- Enforce 90-day maximum date range
- Add quantity snapshot fallback (show quantity only with info tooltip)
- Add performer fallback logic
- Disable export button with "Coming Soon" message

**Testing:**
- Load test with 10,000 movements across 90-day range (target: less than 2 seconds)
- Verify pagination works correctly with filters
- Confirm reference linking displays correct source records

**Acceptance Criteria:**
- Large date ranges do not cause timeouts
- Reference IDs link to actual source transactions
- Warehouse filters use UUIDs correctly

### Week 2: User Experience (Medium Priority)

**Backend Tasks:**
- Implement full dataset aggregations (before pagination)
- Add `net_change` calculation to warehouse and category aggregations
- Move search filter into SQL query
- Add `performed_by_id` UUID to responses
- Create `/export/` endpoint with filter support

**Frontend Tasks:**
- Update summary cards to use full aggregations
- Increase search debounce to 750ms
- Add "Searching" loading indicator
- Enable export button and wire to new endpoint
- Add export format selector (CSV versus Excel)

**Testing:**
- Verify aggregations match full filtered dataset
- Test search performance with large datasets
- Export 5,000 records and verify all filters applied
- Test export with special characters in product names

**Acceptance Criteria:**
- Summary cards show accurate totals
- Search returns results within 500ms
- Export respects all active filters

### Week 3: Polish and Enhancement (Low Priority)

**Backend Tasks:**
- Add schema migration for quantity snapshots (going forward)
- Implement snapshot capture in StockAdjustment, Sale, and Transfer save methods
- Add `performed_via` enum field
- Add `user_role` to performer attribution (optional)
- Add timezone support to export endpoint

**Frontend Tasks:**
- Update quantity display to show before and after when available
- Add role badges to performer column (if available)
- Add timezone selector to export dialog
- Add character count indicator to notes field (if filtering by notes added)

**Testing:**
- Create new adjustment and verify snapshot captured
- Test performer attribution with different user roles
- Export in different timezones and verify timestamps

**Acceptance Criteria:**
- New movements have quantity snapshots after deployment
- Performer attribution includes role context
- Export timestamps reflect the user's timezone

### Week 4: Optional Enhancements (Optional)

**Backend Tasks:**
- Split transfer records into out and in pairs (if approved)
- Add predefined reason templates for adjustments
- Implement `by_product` aggregation (if requested)
- Add materialized view for common date ranges (performance optimization)

**Frontend Tasks:**
- If transfers split, update UI to show paired records with matching reference
- Add reason template dropdown for adjustment filtering
- Add product-level aggregation view
- Add quick date range shortcuts (Today, Yesterday, Last 7 Days, and so on)

**Testing:**
- Full regression test of all features
- Performance benchmark (target: 10,000 movements in less than 2 seconds)
- User acceptance testing
- Mobile responsive testing

**Acceptance Criteria:**
- All planned features functional
- Performance targets met
- User feedback incorporated

---

## Testing Strategy

### Unit Tests (Backend)

```python
def test_reference_id_returns_actual_source_id():
    sale = Sale.objects.create(...)
    movement = MovementTracker.get_movements({'sale_id': sale.id})[0]
    assert movement['reference_id'] == str(sale.id)

def test_pagination_uses_sql_not_python():
    create_10000_movements()
    with assert_num_queries(1):
        response = client.get('/reports/api/inventory/movements/?page=1&page_size=20')
    assert len(response.data['data']['movements']) == 20

def test_aggregations_respect_filters():
    create_movements(warehouse_a=100, warehouse_b=200)
    response = client.get('/reports/api/inventory/movements/?warehouse_id=A')
    assert response.data['data']['summary']['total_movements'] == 100
    assert 'A' in response.data['data']['by_warehouse']
    assert 'B' not in response.data['data']['by_warehouse']
```

### Integration Tests (Frontend)

```typescript
describe('Stock Movements Report', () => {
  it('enforces 90-day maximum date range', () => {
    const { getByLabelText, getByText } = render(<StockMovementsPage />);

    const startDate = new Date('2025-01-01');
    const endDate = new Date('2025-04-10');

    fireEvent.change(getByLabelText('Start Date'), { target: { value: startDate } });
    fireEvent.change(getByLabelText('End Date'), { target: { value: endDate } });

    expect(getByText(/Date range limited to 90 days/)).toBeInTheDocument();
    expect(getByLabelText('End Date').value).toBe('2025-03-31');
  });

  it('shows quantity fallback when snapshots unavailable', () => {
    const movement = { quantity: -50, quantity_before: null, quantity_after: null };

    const { getByText, getByTitle } = render(<MovementRow movement={movement} />);

    expect(getByText('-50 units')).toBeInTheDocument();
    expect(getByTitle('Historical snapshot not available')).toBeInTheDocument();
  });

  it('disables export button until backend ready', () => {
    const { getByRole } = render(<StockMovementsPage />);

    const exportButton = getByRole('button', { name: /Export/i });
    expect(exportButton).toBeDisabled();
    expect(exportButton).toHaveTextContent('Coming Soon');
  });
});
```

---

## Success Metrics

### Performance KPIs

| Metric | Current | Target | Week 1 | Week 2 | Week 4 |
|--------|---------|--------|--------|--------|--------|
| Initial Load (30 days) | ~1s | < 2s | Done | Done | Done |
| Filter Change | ~2s | < 500ms | Pending | Done | Done |
| Search Query | ~1.5s | < 500ms | Pending | Done | Done |
| Pagination | ~1s | < 300ms | Done | Done | Done |
| Export (5K records) | N/A | < 10s | Pending | Done | Done |
| 90-day Load | ~10s | < 5s | Pending | Done | Done |

### Data Quality KPIs

| Metric | Current | Target |
|--------|---------|--------|
| Reference ID Accuracy | 0% | 100% |
| Warehouse UUID Usage | 0% | 100% |
| Snapshot Capture Rate | 0% | 100% (new movements) |
| Performer Attribution | ~70% | 95% |
| Aggregation Accuracy | ~30% (page only) | 100% (full dataset) |

### User Experience KPIs

| Metric | Target |
|--------|--------|
| Mobile Responsiveness | 100% features work on mobile |
| Empty State Clarity | Clear messaging for zero results |
| Error Message Helpfulness | Actionable guidance in all errors |
| Filter Intuition | Users can combine filters without documentation |
| Export Reliability | < 1% failure rate |

---

## Risk Assessment

### High-Risk Items

1. Database Pagination Migration
   - Risk: Existing Python code tightly couples filtering and pagination
   - Impact: May require significant refactor of MovementTracker
   - Mitigation: Create new `get_paginated_movements()` method, keep old one for compatibility
   - Timeline Risk: Could extend Week 1 into Week 2

2. Quantity Snapshot Schema Migration
   - Risk: Adding columns to high-traffic tables (sales, adjustments, transfers)
   - Impact: Could cause downtime during migration on large databases
   - Mitigation: Use online schema migration tools (such as pt-online-schema-change)
   - Timeline Risk: May need maintenance window

### Medium-Risk Items

3. Export Streaming Implementation
   - Risk: Large exports could timeout if not properly chunked
   - Impact: Users frustrated with failed exports
   - Mitigation: Implement proper streaming, add row limits, offer background job option
   - Timeline Risk: May need Week 3 for robust solution

4. Aggregation Performance
   - Risk: Full dataset aggregation on 50,000+ movements could be slow
   - Impact: Summary cards load slowly
   - Mitigation: Use database aggregation functions, consider caching
   - Timeline Risk: May need additional optimization in Week 3

### Low-Risk Items

5. Frontend UI Updates
   - Risk: Minimal, mostly presentation layer changes
   - Impact: Low, graceful degradation already planned
   - Mitigation: Thorough testing before deployment

---

## Next Steps and Ownership

### Backend Team Actions

Week 1:
- Review this document and flag any misunderstandings
- Prioritize tasks: reference linking, database pagination, warehouse UUIDs
- Create implementation plan for Priority 1 items
- Schedule daily standups with frontend team

Week 2:
- Implement Priority 2 items (aggregations, search, export)
- Provide sample responses for frontend testing
- Document new endpoints in API specification

Week 3-4:
- Address Priority 3 enhancements
- Performance optimization
- Support user acceptance testing

### Frontend Team Actions

Week 1:
- Implement immediate fixes (date range limit, fallbacks, disable export)
- Create comprehensive test scenarios
- Prepare mockups for transfer direction display
- Update TypeScript types as backend schema evolves

Week 2:
- Integrate with new export endpoint
- Update summary card logic for full aggregations
- Add search loading indicators
- Test with production-like data

Week 3-4:
- Polish UI based on user feedback
- Mobile responsive testing
- Performance optimization (memoization, virtualization)
- Documentation updates

### Product and PM Actions

Decisions Needed:
- Transfer Records: Single record versus split out and in records
- Export Limits: Maximum 50,000 rows; offer background job for larger exports
- Snapshot Backfill: Accept data loss for historical movements
- Date Range Enforcement: Hard limit at 90 days or soft warning

Timeline Approval:
- Review four-week roadmap
- Approve priority order
- Allocate resources (backend and frontend hours)
- Set user acceptance testing schedule

---

## Related Documentation

- `docs/BACKEND-STOCK-MOVEMENTS-DATA-REQUIREMENTS.md`
- `docs/BACKEND-STOCK-MOVEMENTS-ALIGNMENT-RESPONSE.md` (this document)
- `docs/BACKEND-STOCK-LEVELS-RESERVED-CALCULATION-ISSUE.md`
- `frontend/src/features/reports/pages/StockMovementsPage.tsx`
- `backend/reports/views/inventory_reports.py`
- `backend/reports/services/movement_tracker.py`

---

## Communication Plan

### Standup Updates (Daily)
- Backend progress on Priority 1 items
- Frontend blockers needing backend data
- Any new issues discovered during implementation

### Weekly Demo (Fridays)
- Show working features from completed week
- Capture stakeholder feedback
- Adjust priorities if needed

### Bi-Weekly Retrospective
- What went well
- What could improve
- Process adjustments

---

**Status:** READY FOR BACKEND TEAM PRIORITIZATION  
**Created:** October 31, 2025  
**Next Review:** November 1, 2025 (Backend team response expected)  
**Target Completion:** November 28, 2025 (4 weeks from now)
