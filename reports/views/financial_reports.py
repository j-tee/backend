"""
Financial Analytical Reports

Endpoints for financial analysis and insights.
Tier 1 Implementation: Using existing sales, payment, and credit data.
"""

from decimal import Decimal
from typing import Dict, Any, List
from datetime import timedelta, date
from django.db.models import Sum, Count, Avg, Q, F, Min, Max
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated

from sales.models import Sale, SaleItem, Payment, Customer
from reports.services.report_base import BaseReportView
from reports.utils.response import ReportResponse, ReportError
from reports.utils.aggregation import AggregationHelper


class RevenueProfitReportView(BaseReportView):
    """
    Revenue & Profit Analysis Report
    
    GET /reports/api/financial/revenue-profit/
    
    Query Parameters:
    - start_date: YYYY-MM-DD (default: 30 days ago)
    - end_date: YYYY-MM-DD (default: today)
    - storefront_id: UUID (optional)
    - sale_type: RETAIL or WHOLESALE (optional)
    - grouping: daily, weekly, monthly (default: monthly)
    
    Returns:
    - Total revenue and profit metrics
    - Gross profit margins
    - Revenue breakdown by type
    - Time-series profit analysis
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        # Get business ID
        business_id, error = self.get_business_or_error(request)
        if error:
            return ReportResponse.error(error)
        
        # Get date range
        start_date, end_date, error = self.get_date_range(request, max_days=365)
        if error:
            return ReportResponse.error(error)
        
        # Get grouping parameter
        grouping = request.query_params.get('grouping', 'monthly')
        if grouping not in ['daily', 'weekly', 'monthly']:
            grouping = 'monthly'
        
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
        
        sale_type = request.query_params.get('sale_type')
        if sale_type and sale_type in ['RETAIL', 'WHOLESALE']:
            queryset = queryset.filter(sale_type=sale_type)
        
        # Build summary
        summary = self._build_summary(queryset)
        
        # Build results (time-series)
        results = self._build_time_series(queryset, grouping)
        
        # Build metadata
        metadata = self.build_metadata(
            start_date=start_date,
            end_date=end_date,
            filters={
                'storefront_id': storefront_id,
                'sale_type': sale_type,
                'grouping': grouping,
            }
        )
        
        return ReportResponse.success(summary, results, metadata)
    
    def _build_summary(self, queryset) -> Dict[str, Any]:
        """Build summary metrics"""
        
        # Get aggregated totals
        totals = queryset.aggregate(
            revenue=Sum('total_amount'),
            profit=Sum('total_profit'),
            count=Count('id')
        )
        
        total_revenue = Decimal(str(totals['revenue'] or 0))
        total_profit = Decimal(str(totals['profit'] or 0))
        total_count = totals['count']
        
        # Calculate COGS (Cost of Goods Sold)
        total_cost = total_revenue - total_profit
        
        # Calculate margins
        gross_margin = AggregationHelper.calculate_percentage(
            total_profit, total_revenue
        ) if total_revenue > 0 else Decimal('0.00')
        
        # Revenue by sale type
        revenue_by_type = {}
        type_breakdown = queryset.values('sale_type').annotate(
            revenue=Sum('total_amount'),
            profit=Sum('total_profit')
        )
        for item in type_breakdown:
            sale_type = item['sale_type'] or 'UNKNOWN'
            revenue_by_type[sale_type] = {
                'revenue': float(item['revenue'] or 0),
                'profit': float(item['profit'] or 0),
                'margin': float(
                    AggregationHelper.calculate_percentage(
                        Decimal(str(item['profit'] or 0)),
                        Decimal(str(item['revenue'] or 0))
                    )
                ) if item['revenue'] else 0.0
            }
        
        # Find best and worst margins
        sales_with_margins = queryset.exclude(
            total_amount=0
        ).annotate(
            margin=F('total_profit') * 100.0 / F('total_amount')
        )
        
        best_margin = sales_with_margins.aggregate(Max('margin'))['margin__max'] or 0
        worst_margin = sales_with_margins.aggregate(Min('margin'))['margin__min'] or 0
        
        return {
            'total_revenue': float(total_revenue),
            'total_cost': float(total_cost),
            'gross_profit': float(total_profit),
            'gross_margin': float(gross_margin),
            'net_profit': float(total_profit),  # Same as gross for now (no expenses)
            'net_margin': float(gross_margin),  # Same as gross for now
            'total_sales': total_count,
            'average_sale_value': float(
                total_revenue / total_count if total_count > 0 else 0
            ),
            'revenue_by_type': revenue_by_type,
            'best_margin': float(best_margin),
            'worst_margin': float(worst_margin),
        }
    
    def _build_time_series(self, queryset, grouping: str) -> List[Dict[str, Any]]:
        """Build time-series profit analysis"""
        
        # Select truncation function
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
                profit=Sum('total_profit'),
                count=Count('id')
            )
            .order_by('period')
        )
        
        # Format results
        results = []
        for item in time_series:
            revenue = Decimal(str(item['revenue'] or 0))
            profit = Decimal(str(item['profit'] or 0))
            cost = revenue - profit
            count = item['count']
            
            margin = AggregationHelper.calculate_percentage(
                profit, revenue
            ) if revenue > 0 else Decimal('0.00')
            
            results.append({
                'period': item['period'].date().isoformat() if item['period'] else None,
                'revenue': float(revenue),
                'cost': float(cost),
                'profit': float(profit),
                'margin': float(margin),
                'order_count': count,
                'average_order_value': float(revenue / count if count > 0 else 0),
            })
        
        return results


class ARAgingReportView(BaseReportView):
    """
    Accounts Receivable Aging Report
    
    GET /reports/api/financial/ar-aging/
    
    Query Parameters:
    - as_of_date: YYYY-MM-DD (default: today)
    - customer_id: UUID (optional)
    - min_balance: Decimal (optional - filter small balances)
    - page, page_size (pagination)
    
    Returns:
    - Total AR outstanding
    - Aging buckets (Current, 1-30, 31-60, 61-90, 90+)
    - Customer-level aging breakdown
    - Credit utilization
    - Risk levels
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        # Get business ID
        business_id, error = self.get_business_or_error(request)
        if error:
            return ReportResponse.error(error)
        
        # Get as-of date
        as_of_str = request.query_params.get('as_of_date')
        if as_of_str:
            from reports.utils.date_utils import DateRangeValidator
            as_of_date = DateRangeValidator.parse_date(as_of_str)
            if not as_of_date:
                error = ReportError.create(
                    ReportError.INVALID_FILTER,
                    "Invalid as_of_date format. Use YYYY-MM-DD",
                    {'as_of_date': as_of_str}
                )
                return ReportResponse.error(error)
        else:
            as_of_date = timezone.now().date()
        
        # Get pagination params
        page, page_size = self.get_pagination_params(request)
        
        # Get minimum balance filter
        min_balance = request.query_params.get('min_balance', '0')
        try:
            min_balance = Decimal(min_balance)
        except:
            min_balance = Decimal('0')
        
        # Get customers with credit balances
        customers_query = Customer.objects.filter(
            business_id=business_id,
            credit_balance__gt=min_balance
        ).select_related('business')
        
        # Apply optional customer filter
        customer_id = request.query_params.get('customer_id')
        if customer_id:
            customers_query = customers_query.filter(id=customer_id)
        
        # Build aging data
        aging_data = []
        total_ar = Decimal('0')
        aging_totals = {
            'current': Decimal('0'),
            '1_30_days': Decimal('0'),
            '31_60_days': Decimal('0'),
            '61_90_days': Decimal('0'),
            'over_90_days': Decimal('0'),
        }
        
        for customer in customers_query:
            # Get customer's credit transactions to determine aging
            # For now, we'll use a simplified approach based on credit_balance
            # In a full implementation, we'd track individual invoices/transactions
            
            balance = customer.credit_balance
            if balance <= 0:
                continue
            
            total_ar += balance
            
            # Simplified aging: distribute balance across buckets
            # In reality, you'd track each credit transaction separately
            # For now, assume all balance is in "current" bucket
            # This is a placeholder that should be enhanced with actual transaction tracking
            
            aging_buckets = self._calculate_aging_buckets(
                customer, as_of_date, balance
            )
            
            for bucket, amount in aging_buckets.items():
                aging_totals[bucket] += amount
            
            # Calculate risk level
            risk_level = self._calculate_risk_level(
                aging_buckets, balance, customer.credit_limit
            )
            
            # Calculate credit utilization
            utilization = AggregationHelper.calculate_percentage(
                balance,
                customer.credit_limit
            ) if customer.credit_limit > 0 else Decimal('100.00')
            
            aging_data.append({
                'customer_id': str(customer.id),
                'customer_name': customer.name,
                'customer_email': customer.email,
                'total_balance': float(balance),
                'credit_limit': float(customer.credit_limit),
                'credit_utilization': float(utilization),
                'current': float(aging_buckets['current']),
                '1_30_days': float(aging_buckets['1_30_days']),
                '31_60_days': float(aging_buckets['31_60_days']),
                '61_90_days': float(aging_buckets['61_90_days']),
                'over_90_days': float(aging_buckets['over_90_days']),
                'risk_level': risk_level,
            })
        
        # Sort by balance descending
        aging_data.sort(key=lambda x: x['total_balance'], reverse=True)
        
        # Build summary
        total_customers = len(aging_data)
        percentage_overdue = AggregationHelper.calculate_percentage(
            aging_totals['31_60_days'] + aging_totals['61_90_days'] + aging_totals['over_90_days'],
            total_ar
        ) if total_ar > 0 else Decimal('0.00')
        
        at_risk_amount = aging_totals['61_90_days'] + aging_totals['over_90_days']
        
        summary = {
            'as_of_date': str(as_of_date),
            'total_ar_outstanding': float(total_ar),
            'total_customers_with_balance': total_customers,
            'aging_buckets': {
                'current': float(aging_totals['current']),
                '1_30_days': float(aging_totals['1_30_days']),
                '31_60_days': float(aging_totals['31_60_days']),
                '61_90_days': float(aging_totals['61_90_days']),
                'over_90_days': float(aging_totals['over_90_days']),
            },
            'percentage_overdue': float(percentage_overdue),
            'at_risk_amount': float(at_risk_amount),
        }
        
        # Paginate
        total_count = len(aging_data)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_results = aging_data[start:end]
        
        # Add rank
        for idx, item in enumerate(paginated_results, start=start + 1):
            item['rank'] = idx
        
        # Build metadata
        metadata = self.build_metadata(
            start_date=as_of_date,
            end_date=as_of_date,
            filters={
                'customer_id': customer_id,
                'min_balance': float(min_balance),
            }
        )
        
        return ReportResponse.paginated(
            summary, paginated_results, metadata, page, page_size, total_count
        )
    
    def _calculate_aging_buckets(
        self, customer, as_of_date: date, balance: Decimal
    ) -> Dict[str, Decimal]:
        """
        Calculate aging buckets for customer balance
        
        NOTE: This is a simplified implementation.
        In a full system, you'd track individual credit transactions
        and age each one separately based on its transaction date.
        """
        
        # For now, put all balance in "current" bucket
        # This should be enhanced to track actual transaction dates
        buckets = {
            'current': balance,
            '1_30_days': Decimal('0'),
            '31_60_days': Decimal('0'),
            '61_90_days': Decimal('0'),
            'over_90_days': Decimal('0'),
        }
        
        # TODO: Enhance with actual transaction-level aging
        # Query credit transactions, calculate days old for each
        # Distribute balance across buckets based on transaction dates
        
        return buckets
    
    def _calculate_risk_level(
        self, aging_buckets: Dict[str, Decimal], balance: Decimal, credit_limit: Decimal
    ) -> str:
        """Calculate customer risk level"""
        
        overdue_60_plus = aging_buckets['61_90_days'] + aging_buckets['over_90_days']
        utilization = (balance / credit_limit * 100) if credit_limit > 0 else 100
        
        # High risk: significant overdue or over limit
        if overdue_60_plus > balance * Decimal('0.25') or utilization > 100:
            return 'high'
        
        # Medium risk: some overdue or high utilization
        overdue_30_plus = aging_buckets['31_60_days'] + overdue_60_plus
        if overdue_30_plus > balance * Decimal('0.1') or utilization > 80:
            return 'medium'
        
        # Low risk
        return 'low'


