"""
Tests for cash on hand calculation based on profit.

This test suite verifies:
1. Total profit calculation from sale items
2. Outstanding credit calculation (profit from unpaid credit sales)
3. Cash on hand = total profit - outstanding credit
4. Additional metrics: total_credit_sales, unpaid_credit_count
5. Enhanced filters: days_outstanding, min/max_amount_due, customer_id
"""

import os
import django
from decimal import Decimal
from datetime import timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from accounts.models import Business, BusinessMembership
from sales.models import Sale, SaleItem, Customer
from inventory.models import Product, Category, StockProduct, StoreFront

User = get_user_model()


def setup_test_data():
    """Create test data for profit calculations."""
    print("Setting up test data...")
    
    # Get or create user
    user, created = User.objects.get_or_create(
        email='test@example.com',
        defaults={'password': 'testpass123'}
    )
    if created:
        user.set_password('testpass123')
        user.save()
    
    # Get or create business
    business, _ = Business.objects.get_or_create(
        name='Test Business',
        defaults={'owner': user}
    )
    
    # Get or create membership
    BusinessMembership.objects.get_or_create(
        user=user,
        business=business,
        defaults={'is_active': True, 'role': 'ADMIN'}
    )
    
    # Get or create storefront
    storefront, _ = StoreFront.objects.get_or_create(
        business_link=business,
        name='Test Store',
        defaults={'location': 'Test Location'}
    )
    
    # Give user access to storefront
    if not user.accessible_storefronts.filter(id=storefront.id).exists():
        user.accessible_storefronts.add(storefront)
    
    # Get or create customers
    customer1, _ = Customer.objects.get_or_create(
        business=business,
        email='customer1@example.com',
        defaults={'name': 'Customer 1'}
    )
    
    customer2, _ = Customer.objects.get_or_create(
        business=business,
        email='customer2@example.com',
        defaults={'name': 'Customer 2'}
    )
    
    # Get or create category
    category, _ = Category.objects.get_or_create(
        business=business,
        name='Test Category'
    )
    
    # Get or create products
    product1, _ = Product.objects.get_or_create(
        business=business,
        sku='PROD-001',
        defaults={
            'category': category,
            'name': 'Product 1',
            'price': Decimal('100.00')
        }
    )
    
    stock_product1, _ = StockProduct.objects.get_or_create(
        product=product1,
        storefront=storefront,
        defaults={
            'cost_price': Decimal('50.00'),
            'quantity': 1000
        }
    )
    
    product2, _ = Product.objects.get_or_create(
        business=business,
        sku='PROD-002',
        defaults={
            'category': category,
            'name': 'Product 2',
            'price': Decimal('75.00')
        }
    )
    
    stock_product2, _ = StockProduct.objects.get_or_create(
        product=product2,
        storefront=storefront,
        defaults={
            'cost_price': Decimal('30.00'),
            'quantity': 1000
        }
    )
    
    return {
        'user': user,
        'business': business,
        'storefront': storefront,
        'customer1': customer1,
        'customer2': customer2,
        'product1': product1,
        'product2': product2,
        'stock_product1': stock_product1,
        'stock_product2': stock_product2
    }


def create_sale(data, payment_type, status, amount_paid=None, customer=None, completed_at=None):
    """Helper to create a sale with items."""
    sale = Sale.objects.create(
        business=data['business'],
        storefront=data['storefront'],
        user=data['user'],
        customer=customer,
        payment_type=payment_type,
        status=status,
        completed_at=completed_at or timezone.now()
    )
    return sale


def add_sale_item(sale, product, stock_product, quantity, unit_price, unit_cost):
    """Helper to add an item to a sale."""
    return SaleItem.objects.create(
        sale=sale,
        product=product,
        stock_product=stock_product,
        quantity=quantity,
        unit_price=unit_price,
        unit_cost=unit_cost
    )


