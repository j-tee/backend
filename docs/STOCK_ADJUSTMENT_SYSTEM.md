# Stock Adjustment System - Complete Guide

## Overview

The Stock Adjustment System provides comprehensive tracking of all inventory changes beyond sales. This addresses real-world scenarios including:

- **Theft/Shrinkage**: Track stolen or missing items
- **Damage/Breakage**: Record damaged or broken products
- **Expiration/Spoilage**: Handle expired or spoiled goods
- **Returns**: Process customer and supplier returns
- **Physical Counts**: Reconcile system vs actual inventory
- **Corrections**: Fix inventory count errors
- **Transfers**: Track stock movements between locations

## Key Features

### 1. **Complete Audit Trail**
Every stock change is tracked with:
- Who made the adjustment
- When it was made
- Why it was made
- Supporting documentation (photos, receipts, reports)
- Approval workflow

### 2. **Financial Impact Tracking**
- Unit cost at time of adjustment
- Total financial impact
- Shrinkage reporting
- Cost analysis by type

### 3. **Approval Workflow**
- Sensitive adjustments require approval
- Bulk approval capabilities
- Auto-approval for system-generated adjustments
- Rejection with reason tracking

### 4. **Physical Stock Counts**
- Create count sessions
- Record system vs actual quantities
- Auto-generate adjustments for discrepancies
- Variance reporting

## Database Models

### StockAdjustment

Main model tracking all stock adjustments.

**Key Fields:**
```python
- adjustment_type: Type of adjustment (THEFT, DAMAGE, RETURN, etc.)
- quantity: Amount to adjust (positive = increase, negative = decrease)
- unit_cost: Cost per unit at time of adjustment
- total_cost: Total financial impact (auto-calculated)
- reason: Detailed explanation
- reference_number: External reference (police report, RMA, etc.)
- status: PENDING → APPROVED → COMPLETED
- requires_approval: Whether manager approval is needed
- created_by: User who created adjustment
- approved_by: User who approved (if required)
```

**Adjustment Types:**

**Decreases (Negative Quantity):**
- `THEFT`: Stolen items
- `DAMAGE`: Damaged/broken items
- `EXPIRED`: Expired products
- `SPOILAGE`: Spoiled goods
- `LOSS`: Lost/missing items
- `SAMPLE`: Samples or promotional use
- `WRITE_OFF`: Write-off/disposal
- `SUPPLIER_RETURN`: Returned to supplier
- `TRANSFER_OUT`: Transferred to another location

**Increases (Positive Quantity):**
- `CUSTOMER_RETURN`: Customer returned item
- `FOUND`: Found previously missing item
- `CORRECTION_INCREASE`: Inventory count correction (found more)
- `TRANSFER_IN`: Received from another location

**Either:**
- `CORRECTION`: General inventory correction
- `RECOUNT`: Physical count adjustment
- `OTHER`: Other reasons

### StockAdjustmentPhoto

Supports adjustments with visual evidence.

**Use Cases:**
- Photos of damaged goods
- Evidence of theft/breakage
- Condition documentation

### StockAdjustmentDocument

Attach supporting documents.

**Document Types:**
- `RECEIPT`: Purchase receipt
- `INVOICE`: Invoice
- `POLICE_REPORT`: Police report for theft
- `INSURANCE_CLAIM`: Insurance documentation
- `SUPPLIER_RMA`: Supplier return authorization
- `COUNT_SHEET`: Physical count sheet
- `OTHER`: Other documents

### StockCount

Track physical inventory count sessions.

**Workflow:**
1. Create count session for location
2. Add count items with actual quantities
3. System calculates discrepancies
4. Generate adjustments for variances
5. Complete count

### StockCountItem

Individual products counted in a stock count session.

**Fields:**
- `system_quantity`: What the system thinks we have
- `counted_quantity`: What we actually counted
- `discrepancy`: Difference (auto-calculated)
- `counter_name`: Who counted it
- `adjustment_created`: Link to generated adjustment

## API Endpoints

