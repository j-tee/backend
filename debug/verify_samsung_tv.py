#!/usr/bin/env python
"""
Samsung TV Stock Verification

Detailed analysis of Samsung TV 43" stock quantities:
1. How many have been sold
2. What adjustments have happened
3. Original batch stock across all warehouses

Run: python debug/verify_samsung_tv.py
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from django.db.models import Sum, Count
from sales.models import Sale, SaleItem
from inventory.models import Product, StockProduct
from inventory.stock_adjustments import StockAdjustment
from decimal import Decimal


def verify_samsung_tv():
    """Comprehensive Samsung TV 43" stock verification"""
    print("=" * 80)
    print("SAMSUNG TV 43\" STOCK VERIFICATION")
    print("=" * 80)
    print()
    
    # Find Samsung TV 43"
    samsung_tv = Product.objects.filter(name__icontains="Samsung TV 43").first()
    
    if not samsung_tv:
        print("❌ Samsung TV 43\" not found in database")
        return
    
    print(f"📺 Product: {samsung_tv.name}")
    print(f"   SKU: {samsung_tv.sku}")
    print(f"   ID: {samsung_tv.id}")
    print()
    print("=" * 80)
    print()
    
    # ========================================================================
    # 1. ORIGINAL BATCH STOCK ACROSS ALL WAREHOUSES
    # ========================================================================
    print("1️⃣  ORIGINAL BATCH STOCK (quantity field - immutable)")
    print("-" * 80)
    
    stock_batches = StockProduct.objects.filter(
        product=samsung_tv
    ).select_related('warehouse', 'stock', 'supplier').order_by('warehouse__name')
    
    if not stock_batches.exists():
        print("   No stock records found")
    else:
        total_original = 0
        total_current = 0
        
        for stock in stock_batches:
            original = stock.quantity  # Original intake quantity
            current = stock.calculated_quantity or 0  # Current working quantity
            diff = original - current
            
            print(f"\n   📦 {stock.warehouse.name}")
            print(f"      Batch: {stock.stock.description if stock.stock else 'N/A'}")
            print(f"      Arrival: {stock.stock.arrival_date if stock.stock else 'N/A'}")
            print(f"      Supplier: {stock.supplier.name if stock.supplier else 'N/A'}")
            print(f"      ---")
            print(f"      Original Quantity: {original:,} units (immutable)")
            print(f"      Current Quantity:  {current:,} units (after movements)")
            print(f"      Difference:        {diff:,} units (movements out)")
            print(f"      Unit Cost: ₱{stock.unit_cost:,.2f}")
            print(f"      Retail Price: ₱{stock.retail_price:,.2f}")
            
            total_original += original
            total_current += current
        
        print()
        print("   " + "=" * 76)
        print(f"   TOTALS ACROSS ALL WAREHOUSES:")
        print(f"      Original Stock (intake): {total_original:,} units")
        print(f"      Current Stock (working): {total_current:,} units")
        print(f"      Total Movements Out:     {total_original - total_current:,} units")
        print("   " + "=" * 76)
    
    print()
    print("=" * 80)
    print()
    
    # ========================================================================
    # 2. SALES BREAKDOWN
    # ========================================================================
    print("2️⃣  SALES BREAKDOWN")
    print("-" * 80)
    
    # Get sales by status
    sales_by_status = SaleItem.objects.filter(
        product=samsung_tv
    ).values('sale__status').annotate(
        total_units=Sum('quantity'),
        sale_count=Count('sale_id', distinct=True)
    ).order_by('sale__status')
    
    if not sales_by_status.exists():
        print("   No sales found for Samsung TV 43\"")
    else:
        total_units_sold = 0
        
        for status_data in sales_by_status:
            status = status_data['sale__status']
            units = status_data['total_units']
            count = status_data['sale_count']
            
            status_display = {
                'DRAFT': '📝 DRAFT (in cart, not committed)',
                'PENDING': '⏳ PENDING (committed, awaiting payment)',
                'PARTIAL': '💰 PARTIAL (committed, partially paid)',
                'COMPLETED': '✅ COMPLETED (committed, fully paid)',
                'CANCELLED': '❌ CANCELLED',
                'REFUNDED': '↩️  REFUNDED'
            }.get(status, status)
            
            # DRAFT sales don't reduce stock, others do
            stock_impact = "❌ No stock reduction" if status == 'DRAFT' else "✅ Stock reduced"
            
            print(f"\n   {status_display}")
            print(f"      Units: {units:,} units in {count} sale(s)")
            print(f"      Impact: {stock_impact}")
            
            # Only count non-DRAFT as actually sold/committed
            if status != 'DRAFT':
                total_units_sold += units
        
        print()
        print("   " + "=" * 76)
        print(f"   TOTAL COMMITTED (stock reduced): {total_units_sold:,} units")
        print(f"      (Excludes DRAFT sales - those are just reservations)")
        print("   " + "=" * 76)
    
    # Show detailed sale records
    print()
    print("   📋 DETAILED SALE RECORDS:")
    print("   " + "-" * 76)
    
    recent_sales = SaleItem.objects.filter(
        product=samsung_tv
    ).select_related('sale', 'sale__customer').order_by('-sale__created_at')[:20]
    
    if recent_sales.exists():
        for item in recent_sales:
            sale = item.sale
            status_icon = {
                'DRAFT': '📝',
                'PENDING': '⏳',
                'PARTIAL': '💰',
                'COMPLETED': '✅',
                'CANCELLED': '❌',
                'REFUNDED': '↩️'
            }.get(sale.status, '  ')
            
            customer = sale.customer.name if sale.customer else 'Walk-in'
            date = sale.created_at.strftime('%Y-%m-%d %H:%M')
            
            print(f"   {status_icon} {sale.receipt_number or 'No receipt':<20} "
                  f"{item.quantity:>4} units  {sale.status:<10}  "
                  f"{date}  {customer}")
    else:
        print("   No sales records found")
    
    print()
    print("=" * 80)
    print()
    
    # ========================================================================
    # 3. ADJUSTMENTS BREAKDOWN
    # ========================================================================
    print("3️⃣  STOCK ADJUSTMENTS")
    print("-" * 80)
    
    adjustments = StockAdjustment.objects.filter(
        stock_product__product=samsung_tv
    ).select_related('stock_product__warehouse', 'created_by', 'approved_by').order_by('-created_at')
    
    if not adjustments.exists():
        print("   No adjustments found for Samsung TV 43\"")
    else:
        total_positive = 0
        total_negative = 0
        
        for adj in adjustments:
            qty = adj.quantity
            if qty > 0:
                total_positive += qty
                direction = "⬆️  INCREASE"
            else:
                total_negative += abs(qty)
                direction = "⬇️  DECREASE"
            
            adj_type_display = dict(StockAdjustment.ADJUSTMENT_TYPES).get(
                adj.adjustment_type, adj.adjustment_type
            )
            
            status_icon = {
                'PENDING': '⏳',
                'APPROVED': '✅',
                'REJECTED': '❌',
                'COMPLETED': '✔️'
            }.get(adj.status, '  ')
            
            warehouse = adj.stock_product.warehouse.name
            date = adj.created_at.strftime('%Y-%m-%d %H:%M')
            created_by = adj.created_by.email if adj.created_by else 'System'
            
            print(f"\n   {direction}")
            print(f"      Type: {adj_type_display}")
            print(f"      Quantity: {qty:+,} units")
            print(f"      Warehouse: {warehouse}")
            print(f"      Status: {status_icon} {adj.status}")
            print(f"      Reason: {adj.reason[:60]}..." if len(adj.reason) > 60 else f"      Reason: {adj.reason}")
            print(f"      Created: {date} by {created_by}")
            if adj.reference_number:
                print(f"      Reference: {adj.reference_number}")
            print(f"      Cost Impact: ₱{adj.total_cost:,.2f}")
        
        print()
        print("   " + "=" * 76)
        print(f"   ADJUSTMENT SUMMARY:")
        print(f"      Total Increases: +{total_positive:,} units")
        print(f"      Total Decreases: -{total_negative:,} units")
        print(f"      Net Adjustment:  {total_positive - total_negative:+,} units")
        print("   " + "=" * 76)
    
    print()
    print("=" * 80)
    print()
    
    # ========================================================================
    # 4. RECONCILIATION
    # ========================================================================
    print("4️⃣  RECONCILIATION")
    print("-" * 80)
    
    # Calculate what current stock SHOULD be
    total_original = stock_batches.aggregate(total=Sum('quantity'))['total'] or 0
    total_current = stock_batches.aggregate(total=Sum('calculated_quantity'))['total'] or 0
    
    # Get committed sales (non-DRAFT)
    committed_sales = SaleItem.objects.filter(
        product=samsung_tv,
        sale__status__in=['PENDING', 'PARTIAL', 'COMPLETED', 'REFUNDED']
    ).aggregate(total=Sum('quantity'))['total'] or 0
    
    # Get net adjustments
    net_adjustments = adjustments.aggregate(total=Sum('quantity'))['total'] or 0
    
    print(f"   Original Stock (all warehouses):     {total_original:>6,} units")
    print(f"   Committed Sales (PENDING+PARTIAL+COMPLETED): {committed_sales:>6,} units")
    print(f"   Net Adjustments (theft/damage/returns):      {net_adjustments:>+6,} units")
    print("   " + "-" * 76)
    print(f"   Expected Current Stock:              {total_original - committed_sales + net_adjustments:>6,} units")
    print(f"   Actual Current Stock (calculated):   {total_current:>6,} units")
    print()
    
    if total_current == (total_original - committed_sales + net_adjustments):
        print("   ✅ RECONCILIATION MATCHES - Stock integrity verified!")
    else:
        diff = total_current - (total_original - committed_sales + net_adjustments)
        print(f"   ⚠️  DISCREPANCY: {diff:+,} units")
        print("      This may indicate:")
        print("      - Transfers not yet recorded")
        print("      - Manual database edits")
        print("      - Missing transaction records")
    
    print()
    print("=" * 80)
    print()
    
    # ========================================================================
    # 5. CURRENT RESERVATIONS
    # ========================================================================
    print("5️⃣  CURRENT RESERVATIONS (DRAFT SALES)")
    print("-" * 80)
    
    draft_sales = SaleItem.objects.filter(
        product=samsung_tv,
        sale__status='DRAFT'
    ).select_related('sale')
    
    if not draft_sales.exists():
        print("   No active reservations (DRAFT sales)")
    else:
        total_reserved = draft_sales.aggregate(total=Sum('quantity'))['total'] or 0
        print(f"   Total Reserved: {total_reserved:,} units in {draft_sales.count()} cart(s)")
        print()
        
        for item in draft_sales[:10]:
            sale = item.sale
            cart_id = str(sale.id)[:8]
            date = sale.created_at.strftime('%Y-%m-%d %H:%M')
            print(f"      Cart {cart_id}...  {item.quantity} units  Created: {date}")
    
    print()
    print("=" * 80)
    print()
    
    # ========================================================================
    # SUMMARY
    # ========================================================================
    print("📊 SUMMARY")
    print("=" * 80)
    print(f"Original Stock (all warehouses):   {total_original:>6,} units")
    print(f"Current Stock (working):           {total_current:>6,} units")
    print(f"Reserved (DRAFT carts):            {draft_sales.aggregate(total=Sum('quantity'))['total'] or 0:>6,} units")
    print(f"Available for Sale:                {total_current - (draft_sales.aggregate(total=Sum('quantity'))['total'] or 0):>6,} units")
    print()
    print(f"Committed Sales:                   {committed_sales:>6,} units")
    print(f"Net Adjustments:                   {net_adjustments:>+6,} units")
    print(f"Total Movements:                   {total_original - total_current:>6,} units")
    print("=" * 80)


if __name__ == '__main__':
    try:
        verify_samsung_tv()
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
