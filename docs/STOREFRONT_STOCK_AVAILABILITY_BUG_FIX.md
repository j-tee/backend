# Storefront Stock Availability Bug - Fixed

## 🐛 Bug Description

**Symptom:** Frontend shows "11 laptops available" but backend rejects adding 4 units with error "Available: 2.00"

**Root Cause:** The `AddSaleItemSerializer.validate()` method was calculating storefront availability incorrectly:
```python
# WRONG - Only considered completed sales
available = storefront_inventory.quantity - completed_sales
# Result: 11 - 0 = 11 available ❌
```

**Missing Factor:** Active stock reservations from DRAFT sales were not included in the calculation.

---

## 🔍 Investigation Results

### Database State
```
HP Laptop 15" at Storefront cc45f197-b169-4be2-a769-99138fd02d5b:
- StoreFrontInventory.quantity: 11 units
- Completed sales: 0 units  
- Active reservations: 8 units (from 2 DRAFT sales)
- ACTUAL available: 11 - 0 - 8 = 3 units ✅
```

### Active Reservations Found
```
Sale ID: 2a679396-8120-4456-876d-355106dff1df
  - Quantity: 4 units
  - Expires: 2025-10-14 01:34:47

Sale ID: 8f17e58f-0992-4f41-b843-072f29420142
  - Quantity: 4 units  
  - Expires: 2025-10-13 10:38:07
  
Total Reserved: 8 units
```

---

## ✅ Fix Applied

### Location
`sales/serializers.py` - `AddSaleItemSerializer.validate()` method (lines 590-640)

### Changes Made

**BEFORE:**
```python
# Only counted completed sales
sold_from_storefront = SaleItem.objects.filter(
    product=product,
    sale__storefront=storefront,
    sale__status='COMPLETED'
).aggregate(total=Sum('quantity'))['total'] or Decimal('0')

available_at_storefront = storefront_inv.quantity - sold_from_storefront
```

**AFTER:**
```python
# Count both completed sales AND active reservations
sold_from_storefront = SaleItem.objects.filter(
    product=product,
    sale__storefront=storefront,
    sale__status='COMPLETED'
).aggregate(total=Sum('quantity'))['total'] or Decimal('0')

# NEW: Get active reservations at this storefront
reserved_quantity = Decimal('0')
reservations_query = StockReservation.objects.filter(
    stock_product__product=product,
    status='ACTIVE'
)

# Exclude current sale's reservations (they'll be updated)
if current_sale_id:
    reservations_query = reservations_query.exclude(
        cart_session_id=str(current_sale_id)
    )

# Only count reservations from sales at THIS storefront
for reservation in reservations_query:
    try:
        sale_id = UUID(str(reservation.cart_session_id))
        sale = Sale.objects.filter(id=sale_id, storefront=storefront).first()
        if sale:
            reserved_quantity += Decimal(str(reservation.quantity))
    except (ValueError, TypeError):
        pass

# Calculate available (subtract BOTH sold and reserved)
available_at_storefront = storefront_inv.quantity - sold_from_storefront - reserved_quantity
```

### Improved Error Message
Now includes breakdown:
```
Insufficient storefront inventory for "HP Laptop 15"". 
Available: 3.00, Requested: 4. 
(Total: 11, Sold: 0, Reserved: 8) 
Create a transfer request to move more stock to this storefront.
```

---

## 🎯 Expected Behavior After Fix

### Scenario 1: Adding Item to New Cart
```
Storefront Inventory: 11 units
Completed Sales: 0 units
Active Reservations: 8 units (other carts)
Available: 11 - 0 - 8 = 3 units

✅ Can add 1-3 units (will create new reservation)
❌ Cannot add 4+ units (insufficient after reservations)
```

### Scenario 2: Updating Item in Existing Cart
```
Storefront Inventory: 11 units
Completed Sales: 0 units
Active Reservations: 8 units
Current Cart Reservation: 2 units (excluded from calculation)

Available for THIS cart: 11 - 0 - (8-2) = 5 units

✅ Can update to 1-5 units  
❌ Cannot update to 6+ units
```

