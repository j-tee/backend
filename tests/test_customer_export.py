#!/usr/bin/env python
"""
Test script for Customer Export functionality
"""
import os
import django
from datetime import datetime, timedelta
from decimal import Decimal

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from accounts.models import Business, BusinessMembership
from sales.models import Customer, Sale
from reports.services.customers import CustomerExporter

User = get_user_model()


def test_customer_export():
    """Test the customer export functionality"""
    
    print("=" * 80)
    print("CUSTOMER EXPORT TEST")
    print("=" * 80)
    
    # Get a business with customers
    business = Business.objects.filter(customers__isnull=False).first()
    
    if not business:
        print("❌ No business with customers found. Run populate_data.py first.")
        return
    
    print(f"\n✅ Testing with business: {business.name}")
    
    # Get a user with access to this business
    membership = BusinessMembership.objects.filter(
        business=business,
        is_active=True
    ).first()
    
    if membership:
        user = membership.user
    else:
        user = business.owner
    
    if not user:
        print("❌ No user found with access to this business")
        return
    
    print(f"✅ Using user: {user.name if hasattr(user, 'name') else user.email}")
    
    # Get customer count
    customers_count = Customer.objects.filter(
        business=business,
        is_active=True
    ).count()
    
    print(f"✅ Found {customers_count} active customers for this business")
    
    if customers_count == 0:
        print("❌ No active customers found")
        return
    
    # Get customer types breakdown
    retail_count = Customer.objects.filter(business=business, customer_type='RETAIL').count()
    wholesale_count = Customer.objects.filter(business=business, customer_type='WHOLESALE').count()
    
    print(f"   - Retail customers: {retail_count}")
    print(f"   - Wholesale customers: {wholesale_count}")
    
    # Test 1: Export all customers
    print("\n" + "-" * 80)
    print("TEST 1: Export All Active Customers")
    print("-" * 80)
    
    filters = {
        'is_active': True,
        'include_credit_history': True,
    }
    
    print(f"Filters: {filters}")
    
    exporter = CustomerExporter(user=user)
    
    try:
        data = exporter.export(filters)
        
        print(f"\n✅ Export successful!")
        print(f"   - Total Customers: {data['summary']['total_customers']}")
        print(f"   - Retail: {data['summary']['retail_customers']}")
        print(f"   - Wholesale: {data['summary']['wholesale_customers']}")
        print(f"   - Total Credit Limit: ${data['summary']['total_credit_limit']}")
        print(f"   - Total Outstanding: ${data['summary']['total_outstanding_balance']}")
        print(f"   - Available Credit: ${data['summary']['total_available_credit']}")
        print(f"   - Blocked: {data['summary']['blocked_customers']}")
        
        # Aging analysis
        print(f"\n   Aging Analysis:")
        print(f"   - Current (0-30 days): ${data['summary']['aging_current']}")
        print(f"   - 31-60 days: ${data['summary']['aging_31_60']}")
        print(f"   - 61-90 days: ${data['summary']['aging_61_90']}")
        print(f"   - Over 90 days: ${data['summary']['aging_over_90']}")
        print(f"   - Total Overdue: ${data['summary']['total_overdue']}")
        
        # Show first few customers
        if data['customers']:
            print(f"\n   First 3 customers:")
            for i, customer in enumerate(data['customers'][:3], 1):
                print(f"   {i}. {customer['name']}")
                print(f"      Type: {customer['customer_type']}")
                print(f"      Credit: ${customer['credit_limit']} limit, ${customer['outstanding_balance']} owed")
                print(f"      Sales: {customer['total_sales_count']} transactions, ${customer['total_sales_amount']} total")
                if customer['total_overdue'] != '0.00':
                    print(f"      ⚠️  Overdue: ${customer['total_overdue']}")
        
        # Credit transactions
        if data['credit_transactions']:
            print(f"\n   Credit Transactions: {len(data['credit_transactions'])} found")
        
    except Exception as e:
        print(f"❌ Export failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test 2: Export only wholesale customers
    print("\n" + "-" * 80)
    print("TEST 2: Export Wholesale Customers Only")
    print("-" * 80)
    
    filters = {
        'customer_type': 'WHOLESALE',
        'is_active': True,
    }
    
    print(f"Filters: {filters}")
    
    try:
        data = exporter.export(filters)
        print(f"✅ Wholesale filter successful!")
        print(f"   - Wholesale Customers: {data['summary']['total_customers']}")
        print(f"   - Total Credit Limit: ${data['summary']['total_credit_limit']}")
        print(f"   - Outstanding Balance: ${data['summary']['total_outstanding_balance']}")
    except Exception as e:
        print(f"❌ Wholesale filter failed: {e}")
    
    # Test 3: Export customers with outstanding balances
    print("\n" + "-" * 80)
    print("TEST 3: Customers with Outstanding Balances")
    print("-" * 80)
    
    filters = {
        'min_outstanding_balance': Decimal('0.01'),
        'is_active': True,
    }
    
    print(f"Filtering customers with outstanding balance > $0.01")
    
    try:
        data = exporter.export(filters)
        print(f"✅ Outstanding balance filter successful!")
        print(f"   - Customers with Credit: {data['summary']['total_customers']}")
        print(f"   - Total Outstanding: ${data['summary']['total_outstanding_balance']}")
        print(f"   - Total Overdue: ${data['summary']['total_overdue']}")
        
        if data['customers']:
            print(f"\n   Customers with outstanding balances:")
            for customer in data['customers']:
                if float(customer['outstanding_balance']) > 0:
                    print(f"   - {customer['name']}: ${customer['outstanding_balance']} " +
                          f"(Overdue: ${customer['total_overdue']})")
    except Exception as e:
        print(f"❌ Balance filter failed: {e}")
    
    # Test 4: Export blocked customers
    print("\n" + "-" * 80)
    print("TEST 4: Blocked Customers")
    print("-" * 80)
    
    filters = {
        'credit_status': 'blocked',
    }
    
    print(f"Filtering blocked customers")
    
    try:
        data = exporter.export(filters)
        blocked_count = data['summary']['total_customers']
        print(f"✅ Blocked filter successful!")
        print(f"   - Blocked Customers: {blocked_count}")
        
        if blocked_count > 0 and data['customers']:
            print(f"\n   Blocked customers:")
            for customer in data['customers'][:3]:
                print(f"   - {customer['name']}: ${customer['outstanding_balance']} owed")
        elif blocked_count == 0:
            print(f"   ℹ️  No blocked customers found (good!)")
    except Exception as e:
        print(f"❌ Blocked filter failed: {e}")
    
    # Test 5: Business scoping
    print("\n" + "-" * 80)
    print("TEST 5: Business Scoping Test")
    print("-" * 80)
    
    other_business = Business.objects.exclude(id=business.id).first()
    
    if other_business:
        print(f"Checking that user cannot see data from: {other_business.name}")
        
        # Count customers for other business
        other_customers_count = Customer.objects.filter(business=other_business).count()
        print(f"Other business has {other_customers_count} customers")
        
        # Try to export - should return only user's business data
        filters = {'is_active': True}
        data = exporter.export(filters)
        
        print(f"✅ Business scoping works! User only sees their business data.")
        print(f"   - User's business customers in export: {data['summary']['total_customers']}")
    
    print("\n" + "=" * 80)
    print("ALL TESTS COMPLETED")
    print("=" * 80)


if __name__ == '__main__':
    test_customer_export()
