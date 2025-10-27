# Data Integrity Checks Analysis
## Pre-Population Verification Required

**Date:** October 10, 2025  
**Purpose:** Identify all data integrity checks before creating population script  
**Status:** 🔍 ANALYSIS COMPLETE

---

## Executive Summary

Before creating a data population script, we need to verify ALL data integrity constraints are working correctly. Based on codebase analysis, here are the critical checks organized by category:

---

## 1. INVENTORY DATA INTEGRITY

### ✅ VERIFIED (Working)

#### 1.1 Stock Adjustment Validation
**Signal:** `validate_adjustment_wont_cause_negative_stock`  
**Location:** `inventory/signals.py` line 137  
**Rule:** Adjustments cannot make available stock negative  
**Calculation:** `Available = Intake + SUM(adjustments) - SUM(transfers) - SUM(sales)`  
**Test Status:** ✅ PASS (Test 2)

#### 1.2 Sale Inventory Validation
**Location:** `sales/models.py` - `Sale.complete_sale()` method  
**Rule:** Sales cannot exceed available storefront inventory  
**Test Status:** ✅ PASS (Test 3)

### 🔄 NEEDS VERIFICATION

#### 1.3 StockProduct Quantity Locking
**Signal:** `prevent_quantity_edit_after_movements`  
**Location:** `inventory/signals.py` line 40  
**Rule:** StockProduct.quantity cannot be edited after ANY movement  
**Movements Include:**
- Stock Adjustments (any status)
- Transfer Requests (any status)
- Storefront Inventory allocations
- Sales (any status)

**WHY CRITICAL:**
```python
# StockProduct.quantity = Historical Record (IMMUTABLE)
# If we allow editing after movements, calculations break:
# Available = WRONG_INTAKE + Adjustments - Transfers - Sales  ← WRONG!
```

**Test Required:**
```python
1. Create StockProduct with 100 units
2. Create StockAdjustment (any type)
3. Try to edit StockProduct.quantity to 110
4. Should FAIL with ValidationError
5. Error should list which movements exist
```

---

#### 1.4 Transfer Request Validation
**Signal:** `validate_transfer_has_sufficient_stock`  
**Location:** `inventory/signals.py` line 212  
**Rule:** Transfer cannot exceed available warehouse stock  
**Calculation:** Same as adjustment validation

**Test Required:**
```python
1. Create StockProduct with 50 units in Warehouse A
2. Create Adjustment -10 (now 40 available)
3. Try to create Transfer for 45 units
4. Should FAIL (only 40 available)
5. Try transfer for 35 units
6. Should PASS
```

---

#### 1.5 StockAdjustment Required Fields
**Model:** `StockAdjustment`  
**Location:** `inventory/stock_adjustments.py`

**Required Fields (NOT NULL):**
- `business` - ForeignKey to Business
- `stock_product` - ForeignKey to StockProduct
- `adjustment_type` - Choice field (DAMAGE, THEFT, FOUND, etc.)
- `quantity` - Decimal (can be negative)
- **`unit_cost`** - Decimal (REQUIRED - must match StockProduct.unit_cost)
- **`retail_price`** - Decimal (REQUIRED - must match StockProduct.retail_price)
- `reason` - CharField
- `reference_number` - CharField (unique)
- `status` - Choice field
- `created_by` - ForeignKey to User

**Population Script Must:**
```python
adjustment = StockAdjustment.objects.create(
    business=business,
    stock_product=stock_product,
    adjustment_type='DAMAGE',
    quantity=-5,
    unit_cost=stock_product.unit_cost,      # ← REQUIRED!
    retail_price=stock_product.retail_price,  # ← REQUIRED!
    reason='Damaged during handling',
    reference_number=f'ADJ-{unique_id}',
    status='COMPLETED',
    created_by=user,
    approved_by=user  # If status=COMPLETED
)
```

---

## 2. BUSINESS & MEMBERSHIP INTEGRITY

### ✅ VERIFIED (Auto-created by Signals)

#### 2.1 Business Owner Membership
**Signal:** `Business.save()` override  
**Location:** `accounts/models.py` line 365  
**Rule:** When Business is created, owner automatically gets OWNER membership  
**Auto-created:** Yes

