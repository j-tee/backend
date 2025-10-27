# Phase 5: Frontend Integration Guide

**Target:** Frontend Team  
**Duration:** Week 5 of 9-Week Plan  
**Backend Status:** ✅ Ready for Integration

---

## Overview

This guide helps the frontend team integrate with the new Transfer API endpoints that replace the legacy `stock-adjustments/transfer` system.

---

## Backend Endpoints Ready

### Base URL
```
{API_BASE_URL}/inventory/api/
```

### Authentication
All endpoints require authentication via Token:
```
Authorization: Token {user-auth-token}
```

---

## API Endpoints

### 1. Warehouse Transfers

#### List Warehouse Transfers
```http
GET /inventory/api/warehouse-transfers/
```

**Query Parameters:**
- `status` (optional): `pending`, `in_transit`, `completed`, `cancelled`
- `source_warehouse` (optional): UUID
- `destination_warehouse` (optional): UUID
- `start_date` (optional): YYYY-MM-DD
- `end_date` (optional): YYYY-MM-DD
- `search` (optional): Search reference_number or notes
- `page` (optional): Page number (default: 1)
- `page_size` (optional): Items per page (default: 20)

**Response:**
```json
{
  "count": 100,
  "next": "http://api/warehouse-transfers/?page=2",
  "previous": null,
  "results": [
    {
      "id": "uuid",
      "reference_number": "TRF-20241027153045",
      "status": "pending",
      "source_warehouse": "warehouse-uuid",
      "source_warehouse_name": "Main Warehouse",
      "destination_warehouse": "warehouse-uuid",
      "destination_warehouse_name": "Branch Warehouse",
      "notes": "Monthly restock",
      "items": [
        {
          "id": "item-uuid",
          "product": "product-uuid",
          "product_name": "Widget A",
          "product_sku": "WDG-001",
          "quantity": 100,
          "unit_cost": "10.50",
          "total_cost": "1050.00"
        }
      ],
      "created_by": "user-uuid",
      "created_by_name": "John Doe",
      "created_at": "2024-10-27T15:30:45Z",
      "completed_by": null,
      "completed_by_name": null,
      "completed_at": null
    }
  ]
}
```

#### Create Warehouse Transfer
```http
POST /inventory/api/warehouse-transfers/
Content-Type: application/json

{
  "source_warehouse": "uuid",
  "destination_warehouse": "uuid",
  "notes": "Monthly restock",
  "items": [
    {
      "product": "product-uuid",
      "quantity": 100,
      "unit_cost": "10.50"
    }
  ]
}
```

**Validation Rules:**
- ✅ At least one item required
- ✅ Source and destination must be different
- ✅ Quantity must be > 0
- ✅ Unit cost must be >= 0
- ✅ No duplicate products

**Response:** Same as single transfer object (201 Created)

#### Get Transfer Details
```http
GET /inventory/api/warehouse-transfers/{id}/
```

**Response:** Single transfer object

#### Update Transfer (Pending Only)
```http
PUT /inventory/api/warehouse-transfers/{id}/
PATCH /inventory/api/warehouse-transfers/{id}/
```

**Note:** Can only update transfers with status `pending`

#### Delete Transfer (Pending Only)
```http
DELETE /inventory/api/warehouse-transfers/{id}/
```

**Response:** 204 No Content

**Note:** Cannot delete completed transfers

#### Complete Transfer
```http
POST /inventory/api/warehouse-transfers/{id}/complete/
Content-Type: application/json

{
  "notes": "All items received and verified"
}
```

**Effect:**
- Status → `completed`
- Inventory moves from source to destination
- Sets `completed_by` and `completed_at`
- Creates stock movement records

**Response:** Updated transfer object

#### Cancel Transfer
```http
POST /inventory/api/warehouse-transfers/{id}/cancel/
Content-Type: application/json

{
  "reason": "Order cancelled by management"
}
```

