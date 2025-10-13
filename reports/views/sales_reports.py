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
from reports.utils.profit_calculator import ProfitCalculator


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
            queryset = queryset.filter(type=sale_type)
        
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
        
        # Calculate profit using the same logic as sales summary
        total_profit = ProfitCalculator.calculate_total_profit(queryset)
        
        # Profit margin
        profit_margin = ProfitCalculator.calculate_profit_margin(total_profit, total_revenue)
        
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
                total=Sum('amount_paid')
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
            queryset.values('type')
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
        
        # Note: Profit calculation for individual SaleItems is complex because it requires
        # looking up cost from StockProduct. For now, we'll return 0 or calculate it
        # differently. The sales-level profit is more accurate via ProfitCalculator.
        total_profit = Decimal('0.00')  # TODO: Implement SaleItem-level profit calculation
        
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
            times_sold=Count('sale', distinct=True)
        )
        
        # Calculate profit margin for each
        # Note: Profit calculation requires cost lookup from StockProduct,
        # which is complex in aggregation. Returning 0 for now.
        results = []
        for item in product_data:
            revenue = Decimal(str(item['revenue'] or 0))
            profit = Decimal('0.00')  # TODO: Implement product-level profit calculation
            
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
    
    Query Parameters:
    - start_date: YYYY-MM-DD (default: 30 days ago)
    - end_date: YYYY-MM-DD (default: today)
    - storefront_id: UUID (optional)
    - sort_by: revenue, frequency, avg_order, recency (default: revenue)
    - page, page_size (pagination)
    
    Returns:
    - Top customers by purchase metrics
    - Customer purchase frequency
    - Average order value per customer
    - Recency analysis
    - Customer contribution percentages
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        from django.db.models import Min, Max
        from django.utils import timezone
        
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
        if sort_by not in ['revenue', 'frequency', 'avg_order', 'recency']:
            sort_by = 'revenue'
        
        # Get base queryset - completed sales with customers
        queryset = Sale.objects.filter(
            business_id=business_id,
            status='COMPLETED',
            customer__isnull=False,  # Only sales with customers
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
        
        # Apply optional filters
        storefront_id = request.query_params.get('storefront_id')
        if storefront_id:
            queryset = queryset.filter(storefront_id=storefront_id)
        
        # Aggregate by customer
        customer_data = queryset.values(
            'customer__id',
            'customer__name',
            'customer__email',
        ).annotate(
            total_spent=Sum('total_amount'),
            order_count=Count('id'),
            first_purchase=Min('created_at'),
            last_purchase=Max('created_at')
        )
        
        # Build summary
        total_customers = customer_data.count()
        total_revenue = AggregationHelper.sum_field(queryset, 'total_amount')
        total_orders = queryset.count()
        
        avg_revenue_per_customer = AggregationHelper.safe_divide(
            total_revenue,
            Decimal(str(total_customers))
        ) if total_customers > 0 else Decimal('0.00')
        
        avg_orders_per_customer = total_orders / total_customers if total_customers > 0 else 0
        
        # Calculate repeat customer rate
        repeat_customers = sum(1 for c in customer_data if c['order_count'] > 1)
        repeat_rate = AggregationHelper.calculate_percentage(
            Decimal(str(repeat_customers)),
            Decimal(str(total_customers))
        ) if total_customers > 0 else Decimal('0.00')
        
        summary = {
            'total_customers': total_customers,
            'total_revenue': float(total_revenue),
            'total_orders': total_orders,
            'average_revenue_per_customer': float(avg_revenue_per_customer),
            'average_orders_per_customer': round(avg_orders_per_customer, 2),
            'repeat_customer_rate': float(repeat_rate),
        }
        
        # Build results with calculated fields
        results = []
        for item in customer_data:
            total_spent = Decimal(str(item['total_spent'] or 0))
            order_count = item['order_count']
            
            avg_order_value = AggregationHelper.safe_divide(
                total_spent,
                Decimal(str(order_count))
            )
            
            contribution_pct = AggregationHelper.calculate_percentage(
                total_spent,
                total_revenue
            ) if total_revenue > 0 else Decimal('0.00')
            
            # Calculate days since last purchase
            last_purchase = item['last_purchase']
            if last_purchase:
                days_since = (timezone.now().date() - last_purchase.date()).days
            else:
                days_since = None
            
            results.append({
                'customer_id': str(item['customer__id']),
                'customer_name': item['customer__name'],
                'customer_email': item['customer__email'],
                'total_spent': float(total_spent),
                'order_count': order_count,
                'average_order_value': float(avg_order_value),
                'contribution_percentage': float(contribution_pct),
                'first_purchase_date': item['first_purchase'].date().isoformat() if item['first_purchase'] else None,
                'last_purchase_date': item['last_purchase'].date().isoformat() if item['last_purchase'] else None,
                'days_since_last_purchase': days_since,
            })
        
        # Sort by requested field
        sort_field_map = {
            'revenue': 'total_spent',
            'frequency': 'order_count',
            'avg_order': 'average_order_value',
            'recency': 'days_since_last_purchase',
        }
        sort_field = sort_field_map[sort_by]
        
        # For recency, sort ascending (most recent first)
        reverse = (sort_by != 'recency')
        
        # Handle None values in recency sorting
        if sort_by == 'recency':
            results = sorted(
                results,
                key=lambda x: x[sort_field] if x[sort_field] is not None else float('inf'),
                reverse=False
            )
        else:
            results = sorted(results, key=lambda x: x[sort_field], reverse=reverse)
        
        # Paginate
        total_count = len(results)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_results = results[start:end]
        
        # Add rank
        for idx, item in enumerate(paginated_results, start=start + 1):
            item['rank'] = idx
        
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
            summary, paginated_results, metadata, page, page_size, total_count
        )