```python
def save(self, *args, **kwargs):
    is_new = self._state.adding
    super().save(*args, **kwargs)
    if is_new:
        self.owner.add_business_membership(
            business=self,
            role=BusinessMembership.OWNER,
            is_admin=True
        )
```

**Population Impact:** ✅ Don't manually create owner membership - it's automatic

---

#### 2.2 Business Settings Auto-creation
**Signal:** `create_business_settings`  
**Location:** `settings/signals.py` line 7  
**Rule:** When Business is created, settings auto-created with defaults  
**Auto-created:** Yes

```python
@receiver(post_save, sender=Business)
def create_business_settings(sender, instance, created, **kwargs):
    if created:
        BusinessSettings.objects.get_or_create(
            business=instance,
            defaults={...defaults...}
        )
```

**Population Impact:** ✅ Don't manually create settings - it's automatic

---

### 🔄 NEEDS VERIFICATION

#### 2.3 Business Required Fields
**Model:** `Business`  
**Location:** `accounts/models.py` line 343

**Required (NOT NULL):**
- `owner` - ForeignKey to User
- `name` - CharField (unique)
- **`tin`** - CharField (unique) ← Tax ID Number
- `email` - EmailField
- `address` - TextField

**Optional:**
- `website` - URLField
- `social_handles` - JSONField
- `phone_numbers` - JSONField

**Uniqueness Constraints:**
- `name` must be unique globally
- `tin` must be unique globally

**Test Required:**
```python
1. Try creating Business with duplicate TIN
2. Should FAIL with IntegrityError
3. Try creating Business with duplicate name
4. Should FAIL with IntegrityError
```

---

#### 2.4 BusinessMembership Validation
**Model:** `BusinessMembership`  
**Location:** `accounts/models.py` line 376

**Unique Together:** `('business', 'user')`  
**Rule:** User can only have ONE membership per business

**Test Required:**
```python
1. Create BusinessMembership(business=B1, user=U1, role='STAFF')
2. Try creating another BusinessMembership(business=B1, user=U1, role='MANAGER')
3. Should FAIL with IntegrityError (unique_together violation)
```

---

#### 2.5 StoreFront Employee Validation
**Model:** `StoreFrontEmployee`  
**Location:** `inventory/models.py` line 1205

**Validation in `clean()` method:**
```python
def clean(self):
    # Storefront must belong to business
    if not BusinessStoreFront.objects.filter(
        business=self.business, 
        storefront=self.storefront, 
        is_active=True
    ).exists():
        raise ValidationError('Storefront must belong to the specified business.')
    
    # User must be business member
    if not BusinessMembership.objects.filter(
        business=self.business, 
        user=self.user, 
        is_active=True
    ).exists():
        raise ValidationError('User must be an active member of the business to be assigned.')
```

**Test Required:**
```python
1. Create Business B1, StoreFront S1 (not linked to B1)
2. Try: StoreFrontEmployee(business=B1, storefront=S1, user=U1)
3. Should FAIL (storefront not linked to business)

4. Create Business B1, StoreFront S1 (linked), User U1 (not member of B1)
5. Try: StoreFrontEmployee(business=B1, storefront=S1, user=U1)
6. Should FAIL (user not member of business)
```

---

## 3. SALES DATA INTEGRITY

### 🔄 NEEDS VERIFICATION

#### 3.1 Sale Amount Validators
**Model:** `Sale`  
**Location:** `sales/models.py` line 329

**Decimal Field Validators (MinValueValidator):**
```python
subtotal >= 0.00
discount_amount >= 0.00
tax_amount >= 0.00
total_amount >= 0.00
amount_paid >= 0.00
amount_due >= 0.00
```

**Test Required:**
```python
1. Try creating Sale with subtotal = -100.00
2. Should FAIL with ValidationError
3. Try creating Sale with discount_amount = -50.00
4. Should FAIL with ValidationError
```

---

#### 3.2 SaleItem Amount Validators
**Model:** `SaleItem`  
**Location:** `sales/models.py` line 820

**Decimal Field Validators:**
```python
quantity > 0  # Must be positive
unit_price >= 0.00
discount_amount >= 0.00
discount_percentage: 0.00 <= value <= 100.00
total_price >= 0.00
```

