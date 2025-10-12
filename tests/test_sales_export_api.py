#!/usr/bin/env python
"""
Test the Sales Export API endpoint
"""
import os
import django
from datetime import datetime, timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from rest_framework.test import force_authenticate
from accounts.models import Business, BusinessMembership
from reports.views import SalesExportView
from django.utils import timezone

User = get_user_model()


def test_sales_export_api():
    """Test the Sales Export API endpoint"""
    
    print("=" * 80)
    print("SALES EXPORT API TEST")
    print("=" * 80)
    
    # Get a business with sales
    business = Business.objects.filter(sales__isnull=False).first()
    
    if not business:
        print("❌ No business with sales found")
        return
    
    print(f"\n✅ Testing with business: {business.name}")
    
    # Get a user
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
    
    # Create request
    factory = RequestFactory()
    
    # Test data
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    request_data = {
        'format': 'excel',
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'include_items': True
    }
    
    print(f"\nRequest data: {request_data}")
    
    # Create POST request
    request = factory.post(
        '/api/reports/sales/export/',
        data=request_data,
        content_type='application/json'
    )
    
    # Authenticate request
    force_authenticate(request, user=user)
    
    # Call view
    view = SalesExportView.as_view()
    
    try:
        response = view(request)
        
        print(f"\n✅ API Response:")
        print(f"   - Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print(f"   - Content-Type: {response.get('Content-Type', 'N/A')}")
            print(f"   - Content-Disposition: {response.get('Content-Disposition', 'N/A')}")
            print(f"   - File Size: {len(response.content)} bytes")
            
            # Check if it's a valid Excel file
            if response.content[:2] == b'PK':  # ZIP signature (Excel files are ZIP archives)
                print(f"   ✅ Valid Excel file generated!")
            else:
                print(f"   ⚠️  Response may not be a valid Excel file")
        else:
            print(f"   ❌ Error: {response.data if hasattr(response, 'data') else 'Unknown error'}")
        
    except Exception as e:
        print(f"❌ API call failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test 2: Invalid date range
    print("\n" + "-" * 80)
    print("TEST 2: Invalid Date Range (end before start)")
    print("-" * 80)
    
    request_data_invalid = {
        'format': 'excel',
        'start_date': end_date.strftime('%Y-%m-%d'),
        'end_date': start_date.strftime('%Y-%m-%d'),  # End before start
    }
    
    request = factory.post(
        '/api/reports/sales/export/',
        data=request_data_invalid,
        content_type='application/json'
    )
    force_authenticate(request, user=user)
    
    try:
        response = view(request)
        print(f"   - Status Code: {response.status_code}")
        
        if response.status_code == 400:
            print(f"   ✅ Correctly rejected invalid date range")
            if hasattr(response, 'data'):
                print(f"   - Error message: {response.data}")
        else:
            print(f"   ⚠️  Expected 400, got {response.status_code}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 3: No sales found
    print("\n" + "-" * 80)
    print("TEST 3: Date Range with No Sales")
    print("-" * 80)
    
    future_date = end_date + timedelta(days=365)
    request_data_no_sales = {
        'format': 'excel',
        'start_date': future_date.strftime('%Y-%m-%d'),
        'end_date': (future_date + timedelta(days=30)).strftime('%Y-%m-%d'),
    }
    
    request = factory.post(
        '/api/reports/sales/export/',
        data=request_data_no_sales,
        content_type='application/json'
    )
    force_authenticate(request, user=user)
    
    try:
        response = view(request)
        print(f"   - Status Code: {response.status_code}")
        
        if response.status_code == 404:
            print(f"   ✅ Correctly handled no sales case")
            if hasattr(response, 'data'):
                print(f"   - Message: {response.data}")
        elif response.status_code == 200:
            print(f"   ⚠️  Returned 200 but should be 404 for no sales")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\n" + "=" * 80)
    print("API TESTS COMPLETED")
    print("=" * 80)


if __name__ == '__main__':
    test_sales_export_api()