**Effect:**
- Status → `cancelled`
- Reason appended to notes
- No inventory movement

**Response:** Updated transfer object

---

### 2. Storefront Transfers

Same endpoints as warehouse transfers, but use:
- Base path: `/inventory/api/storefront-transfers/`
- Use `destination_storefront` instead of `destination_warehouse`

**Create Example:**
```json
{
  "source_warehouse": "uuid",
  "destination_storefront": "uuid",
  "notes": "Daily stock replenishment",
  "items": [...]
}
```

---

## Migration from Legacy Endpoint

### Old Endpoint (Deprecated)
```http
POST /inventory/api/stock-adjustments/transfer/
```

### New Endpoints
```http
POST /inventory/api/warehouse-transfers/      # For warehouse-to-warehouse
POST /inventory/api/storefront-transfers/     # For warehouse-to-storefront
```

### Key Differences

| Aspect | Old System | New System |
|--------|-----------|------------|
| Request | Single endpoint | Separate endpoints by type |
| Items | Part of request | Nested items array |
| Reference | Manual | Auto-generated |
| Status | Immediate completion | Pending → Complete workflow |
| Validation | Minimal | Comprehensive |
| Response | Adjustment pairs | Single transfer object |

### Migration Steps

1. **Identify Transfer Type**
   - Warehouse-to-warehouse → Use `/warehouse-transfers/`
   - Warehouse-to-storefront → Use `/storefront-transfers/`

2. **Update Request Format**
   ```javascript
   // OLD FORMAT
   const oldRequest = {
     source_warehouse: 'uuid',
     destination: 'uuid',
     products: [
       {product_id: 'uuid', quantity: 100}
     ]
   };
   
   // NEW FORMAT
   const newRequest = {
     source_warehouse: 'uuid',
     destination_warehouse: 'uuid', // or destination_storefront
     notes: '',
     items: [
       {
         product: 'uuid',
         quantity: 100,
         unit_cost: '10.50'
       }
     ]
   };
   ```

3. **Handle Response**
   ```javascript
   // OLD: Returns two adjustment records
   {
     transfer_out: {...},
     transfer_in: {...}
   }
   
   // NEW: Returns single transfer with items
   {
     id: 'uuid',
     reference_number: 'TRF-...',
     status: 'pending',
     items: [...]
   }
   ```

4. **Add Complete Step**
   ```javascript
   // After creating transfer, complete it:
   await fetch(`/warehouse-transfers/${transferId}/complete/`, {
     method: 'POST',
     headers: {
       'Authorization': `Token ${token}`,
       'Content-Type': 'application/json'
     },
     body: JSON.stringify({
       notes: 'Transfer completed'
     })
   });
   ```

---

## Frontend Components Needed

### 1. Transfer List Component
- Display paginated list of transfers
- Filter by status, date range, warehouse
- Search by reference number
- Show transfer summary (items count, total value)

### 2. Create Transfer Form
- Select source warehouse
- Select destination (warehouse or storefront)
- Add multiple items with quantities and costs
- Auto-calculate total cost
- Validate before submit

### 3. Transfer Detail View
- Show all transfer information
- List all items with details
- Display status workflow
- Show created/completed timestamps and users

### 4. Transfer Actions
- Complete button (for pending/in_transit)
- Cancel button (for pending/in_transit)
- Edit button (for pending only)
- Delete button (for pending only)

### 5. Status Badge Component
- Color-coded status indicators:
  - Pending: Yellow/Orange
  - In Transit: Blue
  - Completed: Green
  - Cancelled: Red/Gray

---

## Example Frontend Code

### React Example

