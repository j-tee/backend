# Frontend Stock Display Issue - Multi-Warehouse Confusion

## 🔴 Problem Identified

**Symptom**: Frontend shows "11 in stock" but backend rejects sale saying only "2 available"

**Root Cause**: **Mismatch between frontend aggregated stock display and backend warehouse-specific validation**

---

## 🎯 Current Architecture (Correct Backend Behavior)

### Backend Stock Validation
The backend correctly validates stock at the **warehouse/location level**:

```python
# sales/serializers.py - SaleItemSerializer.validate()
available = stock_product.get_available_quantity()  # ✅ Warehouse-specific

if available < quantity:
    raise ValidationError(
        f'Insufficient stock. Available: {available}, Requested: {quantity}'
    )
```

### Stock Hierarchy
```
Business
  └─ Storefront (e.g., "Adenta Store")
       ├─ Warehouse A: 2 units  ← Backend checks THIS specific location
       └─ Warehouse B: 9 units
       
Total across storefront: 11 units  ← Frontend shows THIS aggregate
```

---

## 📊 Evidence from Console Log

```javascript
[Stock Status Debug]
{
  productName: "HP Laptop 15"",
  storefrontId: "cc45f197-b169-4be2-a769-99138fd02d5b",
  currentLocationStock: {...},        // Specific warehouse
  storefrontAvailable: 11,            // ❌ WRONG - Aggregated across warehouses
  totalAvailable: 273,                // Total across ALL storefronts
  allLocations: (2) [...]             // Shows 2 warehouses
}
```

**The Issue**: 
- `storefrontAvailable: 11` aggregates stock from multiple warehouses
- `currentLocationStock: 2` is the actual warehouse stock
- Frontend displays the aggregated `11` but backend validates against `2`

---

## 🏗️ System Design (Multi-Warehouse POS)

### Why Warehouse-Specific Validation?

1. **Physical Reality**: Stock exists at specific physical locations
2. **Fulfillment Logic**: Sales must be fulfilled from ONE warehouse at a time
3. **Inventory Accuracy**: Prevents overselling at specific locations
4. **Transfer Requirements**: If stock is at Warehouse B, you need a transfer to Warehouse A

### Example Scenario

```
Product: HP Laptop
Adenta Store:
  ├─ Main Warehouse: 2 units
  └─ Back Warehouse: 9 units

Current Sale Location: Main Warehouse

User tries to sell 4 units:
✅ Frontend shows: "11 in stock" (correct aggregate)
❌ Backend rejects: "Only 2 available" (correct for location)
```

**This is CORRECT behavior** - the user needs to either:
1. Sell only 2 units from Main Warehouse, OR
2. Create a transfer request to move 2 units from Back Warehouse to Main Warehouse

---

## 🔧 Frontend Fix Required

### Issue: Frontend Stock Query Logic

The frontend is likely doing something like this (WRONG):

```javascript
// ❌ WRONG: Aggregating across all warehouses
const storefrontStock = allWarehouses
  .filter(w => w.storefrontId === currentStorefront)
  .reduce((sum, w) => sum + w.quantity, 0);

// Shows: "11 in stock"
```

### Solution: Show Warehouse-Specific Stock

The frontend should:

1. **Display stock for the CURRENT warehouse/location being used**
2. **Show aggregate as additional info** (not the primary number)
3. **Indicate transfers are available** if needed

```javascript
// ✅ CORRECT: Show specific warehouse stock
const currentWarehouseStock = getCurrentWarehouseStock(product, currentWarehouse);
const otherWarehousesStock = getOtherWarehousesStock(product, currentWarehouse);

// Display:
// "2 in stock (at Main Warehouse)"
// "+ 9 available at other locations"
```

---

## 📋 Recommended Frontend Changes

### 1. Stock Display Component

```jsx
// Current (Wrong)
<div className="stock-info">
  <span className="stock-count">{storefrontAvailable}</span> in stock
</div>

// Fixed (Correct)
<div className="stock-info">
  <div className="primary-stock">
    <span className="stock-count">{currentLocationStock}</span> in stock
    <span className="location-label">at {currentWarehouseName}</span>
  </div>
  
  {otherLocationsStock > 0 && (
    <div className="secondary-stock">
      <span className="transfer-available">
        + {otherLocationsStock} at other locations
      </span>
      <button onClick={handleTransferRequest}>
        Request Transfer
      </button>
    </div>
  )}
</div>
```

### 2. Add to Cart Validation

```javascript
// Before adding to cart, validate against current location
const addToCart = async (product, quantity) => {
  const currentLocationStock = product.stock_products.find(
    sp => sp.warehouse.id === currentWarehouseId
  )?.quantity || 0;
  
  if (quantity > currentLocationStock) {
    showError({
      message: `Only ${currentLocationStock} available at ${currentWarehouseName}`,
      actions: [
        {
          label: `Request transfer from other locations`,
          onClick: () => openTransferDialog(product)
        }
      ]
    });
    return;
  }
  
  // Proceed with add to cart
};
```

### 3. Product Search Results

Update the product search to include warehouse context:

```javascript
// API Response should include
{
  product: {
    id: "...",
    name: "HP Laptop 15\"",
    // ... other fields
    stock_products: [
      {
        warehouse: {
          id: "...",
          name: "Main Warehouse",
          is_current: true  // ← Indicates current warehouse
        },
        quantity: 2,
        available_quantity: 2
      },
      {
        warehouse: {
          id: "...",
          name: "Back Warehouse",
          is_current: false
        },
        quantity: 9,
        available_quantity: 9
      }
    ],
    // Calculated fields
    current_location_stock: 2,      // ← Use this for validation
    other_locations_stock: 9,       // ← Show this as "available elsewhere"
    total_storefront_stock: 11      // ← Show this as total info
  }
}
```

