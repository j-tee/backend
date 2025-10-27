# Stock Adjustment System - Quick Reference

## Common Scenarios

### 1. Record Stolen Items

```http
POST /inventory/api/stock-adjustments/
```

```json
{
  "stock_product": "uuid",
  "adjustment_type": "THEFT",
  "quantity": 5,
  "reason": "Items missing after security check",
  "reference_number": "POLICE-2025-001"
}
```

**Note:** Quantity is auto-corrected to negative. Status will be PENDING (requires approval).

---

### 2. Record Damaged Goods

```http
POST /inventory/api/stock-adjustments/
```

```json
{
  "stock_product": "uuid",
  "adjustment_type": "DAMAGE",
  "quantity": 10,
  "reason": "Dropped during handling, bottles broken"
}
```

**Upload Photo:**
```http
POST /inventory/api/adjustment-photos/
Content-Type: multipart/form-data

adjustment: {adjustment_id}
photo: [file]
description: "Broken bottles photo"
```

---

### 3. Customer Return

```http
POST /inventory/api/stock-adjustments/
```

```json
{
  "stock_product": "uuid",
  "adjustment_type": "CUSTOMER_RETURN",
  "quantity": 2,
  "reason": "Customer returned unused items within 30 days",
  "related_sale": "sale_uuid"
}
```

**Note:** Auto-approved, immediately adds stock back.

---

### 4. Physical Inventory Count

**Step 1: Create Count Session**
```http
POST /inventory/api/stock-counts/
```

```json
{
  "storefront": "uuid",
  "count_date": "2025-01-15",
  "notes": "Monthly inventory verification"
}
```

**Step 2: Add Count Items**
```http
POST /inventory/api/stock-count-items/
```

```json
{
  "stock_count": "count_uuid",
  "stock_product": "uuid",
  "counted_quantity": 48,
  "counter_name": "John Doe"
}
```

System auto-sets `system_quantity` and calculates `discrepancy`.

**Step 3: Complete Count**
```http
POST /inventory/api/stock-counts/{count_id}/complete/
```

**Step 4: Create Adjustments for Discrepancies**
```http
POST /inventory/api/stock-counts/{count_id}/create_adjustments/
```

Returns adjustment IDs for all variances.

**Step 5: Approve Adjustments**
```http
POST /inventory/api/stock-adjustments/bulk_approve/
```

```json
{
  "adjustment_ids": ["uuid1", "uuid2", "uuid3"]
}
```

---

### 5. Expired Products

```http
POST /inventory/api/stock-adjustments/
```

```json
{
  "stock_product": "uuid",
  "adjustment_type": "EXPIRED",
  "quantity": 15,
  "reason": "Products passed expiration date: 2025-01-10"
}
```

---

### 6. Record Missing Items (Unknown Cause)

```http
POST /inventory/api/stock-adjustments/
```

```json
{
  "stock_product": "uuid",
  "adjustment_type": "LOSS",
  "quantity": 3,
  "reason": "Items missing during routine check, cause unknown"
}
```

**Note:** Requires approval due to sensitivity.

---

## Approval Workflow

### View Pending Adjustments

```http
GET /inventory/api/stock-adjustments/pending/
```

Returns all adjustments awaiting approval.

---

### Approve Single Adjustment

```http
POST /inventory/api/stock-adjustments/{id}/approve/
```

**Response:** Status changes to APPROVED, then auto-completes if no further approval needed.

---

### Reject Adjustment

```http
POST /inventory/api/stock-adjustments/{id}/reject/
```

**Response:** Status changes to REJECTED, stock NOT affected.

---

### Bulk Approve

```http
POST /inventory/api/stock-adjustments/bulk_approve/
```

```json
{
  "adjustment_ids": ["uuid1", "uuid2", "uuid3"]
}
```

**Response:**
```json
{
  "approved": ["uuid1", "uuid2"],
  "failed": [{"id": "uuid3", "error": "..."}],
  "total_approved": 2,
  "total_failed": 1
}
```

---

## Reporting Endpoints

