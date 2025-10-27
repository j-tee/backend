# Transfer API Enhancement: Stock Batch Fields

**Date:** October 27, 2025  
**Issue:** Missing stock batch fields in Transfer API  
**Status:** ✅ RESOLVED

---

## Problem Statement

When transferring goods between warehouses, the system needs to create `StockProduct` entries at the destination warehouse. However, the original Transfer API only captured basic fields (product, quantity, unit_cost), missing critical fields required for proper stock batch management:

### Missing Fields
1. **supplier** - Original supplier information
2. **expiry_date** - Expiration date for perishable items  
3. **unit_tax_rate** - Tax rate percentage
4. **unit_tax_amount** - Calculated tax amount per unit
5. **unit_additional_cost** - Shipping, handling, customs fees
6. **retail_price** - Retail selling price
7. **wholesale_price** - Wholesale selling price
8. **expected_arrival_date** - When goods expected at destination

### Impact
- Destination warehouses received stock without pricing information
- Tax calculations unavailable
- Supplier tracking lost
- Inventory valuation incomplete
- Frontend reported "This field is required" error

---

## Solution Implemented

### 1. Enhanced TransferItem Model

**File:** `inventory/transfer_models.py`

**Added Fields:**
```python
class TransferItem(models.Model):
    # ... existing fields ...
    
    # Stock batch fields (needed for destination StockProduct creation)
    supplier = models.ForeignKey(
        'inventory.Supplier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Original supplier (copied from source stock)"
    )
    expiry_date = models.DateField(
        null=True,
        blank=True,
        help_text="Expiration date for perishable items"
    )
    unit_tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
        null=True,
        blank=True,
        help_text="Tax rate percentage (0-100)"
    )
    unit_tax_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        null=True,
        blank=True,
        help_text="Tax amount per unit"
    )
    unit_additional_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        null=True,
        blank=True,
        help_text="Additional costs per unit"
    )
    retail_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Retail selling price"
    )
    wholesale_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Wholesale selling price"
    )
```

### 2. Enhanced Transfer Model

**Added Field:**
```python
class Transfer(models.Model):
    # ... existing fields ...
    
    expected_arrival_date = models.DateField(
        null=True,
        blank=True,
        help_text="Expected arrival date at destination"
    )
```

### 3. Updated complete_transfer() Method

**Enhanced StockProduct Creation:**
```python
destination_stock, created = StockProduct.objects.select_for_update().get_or_create(
    warehouse=self.destination_warehouse,
    product=item.product,
    stock=source_stock.stock,
    defaults={
        'quantity': 0,
        'calculated_quantity': 0,
        'unit_cost': item.unit_cost,
        # NEW: Include all stock batch fields
        'supplier': item.supplier or source_stock.supplier,
        'expiry_date': item.expiry_date or source_stock.expiry_date,
        'unit_tax_rate': item.unit_tax_rate or source_stock.unit_tax_rate,
        'unit_tax_amount': item.unit_tax_amount or source_stock.unit_tax_amount,
        'unit_additional_cost': item.unit_additional_cost or source_stock.unit_additional_cost,
        'retail_price': item.retail_price or source_stock.retail_price,
        'wholesale_price': item.wholesale_price or source_stock.wholesale_price,
    }
)
```

**Fallback Logic:**
- If transfer item has explicit values → use them
- Otherwise → copy from source stock (e.g., `item.supplier or source_stock.supplier`)
- This ensures data integrity while allowing manual overrides

### 4. Updated API Serializers

**File:** `inventory/transfer_serializers.py`

**TransferItemSerializer - New Fields:**
```python
fields = [
    'id',
    'product',
    'product_name',
    'product_sku',
    'quantity',
    'unit_cost',
    'total_cost',
    # Stock batch fields
    'supplier',
    'supplier_name',
    'expiry_date',
    'unit_tax_rate',
    'unit_tax_amount',
    'unit_additional_cost',
    'retail_price',
    'wholesale_price',
]
```

**TransferSerializer - New Field:**
```python
fields = [
    # ... existing fields ...
    'expected_arrival_date',
]
```

### 5. Database Migration

**File:** `inventory/migrations/0023_add_stock_batch_fields_to_transfer.py`

**Changes:**
- Added 8 fields to `TransferItem` table
- Added 1 field to `Transfer` table
- All fields nullable/optional for backward compatibility

**Applied Successfully:** ✅

---

## Updated API Reference

### Create Warehouse Transfer

**Endpoint:** `POST /inventory/api/warehouse-transfers/`