def test_cash_on_hand_no_credit_sales():
    """
    TEST 1: Cash on hand when no credit sales exist
    
    Scenario:
    - All sales are CASH
    - Cash on hand should equal total profit
    - Outstanding credit should be 0
    """
    print("\n" + "="*80)
    print("TEST 1: Cash on hand with no credit sales")
    print("="*80)
    
    # Clear existing data
    Sale.objects.all().delete()
    
    data = setup_test_data()
    
    # Create 2 cash sales
    # Sale 1: 5 x Product 1 @ $100 (cost $50) = $500 revenue, $250 profit
    sale1 = create_sale(data, 'CASH', 'COMPLETED')
    add_sale_item(sale1, data['product1'], data['stock_product1'], 5, 
                  Decimal('100.00'), Decimal('50.00'))
    sale1.calculate_totals()
    sale1.save()
    
    # Sale 2: 10 x Product 2 @ $75 (cost $30) = $750 revenue, $450 profit
    sale2 = create_sale(data, 'CASH', 'COMPLETED')
    add_sale_item(sale2, data['product2'], data['stock_product2'], 10,
                  Decimal('75.00'), Decimal('30.00'))
    sale2.calculate_totals()
    sale2.save()
    
    # Get summary
    client = APIClient()
    client.force_authenticate(user=data['user'])
    response = client.get('/api/sales/summary/')
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    summary = response.json()
    
    print(f"\nTotal Profit: ${summary['total_profit']}")
    print(f"Outstanding Credit: ${summary['outstanding_credit']}")
    print(f"Cash on Hand: ${summary['cash_on_hand']}")
    print(f"Unpaid Credit Count: {summary['unpaid_credit_count']}")
    
    # Expected: 250 + 450 = $700 total profit
    assert Decimal(str(summary['total_profit'])) == Decimal('700.00'), \
        f"Expected total profit $700, got ${summary['total_profit']}"
    
    # No credit sales, so outstanding credit = 0
    assert Decimal(str(summary['outstanding_credit'])) == Decimal('0.00'), \
        f"Expected outstanding credit $0, got ${summary['outstanding_credit']}"
    
    # Cash on hand = total profit (no outstanding credit)
    assert Decimal(str(summary['cash_on_hand'])) == Decimal('700.00'), \
        f"Expected cash on hand $700, got ${summary['cash_on_hand']}"
    
    # No unpaid credit sales
    assert summary['unpaid_credit_count'] == 0, \
        f"Expected 0 unpaid credits, got {summary['unpaid_credit_count']}"
    
    print("✅ TEST 1 PASSED")
    return True