---

## 🎨 UI/UX Recommendation

### Product Card Display

```
┌─────────────────────────────────────┐
│  HP Laptop 15"                      │
│  GH₵ 499.60                         │
│                                     │
│  📦 2 in stock (Main Warehouse)     │ ← Primary info
│  ✨ +9 at other locations           │ ← Secondary info
│                                     │
│  [➕ Add] [🔄 Request Transfer]     │
└─────────────────────────────────────┘
```

### Add to Cart Error Message

```
┌─────────────────────────────────────┐
│  ⚠️ Quantity not available          │
│                                     │
│  You requested: 4 units             │
│  Available here: 2 units            │
│  (at Main Warehouse)                │
│                                     │
│  Options:                           │
│  • Change quantity to 2 or less     │
│  • Request transfer from Back       │
│    Warehouse (9 units available)    │
│                                     │
│  [Change Quantity] [Request Transfer]
└─────────────────────────────────────┘
```

---

## 🔍 Backend API Changes Needed

To support the frontend fix, add warehouse context to product responses:

### Option 1: Add to existing product serializer

```python
# inventory/serializers.py
class ProductSerializer(serializers.ModelSerializer):
    current_location_stock = serializers.SerializerMethodField()
    other_locations_stock = serializers.SerializerMethodField()
    current_warehouse_id = serializers.SerializerMethodField()
    
    def get_current_location_stock(self, obj):
        """Get stock at current user's warehouse"""
        request = self.context.get('request')
        if not request or not hasattr(request.user, 'current_warehouse'):
            return 0
        
        stock = obj.stock_products.filter(
            warehouse_id=request.user.current_warehouse_id
        ).first()
        
        return stock.get_available_quantity() if stock else 0
    
    def get_other_locations_stock(self, obj):
        """Get stock at other warehouses in same storefront"""
        request = self.context.get('request')
        if not request or not hasattr(request.user, 'current_warehouse'):
            return 0
        
        current_storefront = request.user.current_storefront
        other_stock = obj.stock_products.filter(
            warehouse__storefront=current_storefront
        ).exclude(
            warehouse_id=request.user.current_warehouse_id
        ).aggregate(
            total=Sum('quantity')
        )['total'] or 0
        
        return other_stock
```

### Option 2: Add warehouse context endpoint

```python
# inventory/views.py
@action(detail=False, methods=['get'])
def check_availability(self, request):
    """
    Check product availability across warehouses
    
    Query params:
    - product_id: UUID
    - quantity: int (optional)
    """
    product_id = request.query_params.get('product_id')
    quantity = int(request.query_params.get('quantity', 1))
    
    product = Product.objects.get(id=product_id)
    current_warehouse = request.user.current_warehouse
    
    # Get stock at current location
    current_stock = product.stock_products.filter(
        warehouse=current_warehouse
    ).first()
    
    # Get stock at other locations in same storefront
    other_locations = product.stock_products.filter(
        warehouse__storefront=current_warehouse.storefront
    ).exclude(
        warehouse=current_warehouse
    ).values('warehouse__name', 'quantity', 'warehouse__id')
    
    return Response({
        'product_id': str(product.id),
        'current_location': {
            'warehouse_id': str(current_warehouse.id),
            'warehouse_name': current_warehouse.name,
            'available': current_stock.get_available_quantity() if current_stock else 0,
            'can_fulfill': current_stock.get_available_quantity() >= quantity if current_stock else False
        },
        'other_locations': [
            {
                'warehouse_id': str(loc['warehouse__id']),
                'warehouse_name': loc['warehouse__name'],
                'available': loc['quantity']
            }
            for loc in other_locations
        ],
        'total_storefront_stock': sum([
            loc['quantity'] for loc in other_locations
        ]) + (current_stock.quantity if current_stock else 0),
        'transfer_required': quantity > (current_stock.get_available_quantity() if current_stock else 0)
    })
```

---

## ✅ Action Items

### Backend Tasks (Priority: Medium)
1. ✅ Keep current validation logic (already correct)
2. 🔲 Add warehouse context to user session/JWT
3. 🔲 Enhance product serializer with location-specific stock
4. 🔲 Add stock availability check endpoint (optional)

### Frontend Tasks (Priority: HIGH - Immediate)
1. 🔲 **URGENT**: Fix stock display to show current warehouse stock (not aggregate)
2. 🔲 Add warehouse name/context to stock display
3. 🔲 Show "other locations available" as secondary info
4. 🔲 Update add-to-cart validation to use current location stock
5. 🔲 Add "Request Transfer" button when stock is at other locations
6. 🔲 Update error messages to be more specific about location

### Documentation Tasks
1. 🔲 Update frontend integration guide with warehouse context
2. 🔲 Document stock availability API endpoints
3. 🔲 Create UI/UX guide for multi-warehouse stock display

---

## 📝 Summary

**The backend is working correctly** - it validates stock at the specific warehouse/location level, which is the proper behavior for a multi-warehouse POS system.

**The frontend needs fixing** - it's showing aggregated stock across all warehouses, which creates user confusion when the backend correctly rejects sales based on location-specific availability.

**Solution**: Update frontend to:
1. Display **current warehouse stock** as the primary number
2. Show **other locations** as secondary information
3. Provide **transfer request** option when needed
4. Match backend's warehouse-specific validation logic

---

*Document created: October 14, 2025*
*Issue Category: Frontend-Backend Integration*
*Priority: HIGH*
*Impact: User Experience, Sales Workflow*
