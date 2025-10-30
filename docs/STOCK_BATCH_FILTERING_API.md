# Stock Batch Filtering API Documentation

## Overview

The Stock API now supports viewing detailed statistics filtered by individual batches. This allows the frontend to show aggregated data across all batches or drill down into specific batch statistics.

## Key Concepts

### What is a Batch?

- A **Stock** record represents a batch of inventory received at a specific time
- Each Stock can contain multiple **StockProduct** items (different products in the same batch)
- The same product can appear in multiple batches (e.g., "10mm Metal Cable" received on different dates)

### Database Structure

```
Stock (Batch)
├── id: UUID
├── business: ForeignKey
├── arrival_date: Date
├── description: Text (batch notes/identifier)
└── items: Many StockProducts
    ├── product: ForeignKey
    ├── quantity: Integer
    ├── warehouse: ForeignKey
    └── ... (cost, prices, etc.)
```

## API Endpoints

### 1. List All Stocks (Batches)

**Endpoint:** `GET /api/inventory/stocks/`

**Response:**
```json
{
  "count": 10,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "batch-uuid",
      "business": "business-uuid",
      "business_name": "My Business",
      "arrival_date": "2025-10-28",
      "description": "Some cool Optional Notes",
      "warehouse_id": "warehouse-uuid",
      "warehouse_name": "Rawlings Park Warehouse",
      "total_items": 1,
      "total_quantity": 200,
      "items": [...],
      "created_at": "2025-10-28T14:29:00Z",
      "updated_at": "2025-10-28T14:29:00Z"
    }
  ]
}
```

### 2. Get Stock Details (Aggregated - All Batches)

**Endpoint:** `GET /api/inventory/stocks/{stock_id}/`

**Description:** Shows aggregated statistics across all batches for products in this stock.

**Response:**
```json
{
  "id": "stock-uuid",
  "business": "business-uuid",
  "business_name": "My Business",
  "arrival_date": "2025-10-28",
  "description": "Some cool Optional Notes",
  
  // Warehouse info
  "warehouse_id": "warehouse-uuid",
  "warehouse_name": "Rawlings Park Warehouse",
  
  // Basic counts
  "total_items": 2,
  "total_quantity": 400,
  
  // Batch information
  "batches": [
    {
      "id": "batch-1-uuid",
      "batch_identifier": "Some cool Optional Notes",
      "batch_size": 200,
      "created_at": "2025-10-28T14:29:00Z",
      "arrival_date": "2025-10-28"
    },
    {
      "id": "batch-2-uuid",
      "batch_identifier": "Another batch notes",
      "batch_size": 200,
      "created_at": "2025-10-28T15:30:00Z",
      "arrival_date": "2025-10-28"
    }
  ],
  "selected_batch_id": null,  // null = aggregated view
  
  // Inventory statistics (aggregated across all batches)
  "batch_size": 400,
  "warehouse_quantity": 400,
  "storefront_transferred": 0,
  "available_for_sale": 400,
  "sold": 0,
  "reserved": 0,
  "shrinkage": 0,
  "corrections": 0,
  
  // Financial
  "landed_cost": "82.10",
  
  // Reconciliation
  "reconciliation_formula": "Warehouse (400) + Storefront transferred (0) - Shrinkage (0) + Corrections (0) - Reservations (0) = 400",
  "inventory_balanced": true,
  
  // Item details
  "items": [
    {
      "id": "item-uuid",
      "product": {...},
      "quantity": 200,
      ...
    }
  ],
  
  "created_at": "2025-10-28T14:29:00Z",
  "updated_at": "2025-10-28T14:29:00Z"
}
```

### 3. Get Stock Details (Filtered by Specific Batch)

**Endpoint:** `GET /api/inventory/stocks/{stock_id}/?batch_id={batch_uuid}`

**Description:** Shows statistics for ONLY the specified batch.

