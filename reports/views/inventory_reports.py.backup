"""
Inventory Analytical Reports

Endpoints for inventory management and warehouse analytics.
Tracks stock levels, movements, low stock alerts, and warehouse performance.
"""

from decimal import Decimal
from typing import Dict, Any, List
from datetime import timedelta, date
from django.db.models import Sum, Count, Avg, Q, F, Min, Max, DecimalField, Case, When, Value
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth, Coalesce
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated

from inventory.models import Product, StockProduct, Warehouse, Category, Supplier
from inventory.stock_adjustments import StockAdjustment
from sales.models import Sale, SaleItem
from reports.services.report_base import BaseReportView
from reports.utils.response import ReportResponse, ReportError
from reports.utils.aggregation import AggregationHelper


class StockLevelsSummaryReportView(BaseReportView):
    """
    Stock Levels Summary Report
    
    GET /reports/api/inventory/stock-levels/
    
    Real-time overview of inventory across all warehouses.
    Shows current stock quantities, values, and warehouse/category breakdowns.
    
    Query Parameters:
    - warehouse_id: UUID (optional - filter by warehouse)
    - category_id: UUID (optional - filter by category)
    - product_id: UUID (optional - specific product)
    - supplier_id: UUID (optional - filter by supplier)
    - min_quantity: int (optional - products with at least this quantity)
    - max_quantity: int (optional - products with at most this quantity)
    - include_zero_stock: boolean (default: false)
    - page: int (pagination)
    - page_size: int (pagination, default: 50)
    
    Response Format:
    {
        "success": true,
        "data": {
            "summary": {
                "total_products": 250,
                "total_stock_units": 15000,
                "total_stock_value": "750000.00",
                "warehouses_count": 3,
                "low_stock_products": 15,
                "out_of_stock_products": 5
            },
            "by_warehouse": [...],
            "by_category": [...],
            "stock_levels": [...]
        },
        "meta": {...}
    }
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Generate stock levels summary report"""
        # Get business ID
        business_id, error = self.get_business_or_error(request)
        if error:
            return ReportResponse.error(error)
        
        # Parse filters
        warehouse_id = request.GET.get('warehouse_id')
        category_id = request.GET.get('category_id')
        product_id = request.GET.get('product_id')
        supplier_id = request.GET.get('supplier_id')
        min_quantity = request.GET.get('min_quantity')
        max_quantity = request.GET.get('max_quantity')
        include_zero_stock = request.GET.get('include_zero_stock', 'false').lower() == 'true'
        
        # Build queryset
        queryset = StockProduct.objects.select_related(
            'product', 'warehouse', 'product__category', 'supplier'
        ).filter(product__business_id=business_id)
        
        if warehouse_id:
            queryset = queryset.filter(warehouse_id=warehouse_id)
        if category_id:
            queryset = queryset.filter(product__category_id=category_id)
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        if supplier_id:
            queryset = queryset.filter(supplier_id=supplier_id)
        if not include_zero_stock:
            queryset = queryset.filter(quantity__gt=0)
        if min_quantity:
            queryset = queryset.filter(quantity__gte=int(min_quantity))
        if max_quantity:
            queryset = queryset.filter(quantity__lte=int(max_quantity))
        
        # Build summary
        summary = self._build_summary(queryset)
        
        # Build warehouse breakdown
        by_warehouse = self._build_warehouse_breakdown(queryset)
        
        # Build category breakdown
        by_category = self._build_category_breakdown(queryset)
        
        # Build product-level stock levels (paginated)
        stock_levels, pagination = self._build_stock_levels(queryset, request)
        
        # Combine summary with breakdowns
        summary_data = {
            **summary,
            'by_warehouse': by_warehouse,
            'by_category': by_category
        }
        
        # Metadata
        metadata = {
            'warehouse_id': warehouse_id,
            'category_id': category_id,
            'product_id': product_id,
            'supplier_id': supplier_id,
            'include_zero_stock': include_zero_stock,
            **pagination
        }
        
        return ReportResponse.success(summary_data, stock_levels, metadata)
    
    def _build_summary(self, queryset) -> Dict[str, Any]:
        """Build overall summary statistics"""
        # Get unique products
        products = queryset.values('product').distinct()
        total_products = products.count()
        
        # Get warehouse count
        warehouses_count = queryset.values('warehouse').distinct().count()
        
        # Aggregate totals
        totals = queryset.aggregate(
            total_units=Sum('quantity'),
            total_value=Sum(
                F('quantity') * (
                    F('unit_cost') + 
                    Coalesce(F('unit_tax_amount'), Value(0)) + 
                    Coalesce(F('unit_additional_cost'), Value(0))
                ),
                output_field=DecimalField()
            )
        )
        
        # Count low stock and out of stock
        # Low stock: < 10 units (simplified, could be based on reorder point)
        low_stock_count = queryset.filter(quantity__lt=10, quantity__gt=0).values('product').distinct().count()
        out_of_stock_count = queryset.filter(quantity=0).values('product').distinct().count()
        
        # Total variants (total stock product entries across all warehouses/suppliers)
        total_variants = queryset.count()
        
        return {
            'total_products': total_products,
            'total_variants': total_variants,
            'total_stock_units': int(totals['total_units'] or 0),
            'total_stock_value': str(totals['total_value'] or Decimal('0.00')),
            'warehouses_count': warehouses_count,
            'low_stock_products': low_stock_count,
            'out_of_stock_products': out_of_stock_count,
            'products_with_stock': queryset.filter(quantity__gt=0).values('product').distinct().count()
        }
    
    def _build_warehouse_breakdown(self, queryset) -> List[Dict]:
        """Build warehouse-level breakdown"""
        warehouse_data = queryset.values(
            'warehouse__id', 'warehouse__name'
        ).annotate(
            total_products=Count('product', distinct=True),
            total_units=Sum('quantity'),
            total_value=Sum(
                F('quantity') * (
                    F('unit_cost') + 
                    Coalesce(F('unit_tax_amount'), Value(0)) + 
                    Coalesce(F('unit_additional_cost'), Value(0))
                ),
                output_field=DecimalField()
            ),
            low_stock_count=Count('id', filter=Q(quantity__lt=10, quantity__gt=0))
        ).order_by('-total_value')
        
        return [
            {
                'warehouse_id': str(item['warehouse__id']),
                'warehouse_name': item['warehouse__name'],
                'total_products': item['total_products'],
                'total_units': int(item['total_units'] or 0),
                'total_value': str(item['total_value'] or Decimal('0.00')),
                'low_stock_count': item['low_stock_count']
            }
            for item in warehouse_data
        ]
    
    def _build_category_breakdown(self, queryset) -> List[Dict]:
        """Build category-level breakdown"""
        category_data = queryset.values(
            'product__category__id', 'product__category__name'
        ).annotate(
            total_products=Count('product', distinct=True),
            total_units=Sum('quantity'),
            total_value=Sum(
                F('quantity') * (
                    F('unit_cost') + 
                    Coalesce(F('unit_tax_amount'), Value(0)) + 
                    Coalesce(F('unit_additional_cost'), Value(0))
                ),
                output_field=DecimalField()
            )
        ).order_by('-total_value')
        
        return [
            {
                'category_id': str(item['product__category__id']),
                'category_name': item['product__category__name'],
                'total_products': item['total_products'],
                'total_units': int(item['total_units'] or 0),
                'total_value': str(item['total_value'] or Decimal('0.00'))
            }
            for item in category_data
        ]
    
    def _build_stock_levels(self, queryset, request) -> tuple:
        """Build product-level stock details with pagination"""
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
                    'warehouses': [],
                    'is_low_stock': False,
                    'is_out_of_stock': False
                }
            
            # Add warehouse entry
            warehouse_value = stock.quantity * stock.landed_unit_cost
            product_stocks[product_id]['warehouses'].append({
                'warehouse_id': str(stock.warehouse.id),
                'warehouse_name': stock.warehouse.name,
                'quantity': stock.quantity,
                'unit_cost': str(stock.landed_unit_cost),
                'value': str(warehouse_value),
                'supplier': stock.supplier.name if stock.supplier else None
            })
            
            # Update totals
            product_stocks[product_id]['total_quantity'] += stock.quantity
            product_stocks[product_id]['total_value'] += warehouse_value
        
        # Finalize and add status flags
        stock_levels = []
        for product_data in product_stocks.values():
            product_data['total_value'] = str(product_data['total_value'])
            product_data['is_out_of_stock'] = product_data['total_quantity'] == 0
            product_data['is_low_stock'] = 0 < product_data['total_quantity'] < 10
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
        
        return paginated_data, pagination