**New Request Format:**
```json
{
  "source_warehouse": "uuid",
  "destination_warehouse": "uuid",
  "expected_arrival_date": "2025-11-01",
  "notes": "Monthly restock",
  "items": [
    {
      "product": "uuid",
      "quantity": 100,
      "unit_cost": "10.50",
      "supplier": "supplier-uuid",
      "expiry_date": "2026-06-30",
      "unit_tax_rate": "15.00",
      "unit_tax_amount": "1.58",
      "unit_additional_cost": "0.50",
      "retail_price": "15.00",
      "wholesale_price": "12.00"
    }
  ]
}
```

### Field Descriptions

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `supplier` | No | UUID | Original supplier reference |
| `expiry_date` | No | Date | Expiration date (YYYY-MM-DD) |
| `unit_tax_rate` | No | Decimal | Tax rate % (0-100) |
| `unit_tax_amount` | No | Decimal | Tax amount per unit |
| `unit_additional_cost` | No | Decimal | Shipping/handling costs |
| `retail_price` | No | Decimal | Retail selling price |
| `wholesale_price` | No | Decimal | Wholesale selling price |
| `expected_arrival_date` | No | Date | Expected delivery date |

### Default Behavior

**If fields not provided:**
- System auto-copies from source `StockProduct`
- Example: If `retail_price` not specified → uses source stock's retail price
- Ensures consistency while allowing manual overrides

---

## Frontend Integration Guide

### 1. Update Transfer Creation Form

**Add Optional Fields Section:**
```tsx
interface TransferItem {
  product: string;
  quantity: number;
  unit_cost: string;
  // Stock batch fields (optional)
  supplier?: string;
  expiry_date?: string;
  unit_tax_rate?: string;
  unit_tax_amount?: string;
  unit_additional_cost?: string;
  retail_price?: string;
  wholesale_price?: string;
}

interface Transfer {
  source_warehouse: string;
  destination_warehouse: string;
  expected_arrival_date?: string;
  notes?: string;
  items: TransferItem[];
}
```

### 2. Form UI Recommendations

**Basic Fields (Always Visible):**
- Product selector
- Quantity
- Unit cost

**Advanced Fields (Collapsible/Optional):**
- Supplier dropdown
- Expiry date picker (for perishables)
- Tax information (rate + amount)
- Additional costs
- Pricing (retail/wholesale)

**Example UI:**
```
┌─────────────────────────────────────┐
│ Product: [Canned Tomatoes ▼]        │
│ Quantity: [100]  Unit Cost: [10.50] │
│                                      │
│ ⊕ Advanced Stock Details             │
│   (Click to expand)                  │
└─────────────────────────────────────┘

When expanded:
┌─────────────────────────────────────┐
│ ⊖ Advanced Stock Details             │
│                                      │
│ Supplier: [Supplier A ▼]             │
│ Expiry Date: [2026-06-30]            │
│ Tax Rate: [15.00]%                   │
│ Tax Amount: [Auto-calculated]        │
│ Additional Cost: [0.50]              │
│ Retail Price: [15.00]                │
│ Wholesale Price: [12.00]             │
└─────────────────────────────────────┘
```

### 3. Auto-Fill Feature

**Fetch from Source Stock:**
```typescript
async function fetchSourceStockDetails(
  sourceWarehouse: string,
  product: string
): Promise<StockDetails> {
  const response = await fetch(
    `/inventory/api/stock-products/?warehouse=${sourceWarehouse}&product=${product}`
  );
  const data = await response.json();
  
  return {
    supplier: data.supplier,
    retail_price: data.retail_price,
    wholesale_price: data.wholesale_price,
    unit_tax_rate: data.unit_tax_rate,
    // ... other fields
  };
}

// Use in form:
const handleProductSelect = async (productId: string) => {
  const stockDetails = await fetchSourceStockDetails(
    form.source_warehouse,
    productId
  );
  
  // Pre-fill advanced fields
  setFormValues({
    ...formValues,
    supplier: stockDetails.supplier,
    retail_price: stockDetails.retail_price,
    wholesale_price: stockDetails.wholesale_price,
  });
};
```

### 4. Validation

```typescript
const validateTransferItem = (item: TransferItem) => {
  const errors: string[] = [];
  
  // Required fields
  if (!item.product) errors.push("Product is required");
  if (!item.quantity || item.quantity <= 0) errors.push("Quantity must be positive");
  if (!item.unit_cost || item.unit_cost < 0) errors.push("Unit cost cannot be negative");
  
  // Optional field validation
  if (item.retail_price && item.retail_price < 0) {
    errors.push("Retail price cannot be negative");
  }
  if (item.wholesale_price && item.wholesale_price < 0) {
    errors.push("Wholesale price cannot be negative");
  }
  if (item.unit_tax_rate && (item.unit_tax_rate < 0 || item.unit_tax_rate > 100)) {
    errors.push("Tax rate must be between 0 and 100");
  }
  
  return errors;
};
```

---

## Migration Notes

### Backward Compatibility