```typescript
// types.ts
interface TransferItem {
  id?: string;
  product: string;
  product_name?: string;
  product_sku?: string;
  quantity: number;
  unit_cost: string;
  total_cost?: string;
}

interface Transfer {
  id: string;
  reference_number: string;
  status: 'pending' | 'in_transit' | 'completed' | 'cancelled';
  source_warehouse: string;
  source_warehouse_name?: string;
  destination_warehouse?: string;
  destination_warehouse_name?: string;
  destination_storefront?: string;
  destination_storefront_name?: string;
  notes: string;
  items: TransferItem[];
  created_by: string;
  created_by_name?: string;
  created_at: string;
  completed_by?: string;
  completed_by_name?: string;
  completed_at?: string;
}

// api.ts
const API_BASE = '/inventory/api';

export async function listWarehouseTransfers(params?: {
  status?: string;
  source_warehouse?: string;
  destination_warehouse?: string;
  start_date?: string;
  end_date?: string;
  search?: string;
  page?: number;
}): Promise<PaginatedResponse<Transfer>> {
  const queryString = new URLSearchParams(params).toString();
  const response = await fetch(
    `${API_BASE}/warehouse-transfers/?${queryString}`,
    {
      headers: {
        'Authorization': `Token ${getToken()}`,
      }
    }
  );
  
  if (!response.ok) throw new Error('Failed to fetch transfers');
  return response.json();
}

export async function createWarehouseTransfer(data: {
  source_warehouse: string;
  destination_warehouse: string;
  notes?: string;
  items: TransferItem[];
}): Promise<Transfer> {
  const response = await fetch(`${API_BASE}/warehouse-transfers/`, {
    method: 'POST',
    headers: {
      'Authorization': `Token ${getToken()}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(data),
  });
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(JSON.stringify(error));
  }
  
  return response.json();
}

export async function completeTransfer(
  id: string,
  notes?: string
): Promise<Transfer> {
  const response = await fetch(
    `${API_BASE}/warehouse-transfers/${id}/complete/`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Token ${getToken()}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ notes }),
    }
  );
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(JSON.stringify(error));
  }
  
  return response.json();
}

export async function cancelTransfer(
  id: string,
  reason: string
): Promise<Transfer> {
  const response = await fetch(
    `${API_BASE}/warehouse-transfers/${id}/cancel/`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Token ${getToken()}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ reason }),
    }
  );
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(JSON.stringify(error));
  }
  
  return response.json();
}

// TransferList.tsx
import React, { useEffect, useState } from 'react';
import { listWarehouseTransfers } from './api';

