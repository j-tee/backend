# Frontend Implementation Guide - Stock Reconciliation Modal

**Date:** 2025-10-09  
**Related Guides:**
- [Stock Adjustment View & Edit Guide](./STOCK_ADJUSTMENT_EDIT_FRONTEND_GUIDE.md) - View and edit stock adjustments

## API Response Structure

```typescript
interface StockReconciliationResponse {
  product: {
    id: string;
    name: string;
    sku: string;
  };
  warehouse: {
    recorded_quantity: number;        // Sum of StockProduct.quantity (what was received)
    inventory_on_hand: number;        // Computed: recorded_quantity - storefront.total_on_hand
    batches: Array<{
      stock_product_id: string;
      warehouse_id: string | null;
      warehouse_name: string | null;
      quantity: number;
      arrival_date: string | null;
    }>;
    inventory_breakdown: Array<{      // For audit only, not used in main calculations
      warehouse_id: string;
      warehouse_name: string;
      quantity: number;
    }>;
  };
  storefront: {
    total_on_hand: number;            // Sum of StoreFrontInventory.quantity
    breakdown: Array<{                // Per-storefront details
      storefront_id: string;
      storefront_name: string;
      on_hand: number;                // Total at this location
      sellable: number;               // on_hand - reserved
      reserved: number;               // Active cart reservations
    }>;
  };
  sales: {
    completed_units: number;          // Sum of sold quantities
    completed_value: number;          // Revenue from sales
    completed_sale_ids: string[];     // Sale IDs for reference
  };
  adjustments: {
    shrinkage_units: number;          // Negative adjustments (loss/damage/theft)
    correction_units: number;         // Positive adjustments (found inventory)
  };
  reservations: {
    linked_units: number;             // Reservations tied to active sales
    orphaned_units: number;           // Reservations without valid sales
    linked_count: number;
    orphaned_count: number;
    details: Array<{
      id: string;
      quantity: number;
      cart_session_id: string;
      linked_sale_id: string | null;
      expires_at: string;
    }>;
  };
  formula: {
    warehouse_inventory_on_hand: number;    // Same as warehouse.inventory_on_hand
    storefront_on_hand: number;             // Same as storefront.total_on_hand
    completed_sales_units: number;          // Same as sales.completed_units
    shrinkage_units: number;                // Same as adjustments.shrinkage_units
    correction_units: number;               // Same as adjustments.correction_units
    active_reservations_units: number;      // Same as reservations.linked_units
    calculated_baseline: number;            // Computed reconciliation result
    recorded_batch_quantity: number;        // Same as warehouse.recorded_quantity
    baseline_vs_recorded_delta: number;     // recorded - baseline (should be 0)
  };
}
```

## UI Component Mapping

### Top Section
```tsx
<ProductInfo>
  <Label>Recorded batch size:</Label>
  <Badge>{data.warehouse.recorded_quantity}</Badge>
  
  <Label>Warehouse on hand:</Label>
  <Badge>{data.warehouse.inventory_on_hand}</Badge>
  
  <Label>Storefront on hand:</Label>
  <Badge>{data.storefront.total_on_hand}</Badge>
  
  <Label>Units sold:</Label>
  <Badge>{data.sales.completed_units}</Badge>
  
  <Label>Shrinkage / write-offs:</Label>
  <Badge variant="danger">{data.adjustments.shrinkage_units}</Badge>
  
  <Label>Corrections applied:</Label>
  <Badge variant="success">{data.adjustments.correction_units}</Badge>
  
  <Label>Active reservations:</Label>
  <Badge>{data.reservations.linked_units + data.reservations.orphaned_units}</Badge>
</ProductInfo>
```

### Reconciliation Formula Display
```tsx
<FormulaDisplay>
  Warehouse ({data.formula.warehouse_inventory_on_hand}) 
  + Storefront ({data.formula.storefront_on_hand}) 
  + Sold ({data.formula.completed_sales_units}) 
  − Shrinkage ({data.formula.shrinkage_units}) 
  + Corrections ({data.formula.correction_units}) 
  − Reservations ({data.formula.active_reservations_units}) 
  = {data.formula.calculated_baseline} 
  — Recorded batch size {data.formula.recorded_batch_quantity}
</FormulaDisplay>

{data.formula.baseline_vs_recorded_delta !== 0 && (
  <Alert variant="warning">
    Calculated baseline differs from recorded batch size by{' '}
    {Math.abs(data.formula.baseline_vs_recorded_delta)}{' '}
    {data.formula.baseline_vs_recorded_delta > 0 ? 'more' : 'fewer'} units. 
    Backend reconciliation required.
  </Alert>
)}
```