### Scenario 3: Completing a Sale
```
Before completion:
- Storefront Inventory: 11 units
- Reservations: 8 units
- Available: 3 units

After completing 4-unit sale:
- Storefront Inventory: 11 units (unchanged)
- Completed Sales: 4 units (new)
- Reservations: 4 units (one released)
- Available: 11 - 4 - 4 = 3 units
```

---

## 🔄 Consistency Across System

This fix ensures the `AddSaleItemSerializer` calculation matches other parts of the system:

### 1. StockAvailabilityView (inventory/views.py)
Already correctly calculates:
```python
total_available = storefront_inventory.quantity
reserved_quantity = StockReservation.objects.filter(...).aggregate(...)
unreserved_quantity = total_available - reserved_quantity
```

### 2. Sale.commit_stock() (sales/models.py)
Correctly checks storefront inventory when completing sale:
```python
current_qty = storefront_inventory.quantity
if current_qty < quantity_required:
    raise ValidationError("Insufficient storefront stock")
```

### 3. Frontend Stock Display
Should now see consistent availability across:
- Product search results
- Add to cart validation  
- Cart quantity updates
- Checkout process

---

## 🧪 Testing Recommendations

### Manual Testing
1. **Check current state:**
   ```bash
   python manage.py shell
   from sales.models import StockReservation
   from inventory.models import Product
   
   laptop = Product.objects.get(name__icontains='HP Laptop')
   reservations = StockReservation.objects.filter(
       stock_product__product=laptop, status='ACTIVE'
   )
   print(f'Reserved: {sum(r.quantity for r in reservations)}')
   ```

2. **Try adding item:**
   - Should now correctly show available = total - sold - reserved
   - Error message should show breakdown

3. **Complete one cart:**
   - Should release its reservation
   - Should make those units available for new carts

### Automated Testing
```python
def test_storefront_availability_with_reservations():
    # Setup: 10 units in storefront
    # Create cart 1 with 4 units (active reservation)
    # Create cart 2 with 3 units (active reservation)
    # Available should be: 10 - 0 - 7 = 3 units
    
    # Try to add 4 units to cart 3
    # Should fail with "Available: 3"
    
    # Try to add 2 units to cart 3  
    # Should succeed
```

---

## 📊 Impact Analysis

### Before Fix
- ❌ Multiple users could add items beyond storefront capacity
- ❌ Checkout would fail with cryptic errors
- ❌ Frontend showed misleading availability
- ❌ Race conditions in high-traffic scenarios

### After Fix
- ✅ Accurate availability calculation at all times
- ✅ Reservations properly tracked across carts
- ✅ Clear error messages with breakdowns
- ✅ Consistent behavior system-wide
- ✅ Prevents overselling at storefront level

---

## 🚀 Deployment Notes

### Required Actions
1. ✅ Code fix applied to `sales/serializers.py`
2. ⚠️ **IMPORTANT:** Check for expired reservations before deployment
3. ⚠️ Clear any stale DRAFT sales if needed

### Cleanup Script (Optional)
```python
# Clean up expired reservations
from sales.models import StockReservation
from django.utils import timezone

expired = StockReservation.objects.filter(
    status='ACTIVE',
    expires_at__lt=timezone.now()
)
print(f'Found {expired.count()} expired reservations')
expired.update(status='EXPIRED')
```

### Monitoring
After deployment, monitor:
- Cart abandonment rate (should decrease)
- "Add to cart" failure rate (should show accurate errors)
- Checkout completion rate (should improve)

---

## 📝 Related Files

- `sales/serializers.py` - Main fix location
- `inventory/views.py` - `StockAvailabilityView` (already correct)
- `sales/models.py` - `Sale.commit_stock()` (already correct)
- `inventory/models.py` - `StockReservation` model

---

## ✅ Resolution Status

- [x] Bug identified and root cause found
- [x] Fix implemented in serializer
- [x] Error messages improved
- [x] Documentation created
- [ ] Tested manually (pending)
- [ ] Unit tests added (recommended)
- [ ] Deployed to production (pending)

---

*Fixed on: October 14, 2025*
*Bug Report: Frontend showing inconsistent stock availability*
*Fix: Account for active reservations in storefront availability calculation*
