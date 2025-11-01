"""
Test PDF export functionality for all export types

This test file validates that PDF exports work correctly for:
- Sales export
- Customer export
- Inventory export
- Audit log export
"""

import os
import sys
import django
from io import BytesIO
from datetime import datetime, timedelta
from django.utils import timezone

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import Business, BusinessMembership
from reports.pdf_exporters import (
    SalesPDFExporter,
    CustomerPDFExporter,
    InventoryPDFExporter,
    AuditLogPDFExporter,
)
from reports.services.sales import SalesExporter
from reports.services.customers import CustomerExporter
from reports.services.inventory import InventoryExporter
from reports.services.audit import AuditLogExporter

# Try to import PyPDF2 for PDF validation
try:
    from PyPDF2 import PdfReader
    PDF_VALIDATION_AVAILABLE = True
except ImportError:
    PDF_VALIDATION_AVAILABLE = False
    print("⚠️  PyPDF2 not installed - PDF validation will be limited")

User = get_user_model()


def validate_pdf(pdf_bytes):
    """Validate that the bytes represent a valid PDF"""
    if not PDF_VALIDATION_AVAILABLE:
        # Basic validation - check PDF header
        return pdf_bytes.startswith(b'%PDF')
    
    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        return len(reader.pages) > 0
    except Exception as e:
        print(f"  PDF validation error: {e}")
        return False


def test_sales_pdf_export():
    """Test sales PDF export"""
    print("\n" + "="*60)
    print("TEST 1: Sales PDF Export")
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
        print(f"Total revenue: ${data['summary'].get('total_revenue', 'N/A')}")
        
        # Generate PDF
        pdf_exporter = SalesPDFExporter()
        pdf_bytes = pdf_exporter.export(data)
        
        print(f"\nPDF generated successfully")
        print(f"File size: {len(pdf_bytes)} bytes ({len(pdf_bytes) / 1024:.2f} KB)")
        print(f"Content type: {pdf_exporter.content_type}")
        print(f"Extension: {pdf_exporter.file_extension}")
        
        # Validate PDF
        is_valid = validate_pdf(pdf_bytes)
        print(f"PDF valid: {'Yes' if is_valid else 'No'}")
        
        # Check PDF header
        has_pdf_header = pdf_bytes.startswith(b'%PDF')
        print(f"✓ PDF header: {'Yes' if has_pdf_header else 'No'}")
        
        # Check reasonable file size (should be > 1KB for data)
        reasonable_size = len(pdf_bytes) > 1024
        print(f"✓ Reasonable size: {'Yes' if reasonable_size else 'No'}")
        
        if is_valid and has_pdf_header and reasonable_size:
            print("\n✅ Sales PDF export test PASSED")
            return True
        else:
            print("\n❌ Sales PDF export test FAILED")
            return False
            
    except Exception as e:
        print(f"\n❌ Error during sales PDF export: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_customer_pdf_export():
    """Test customer PDF export"""
    print("\n" + "="*60)
    print("TEST 2: Customer PDF Export")
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
        print(f"Outstanding balance: ${data['summary'].get('total_outstanding_balance', 'N/A')}")
        
        # Generate PDF
        pdf_exporter = CustomerPDFExporter()
        pdf_bytes = pdf_exporter.export(data)
        
        print(f"\nPDF generated successfully")
        print(f"File size: {len(pdf_bytes)} bytes ({len(pdf_bytes) / 1024:.2f} KB)")
        
        # Validate PDF
        is_valid = validate_pdf(pdf_bytes)
        print(f"PDF valid: {'Yes' if is_valid else 'No'}")
        
        has_pdf_header = pdf_bytes.startswith(b'%PDF')
        reasonable_size = len(pdf_bytes) > 1024
        
        print(f"✓ PDF header: {'Yes' if has_pdf_header else 'No'}")
        print(f"✓ Reasonable size: {'Yes' if reasonable_size else 'No'}")
        
        if is_valid and has_pdf_header and reasonable_size:
            print("\n✅ Customer PDF export test PASSED")
            return True
        else:
            print("\n❌ Customer PDF export test FAILED")
            return False
            
    except Exception as e:
        print(f"\n❌ Error during customer PDF export: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_inventory_pdf_export():
    """Test inventory PDF export"""
    print("\n" + "="*60)
    print("TEST 3: Inventory PDF Export")
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
        print(f"Total value: ${data['summary'].get('total_inventory_value', 'N/A')}")
        
        # Generate PDF
        pdf_exporter = InventoryPDFExporter()
        pdf_bytes = pdf_exporter.export(data)
        
        print(f"\nPDF generated successfully")
        print(f"File size: {len(pdf_bytes)} bytes ({len(pdf_bytes) / 1024:.2f} KB)")
        
        # Validate PDF
        is_valid = validate_pdf(pdf_bytes)
        print(f"PDF valid: {'Yes' if is_valid else 'No'}")
        
        has_pdf_header = pdf_bytes.startswith(b'%PDF')
        reasonable_size = len(pdf_bytes) > 1024
        
        print(f"✓ PDF header: {'Yes' if has_pdf_header else 'No'}")
        print(f"✓ Reasonable size: {'Yes' if reasonable_size else 'No'}")
        
        if is_valid and has_pdf_header and reasonable_size:
            print("\n✅ Inventory PDF export test PASSED")
            return True
        else:
            print("\n❌ Inventory PDF export test FAILED")
            return False
            
    except Exception as e:
        print(f"\n❌ Error during inventory PDF export: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_audit_log_pdf_export():
    """Test audit log PDF export"""
    print("\n" + "="*60)
    print("TEST 4: Audit Log PDF Export")
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
        
        # Generate PDF
        pdf_exporter = AuditLogPDFExporter()
        pdf_bytes = pdf_exporter.export(data)
        
        print(f"\nPDF generated successfully")
        print(f"File size: {len(pdf_bytes)} bytes ({len(pdf_bytes) / 1024:.2f} KB)")
        
        # Validate PDF
        is_valid = validate_pdf(pdf_bytes)
        print(f"PDF valid: {'Yes' if is_valid else 'No'}")
        
        has_pdf_header = pdf_bytes.startswith(b'%PDF')
        reasonable_size = len(pdf_bytes) > 1024
        
        print(f"✓ PDF header: {'Yes' if has_pdf_header else 'No'}")
        print(f"✓ Reasonable size: {'Yes' if reasonable_size else 'No'}")
        
        if is_valid and has_pdf_header and reasonable_size:
            print("\n✅ Audit log PDF export test PASSED")
            return True
        else:
            print("\n❌ Audit log PDF export test FAILED")
            return False
            
    except Exception as e:
        print(f"\n❌ Error during audit log PDF export: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all PDF export tests"""
    print("\n" + "="*60)
    print("PDF EXPORT TEST SUITE")
    print("="*60)
    
    if not PDF_VALIDATION_AVAILABLE:
        print("\n⚠️  Note: Install PyPDF2 for full PDF validation")
        print("   pip install PyPDF2")
        print()
    
    results = {
        'Sales PDF Export': test_sales_pdf_export(),
        'Customer PDF Export': test_customer_pdf_export(),
        'Inventory PDF Export': test_inventory_pdf_export(),
        'Audit Log PDF Export': test_audit_log_pdf_export(),
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
        print("\n🎉 All PDF export tests PASSED!")
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) FAILED")
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
