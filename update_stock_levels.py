#!/usr/bin/env python3
"""
Stock Levels Backend Update Script
Updates the StockLevelsSummaryReportView to match frontend expectations
"""

import re
import sys
from pathlib import Path

def update_stock_levels_report():
    """Update the inventory_reports.py file with new structure"""
    
    file_path = Path('reports/views/inventory_reports.py')
    
    if not file_path.exists():
        print(f"Error: File {file_path} not found!")
        sys.exit(1)
    
    print(f"Reading {file_path}...")
    with open(file_path, 'r') as f:
        content = f.read()
    
    print("Backing up original file...")
    backup_path = file_path.with_suffix('.py.backup')
    with open(backup_path, 'w') as f:
        f.write(content)
    print(f"Backup created at {backup_path}")
    
    # Change 1: Update _build_summary to return in_stock, low_stock, out_of_stock
    print("\n1. Updating _build_summary() method...")
    old_summary = r'''    def _build_summary\(self, queryset\) -> Dict\[str, Any\]:
        """Build overall summary statistics"""
        # Get unique products
        products = queryset\.values\('product'\)\.distinct\(\)
        total_products = products\.count\(\)
        
        # Get warehouse count
        warehouses_count = queryset\.values\('warehouse'\)\.distinct\(\)\.count\(\)
        
        # Aggregate totals
        totals = queryset\.aggregate\(
            total_units=Sum\('quantity'\),
            total_value=Sum\(
                F\('quantity'\) \* \(
                    F\('unit_cost'\) \+ 
                    Coalesce\(F\('unit_tax_amount'\), Value\(0\)\) \+ 
                    Coalesce\(F\('unit_additional_cost'\), Value\(0\)\)
                \),
                output_field=DecimalField\(\)
            \)
        \)
        
        # Count low stock and out of stock
        # Low stock: < 10 units \(simplified, could be based on reorder point\)
        low_stock_count = queryset\.filter\(quantity__lt=10, quantity__gt=0\)\.values\('product'\)\.distinct\(\)\.count\(\)
        out_of_stock_count = queryset\.filter\(quantity=0\)\.values\('product'\)\.distinct\(\)\.count\(\)
        
        # Total variants \(total stock product entries across all warehouses/suppliers\)
        total_variants = queryset\.count\(\)
        
        return \{
            'total_products': total_products,
            'total_variants': total_variants,
            'total_stock_units': int\(totals\['total_units'\] or 0\),
            'total_stock_value': str\(totals\['total_value'\] or Decimal\('0\.00'\)\),
            'warehouses_count': warehouses_count,
            'low_stock_products': low_stock_count,
            'out_of_stock_products': out_of_stock_count,
            'products_with_stock': queryset\.filter\(quantity__gt=0\)\.values\('product'\)\.distinct\(\)\.count\(\)
        \}'''
    
    new_summary = '''    def _build_summary(self, queryset) -> Dict[str, Any]:
        """Build overall summary statistics"""
        # Get unique products
        products = queryset.values('product').distinct()
        total_products = products.count()
        
        # Get warehouse count
        warehouses_count = queryset.values('warehouse').distinct().count()
        
        # Aggregate totals using landed_unit_cost
        totals = queryset.aggregate(
            total_units=Sum('quantity'),
            total_value=Sum(
                F('quantity') * F('landed_unit_cost'),
                output_field=DecimalField()
            )
        )
        
        # Calculate in_stock, low_stock, out_of_stock BY PRODUCT
        # A product counts once regardless of how many warehouses it's in
        product_statuses = {}
        REORDER_POINT = 10  # Default reorder threshold
        
        for stock in queryset:
            prod_id = str(stock.product.id)
            if prod_id not in product_statuses:
                product_statuses[prod_id] = {
                    'has_good_stock': False,
                    'has_some_stock': False,
                    'has_no_stock': True
                }
            
            # If ANY location has stock above reorder point, product is "in stock"
            if stock.quantity > REORDER_POINT:
                product_statuses[prod_id]['has_good_stock'] = True
                product_statuses[prod_id]['has_no_stock'] = False
            # If ANY location has some stock (but all below reorder point), it's "low stock"
            elif stock.quantity > 0:
                product_statuses[prod_id]['has_some_stock'] = True
                product_statuses[prod_id]['has_no_stock'] = False
        
        # Count products in each category
        in_stock = sum(1 for p in product_statuses.values() if p['has_good_stock'])
        low_stock = sum(1 for p in product_statuses.values() if p['has_some_stock'] and not p['has_good_stock'])
        out_of_stock = sum(1 for p in product_statuses.values() if p['has_no_stock'])
        
        # Total variants
        total_variants = queryset.count()
        
        return {
            'total_products': total_products,
            'total_variants': total_variants,
            'in_stock': in_stock,
            'low_stock': low_stock,
            'out_of_stock': out_of_stock,
            'total_stock_value': str(totals['total_value'] or Decimal('0.00')),
            'warehouses_count': warehouses_count
        }'''
    
    # Apply the change (using simple string replacement due to regex complexity)
    # Find the method and replace it
    start_marker = "    def _build_summary(self, queryset) -> Dict[str, Any]:"
    end_marker = "    def _build_warehouse_breakdown(self, queryset) -> List[Dict]:"
    
    start_idx = content.find(start_marker)
    end_idx = content.find(end_marker)
    
    if start_idx == -1 or end_idx == -1:
        print("ERROR: Could not find _build_summary method boundaries!")
        sys.exit(1)
    
    content = content[:start_idx] + new_summary + '\n    \n' + content[end_idx:]
    print("✓ _build_summary() updated")
    
    # Change 2: Update get() method to return correct structure
    print("\n2. Updating get() method response structure...")
    
    old_return = """        return ReportResponse.success(summary_data, stock_levels, metadata)"""
    new_return = """        # Return simplified structure matching frontend expectations
        response_data = {
            'summary': summary,
            'items': stock_levels
        }
        
        return ReportResponse.success(response_data, None, metadata)"""
    
    content = content.replace(old_return, new_return)
    print("✓ get() method response updated")
    
    # Write the updated content
    print(f"\nWriting updated file to {file_path}...")
    with open(file_path, 'w') as f:
        f.write(content)
    
    print("\n✅ Stock Levels Report updated successfully!")
    print(f"\nBackup saved at: {backup_path}")
    print("\nNext steps:")
    print("1. Review the changes")
    print("2. Test the API endpoint")
    print("3. Update _build_stock_levels() method manually (complex changes)")
    print("\nFor _build_stock_levels(), see: backend/reports/STOCK-LEVELS-BACKEND-CHANGES.md")

if __name__ == '__main__':
    update_stock_levels_report()