def test_cash_on_hand_with_unpaid_credit():
    """
    TEST 2: Cash on hand with unpaid credit sales
    
    Scenario:
    - Mix of CASH and CREDIT sales
    - Some credit sales are PENDING (no payment)
    - Cash on hand = profit from cash sales only
    - Outstanding credit = profit from pending credit sales
    """
    print("\n" + "="*80)
    print("TEST 2: Cash on hand with unpaid credit sales")
    print("="*80)
    
    # Clear existing data
    Sale.objects.all().delete()
    
    data = setup_test_data()
    
    # Cash Sale: 5 x Product 1 @ $100 (cost $50) = $500 revenue, $250 profit
    cash_sale = create_sale(data, 'CASH', 'COMPLETED')
    add_sale_item(cash_sale, data['product1'], data['stock_product1'], 5,
                  Decimal('100.00'), Decimal('50.00'))
    cash_sale.calculate_totals()
    cash_sale.save()
    
    # Credit Sale (PENDING): 10 x Product 2 @ $75 (cost $30) = $750 revenue, $450 profit
    credit_sale = create_sale(data, 'CREDIT', 'PENDING', customer=data['customer1'])
    add_sale_item(credit_sale, data['product2'], data['stock_product2'], 10,
                  Decimal('75.00'), Decimal('30.00'))
    credit_sale.calculate_totals()
    credit_sale.save()
    
    # Get summary
    client = APIClient()
    client.force_authenticate(user=data['user'])
    response = client.get('/api/sales/summary/')
    
    assert response.status_code == 200
    summary = response.json()
    
    print(f"\nTotal Profit: ${summary['total_profit']}")
    print(f"Outstanding Credit: ${summary['outstanding_credit']}")
    print(f"Cash on Hand: ${summary['cash_on_hand']}")
    print(f"Total Credit Sales: ${summary['total_credit_sales']}")
    print(f"Unpaid Credit Count: {summary['unpaid_credit_count']}")
    
    # Total profit = 250 (cash) + 450 (credit) = $700
    assert Decimal(str(summary['total_profit'])) == Decimal('700.00'), \
        f"Expected total profit $700, got ${summary['total_profit']}"
    
    # Outstanding credit = profit from pending credit sale = $450
    assert Decimal(str(summary['outstanding_credit'])) == Decimal('450.00'), \
        f"Expected outstanding credit $450, got ${summary['outstanding_credit']}"
    
    # Cash on hand = total profit - outstanding credit = 700 - 450 = $250
    assert Decimal(str(summary['cash_on_hand'])) == Decimal('250.00'), \
        f"Expected cash on hand $250, got ${summary['cash_on_hand']}"
    
    # Total credit sales amount = $750
    assert Decimal(str(summary['total_credit_sales'])) == Decimal('750.00'), \
        f"Expected total credit sales $750, got ${summary['total_credit_sales']}"
    
    # 1 unpaid credit sale
    assert summary['unpaid_credit_count'] == 1, \
        f"Expected 1 unpaid credit, got {summary['unpaid_credit_count']}"
    
    print("✅ TEST 2 PASSED")
    return True


def test_cash_on_hand_with_partial_payment():
    """
    TEST 3: Cash on hand with partially paid credit sales
    
    Scenario:
    - Credit sale with partial payment
    - Outstanding credit should still include profit from partial sale
    - Cash on hand excludes profit from partially paid amount
    """
    print("\n" + "="*80)
    print("TEST 3: Cash on hand with partially paid credit")
    print("="*80)
    
    # Clear existing data
    Sale.objects.all().delete()
    
    data = setup_test_data()
    
    # Credit Sale (PARTIAL): 10 x Product 1 @ $100 (cost $50) = $1000 revenue, $500 profit
    # Customer paid $600 out of $1000
    credit_sale = create_sale(data, 'CREDIT', 'PARTIAL', customer=data['customer1'])
    add_sale_item(credit_sale, data['product1'], data['stock_product1'], 10,
                  Decimal('100.00'), Decimal('50.00'))
    credit_sale.calculate_totals()
    credit_sale.amount_paid = Decimal('600.00')
    credit_sale.amount_due = Decimal('400.00')
    credit_sale.save()
    
    # Get summary
    client = APIClient()
    client.force_authenticate(user=data['user'])
    response = client.get('/api/sales/summary/')
    
    assert response.status_code == 200
    summary = response.json()
    
    print(f"\nTotal Profit: ${summary['total_profit']}")
    print(f"Outstanding Credit: ${summary['outstanding_credit']}")
    print(f"Cash on Hand: ${summary['cash_on_hand']}")
    print(f"Total Credit Sales: ${summary['total_credit_sales']}")
    print(f"Unpaid Credit Count: {summary['unpaid_credit_count']}")
    
    # Total profit = $500 (full profit even though partially paid)
    assert Decimal(str(summary['total_profit'])) == Decimal('500.00'), \
        f"Expected total profit $500, got ${summary['total_profit']}"
    
    # Outstanding credit = full $500 (sale is PARTIAL, not COMPLETED)
    assert Decimal(str(summary['outstanding_credit'])) == Decimal('500.00'), \
        f"Expected outstanding credit $500, got ${summary['outstanding_credit']}"
    
    # Cash on hand = 0 (all profit is outstanding)
    assert Decimal(str(summary['cash_on_hand'])) == Decimal('0.00'), \
        f"Expected cash on hand $0, got ${summary['cash_on_hand']}"
    
    # Total credit sales = $400 (amount still due)
    assert Decimal(str(summary['total_credit_sales'])) == Decimal('400.00'), \
        f"Expected total credit sales $400, got ${summary['total_credit_sales']}"
    
    # 1 unpaid credit (PARTIAL counts as unpaid)
    assert summary['unpaid_credit_count'] == 1, \
        f"Expected 1 unpaid credit, got {summary['unpaid_credit_count']}"
    
    print("✅ TEST 3 PASSED")
    return True


