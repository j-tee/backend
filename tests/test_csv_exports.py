"""
Test CSV export functionality for all export types

This test file validates that CSV exports work correctly for:
- Sales export
- Customer export
- Inventory export
- Audit log export
"""

import os
import sys
import django
import csv
from io import StringIO
from datetime import datetime, timedelta
from django.utils import timezone

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import Business, BusinessMembership
from reports.csv_exporters import (
    SalesCSVExporter,
    CustomerCSVExporter,
    InventoryCSVExporter,
    AuditLogCSVExporter,
)
from reports.services.sales import SalesExporter
from reports.services.customers import CustomerExporter
from reports.services.inventory import InventoryExporter
from reports.services.audit import AuditLogExporter

User = get_user_model()


def test_sales_csv_export():
    """Test sales CSV export"""
    print("\n" + "="*60)
    print("TEST 1: Sales CSV Export")
    print("="*60)
    
    # Get a test user with business
    user = User.objects.filter(
        business_memberships__isnull=False
    ).first()
    
    if not user:
        print("❌ No user with business membership found")
        return False
    
    membership = user.business_memberships.first()
    business = membership.business
    
    print(f"Business: {business.name}")
    print(f"User: {user.name}")
    
    # Export last 30 days of sales
    exporter = SalesExporter(user=user)
    
    filters = {
        'start_date': (timezone.now() - timedelta(days=30)).date(),
        'end_date': timezone.now().date(),
        'include_items': True,
    }
    
    try:
        data = exporter.export(filters)
        
        print(f"\nSales found: {data['summary']['total_sales']}")
        print(f"Total revenue: {data['summary'].get('total_revenue', 'N/A')}")
        
        # Generate CSV
        csv_exporter = SalesCSVExporter()
        csv_bytes = csv_exporter.export(data)
        csv_text = csv_bytes.decode('utf-8')
        
        # Parse CSV to validate structure
        reader = csv.reader(StringIO(csv_text))
        rows = list(reader)
        
        print(f"\nCSV generated successfully")
        print(f"Total rows: {len(rows)}")
        
        # Validate headers exist
        has_summary = any('Summary Metrics' in row for row in rows)
        has_sales = any('Sales Details' in row for row in rows)
        has_items = any('Line Items' in row for row in rows)
        
        print(f"✓ Summary section: {'Yes' if has_summary else 'No'}")
        print(f"✓ Sales detail section: {'Yes' if has_sales else 'No'}")
        print(f"✓ Line items section: {'Yes' if has_items else 'No'}")
        
        # Sample first few rows
        print(f"\nFirst 10 rows:")
        for i, row in enumerate(rows[:10]):
            print(f"  {i+1}. {row[:3]}")  # First 3 columns
        
        if has_summary and has_sales:
            print("\n✅ Sales CSV export test PASSED")
            return True
        else:
            print("\n❌ Sales CSV export test FAILED - Missing sections")
            return False
            
    except Exception as e:
        print(f"\n❌ Error during sales CSV export: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_customer_csv_export():
    """Test customer CSV export"""
    print("\n" + "="*60)
    print("TEST 2: Customer CSV Export")
    print("="*60)
    
    # Get a test user with business
    user = User.objects.filter(
        business_memberships__isnull=False
    ).first()
    
    if not user:
        print("❌ No user with business membership found")
        return False
    
    membership = user.business_memberships.first()
    business = membership.business
    
    print(f"Business: {business.name}")
    print(f"User: {user.name}")
    
    # Export all customers
    exporter = CustomerExporter(user=user)
    
    filters = {
        'include_credit_history': True,
    }
    
    try:
        data = exporter.export(filters)
        
        print(f"\nCustomers found: {data['summary']['total_customers']}")
        print(f"Outstanding balance: {data['summary'].get('total_outstanding_balance', 'N/A')}")
        
        # Generate CSV
        csv_exporter = CustomerCSVExporter()
        csv_bytes = csv_exporter.export(data)
        csv_text = csv_bytes.decode('utf-8')
        
        # Parse CSV to validate structure
        reader = csv.reader(StringIO(csv_text))
        rows = list(reader)
        
        print(f"\nCSV generated successfully")
        print(f"Total rows: {len(rows)}")
        
        # Validate sections
        has_statistics = any('Customer Statistics' in row for row in rows)
        has_aging = any('Aging Analysis Summary' in row for row in rows)
        has_details = any('Customer Details' in row for row in rows)
        has_aging_report = any('Credit Aging Analysis' in row for row in rows)
        
        print(f"✓ Statistics section: {'Yes' if has_statistics else 'No'}")
        print(f"✓ Aging summary section: {'Yes' if has_aging else 'No'}")
        print(f"✓ Customer details section: {'Yes' if has_details else 'No'}")
        print(f"✓ Aging report section: {'Yes' if has_aging_report else 'No'}")
        
        if has_statistics and has_details and has_aging_report:
            print("\n✅ Customer CSV export test PASSED")
            return True
        else:
            print("\n❌ Customer CSV export test FAILED - Missing sections")
            return False
            
    except Exception as e:
        print(f"\n❌ Error during customer CSV export: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_inventory_csv_export():
    """Test inventory CSV export"""
    print("\n" + "="*60)
    print("TEST 3: Inventory CSV Export")
    print("="*60)
    
    # Get a test user with business
    user = User.objects.filter(
        business_memberships__isnull=False
    ).first()
    
    if not user:
        print("❌ No user with business membership found")
        return False
    
    membership = user.business_memberships.first()
    business = membership.business
    
    print(f"Business: {business.name}")
    print(f"User: {user.name}")
    
    # Export all inventory
    exporter = InventoryExporter(user=user)
    
    filters = {}
    
    try:
        data = exporter.export(filters)
        
        print(f"\nStock items found: {data['summary']['total_unique_products']}")
        print(f"Total value: {data['summary'].get('total_inventory_value', 'N/A')}")
        
        # Generate CSV
        csv_exporter = InventoryCSVExporter()
        csv_bytes = csv_exporter.export(data)
        csv_text = csv_bytes.decode('utf-8')
        
        # Parse CSV to validate structure
        reader = csv.reader(StringIO(csv_text))
        rows = list(reader)
        
        print(f"\nCSV generated successfully")
        print(f"Total rows: {len(rows)}")
        
        # Validate sections
        has_statistics = any('Inventory Statistics' in row for row in rows)
        has_breakdown = any('Storefront Breakdown' in row for row in rows)
        has_stock_items = any('Stock Items' in row for row in rows)
        
        print(f"✓ Statistics section: {'Yes' if has_statistics else 'No'}")
        print(f"✓ Storefront breakdown: {'Yes' if has_breakdown else 'No'}")
        print(f"✓ Stock items section: {'Yes' if has_stock_items else 'No'}")
        
        if has_statistics and has_stock_items:
            print("\n✅ Inventory CSV export test PASSED")
            return True
        else:
            print("\n❌ Inventory CSV export test FAILED - Missing sections")
            return False
            
    except Exception as e:
        print(f"\n❌ Error during inventory CSV export: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_audit_log_csv_export():
    """Test audit log CSV export"""
    print("\n" + "="*60)
    print("TEST 4: Audit Log CSV Export")
    print("="*60)
    
    # Get a test user with business
    user = User.objects.filter(
        business_memberships__isnull=False
    ).first()
    
    if not user:
        print("❌ No user with business membership found")
        return False
    
    membership = user.business_memberships.first()
    business = membership.business
    
    print(f"Business: {business.name}")
    print(f"User: {user.name}")
    
    # Export last 30 days of audit logs
    exporter = AuditLogExporter(user=user)
    
    filters = {
        'start_date': (timezone.now() - timedelta(days=30)).date(),
        'end_date': timezone.now().date(),
    }
    
    try:
        data = exporter.export(filters)
        
        print(f"\nAudit logs found: {data['summary']['total_events']}")
        print(f"Unique users: {data['summary'].get('unique_users', 'N/A')}")
        
        # Generate CSV
        csv_exporter = AuditLogCSVExporter()
        csv_bytes = csv_exporter.export(data)
        csv_text = csv_bytes.decode('utf-8')
        
        # Parse CSV to validate structure
        reader = csv.reader(StringIO(csv_text))
        rows = list(reader)
        
        print(f"\nCSV generated successfully")
        print(f"Total rows: {len(rows)}")
        
        # Validate sections
        has_statistics = any('Audit Statistics' in row for row in rows)
        has_events = any('Top Event Types' in row for row in rows)
        has_users = any('Top Users' in row for row in rows)
        has_logs = any('Audit Logs' in row for row in rows)
        
        print(f"✓ Statistics section: {'Yes' if has_statistics else 'No'}")
        print(f"✓ Event types section: {'Yes' if has_events else 'No'}")
        print(f"✓ Users section: {'Yes' if has_users else 'No'}")
        print(f"✓ Audit logs section: {'Yes' if has_logs else 'No'}")
        
        if has_statistics and has_logs:
            print("\n✅ Audit log CSV export test PASSED")
            return True
        else:
            print("\n❌ Audit log CSV export test FAILED - Missing sections")
            return False
            
    except Exception as e:
        print(f"\n❌ Error during audit log CSV export: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all CSV export tests"""
    print("\n" + "="*60)
    print("CSV EXPORT TEST SUITE")
    print("="*60)
    
    results = {
        'Sales CSV Export': test_sales_csv_export(),
        'Customer CSV Export': test_customer_csv_export(),
        'Inventory CSV Export': test_inventory_csv_export(),
        'Audit Log CSV Export': test_audit_log_csv_export(),
    }
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All CSV export tests PASSED!")
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) FAILED")
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