### Storefront Breakdown Section
```tsx
<StorefrontBreakdown title="STOREFRONT BREAKDOWN">
  {data.storefront.breakdown.map(store => (
    <StoreRow key={store.storefront_id}>
      <StoreName>{store.storefront_name}</StoreName>
      <Metrics>
        On hand: <Badge>{store.on_hand}</Badge>
        {' • '}
        Sellable: <Badge variant="success">{store.sellable}</Badge>
        {' • '}
        Reserved: <Badge variant="warning">{store.reserved}</Badge>
      </Metrics>
    </StoreRow>
  ))}
</StorefrontBreakdown>
```

## Key Implementation Notes

### 1. No Frontend Calculations Required
```tsx
// ❌ DON'T DO THIS
const warehouseOnHand = recordedBatch - storefrontOnHand;

// ✅ DO THIS
const warehouseOnHand = data.warehouse.inventory_on_hand;
```

### 2. Handle Missing Data Gracefully
```tsx
const snapshot = await fetchReconciliation(productId);

if (!snapshot) {
  return <EmptyState message="Reconciliation snapshot not available yet." />;
}

// All values have defaults on backend, but defensive coding is good:
const warehouseOnHand = snapshot?.warehouse?.inventory_on_hand ?? 0;
```

### 3. Sellable vs Reserved
```tsx
// Per storefront:
store.on_hand      // What physically exists
store.sellable     // What customers can buy (on_hand - reserved)
store.reserved     // What's in active carts

// Total available for new sales across all stores:
const totalSellable = data.storefront.breakdown.reduce(
  (sum, store) => sum + store.sellable, 
  0
);
```

### 4. Warning States
```tsx
// Show warning when reconciliation doesn't match
if (data.formula.baseline_vs_recorded_delta !== 0) {
  showReconciliationWarning({
    delta: data.formula.baseline_vs_recorded_delta,
    baseline: data.formula.calculated_baseline,
    recorded: data.formula.recorded_batch_quantity,
  });
}

// Show info when there are orphaned reservations
if (data.reservations.orphaned_units > 0) {
  showOrphanedReservationsInfo({
    count: data.reservations.orphaned_count,
    units: data.reservations.orphaned_units,
  });
}
```

## Common Pitfalls to Avoid

### ❌ Don't recalculate warehouse inventory
```tsx
// WRONG - ignores backend business logic
const warehouseOnHand = recordedBatch - transfers;
```

### ❌ Don't assume storefront breakdown exists
```tsx
// WRONG - may throw if no storefronts
const firstStore = data.storefront.breakdown[0].on_hand;

// RIGHT
const firstStore = data.storefront.breakdown[0]?.on_hand ?? 0;
```

### ❌ Don't conflate Inventory table with warehouse on-hand
```tsx
// The warehouse.inventory_breakdown[] array is for audit purposes only
// It shows raw Inventory table rows, which may not match the computed
// warehouse.inventory_on_hand value due to how transfers work

// Use warehouse.inventory_on_hand for display, not inventory_breakdown
```

## Testing Checklist

- [ ] Modal displays all metrics from API response without calculation
- [ ] Storefront breakdown shows per-store on-hand, sellable, reserved
- [ ] Warning appears when `baseline_vs_recorded_delta ≠ 0`
- [ ] "Refresh snapshot" button re-fetches and updates all values
- [ ] Handles missing/null values gracefully
- [ ] Shows appropriate empty state when endpoint returns 404 or error
- [ ] Formula display matches backend calculation exactly

## Questions?

If any field seems wrong or confusing:
1. Check the network response in DevTools to see actual API payload
2. Verify you're reading from the correct response path
3. Confirm you're not doing any transformations/calculations
4. Share the network payload with backend team for investigation

The reconciliation system is designed to surface data inconsistencies—warnings are features, not bugs!