**Query Parameters:**
- `batch_id` (UUID, optional): Filter statistics by specific batch

**Response:**
```json
{
  "id": "stock-uuid",
  "business": "business-uuid",
  "business_name": "My Business",
  "arrival_date": "2025-10-28",
  "description": "Some cool Optional Notes",
  
  "warehouse_id": "warehouse-uuid",
  "warehouse_name": "Rawlings Park Warehouse",
  
  "total_items": 1,  // Only items in selected batch
  "total_quantity": 200,  // Only quantity in selected batch
  
  // Batch list (always shows all available batches)
  "batches": [
    {
      "id": "batch-1-uuid",
      "batch_identifier": "Some cool Optional Notes",
      "batch_size": 200,
      "created_at": "2025-10-28T14:29:00Z",
      "arrival_date": "2025-10-28"
    },
    {
      "id": "batch-2-uuid",
      "batch_identifier": "Another batch notes",
      "batch_size": 200,
      "created_at": "2025-10-28T15:30:00Z",
      "arrival_date": "2025-10-28"
    }
  ],
  "selected_batch_id": "batch-1-uuid",  // Indicates filtered view
  
  // Statistics ONLY for selected batch
  "batch_size": 200,
  "warehouse_quantity": 200,
  "storefront_transferred": 0,
  "available_for_sale": 200,
  "sold": 0,
  "reserved": 0,
  "shrinkage": 0,
  "corrections": 0,
  
  "landed_cost": "41.05",  // Only for selected batch
  
  "reconciliation_formula": "Warehouse (200) + Storefront transferred (0) - Shrinkage (0) + Corrections (0) - Reservations (0) = 200",
  "inventory_balanced": true,
  
  // Items ONLY from selected batch
  "items": [
    {
      "id": "item-uuid",
      "product": {...},
      "quantity": 200,
      ...
    }
  ],
  
  "created_at": "2025-10-28T14:29:00Z",
  "updated_at": "2025-10-28T14:29:00Z"
}
```

## Frontend Implementation Guide

### 1. TypeScript Interfaces

```typescript
interface BatchInfo {
  id: string;
  batch_identifier: string;
  batch_size: number;
  created_at: string;
  arrival_date: string;
}

interface StockDetail {
  id: string;
  business: string;
  business_name: string;
  arrival_date: string;
  description: string;
  
  warehouse_id: string;
  warehouse_name: string;
  
  total_items: number;
  total_quantity: number;
  
  // Batch filtering
  batches: BatchInfo[];
  selected_batch_id: string | null;
  
  // Statistics
  batch_size: number;
  warehouse_quantity: number;
  storefront_transferred: number;
  available_for_sale: number;
  sold: number;
  reserved: number;
  shrinkage: number;
  corrections: number;
  
  landed_cost: string;
  reconciliation_formula: string;
  inventory_balanced: boolean;
  
  items: StockProductItem[];
  created_at: string;
  updated_at: string;
}
```

### 2. React Component Example