### Stock Adjustments

#### List Adjustments
```http
GET /inventory/api/stock-adjustments/
```

**Query Parameters:**
- `adjustment_type`: Filter by type (THEFT, DAMAGE, etc.)
- `status`: Filter by status (PENDING, APPROVED, COMPLETED)
- `stock_product`: Filter by stock product ID
- `warehouse`: Filter by warehouse ID
- `start_date`: Filter from date (ISO format)
- `end_date`: Filter to date (ISO format)
- `search`: Search in reason, reference_number, product name
- `ordering`: Sort by field (created_at, total_cost, quantity)

**Response:**
```json
{
  "count": 45,
  "next": "...",
  "previous": null,
  "results": [
    {
      "id": "uuid",
      "business": "uuid",
      "stock_product": "uuid",
      "stock_product_details": {
        "id": "uuid",
        "product_name": "Product A",
        "product_code": "SKU-001",
        "current_quantity": 50,
        "warehouse": "Main Warehouse",
        "supplier": "Supplier Inc",
        "unit_cost": "15.00",
        "retail_price": "25.00"
      },
      "adjustment_type": "THEFT",
      "adjustment_type_display": "Theft/Shrinkage",
      "quantity": -5,
      "unit_cost": "15.00",
      "total_cost": "75.00",
      "reason": "Items missing from shelf after inventory check",
      "reference_number": "POLICE-2025-001",
      "status": "COMPLETED",
      "status_display": "Completed",
      "requires_approval": true,
      "created_by": "uuid",
      "created_by_name": "John Manager",
      "approved_by": "uuid",
      "approved_by_name": "Jane Owner",
      "created_at": "2025-01-15T10:30:00Z",
      "approved_at": "2025-01-15T14:20:00Z",
      "completed_at": "2025-01-15T14:21:00Z",
      "has_photos": true,
      "has_documents": true,
      "related_sale": null,
      "related_transfer": null,
      "financial_impact": "-75.00",
      "is_increase": false,
      "is_decrease": true,
      "photos": [...],
      "documents": [...]
    }
  ]
}
```

#### Create Adjustment
```http
POST /inventory/api/stock-adjustments/
```

**Request Body:**
```json
{
  "stock_product": "uuid",
  "adjustment_type": "DAMAGE",
  "quantity": -10,
  "reason": "Boxes fell from shelf and broke bottles",
  "reference_number": "INC-2025-042",
  "unit_cost": "12.50"
}
```

**Notes:**
- `business` is auto-set from user's membership
- `created_by` is auto-set to current user
- `quantity` sign is auto-corrected based on adjustment_type
- `unit_cost` defaults to stock_product's landed_unit_cost if not provided
- `requires_approval` is auto-determined based on type and value
- Sensitive types (THEFT, LOSS, WRITE_OFF) always require approval
- Adjustments over $1000 require approval
- Some types (CUSTOMER_RETURN, TRANSFER_IN) are auto-approved

**Response:**
```json
{
  "id": "uuid",
  "status": "PENDING",
  ...
}
```

#### Approve Adjustment
```http
POST /inventory/api/stock-adjustments/{id}/approve/
```

**Response:**
```json
{
  "id": "uuid",
  "status": "APPROVED",
  "approved_by": "uuid",
  "approved_at": "2025-01-15T14:20:00Z",
  ...
}
```

**Notes:**
- Only PENDING adjustments can be approved
- If adjustment doesn't require further approval, it's auto-completed
- Stock is updated when completed

#### Reject Adjustment
```http
POST /inventory/api/stock-adjustments/{id}/reject/
```

**Response:**
```json
{
  "id": "uuid",
  "status": "REJECTED",
  "approved_by": "uuid",
  ...
}
```

#### Complete Adjustment
```http
POST /inventory/api/stock-adjustments/{id}/complete/
```

**Response:**
```json
{
  "id": "uuid",
  "status": "COMPLETED",
  "completed_at": "2025-01-15T14:21:00Z",
  ...
}
```