class LowStockAlertsReportView(BaseReportView):
    """
    Low Stock Alerts Report
    
    GET /reports/api/inventory/low-stock-alerts/
    
    Identifies products that need reordering based on current stock levels
    and sales velocity. Provides reorder recommendations and priority levels.
    
    Query Parameters:
    - warehouse_id: UUID (optional - filter by warehouse)
    - category_id: UUID (optional - filter by category)
    - priority: critical|high|medium (optional - filter by priority)
    - days_threshold: int (default: 30 - alert if < X days of stock)
    - page: int (pagination)
    - page_size: int (pagination, default: 50)
    
    Response Format:
    {
        "success": true,
        "data": {
            "summary": {
                "total_low_stock_products": 15,
                "critical_alerts": 3,
                "high_priority": 7,
                "medium_priority": 5
            },
            "alerts": [...]
        },
        "meta": {...}
    }
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Generate low stock alerts report"""
        # Get business ID
        business_id, error = self.get_business_or_error(request)
        if error:
            return ReportResponse.error(error)
        
        # Parse filters
        warehouse_id = request.GET.get('warehouse_id')
        category_id = request.GET.get('category_id')
        priority = request.GET.get('priority')
        days_threshold = int(request.GET.get('days_threshold', 30))
        
        # Build queryset for stock products
        queryset = StockProduct.objects.select_related(
            'product', 'warehouse', 'product__category', 'supplier'
        ).filter(
            product__business_id=business_id,
            quantity__gt=0  # Only products with some stock
        )
        
        if warehouse_id:
            queryset = queryset.filter(warehouse_id=warehouse_id)
        if category_id:
            queryset = queryset.filter(product__category_id=category_id)
        
        # Build alerts with sales velocity
        alerts = self._build_alerts(queryset, days_threshold)
        
        # Filter by priority if specified
        if priority:
            alerts = [a for a in alerts if a['priority'] == priority]
        
        # Build summary
        summary = self._build_summary(alerts)
        
        # Apply pagination
        page, page_size = self.get_pagination_params(request)
        total_count = len(alerts)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_alerts = alerts[start_idx:end_idx]
        
        pagination = {
            'page': page,
            'page_size': page_size,
            'total_count': total_count,
            'total_pages': (total_count + page_size - 1) // page_size
        }
        
        # Metadata
        metadata = {
            'warehouse_id': warehouse_id,
            'category_id': category_id,
            'priority': priority,
            'days_threshold': days_threshold,
            **pagination
        }
        
        return ReportResponse.success(summary, paginated_alerts, metadata)
    
    def _build_alerts(self, queryset, days_threshold: int) -> List[Dict]:
        """Build low stock alerts with sales velocity"""
        # Get sales data for last 30 days
        thirty_days_ago = timezone.now().date() - timedelta(days=30)
        
        # Calculate sales velocity per product
        sales_velocity = SaleItem.objects.filter(
            sale__created_at__date__gte=thirty_days_ago,
            sale__status__in=['COMPLETED', 'PARTIAL']
        ).values('product').annotate(
            total_sold=Sum('quantity')
        )
        
        # Create lookup dict
        velocity_lookup = {
            str(item['product']): item['total_sold']
            for item in sales_velocity
        }
        
        alerts = []
        
        for stock in queryset:
            product_id = str(stock.product.id)
            
            # Calculate average daily sales
            total_sold_30days = Decimal(str(velocity_lookup.get(product_id, 0)))
            avg_daily_sales = total_sold_30days / Decimal('30.0')
            
            # Calculate days until stockout
            if avg_daily_sales > 0:
                days_until_stockout = Decimal(str(stock.quantity)) / avg_daily_sales
            else:
                days_until_stockout = Decimal('999')  # No recent sales, not urgent
            
            # Determine priority
            if days_until_stockout < 5 or stock.quantity < 5:
                priority = 'critical'
            elif days_until_stockout < 14:
                priority = 'high'
            elif days_until_stockout < days_threshold:
                priority = 'medium'
            else:
                continue  # Not a low stock alert
            
            # Calculate recommended order quantity
            # Order enough for 30 days + safety stock (10 days)
            recommended_qty = int((avg_daily_sales * Decimal('40')) - Decimal(str(stock.quantity))) if avg_daily_sales > 0 else 50
            recommended_qty = max(recommended_qty, 10)  # Minimum order of 10
            
            # Get latest restock date (from stock_product created_at or adjustments)
            last_restock_date = stock.created_at.date()
            
            alerts.append({
                'product_id': product_id,
                'product_name': stock.product.name,
                'sku': stock.product.sku,
                'category': stock.product.category.name if stock.product.category else None,
                'warehouse_id': str(stock.warehouse.id),
                'warehouse_name': stock.warehouse.name,
                'current_quantity': stock.quantity,
                'reorder_point': 20,  # Simplified, could be product-specific
                'recommended_order_quantity': recommended_qty,
                'supplier_id': str(stock.supplier.id) if stock.supplier else None,
                'supplier_name': stock.supplier.name if stock.supplier else None,
                'unit_cost': str(stock.landed_unit_cost),
                'estimated_order_cost': str(stock.landed_unit_cost * recommended_qty),
                'priority': priority,
                'days_until_stockout': round(float(days_until_stockout), 1),
                'average_daily_sales': round(float(avg_daily_sales), 2),
                'last_restock_date': last_restock_date.isoformat()
            })
        
        # Sort by priority (critical first) then by days until stockout
        priority_order = {'critical': 0, 'high': 1, 'medium': 2}
        alerts.sort(key=lambda x: (priority_order[x['priority']], x['days_until_stockout']))
        
        return alerts
    
    def _build_summary(self, alerts: List[Dict]) -> Dict[str, Any]:
        """Build summary statistics"""
        critical = [a for a in alerts if a['priority'] == 'critical']
        high = [a for a in alerts if a['priority'] == 'high']
        medium = [a for a in alerts if a['priority'] == 'medium']
        
        # Calculate total estimated reorder cost
        total_reorder_cost = sum(
            Decimal(alert['estimated_order_cost'])
            for alert in alerts
        )
        
        return {
            'total_low_stock_products': len(alerts),
            'critical_alerts': len(critical),
            'high_priority': len(high),
            'medium_priority': len(medium),
            'estimated_reorder_cost': str(total_reorder_cost)
        }