def test_days_outstanding_filter():
    """
    TEST 4: Filter sales by days outstanding
    
    Scenario:
    - Create credit sales from different dates
    - Filter for sales outstanding > 30 days
    """
    print("\n" + "="*80)
    print("TEST 4: Days outstanding filter")
    print("="*80)
    
    # Clear existing data
    Sale.objects.all().delete()
    
    data = setup_test_data()
    
    # Recent credit sale (5 days old)
    recent_sale = create_sale(
        data, 'CREDIT', 'PENDING',
        customer=data['customer1'],
        completed_at=timezone.now() - timedelta(days=5)
    )
    add_sale_item(recent_sale, data['product1'], data['stock_product1'], 1,
                  Decimal('100.00'), Decimal('50.00'))
    recent_sale.calculate_totals()
    recent_sale.save()
    
    # Old credit sale (45 days old)
    old_sale = create_sale(
        data, 'CREDIT', 'PENDING',
        customer=data['customer1'],
        completed_at=timezone.now() - timedelta(days=45)
    )
    add_sale_item(old_sale, data['product2'], data['stock_product2'], 1,
                  Decimal('75.00'), Decimal('30.00'))
    old_sale.calculate_totals()
    old_sale.save()
    
    # Get sales outstanding > 30 days
    client = APIClient()
    client.force_authenticate(user=data['user'])
    response = client.get('/api/sales/?days_outstanding=30')
    
    assert response.status_code == 200
    results = response.json()['results']
    
    print(f"\nSales outstanding > 30 days: {len(results)}")
    
    # Should only return the 45-day-old sale
    assert len(results) == 1, f"Expected 1 sale, got {len(results)}"
    assert results[0]['id'] == str(old_sale.id), "Wrong sale returned"
    
    print(f"Sale ID: {results[0]['id']}")
    print(f"Amount Due: ${results[0]['amount_due']}")
    
    print("✅ TEST 4 PASSED")
    return True


