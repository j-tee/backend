#!/usr/bin/env python3
"""
Script to update the _build_stock_levels() method in StockLevelsSummaryReportView
to match the enhanced frontend requirements.

This script adds:
1. Rename 'warehouses' to 'locations'
2. Add 'reserved', 'available', 'reorder_point', 'status' per location
3. Add 'total_available', 'last_restocked', 'days_until_stockout' per product
"""

import re
from datetime import datetime

def update_build_stock_levels():
    file_path = 'reports/views/inventory_reports.py'
    
    print(f"Reading {file_path}...")
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Define the new _build_stock_levels method
    new_method = '''    def _build_stock_levels(self, queryset, request) -> tuple:
        """Build product-level stock details with pagination"""
        from django.db.models import Sum, Q
        from datetime import datetime, timedelta
        
        # Group by product and aggregate across warehouses
        product_stocks = {}
        
        for stock in queryset:
            product_id = str(stock.product.id)
            
            if product_id not in product_stocks:
                product_stocks[product_id] = {
                    'product_id': product_id,
                    'product_name': stock.product.name,
                    'sku': stock.product.sku,
                    'category': stock.product.category.name if stock.product.category else None,
                    'total_quantity': 0,
                    'total_value': Decimal('0.00'),
                    'total_available': 0,  # New field
                    'locations': [],  # Renamed from 'warehouses'
                    'is_low_stock': False,
                    'is_out_of_stock': False,
                    'last_restocked': None,  # New field
                    'days_until_stockout': None  # New field
                }
            
            # Calculate reserved quantity for this product at this warehouse
            # Query only DRAFT sales - PENDING/PARTIAL/COMPLETED have already committed stock
            from sales.models import Sale, SaleItem
            reserved_qty = SaleItem.objects.filter(
                sale__warehouse_id=stock.warehouse.id,
                product_id=stock.product.id,
                sale__status='DRAFT'  # Only uncommitted cart items are reservations
            ).aggregate(total=Sum('quantity'))['total'] or 0
            
            # Calculate available quantity
            available_qty = max(0, stock.quantity - reserved_qty)
            
            # Get reorder point (default to 10 if not set on product)
            reorder_point = getattr(stock.product, 'reorder_point', 10)
            
            # Determine status for this location
            if stock.quantity == 0:
                location_status = 'out_of_stock'
            elif stock.quantity < reorder_point:
                location_status = 'low_stock'
            else:
                location_status = 'in_stock'
            
            # Add location entry (renamed from warehouse)
            warehouse_value = stock.quantity * stock.landed_unit_cost
            product_stocks[product_id]['locations'].append({
                'warehouse_id': str(stock.warehouse.id),
                'warehouse_name': stock.warehouse.name,
                'quantity': stock.quantity,
                'reserved': reserved_qty,  # New field
                'available': available_qty,  # New field
                'reorder_point': reorder_point,  # New field
                'status': location_status,  # New field
                'unit_cost': str(stock.landed_unit_cost),
                'value': str(warehouse_value),
                'supplier': stock.supplier.name if stock.supplier else None
            })
            
            # Update totals
            product_stocks[product_id]['total_quantity'] += stock.quantity
            product_stocks[product_id]['total_available'] += available_qty
            product_stocks[product_id]['total_value'] += warehouse_value
            
            # Track last restocked date (most recent stock record for this product)
            if stock.created_at:
                if (product_stocks[product_id]['last_restocked'] is None or 
                    stock.created_at > product_stocks[product_id]['last_restocked']):
                    product_stocks[product_id]['last_restocked'] = stock.created_at
        
        # Finalize and add status flags + sales velocity calculations
        stock_levels = []
        for product_data in product_stocks.values():
            product_data['total_value'] = str(product_data['total_value'])
            product_data['is_out_of_stock'] = product_data['total_quantity'] == 0
            product_data['is_low_stock'] = 0 < product_data['total_quantity'] < 10
            
            # Calculate days until stockout based on 30-day sales velocity
            if product_data['total_available'] > 0:
                try:
                    from sales.models import SaleItem
                    thirty_days_ago = datetime.now() - timedelta(days=30)
                    
                    # Get total quantity sold in last 30 days for this product
                    sales_volume = SaleItem.objects.filter(
                        product_id=product_data['product_id'],
                        sale__status='COMPLETED',
                        sale__created_at__gte=thirty_days_ago
                    ).aggregate(total=Sum('quantity'))['total'] or 0
                    
                    if sales_volume > 0:
                        # Daily velocity = 30-day volume / 30
                        daily_velocity = sales_volume / 30.0
                        # Days until stockout = available / daily_velocity
                        days_left = int(product_data['total_available'] / daily_velocity)
                        product_data['days_until_stockout'] = days_left
                    else:
                        # No sales in last 30 days - set to null
                        product_data['days_until_stockout'] = None
                except Exception as e:
                    # If calculation fails, set to null
                    product_data['days_until_stockout'] = None
            else:
                product_data['days_until_stockout'] = 0
            
            # Format last_restocked as ISO string
            if product_data['last_restocked']:
                product_data['last_restocked'] = product_data['last_restocked'].isoformat()
            
            stock_levels.append(product_data)
        
        # Sort by total value descending
        stock_levels.sort(key=lambda x: Decimal(x['total_value']), reverse=True)
        
        # Apply pagination
        page, page_size = self.get_pagination_params(request)
        total_count = len(stock_levels)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_data = stock_levels[start_idx:end_idx]
        
        pagination = {
            'page': page,
            'page_size': page_size,
            'total_count': total_count,
            'total_pages': (total_count + page_size - 1) // page_size
        }
        
        return paginated_data, pagination'''
    
    # Find and replace the _build_stock_levels method
    # Pattern to match the entire method (from def to the next method or class)
    pattern = r'    def _build_stock_levels\(self, queryset, request\) -> tuple:.*?(?=\n\nclass |\n    def [a-z_]+\(|\Z)'
    
    match = re.search(pattern, content, re.DOTALL)
    if match:
        print("\n✓ Found _build_stock_levels() method")
        print(f"  Current method: {len(match.group(0))} characters")
        print(f"  New method: {len(new_method)} characters")
        
        # Replace the method
        updated_content = content[:match.start()] + new_method + content[match.end():]
        
        print("\nWriting updated file...")
        with open(file_path, 'w') as f:
            f.write(updated_content)
        
        print("\n✅ _build_stock_levels() method updated successfully!")
        print("\nChanges made:")
        print("  1. ✓ Renamed 'warehouses' → 'locations'")
        print("  2. ✓ Added 'reserved' field per location")
        print("  3. ✓ Added 'available' field per location")
        print("  4. ✓ Added 'reorder_point' field per location")
        print("  5. ✓ Added 'status' field per location")
        print("  6. ✓ Added 'total_available' field per product")
        print("  7. ✓ Added 'last_restocked' field per product")
        print("  8. ✓ Added 'days_until_stockout' field per product")
        print("  9. ✓ Implemented sales velocity calculation")
        print("\nThe backend is now fully aligned with the frontend!")
    else:
        print("❌ Could not find _build_stock_levels() method")
        return False
    
    return True

if __name__ == '__main__':
    success = update_build_stock_levels()
    exit(0 if success else 1)
