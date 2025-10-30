"""
Inventory Analytical Reports

Endpoints for inventory management and warehouse analytics.
Tracks stock levels, movements, low stock alerts, and warehouse performance.
"""

from decimal import Decimal
from typing import Dict, Any, List
from datetime import timedelta, date, datetime
from django.db.models import Sum, Count, Avg, Q, F, Min, Max, DecimalField, Case, When, Value
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth, Coalesce
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from inventory.models import Product, StockProduct, Warehouse, Category, Supplier
from inventory.stock_adjustments import StockAdjustment
from sales.models import Sale, SaleItem
from reports.services.report_base import BaseReportView
from reports.services import MovementTracker  # Phase 3: Use MovementTracker
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
            'pagination': pagination
        }
        
        # Return simplified structure matching frontend expectations
        from rest_framework.response import Response
        
        return Response({
            'success': True,
            'data': {
                'summary': summary,
                'items': stock_levels
            },
            'meta': metadata
        })
    
    def _build_summary(self, queryset) -> Dict[str, Any]:
        """Build overall summary statistics"""
        # Get unique products
        products = queryset.values('product').distinct()
        total_products = products.count()
        
        # Get warehouse count
        warehouses_count = queryset.values('warehouse').distinct().count()
        
        # Aggregate totals using unit_cost
        totals = queryset.aggregate(
            total_units=Sum('quantity'),
            total_value=Sum(
                F('quantity') * F('unit_cost'),
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
        from django.db.models import Sum, Q
        from datetime import datetime, timedelta
        from sales.models import SaleItem
        
        # PRE-CALCULATE: Get all reservations grouped by product (PERFORMANCE OPTIMIZATION)
        # This prevents querying reservations N times in the loop
        reservations_by_product = {}
        all_product_ids = queryset.values_list('product_id', flat=True).distinct()
        
        reservation_data = SaleItem.objects.filter(
            product_id__in=all_product_ids,
            sale__status__in=['DRAFT', 'PENDING']
        ).values('product_id').annotate(
            total_reserved=Sum('quantity')
        )
        
        for item in reservation_data:
            reservations_by_product[str(item['product_id'])] = item['total_reserved']
        
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
                    'total_available': 0,  # Will be calculated after proportional distribution
                    'locations': [],  # Renamed from 'warehouses'
                    'is_low_stock': False,
                    'is_out_of_stock': False,
                    'last_restocked': None,  # New field
                    'days_until_stockout': None,  # New field
                    '_total_reserved': reservations_by_product.get(product_id, 0),  # Total reserved for this product
                    '_total_stock': 0  # Total stock across all warehouses (for proportional calc)
                }
            
            # Track total stock for this product (needed for proportional distribution)
            product_stocks[product_id]['_total_stock'] += stock.quantity
            
            # NOTE: reserved and available will be calculated AFTER the loop
            # using proportional distribution to ensure math consistency
            
            # Get reorder point (default to 10 if not set on product)
            reorder_point = getattr(stock.product, 'reorder_point', 10)
            
            # Determine status for this location (will be recalculated after reserved is set)
            if stock.quantity == 0:
                location_status = 'out_of_stock'
            elif stock.quantity < reorder_point:
                location_status = 'low_stock'
            else:
                location_status = 'in_stock'
            
            # Add location entry (reserved and available will be set in second pass)
            warehouse_value = stock.quantity * stock.unit_cost
            product_stocks[product_id]['locations'].append({
                'warehouse_id': str(stock.warehouse.id),
                'warehouse_name': stock.warehouse.name,
                'quantity': stock.quantity,
                'reserved': 0,  # Placeholder - will be calculated in second pass
                'available': stock.quantity,  # Placeholder - will be calculated in second pass
                'reorder_point': reorder_point,
                'status': location_status,
                'unit_cost': str(stock.unit_cost),
                'value': str(warehouse_value),
                'supplier': stock.supplier.name if stock.supplier else None
            })
            
            # Update totals
            product_stocks[product_id]['total_quantity'] += stock.quantity
            product_stocks[product_id]['total_value'] += warehouse_value
            
            # Track last restocked date (most recent stock record for this product)
            if stock.created_at:
                if (product_stocks[product_id]['last_restocked'] is None or 
                    stock.created_at > product_stocks[product_id]['last_restocked']):
                    product_stocks[product_id]['last_restocked'] = stock.created_at
        
        # SECOND PASS: Distribute reservations proportionally across warehouses
        # This ensures: total_quantity = total_available + total_reserved (math consistency)
        for product_data in product_stocks.values():
            total_reserved = product_data['_total_reserved']
            total_stock = product_data['_total_stock']
            total_available = 0
            
            if total_stock > 0 and total_reserved > 0:
                # Distribute reservations proportionally based on each warehouse's stock share
                for location in product_data['locations']:
                    warehouse_qty = location['quantity']
                    proportion = warehouse_qty / total_stock
                    location['reserved'] = int(total_reserved * proportion)
                    location['available'] = max(0, warehouse_qty - location['reserved'])
                    total_available += location['available']
                    
                    # Update status based on available quantity
                    if location['available'] == 0:
                        location['status'] = 'out_of_stock'
                    elif location['available'] < location['reorder_point']:
                        location['status'] = 'low_stock'
                    else:
                        location['status'] = 'in_stock'
            elif total_stock > 0:
                # No reservations - all stock is available
                for location in product_data['locations']:
                    location['reserved'] = 0
                    location['available'] = location['quantity']
                    total_available += location['available']
            
            # Set total available
            product_data['total_available'] = total_available
            
            # Clean up internal tracking fields
            del product_data['_total_reserved']
            del product_data['_total_stock']
        
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
                        product__id=product_data['product_id'],
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
        
        return paginated_data, pagination

class LowStockAlertsReportView(BaseReportView):
    """
    Low Stock Alerts Report
    
    GET /reports/api/inventory/low-stock-alerts/
    
    Identifies products that need reordering based on current stock levels
    and sales velocity. Provides reorder recommendations and urgency levels.
    
    Query Parameters:
    - search: str (optional - search by product name or SKU)
    - warehouse_id: UUID (optional - filter by warehouse)
    - category_id: UUID (optional - filter by category)
    - urgency: critical|warning|watch (optional - filter by urgency)
    - sort_by: urgency|days_remaining|value (optional - default: urgency)
    - days_threshold: int (default: 30 - alert if < X days of stock)
    - page: int (pagination)
    - page_size: int (pagination, default: 20)
    
    Response Format:
    {
        "success": true,
        "data": {
            "summary": {
                "critical": 3,
                "warning": 7,
                "watch": 5
            },
            "alerts": [...],
            "total_restock_cost": 12345.50,
            "by_warehouse": {...},
            "by_category": {...}
        },
        "meta": {
            "pagination": {...}
        }
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
        search_term = request.GET.get('search', '').strip()
        warehouse_id = request.GET.get('warehouse_id')
        category_id = request.GET.get('category_id')
        urgency_filter = request.GET.get('urgency')  # critical|warning|watch
        sort_by = request.GET.get('sort_by', 'urgency')  # urgency|days_remaining|value
        days_threshold = int(request.GET.get('days_threshold', 30))
        
        # Build queryset for stock products
        queryset = StockProduct.objects.select_related(
            'product', 'warehouse', 'product__category', 'supplier'
        ).filter(
            product__business_id=business_id,
            quantity__gt=0  # Only products with some stock
        ).distinct()
        
        # Apply search filter
        if search_term:
            queryset = queryset.filter(
                Q(product__name__icontains=search_term) |
                Q(product__sku__icontains=search_term)
            )
        
        if warehouse_id:
            queryset = queryset.filter(warehouse_id=warehouse_id)
        if category_id:
            queryset = queryset.filter(product__category_id=category_id)
        
        # Build alerts with sales velocity
        all_alerts = self._build_alerts(queryset, days_threshold)
        
        # Filter by urgency if specified
        if urgency_filter:
            all_alerts = [a for a in all_alerts if a['urgency'] == urgency_filter]
        
        # Apply sorting
        all_alerts = self._apply_sorting(all_alerts, sort_by)
        
        # Build summary
        summary = self._build_summary(all_alerts)
        
        # Build warehouse and category groupings
        by_warehouse = self._build_warehouse_grouping(all_alerts)
        by_category = self._build_category_grouping(all_alerts)
        
        # Apply pagination
        page, page_size = self.get_pagination_params(request)
        total_count = len(all_alerts)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_alerts = all_alerts[start_idx:end_idx]
        
        # Calculate total restock cost
        total_restock_cost = sum(
            Decimal(alert['estimated_cost'])
            for alert in all_alerts
        )
        
        # Build response data
        data = {
            'summary': summary,
            'alerts': paginated_alerts,
            'total_restock_cost': str(total_restock_cost),
            'by_warehouse': by_warehouse,
            'by_category': by_category
        }
        
        # Build metadata with nested pagination
        metadata = {
            'pagination': {
                'page': page,
                'page_size': page_size,
                'total_count': total_count,
                'total_pages': (total_count + page_size - 1) // page_size
            }
        }
        
        # Return custom Response to match frontend expectations
        return Response({
            'success': True,
            'data': data,
            'meta': metadata
        })
    
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
            
            # Determine urgency (matching frontend expectations)
            if days_until_stockout < 5 or stock.quantity < 5:
                urgency = 'critical'  # Red alert
            elif days_until_stockout < 14:
                urgency = 'warning'   # Orange/amber alert
            elif days_until_stockout < days_threshold:
                urgency = 'watch'     # Yellow/blue alert
            else:
                continue  # Not a low stock alert
            
            # Calculate recommended order quantity
            # Order enough for 30 days + safety stock (10 days)
            recommended_qty = int((avg_daily_sales * Decimal('40')) - Decimal(str(stock.quantity))) if avg_daily_sales > 0 else 50
            recommended_qty = max(recommended_qty, 10)  # Minimum order of 10
            
            # Get latest restock date
            last_restock_date = stock.created_at.date()
            
            # Calculate lead time and suggested order date (simplified)
            lead_time_days = 7  # Default lead time
            if stock.supplier:
                # Could pull from supplier.lead_time_days if that field exists
                lead_time_days = getattr(stock.supplier, 'lead_time_days', 7)
            
            # Suggested order date = today if critical, or (stockout_date - lead_time) otherwise
            if urgency == 'critical':
                suggested_order_date = timezone.now().date()
            else:
                days_before_order = max(0, int(days_until_stockout) - lead_time_days)
                suggested_order_date = timezone.now().date() + timedelta(days=days_before_order)
            
            alerts.append({
                'product_id': product_id,
                'product_name': stock.product.name,
                'sku': stock.product.sku,
                'category_id': str(stock.product.category.id) if stock.product.category else None,
                'category_name': stock.product.category.name if stock.product.category else 'Uncategorized',
                'warehouse_id': str(stock.warehouse.id),
                'warehouse_name': stock.warehouse.name,
                'current_stock': int(stock.quantity),
                'reorder_point': 20,  # Simplified, could be product-specific
                'reorder_quantity': recommended_qty,
                'urgency': urgency,
                'average_daily_sales': round(float(avg_daily_sales), 2),
                'days_until_stockout': round(float(days_until_stockout), 1),
                'last_restock_date': last_restock_date.isoformat(),
                'supplier': stock.supplier.name if stock.supplier else 'No Supplier',
                'lead_time_days': lead_time_days,
                'suggested_order_date': suggested_order_date.isoformat(),
                'estimated_cost': str(stock.unit_cost * recommended_qty)
            })
        
        return alerts
    
    def _apply_sorting(self, alerts: List[Dict], sort_by: str) -> List[Dict]:
        """Apply sorting to alerts"""
        if sort_by == 'urgency':
            # Sort by urgency (critical first) then by days until stockout
            urgency_order = {'critical': 0, 'warning': 1, 'watch': 2}
            alerts.sort(key=lambda x: (urgency_order[x['urgency']], x['days_until_stockout']))
        elif sort_by == 'days_remaining':
            # Sort by days until stockout (lowest first)
            alerts.sort(key=lambda x: x['days_until_stockout'])
        elif sort_by == 'value':
            # Sort by estimated cost (highest first)
            alerts.sort(key=lambda x: Decimal(x['estimated_cost']), reverse=True)
        
        return alerts
    
    def _build_summary(self, alerts: List[Dict]) -> Dict[str, Any]:
        """Build summary statistics (matching frontend expectations)"""
        critical = [a for a in alerts if a['urgency'] == 'critical']
        warning = [a for a in alerts if a['urgency'] == 'warning']
        watch = [a for a in alerts if a['urgency'] == 'watch']
        
        return {
            'critical': len(critical),
            'warning': len(warning),
            'watch': len(watch)
        }
    
    def _build_warehouse_grouping(self, alerts: List[Dict]) -> Dict[str, Any]:
        """Group alerts by warehouse for filter dropdown"""
        warehouse_groups = {}
        
        for alert in alerts:
            warehouse_id = alert['warehouse_id']
            if warehouse_id not in warehouse_groups:
                warehouse_groups[warehouse_id] = {
                    'name': alert['warehouse_name'],
                    'alerts': 0,
                    'restock_cost': Decimal('0')
                }
            
            warehouse_groups[warehouse_id]['alerts'] += 1
            warehouse_groups[warehouse_id]['restock_cost'] += Decimal(alert['estimated_cost'])
        
        # Convert Decimal to string for JSON serialization
        for warehouse_id in warehouse_groups:
            warehouse_groups[warehouse_id]['restock_cost'] = str(
                warehouse_groups[warehouse_id]['restock_cost']
            )
        
        return warehouse_groups
    
    def _build_category_grouping(self, alerts: List[Dict]) -> Dict[str, Any]:
        """Group alerts by category for filter dropdown"""
        category_groups = {}
        
        for alert in alerts:
            category_id = alert.get('category_id')
            if not category_id:
                continue
            
            if category_id not in category_groups:
                category_groups[category_id] = {
                    'name': alert['category_name'],
                    'alerts': 0,
                    'restock_cost': Decimal('0')
                }
            
            category_groups[category_id]['alerts'] += 1
            category_groups[category_id]['restock_cost'] += Decimal(alert['estimated_cost'])
        
        # Convert Decimal to string for JSON serialization
        for category_id in category_groups:
            category_groups[category_id]['restock_cost'] = str(
                category_groups[category_id]['restock_cost']
            )
        
        return category_groups
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
        
        # Parse filters
        search_term = request.GET.get('search', '').strip()
        warehouse_id = request.GET.get('warehouse_id')
        category_id = request.GET.get('category_id')
        product_id = request.GET.get('product_id')
        movement_type = request.GET.get('movement_type', 'all')
        adjustment_type = request.GET.get('adjustment_type')
        sort_by = request.GET.get('sort_by', 'date_desc')  # date_desc|date_asc|quantity|product
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
        
        # Build warehouse and category groupings for filters
        by_warehouse = self._build_warehouse_grouping(movements)
        by_category = self._build_category_grouping(movements)
        
        # Build response data
        data = {
            'summary': summary,
            'movements': movements,
            'time_series': time_series,
            'by_warehouse': by_warehouse,
            'by_category': by_category
        }
        
        # Build metadata with nested pagination
        metadata = {
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'pagination': pagination
        }
        
        # Return custom Response to match frontend expectations
        return Response({
            'success': True,
            'data': data,
            'meta': metadata
        })
    
    def _build_summary(self, start_date, end_date, warehouse_id, product_id,
                      movement_type, adjustment_type) -> Dict[str, Any]:
        """Build summary of all movements using MovementTracker (Phase 3)"""
        # Use MovementTracker to get unified summary
        summary = MovementTracker.get_summary(
            business_id=str(self.request.user.primary_business.id),
            warehouse_id=warehouse_id,
            product_id=product_id,
            start_date=start_date,
            end_date=end_date
        )
        
        # Calculate shrinkage percentage
        shrinkage_pct = 0
        if summary['total_quantity_out'] > 0:
            shrinkage_pct = (summary.get('shrinkage_count', 0) / summary['total_quantity_out'] * 100)
        
        return {
            'total_movements': summary['total_movements'],
            'total_units_in': summary['total_quantity_in'],
            'total_units_out': summary['total_quantity_out'],
            'net_change': summary['net_quantity'],
            'value_in': str(summary['total_value_in']),
            'value_out': str(summary['total_value_out']),
            'net_value_change': str(summary['net_value']),
            'movement_breakdown': {
                'transfers': summary.get('transfers_count', 0),
                'sales': summary.get('sales_count', 0),
                'shrinkage': summary.get('shrinkage_count', 0),
            },
            'shrinkage': {
                'total_units': summary.get('shrinkage_count', 0),
                'total_value': str(abs(summary.get('shrinkage_value', 0))),
                'percentage_of_outbound': round(shrinkage_pct, 2)
            }
        }
    
    def _build_time_series(self, start_date, end_date, warehouse_id, product_id,
                          movement_type, grouping) -> List[Dict]:
        """Build time-series breakdown of movements using MovementTracker (Phase 3)"""
        from datetime import timedelta
        from collections import defaultdict
        
        # Get all movements using MovementTracker
        movements_data = MovementTracker.get_movements(
            business_id=str(self.request.user.primary_business.id),
            warehouse_id=warehouse_id,
            product_id=product_id,
            start_date=start_date,
            end_date=end_date,
            movement_types=None  # Get all types, filter later
        )
        
        # Group movements by period
        period_map = defaultdict(lambda: {
            'units_in': 0,
            'units_out': 0,
            'movements_count': 0
        })
        
        for movement in movements_data:
            # Apply movement_type filter
            if movement_type == 'sales' and movement['type'] != 'SALE':
                continue
            if movement_type == 'adjustments' and movement['type'] not in ['TRANSFER', 'ADJUSTMENT', 'SHRINKAGE']:
                continue
            
            # Parse movement date
            movement_date = datetime.fromisoformat(movement['date'].replace('Z', '+00:00')).date()
            
            # Determine period based on grouping
            if grouping == 'daily':
                period_start = movement_date
            elif grouping == 'weekly':
                # Week starts on Monday
                period_start = movement_date - timedelta(days=movement_date.weekday())
            else:  # monthly
                period_start = movement_date.replace(day=1)
            
            period_key = period_start.strftime('%Y-%m-%d')
            
            # Aggregate quantities
            quantity = movement['quantity']
            if movement['direction'] == 'in':
                period_map[period_key]['units_in'] += quantity
            else:
                period_map[period_key]['units_out'] += abs(quantity)
            
            period_map[period_key]['movements_count'] += 1
        
        # Build time series with period boundaries
        time_series = []
        for period_key, data in sorted(period_map.items()):
            period_date = datetime.strptime(period_key, '%Y-%m-%d').date()
            time_series.append({
                'period': period_key,
                'period_start': period_key,
                'period_end': self._get_period_end(period_date, grouping).strftime('%Y-%m-%d'),
                'units_in': data['units_in'],
                'units_out': data['units_out'],
                'net_change': data['units_in'] - data['units_out'],
                'movements_count': data['movements_count']
            })
        
        return time_series
    
    def _build_movements(self, start_date, end_date, warehouse_id, product_id,
                        movement_type, adjustment_type, request,
                        search_term=None, category_id=None, sort_by='date_desc') -> tuple:
        """Build list of individual movements using MovementTracker (Phase 3)"""
        # Use MovementTracker to get unified movements
        movements_data = MovementTracker.get_movements(
            business_id=str(self.request.user.primary_business.id),
            warehouse_id=warehouse_id,
            product_id=product_id,
            start_date=start_date,
            end_date=end_date,
            movement_types=None  # Get all types, filter later
        )
        
        # Transform to frontend format
        movements = []
        for movement in movements_data:
            # Apply movement_type filter
            if movement_type == 'sales' and movement['type'] != 'SALE':
                continue
            if movement_type == 'adjustments' and movement['type'] not in ['TRANSFER', 'ADJUSTMENT', 'SHRINKAGE']:
                continue
            
            # Apply search filter
            if search_term:
                search_lower = search_term.lower()
                if (search_lower not in movement.get('product_name', '').lower() and
                    search_lower not in movement.get('product_sku', '').lower()):
                    continue
            
            # Format movement for frontend
            formatted = {
                'movement_id': movement['id'],
                'product_id': movement.get('product_id'),
                'product_name': movement.get('product_name'),
                'sku': movement.get('product_sku'),
                'category_id': movement.get('category_id'),
                'category_name': movement.get('category'),
                'warehouse_id': movement.get('source_location') if movement['direction'] == 'out' else movement.get('destination_location'),
                'warehouse_name': movement.get('source_location') if movement['direction'] == 'out' else movement.get('destination_location'),
                'movement_type': movement['type'].lower(),
                'quantity': movement['quantity'],
                'quantity_before': None,  # Not available in MovementTracker
                'quantity_after': None,   # Not available in MovementTracker
                'reference_type': movement['source_type'],
                'reference_id': movement['id'],
                'performed_by': movement.get('created_by'),
                'performed_by_id': None,  # Not available in current MovementTracker
                'notes': movement.get('reason'),
                'created_at': movement['date'],
            }
            movements.append(formatted)
        
        # Apply sorting
        if sort_by == 'date_desc':
            movements.sort(key=lambda x: x['created_at'], reverse=True)
        elif sort_by == 'date_asc':
            movements.sort(key=lambda x: x['created_at'])
        elif sort_by == 'quantity':
            movements.sort(key=lambda x: abs(x['quantity']), reverse=True)
        elif sort_by == 'product':
            movements.sort(key=lambda x: x['product_name'] or '')
        
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
    
    def _build_warehouse_grouping(self, movements: list) -> dict:
        """Group movements by warehouse for filter dropdown"""
        warehouse_groups = {}
        for movement in movements:
            warehouse_id = movement.get('warehouse_id')
            if not warehouse_id:
                continue
            if warehouse_id not in warehouse_groups:
                warehouse_groups[warehouse_id] = {
                    'name': movement['warehouse_name'],
                    'movements': 0
                }
            warehouse_groups[warehouse_id]['movements'] += 1
        return warehouse_groups

    def _build_category_grouping(self, movements: list) -> dict:
        """Group movements by category for filter dropdown"""
        category_groups = {}
        for movement in movements:
            category_id = movement.get('category_id')
            if not category_id:
                continue
            if category_id not in category_groups:
                category_groups[category_id] = {
                    'name': movement['category_name'],
                    'movements': 0
                }
            category_groups[category_id]['movements'] += 1
        return category_groups
    
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
                p['stock'].quantity * p['stock'].unit_cost
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
                        'stock_value': str(p['stock'].quantity * p['stock'].unit_cost)
                    }
                    for p in top_products
                ],
                'slow_moving_products': [
                    {
                        'product_name': p['product'].name,
                        'sku': p['product'].sku,
                        'current_quantity': p['stock'].quantity,
                        'turnover_rate': round(p['turnover'], 2),
                        'stock_value': str(p['stock'].quantity * p['stock'].unit_cost)
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
                dead_stock_value += stock.quantity * stock.unit_cost
        
        return dead_stock_value