### Get Adjustment Summary

```http
GET /inventory/api/stock-adjustments/summary/
```

**Optional Filters:**
- `?start_date=2025-01-01`
- `&end_date=2025-01-31`
- `&warehouse=uuid`

**Returns:**
- Total adjustments count
- Total increases/decreases
- Financial impact
- Breakdown by type
- Breakdown by status

---

### Get Shrinkage Report

```http
GET /inventory/api/stock-adjustments/shrinkage/
```

**Returns:**
- Total shrinkage units
- Total shrinkage cost
- Total incidents
- Breakdown by type (THEFT, DAMAGE, LOSS, etc.)
- Top 10 affected products

**Use for:**
- Loss prevention analysis
- Identifying problem areas
- Financial reporting
- Inventory audits

---

### List Adjustments with Filters

```http
GET /inventory/api/stock-adjustments/?adjustment_type=THEFT&status=COMPLETED
```

**Available Filters:**
- `adjustment_type`: THEFT, DAMAGE, EXPIRED, etc.
- `status`: PENDING, APPROVED, COMPLETED, REJECTED
- `stock_product`: UUID
- `warehouse`: UUID
- `start_date`: ISO date (2025-01-01)
- `end_date`: ISO date (2025-01-31)
- `search`: Search in reason, reference, product name
- `ordering`: created_at, -created_at, total_cost, -total_cost

---

## Adjustment Types Reference

### Negative (Decrease Stock)

| Type | Code | Auto-Approved? | Use Case |
|------|------|----------------|----------|
| Theft | `THEFT` | No | Stolen items |
| Damage | `DAMAGE` | No | Broken/damaged goods |
| Expired | `EXPIRED` | No | Past expiration |
| Spoilage | `SPOILAGE` | No | Spoiled items |
| Loss | `LOSS` | No | Missing items |
| Sample | `SAMPLE` | Yes* | Promotional use |
| Write-off | `WRITE_OFF` | No | Disposed items |
| Return to Supplier | `SUPPLIER_RETURN` | Yes* | RMA to supplier |
| Transfer Out | `TRANSFER_OUT` | Yes | Sent to other location |

### Positive (Increase Stock)

| Type | Code | Auto-Approved? | Use Case |
|------|------|----------------|----------|
| Customer Return | `CUSTOMER_RETURN` | Yes | Customer returned |
| Found | `FOUND` | Yes* | Previously missing |
| Correction (Increase) | `CORRECTION_INCREASE` | No | Count found more |
| Transfer In | `TRANSFER_IN` | Yes | Received from other location |

### Either Direction

| Type | Code | Auto-Approved? | Use Case |
|------|------|----------------|----------|
| Correction | `CORRECTION` | No | General count fix |
| Recount | `RECOUNT` | No | Physical count adjustment |

*Unless value exceeds approval threshold ($1000)

---

## Status Flow

```
CREATE
  ↓
PENDING ─────→ REJECTED (end)
  ↓
APPROVED
  ↓
COMPLETED (stock updated)
```

**Key Points:**
- Some adjustments skip PENDING → go straight to APPROVED
- Only APPROVED adjustments can be COMPLETED
- COMPLETED is final - stock has been updated
- REJECTED adjustments don't affect stock

---

## Quick Tips

### 1. Upload Evidence
For theft/damage, always upload photos or documents:

```http
POST /inventory/api/adjustment-photos/
POST /inventory/api/adjustment-documents/
```

### 2. Reference Numbers
Include external references:
- Police report numbers for theft
- Supplier RMA numbers for returns
- Incident report numbers for damage
- Insurance claim numbers

### 3. Detailed Reasons
Provide clear, specific reasons:
- ✅ "15 units damaged when forklift knocked shelf, bottles broken"
- ❌ "some broken"

### 4. Regular Physical Counts
- Schedule monthly counts
- Focus on high-value or high-shrinkage items
- Create adjustments immediately for discrepancies
- Track patterns over time

### 5. Review Pending Daily
Check pending adjustments regularly:

```http
GET /inventory/api/stock-adjustments/pending/
```

Approve or reject promptly to keep inventory accurate.

---

## Common Workflows

### Weekly Shrinkage Review

1. Get shrinkage report:
   ```http
   GET /inventory/api/stock-adjustments/shrinkage/?start_date=2025-01-08&end_date=2025-01-14
   ```

2. Identify top affected products

3. Investigate patterns

4. Implement preventive measures

### End of Month Reconciliation

1. Create physical count session

2. Count all products

3. Generate adjustments for discrepancies

4. Review and approve adjustments

5. Run adjustment summary:
   ```http
   GET /inventory/api/stock-adjustments/summary/?start_date=2025-01-01&end_date=2025-01-31
   ```

6. Document findings

### Damage Incident Response

1. Create DAMAGE adjustment with photo

2. Include incident report reference

3. Get manager approval

4. File insurance claim if needed

5. Upload claim documents

6. Complete adjustment to update stock

---

## API Response Fields

### Adjustment Object

```json
{
  "id": "uuid",
  "business": "uuid",
  "stock_product": "uuid",
  "stock_product_details": {
    "product_name": "Product Name",
    "product_code": "SKU",
    "current_quantity": 50,
    "warehouse": "Warehouse Name"
  },
  "adjustment_type": "THEFT",
  "adjustment_type_display": "Theft/Shrinkage",
  "quantity": -5,
  "unit_cost": "15.00",
  "total_cost": "75.00",
  "reason": "Detailed reason",
  "reference_number": "REF-001",
  "status": "COMPLETED",
  "status_display": "Completed",
  "requires_approval": true,
  "created_by": "uuid",
  "created_by_name": "User Name",
  "approved_by": "uuid",
  "approved_by_name": "Approver Name",
  "created_at": "2025-01-15T10:00:00Z",
  "approved_at": "2025-01-15T14:00:00Z",
  "completed_at": "2025-01-15T14:01:00Z",
  "has_photos": true,
  "has_documents": true,
  "financial_impact": "-75.00",
  "is_increase": false,
  "is_decrease": true,
  "photos": [...],
  "documents": [...]
}
```

**Key Fields:**
- `quantity`: Signed integer (negative = decrease, positive = increase)
- `total_cost`: Always positive (absolute value of cost)
- `financial_impact`: Signed (negative = loss, positive = gain)
- `*_display`: Human-readable versions of choice fields

---

## Error Handling

### Common Errors

**Cannot reduce stock below zero:**
```json
{
  "error": "This adjustment would result in negative stock. Current: 10, Adjustment: -15, Result: -5"
}
```

**Already approved/completed:**
```json
{
  "error": "Cannot approve adjustment with status: COMPLETED"
}
```

**Invalid adjustment type:**
```json
{
  "adjustment_type": ["Invalid choice."]
}
```

**No business membership:**
```json
{
  "error": "User has no active business membership"
}
```

---

## Integration with Stock Product

Access adjustment data on StockProduct:

```python
# Get adjustment summary
summary = stock_product.get_adjustment_summary()
# Returns: {summary: {...}, by_type: [...]}

# Get total shrinkage
shrinkage = stock_product.get_shrinkage_total()
# Returns: {units: 25, cost: Decimal('375.00')}

# Get pending adjustments
pending = stock_product.get_pending_adjustments()
# Returns: QuerySet of pending/approved adjustments
```

---

## Summary

**System Status:** ✅ LIVE

**Key Endpoints:**
- `/inventory/api/stock-adjustments/` - Main CRUD
- `/inventory/api/stock-adjustments/pending/` - Review queue
- `/inventory/api/stock-adjustments/shrinkage/` - Loss analysis
- `/inventory/api/stock-counts/` - Physical counts

**Auto-Features:**
- Business scoping from user membership
- Quantity sign auto-correction
- Unit cost defaults from stock
- Approval requirement determination
- Auto-completion for simple adjustments

**Best Practices:**
- Document everything
- Upload evidence
- Regular physical counts
- Review pending daily
- Monitor shrinkage trends
