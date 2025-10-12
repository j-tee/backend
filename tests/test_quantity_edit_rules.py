#!/usr/bin/env python
"""
TEST: StockProduct.quantity Edit Rules
======================================

Verifies the EXACT requirement:
- CAN edit quantity during intake (before any movements)
- CANNOT edit quantity after ANY stock movement (adjustment, transfer, sale)

This test validates the signal enforcement matches the business rule.
"""

import sys
import os
import django

sys.path.insert(0, '/home/teejay/Documents/Projects/pos/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from decimal import Decimal
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from accounts.models import Business, BusinessMembership
from inventory.models import (
    Category, Product, Supplier, Warehouse, Stock, StockProduct,
    BusinessWarehouse, StoreFrontInventory, StoreFront, BusinessStoreFront,
    TransferRequest, TransferRequestLineItem
)
from inventory.stock_adjustments import StockAdjustment
from sales.models import Sale, SaleItem, Customer

User = get_user_model()


def setup_test_data():
    """Create test business and product."""
    print("\n" + "="*70)
    print("SETUP: Creating test data...")
    print("="*70)
    
    # Create user and business
    user = User.objects.create_user(
        email='test@example.com',
        password='testpass123',
        name='Test User'
    )
    user.account_type = User.ACCOUNT_OWNER
    user.is_active = True
    user.save()
    
    business = Business.objects.create(
        owner=user,
        name='Test Business',
        tin='TIN123',
        email='biz@test.com',
        address='123 Test St'
    )
    
    # Create product
    category = Category.objects.create(name='Electronics')
    product = Product.objects.create(
        business=business,
        name='Test Product',
        sku='TEST-001',
        category=category
    )
    
    # Create warehouse
    warehouse = Warehouse.objects.create(name='Main Warehouse', location='Location A')
    BusinessWarehouse.objects.create(business=business, warehouse=warehouse)
    
    # Create stock
    stock = Stock.objects.create(warehouse=warehouse, description='Test batch')
    supplier = Supplier.objects.create(
        business=business,
        name='Test Supplier',
        email='supplier@test.com'
    )
    
    print(f"✅ Created business: {business.name}")
    print(f"✅ Created product: {product.name}")
    print(f"✅ Created warehouse: {warehouse.name}")
    
    return {
        'user': user,
        'business': business,
        'product': product,
        'warehouse': warehouse,
        'stock': stock,
        'supplier': supplier,
        'category': category
    }


def test_can_edit_on_creation():
    """TEST 1: User CAN edit quantity immediately after creation (no movements)."""
    print("\n" + "="*70)
    print("TEST 1: Can edit quantity BEFORE any movements")
    print("="*70)
    
    data = setup_test_data()
    
    # Create stock product with initial quantity
    stock_product = StockProduct.objects.create(
        stock=data['stock'],
        product=data['product'],
        supplier=data['supplier'],
        quantity=100,  # Initial intake
        unit_cost=Decimal('10.00'),
        retail_price=Decimal('15.00')
    )
    print(f"✅ Created StockProduct with quantity=100")
    
    # User realizes mistake, edits to 105
    try:
        stock_product.quantity = 105
        stock_product.save()
        print(f"✅ SUCCESS: Edited quantity from 100 to 105 (NO movements yet)")
        print(f"   Current quantity: {stock_product.quantity}")
        
        # Verify change persisted
        stock_product.refresh_from_db()
        assert stock_product.quantity == 105, "Quantity not saved!"
        print(f"✅ VERIFIED: Quantity persisted in database: {stock_product.quantity}")
        
    except ValidationError as e:
        print(f"❌ FAILED: Should allow edit before movements!")
        print(f"   Error: {e}")
        return False
    
    print("✅ TEST 1 PASSED: Can edit before movements")
    return True


def test_cannot_edit_after_adjustment():
    """TEST 2: User CANNOT edit quantity after creating an adjustment."""
    print("\n" + "="*70)
    print("TEST 2: Cannot edit quantity AFTER adjustment created")
    print("="*70)
    
    data = setup_test_data()
    
    # Create stock product
    stock_product = StockProduct.objects.create(
        stock=data['stock'],
        product=data['product'],
        supplier=data['supplier'],
        quantity=100,
        unit_cost=Decimal('10.00'),
        retail_price=Decimal('15.00')
    )
    print(f"✅ Created StockProduct with quantity=100")
    
    # Create a PENDING adjustment (movement occurred!)
    adjustment = StockAdjustment.objects.create(
        business=data['business'],
        stock_product=stock_product,
        adjustment_type='DAMAGE',
        quantity=-5,
        unit_cost=Decimal('10.00'),
        total_cost=Decimal('50.00'),
        reason='Test damage',
        created_by=data['user'],
        status='PENDING',  # Even PENDING blocks edits!
        requires_approval=True
    )
    print(f"✅ Created PENDING adjustment: -5 units (damage)")
    
    # Try to edit quantity - should FAIL
    try:
        stock_product.quantity = 105
        stock_product.save()
        print(f"❌ FAILED: Should NOT allow edit after adjustment!")
        return False
        
    except ValidationError as e:
        print(f"✅ SUCCESS: Edit blocked as expected")
        print(f"   Error message: {e.message}")
        assert '1 stock adjustment(s)' in str(e), "Wrong error message!"
        print(f"✅ VERIFIED: Error mentions the adjustment blocking the edit")
    
    print("✅ TEST 2 PASSED: Cannot edit after adjustment")
    return True


def test_cannot_edit_after_transfer():
    """TEST 3: User CANNOT edit quantity after creating a transfer request."""
    print("\n" + "="*70)
    print("TEST 3: Cannot edit quantity AFTER transfer request created")
    print("="*70)
    
    data = setup_test_data()
    
    # Create stock product
    stock_product = StockProduct.objects.create(
        stock=data['stock'],
        product=data['product'],
        supplier=data['supplier'],
        quantity=100,
        unit_cost=Decimal('10.00'),
        retail_price=Decimal('15.00')
    )
    print(f"✅ Created StockProduct with quantity=100")
    
    # Create storefront
    storefront = StoreFront.objects.create(
        user=data['user'],
        name='Test Storefront',
        location='Downtown'
    )
    BusinessStoreFront.objects.create(business=data['business'], storefront=storefront)
    
    # Create transfer request
    transfer = TransferRequest.objects.create(
        business=data['business'],
        storefront=storefront,
        requested_by=data['user'],
        status='NEW',
        priority='MEDIUM'
    )
    TransferRequestLineItem.objects.create(
        request=transfer,
        product=data['product'],
        requested_quantity=10,
        notes='Test transfer'
    )
    print(f"✅ Created PENDING transfer request: 10 units to storefront")
    
    # Try to edit quantity - should FAIL
    try:
        stock_product.quantity = 105
        stock_product.save()
        print(f"❌ FAILED: Should NOT allow edit after transfer!")
        return False
        
    except ValidationError as e:
        print(f"✅ SUCCESS: Edit blocked as expected")
        print(f"   Error message: {e.message}")
        assert 'transfer request' in str(e).lower(), "Wrong error message!"
        print(f"✅ VERIFIED: Error mentions the transfer blocking the edit")
    
    print("✅ TEST 3 PASSED: Cannot edit after transfer")
    return True


def test_cannot_edit_after_storefront_allocation():
    """TEST 4: User CANNOT edit quantity after storefront allocation exists."""
    print("\n" + "="*70)
    print("TEST 4: Cannot edit quantity AFTER storefront allocation")
    print("="*70)
    
    data = setup_test_data()
    
    # Create stock product
    stock_product = StockProduct.objects.create(
        stock=data['stock'],
        product=data['product'],
        supplier=data['supplier'],
        quantity=100,
        unit_cost=Decimal('10.00'),
        retail_price=Decimal('15.00')
    )
    print(f"✅ Created StockProduct with quantity=100")
    
    # Create storefront
    storefront = StoreFront.objects.create(
        user=data['user'],
        name='Test Storefront',
        location='Downtown'
    )
    BusinessStoreFront.objects.create(business=data['business'], storefront=storefront)
    
    # Allocate to storefront
    StoreFrontInventory.objects.create(
        storefront=storefront,
        product=data['product'],
        quantity=20
    )
    print(f"✅ Created storefront allocation: 20 units")
    
    # Try to edit quantity - should FAIL
    try:
        stock_product.quantity = 105
        stock_product.save()
        print(f"❌ FAILED: Should NOT allow edit after storefront allocation!")
        return False
        
    except ValidationError as e:
        print(f"✅ SUCCESS: Edit blocked as expected")
        print(f"   Error message: {e.message}")
        assert 'storefront allocation' in str(e).lower(), "Wrong error message!"
        print(f"✅ VERIFIED: Error mentions the storefront allocation blocking the edit")
    
    print("✅ TEST 4 PASSED: Cannot edit after storefront allocation")
    return True


def test_cannot_edit_after_sale():
    """TEST 5: User CANNOT edit quantity after a sale transaction exists."""
    print("\n" + "="*70)
    print("TEST 5: Cannot edit quantity AFTER sale transaction")
    print("="*70)
    
    data = setup_test_data()
    
    # Create stock product
    stock_product = StockProduct.objects.create(
        stock=data['stock'],
        product=data['product'],
        supplier=data['supplier'],
        quantity=100,
        unit_cost=Decimal('10.00'),
        retail_price=Decimal('15.00')
    )
    print(f"✅ Created StockProduct with quantity=100")
    
    # Create storefront
    storefront = StoreFront.objects.create(
        user=data['user'],
        name='Test Storefront',
        location='Downtown'
    )
    BusinessStoreFront.objects.create(business=data['business'], storefront=storefront)
    
    # Create customer and sale
    customer = Customer.objects.create(
        business=data['business'],
        name='Test Customer',
        created_by=data['user']
    )
    sale = Sale.objects.create(
        business=data['business'],
        storefront=storefront,
        user=data['user'],
        customer=customer,
        status='DRAFT',  # Even DRAFT blocks edits!
        payment_type='CASH'
    )
    SaleItem.objects.create(
        sale=sale,
        product=data['product'],
        stock=data['stock'],
        stock_product=stock_product,
        quantity=Decimal('2'),
        unit_price=Decimal('15.00')
    )
    print(f"✅ Created DRAFT sale: 2 units")
    
    # Try to edit quantity - should FAIL
    try:
        stock_product.quantity = 105
        stock_product.save()
        print(f"❌ FAILED: Should NOT allow edit after sale!")
        return False
        
    except ValidationError as e:
        print(f"✅ SUCCESS: Edit blocked as expected")
        print(f"   Error message: {e.message}")
        assert 'sale transaction' in str(e).lower(), "Wrong error message!"
        print(f"✅ VERIFIED: Error mentions the sale blocking the edit")
    
    print("✅ TEST 5 PASSED: Cannot edit after sale")
    return True


def run_all_tests():
    """Run all test scenarios."""
    print("\n" + "="*70)
    print("STOCK PRODUCT QUANTITY EDIT RULES - VALIDATION TESTS")
    print("="*70)
    print("\nRequirement: quantity can ONLY be edited BEFORE any stock movements")
    print("After ANY movement (adjustment/transfer/allocation/sale), it's LOCKED")
    
    results = []
    
    # Clean database before each test to avoid unique constraint violations
    from django.core.management import call_command
    
    # Test 1: CAN edit before movements
    print("\n🧹 Cleaning database...")
    call_command('flush', '--noinput')
    results.append(("CAN edit before movements", test_can_edit_on_creation()))
    
    # Test 2-5: CANNOT edit after movements
    print("\n🧹 Cleaning database...")
    call_command('flush', '--noinput')
    results.append(("CANNOT edit after adjustment", test_cannot_edit_after_adjustment()))
    
    print("\n🧹 Cleaning database...")
    call_command('flush', '--noinput')
    results.append(("CANNOT edit after transfer", test_cannot_edit_after_transfer()))
    
    print("\n🧹 Cleaning database...")
    call_command('flush', '--noinput')
    results.append(("CANNOT edit after storefront allocation", test_cannot_edit_after_storefront_allocation()))
    
    print("\n🧹 Cleaning database...")
    call_command('flush', '--noinput')
    results.append(("CANNOT edit after sale", test_cannot_edit_after_sale()))
    
    # Summary
    print("\n" + "="*70)
    print("TEST RESULTS SUMMARY")
    print("="*70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print("\n" + "="*70)
    print(f"TOTAL: {passed}/{total} tests passed")
    print("="*70)
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Signal enforcement is correct.")
        print("\nThe requirement is implemented correctly:")
        print("  ✅ Users CAN edit quantity during intake (before movements)")
        print("  ✅ Users CANNOT edit quantity after ANY movement occurs")
        print("  ✅ Signal blocks edits with clear error messages")
    else:
        print(f"\n❌ {total - passed} test(s) failed!")
        print("Signal enforcement does NOT match the requirement.")
    
    return passed == total


if __name__ == '__main__':
    # Clean database before tests
    from django.core.management import call_command
    print("Cleaning test database...")
    call_command('flush', '--noinput')
    
    # Run tests
    success = run_all_tests()
    
    sys.exit(0 if success else 1)
