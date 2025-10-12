"""
Sales Analytical Reports

Endpoints for sales analysis and insights.
"""

from decimal import Decimal
from typing import Dict, Any, List
from django.db.models import Sum, Count, Avg, Q, F
from rest_framework.permissions import IsAuthenticated

from sales.models import Sale, SaleItem, Payment
from reports.services.report_base import BaseReportView
from reports.utils.response import ReportResponse, ReportError
from reports.utils.aggregation import AggregationHelper, PercentageCalculator


class SalesSummaryReportView(BaseReportView):
    """
    Sales Summary Report
    
    GET /reports/api/sales/summary/
    
    Query Parameters:
    - start_date: YYYY-MM-DD (default: 30 days ago)
    - end_date: YYYY-MM-DD (default: today)
    - storefront_id: UUID (optional)
    - sale_type: RETAIL or WHOLESALE (optional)
    
    Returns:
    - Total sales count and revenue
    - Average order value
    - Sales by payment method
    - Sales by type (retail/wholesale)
    - Daily breakdown
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        # Get business ID
        business_id, error = self.get_business_or_error(request)
        if error:
            return ReportResponse.error(error)
        
        # Get date range
        start_date, end_date, error = self.get_date_range(request)
        if error:
            return ReportResponse.error(error)
        
        # Get base queryset
        queryset = Sale.objects.filter(business_id=business_id)
        
        # Apply date filter
        queryset = queryset.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
        
        # Apply optional filters
        storefront_id = request.query_params.get('storefront_id')
        if storefront_id:
            queryset = queryset.filter(storefront_id=storefront_id)
        
        sale_type = request.query_params.get('sale_type')
        if sale_type and sale_type in ['RETAIL', 'WHOLESALE']:
            queryset = queryset.filter(sale_type=sale_type)
        
        # Only completed sales
        queryset = queryset.filter(status='COMPLETED')
        
        # Build summary
        summary = self._build_summary(queryset)
        
        # Build results (daily breakdown)
        results = self._build_daily_breakdown(queryset)
        
        # Build metadata
        metadata = self.build_metadata(
            start_date=start_date,
            end_date=end_date,
            filters={
                'storefront_id': storefront_id,
                'sale_type': sale_type,
            }
        )
        
        return ReportResponse.success(summary, results, metadata)
    
    def _build_summary(self, queryset) -> Dict[str, Any]:
        """Build summary metrics"""
        
        # Total sales and revenue
        total_sales = queryset.count()
        total_revenue = AggregationHelper.sum_field(queryset, 'total_amount')
        
        # Average order value
        avg_order_value = AggregationHelper.avg_field(queryset, 'total_amount')
        
        # Sales by payment method
        payment_breakdown = self._get_payment_breakdown(queryset)
        
        # Sales by type
        type_breakdown = self._get_type_breakdown(queryset)
        
        # Total items sold
        total_items = SaleItem.objects.filter(
            sale__in=queryset
        ).aggregate(
            total=Sum('quantity')
        )['total'] or 0
        
        # Total profit (if available)
        total_profit = AggregationHelper.sum_field(queryset, 'total_profit')
        
        # Profit margin
        profit_margin = AggregationHelper.calculate_percentage(
            total_profit, total_revenue
        ) if total_revenue > 0 else Decimal('0.00')
        
        return {
            'total_sales': total_sales,
            'total_revenue': float(total_revenue),
            'total_profit': float(total_profit),
            'profit_margin': float(profit_margin),
            'average_order_value': float(avg_order_value),
            'total_items_sold': total_items,
            'payment_methods': payment_breakdown,
            'sales_by_type': type_breakdown,
        }
    
    def _get_payment_breakdown(self, queryset) -> List[Dict[str, Any]]:
        """Get sales breakdown by payment method"""
        
        # Get all payments for these sales
        payments = Payment.objects.filter(sale__in=queryset)
        
        # Group by payment method
        breakdown = list(
            payments.values('payment_method')
            .annotate(
                count=Count('id'),
                total=Sum('amount')
            )
            .order_by('-total')
        )
        
        # Calculate percentages
        total = sum(Decimal(str(item['total'])) for item in breakdown)
        for item in breakdown:
            item['total'] = float(item['total'])
            item['percentage'] = float(
                AggregationHelper.calculate_percentage(
                    Decimal(str(item['total'])),
                    total
                )
            )
        
        return breakdown
    
    def _get_type_breakdown(self, queryset) -> List[Dict[str, Any]]:
        """Get sales breakdown by sale type"""
        
        breakdown = list(
            queryset.values('sale_type')
            .annotate(
                count=Count('id'),
                total=Sum('total_amount')
            )
            .order_by('-total')
        )
        
        # Calculate percentages
        total = sum(Decimal(str(item['total'] or 0)) for item in breakdown)
        for item in breakdown:
            item['total'] = float(item['total'] or 0)
            item['percentage'] = float(
                AggregationHelper.calculate_percentage(
                    Decimal(str(item['total'])),
                    total
                )
            ) if total > 0 else 0.0
        
        return breakdown
    
    def _build_daily_breakdown(self, queryset) -> List[Dict[str, Any]]:
        """Build daily sales breakdown"""
        
        daily_data = AggregationHelper.group_by_date(
            queryset,
            date_field='created_at',
            value_field='total_amount',
            aggregation='sum'
        )
        
        # Add count and average
        for item in daily_data:
            date_sales = queryset.filter(created_at__date=item['date'])
            item['count'] = date_sales.count()
            item['revenue'] = float(item.pop('value', 0))
            item['average'] = float(
                item['revenue'] / item['count'] if item['count'] > 0 else 0
            )
            item['date'] = str(item['date'])
        
        return daily_data


class ProductPerformanceReportView(BaseReportView):
    """
    Product Performance Report
    
    GET /reports/api/sales/products/
    
    Query Parameters:
    - start_date: YYYY-MM-DD (default: 30 days ago)
    - end_date: YYYY-MM-DD (default: today)
    - storefront_id: UUID (optional)
    - limit: int (default: 50, max: 500)
    - sort_by: revenue, quantity, profit (default: revenue)
    
    Returns:
    - Top selling products by revenue/quantity
    - Product profit analysis
    - Performance metrics per product
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        # Get business ID
        business_id, error = self.get_business_or_error(request)
        if error:
            return ReportResponse.error(error)
        
        # Get date range
        start_date, end_date, error = self.get_date_range(request)
        if error:
            return ReportResponse.error(error)
        
        # Get pagination params
        page, page_size = self.get_pagination_params(request)
        
        # Get sort parameter
        sort_by = request.query_params.get('sort_by', 'revenue')
        if sort_by not in ['revenue', 'quantity', 'profit']:
            sort_by = 'revenue'
        
        # Get base queryset - SaleItems from completed sales
        queryset = SaleItem.objects.filter(
            sale__business_id=business_id,
            sale__status='COMPLETED',
            sale__created_at__date__gte=start_date,
            sale__created_at__date__lte=end_date
        )
        
        # Apply optional filters
        storefront_id = request.query_params.get('storefront_id')
        if storefront_id:
            queryset = queryset.filter(sale__storefront_id=storefront_id)
        
        # Build summary
        summary = self._build_summary(queryset)
        
        # Build results (product performance)
        results, total_count = self._build_product_performance(
            queryset, sort_by, page, page_size
        )
        
        # Build metadata
        metadata = self.build_metadata(
            start_date=start_date,
            end_date=end_date,
            filters={
                'storefront_id': storefront_id,
                'sort_by': sort_by,
            }
        )
        
        return ReportResponse.paginated(
            summary, results, metadata, page, page_size, total_count
        )
    
    def _build_summary(self, queryset) -> Dict[str, Any]:
        """Build summary metrics"""
        
        total_products = queryset.values('product').distinct().count()
        total_items_sold = AggregationHelper.sum_field(queryset, 'quantity')
        total_revenue = AggregationHelper.sum_field(queryset, 'total_price')
        total_profit = AggregationHelper.sum_field(queryset, 'profit')
        
        profit_margin = AggregationHelper.calculate_percentage(
            total_profit, total_revenue
        ) if total_revenue > 0 else Decimal('0.00')
        
        return {
            'total_products_sold': total_products,
            'total_items_sold': float(total_items_sold),
            'total_revenue': float(total_revenue),
            'total_profit': float(total_profit),
            'overall_profit_margin': float(profit_margin),
        }
    
    def _build_product_performance(
        self, queryset, sort_by: str, page: int, page_size: int
    ) -> tuple[List[Dict[str, Any]], int]:
        """Build product performance breakdown"""
        
        # Aggregate by product
        product_data = queryset.values(
            'product__id',
            'product__name',
            'product__sku'
        ).annotate(
            quantity_sold=Sum('quantity'),
            revenue=Sum('total_price'),
            profit=Sum('profit'),
            times_sold=Count('sale', distinct=True)
        )
        
        # Calculate profit margin for each
        results = []
        for item in product_data:
            revenue = Decimal(str(item['revenue'] or 0))
            profit = Decimal(str(item['profit'] or 0))
            
            profit_margin = AggregationHelper.calculate_percentage(
                profit, revenue
            ) if revenue > 0 else Decimal('0.00')
            
            results.append({
                'product_id': str(item['product__id']),
                'product_name': item['product__name'],
                'sku': item['product__sku'],
                'quantity_sold': float(item['quantity_sold']),
                'revenue': float(revenue),
                'profit': float(profit),
                'profit_margin': float(profit_margin),
                'times_sold': item['times_sold'],
            })
        
        # Sort by requested field
        sort_field = {
            'revenue': 'revenue',
            'quantity': 'quantity_sold',
            'profit': 'profit',
        }[sort_by]
        
        results = sorted(results, key=lambda x: x[sort_field], reverse=True)
        
        # Paginate
        total_count = len(results)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_results = results[start:end]
        
        # Add rank
        for idx, item in enumerate(paginated_results, start=start + 1):
            item['rank'] = idx
        
        return paginated_results, total_count


class CustomerAnalyticsReportView(BaseReportView):
    """
    Customer Analytics Report (via Sales)
    
    GET /reports/api/sales/customer-analytics/
    
    Placeholder - Will be implemented in Customer Reports module
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        return ReportResponse.error(
            ReportError.create(
                'NOT_IMPLEMENTED',
                'This report will be implemented in Phase 5: Customer Reports',
                {}
            )
        )


class RevenueTrendsReportView(BaseReportView):
    """
    Revenue Trends Report
    
    GET /reports/api/sales/revenue-trends/
    
    Placeholder - Will enhance in Phase 3: Financial Reports
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        return ReportResponse.error(
            ReportError.create(
                'NOT_IMPLEMENTED',
                'This report will be fully implemented in Phase 3: Financial Reports',
                {}
            )
        )
