#!/usr/bin/env python
"""
Verify Stock Quantities vs Sales

This script checks if StockProduct.quantity correctly reflects
completed sales (should be reduced).

Run: python debug/verify_stock_vs_sales.py
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from django.db.models import Sum
from sales.models import Sale, SaleItem
from inventory.models import Product, StockProduct
from decimal import Decimal


def verify_stock_vs_sales():
    """Check if stock quantities match expected values after sales"""
    print("=" * 80)
    print("STOCK QUANTITY VS SALES VERIFICATION")
    print("=" * 80)
    print()
    
    # Get products with both stock and sales
    products_with_sales = SaleItem.objects.filter(
        sale__status__in=['COMPLETED', 'PARTIAL', 'PENDING']
    ).values('product_id').distinct()
    
    print(f"Found {products_with_sales.count()} products with completed/pending sales")
    print()
    
    issues_found = []
    
    for item in products_with_sales[:10]:  # Check first 10 products
        product_id = item['product_id']
        product = Product.objects.filter(id=product_id).first()
        
        if not product:
            continue
            
        # Get current stock (what's in warehouse NOW)
        current_stock = StockProduct.objects.filter(
            product_id=product_id
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        # Get COMPLETED sales (should have reduced stock)
        completed_sales = SaleItem.objects.filter(
            product_id=product_id,
            sale__status='COMPLETED'
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        # Get PENDING sales (should have reduced stock - committed but unpaid)
        pending_sales = SaleItem.objects.filter(
            product_id=product_id,
            sale__status='PENDING'
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        # Get DRAFT sales (should NOT have reduced stock - just reservations)
        draft_sales = SaleItem.objects.filter(
            product_id=product_id,
            sale__status='DRAFT'
        ).aggregate(total=Sum('quantity'))['total'] or 0
        
        total_committed = completed_sales + pending_sales
        
        print(f"📦 {product.name} (ID: {str(product_id)[:8]}...)")
        print(f"   Current Stock (StockProduct.quantity): {current_stock} units")
        print(f"   COMPLETED sales: {completed_sales} units (should be deducted)")
        print(f"   PENDING sales: {pending_sales} units (should be deducted)")
        print(f"   DRAFT sales: {draft_sales} units (NOT deducted - just reserved)")
        print(f"   Total Committed: {total_committed} units")
        
        # Check if stock makes sense
        if completed_sales > 0 or pending_sales > 0:
            # If we have committed sales, current stock should reflect this
            # We can't calculate "original stock" without historical data,
            # but we can check if current stock seems reasonable
            
            if current_stock == 0 and total_committed > 0:
                print(f"   ⚠️  POTENTIAL ISSUE: Stock is 0 but {total_committed} units sold")
                issues_found.append(product.name)
            elif current_stock > 0:
                print(f"   ✅ Stock > 0, appears normal")
        
        print()
    
    print("=" * 80)
    print()
    
    if issues_found:
        print(f"⚠️  Found {len(issues_found)} products with potential stock issues:")
        for name in issues_found:
            print(f"   - {name}")
    else:
        print("✅ No obvious stock integrity issues detected")
    
    print()
    print("=" * 80)
    print()
    
    # Additional check: Find products with high stock but no sales
    print("🔍 ADDITIONAL CHECK: Products with 464 units in stock")
    print("-" * 80)
    
    products_464 = StockProduct.objects.filter(quantity=464).select_related('product')
    
    if products_464.exists():
        for stock in products_464[:5]:
            completed = SaleItem.objects.filter(
                product=stock.product,
                sale__status='COMPLETED'
            ).aggregate(total=Sum('quantity'))['total'] or 0
            
            pending = SaleItem.objects.filter(
                product=stock.product,
                sale__status='PENDING'
            ).aggregate(total=Sum('quantity'))['total'] or 0
            
            print(f"\n📦 {stock.product.name}")
            print(f"   Warehouse: {stock.warehouse.name}")
            print(f"   Current Stock: {stock.quantity} units")
            print(f"   COMPLETED sales: {completed} units")
            print(f"   PENDING sales: {pending} units")
            
            if completed > 0 or pending > 0:
                print(f"   ⚠️  ISSUE: Has {completed + pending} committed sales but stock unchanged!")
                print(f"   Expected stock: ~{stock.quantity - (completed + pending)} units")
            else:
                print(f"   ℹ️  No sales yet - stock level is original")
    else:
        print("No products with exactly 464 units in stock")
    
    print()
    print("=" * 80)


if __name__ == '__main__':
    try:
        verify_stock_vs_sales()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