**Test Required:**
```python
1. Try creating SaleItem with quantity = 0
2. Should FAIL (quantity must be positive)
3. Try SaleItem with discount_percentage = 150.00
4. Should FAIL (max 100.00)
```

---

#### 3.3 Credit Sale Validation
**Serializer:** `SaleSerializer.validate()`  
**Location:** `sales/serializers.py` line 342

**Rules:**
```python
# Credit sales MUST have a customer
if payment_type == 'CREDIT' and not customer:
    raise ValidationError('Customer is required for credit sales')

# Credit sale must not exceed customer's available credit
available_credit = customer.credit_limit - customer.outstanding_balance
if total_amount > available_credit and not manager_override:
    raise ValidationError('Exceeds customer credit limit')
```

**Test Required:**
```python
1. Create Customer with credit_limit=1000, outstanding_balance=800
2. Try Sale(payment_type='CREDIT', total=300) # Exceeds 200 available
3. Should FAIL unless manager_override=True
```

---

#### 3.4 Customer Unique Constraint
**Model:** `Customer`  
**Migration:** `sales/migrations/0003` line 227

**Unique Together:** `('business', 'phone')`  
**Rule:** Phone number must be unique within a business

**Test Required:**
```python
1. Create Customer(business=B1, phone='+233123456789')
2. Try creating another Customer(business=B1, phone='+233123456789')
3. Should FAIL with IntegrityError
```

---

#### 3.5 AuditLog Immutability
**Model:** `AuditLog`  
**Location:** `sales/models.py` line 1226

**Rules:**
```python
def save(self, *args, **kwargs):
    if self.pk and AuditLog.objects.filter(pk=self.pk).exists():
        raise ValidationError("Audit logs cannot be modified")
    super().save(*args, **kwargs)

def delete(self, *args, **kwargs):
    raise ValidationError("Audit logs cannot be deleted")
```

**Test Required:**
```python
1. Create AuditLog
2. Try updating any field
3. Should FAIL
4. Try deleting
5. Should FAIL
```

---

## 4. RELATIONSHIP INTEGRITY

### 🔄 NEEDS VERIFICATION

#### 4.1 BusinessWarehouse Unique Constraint
**Constraint:** One warehouse can belong to only ONE business  
**Database:** `business_warehouses_warehouse_id_key` UNIQUE constraint

**Test Required:**
```python
1. Create Warehouse W1
2. Create BusinessWarehouse(business=B1, warehouse=W1)
3. Try: BusinessWarehouse(business=B2, warehouse=W1)
4. Should FAIL with IntegrityError (warehouse already linked)
```

---

#### 4.2 BusinessStoreFront Validation
**Similar to BusinessWarehouse**

**Test Required:**
```python
1. Create StoreFront S1
2. Create BusinessStoreFront(business=B1, storefront=S1)
3. Try: BusinessStoreFront(business=B2, storefront=S1)
4. Should check if this is allowed or constrained
```

---

## 5. PRODUCT & STOCK INTEGRITY

### 🔄 NEEDS VERIFICATION

#### 5.1 Product SKU Uniqueness
**Model:** `Product`  
**Field:** `sku` - Likely unique within business

**Test Required:**
```python
1. Check if SKU has unique constraint
2. If yes, test: Create Product(business=B1, sku='LAP-001')
3. Try: Product(business=B1, sku='LAP-001')
4. Should FAIL if unique constraint exists
```

---

#### 5.2 Stock Batch Date Validation
**Model:** `Stock`  
**Field:** `arrival_date` - Should not be in future?

**Test Required:**
```python
1. Try creating Stock with arrival_date = tomorrow
2. Check if validation exists
3. If no validation, consider adding
```

---

#### 5.3 StockProduct Price Validation
**Model:** `StockProduct`

**Business Rules to Verify:**
```python
# Should retail_price > wholesale_price > unit_cost?
# Or are all prices independent?

unit_cost = 500
wholesale_price = 450  # ← Less than cost? Allowed?
retail_price = 400     # ← Less than wholesale? Allowed?
```

**Test Required:**
```python
1. Create StockProduct with retail_price < unit_cost
2. Check if this is allowed
3. Document business rule
```