export const TransferList: React.FC = () => {
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState<string>('');
  
  useEffect(() => {
    loadTransfers();
  }, [status]);
  
  const loadTransfers = async () => {
    setLoading(true);
    try {
      const data = await listWarehouseTransfers({ status });
      setTransfers(data.results);
    } catch (error) {
      console.error('Failed to load transfers:', error);
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div>
      <h2>Warehouse Transfers</h2>
      
      <select value={status} onChange={(e) => setStatus(e.target.value)}>
        <option value="">All Statuses</option>
        <option value="pending">Pending</option>
        <option value="in_transit">In Transit</option>
        <option value="completed">Completed</option>
        <option value="cancelled">Cancelled</option>
      </select>
      
      {loading ? (
        <p>Loading...</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Reference</th>
              <th>From</th>
              <th>To</th>
              <th>Items</th>
              <th>Status</th>
              <th>Created</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {transfers.map((transfer) => (
              <tr key={transfer.id}>
                <td>{transfer.reference_number}</td>
                <td>{transfer.source_warehouse_name}</td>
                <td>{transfer.destination_warehouse_name}</td>
                <td>{transfer.items.length}</td>
                <td>
                  <StatusBadge status={transfer.status} />
                </td>
                <td>{new Date(transfer.created_at).toLocaleDateString()}</td>
                <td>
                  <TransferActions transfer={transfer} onUpdate={loadTransfers} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};
```

---

## Error Handling

### Common Error Responses

#### 400 Bad Request - Validation Error
```json
{
  "items": ["At least one item is required"],
  "source_warehouse": ["This field is required"]
}
```

#### 400 Bad Request - Business Logic Error
```json
{
  "non_field_errors": ["Source and destination warehouse cannot be the same"]
}
```

#### 404 Not Found
```json
{
  "detail": "Not found."
}
```

#### 401 Unauthorized
```json
{
  "detail": "Authentication credentials were not provided."
}
```

### Frontend Error Handling
```typescript
try {
  const transfer = await createWarehouseTransfer(data);
  // Success
} catch (error) {
  if (error.response) {
    const errors = await error.response.json();
    
    // Display validation errors
    if (errors.items) {
      showError(`Items: ${errors.items.join(', ')}`);
    }
    
    // Display field errors
    Object.entries(errors).forEach(([field, messages]) => {
      if (Array.isArray(messages)) {
        showFieldError(field, messages[0]);
      }
    });
  }
}
```

---

## Testing Checklist

### Backend Integration Tests

- [ ] Can list transfers with filters
- [ ] Can create warehouse transfer
- [ ] Can create storefront transfer
- [ ] Can get transfer details
- [ ] Can complete pending transfer
- [ ] Can cancel pending transfer
- [ ] Cannot complete cancelled transfer
- [ ] Cannot cancel completed transfer
- [ ] Cannot delete completed transfer
- [ ] Validation prevents duplicate products
- [ ] Validation prevents self-transfer
- [ ] Validation requires items
- [ ] Business isolation works (users only see own transfers)

### UI Tests

- [ ] Transfer list loads and displays correctly
- [ ] Filters work (status, date, search)
- [ ] Pagination works
- [ ] Create form validates input
- [ ] Create form calculates totals correctly
- [ ] Complete action updates status and inventory
- [ ] Cancel action updates status
- [ ] Status badges display correctly
- [ ] Error messages display properly

---

## Performance Considerations

### Backend Performance
- Transfers are paginated (20 per page default)
- Includes select_related for related objects (reduces queries)
- Includes prefetch_related for items (reduces N+1 queries)

### Frontend Optimization
- Implement virtual scrolling for large lists
- Cache transfer list data
- Debounce search input
- Use optimistic updates for complete/cancel actions

---

## Reports Integration

**No Frontend Changes Needed!**

The Stock Movement reports (`/reports/api/inventory/stock-movements/`) already include new transfer data thanks to Phase 3 MovementTracker integration.

Existing reports will automatically show:
- New Transfer records
- Legacy StockAdjustment transfers
- All aggregated seamlessly

---

## Monitoring & Debugging

### Backend Logging
The backend logs all transfer operations. Check logs for:
- Transfer creation
- Transfer completion
- Transfer cancellation
- Validation errors

### Debug Mode
Add `?debug=1` to API requests during development for detailed error messages (if enabled on backend).

---

## Support & Questions

### Backend Team Contact
- For API issues or questions
- For additional endpoint needs
- For performance concerns

### Documentation
- `PHASE_4_SUMMARY.md` - Implementation details
- `PHASE_4_API_REFERENCE.md` - Quick API reference
- This guide - Frontend integration

---

## Timeline

**Phase 5 (Week 5): Frontend Integration**
- Week 5, Days 1-2: API integration layer
- Week 5, Days 3-4: UI components
- Week 5, Day 5: Testing & bug fixes

**Phase 6 (Week 6): Testing & Monitoring**
- Integration testing
- Performance testing
- User acceptance testing

---

## Success Criteria

Phase 5 complete when:
- ✅ Frontend can create transfers
- ✅ Frontend can list/filter transfers
- ✅ Frontend can complete transfers
- ✅ Frontend can cancel transfers
- ✅ All validation errors handled gracefully
- ✅ UI is intuitive and user-friendly
- ✅ Integration tests pass
- ✅ Performance is acceptable

---

**Backend is ready! Let's build an amazing transfer management UI! 🚀**