def test_amount_range_filters():
    """
    TEST 5: Filter sales by amount due range
    
    Scenario:
    - Create sales with different amounts due
    - Filter by min_amount_due and max_amount_due
    """
    print("\n" + "="*80)
    print("TEST 5: Amount range filters")
    print("="*80)
    
    # Clear existing data
    Sale.objects.all().delete()
    
    data = setup_test_data()
    
    # Small credit sale: $100
    small_sale = create_sale(data, 'CREDIT', 'PENDING', customer=data['customer1'])
    add_sale_item(small_sale, data['product1'], data['stock_product1'], 1,
                  Decimal('100.00'), Decimal('50.00'))
    small_sale.calculate_totals()
    small_sale.save()
    
    # Medium credit sale: $500
    medium_sale = create_sale(data, 'CREDIT', 'PENDING', customer=data['customer1'])
    add_sale_item(medium_sale, data['product1'], data['stock_product1'], 5,
                  Decimal('100.00'), Decimal('50.00'))
    medium_sale.calculate_totals()
    medium_sale.save()
    
    # Large credit sale: $1000
    large_sale = create_sale(data, 'CREDIT', 'PENDING', customer=data['customer2'])
    add_sale_item(large_sale, data['product1'], data['stock_product1'], 10,
                  Decimal('100.00'), Decimal('50.00'))
    large_sale.calculate_totals()
    large_sale.save()
    
    # Test min_amount_due filter (>= $500)
    client = APIClient()
    client.force_authenticate(user=data['user'])
    response = client.get('/api/sales/?min_amount_due=500')
    
    assert response.status_code == 200
    results = response.json()['results']
    
    print(f"\nSales with amount due >= $500: {len(results)}")
    assert len(results) == 2, f"Expected 2 sales, got {len(results)}"
    
    # Test max_amount_due filter (<= $500)
    response = client.get('/api/sales/?max_amount_due=500')
    assert response.status_code == 200
    results = response.json()['results']
    
    print(f"Sales with amount due <= $500: {len(results)}")
    assert len(results) == 2, f"Expected 2 sales, got {len(results)}"
    
    # Test range filter ($200 to $600)
    response = client.get('/api/sales/?min_amount_due=200&max_amount_due=600')
    assert response.status_code == 200
    results = response.json()['results']
    
    print(f"Sales with amount due $200-$600: {len(results)}")
    assert len(results) == 1, f"Expected 1 sale, got {len(results)}"
    assert Decimal(results[0]['amount_due']) == Decimal('500.00'), \
        f"Expected $500 sale, got ${results[0]['amount_due']}"
    
    print("✅ TEST 5 PASSED")
    return True


def test_customer_filter():
    """
    TEST 6: Filter sales by customer
    
    Scenario:
    - Create sales for different customers
    - Filter by customer_id
    """
    print("\n" + "="*80)
    print("TEST 6: Customer filter")
    print("="*80)
    
    # Clear existing data
    Sale.objects.all().delete()
    
    data = setup_test_data()
    
    # Sales for customer 1
    for i in range(3):
        sale = create_sale(data, 'CREDIT', 'PENDING', customer=data['customer1'])
        add_sale_item(sale, data['product1'], data['stock_product1'], 1,
                      Decimal('100.00'), Decimal('50.00'))
        sale.calculate_totals()
        sale.save()
    
    # Sales for customer 2
    for i in range(2):
        sale = create_sale(data, 'CREDIT', 'PENDING', customer=data['customer2'])
        add_sale_item(sale, data['product2'], data['stock_product2'], 1,
                      Decimal('75.00'), Decimal('30.00'))
        sale.calculate_totals()
        sale.save()
    
    # Filter by customer 1
    client = APIClient()
    client.force_authenticate(user=data['user'])
    response = client.get(f'/api/sales/?customer_id={data["customer1"].id}')
    
    assert response.status_code == 200
    results = response.json()['results']
    
    print(f"\nSales for Customer 1: {len(results)}")
    assert len(results) == 3, f"Expected 3 sales, got {len(results)}"
    
    # Filter by customer 2
    response = client.get(f'/api/sales/?customer_id={data["customer2"].id}')
    assert response.status_code == 200
    results = response.json()['results']
    
    print(f"Sales for Customer 2: {len(results)}")
    assert len(results) == 2, f"Expected 2 sales, got {len(results)}"
    
    print("✅ TEST 6 PASSED")
    return True


