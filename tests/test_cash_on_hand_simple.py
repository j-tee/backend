"""
Simple test for cash on hand calculation using existing data.

This test uses the existing sales data in the database to verify:
1. Total profit calculation
2. Outstanding credit calculation  
3. Cash on hand = total profit - outstanding credit
4. Additional metrics and filters
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from decimal import Decimal
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from sales.models import Sale

User = get_user_model()


def test_summary_endpoint_with_real_data():
    """Test the summary endpoint with existing database data."""
    print("\n" + "="*80)
    print("TESTING CASH ON HAND CALCULATION WITH REAL DATA")
    print("="*80)
    
    # Get a user from the database
    user = User.objects.first()
    if not user:
        print("❌ No users found in database. Please populate data first.")
        return False
    
    print(f"\nUsing user: {user.email}")
    
    # Create API client
    client = APIClient()
    client.force_authenticate(user=user)
    
    # Test 1: Summary endpoint returns new fields
    print("\n" + "-"*80)
    print("TEST 1: Summary endpoint includes profit-based metrics")
    print("-"*80)
    
    response = client.get('/api/sales/summary/')
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    summary = response.json()
    
    # Check for required fields
    required_fields = ['total_profit', 'outstanding_credit', 'cash_on_hand', 
                      'total_credit_sales', 'unpaid_credit_count']
    
    for field in required_fields:
        assert field in summary, f"Missing field: {field}"
        print(f"✓ {field}: {summary[field]}")
    
    # Validate calculations
    total_profit = Decimal(str(summary['total_profit']))
    outstanding_credit = Decimal(str(summary['outstanding_credit']))
    cash_on_hand = Decimal(str(summary['cash_on_hand']))
    
    # Cash on hand should = total profit - outstanding credit
    expected_cash_on_hand = total_profit - outstanding_credit
    assert cash_on_hand == expected_cash_on_hand, \
        f"Cash on hand calculation incorrect: {cash_on_hand} != {total_profit} - {outstanding_credit}"
    
    print(f"\n✓ Cash on hand calculation correct:")
    print(f"  Total Profit: ${total_profit:,.2f}")
    print(f"  - Outstanding Credit: ${outstanding_credit:,.2f}")
    print(f"  = Cash on Hand: ${cash_on_hand:,.2f}")
    
    print("\n✅ TEST 1 PASSED")
    
    # Test 2: Filter by days outstanding
    print("\n" + "-"*80)
    print("TEST 2: Filter sales by days outstanding")
    print("-"*80)
    
    response = client.get('/api/sales/?days_outstanding=30')
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    results = response.json()['results']
    print(f"✓ Found {len(results)} sales outstanding > 30 days")
    
    # Verify all results are credit sales with outstanding balance
    for sale in results:
        assert sale['payment_type'] == 'CREDIT', \
            f"Non-credit sale in results: {sale['id']}"
        assert sale['status'] in ['PENDING', 'PARTIAL'], \
            f"Completed sale in results: {sale['id']}"
    
    print("✅ TEST 2 PASSED")
    
    # Test 3: Filter by amount due range
    print("\n" + "-"*80)
    print("TEST 3: Filter sales by amount due range")
    print("-"*80)
    
    # Test minimum amount due
    response = client.get('/api/sales/?min_amount_due=1000')
    assert response.status_code == 200
    results = response.json()['results']
    print(f"✓ Found {len(results)} sales with amount due >= $1000")
    
    for sale in results:
        assert Decimal(sale['amount_due']) >= Decimal('1000'), \
            f"Sale amount due too low: {sale['amount_due']}"
    
    # Test maximum amount due  
    response = client.get('/api/sales/?max_amount_due=500')
    assert response.status_code == 200
    results = response.json()['results']
    print(f"✓ Found {len(results)} sales with amount due <= $500")
    
    for sale in results:
        assert Decimal(sale['amount_due']) <= Decimal('500'), \
            f"Sale amount due too high: {sale['amount_due']}"
    
    # Test range filter
    response = client.get('/api/sales/?min_amount_due=100&max_amount_due=500')
    assert response.status_code == 200
    results = response.json()['results']
    print(f"✓ Found {len(results)} sales with amount due $100-$500")
    
    for sale in results:
        amount = Decimal(sale['amount_due'])
        assert Decimal('100') <= amount <= Decimal('500'), \
            f"Sale amount due out of range: {sale['amount_due']}"
    
    print("✅ TEST 3 PASSED")
    
    # Test 4: Filter by customer
    print("\n" + "-"*80)
    print("TEST 4: Filter sales by customer")
    print("-"*80)
    
    # Find a sale with a customer
    sale_with_customer = Sale.objects.filter(customer__isnull=False).first()
    if sale_with_customer:
        customer_id = sale_with_customer.customer.id
        response = client.get(f'/api/sales/?customer_id={customer_id}')
        assert response.status_code == 200
        results = response.json()['results']
        print(f"✓ Found {len(results)} sales for customer {customer_id}")
        
        for sale in results:
            assert sale['customer'] == str(customer_id), \
                f"Wrong customer in results: {sale['customer']}"
        
        print("✅ TEST 4 PASSED")
    else:
        print("⚠ No sales with customers found, skipping customer filter test")
    
    return True


def run_tests():
    """Run all tests."""
    print("\n" + "="*80)
    print("CASH ON HAND CALCULATION - INTEGRATION TESTS")
    print("="*80)
    
    try:
        success = test_summary_endpoint_with_real_data()
        
        if success:
            print("\n" + "="*80)
            print("✅ ALL TESTS PASSED!")
            print("="*80)
            return True
        else:
            print("\n" + "="*80)
            print("❌ TESTS FAILED")
            print("="*80)
            return False
            
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return False
    except Exception as e:
        print(f"\n❌ TEST ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = run_tests()
    exit(0 if success else 1)
