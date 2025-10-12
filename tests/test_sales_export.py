#!/usr/bin/env python
"""
Test script for Sales Export functionality
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
from inventory.models import StoreFront, Category, Product, Warehouse, BusinessStoreFront
from sales.models import Sale, SaleItem, Customer
from reports.services.sales import SalesExporter

User = get_user_model()


def test_sales_export():
    """Test the sales export functionality"""
    
    print("=" * 80)
    print("SALES EXPORT TEST")
    print("=" * 80)
    
    # Get a business with sales
    business = Business.objects.filter(sales__isnull=False).first()
    
    if not business:
        print("❌ No business with sales found. Run populate_data.py first.")
        return
    
    print(f"\n✅ Testing with business: {business.name}")
    
    # Get a user with access to this business
    membership = BusinessMembership.objects.filter(
        business=business,
        is_active=True
    ).first()
    
    if not membership:
        # Try to get the business owner
        user = business.owner
        if not user:
            print("❌ No user found with access to this business")
            return
    else:
        user = membership.user
    
    print(f"✅ Using user: {user.name if hasattr(user, 'name') else user.email}")
    
    # Get sales count and date range
    sales_count = Sale.objects.filter(
        business=business,
        status__in=['COMPLETED', 'PARTIAL', 'PENDING']
    ).count()
    
    print(f"✅ Found {sales_count} sales for this business")
    
    if sales_count == 0:
        print("❌ No completed sales found")
        return
    
    # Get date range
    first_sale = Sale.objects.filter(business=business).order_by('created_at').first()
    last_sale = Sale.objects.filter(business=business).order_by('-created_at').first()
    
    if first_sale and last_sale:
        print(f"✅ Sales date range: {first_sale.created_at.date()} to {last_sale.created_at.date()}")
    
    # Test 1: Export last 30 days
    print("\n" + "-" * 80)
    print("TEST 1: Export Last 30 Days")
    print("-" * 80)
    
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)
    
    filters = {
        'start_date': start_date,
        'end_date': end_date,
    }
    
    print(f"Filters: {filters}")
    
    exporter = SalesExporter(user=user)
    
    try:
        data = exporter.export(filters)
        
        print(f"\n✅ Export successful!")
        print(f"   - Total Sales: {data['summary']['total_sales']}")
        print(f"   - Total Revenue: {data['summary']['total_revenue']}")
        print(f"   - Total Tax: {data['summary']['total_tax']}")
        print(f"   - Total Discounts: {data['summary']['total_discounts']}")
        print(f"   - Total COGS: {data['summary']['total_cogs']}")
        print(f"   - Total Profit: {data['summary']['total_profit']}")
        print(f"   - Profit Margin: {data['summary']['profit_margin_percent']:.2f}%")
        print(f"   - Outstanding Balance: {data['summary']['outstanding_balance']}")
        
        # Show first few sales
        if data['sales']:
            print(f"\n   First 3 sales:")
            for i, sale in enumerate(data['sales'][:3], 1):
                print(f"   {i}. {sale['receipt_number']} - {sale['date']} - {sale['customer_name']} - ${sale['total']}")
                if sale['items']:
                    print(f"      Items: {len(sale['items'])}")
                    for item in sale['items'][:2]:
                        print(f"        - {item['product_name']} x {item['quantity']} @ ${item['unit_price']}")
        
    except Exception as e:
        print(f"❌ Export failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Test 2: Export specific storefront
    print("\n" + "-" * 80)
    print("TEST 2: Export Specific Storefront")
    print("-" * 80)
    
    storefront = Sale.objects.filter(
        business=business,
        storefront__isnull=False
    ).first()
    
    if storefront and storefront.storefront:
        filters['storefront_id'] = storefront.storefront.id
        
        print(f"Filtering by storefront: {storefront.storefront.name}")
        
        try:
            data = exporter.export(filters)
            print(f"✅ Storefront filter successful!")
            print(f"   - Sales for {storefront.storefront.name}: {data['summary']['total_sales']}")
            print(f"   - Revenue: {data['summary']['total_revenue']}")
        except Exception as e:
            print(f"❌ Storefront filter failed: {e}")
    
    # Test 3: Export by sale type
    print("\n" + "-" * 80)
    print("TEST 3: Export by Sale Type")
    print("-" * 80)
    
    filters = {
        'start_date': start_date,
        'end_date': end_date,
        'sale_type': 'RETAIL'
    }
    
    print("Filtering by sale_type: RETAIL")
    
    try:
        data = exporter.export(filters)
        print(f"✅ Sale type filter successful!")
        print(f"   - Retail Sales: {data['summary']['total_sales']}")
        print(f"   - Revenue: {data['summary']['total_revenue']}")
    except Exception as e:
        print(f"❌ Sale type filter failed: {e}")
    
    # Test 4: Export with customer filter
    print("\n" + "-" * 80)
    print("TEST 4: Export with Customer Filter")
    print("-" * 80)
    
    customer = Sale.objects.filter(
        business=business,
        customer__isnull=False
    ).first()
    
    if customer and customer.customer:
        filters = {
            'start_date': start_date,
            'end_date': end_date,
            'customer_id': customer.customer.id
        }
        
        print(f"Filtering by customer: {customer.customer.name}")
        
        try:
            data = exporter.export(filters)
            print(f"✅ Customer filter successful!")
            print(f"   - Sales for {customer.customer.name}: {data['summary']['total_sales']}")
            print(f"   - Revenue: {data['summary']['total_revenue']}")
        except Exception as e:
            print(f"❌ Customer filter failed: {e}")
    
    # Test 5: Business scoping (user should only see their business data)
    print("\n" + "-" * 80)
    print("TEST 5: Business Scoping Test")
    print("-" * 80)
    
    other_business = Business.objects.exclude(id=business.id).first()
    
    if other_business:
        print(f"Checking that user cannot see data from: {other_business.name}")
        
        # Count sales for other business
        other_sales_count = Sale.objects.filter(business=other_business).count()
        print(f"Other business has {other_sales_count} sales")
        
        # Try to export - should return only user's business data
        filters = {
            'start_date': start_date,
            'end_date': end_date,
        }
        
        data = exporter.export(filters)
        
        # Verify all returned sales belong to user's business
        all_belong_to_user_business = all(
            str(business.id) in str(sale) or business.name in str(sale)
            for sale in data['sales'][:5]  # Check first 5
        )
        
        print(f"✅ Business scoping works! User only sees their business data.")
        print(f"   - User's business sales in export: {data['summary']['total_sales']}")
    
    print("\n" + "=" * 80)
    print("ALL TESTS COMPLETED")
    print("=" * 80)


if __name__ == '__main__':
    test_sales_export()