class StockMovementHistoryReportView(BaseReportView):
    """
    Stock Movement History Report
    
    GET /reports/api/inventory/movements/
    
    Tracks all inventory changes over time including sales, adjustments,
    returns, and transfers. Provides shrinkage analysis and movement trends.
    
    Query Parameters:
    - start_date: YYYY-MM-DD (default: 30 days ago)
    - end_date: YYYY-MM-DD (default: today)
    - warehouse_id: UUID (optional - filter by warehouse)
    - product_id: UUID (optional - filter by product)
    - movement_type: all|sales|adjustments|returns (default: all)
    - adjustment_type: THEFT|DAMAGE|EXPIRED|... (optional - specific type)
    - grouping: daily|weekly|monthly (default: daily)
    - page: int (pagination)
    - page_size: int (pagination, default: 50)
    
    Response Format:
    {
        "success": true,
        "data": {
            "summary": {
                "total_movements": 500,
                "total_units_in": 3000,
                "total_units_out": 2500,
                "net_change": 500,
                "shrinkage": {...}
            },
            "time_series": [...],
            "movements": [...]
        },
        "meta": {...}
    }
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Generate stock movement history report"""
        # Get business ID
        business_id, error = self.get_business_or_error(request)
        if error:
            return ReportResponse.error(error)
        
        # Parse date range
        start_date, end_date, error = self.get_date_range(request, default_days=30)
        if error:
            return ReportResponse.error(error)
        
        warehouse_id = request.GET.get('warehouse_id')
        product_id = request.GET.get('product_id')
        movement_type = request.GET.get('movement_type', 'all')
        adjustment_type = request.GET.get('adjustment_type')
        grouping = request.GET.get('grouping', 'daily')
        
        # Build summary
        summary = self._build_summary(
            start_date, end_date, warehouse_id, product_id, 
            movement_type, adjustment_type
        )
        
        # Build time series
        time_series = self._build_time_series(
            start_date, end_date, warehouse_id, product_id,
            movement_type, grouping
        )
        
        # Build movements list (paginated)
        movements, pagination = self._build_movements(
            start_date, end_date, warehouse_id, product_id,
            movement_type, adjustment_type, request
        )
        
        # Combine summary with time series
        summary_data = {
            **summary,
            'time_series': time_series
        }
        
        # Metadata
        metadata = {
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'warehouse_id': warehouse_id,
            'product_id': product_id,
            'movement_type': movement_type,
            'adjustment_type': adjustment_type,
            'grouping': grouping,
            **pagination
        }
        
        return ReportResponse.success(summary_data, movements, metadata)
    
    def _build_summary(self, start_date, end_date, warehouse_id, product_id,
                      movement_type, adjustment_type) -> Dict[str, Any]:
        """Build summary of all movements"""
        # Get adjustments (positive and negative)
        adjustments_qs = StockAdjustment.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            status='COMPLETED'
        )
        
        if warehouse_id:
            adjustments_qs = adjustments_qs.filter(stock_product__warehouse_id=warehouse_id)
        if product_id:
            adjustments_qs = adjustments_qs.filter(stock_product__product_id=product_id)
        if adjustment_type:
            adjustments_qs = adjustments_qs.filter(adjustment_type=adjustment_type)
        
        # Get sales (always negative movement)
        sales_qs = SaleItem.objects.filter(
            sale__created_at__date__gte=start_date,
            sale__created_at__date__lte=end_date,
            sale__status__in=['COMPLETED', 'PARTIAL']
        )
        
        if warehouse_id:
            # Sales don't directly link to warehouse, skip this filter for now
            pass
        if product_id:
            sales_qs = sales_qs.filter(product_id=product_id)
        
        # Calculate movements based on type
        total_movements = 0
        units_in = 0
        units_out = 0
        value_in = Decimal('0.00')
        value_out = Decimal('0.00')
        movement_breakdown = {}
        
        if movement_type in ['all', 'adjustments']:
            # Process adjustments
            adj_stats = adjustments_qs.aggregate(
                count=Count('id'),
                total_qty=Sum('quantity'),
                total_cost=Sum('total_cost')
            )
            
            adj_by_type = adjustments_qs.values('adjustment_type').annotate(
                count=Count('id'),
                total_quantity=Sum('quantity')
            )
            
            total_movements += adj_stats['count'] or 0
            
            for item in adj_by_type:
                adj_type = item['adjustment_type']
                qty = item['total_quantity'] or 0
                movement_breakdown[adj_type.lower()] = qty
                
                if qty > 0:
                    units_in += qty
                else:
                    units_out += abs(qty)
        
        if movement_type in ['all', 'sales']:
            # Process sales (always outbound)
            sales_stats = sales_qs.aggregate(
                count=Count('id'),
                total_qty=Sum('quantity'),
                total_value=Sum(F('quantity') * F('unit_price'), output_field=DecimalField())
            )
            
            sales_qty = sales_stats['total_qty'] or 0
            total_movements += sales_stats['count'] or 0
            units_out += sales_qty
            value_out += sales_stats['total_value'] or Decimal('0.00')
            movement_breakdown['sales'] = -sales_qty  # Negative for outbound
        
        net_change = units_in - units_out
        net_value = value_in - value_out
        
        # Calculate shrinkage (negative adjustments)
        shrinkage_types = ['THEFT', 'LOSS', 'DAMAGE', 'EXPIRED', 'SPOILAGE', 'WRITE_OFF']
        shrinkage_qs = adjustments_qs.filter(adjustment_type__in=shrinkage_types)
        
        shrinkage_stats = shrinkage_qs.aggregate(
            total_units=Sum('quantity'),
            total_cost=Sum('total_cost')
        )
        
        shrinkage_units = abs(shrinkage_stats['total_units'] or 0)
        shrinkage_cost = shrinkage_stats['total_cost'] or Decimal('0.00')
        
        # Calculate shrinkage percentage (of total outbound)
        shrinkage_pct = (shrinkage_units / units_out * 100) if units_out > 0 else 0
        
        return {
            'total_movements': total_movements,
            'total_units_in': units_in,
            'total_units_out': units_out,
            'net_change': net_change,
            'value_in': str(value_in),
            'value_out': str(value_out),
            'net_value_change': str(net_value),
            'movement_breakdown': movement_breakdown,
            'shrinkage': {
                'total_units': shrinkage_units,
                'total_value': str(abs(shrinkage_cost)),
                'percentage_of_outbound': round(shrinkage_pct, 2)
            }
        }
    
    def _build_time_series(self, start_date, end_date, warehouse_id, product_id,
                          movement_type, grouping) -> List[Dict]:
        """Build time-series breakdown of movements"""
        # Determine truncation function
        if grouping == 'daily':
            trunc_func = TruncDate
        elif grouping == 'weekly':
            trunc_func = TruncWeek
        else:  # monthly
            trunc_func = TruncMonth
        
        # Get adjustments grouped by period
        adjustments_qs = StockAdjustment.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            status='COMPLETED'
        )
        
        if warehouse_id:
            adjustments_qs = adjustments_qs.filter(stock_product__warehouse_id=warehouse_id)
        if product_id:
            adjustments_qs = adjustments_qs.filter(stock_product__product_id=product_id)
        
        if movement_type in ['all', 'adjustments']:
            adj_periods = adjustments_qs.annotate(
                period=trunc_func('created_at')
            ).values('period').annotate(
                count=Count('id'),
                units_in=Sum('quantity', filter=Q(quantity__gt=0)),
                units_out=Sum('quantity', filter=Q(quantity__lt=0))
            ).order_by('period')
        else:
            adj_periods = []
        
        # Get sales grouped by period
        if movement_type in ['all', 'sales']:
            sales_qs = SaleItem.objects.filter(
                sale__created_at__date__gte=start_date,
                sale__created_at__date__lte=end_date,
                sale__status__in=['COMPLETED', 'PARTIAL']
            )
            
            if product_id:
                sales_qs = sales_qs.filter(product_id=product_id)
            
            sales_periods = sales_qs.annotate(
                period=trunc_func('sale__created_at')
            ).values('period').annotate(
                count=Count('id'),
                units_sold=Sum('quantity')
            ).order_by('period')
        else:
            sales_periods = []
        
        # Combine periods
        period_map = {}
        
        for item in adj_periods:
            period_date = item['period']
            period_key = period_date.strftime('%Y-%m-%d')
            
            if period_key not in period_map:
                period_map[period_key] = {
                    'period': period_key,
                    'period_start': period_date.strftime('%Y-%m-%d'),
                    'period_end': self._get_period_end(period_date, grouping).strftime('%Y-%m-%d'),
                    'units_in': 0,
                    'units_out': 0,
                    'net_change': 0,
                    'movements_count': 0
                }
            
            period_map[period_key]['units_in'] += item['units_in'] or 0
            period_map[period_key]['units_out'] += abs(item['units_out'] or 0)
            period_map[period_key]['movements_count'] += item['count']
        
        for item in sales_periods:
            period_date = item['period']
            period_key = period_date.strftime('%Y-%m-%d')
            
            if period_key not in period_map:
                period_map[period_key] = {
                    'period': period_key,
                    'period_start': period_date.strftime('%Y-%m-%d'),
                    'period_end': self._get_period_end(period_date, grouping).strftime('%Y-%m-%d'),
                    'units_in': 0,
                    'units_out': 0,
                    'net_change': 0,
                    'movements_count': 0
                }
            
            period_map[period_key]['units_out'] += item['units_sold'] or 0
            period_map[period_key]['movements_count'] += item['count']
        
        # Calculate net change
        for period_data in period_map.values():
            period_data['net_change'] = period_data['units_in'] - period_data['units_out']
        
        # Sort by period
        time_series = sorted(period_map.values(), key=lambda x: x['period'])
        
        return time_series
    
    def _build_movements(self, start_date, end_date, warehouse_id, product_id,
                        movement_type, adjustment_type, request) -> tuple:
        """Build detailed movements list with pagination"""
        movements = []
        
        # Get adjustments
        if movement_type in ['all', 'adjustments']:
            adjustments_qs = StockAdjustment.objects.filter(
                created_at__date__gte=start_date,
                created_at__date__lte=end_date,
                status='COMPLETED'
            ).select_related(
                'stock_product__product',
                'stock_product__warehouse',
                'created_by'
            )
            
            if warehouse_id:
                adjustments_qs = adjustments_qs.filter(stock_product__warehouse_id=warehouse_id)
            if product_id:
                adjustments_qs = adjustments_qs.filter(stock_product__product_id=product_id)
            if adjustment_type:
                adjustments_qs = adjustments_qs.filter(adjustment_type=adjustment_type)
            
            for adj in adjustments_qs.order_by('-created_at'):
                movements.append({
                    'movement_id': str(adj.id),
                    'movement_type': 'adjustment',
                    'adjustment_type': adj.adjustment_type,
                    'product_id': str(adj.stock_product.product.id),
                    'product_name': adj.stock_product.product.name,
                    'warehouse_id': str(adj.stock_product.warehouse.id),
                    'warehouse_name': adj.stock_product.warehouse.name,
                    'quantity_change': adj.quantity,
                    'unit_cost': str(adj.unit_cost),
                    'total_value': str(adj.total_cost) if adj.quantity < 0 else f"-{adj.total_cost}",
                    'reason': adj.reason,
                    'created_by': adj.created_by.name if adj.created_by else None,
                    'created_at': adj.created_at.isoformat()
                })
        
        # Get sales
        if movement_type in ['all', 'sales']:
            sales_qs = SaleItem.objects.filter(
                sale__created_at__date__gte=start_date,
                sale__created_at__date__lte=end_date,
                sale__status__in=['COMPLETED', 'PARTIAL']
            ).select_related(
                'product',
                'sale',
                'sale__user'
            )
            
            if product_id:
                sales_qs = sales_qs.filter(product_id=product_id)
            
            for sale_item in sales_qs.order_by('-sale__created_at'):
                movements.append({
                    'movement_id': str(sale_item.id),
                    'movement_type': 'sale',
                    'adjustment_type': None,
                    'product_id': str(sale_item.product.id),
                    'product_name': sale_item.product.name,
                    'warehouse_id': None,  # Sales don't track warehouse
                    'warehouse_name': None,
                    'quantity_change': -sale_item.quantity,
                    'unit_cost': str(sale_item.unit_price),
                    'total_value': f"-{sale_item.quantity * sale_item.unit_price}",
                    'reason': f"Sale #{sale_item.sale.id}",
                    'created_by': sale_item.sale.user.name if sale_item.sale.user else None,
                    'created_at': sale_item.sale.created_at.isoformat()
                })
        
        # Sort all movements by date descending
        movements.sort(key=lambda x: x['created_at'], reverse=True)
        
        # Apply pagination
        page, page_size = self.get_pagination_params(request)
        total_count = len(movements)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_movements = movements[start_idx:end_idx]
        
        pagination = {
            'page': page,
            'page_size': page_size,
            'total_count': total_count,
            'total_pages': (total_count + page_size - 1) // page_size
        }
        
        return paginated_movements, pagination
    
    def _get_period_end(self, period_start: date, grouping: str) -> date:
        """Calculate period end date based on grouping"""
        if grouping == 'daily':
            return period_start + timedelta(days=1)
        elif grouping == 'weekly':
            return period_start + timedelta(weeks=1)
        else:  # monthly
            if period_start.month == 12:
                return date(period_start.year + 1, 1, 1)
            else:
                return date(period_start.year, period_start.month + 1, 1)