**Notes:**
- Only APPROVED adjustments can be completed
- This applies the adjustment to stock
- Stock quantity is updated: `new_quantity = current_quantity + adjustment.quantity`
- Cannot complete if result would be negative stock

#### Get Pending Adjustments
```http
GET /inventory/api/stock-adjustments/pending/
```

Returns all adjustments with status=PENDING for user's business.

#### Get Adjustment Summary
```http
GET /inventory/api/stock-adjustments/summary/
```

**Response:**
```json
{
  "overall": {
    "total_adjustments": 150,
    "total_increase": 25,
    "total_decrease": -125,
    "total_cost_impact": "3250.00"
  },
  "by_type": [
    {
      "adjustment_type": "THEFT",
      "count": 12,
      "total_quantity": -45,
      "total_cost": "1200.00"
    },
    {
      "adjustment_type": "DAMAGE",
      "count": 8,
      "total_quantity": -22,
      "total_cost": "850.00"
    }
  ],
  "by_status": [
    {
      "status": "COMPLETED",
      "count": 120
    },
    {
      "status": "PENDING",
      "count": 30
    }
  ]
}
```

#### Get Shrinkage Report
```http
GET /inventory/api/stock-adjustments/shrinkage/
```

**Response:**
```json
{
  "overall": {
    "total_units": 95,
    "total_cost": "2850.00",
    "total_incidents": 25
  },
  "by_type": [
    {
      "adjustment_type": "THEFT",
      "count": 12,
      "total_quantity": -45,
      "total_cost": "1200.00"
    },
    {
      "adjustment_type": "DAMAGE",
      "count": 8,
      "total_quantity": -22,
      "total_cost": "850.00"
    },
    {
      "adjustment_type": "EXPIRED",
      "count": 5,
      "total_quantity": -28,
      "total_cost": "800.00"
    }
  ],
  "top_affected_products": [
    {
      "stock_product__product__name": "Product A",
      "stock_product__product__code": "SKU-001",
      "total_quantity": -25,
      "total_cost": "750.00",
      "incidents": 8
    }
  ]
}
```

**Notes:**
- Shrinkage includes: THEFT, LOSS, DAMAGE, EXPIRED, SPOILAGE, WRITE_OFF
- Only COMPLETED adjustments are included
- Top 10 most affected products by cost

#### Bulk Approve
```http
POST /inventory/api/stock-adjustments/bulk_approve/
```

**Request Body:**
```json
{
  "adjustment_ids": [
    "uuid1",
    "uuid2",
    "uuid3"
  ]
}
```

**Response:**
```json
{
  "approved": ["uuid1", "uuid2"],
  "failed": [
    {
      "id": "uuid3",
      "error": "Adjustment not in pending status"
    }
  ],
  "total_approved": 2,
  "total_failed": 1
}
```

### Stock Counts

#### List Stock Counts
```http
GET /inventory/api/stock-counts/
```

**Query Parameters:**
- `status`: IN_PROGRESS, COMPLETED, CANCELLED
- `storefront`: Filter by storefront ID
- `warehouse`: Filter by warehouse ID
- `ordering`: count_date, created_at

**Response:**
```json
{
  "count": 10,
  "results": [
    {
      "id": "uuid",
      "business": "uuid",
      "storefront": "uuid",
      "warehouse": null,
      "count_date": "2025-01-15",
      "status": "COMPLETED",
      "status_display": "Completed",
      "notes": "Monthly inventory count",
      "created_by": "uuid",
      "created_by_name": "John Manager",
      "created_at": "2025-01-15T08:00:00Z",
      "completed_at": "2025-01-15T16:30:00Z",
      "items": [...],
      "total_items": 150,
      "items_with_discrepancy": 12,
      "total_discrepancy_value": "-245.00"
    }
  ]
}
```

#### Create Stock Count
```http
POST /inventory/api/stock-counts/
```

**Request Body:**
```json
{
  "storefront": "uuid",
  "count_date": "2025-01-15",
  "notes": "Monthly inventory verification"
}
```