class RevenueTrendsReportView(BaseReportView):
    """
    Revenue Trends Report
    
    GET /reports/api/sales/revenue-trends/
    
    Query Parameters:
    - start_date: YYYY-MM-DD (default: 30 days ago)
    - end_date: YYYY-MM-DD (default: today)
    - storefront_id: UUID (optional)
    - grouping: daily, weekly, monthly (default: daily)
    - compare: boolean (default: false) - compare to previous period
    
    Returns:
    - Time-series revenue data
    - Growth rates
    - Trend indicators
    - Comparison with previous period (if requested)
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
        from datetime import timedelta
        
        # Get business ID
        business_id, error = self.get_business_or_error(request)
        if error:
            return ReportResponse.error(error)
        
        # Get date range
        start_date, end_date, error = self.get_date_range(request, max_days=365)
        if error:
            return ReportResponse.error(error)
        
        # Get grouping parameter
        grouping = request.query_params.get('grouping', 'daily')
        if grouping not in ['daily', 'weekly', 'monthly']:
            grouping = 'daily'
        
        # Get comparison flag
        compare = request.query_params.get('compare', '').lower() == 'true'
        
        # Get base queryset
        queryset = Sale.objects.filter(
            business_id=business_id,
            status='COMPLETED',
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
        
        # Apply optional filters
        storefront_id = request.query_params.get('storefront_id')
        if storefront_id:
            queryset = queryset.filter(storefront_id=storefront_id)
        
        # Get previous period data if comparison requested
        previous_data = None
        if compare:
            duration = (end_date - start_date).days
            prev_end = start_date - timedelta(days=1)
            prev_start = prev_end - timedelta(days=duration)
            
            prev_queryset = Sale.objects.filter(
                business_id=business_id,
                status='COMPLETED',
                created_at__date__gte=prev_start,
                created_at__date__lte=prev_end
            )
            if storefront_id:
                prev_queryset = prev_queryset.filter(storefront_id=storefront_id)
            
            previous_data = {
                'start_date': prev_start,
                'end_date': prev_end,
                'queryset': prev_queryset
            }
        
        # Build summary
        summary = self._build_summary(queryset, start_date, end_date, previous_data)
        
        # Build results (time-series data)
        results = self._build_time_series(queryset, grouping, start_date, end_date)
        
        # Build metadata
        metadata = self.build_metadata(
            start_date=start_date,
            end_date=end_date,
            filters={
                'storefront_id': storefront_id,
                'grouping': grouping,
                'compare_to_previous': compare,
            }
        )
        
        return ReportResponse.success(summary, results, metadata)
    
    def _build_summary(
        self, queryset, start_date, end_date, previous_data
    ) -> Dict[str, Any]:
        """Build summary metrics"""
        
        total_revenue = AggregationHelper.sum_field(queryset, 'total_amount')
        total_orders = queryset.count()
        total_profit = ProfitCalculator.calculate_total_profit(queryset)
        
        # Calculate averages
        days_in_period = (end_date - start_date).days + 1
        avg_daily_revenue = AggregationHelper.safe_divide(
            total_revenue,
            Decimal(str(days_in_period))
        )
        
        avg_order_value = AggregationHelper.safe_divide(
            total_revenue,
            Decimal(str(total_orders))
        ) if total_orders > 0 else Decimal('0.00')
        
        # Find peak day
        daily_sales = queryset.extra(
            select={'date': 'DATE(created_at)'}
        ).values('date').annotate(
            revenue=Sum('total_amount')
        ).order_by('-revenue').first()
        
        peak_day = daily_sales['date'] if daily_sales else None
        peak_revenue = Decimal(str(daily_sales['revenue'])) if daily_sales else Decimal('0.00')
        
        summary = {
            'period_start': str(start_date),
            'period_end': str(end_date),
            'total_revenue': float(total_revenue),
            'total_profit': float(total_profit),
            'total_orders': total_orders,
            'average_daily_revenue': float(avg_daily_revenue),
            'average_order_value': float(avg_order_value),
            'peak_day': str(peak_day) if peak_day else None,
            'peak_revenue': float(peak_revenue),
        }
        
        # Add comparison if previous period data provided
        if previous_data:
            prev_revenue = AggregationHelper.sum_field(
                previous_data['queryset'], 'total_amount'
            )
            prev_orders = previous_data['queryset'].count()
            prev_profit = ProfitCalculator.calculate_total_profit(previous_data['queryset'])
            
            revenue_growth = AggregationHelper.calculate_growth_rate(
                total_revenue, prev_revenue
            )
            order_growth = AggregationHelper.calculate_growth_rate(
                Decimal(str(total_orders)), Decimal(str(prev_orders))
            )
            profit_growth = AggregationHelper.calculate_growth_rate(
                total_profit, prev_profit
            )
            
            summary['previous_period'] = {
                'start': str(previous_data['start_date']),
                'end': str(previous_data['end_date']),
                'revenue': float(prev_revenue),
                'profit': float(prev_profit),
                'orders': prev_orders,
            }
            
            summary['comparison'] = {
                'revenue_growth': float(revenue_growth),
                'order_growth': float(order_growth),
                'profit_growth': float(profit_growth),
                'revenue_change': float(total_revenue - prev_revenue),
                'order_change': total_orders - prev_orders,
            }
        
        return summary
    
    def _build_time_series(
        self, queryset, grouping: str, start_date, end_date
    ) -> List[Dict[str, Any]]:
        """Build time-series data"""
        
        from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
        
        # Select truncation function based on grouping
        trunc_func = {
            'daily': TruncDate('created_at'),
            'weekly': TruncWeek('created_at'),
            'monthly': TruncMonth('created_at'),
        }[grouping]
        
        # Group by period
        time_series = list(
            queryset
            .annotate(period=trunc_func)
            .values('period')
            .annotate(
                revenue=Sum('total_amount'),
                order_count=Count('id')
            )
            .order_by('period')
        )
        
        # Calculate profit for each period
        # Note: We need to calculate profit separately for each period since it's not a direct field
        period_profits = {}
        for item in time_series:
            period = item['period']
            
            # Filter sales for this period based on grouping type
            if grouping == 'daily':
                # period is already a date object from TruncDate
                period_sales = queryset.filter(created_at__date=period)
            elif grouping == 'weekly':
                # For weekly, filter by the week start date (period is a datetime)
                period_sales = queryset.annotate(week=TruncWeek('created_at')).filter(week=period)
            elif grouping == 'monthly':
                # For monthly, filter by the month start date (period is a datetime)
                period_sales = queryset.annotate(month=TruncMonth('created_at')).filter(month=period)
            else:
                # Default to daily filtering
                period_sales = queryset.filter(created_at__date=period)
            
            period_profits[str(period)] = ProfitCalculator.calculate_total_profit(period_sales)
        
        # Format results
        results = []
        prev_revenue = None
        
        for idx, item in enumerate(time_series):
            revenue = Decimal(str(item['revenue'] or 0))
            profit = period_profits.get(str(item['period']), Decimal('0.00'))
            order_count = item['order_count']
            
            # Calculate profit margin
            profit_margin = AggregationHelper.calculate_percentage(
                profit, revenue
            ) if revenue > 0 else Decimal('0.00')
            
            # Calculate period-over-period growth
            growth_rate = None
            if prev_revenue is not None and prev_revenue > 0:
                growth_rate = float(
                    AggregationHelper.calculate_growth_rate(revenue, prev_revenue)
                )
            
            # Determine trend
            trend = 'stable'
            if growth_rate is not None:
                if growth_rate > 5:
                    trend = 'up'
                elif growth_rate < -5:
                    trend = 'down'
            
            result = {
                'period': item['period'].date().isoformat() if item['period'] else None,
                'revenue': float(revenue),
                'profit': float(profit),
                'profit_margin': float(profit_margin),
                'order_count': order_count,
                'average_order_value': float(
                    revenue / order_count if order_count > 0 else 0
                ),
            }
            
            if growth_rate is not None:
                result['growth_rate'] = growth_rate
                result['trend'] = trend
            
            results.append(result)
            prev_revenue = revenue
        
        return results

