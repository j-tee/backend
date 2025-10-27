# Phase 4 Quick API Reference

**New Transfer Endpoints** - Ready to Use! ✅

---

## Warehouse Transfers

### List/Create
```
GET/POST /inventory/api/warehouse-transfers/
```

### Detail Operations
```
GET/PUT/PATCH /inventory/api/warehouse-transfers/{id}/
DELETE        /inventory/api/warehouse-transfers/{id}/  (pending only)
```

### Actions
```
POST /inventory/api/warehouse-transfers/{id}/complete/
POST /inventory/api/warehouse-transfers/{id}/cancel/
```

---

## Storefront Transfers

### List/Create
```
GET/POST /inventory/api/storefront-transfers/
```

### Detail Operations
```
GET/PUT/PATCH /inventory/api/storefront-transfers/{id}/
DELETE        /inventory/api/storefront-transfers/{id}/  (pending only)
```

### Actions
```
POST /inventory/api/storefront-transfers/{id}/complete/
POST /inventory/api/storefront-transfers/{id}/cancel/
```

---

## Query Parameters

- `status` - pending, in_transit, completed, cancelled
- `source_warehouse` - UUID
- `destination_warehouse` - UUID (warehouse transfers)
- `destination_storefront` - UUID (storefront transfers)
- `start_date` - YYYY-MM-DD
- `end_date` - YYYY-MM-DD
- `search` - Search reference_number or notes

---

## Request/Response Format

### Create Transfer Request
```json
{
  "source_warehouse": "uuid",
  "destination_warehouse": "uuid",
  "notes": "Optional notes",
  "items": [
    {
      "product": "product-uuid",
      "quantity": 100,
      "unit_cost": "10.50"
    }
  ]
}
```

### Transfer Response
```json
{
  "id": "transfer-uuid",
  "reference_number": "TRF-20241027153045",
  "status": "pending",
  "source_warehouse": "uuid",
  "source_warehouse_name": "Main Warehouse",
  "destination_warehouse": "uuid",
  "destination_warehouse_name": "Branch",
  "items": [...],
  "created_by_name": "John Doe",
  "created_at": "2024-10-27T15:30:45Z"
}
```

### Complete Transfer Request
```json
{
  "notes": "Optional completion notes"
}
```

### Cancel Transfer Request
```json
{
  "reason": "Required cancellation reason"
}
```

---

## Status Workflow

```
pending → in_transit → completed
   ↓
cancelled
```

**Rules:**
- Can only complete: pending, in_transit
- Can only cancel: pending, in_transit
- Can only update/delete: pending
- Cannot delete: completed

---

## Files

- `inventory/transfer_serializers.py` - Serializers
- `inventory/transfer_views.py` - ViewSets
- `inventory/urls.py` - URL registration

---

**Phase 4 Complete! All endpoints working! 🚀**