**Notes:**
- Specify either `storefront` or `warehouse`, not both
- `business` and `created_by` auto-set from user
- Status starts as IN_PROGRESS

#### Complete Stock Count
```http
POST /inventory/api/stock-counts/{id}/complete/
```

Marks count as completed. Count must be IN_PROGRESS.

#### Create Adjustments from Count
```http
POST /inventory/api/stock-counts/{id}/create_adjustments/
```

**Response:**
```json
{
  "adjustments_created": 8,
  "adjustment_ids": ["uuid1", "uuid2", ...]
}
```

**Notes:**
- Only works on COMPLETED counts
- Creates adjustments for all items with discrepancies
- Skips items that already have adjustments created
- Adjustments are created as PENDING and require approval

#### Get Discrepancies
```http
GET /inventory/api/stock-counts/{id}/discrepancies/
```

Returns only count items with non-zero discrepancies.

### Stock Count Items

#### List Count Items
```http
GET /inventory/api/stock-count-items/
```

**Query Parameters:**
- `stock_count`: Filter by stock count ID

**Response:**
```json
{
  "count": 150,
  "results": [
    {
      "id": "uuid",
      "stock_product": "uuid",
      "stock_product_details": {
        "id": "uuid",
        "product_name": "Product A",
        "product_code": "SKU-001",
        "warehouse": "Main Warehouse",
        "current_quantity": 48
      },
      "system_quantity": 50,
      "counted_quantity": 48,
      "discrepancy": -2,
      "has_discrepancy": true,
      "discrepancy_percentage": "4.00",
      "counter_name": "John Doe",
      "notes": "Two units missing from top shelf",
      "counted_at": "2025-01-15T14:30:00Z",
      "adjustment_created_id": "uuid"
    }
  ]
}
```

#### Create Count Item
```http
POST /inventory/api/stock-count-items/
```

**Request Body:**
```json
{
  "stock_count": "uuid",
  "stock_product": "uuid",
  "counted_quantity": 48,
  "counter_name": "John Doe",
  "notes": "Two units missing from top shelf"
}
```

**Notes:**
- `system_quantity` is auto-set from stock_product.quantity
- `discrepancy` is auto-calculated: counted_quantity - system_quantity

#### Create Adjustment from Item
```http
POST /inventory/api/stock-count-items/{id}/create_adjustment/
```

Creates an adjustment for this specific count item's discrepancy.

**Response:**
```json
{
  "id": "uuid",
  "adjustment_type": "CORRECTION",
  "quantity": -2,
  "reason": "Physical count found 2 fewer units than system",
  "reference_number": "COUNT-{stock_count_id}",
  "status": "PENDING",
  ...
}
```

## Integration with Stock Management

### StockProduct Methods

New methods added to `StockProduct` model:

#### get_adjustment_summary()
```python
stock_product.get_adjustment_summary()
```

Returns:
```python
{
    'summary': {
        'total_adjustments': 15,
        'total_increase': 5,
        'total_decrease': -30,
        'total_cost_impact': Decimal('450.00')
    },
    'by_type': [
        {
            'adjustment_type': 'THEFT',
            'count': 3,
            'total_quantity': -12,
            'total_cost': Decimal('180.00')
        },
        ...
    ]
}
```

#### get_shrinkage_total()
```python
stock_product.get_shrinkage_total()
```

Returns:
```python
{
    'units': 25,  # Absolute value
    'cost': Decimal('375.00')
}
```

#### get_pending_adjustments()
```python
stock_product.get_pending_adjustments()
```

Returns queryset of adjustments with status PENDING or APPROVED.

## Usage Examples

### Example 1: Record Theft

```python
# Create adjustment for stolen items
adjustment = StockAdjustment.objects.create(
    business=user_business,
    stock_product=stock_product,
    adjustment_type='THEFT',
    quantity=-5,  # 5 units stolen
    unit_cost=stock_product.landed_unit_cost,
    reason='Items missing after break-in. Police report filed.',
    reference_number='POLICE-2025-001',
    created_by=user,
    requires_approval=True,
    status='PENDING'
)

# Manager approves
adjustment.approve(manager_user)

# System completes and updates stock
adjustment.complete()  # stock_product.quantity reduced by 5
```