---

## 6. TRANSFER REQUEST INTEGRITY

### 🔄 NEEDS VERIFICATION

#### 6.1 Transfer Fulfillment Validation
**Model:** `TransferRequest`

**Business Rules:**
```python
# When fulfilling transfer:
# 1. Warehouse stock must be sufficient (signal validates this)
# 2. Must create StoreFrontInventory record
# 3. Status must change to 'FULFILLED'
# 4. fulfilled_at timestamp set
```

**Test Required:**
```python
1. Create TransferRequest(status='APPROVED', quantity=50)
2. Call fulfill() method
3. Verify:
   - StoreFrontInventory created with quantity=50
   - TransferRequest.status = 'FULFILLED'
   - TransferRequest.fulfilled_at is set
   - Warehouse available stock decreased by 50
```

---

## 7. SUMMARY: Tests to Create Before Population

### Priority 1 (CRITICAL - Must Work Before Population)

1. **✅ Stock Adjustment Negative Validation** - DONE
2. **✅ Sale Overselling Prevention** - DONE
3. **🔄 StockProduct Quantity Locking** - TO DO
4. **🔄 Transfer Request Validation** - TO DO
5. **🔄 StockAdjustment Required Fields (unit_cost, retail_price)** - TO DO
6. **🔄 Credit Sale Customer Requirement** - TO DO
7. **🔄 Customer Credit Limit Validation** - TO DO

### Priority 2 (IMPORTANT - Should Work)

8. **🔄 Business TIN Uniqueness** - TO DO
9. **🔄 Business Name Uniqueness** - TO DO
10. **🔄 BusinessMembership Unique Together** - TO DO
11. **🔄 Customer Phone Uniqueness per Business** - TO DO
12. **🔄 StoreFrontEmployee Validation** - TO DO
13. **🔄 BusinessWarehouse One-to-One** - TO DO

### Priority 3 (NICE TO HAVE - Good Practices)

14. **🔄 Sale Amount Validators** - TO DO
15. **🔄 SaleItem Amount Validators** - TO DO
16. **🔄 AuditLog Immutability** - TO DO
17. **🔄 Product SKU Uniqueness** - TO DO
18. **🔄 Price Relationship Validation** - TO DO

---

## Recommended Approach

### Phase 1: Complete Existing Test Suite
Fix `test_data_integrity.py` to properly create adjustments with unit_cost/retail_price.

### Phase 2: Add Missing Critical Tests
Create tests for:
- StockProduct quantity locking (Test 1 fix)
- Transfer request validation (Test 4 fix)
- Credit sale validation

### Phase 3: Create Population Script
Once ALL Priority 1 tests pass, create population script that:
- Respects all validated constraints
- Handles auto-created relationships (Business.owner membership, Settings)
- Provides proper unit_cost/retail_price for adjustments
- Validates credit limits for credit sales
- Creates realistic data flows

### Phase 4: Run Population with Verification
- Populate database
- Run ALL tests again to verify data integrity maintained
- Check for any constraint violations

---

## Next Steps

1. **Fix test_data_integrity.py:**
   - Add unit_cost and retail_price to all StockAdjustment creations
   - Re-run to verify all signals work

2. **Add missing tests:**
   - Test 5: Transfer validation
   - Test 6: Credit sale validation
   - Test 7: Business uniqueness constraints

3. **Document all findings:**
   - Which constraints are database-level (UNIQUE, FK)
   - Which are application-level (signals, clean() methods)
   - Which are both

4. **Create population script** only after ALL tests pass

---

## Conclusion

We have **2 out of 18 critical data integrity checks verified**. Before creating a population script, we need to:

1. ✅ Fix the existing test suite (add unit_cost/retail_price)
2. 🔄 Complete all Priority 1 tests (6 more critical tests)
3. 🔄 Run full test suite to ensure ALL constraints work
4. 📝 Document any business rules we discover
5. ✨ THEN create population script with confidence

**Estimated Work:**
- Fix existing tests: 30 minutes
- Add Priority 1 tests: 2-3 hours
- Documentation: 1 hour
- Total: ~4 hours before population script

This ensures our population script will create **valid, realistic data** that respects all constraints.