class CollectionRatesReportView(BaseReportView):
    """
    Collection Rates Report
    
    GET /reports/api/financial/collection-rates/
    
    Tracks how effectively credit sales are being collected.
    Measures collection rate, average collection period, and trends.
    
    Query Parameters:
    - start_date: YYYY-MM-DD (default: 90 days ago)
    - end_date: YYYY-MM-DD (default: today)
    - storefront_id: int (optional)
    - grouping: daily|weekly|monthly (default: monthly)
    
    Response Format:
    {
        "success": true,
        "data": {
            "summary": {
                "total_credit_sales_amount": "50000.00",
                "total_collected_amount": "42000.00",
                "outstanding_amount": "8000.00",
                "overall_collection_rate": 84.0,
                "average_collection_period_days": 25.5,
                "total_credit_sales_count": 150,
                "collected_sales_count": 120,
                "outstanding_sales_count": 30
            },
            "time_series": [
                {
                    "period": "2024-01",
                    "period_start": "2024-01-01",
                    "period_end": "2024-01-31",
                    "credit_sales_amount": "15000.00",
                    "collected_amount": "12000.00",
                    "collection_rate": 80.0,
                    "average_days_to_collect": 22.3
                }
            ]
        },
        "meta": {
            "date_range": {"start": "...", "end": "..."},
            "grouping": "monthly",
            "storefront_id": null
        }
    }
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Generate collection rates report"""
        # Parse filters
        filters = self.parse_filters(request)
        start_date = filters.get('start_date', timezone.now().date() - timedelta(days=90))
        end_date = filters.get('end_date', timezone.now().date())
        storefront_id = filters.get('storefront_id')
        grouping = request.GET.get('grouping', 'monthly')
        
        # Build queryset for credit sales
        queryset = Sale.objects.filter(
            sale_type='credit',
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
        
        if storefront_id:
            queryset = queryset.filter(storefront_id=storefront_id)
        
        # Build summary
        summary = self._build_summary(queryset)
        
        # Build time series
        time_series = self._build_time_series(queryset, grouping, start_date, end_date)
        
        return ReportResponse.success({
            'summary': summary,
            'time_series': time_series
        }, meta={
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'grouping': grouping,
            'storefront_id': storefront_id
        })
    
    def _build_summary(self, queryset) -> Dict[str, Any]:
        """Build summary statistics for collection rates"""
        # Get all credit sales in period
        total_stats = queryset.aggregate(
            total_amount=Sum('total_amount'),
            total_count=Count('id')
        )
        
        # Get collected amounts (sales with payments)
        collected_stats = queryset.filter(
            payment_status__in=['paid', 'partial']
        ).aggregate(
            collected_amount=Sum('amount_paid'),
            collected_count=Count('id')
        )
        
        total_amount = total_stats['total_amount'] or Decimal('0.00')
        total_count = total_stats['total_count'] or 0
        collected_amount = collected_stats['collected_amount'] or Decimal('0.00')
        collected_count = collected_stats['collected_count'] or 0
        outstanding_amount = total_amount - collected_amount
        outstanding_count = total_count - collected_count
        
        # Calculate collection rate
        collection_rate = (
            float(collected_amount / total_amount * 100)
            if total_amount > 0 else 0.0
        )
        
        # Calculate average collection period
        # For sales with payments, calculate days between sale and last payment
        avg_days = self._calculate_average_collection_period(queryset)
        
        return {
            'total_credit_sales_amount': str(total_amount),
            'total_collected_amount': str(collected_amount),
            'outstanding_amount': str(outstanding_amount),
            'overall_collection_rate': round(collection_rate, 2),
            'average_collection_period_days': round(avg_days, 1),
            'total_credit_sales_count': total_count,
            'collected_sales_count': collected_count,
            'outstanding_sales_count': outstanding_count
        }
    
    def _calculate_average_collection_period(self, queryset) -> float:
        """Calculate average days to collect payment"""
        # Get sales with at least one payment
        sales_with_payments = queryset.filter(
            payment_status__in=['paid', 'partial']
        ).prefetch_related('payment_set')
        
        total_days = 0
        count = 0
        
        for sale in sales_with_payments:
            # Get last payment date
            last_payment = sale.payment_set.order_by('-payment_date').first()
            if last_payment:
                days_to_collect = (last_payment.payment_date - sale.created_at.date()).days
                total_days += days_to_collect
                count += 1
        
        return total_days / count if count > 0 else 0.0
    
    def _build_time_series(self, queryset, grouping: str, start_date: date, end_date: date) -> List[Dict]:
        """Build time-series breakdown of collection rates"""
        # Determine truncation function
        if grouping == 'daily':
            trunc_func = TruncDate
        elif grouping == 'weekly':
            trunc_func = TruncWeek
        else:  # monthly
            trunc_func = TruncMonth
        
        # Group sales by period
        period_data = queryset.annotate(
            period=trunc_func('created_at')
        ).values('period').annotate(
            credit_sales_amount=Sum('total_amount'),
            credit_sales_count=Count('id')
        ).order_by('period')
        
        # For each period, calculate collection metrics
        time_series = []
        for period_item in period_data:
            period_date = period_item['period']
            
            # Get collected amount for this period's sales
            period_sales = queryset.filter(
                created_at__date__gte=period_date,
                created_at__date__lt=self._get_period_end(period_date, grouping)
            )
            
            collected_stats = period_sales.filter(
                payment_status__in=['paid', 'partial']
            ).aggregate(
                collected_amount=Sum('amount_paid')
            )
            
            collected_amount = collected_stats['collected_amount'] or Decimal('0.00')
            credit_sales_amount = period_item['credit_sales_amount'] or Decimal('0.00')
            
            collection_rate = (
                float(collected_amount / credit_sales_amount * 100)
                if credit_sales_amount > 0 else 0.0
            )
            
            # Calculate average days for this period
            avg_days = self._calculate_average_collection_period(period_sales)
            
            time_series.append({
                'period': period_date.strftime('%Y-%m-%d' if grouping == 'daily' else '%Y-%m-%d'),
                'period_start': period_date.strftime('%Y-%m-%d'),
                'period_end': self._get_period_end(period_date, grouping).strftime('%Y-%m-%d'),
                'credit_sales_amount': str(credit_sales_amount),
                'collected_amount': str(collected_amount),
                'collection_rate': round(collection_rate, 2),
                'average_days_to_collect': round(avg_days, 1)
            })
        
        return time_series
    
    def _get_period_end(self, period_start: date, grouping: str) -> date:
        """Calculate period end date based on grouping"""
        if grouping == 'daily':
            return period_start + timedelta(days=1)
        elif grouping == 'weekly':
            return period_start + timedelta(weeks=1)
        else:  # monthly
            # Get first day of next month
            if period_start.month == 12:
                return date(period_start.year + 1, 1, 1)
            else:
                return date(period_start.year, period_start.month + 1, 1)


class CashFlowReportView(BaseReportView):
    """
    Cash Flow Report
    
    GET /reports/api/financial/cash-flow/
    
    Tracks cash inflows (payments received) over time.
    Note: Tier 1 implementation - only tracks inflows (no expense/outflow tracking yet)
    
    Query Parameters:
    - start_date: YYYY-MM-DD (default: 30 days ago)
    - end_date: YYYY-MM-DD (default: today)
    - storefront_id: int (optional)
    - grouping: daily|weekly|monthly (default: daily)
    - payment_method: cash|card|bank_transfer|mobile_money (optional)
    
    Response Format:
    {
        "success": true,
        "data": {
            "summary": {
                "total_inflows": "125000.00",
                "total_outflows": "0.00",
                "net_cash_flow": "125000.00",
                "opening_balance": "0.00",
                "closing_balance": "125000.00",
                "inflow_by_method": {
                    "cash": "50000.00",
                    "card": "40000.00",
                    "bank_transfer": "25000.00",
                    "mobile_money": "10000.00"
                },
                "inflow_by_type": {
                    "cash_sales": "80000.00",
                    "credit_payments": "45000.00"
                }
            },
            "time_series": [
                {
                    "period": "2024-01-15",
                    "period_start": "2024-01-15",
                    "period_end": "2024-01-16",
                    "inflows": "5000.00",
                    "outflows": "0.00",
                    "net_flow": "5000.00",
                    "running_balance": "5000.00",
                    "transaction_count": 25
                }
            ]
        },
        "meta": {
            "date_range": {"start": "...", "end": "..."},
            "grouping": "daily",
            "storefront_id": null,
            "payment_method": null,
            "note": "Tier 1: Only tracking inflows (payments). Outflows will be added in Tier 2."
        }
    }
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Generate cash flow report"""
        # Parse filters
        filters = self.parse_filters(request)
        start_date = filters.get('start_date', timezone.now().date() - timedelta(days=30))
        end_date = filters.get('end_date', timezone.now().date())
        storefront_id = filters.get('storefront_id')
        grouping = request.GET.get('grouping', 'daily')
        payment_method = request.GET.get('payment_method')
        
        # Build queryset for payments (inflows)
        queryset = Payment.objects.filter(
            payment_date__gte=start_date,
            payment_date__lte=end_date
        )
        
        if storefront_id:
            queryset = queryset.filter(sale__storefront_id=storefront_id)
        
        if payment_method:
            queryset = queryset.filter(payment_method=payment_method)
        
        # Build summary
        summary = self._build_summary(queryset)
        
        # Build time series
        time_series = self._build_time_series(queryset, grouping, start_date, end_date)
        
        return ReportResponse.success({
            'summary': summary,
            'time_series': time_series
        }, meta={
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'grouping': grouping,
            'storefront_id': storefront_id,
            'payment_method': payment_method,
            'note': 'Tier 1: Only tracking inflows (payments). Outflows will be added in Tier 2.'
        })
    
    def _build_summary(self, queryset) -> Dict[str, Any]:
        """Build summary cash flow statistics"""
        # Total inflows
        total_inflows = queryset.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        # Inflows by payment method
        inflow_by_method = {}
        method_breakdown = queryset.values('payment_method').annotate(
            total=Sum('amount')
        )
        for item in method_breakdown:
            inflow_by_method[item['payment_method']] = str(item['total'])
        
        # Ensure all methods are represented
        for method in ['cash', 'card', 'bank_transfer', 'mobile_money']:
            if method not in inflow_by_method:
                inflow_by_method[method] = '0.00'
        
        # Inflows by sale type (cash sales vs credit payments)
        cash_sales_amount = queryset.filter(
            sale__sale_type='cash'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        credit_payments_amount = queryset.filter(
            sale__sale_type='credit'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Note: No outflows in Tier 1
        total_outflows = Decimal('0.00')
        net_cash_flow = total_inflows - total_outflows
        
        # Note: We don't track opening balance in Tier 1
        # This would require bank account/cash drawer tracking
        opening_balance = Decimal('0.00')
        closing_balance = opening_balance + net_cash_flow
        
        return {
            'total_inflows': str(total_inflows),
            'total_outflows': str(total_outflows),
            'net_cash_flow': str(net_cash_flow),
            'opening_balance': str(opening_balance),
            'closing_balance': str(closing_balance),
            'inflow_by_method': inflow_by_method,
            'inflow_by_type': {
                'cash_sales': str(cash_sales_amount),
                'credit_payments': str(credit_payments_amount)
            }
        }
    
    def _build_time_series(self, queryset, grouping: str, start_date: date, end_date: date) -> List[Dict]:
        """Build time-series cash flow breakdown"""
        # Determine truncation function
        if grouping == 'daily':
            trunc_func = TruncDate
        elif grouping == 'weekly':
            trunc_func = TruncWeek
        else:  # monthly
            trunc_func = TruncMonth
        
        # Group payments by period
        period_data = queryset.annotate(
            period=trunc_func('payment_date')
        ).values('period').annotate(
            inflows=Sum('amount'),
            transaction_count=Count('id')
        ).order_by('period')
        
        # Build time series with running balance
        running_balance = Decimal('0.00')
        time_series = []
        
        for period_item in period_data:
            period_date = period_item['period']
            inflows = period_item['inflows'] or Decimal('0.00')
            outflows = Decimal('0.00')  # Tier 1: no outflows
            net_flow = inflows - outflows
            running_balance += net_flow
            
            time_series.append({
                'period': period_date.strftime('%Y-%m-%d'),
                'period_start': period_date.strftime('%Y-%m-%d'),
                'period_end': self._get_period_end(period_date, grouping).strftime('%Y-%m-%d'),
                'inflows': str(inflows),
                'outflows': str(outflows),
                'net_flow': str(net_flow),
                'running_balance': str(running_balance),
                'transaction_count': period_item['transaction_count']
            })
        
        return time_series
    
    def _get_period_end(self, period_start: date, grouping: str) -> date:
        """Calculate period end date based on grouping"""
        if grouping == 'daily':
            return period_start + timedelta(days=1)
        elif grouping == 'weekly':
            return period_start + timedelta(weeks=1)
        else:  # monthly
            # Get first day of next month
            if period_start.month == 12:
                return date(period_start.year + 1, 1, 1)
            else:
                return date(period_start.year, period_start.month + 1, 1)