### Example 2: Handle Damaged Goods

```python
# Create adjustment
adjustment = StockAdjustment.objects.create(
    stock_product=stock_product,
    adjustment_type='DAMAGE',
    quantity=-10,
    reason='Forklift accident damaged boxes',
    reference_number='INC-2025-042',
    created_by=warehouse_staff
)

# Upload photo evidence
photo = StockAdjustmentPhoto.objects.create(
    adjustment=adjustment,
    photo=photo_file,
    description='Damaged boxes after accident',
    uploaded_by=warehouse_staff
)

# Approve and complete
adjustment.approve(manager)
adjustment.complete()
```

### Example 3: Physical Count with Discrepancies

```python
# Start count
count = StockCount.objects.create(
    business=business,
    storefront=storefront,
    count_date=date.today(),
    notes='Monthly inventory verification',
    created_by=manager
)

# Add counted items
for stock_product in storefront_stock:
    actual_count = count_physical_inventory(stock_product)
    
    StockCountItem.objects.create(
        stock_count=count,
        stock_product=stock_product,
        counted_quantity=actual_count,
        counter_name='John Doe'
    )

# Complete count
count.complete()

# Create adjustments for discrepancies
items_with_variance = count.items.exclude(discrepancy=0)
for item in items_with_variance:
    adjustment = item.create_adjustment(manager)
    # Adjustments created as PENDING, need approval

# Manager approves all adjustments
for item in items_with_variance:
    if item.adjustment_created:
        item.adjustment_created.approve(manager)
        item.adjustment_created.complete()
```

### Example 4: Customer Return

```python
# Customer returns item from sale
adjustment = StockAdjustment.objects.create(
    stock_product=original_stock_product,
    adjustment_type='CUSTOMER_RETURN',
    quantity=2,  # Returning 2 units
    reason='Customer returned unused items',
    reference_number=f'SALE-{sale.id}',
    related_sale=sale,
    created_by=cashier,
    requires_approval=False,  # Auto-approved
    status='APPROVED'
)

# Auto-complete since no approval needed
adjustment.complete()  # Stock increased by 2
```

## Frontend Integration

### Display Adjustment Types

```javascript
const ADJUSTMENT_TYPE_ICONS = {
  THEFT: '🚨',
  DAMAGE: '💔',
  EXPIRED: '📅',
  SPOILAGE: '🦠',
  LOSS: '❓',
  CUSTOMER_RETURN: '↩️',
  FOUND: '🔍',
  CORRECTION: '✏️',
  RECOUNT: '🔢'
};

const ADJUSTMENT_TYPE_COLORS = {
  THEFT: 'red',
  DAMAGE: 'orange',
  EXPIRED: 'yellow',
  SPOILAGE: 'brown',
  LOSS: 'gray',
  CUSTOMER_RETURN: 'green',
  FOUND: 'green',
  CORRECTION: 'blue',
  RECOUNT: 'blue'
};
```

### Show Adjustment Status

```javascript
const STATUS_BADGES = {
  PENDING: { label: 'Pending Approval', color: 'warning' },
  APPROVED: { label: 'Approved', color: 'info' },
  REJECTED: { label: 'Rejected', color: 'error' },
  COMPLETED: { label: 'Completed', color: 'success' }
};
```

### Create Adjustment Form