def test_complex_scenario():
    """
    TEST 7: Complex real-world scenario
    
    Scenario:
    - Mix of CASH and CREDIT sales
    - Mix of COMPLETED, PARTIAL, and PENDING statuses
    - Verify all metrics are accurate
    """
    print("\n" + "="*80)
    print("TEST 7: Complex real-world scenario")
    print("="*80)
    
    # Clear existing data
    Sale.objects.all().delete()
    
    data = setup_test_data()
    
    # Cash sales (3 sales, total profit $700)
    for i in range(3):
        sale = create_sale(data, 'CASH', 'COMPLETED')
        add_sale_item(sale, data['product1'], data['stock_product1'], 5,
                      Decimal('100.00'), Decimal('50.00'))
        sale.calculate_totals()
        sale.save()
    
    # Completed credit sales (2 sales, total profit $900, should NOT count as outstanding)
    for i in range(2):
        sale = create_sale(data, 'CREDIT', 'COMPLETED', customer=data['customer1'])
        add_sale_item(sale, data['product2'], data['stock_product2'], 10,
                      Decimal('75.00'), Decimal('30.00'))
        sale.calculate_totals()
        sale.amount_paid = sale.total_amount
        sale.amount_due = Decimal('0.00')
        sale.save()
    
    # Pending credit sales (2 sales, total profit $500, should count as outstanding)
    for i in range(2):
        sale = create_sale(data, 'CREDIT', 'PENDING', customer=data['customer2'])
        add_sale_item(sale, data['product1'], data['stock_product1'], 5,
                      Decimal('100.00'), Decimal('50.00'))
        sale.calculate_totals()
        sale.save()
    
    # Partial credit sale (1 sale, profit $450, should count as outstanding)
    partial_sale = create_sale(data, 'CREDIT', 'PARTIAL', customer=data['customer1'])
    add_sale_item(partial_sale, data['product2'], data['stock_product2'], 10,
                  Decimal('75.00'), Decimal('30.00'))
    partial_sale.calculate_totals()
    partial_sale.amount_paid = Decimal('400.00')
    partial_sale.amount_due = Decimal('350.00')
    partial_sale.save()
    
    # Get summary
    client = APIClient()
    client.force_authenticate(user=data['user'])
    response = client.get('/api/sales/summary/')
    
    assert response.status_code == 200
    summary = response.json()
    
    print(f"\nTotal Profit: ${summary['total_profit']}")
    print(f"Outstanding Credit: ${summary['outstanding_credit']}")
    print(f"Cash on Hand: ${summary['cash_on_hand']}")
    print(f"Total Credit Sales: ${summary['total_credit_sales']}")
    print(f"Unpaid Credit Count: {summary['unpaid_credit_count']}")
    
    # Total profit = (3 × 250) + (2 × 450) + (2 × 250) + 450 = 750 + 900 + 500 + 450 = $2600
    assert Decimal(str(summary['total_profit'])) == Decimal('2600.00'), \
        f"Expected total profit $2600, got ${summary['total_profit']}"
    
    # Outstanding credit = (2 × 250) + 450 = 500 + 450 = $950
    assert Decimal(str(summary['outstanding_credit'])) == Decimal('950.00'), \
        f"Expected outstanding credit $950, got ${summary['outstanding_credit']}"
    
    # Cash on hand = 2600 - 950 = $1650
    assert Decimal(str(summary['cash_on_hand'])) == Decimal('1650.00'), \
        f"Expected cash on hand $1650, got ${summary['cash_on_hand']}"
    
    # Unpaid credit count = 2 (PENDING) + 1 (PARTIAL) = 3
    assert summary['unpaid_credit_count'] == 3, \
        f"Expected 3 unpaid credits, got {summary['unpaid_credit_count']}"
    
    print("✅ TEST 7 PASSED")
    return True


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*80)
    print("RUNNING CASH ON HAND CALCULATION TESTS")
    print("="*80)
    
    tests = [
        test_cash_on_hand_no_credit_sales,
        test_cash_on_hand_with_unpaid_credit,
        test_cash_on_hand_with_partial_payment,
        test_days_outstanding_filter,
        test_amount_range_filters,
        test_customer_filter,
        test_complex_scenario
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except AssertionError as e:
            print(f"❌ TEST FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ TEST ERROR: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total Tests: {len(tests)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed == 0:
        print("\n✅ ALL TESTS PASSED!")
    else:
        print(f"\n❌ {failed} TEST(S) FAILED")
    
    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    exit(0 if success else 1)