✅ **Fully backward compatible**
- All new fields are optional (nullable/blank=True)
- Existing transfers continue to work
- Legacy API calls work unchanged
- Fallback to source stock values if not provided

### Data Migration

**No data migration needed**
- Existing transfers: No changes required
- New transfers: Can use new fields immediately
- System auto-copies from source if fields omitted

---

## Testing Checklist

### Backend Tests
- [ ] Create transfer with all stock batch fields
- [ ] Create transfer without optional fields (uses source defaults)
- [ ] Complete transfer - verify StockProduct has all fields
- [ ] Verify supplier is copied correctly
- [ ] Verify pricing is maintained
- [ ] Verify tax calculations
- [ ] Test expiry date handling

### Frontend Tests
- [ ] Advanced fields section collapses/expands
- [ ] Auto-fill from source stock works
- [ ] Form validation prevents negative prices
- [ ] Expiry date picker works
- [ ] Supplier dropdown populates
- [ ] Tax amount auto-calculates
- [ ] Transfer creation succeeds
- [ ] Transfer completion updates destination stock

### Integration Tests
- [ ] Transfer between warehouses maintains all fields
- [ ] Transfer to storefront maintains all fields
- [ ] Destination StockProduct has correct pricing
- [ ] Supplier information is preserved
- [ ] Tax and cost calculations are accurate

---

## Benefits

### For Inventory Management
✅ **Complete stock tracking** - All product attributes preserved  
✅ **Accurate valuation** - Proper cost and pricing at all locations  
✅ **Tax compliance** - Tax rates maintained across transfers  
✅ **Supplier traceability** - Origin tracking maintained  
✅ **Expiry management** - Perishable goods tracked properly  

### For Business Operations
✅ **Better profit analysis** - Retail/wholesale pricing available  
✅ **Cost accountability** - Additional costs tracked  
✅ **Planning** - Expected arrival dates for logistics  
✅ **Reporting** - Complete data for financial reports  

---

## Updated Postman Examples

### Example 1: Basic Transfer (Minimal Fields)
```json
{
  "source_warehouse": "2430eb7f-72e8-47be-ab2f-7f488e0189be",
  "destination_warehouse": "c7b701bd-b50a-409a-b30e-6d35848e2ec8",
  "notes": "Weekly restock",
  "items": [
    {
      "product": "product-uuid",
      "quantity": 50,
      "unit_cost": "10.00"
    }
  ]
}
```
**Result:** System auto-copies supplier, pricing, tax info from source

### Example 2: Complete Transfer (All Fields)
```json
{
  "source_warehouse": "2430eb7f-72e8-47be-ab2f-7f488e0189be",
  "destination_warehouse": "c7b701bd-b50a-409a-b30e-6d35848e2ec8",
  "expected_arrival_date": "2025-11-05",
  "notes": "Special pricing for destination",
  "items": [
    {
      "product": "product-uuid",
      "quantity": 100,
      "unit_cost": "10.50",
      "supplier": "supplier-uuid",
      "expiry_date": "2026-12-31",
      "unit_tax_rate": "15.00",
      "unit_tax_amount": "1.58",
      "unit_additional_cost": "0.75",
      "retail_price": "18.00",
      "wholesale_price": "14.50"
    }
  ]
}
```
**Result:** Destination stock created with exact values specified

### Example 3: Perishable Goods Transfer
```json
{
  "source_warehouse": "2430eb7f-72e8-47be-ab2f-7f488e0189be",
  "destination_warehouse": "c7b701bd-b50a-409a-b30e-6d35848e2ec8",
  "expected_arrival_date": "2025-10-30",
  "notes": "Perishable - refrigerate upon arrival",
  "items": [
    {
      "product": "dairy-product-uuid",
      "quantity": 24,
      "unit_cost": "5.00",
      "expiry_date": "2025-11-15",
      "retail_price": "8.00",
      "wholesale_price": "6.50"
    }
  ]
}
```
**Result:** Expiry tracking maintained for food safety compliance

---

## Summary

**Status:** ✅ **COMPLETE**

**Files Modified:**
- `inventory/transfer_models.py` - Added 8 fields to TransferItem, 1 to Transfer
- `inventory/transfer_serializers.py` - Updated API serializers
- `inventory/migrations/0023_add_stock_batch_fields_to_transfer.py` - Database migration

**Database Changes:**
- 9 new columns added (all optional)
- No breaking changes
- Fully backward compatible

**API Changes:**
- 8 new optional fields in transfer item payload
- 1 new optional field in transfer payload
- Existing API calls work unchanged

**Next Steps:**
1. ✅ Backend migration applied
2. ⏳ Frontend form update (add optional fields)
3. ⏳ Update Postman collection with new examples
4. ⏳ User documentation update
5. ⏳ Testing with real data

**The Transfer API now supports complete stock batch management! 🎉**
