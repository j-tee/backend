#!/usr/bin/env python
"""
Test script for Customer Export API endpoints
"""
import os
import django
from decimal import Decimal

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from accounts.models import Business, BusinessMembership
from sales.models import Customer

User = get_user_model()


def test_customer_export_api():
    """Test the customer export API endpoint"""
    
    print("=" * 80)
    print("CUSTOMER EXPORT API TEST")
    print("=" * 80)
    
    # Get a business with customers
    business = Business.objects.filter(customers__isnull=False).first()
    
    if not business:
        print("❌ No business with customers found")
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
        print("❌ No user found")
        return
    
    print(f"✅ Using user: {user.name if hasattr(user, 'name') else user.email}")
    
    # Create API client and authenticate
    client = APIClient()
    client.force_authenticate(user=user)
    
    # Test 1: Export all customers (Excel)
    print("\n" + "-" * 80)
    print("TEST 1: Export All Customers (Excel)")
    print("-" * 80)
    
    response = client.post('/reports/customers/export/', {
        'format': 'excel',
        'is_active': True,
        'include_credit_history': True,
    })
    
    if response.status_code == 200:
        print(f"✅ Excel export successful!")
        print(f"   - Status Code: {response.status_code}")
        print(f"   - Content-Type: {response['Content-Type']}")
        print(f"   - File Size: {len(response.content)} bytes")
        print(f"   - Filename: {response.get('Content-Disposition', 'N/A')}")
        
        # Verify it's a valid Excel file
        if response.content.startswith(b'PK'):
            print(f"   - ✅ Valid Excel file (ZIP/XLSX signature detected)")
        else:
            print(f"   - ⚠️  May not be a valid Excel file")
    else:
        print(f"❌ Export failed!")
        print(f"   - Status Code: {response.status_code}")
        print(f"   - Response: {response.json() if response.status_code != 500 else response.content}")
    
    # Test 2: Export wholesale customers only
    print("\n" + "-" * 80)
    print("TEST 2: Export Wholesale Customers Only")
    print("-" * 80)
    
    response = client.post('/reports/customers/export/', {
        'format': 'excel',
        'customer_type': 'WHOLESALE',
        'is_active': True,
    })
    
    if response.status_code == 200:
        print(f"✅ Wholesale filter successful!")
        print(f"   - File Size: {len(response.content)} bytes")
    else:
        print(f"❌ Wholesale filter failed!")
        print(f"   - Status Code: {response.status_code}")
    
    # Test 3: Export with minimum outstanding balance
    print("\n" + "-" * 80)
    print("TEST 3: Export Customers with Outstanding Balance > $100")
    print("-" * 80)
    
    response = client.post('/reports/customers/export/', {
        'format': 'excel',
        'min_outstanding_balance': '100.00',
        'is_active': True,
    })
    
    if response.status_code == 200:
        print(f"✅ Balance filter successful!")
        print(f"   - File Size: {len(response.content)} bytes")
    else:
        print(f"❌ Balance filter failed!")
        print(f"   - Status Code: {response.status_code}")
    
    # Test 4: Try CSV format (should return 501)
    print("\n" + "-" * 80)
    print("TEST 4: Try CSV Format (Should Return 501)")
    print("-" * 80)
    
    response = client.post('/reports/customers/export/', {
        'format': 'csv',
        'is_active': True,
    })
    
    if response.status_code == 501:
        print(f"✅ CSV not implemented (as expected)")
        print(f"   - Status Code: {response.status_code}")
        try:
            print(f"   - Message: {response.json()}")
        except:
            pass
    else:
        print(f"⚠️  Unexpected response for CSV")
        print(f"   - Status Code: {response.status_code}")
    
    # Test 5: Invalid format
    print("\n" + "-" * 80)
    print("TEST 5: Invalid Format (Should Return 400)")
    print("-" * 80)
    
    response = client.post('/reports/customers/export/', {
        'format': 'invalid',
    })
    
    if response.status_code == 400:
        print(f"✅ Validation error (as expected)")
        print(f"   - Status Code: {response.status_code}")
        try:
            print(f"   - Errors: {response.json()}")
        except:
            pass
    else:
        print(f"⚠️  Unexpected response for invalid format")
        print(f"   - Status Code: {response.status_code}")
    
    # Test 6: No customers found (filter all out)
    print("\n" + "-" * 80)
    print("TEST 6: No Customers Found (High Balance Filter)")
    print("-" * 80)
    
    response = client.post('/reports/customers/export/', {
        'format': 'excel',
        'min_outstanding_balance': '999999999.00',
    })
    
    if response.status_code == 404:
        print(f"✅ No customers error (as expected)")
        print(f"   - Status Code: {response.status_code}")
        try:
            print(f"   - Message: {response.json()}")
        except:
            pass
    elif response.status_code == 200:
        print(f"ℹ️  Export succeeded with empty data")
        print(f"   - File Size: {len(response.content)} bytes")
    else:
        print(f"⚠️  Unexpected response")
        print(f"   - Status Code: {response.status_code}")
    
    # Test 7: Unauthenticated request
    print("\n" + "-" * 80)
    print("TEST 7: Unauthenticated Request (Should Return 401)")
    print("-" * 80)
    
    unauth_client = APIClient()
    response = unauth_client.post('/reports/customers/export/', {
        'format': 'excel',
    })
    
    if response.status_code in [401, 403]:
        print(f"✅ Authentication required (as expected)")
        print(f"   - Status Code: {response.status_code}")
    else:
        print(f"⚠️  Security issue: Unauthenticated request succeeded!")
        print(f"   - Status Code: {response.status_code}")
    
    print("\n" + "=" * 80)
    print("API TESTS COMPLETED")
    print("=" * 80)


if __name__ == '__main__':
    test_customer_export_api()
