"""
Test Stock Data Integrity Signals

This script verifies that all stock integrity signals are working correctly:
1. prevent_quantity_edit_after_movements - Locks StockProduct.quantity after movements
2. validate_adjustment_wont_cause_negative_stock - Prevents negative available stock
3. validate_transfer_has_sufficient_stock - Validates warehouse availability
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

import uuid
from decimal import Decimal
from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models
from django.utils import timezone

from accounts.models import Business, BusinessMembership
from inventory.models import (
    Category, Product, Supplier, Warehouse, Stock, StockProduct,
    StoreFront, StoreFrontInventory, BusinessWarehouse, BusinessStoreFront,
    TransferRequest, TransferRequestLineItem
)
from inventory.stock_adjustments import StockAdjustment
from sales.models import Sale, SaleItem, Customer
from sales.serializers import SaleSerializer

User = get_user_model()


class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(80)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*80}{Colors.ENDC}\n")


def print_test(name):
    print(f"{Colors.OKBLUE}TEST:{Colors.ENDC} {name}")


def print_success(message):
    print(f"  {Colors.OKGREEN}✓{Colors.ENDC} {message}")


def print_failure(message):
    print(f"  {Colors.FAIL}✗{Colors.ENDC} {message}")


def print_info(message):
    print(f"  {Colors.OKCYAN}ℹ{Colors.ENDC} {message}")


def generate_reference(prefix: str) -> str:
    """Generate a unique reference string with the given prefix."""
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def adjustment_kwargs(env, stock_product, *, quantity, reference, adjustment_type='DAMAGE', reason=None):
    """Build kwargs for creating StockAdjustment records consistently."""
    return {
        'business': env['business'],
        'stock_product': stock_product,
        'adjustment_type': adjustment_type,
        'quantity': quantity,
        'unit_cost': stock_product.unit_cost,
        'reason': reason or f'TEST: {adjustment_type}',
        'reference_number': reference,
        'status': 'COMPLETED',
        'created_by': env['owner'],
        'approved_by': env['owner'],
        'requires_approval': False,
    }


def create_stock_adjustment(env, stock_product, *, quantity, reference, adjustment_type='DAMAGE', reason=None):
    """Create a stock adjustment with standard defaults."""
    return StockAdjustment.objects.create(
        **adjustment_kwargs(
            env,
            stock_product,
            quantity=quantity,
            reference=reference,
            adjustment_type=adjustment_type,
            reason=reason,
        )
    )


def calculate_available_stock(stock_product):
    """Mirror signal calculation for available stock."""
    from inventory.models import StoreFrontInventory
    from sales.models import SaleItem

    adjustments_sum = stock_product.adjustments.filter(
        status='COMPLETED'
    ).aggregate(total=models.Sum('quantity'))['total'] or 0

    transferred = StoreFrontInventory.objects.filter(
        product=stock_product.product
    ).aggregate(total=models.Sum('quantity'))['total'] or 0

    sold = SaleItem.objects.filter(
        product=stock_product.product,
        sale__status='COMPLETED'
    ).aggregate(total=models.Sum('quantity'))['total'] or 0

    return stock_product.quantity + adjustments_sum - transferred - sold


class DummyRequest:
    """Minimal request-like object for serializer validation."""

    def __init__(self, user):
        self.user = user
        self.META = {}


def cleanup_test_data():
    """Clean up any existing test data"""
    print_info("Cleaning up existing test data...")
    
    # Delete in correct order to avoid foreign key issues
    # First delete SaleItems, then Sales
    SaleItem.objects.filter(sale__receipt_number__startswith='TEST-').delete()
    Sale.objects.filter(receipt_number__startswith='TEST-').delete()
    
    # Then adjustments and inventory
    StockAdjustment.objects.filter(reference_number__startswith='TEST-').delete()
    StoreFrontInventory.objects.filter(product__sku__startswith='TEST-').delete()
    TransferRequestLineItem.objects.filter(request__notes__startswith='TEST').delete()
    TransferRequest.objects.filter(notes__startswith='TEST').delete()
    
    # Stock products and stock batches
    StockProduct.objects.filter(product__sku__startswith='TEST-').delete()
    Stock.objects.filter(description__startswith='TEST').delete()
    
    # Finally products and related
    Product.objects.filter(sku__startswith='TEST-').delete()
    Supplier.objects.filter(name__startswith='Test').delete()
    Category.objects.filter(name__startswith='Test').delete()
    Customer.objects.filter(name__startswith='Test').delete()
    
    print_success("Test data cleaned up")


def setup_test_environment():
    """Set up test users, business, warehouse, and storefront"""
    print_header("SETTING UP TEST ENVIRONMENT")
    
    # Get or create test users
    owner = User.objects.filter(email='juliustetteh@gmail.com').first()
    if not owner:
        print_failure("Owner user not found!")
        return None
    print_success(f"Owner: {owner.email}")
    
    employee = User.objects.filter(email='mikedit009@gmail.com').first()
    if not employee:
        print_failure("Employee user not found!")
        return None
    print_success(f"Employee: {employee.email}")
    
    # Get or create business
    business = Business.objects.filter(owner=owner).first()
    if not business:
        business = Business.objects.create(
            owner=owner,
            name="Test Electronics Store",
            tin="TEST123456789",
            email="business@test.com",
            address="123 Test Street"
        )
        print_success(f"Created business: {business.name}")
    else:
        print_success(f"Using existing business: {business.name}")
    
    # Ensure employee is a member
    membership, created = BusinessMembership.objects.get_or_create(
        business=business,
        user=employee,
        defaults={'role': 'STAFF', 'is_active': True}
    )
    if created:
        print_success(f"Added {employee.email} as staff member")
    else:
        print_info(f"{employee.email} already a member")
    
    # Create warehouse
    warehouse = Warehouse.objects.filter(name='Main Warehouse').first()
    if not warehouse:
        warehouse = Warehouse.objects.create(
            name='Main Warehouse',
            location='Main Storage Facility',
            manager=owner
        )
        print_success(f"Created warehouse: {warehouse.name}")
        
        # Link warehouse to business
        BusinessWarehouse.objects.create(
            business=business,
            warehouse=warehouse,
            is_active=True
        )
    else:
        print_success(f"Using existing warehouse: {warehouse.name}")
        # Ensure warehouse is linked to our test business
        if not BusinessWarehouse.objects.filter(business=business, warehouse=warehouse).exists():
            # Warehouse is linked to another business, create a new test warehouse
            warehouse = Warehouse.objects.create(
                name=f'Test Warehouse {timezone.now().timestamp()}',
                location='Test Storage Facility',
                manager=owner
            )
            BusinessWarehouse.objects.create(
                business=business,
                warehouse=warehouse,
                is_active=True
            )
            print_success(f"Created new test warehouse: {warehouse.name}")
    
    # Create storefront
    storefront = StoreFront.objects.filter(name='Main Store').first()
    if not storefront:
        storefront = StoreFront.objects.create(
            user=owner,
            name='Main Store',
            location='123 Main Street',
            manager=employee
        )
        print_success(f"Created storefront: {storefront.name}")
        
        # Link storefront to business
        BusinessStoreFront.objects.create(
            business=business,
            storefront=storefront,
            is_active=True
        )
    else:
        print_success(f"Using existing storefront: {storefront.name}")
        # Ensure storefront is linked to our test business
        if not BusinessStoreFront.objects.filter(business=business, storefront=storefront).exists():
            # Storefront is linked to another business, create a new test storefront
            storefront = StoreFront.objects.create(
                user=owner,
                name=f'Test Store {timezone.now().timestamp()}',
                location='Test Store Location',
                manager=employee
            )
            BusinessStoreFront.objects.create(
                business=business,
                storefront=storefront,
                is_active=True
            )
            print_success(f"Created new test storefront: {storefront.name}")
    
    # Create test category
    category = Category.objects.get_or_create(
        name='Test Electronics',
        defaults={'description': 'Test electronics products'}
    )[0]
    
    # Create test supplier
    supplier = Supplier.objects.get_or_create(
        business=business,
        name='Test Supplier Inc',
        defaults={
            'contact_person': 'John Doe',
            'email': 'supplier@test.com',
            'phone_number': '+1234567890'
        }
    )[0]
    
    return {
        'owner': owner,
        'employee': employee,
        'business': business,
        'warehouse': warehouse,
        'storefront': storefront,
        'category': category,
        'supplier': supplier
    }


def test_1_prevent_quantity_edit_after_adjustment(env):
    """Test that quantity cannot be edited after creating a stock adjustment"""
    print_header("TEST 1: Prevent Quantity Edit After Adjustment")
    
    print_test("Creating product with initial stock...")
    
    # Create product
    product = Product.objects.create(
        business=env['business'],
        name='TEST Laptop',
        sku='TEST-LAP-001',
        category=env['category'],
        unit='pcs',
        is_active=True
    )
    
    # Create stock batch
    stock = Stock.objects.create(
        arrival_date=date.today(),
        description='TEST Initial Stock Batch'
    )
    
    # Create stock product
    stock_product = StockProduct.objects.create(
        stock=stock,
        warehouse=env['warehouse'],
        product=product,
        supplier=env['supplier'],
        quantity=100,
        unit_cost=Decimal('500.00'),
        retail_price=Decimal('750.00'),
        wholesale_price=Decimal('650.00')
    )
    
    print_success(f"Created {product.name} with {stock_product.quantity} units")
    print_info(f"StockProduct ID: {stock_product.id}")
    
    # Try to edit quantity BEFORE any movements (should work)
    print_test("Attempting to edit quantity before any movements...")
    try:
        stock_product.quantity = 110
        stock_product.save()
        print_success("✓ Quantity edit allowed before movements (Expected)")
        stock_product.quantity = 100  # Reset
        stock_product.save()
    except ValidationError as e:
        print_failure(f"✗ Quantity edit blocked before movements (Unexpected): {e}")
        return False
    
    # Create a stock adjustment
    print_test("Creating stock adjustment...")
    adjustment = create_stock_adjustment(
        env,
        stock_product,
        quantity=-5,
        reference='TEST-ADJ-001',
        adjustment_type='DAMAGE',
        reason='TEST: Damaged during inspection'
    )
    print_success(f"Created adjustment: {adjustment.adjustment_type} of {adjustment.quantity} units")
    
    # Try to edit quantity AFTER adjustment (should fail)
    print_test("Attempting to edit quantity after adjustment...")
    try:
        stock_product.quantity = 110
        stock_product.save()
        print_failure("✗ Quantity edit allowed after movements (INTEGRITY VIOLATION!)")
        return False
    except ValidationError as e:
        print_success(f"✓ Quantity edit blocked after movements (Expected)")
        print_info(f"Error message: {str(e)}")
        return True


def test_2_prevent_negative_stock_via_adjustment(env):
    """Test that adjustments cannot cause negative available stock"""
    print_header("TEST 2: Prevent Negative Stock via Adjustment")
    
    print_test("Creating product with limited stock...")
    
    # Create product
    product = Product.objects.create(
        business=env['business'],
        name='TEST Mouse',
        sku='TEST-MOU-001',
        category=env['category'],
        unit='pcs',
        is_active=True
    )
    
    # Create stock batch
    stock = Stock.objects.create(
        arrival_date=date.today(),
        description='TEST Stock Batch'
    )
    
    # Create stock product with only 10 units
    stock_product = StockProduct.objects.create(
        stock=stock,
        warehouse=env['warehouse'],
        product=product,
        supplier=env['supplier'],
        quantity=10,
        unit_cost=Decimal('15.00'),
        retail_price=Decimal('25.00'),
        wholesale_price=Decimal('20.00')
    )
    
    print_success(f"Created {product.name} with {stock_product.quantity} units")
    
    # Try to create adjustment that would make stock negative (should fail)
    print_test("Attempting to create adjustment for -15 units (more than available)...")
    try:
        StockAdjustment.objects.create(
            **adjustment_kwargs(
                env,
                stock_product,
                quantity=-15,
                reference='TEST-ADJ-002',
                reason='TEST: Attempting to exceed available stock'
            )
        )
        print_failure("✗ Negative stock adjustment allowed (INTEGRITY VIOLATION!)")
        return False
    except ValidationError as e:
        print_success("✓ Negative stock adjustment blocked (Expected)")
        print_info(f"Error message: {str(e)}")
    
    # Try valid adjustment (should work)
    print_test("Attempting to create valid adjustment for -5 units...")
    try:
        create_stock_adjustment(
            env,
            stock_product,
            quantity=-5,
            reference='TEST-ADJ-003',
            reason='TEST: Valid adjustment'
        )
        print_success(f"✓ Valid adjustment created (Expected)")
        available_now = calculate_available_stock(stock_product)
        print_info(f"Calculated available stock after adjustment: {available_now} units")
        return True
    except ValidationError as e:
        print_failure(f"✗ Valid adjustment blocked (Unexpected): {e}")
        return False


def test_3_prevent_overselling(env):
    """Test that sales cannot exceed available storefront inventory"""
    print_header("TEST 3: Prevent Overselling at Storefront")
    
    print_test("Creating product with storefront inventory...")
    
    # Create product
    product = Product.objects.create(
        business=env['business'],
        name='TEST Keyboard',
        sku='TEST-KEY-001',
        category=env['category'],
        unit='pcs',
        is_active=True
    )
    
    # Create stock batch
    stock = Stock.objects.create(
        arrival_date=date.today(),
        description='TEST Stock Batch'
    )
    
    # Create stock product
    stock_product = StockProduct.objects.create(
        stock=stock,
        warehouse=env['warehouse'],
        product=product,
        supplier=env['supplier'],
        quantity=50,
        unit_cost=Decimal('30.00'),
        retail_price=Decimal('50.00'),
        wholesale_price=Decimal('40.00')
    )
    
    # Transfer to storefront
    storefront_inventory = StoreFrontInventory.objects.create(
        storefront=env['storefront'],
        product=product,
        quantity=20  # Only 20 units at storefront
    )
    
    print_success(f"Created {product.name} with {storefront_inventory.quantity} units at storefront")
    
    # Create customer
    customer = Customer.objects.create(
        business=env['business'],
        name='Test Customer',
        email='customer@test.com'
    )
    
    # Try to create sale for more than available (should fail when completing)
    print_test("Attempting to sell 25 units (more than the 20 available)...")
    try:
        sale = Sale.objects.create(
            business=env['business'],
            storefront=env['storefront'],
            customer=customer,
            user=env['employee'],  # Changed from cashier to user
            payment_type='CASH',
            receipt_number='TEST-SALE-001',  # Changed from reference
            status='DRAFT'
        )
        
        sale_item = SaleItem.objects.create(
            sale=sale,
            product=product,
            quantity=25,  # More than available
            unit_price=Decimal('50.00'),
            total_price=Decimal('1250.00')
        )
        
        # Try to complete the sale
        sale.complete_sale()
        
        print_failure("✗ Overselling allowed (INTEGRITY VIOLATION!)")
        return False
        
    except (ValidationError, ValueError) as e:
        print_success("✓ Overselling blocked (Expected)")
        print_info(f"Error: {str(e)}")
        return True


def test_4_multiple_adjustments_calculation(env):
    """Test that multiple adjustments are calculated correctly"""
    print_header("TEST 4: Multiple Adjustments Calculation")
    
    print_test("Creating product with multiple adjustments...")
    
    # Create product
    product = Product.objects.create(
        business=env['business'],
        name='TEST Monitor',
        sku='TEST-MON-001',
        category=env['category'],
        unit='pcs',
        is_active=True
    )
    
    # Create stock batch
    stock = Stock.objects.create(
        arrival_date=date.today(),
        description='TEST Stock Batch'
    )
    
    # Create stock product
    stock_product = StockProduct.objects.create(
        stock=stock,
        warehouse=env['warehouse'],
        product=product,
        supplier=env['supplier'],
        quantity=100,
        unit_cost=Decimal('200.00'),
        retail_price=Decimal('350.00'),
        wholesale_price=Decimal('300.00')
    )
    
    print_success(f"Created {product.name} with initial quantity: {stock_product.quantity}")
    
    # Create multiple adjustments
    adjustments = [
        ('DAMAGE', -5, 'TEST-ADJ-004'),
        ('FOUND', 3, 'TEST-ADJ-005'),
        ('THEFT', -2, 'TEST-ADJ-006'),
        ('DAMAGE', -4, 'TEST-ADJ-007'),
    ]
    
    expected_available = stock_product.quantity
    
    for adj_type, quantity, ref in adjustments:
        print_test(f"Creating {adj_type} adjustment for {quantity} units...")
        create_stock_adjustment(
            env,
            stock_product,
            quantity=quantity,
            reference=ref,
            adjustment_type=adj_type
        )
        expected_available += quantity
        print_success(f"Created {adj_type} adjustment")
        print_info(f"Expected available: {expected_available}")

    calculated_available = calculate_available_stock(stock_product)
    print_info(f"Calculated available stock after adjustments: {calculated_available} units")
    
    # Try to create an adjustment that would exceed available
    print_test(f"Attempting adjustment that would exceed available ({expected_available} units)...")
    try:
        StockAdjustment.objects.create(
            **adjustment_kwargs(
                env,
                stock_product,
                quantity=-(expected_available + 1),
                reference='TEST-ADJ-008',
                reason='TEST: Exceeding available'
            )
        )
        print_failure("✗ Excessive adjustment allowed (INTEGRITY VIOLATION!)")
        return False
    except ValidationError as e:
        print_success("✓ Excessive adjustment blocked (Expected)")
        print_info(f"Error: {str(e)}")
        
        # Verify the calculation in the error message
        if str(expected_available) in str(e):
            print_success(f"✓ Error message shows correct available quantity: {expected_available}")
            return True
        else:
            print_failure(f"✗ Error message doesn't show correct available quantity")
            return False


def test_5_stock_adjustment_required_fields(env):
    """Ensure stock adjustments enforce required financial fields."""
    print_header("TEST 5: Stock Adjustment Required Fields")

    product = Product.objects.create(
        business=env['business'],
        name='TEST Adjustment Product',
        sku='TEST-ADJ-REQ-001',
        category=env['category'],
        unit='pcs',
        is_active=True
    )

    stock = Stock.objects.create(
        arrival_date=date.today(),
        description='TEST Adjustment Requirement Batch'
    )

    stock_product = StockProduct.objects.create(
        stock=stock,
        warehouse=env['warehouse'],
        product=product,
        supplier=env['supplier'],
        quantity=25,
        unit_cost=Decimal('12.50'),
        retail_price=Decimal('20.00'),
        wholesale_price=Decimal('16.00')
    )

    print_test("Attempting to create adjustment without unit_cost (should fail)...")
    try:
        StockAdjustment.objects.create(
            business=env['business'],
            stock_product=stock_product,
            adjustment_type='DAMAGE',
            quantity=-3,
            reason='TEST: Missing unit cost',
            reference_number='TEST-ADJ-MISSING',
            status='COMPLETED',
            created_by=env['owner'],
            approved_by=env['owner'],
            requires_approval=False
        )
        print_failure("✗ Adjustment created without unit_cost (should fail)")
        return False
    except IntegrityError as e:
        print_success("✓ Database blocked adjustment without unit_cost (Expected)")
        print_info(f"Error: {str(e).split('DETAIL:')[0].strip()}")
    except ValidationError as e:
        print_success("✓ Validation prevented adjustment without unit_cost (Expected)")
        print_info(f"Error: {e}")
    except Exception as e:
        print_failure(f"✗ Unexpected exception type: {type(e).__name__} - {e}")
        return False

    print_test("Creating valid adjustment with unit_cost...")
    try:
        create_stock_adjustment(
            env,
            stock_product,
            quantity=-2,
            reference='TEST-ADJ-VALID-REQ'
        )
        print_success("✓ Adjustment created successfully when unit_cost provided")
        return True
    except Exception as e:
        print_failure(f"✗ Failed to create valid adjustment: {e}")
        return False


def test_6_transfer_request_validation(env):
    """Validate warehouse stock check when fulfilling transfer requests."""
    print_header("TEST 6: Transfer Request Stock Validation")

    product = Product.objects.create(
        business=env['business'],
        name='TEST Transfer Product',
        sku='TEST-TRF-001',
        category=env['category'],
        unit='pcs',
        is_active=True
    )

    stock = Stock.objects.create(
        arrival_date=date.today(),
        description='TEST Transfer Batch'
    )

    StockProduct.objects.create(
        stock=stock,
        warehouse=env['warehouse'],
        product=product,
        supplier=env['supplier'],
        quantity=80,
        unit_cost=Decimal('18.00'),
        retail_price=Decimal('30.00'),
        wholesale_price=Decimal('24.00')
    )

    transfer_request = TransferRequest.objects.create(
        business=env['business'],
        storefront=env['storefront'],
        requested_by=env['employee'],
        status=TransferRequest.STATUS_ASSIGNED,
        priority=TransferRequest.PRIORITY_HIGH,
        notes='TEST Transfer Request - Validation'
    )

    line_item = TransferRequestLineItem.objects.create(
        request=transfer_request,
        product=product,
        requested_quantity=90
    )

    print_test("Attempting to fulfill request exceeding available stock...")
    try:
        transfer_request.status = TransferRequest.STATUS_FULFILLED
        transfer_request.save()
        print_failure("✗ Transfer request fulfilled despite insufficient stock")
        return False
    except ValidationError as e:
        print_success("✓ Transfer request blocked (Expected)")
        print_info(f"Error: {e}")
        transfer_request.refresh_from_db()

    print_test("Attempting to fulfill request within available stock...")
    line_item.refresh_from_db()
    line_item.requested_quantity = 40
    line_item.save(update_fields=['requested_quantity', 'updated_at'])

    transfer_request.status = TransferRequest.STATUS_FULFILLED
    try:
        transfer_request.save()
        print_success("✓ Transfer request fulfilled when stock is sufficient")
        return True
    except ValidationError as e:
        print_failure(f"✗ Transfer request still blocked: {e}")
        return False


def test_7_credit_sale_validation(env):
    """Ensure credit sale validations enforce customer rules."""
    print_header("TEST 7: Credit Sale Validation")

    request = DummyRequest(env['employee'])

    customer = Customer.objects.create(
        business=env['business'],
        name='Test Credit Customer',
        email='credit@test.com',
        phone=f"+233{uuid.uuid4().hex[:9]}",
        credit_limit=Decimal('1000.00'),
        outstanding_balance=Decimal('800.00'),
        created_by=env['owner']
    )

    base_payload = {
        'storefront': str(env['storefront'].id),
        'payment_type': 'CREDIT',
        'subtotal': '300.00',
        'discount_amount': '0.00',
        'tax_amount': '0.00',
        'total_amount': '300.00',
        'amount_paid': '0.00',
        'amount_refunded': '0.00',
        'amount_due': '300.00',
        'status': 'DRAFT'
    }

    print_test("Validating credit sale without customer...")
    serializer = SaleSerializer(data=base_payload, context={'request': request})
    if serializer.is_valid():
        print_failure("✗ Credit sale without customer passed validation")
        return False
    missing_customer_error = serializer.errors.get('customer', [''])[0]
    print_success("✓ Missing customer blocked (Expected)")
    print_info(f"Error: {missing_customer_error}")

    print_test("Validating credit sale exceeding customer credit limit...")
    payload_with_customer = {
        **base_payload,
        'customer': str(customer.id)
    }
    serializer = SaleSerializer(data=payload_with_customer, context={'request': request})
    if serializer.is_valid():
        print_failure("✗ Credit sale exceeding limit passed validation")
        return False
    credit_error = serializer.errors.get('customer', [''])[0]
    if 'Insufficient credit' not in credit_error:
        print_failure(f"✗ Unexpected credit limit error message: {credit_error}")
        return False
    print_success("✓ Credit limit enforced (Expected)")
    print_info(f"Error: {credit_error}")

    print_test("Validating credit sale within available credit...")
    payload_within_limit = {
        **payload_with_customer,
        'total_amount': '150.00',
        'amount_due': '150.00'
    }
    serializer = SaleSerializer(data=payload_within_limit, context={'request': request})
    if serializer.is_valid():
        print_success("✓ Credit sale within limit validated successfully")
        return True
    print_failure(f"✗ Credit sale within limit failed validation: {serializer.errors}")
    return False


def run_all_tests():
    """Run all integrity tests"""
    print_header("STOCK DATA INTEGRITY TEST SUITE")
    print(f"{Colors.OKCYAN}Testing all stock integrity signals and constraints{Colors.ENDC}\n")
    
    # Clean up first
    cleanup_test_data()
    
    # Setup environment
    env = setup_test_environment()
    if not env:
        print_failure("Failed to set up test environment")
        return
    
    # Run tests
    results = {}
    
    try:
        results['test_1'] = test_1_prevent_quantity_edit_after_adjustment(env)
    except Exception as e:
        print_failure(f"Test 1 crashed: {e}")
        import traceback
        traceback.print_exc()
        results['test_1'] = False
    
    try:
        results['test_2'] = test_2_prevent_negative_stock_via_adjustment(env)
    except Exception as e:
        print_failure(f"Test 2 crashed: {e}")
        import traceback
        traceback.print_exc()
        results['test_2'] = False
    
    try:
        results['test_3'] = test_3_prevent_overselling(env)
    except Exception as e:
        print_failure(f"Test 3 crashed: {e}")
        import traceback
        traceback.print_exc()
        results['test_3'] = False
    
    try:
        results['test_4'] = test_4_multiple_adjustments_calculation(env)
    except Exception as e:
        print_failure(f"Test 4 crashed: {e}")
        import traceback
        traceback.print_exc()
        results['test_4'] = False
    
    try:
        results['test_5'] = test_5_stock_adjustment_required_fields(env)
    except Exception as e:
        print_failure(f"Test 5 crashed: {e}")
        import traceback
        traceback.print_exc()
        results['test_5'] = False

    try:
        results['test_6'] = test_6_transfer_request_validation(env)
    except Exception as e:
        print_failure(f"Test 6 crashed: {e}")
        import traceback
        traceback.print_exc()
        results['test_6'] = False

    try:
        results['test_7'] = test_7_credit_sale_validation(env)
    except Exception as e:
        print_failure(f"Test 7 crashed: {e}")
        import traceback
        traceback.print_exc()
        results['test_7'] = False
    
    # Print summary
    print_header("TEST SUMMARY")
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = f"{Colors.OKGREEN}PASS{Colors.ENDC}" if result else f"{Colors.FAIL}FAIL{Colors.ENDC}"
        print(f"  {test_name}: {status}")
    
    print(f"\n{Colors.BOLD}Results: {passed}/{total} tests passed{Colors.ENDC}")
    
    if passed == total:
        print(f"\n{Colors.OKGREEN}{Colors.BOLD}🎉 ALL TESTS PASSED! Data integrity is working correctly!{Colors.ENDC}\n")
    else:
        print(f"\n{Colors.FAIL}{Colors.BOLD}⚠️  SOME TESTS FAILED! Please review the failures above.{Colors.ENDC}\n")
    
    # Cleanup
    print_info("Cleaning up test data...")
    cleanup_test_data()
    print_success("Cleanup complete")


if __name__ == '__main__':
    run_all_tests()