```typescript
import { useState, useEffect } from 'react';

interface StockDetailViewProps {
  stockId: string;
}

export function StockDetailView({ stockId }: StockDetailViewProps) {
  const [stockDetail, setStockDetail] = useState<StockDetail | null>(null);
  const [selectedBatchId, setSelectedBatchId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchStockDetail();
  }, [stockId, selectedBatchId]);

  const fetchStockDetail = async () => {
    setLoading(true);
    try {
      const url = selectedBatchId
        ? `/api/inventory/stocks/${stockId}/?batch_id=${selectedBatchId}`
        : `/api/inventory/stocks/${stockId}/`;
      
      const response = await fetch(url);
      const data = await response.json();
      setStockDetail(data);
    } catch (error) {
      console.error('Failed to fetch stock detail:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleBatchChange = (batchId: string | null) => {
    setSelectedBatchId(batchId);
  };

  if (!stockDetail) return <div>Loading...</div>;

  const showBatchDropdown = stockDetail.batches.length > 1;

  return (
    <div className="stock-detail">
      <h2>{stockDetail.warehouse_name}</h2>
      
      {/* Batch Dropdown - Only show if multiple batches */}
      {showBatchDropdown && (
        <div className="batch-filter">
          <label>Batch:</label>
          <select
            value={selectedBatchId || ''}
            onChange={(e) => handleBatchChange(e.target.value || null)}
          >
            <option value="">All batches</option>
            {stockDetail.batches.map((batch) => (
              <option key={batch.id} value={batch.id}>
                {batch.batch_identifier || 'Unnamed batch'} 
                ({new Date(batch.created_at).toLocaleDateString()})
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Statistics Grid */}
      <div className="stats-grid">
        <div className="stat">
          <label>Batch Size</label>
          <value>{stockDetail.batch_size}</value>
          <caption>Recorded</caption>
        </div>
        
        <div className="stat">
          <label>Warehouse</label>
          <value>{stockDetail.warehouse_quantity}</value>
          <caption>On hand</caption>
        </div>
        
        <div className="stat">
          <label>Storefront</label>
          <value>{stockDetail.storefront_transferred}</value>
          <caption>Transferred</caption>
        </div>
        
        <div className="stat">
          <label>Available</label>
          <value>{stockDetail.available_for_sale}</value>
          <caption>For sale</caption>
        </div>
      </div>

      {/* Reconciliation */}
      <div className="reconciliation">
        <p>{stockDetail.reconciliation_formula}</p>
        <span className={stockDetail.inventory_balanced ? 'balanced' : 'unbalanced'}>
          {stockDetail.inventory_balanced ? '✓ Balanced' : '⚠ Unbalanced'}
        </span>
      </div>

      {/* Show which view is active */}
      {selectedBatchId && (
        <div className="filter-indicator">
          Showing statistics for: {stockDetail.batches.find(b => b.id === selectedBatchId)?.batch_identifier}
        </div>
      )}
    </div>
  );
}
```

### 3. Vue.js Example

```vue
<template>
  <div class="stock-detail">
    <h2>{{ stockDetail?.warehouse_name }}</h2>
    
    <!-- Batch Dropdown -->
    <div v-if="showBatchDropdown" class="batch-filter">
      <label>Batch:</label>
      <select v-model="selectedBatchId">
        <option :value="null">All batches</option>
        <option 
          v-for="batch in stockDetail?.batches" 
          :key="batch.id" 
          :value="batch.id"
        >
          {{ batch.batch_identifier || 'Unnamed batch' }}
          ({{ formatDate(batch.created_at) }})
        </option>
      </select>
    </div>

    <!-- Statistics -->
    <div class="stats-grid">
      <div class="stat">
        <label>Batch Size</label>
        <div class="value">{{ stockDetail?.batch_size }}</div>
        <div class="caption">Recorded</div>
      </div>
      <!-- ... other stats ... -->
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';

const props = defineProps<{
  stockId: string;
}>();

const stockDetail = ref<StockDetail | null>(null);
const selectedBatchId = ref<string | null>(null);

const showBatchDropdown = computed(() => 
  stockDetail.value && stockDetail.value.batches.length > 1
);

watch([() => props.stockId, selectedBatchId], () => {
  fetchStockDetail();
});

async function fetchStockDetail() {
  const url = selectedBatchId.value
    ? `/api/inventory/stocks/${props.stockId}/?batch_id=${selectedBatchId.value}`
    : `/api/inventory/stocks/${props.stockId}/`;
  
  const response = await fetch(url);
  stockDetail.value = await response.json();
}

function formatDate(dateString: string) {
  return new Date(dateString).toLocaleDateString();
}
</script>
```

## Statistics Explanation

### Field Definitions