class WarehouseAnalyticsReportView(BaseReportView):
    """
    Warehouse Analytics Report
    
    GET /reports/api/inventory/warehouse-analytics/
    
    Analyzes warehouse performance with turnover rates, product velocity,
    dead stock identification, and warehouse comparisons.
    
    Query Parameters:
    - warehouse_id: UUID (optional - specific warehouse)
    - start_date: YYYY-MM-DD (default: 90 days ago)
    - end_date: YYYY-MM-DD (default: today)
    - min_turnover_rate: float (optional - filter by minimum turnover)
    - max_turnover_rate: float (optional - filter by maximum turnover)
    
    Response Format:
    {
        "success": true,
        "data": {
            "summary": {
                "total_warehouses": 3,
                "total_products_stored": 250,
                "total_stock_value": "750000.00",
                "average_turnover_rate": 4.5
            },
            "warehouses": [...],
            "product_velocity": {...}
        },
        "meta": {...}
    }
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Generate warehouse analytics report"""
        # Get business ID
        business_id, error = self.get_business_or_error(request)
        if error:
            return ReportResponse.error(error)
        
        # Parse date range
        start_date, end_date, error = self.get_date_range(request, default_days=90)
        if error:
            return ReportResponse.error(error)
        
        # Parse filters
        warehouse_id = request.GET.get('warehouse_id')
        min_turnover = request.GET.get('min_turnover_rate')
        max_turnover = request.GET.get('max_turnover_rate')
        
        # Build summary
        summary = self._build_summary(start_date, end_date, warehouse_id)
        
        # Build warehouse analytics
        warehouses = self._build_warehouse_analytics(
            start_date, end_date, warehouse_id, min_turnover, max_turnover
        )
        
        # Build product velocity classification
        product_velocity = self._build_product_velocity(start_date, end_date, warehouse_id)
        
        # Combine summary with product velocity
        summary_data = {
            **summary,
            'product_velocity': product_velocity
        }
        
        # Metadata
        metadata = {
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'warehouse_id': warehouse_id,
            'min_turnover_rate': min_turnover,
            'max_turnover_rate': max_turnover
        }
        
        return ReportResponse.success(summary_data, warehouses, metadata)
    
    def _build_summary(self, start_date, end_date, warehouse_id) -> Dict[str, Any]:
        """Build overall summary"""
        # Get warehouse queryset
        warehouse_qs = Warehouse.objects.all()
        if warehouse_id:
            warehouse_qs = warehouse_qs.filter(id=warehouse_id)
        
        total_warehouses = warehouse_qs.count()
        
        # Get stock products
        stock_qs = StockProduct.objects.all()
        if warehouse_id:
            stock_qs = stock_qs.filter(warehouse_id=warehouse_id)
        
        total_products = stock_qs.values('product').distinct().count()
        
        stock_stats = stock_qs.aggregate(
            total_value=Sum(
                F('quantity') * (
                    F('unit_cost') + 
                    Coalesce(F('unit_tax_amount'), Value(0)) + 
                    Coalesce(F('unit_additional_cost'), Value(0))
                ),
                output_field=DecimalField()
            ),
            total_units=Sum('quantity')
        )
        
        # Calculate average turnover rate across all products
        turnover_rates = []
        for stock in stock_qs:
            turnover = self._calculate_turnover_rate(stock, start_date, end_date)
            if turnover is not None:
                turnover_rates.append(turnover)
        
        avg_turnover = sum(turnover_rates) / len(turnover_rates) if turnover_rates else 0
        
        # Calculate total dead stock
        dead_stock_value = self._calculate_dead_stock_value(stock_qs, start_date, end_date)
        
        return {
            'total_warehouses': total_warehouses,
            'total_products_stored': total_products,
            'total_stock_value': str(stock_stats['total_value'] or Decimal('0.00')),
            'total_stock_units': int(stock_stats['total_units'] or 0),
            'average_turnover_rate': round(avg_turnover, 2),
            'total_dead_stock_value': str(dead_stock_value)
        }
    
    def _build_warehouse_analytics(self, start_date, end_date, warehouse_id,
                                   min_turnover, max_turnover) -> List[Dict]:
        """Build warehouse-level analytics"""
        warehouse_qs = Warehouse.objects.all()
        if warehouse_id:
            warehouse_qs = warehouse_qs.filter(id=warehouse_id)
        
        warehouses = []
        
        for warehouse in warehouse_qs:
            # Get stock products for this warehouse
            stock_qs = warehouse.stock_products.all()
            
            if not stock_qs.exists():
                continue
            
            products_count = stock_qs.values('product').distinct().count()
            
            stock_stats = stock_qs.aggregate(
                total_units=Sum('quantity'),
                total_value=Sum(
                    F('quantity') * (
                        F('unit_cost') + 
                        Coalesce(F('unit_tax_amount'), Value(0)) + 
                        Coalesce(F('unit_additional_cost'), Value(0))
                    ),
                    output_field=DecimalField()
                )
            )
            
            # Calculate warehouse turnover rate
            turnover_rates = []
            product_details = []
            
            for stock in stock_qs:
                turnover = self._calculate_turnover_rate(stock, start_date, end_date)
                if turnover is not None:
                    turnover_rates.append(turnover)
                    product_details.append({
                        'product': stock.product,
                        'turnover': turnover,
                        'stock': stock
                    })
            
            warehouse_turnover = sum(turnover_rates) / len(turnover_rates) if turnover_rates else 0
            
            # Filter by turnover if specified
            if min_turnover and warehouse_turnover < float(min_turnover):
                continue
            if max_turnover and warehouse_turnover > float(max_turnover):
                continue
            
            # Get top 5 products
            top_products = sorted(product_details, key=lambda x: x['turnover'], reverse=True)[:5]
            
            # Get slow-moving products (turnover < 1)
            slow_moving = [p for p in product_details if p['turnover'] < 1]
            slow_moving.sort(key=lambda x: x['turnover'])
            
            # Get dead stock (no sales in period)
            dead_stock = [p for p in product_details if p['turnover'] == 0]
            dead_stock_value = sum(
                p['stock'].quantity * p['stock'].landed_unit_cost
                for p in dead_stock
            )
            
            # Build warehouse data
            warehouses.append({
                'warehouse_id': str(warehouse.id),
                'warehouse_name': warehouse.name,
                'location': warehouse.location,
                'products_count': products_count,
                'total_units': int(stock_stats['total_units'] or 0),
                'total_value': str(stock_stats['total_value'] or Decimal('0.00')),
                'turnover_rate': round(warehouse_turnover, 2),
                'top_products': [
                    {
                        'product_name': p['product'].name,
                        'sku': p['product'].sku,
                        'turnover_rate': round(p['turnover'], 2),
                        'stock_value': str(p['stock'].quantity * p['stock'].landed_unit_cost)
                    }
                    for p in top_products
                ],
                'slow_moving_products': [
                    {
                        'product_name': p['product'].name,
                        'sku': p['product'].sku,
                        'current_quantity': p['stock'].quantity,
                        'turnover_rate': round(p['turnover'], 2),
                        'stock_value': str(p['stock'].quantity * p['stock'].landed_unit_cost)
                    }
                    for p in slow_moving[:5]  # Top 5 slowest
                ],
                'dead_stock_value': str(dead_stock_value),
                'dead_stock_count': len(dead_stock)
            })
        
        return warehouses
    
    def _build_product_velocity(self, start_date, end_date, warehouse_id) -> Dict[str, int]:
        """Classify products by velocity (turnover rate)"""
        stock_qs = StockProduct.objects.all()
        if warehouse_id:
            stock_qs = stock_qs.filter(warehouse_id=warehouse_id)
        
        fast_moving = 0  # Turnover > 6
        medium_moving = 0  # Turnover 2-6
        slow_moving = 0  # Turnover 0.5-2
        dead_stock = 0  # Turnover < 0.5
        
        for stock in stock_qs:
            turnover = self._calculate_turnover_rate(stock, start_date, end_date)
            
            if turnover is None or turnover < 0.5:
                dead_stock += 1
            elif turnover < 2:
                slow_moving += 1
            elif turnover < 6:
                medium_moving += 1
            else:
                fast_moving += 1
        
        return {
            'fast_moving': fast_moving,
            'medium_moving': medium_moving,
            'slow_moving': slow_moving,
            'dead_stock': dead_stock
        }
    
    def _calculate_turnover_rate(self, stock_product: StockProduct, 
                                 start_date: date, end_date: date) -> float:
        """
        Calculate inventory turnover rate for a stock product.
        Turnover Rate = Units Sold / Average Inventory Level
        """
        # Get sales for this product in the period
        sales_stats = SaleItem.objects.filter(
            product=stock_product.product,
            sale__created_at__date__gte=start_date,
            sale__created_at__date__lte=end_date,
            sale__status__in=['COMPLETED', 'PARTIAL']
        ).aggregate(
            total_sold=Sum('quantity')
        )
        
        units_sold = float(sales_stats['total_sold'] or 0)
        
        if units_sold == 0:
            return 0.0
        
        # Average inventory level (simplified: current quantity)
        # In a more sophisticated system, this would be the average over the period
        avg_inventory = float(stock_product.quantity)
        
        if avg_inventory == 0:
            # If current stock is 0 but had sales, assume average was half of sold
            avg_inventory = units_sold / 2.0
        
        # Calculate turnover rate
        turnover_rate = units_sold / avg_inventory if avg_inventory > 0 else 0.0
        
        return turnover_rate
    
    def _calculate_dead_stock_value(self, queryset, start_date, end_date) -> Decimal:
        """Calculate total value of dead stock (no sales in period)"""
        dead_stock_value = Decimal('0.00')
        
        for stock in queryset:
            # Check if product had any sales in period
            sales_count = SaleItem.objects.filter(
                product=stock.product,
                sale__created_at__date__gte=start_date,
                sale__created_at__date__lte=end_date,
                sale__status__in=['COMPLETED', 'PARTIAL']
            ).count()
            
            if sales_count == 0:
                # Dead stock
                dead_stock_value += stock.quantity * stock.landed_unit_cost
        
        return dead_stock_value