```javascript
async function createAdjustment(data) {
  const response = await fetch('/inventory/api/stock-adjustments/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Token ${authToken}`
    },
    body: JSON.stringify({
      stock_product: data.stockProductId,
      adjustment_type: data.type,  // DAMAGE, THEFT, etc.
      quantity: Math.abs(data.quantity),  // API auto-corrects sign
      reason: data.reason,
      reference_number: data.referenceNumber,
      unit_cost: data.unitCost  // Optional, defaults to stock cost
    })
  });
  
  return await response.json();
}
```

### Approve Adjustments

```javascript
async function approveAdjustment(adjustmentId) {
  const response = await fetch(
    `/inventory/api/stock-adjustments/${adjustmentId}/approve/`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Token ${authToken}`
      }
    }
  );
  
  return await response.json();
}
```

### Get Shrinkage Report

```javascript
async function getShrinkageReport() {
  const response = await fetch(
    '/inventory/api/stock-adjustments/shrinkage/',
    {
      headers: { 'Authorization': `Token ${authToken}` }
    }
  );
  
  const data = await response.json();
  
  // Display shrinkage dashboard
  displayShrinkage(data);
}
```

## Permissions & Security

### Business Scoping

All adjustments are scoped to user's active business:
- User must have active BusinessMembership
- Adjustments filtered by business
- Cannot access other businesses' adjustments

### Approval Requirements

**Always Require Approval:**
- THEFT adjustments (security concern)
- LOSS adjustments (security concern)
- WRITE_OFF adjustments (financial impact)
- Adjustments over $1000 (financial threshold)

**Auto-Approved:**
- CUSTOMER_RETURN (low risk)
- TRANSFER_IN (system-generated)
- TRANSFER_OUT (system-generated)

### Audit Trail

Every adjustment tracks:
- Created by (who initiated)
- Approved by (who authorized)
- Created at (when initiated)
- Approved at (when authorized)
- Completed at (when applied to stock)

## Reporting Capabilities

### 1. Shrinkage Analysis
- Total shrinkage by type
- Top products affected
- Trend analysis over time
- Cost impact

### 2. Adjustment History
- All adjustments by product
- Adjustments by warehouse
- Adjustments by date range
- Approval status breakdown

### 3. Physical Count Variance
- Items with discrepancies
- Variance percentage
- Value of discrepancies
- Trend in count accuracy

### 4. Financial Impact
- Total cost of adjustments
- Cost by adjustment type
- Monthly/quarterly trends
- Comparison periods

## Best Practices

### 1. Documentation
- Always provide detailed reason
- Include reference numbers when available
- Attach photos for damage/theft
- Upload supporting documents

### 2. Regular Counts
- Schedule monthly physical counts
- Focus on high-value items
- Track count accuracy over time
- Address discrepancies promptly

### 3. Approval Workflow
- Review pending adjustments daily
- Investigate high-value adjustments
- Verify documentation before approval
- Track repeat issues by product/location

### 4. Shrinkage Prevention
- Monitor shrinkage trends
- Identify problematic products
- Investigate unusual patterns
- Implement preventive measures

## Migration & Deployment

### Files Created
1. `inventory/stock_adjustments.py` - Models
2. `inventory/adjustment_serializers.py` - API serializers
3. `inventory/adjustment_views.py` - ViewSets
4. `inventory/urls.py` - URL patterns (updated)
5. `inventory/admin.py` - Admin interface (updated)
6. `inventory/models.py` - StockProduct methods (updated)
7. `inventory/migrations/0013_...py` - Database migration

### Database Changes
- New table: `stock_adjustments`
- New table: `stock_adjustment_photos`
- New table: `stock_adjustment_documents`
- New table: `stock_counts`
- New table: `stock_count_items`

### Migration Applied
```bash
python manage.py migrate
```

Status: ✅ **COMPLETE - NO ERRORS**

## Summary

The Stock Adjustment System provides:

✅ **Complete audit trail** for all inventory changes  
✅ **Financial impact tracking** for accountability  
✅ **Approval workflows** for sensitive adjustments  
✅ **Physical count reconciliation** with auto-adjustment generation  
✅ **Shrinkage analysis** for loss prevention  
✅ **Supporting documentation** (photos, documents)  
✅ **Multi-tenant security** with business scoping  
✅ **Comprehensive API** with filtering and reporting  
✅ **Admin interface** for management  

This system ensures your inventory levels reflect real-world situations, accounting for theft, damage, returns, expiration, and all other factors that affect stock beyond sales.