| Field | Description | Filtered by batch_id? |
|-------|-------------|----------------------|
| `batch_size` | Total quantity recorded when batch arrived | ✅ Yes |
| `warehouse_quantity` | Current quantity in warehouse (after movements) | ✅ Yes |
| `storefront_transferred` | Quantity sent to storefronts via transfer requests | ✅ Yes |
| `available_for_sale` | warehouse + storefront - sold - reserved | ✅ Yes |
| `sold` | Quantity sold from storefronts | ✅ Yes |
| `reserved` | Quantity reserved for future sales | ✅ Yes |
| `shrinkage` | Losses (theft, damage, expiry, etc.) | ✅ Yes |
| `corrections` | Inventory adjustments/corrections | ✅ Yes |
| `landed_cost` | Total cost including taxes and additional costs | ✅ Yes |
| `batches` | List of all available batches | ❌ No (always shows all) |

### Reconciliation Formula

The reconciliation formula shows how the available quantity is calculated:

```
Warehouse + Storefront - Shrinkage + Corrections - Reservations = Available
```

Example:
```
Warehouse (200) + Storefront transferred (0) - Shrinkage (0) + Corrections (0) - Reservations (0) = 200
```

### Inventory Balanced

- `true`: The calculated quantity matches the expected quantity
- `false`: There's a discrepancy (investigate shrinkage, corrections, or data issues)

## Use Cases

### 1. Product with Single Batch
```
batches.length === 1
→ Don't show dropdown
→ Show statistics directly (no need to filter)
```

### 2. Product with Multiple Batches
```
batches.length > 1
→ Show batch dropdown
→ Default: "All batches" (aggregated)
→ User can select specific batch to drill down
```

### 3. Comparing Batches
```
1. View aggregated statistics
2. Select Batch A → See Batch A's performance
3. Select Batch B → Compare Batch B's performance
4. Select "All batches" → See total again
```

## Error Handling

### Invalid batch_id

```json
{
  "detail": "Invalid batch_id parameter"
}
```

### Non-existent batch

If `batch_id` doesn't match any batches for this product:
- Statistics will show zeros
- `selected_batch_id` will still be set
- Frontend should validate against `batches` array

## Testing

### Manual Testing

```bash
# Get aggregated view
curl http://localhost:8000/api/inventory/stocks/{stock-uuid}/

# Get filtered view
curl http://localhost:8000/api/inventory/stocks/{stock-uuid}/?batch_id={batch-uuid}

# Test with invalid batch_id
curl http://localhost:8000/api/inventory/stocks/{stock-uuid}/?batch_id=invalid-uuid
```

### Frontend Testing Checklist

- [ ] Single batch: Dropdown hidden
- [ ] Multiple batches: Dropdown visible
- [ ] "All batches" selected: Shows aggregated statistics
- [ ] Specific batch selected: Shows filtered statistics
- [ ] Batch change: Stats update correctly
- [ ] URL parameter persists on page refresh
- [ ] Invalid batch_id handled gracefully

## Migration Notes

### Breaking Changes
❌ None - This is a backward-compatible enhancement

### New Fields
The following fields are NEW in the retrieve endpoint:
- `batches`
- `selected_batch_id`
- `batch_size` (was `total_quantity` before)
- `warehouse_quantity`
- `storefront_transferred`
- `available_for_sale`
- `sold`
- `reserved`
- `shrinkage`
- `corrections`
- `landed_cost`
- `reconciliation_formula`
- `inventory_balanced`

### Existing Fields
- `items`: Still works, filtered by batch if `batch_id` provided
- `total_items`: Now respects batch filter
- `total_quantity`: Still works (same as `batch_size`)

## Support

For questions or issues:
1. Check this documentation
2. Review the API response structure
3. Test with curl/Postman first
4. Contact backend team with specific endpoint and parameters

---

**Version:** 1.0  
**Last Updated:** October 30, 2025  
**Status:** ✅ Implemented and Ready for Frontend Integration
