# Stock Flow and Data Integrity Guide

## Critical Data Integrity Issue Found

**Date:** October 10, 2025  
**Issue:** Sample data population script was bypassing proper stock flow, creating sales without storefront inventory, leading to reconciliation mismatches.

## Correct Stock Flow

### 1. Stock Intake (Warehouse)
```
Warehouse receives stock → Creates StockProduct records
- Stock batches are received at warehouse
- Each batch creates a StockProduct with quantity
- StockProduct.quantity represents units in warehouse
```

### 2. Transfer Request (Storefront → Warehouse)
```
Employee creates TransferRequest → Requests stock for storefront
- Storefront employee requests products
- TransferRequest contains TransferRequestLineItem(s)
- Status: NEW
```

### 3. Request Fulfillment (Warehouse → Storefront)
```
Manager fulfills request → Stock moves to storefront
- Manager approves and fulfills request
- Calls: TransferRequest.apply_manual_inventory_fulfillment()
- Creates/Updates StoreFrontInventory records
- StoreFrontInventory.quantity += requested_quantity
- Status: FULFILLED
```

### 4. Sales (Storefront)
```
Customer purchases → Reduces storefront inventory
- Sale created with status PENDING/COMPLETED
- SaleItem references:
  - stock_product (warehouse batch origin)
  - product
  - sale
- Sale does NOT modify StockProduct.quantity
- Sale does NOT directly modify StoreFrontInventory
```

### 5. Stock Reconciliation
```
Formula: Warehouse (459) + Storefront (0) + Sold (135) - Shrinkage (0) + Corrections (0) - Reservations (0) = Recorded batch size (459)

If mismatch detected:
- Over accounted: Sales happened without storefront stock
- Under accounted: Stock missing/untracked
```

## Data Integrity Rules

### RULE 1: Stock Product Quantity is IMMUTABLE After First Movement
```python
# StockProduct.quantity should NEVER be modified after:
# - Any StoreFrontInventory transfer
# - Any Sale completion
# - Any adjustment applied

# This quantity represents the original warehouse intake
```

### RULE 2: Sales MUST Have Corresponding Storefront Inventory
```python
# Before creating a sale:
1. Check StoreFrontInventory.quantity >= sale_quantity
2. Create StockReservation (optional, for pending sales)
3. Create Sale + SaleItem
4. Storefront inventory is implicitly reduced through sale tracking
```

### RULE 3: Transfer Requests Must Be Fulfilled Before Sales
```python
# Incorrect flow (causes data integrity issues):
Stock → Sale (❌ No storefront inventory)

# Correct flow:
Stock → TransferRequest → Fulfill → StoreFrontInventory → Sale (✅)
```

### RULE 4: Reconciliation Must Balance
```python
# For any product:
original_warehouse_stock = StockProduct.quantity
transferred_to_storefronts = sum(StoreFrontInventory.quantity)
sold_units = sum(SaleItem.quantity where sale.status='COMPLETED')
shrinkage = sum(StockAdjustment.quantity where type in SHRINKAGE_TYPES)
corrections = sum(StockAdjustment.quantity where type='CORRECTION')
active_reservations = sum(StockReservation.quantity where status='ACTIVE')

# Balance equation:
original_warehouse_stock = 
    transferred_to_storefronts + 
    sold_units + 
    shrinkage - 
    corrections + 
    active_reservations
```

## Common Data Integrity Violations

### Violation 1: Sales Without Storefront Inventory
```python
# Symptom: "135 units over accounted"
# Cause: Sale created without transfer request fulfillment
# Fix: Always create TransferRequest → Fulfill → Sale
```

### Violation 2: Modifying StockProduct.quantity After Sales
```python
# ❌ WRONG:
stock_product.quantity -= sale_item.quantity
stock_product.save()

# ✅ CORRECT:
# Don't modify stock_product.quantity
# System tracks availability through:
# - StoreFrontInventory
# - SaleItem
# - StockReservation
```

### Violation 3: Double-Counting Inventory
```python
# ❌ WRONG:
# Creating StoreFrontInventory AND modifying StockProduct.quantity

# ✅ CORRECT:
# StockProduct.quantity = original warehouse intake (immutable)
# StoreFrontInventory.quantity = current storefront stock
# Available = StoreFrontInventory - SaleItems - Reservations
```

## Fix for Sample Data Population

### Before (Incorrect):
```python
# populate_sample_data.py - WRONG
stock_product = StockProduct.objects.create(...)
sale = Sale.objects.create(...)
SaleItem.objects.create(
    sale=sale,
    stock_product=stock_product,  # Selling from warehouse!
    ...
)
# ❌ No StoreFrontInventory created
# ❌ No TransferRequest/Fulfillment
```

### After (Correct):
```python
# populate_sample_data.py - CORRECT
# 1. Create warehouse stock
stock_product = StockProduct.objects.create(...)

# 2. Create transfer request
transfer_request = TransferRequest.objects.create(
    business=business,
    storefront=storefront,
    ...
)
TransferRequestLineItem.objects.create(
    transfer_request=transfer_request,
    product=product,
    requested_quantity=quantity,
)

# 3. Fulfill request (moves to storefront)
transfer_request.apply_manual_inventory_fulfillment()
transfer_request.status = 'FULFILLED'
transfer_request.save()

# 4. NOW sales can happen
sale = Sale.objects.create(storefront=storefront, ...)
SaleItem.objects.create(sale=sale, ...)
# ✅ Storefront inventory exists
# ✅ Reconciliation will balance
```

## Monitoring and Validation

### Check for Data Integrity Issues:
```python
# Find products with reconciliation mismatches
from inventory.models import Product, StockProduct, StoreFrontInventory
from sales.models import SaleItem

for product in Product.objects.all():
    warehouse_stock = StockProduct.objects.filter(
        product=product
    ).aggregate(total=Sum('quantity'))['total'] or 0
    
    storefront_stock = StoreFrontInventory.objects.filter(
        product=product
    ).aggregate(total=Sum('quantity'))['total'] or 0
    
    sold = SaleItem.objects.filter(
        product=product,
        sale__status='COMPLETED'
    ).aggregate(total=Sum('quantity'))['total'] or 0
    
    expected = warehouse_stock
    actual = storefront_stock + sold
    
    if expected != actual:
        print(f"❌ {product.name}: Expected {expected}, Got {actual}")
        print(f"   Warehouse: {warehouse_stock}, Storefront: {storefront_stock}, Sold: {sold}")
        print(f"   Mismatch: {actual - expected} units")
```

## Prevention Measures

### 1. Add Database Constraints
Consider adding triggers or constraints to prevent:
- Creating sales without corresponding storefront inventory
- Modifying StockProduct.quantity after first movement

### 2. API Validation
```python
# In SaleSerializer.validate():
def validate(self, data):
    for item in data['items']:
        storefront_inv = StoreFrontInventory.objects.filter(
            storefront=data['storefront'],
            product=item['product']
        ).first()
        
        if not storefront_inv or storefront_inv.quantity < item['quantity']:
            raise ValidationError(
                f"Insufficient storefront inventory for {item['product'].name}"
            )
    return data
```

### 3. Automated Reconciliation Checks
Run periodic checks to detect and alert on reconciliation mismatches.

## Summary

**Key Takeaway:** Sales should ONLY happen from storefront inventory, not directly from warehouse stock. The proper flow is:

```
Warehouse Stock → Transfer Request → Fulfillment → Storefront Inventory → Sales
```

Any deviation from this flow will cause data integrity issues and reconciliation mismatches.
