#!/usr/bin/env python
"""
Test if sales_reports view can be loaded
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

try:
    from reports.views.sales_reports import SalesSummaryReportView
    print("✅ SalesSummaryReportView imported successfully")
    print(f"✅ Has _handle_export: {hasattr(SalesSummaryReportView, '_handle_export')}")
    print(f"✅ Has _export_csv: {hasattr(SalesSummaryReportView, '_export_csv')}")
    print(f"✅ Has get method: {hasattr(SalesSummaryReportView, 'get')}")
    
    # Check if view can be instantiated
    view = SalesSummaryReportView()
    print(f"✅ View can be instantiated")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
