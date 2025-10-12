"""
Customer Analytical Reports

Endpoints for customer analytics and relationship management.
Tracks customer lifetime value, segmentation, purchase patterns, and retention metrics.
"""

from decimal import Decimal
from typing import Dict, Any, List, Tuple
from datetime import timedelta, date, datetime
from django.db.models import Sum, Count, Avg, Q, F, Min, Max, DecimalField, Case, When, Value, IntegerField
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth, ExtractWeekDay, ExtractHour, Coalesce
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated

from sales.models import Customer, Sale, SaleItem, Payment
from inventory.models import Product
from reports.services.report_base import BaseReportView
from reports.utils.response import ReportResponse, ReportError
from reports.utils.aggregation import AggregationHelper


class CustomerLifetimeValueReportView(BaseReportView):
    """
    Customer Lifetime Value (CLV) Report
    
    GET /reports/api/customer/lifetime-value/
    
    Identifies most valuable customers based on total revenue, profitability,
    and purchase behavior. Ranks customers and provides detailed metrics.
    
    Query Parameters:
    - start_date: YYYY-MM-DD (optional - filter by customer creation date)
    - end_date: YYYY-MM-DD (optional)
    - customer_type: RETAIL|WHOLESALE (optional)
    - min_revenue: decimal (optional - minimum total revenue)
    - min_profit: decimal (optional - minimum total profit)
    - sort_by: revenue|profit|orders|aov (default: revenue)
    - page: int (pagination)
    - page_size: int (pagination, default: 50)
    
    Response Format:
    {
        "success": true,
        "data": {
            "summary": {
                "total_customers": 500,
                "total_revenue": "1500000.00",
                "total_profit": "600000.00",
                "average_clv": "3000.00",
                "top_10_percent_contribution": 45.5
            },
            "customers": [...]
        },
        "meta": {...}
    }
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Generate customer lifetime value report"""
        # Parse filters
        filters = self.parse_filters(request)
        start_date = filters.get('start_date')
        end_date = filters.get('end_date')
        customer_type = request.GET.get('customer_type')
        min_revenue = request.GET.get('min_revenue')
        min_profit = request.GET.get('min_profit')
        sort_by = request.GET.get('sort_by', 'revenue')
        
        # Build queryset
        queryset = Customer.objects.filter(is_active=True)
        
        if customer_type:
            queryset = queryset.filter(customer_type=customer_type)
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        # Annotate with lifetime metrics
        queryset = queryset.annotate(
            total_revenue=Coalesce(Sum('sales__total_amount'), Decimal('0.00')),
            total_profit=Coalesce(Sum('sales__total_profit'), Decimal('0.00')),
            total_orders=Count('sales', filter=Q(sales__payment_status__in=['paid', 'partial'])),
            first_purchase=Min('sales__created_at'),
            last_purchase=Max('sales__created_at')
        )
        
        # Filter by minimum thresholds
        if min_revenue:
            queryset = queryset.filter(total_revenue__gte=Decimal(min_revenue))
        if min_profit:
            queryset = queryset.filter(total_profit__gte=Decimal(min_profit))
        
        # Build summary
        summary = self._build_summary(queryset)
        
        # Build customer details
        customers = self._build_customer_details(queryset, sort_by)
        
        # Apply pagination
        paginated_customers, pagination = self.paginate_data(customers, request)
        
        return ReportResponse.success({
            'summary': summary,
            'customers': paginated_customers
        }, meta={
            'customer_type': customer_type,
            'min_revenue': min_revenue,
            'min_profit': min_profit,
            'sort_by': sort_by,
            'pagination': pagination
        })
    
    def _build_summary(self, queryset) -> Dict[str, Any]:
        """Build summary statistics"""
        totals = queryset.aggregate(
            total_customers=Count('id'),
            total_revenue=Sum('total_revenue'),
            total_profit=Sum('total_profit'),
            total_orders=Sum('total_orders')
        )
        
        total_customers = totals['total_customers'] or 0
        total_revenue = totals['total_revenue'] or Decimal('0.00')
        total_profit = totals['total_profit'] or Decimal('0.00')
        total_orders = totals['total_orders'] or 0
        
        avg_clv = total_revenue / total_customers if total_customers > 0 else Decimal('0.00')
        avg_profit = total_profit / total_customers if total_customers > 0 else Decimal('0.00')
        
        # Get top customer revenue
        top_customer = queryset.order_by('-total_revenue').first()
        top_customer_revenue = top_customer.total_revenue if top_customer else Decimal('0.00')
        
        # Calculate top 10% contribution
        top_10_pct = self._calculate_top_percent_contribution(queryset, 10)
        
        return {
            'total_customers': total_customers,
            'total_revenue': str(total_revenue),
            'total_profit': str(total_profit),
            'total_orders': total_orders,
            'average_clv': str(avg_clv.quantize(Decimal('0.01'))),
            'average_profit_per_customer': str(avg_profit.quantize(Decimal('0.01'))),
            'top_customer_revenue': str(top_customer_revenue),
            'top_10_percent_contribution': top_10_pct
        }
    
    def _calculate_top_percent_contribution(self, queryset, percent: int) -> float:
        """Calculate revenue contribution from top X percent of customers"""
        total_customers = queryset.count()
        if total_customers == 0:
            return 0.0
        
        top_count = max(1, int(total_customers * percent / 100))
        
        # Get total revenue
        total_revenue = queryset.aggregate(total=Sum('total_revenue'))['total'] or Decimal('0.00')
        
        # Get top customers revenue
        top_revenue = queryset.order_by('-total_revenue')[:top_count].aggregate(
            total=Sum('total_revenue')
        )['total'] or Decimal('0.00')
        
        contribution = (float(top_revenue) / float(total_revenue) * 100) if total_revenue > 0 else 0.0
        
        return round(contribution, 2)
    
    def _build_customer_details(self, queryset, sort_by: str) -> List[Dict]:
        """Build detailed customer metrics"""
        # Sort queryset
        sort_map = {
            'revenue': '-total_revenue',
            'profit': '-total_profit',
            'orders': '-total_orders',
            'aov': '-total_revenue'  # Will recalculate for AOV
        }
        
        queryset = queryset.order_by(sort_map.get(sort_by, '-total_revenue'))
        
        customers = []
        rank = 1
        
        for customer in queryset:
            # Calculate metrics
            total_revenue = customer.total_revenue or Decimal('0.00')
            total_profit = customer.total_profit or Decimal('0.00')
            total_orders = customer.total_orders or 0
            
            profit_margin = (float(total_profit) / float(total_revenue) * 100) if total_revenue > 0 else 0.0
            aov = total_revenue / total_orders if total_orders > 0 else Decimal('0.00')
            
            # Calculate customer tenure
            first_purchase = customer.first_purchase
            last_purchase = customer.last_purchase
            
            if first_purchase and last_purchase:
                first_date = first_purchase.date() if isinstance(first_purchase, datetime) else first_purchase
                last_date = last_purchase.date() if isinstance(last_purchase, datetime) else last_purchase
                days_as_customer = (last_date - first_date).days + 1
                purchase_frequency = days_as_customer / total_orders if total_orders > 1 else 0
            else:
                first_date = None
                last_date = None
                days_as_customer = 0
                purchase_frequency = 0
            
            customers.append({
                'customer_id': str(customer.id),
                'customer_name': customer.name,
                'customer_type': customer.customer_type,
                'email': customer.email,
                'phone': customer.phone,
                'total_revenue': str(total_revenue),
                'total_profit': str(total_profit),
                'profit_margin': round(profit_margin, 2),
                'total_orders': total_orders,
                'average_order_value': str(aov.quantize(Decimal('0.01'))),
                'first_purchase_date': first_date.isoformat() if first_date else None,
                'last_purchase_date': last_date.isoformat() if last_date else None,
                'days_as_customer': days_as_customer,
                'purchase_frequency_days': round(purchase_frequency, 1),
                'rank': rank
            })
            
            rank += 1
        
        # Re-sort if sorting by AOV
        if sort_by == 'aov':
            customers.sort(key=lambda x: Decimal(x['average_order_value']), reverse=True)
            # Update ranks
            for idx, customer in enumerate(customers, 1):
                customer['rank'] = idx
        
        return customers


class CustomerSegmentationReportView(BaseReportView):
    """
    Customer Segmentation Report
    
    GET /reports/api/customer/segmentation/
    
    Groups customers by behavior, value, and credit patterns using RFM analysis,
    tier classification, and credit utilization segmentation.
    
    Query Parameters:
    - segment_type: rfm|tier|credit|all (default: all)
    - customer_type: RETAIL|WHOLESALE (optional)
    - include_inactive: boolean (default: false)
    
    Response Format:
    {
        "success": true,
        "data": {
            "summary": {...},
            "rfm_segments": [...],
            "tier_segments": [...],
            "credit_segments": [...]
        },
        "meta": {...}
    }
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Generate customer segmentation report"""
        # Parse filters
        segment_type = request.GET.get('segment_type', 'all')
        customer_type = request.GET.get('customer_type')
        include_inactive = request.GET.get('include_inactive', 'false').lower() == 'true'
        
        # Build queryset
        queryset = Customer.objects.all()
        
        if not include_inactive:
            queryset = queryset.filter(is_active=True)
        if customer_type:
            queryset = queryset.filter(customer_type=customer_type)
        
        # Build summary
        summary = self._build_summary(queryset)
        
        # Build segments based on type
        result = {'summary': summary}
        
        if segment_type in ['rfm', 'all']:
            result['rfm_segments'] = self._build_rfm_segments(queryset)
        
        if segment_type in ['tier', 'all']:
            result['tier_segments'] = self._build_tier_segments(queryset)
        
        if segment_type in ['credit', 'all']:
            result['credit_segments'] = self._build_credit_segments(queryset)
        
        return ReportResponse.success(result, meta={
            'segment_type': segment_type,
            'customer_type': customer_type,
            'include_inactive': include_inactive
        })
    
    def _build_summary(self, queryset) -> Dict[str, Any]:
        """Build summary statistics"""
        total = queryset.count()
        active = queryset.filter(is_active=True).count()
        
        return {
            'total_customers': total,
            'active_customers': active,
            'inactive_customers': total - active
        }
    
    def _build_rfm_segments(self, queryset) -> List[Dict]:
        """Build RFM (Recency, Frequency, Monetary) segmentation"""
        # Annotate customers with RFM metrics
        today = timezone.now().date()
        
        customers_with_rfm = queryset.annotate(
            last_purchase_date=Max('sales__created_at'),
            total_purchases=Count('sales', filter=Q(sales__payment_status__in=['paid', 'partial'])),
            total_revenue=Coalesce(Sum('sales__total_amount'), Decimal('0.00'))
        )
        
        # Calculate RFM scores (1-5)
        customer_scores = []
        
        for customer in customers_with_rfm:
            if customer.last_purchase_date:
                last_date = customer.last_purchase_date.date() if isinstance(customer.last_purchase_date, datetime) else customer.last_purchase_date
                recency_days = (today - last_date).days
            else:
                recency_days = 9999  # Never purchased
            
            customer_scores.append({
                'customer': customer,
                'recency_days': recency_days,
                'frequency': customer.total_purchases or 0,
                'monetary': customer.total_revenue or Decimal('0.00')
            })
        
        # Calculate quintiles for scoring
        recency_values = sorted([c['recency_days'] for c in customer_scores])
        frequency_values = sorted([c['frequency'] for c in customer_scores], reverse=True)
        monetary_values = sorted([float(c['monetary']) for c in customer_scores], reverse=True)
        
        # Score each customer
        for score_data in customer_scores:
            score_data['r_score'] = self._calculate_quintile_score(score_data['recency_days'], recency_values, reverse=True)
            score_data['f_score'] = self._calculate_quintile_score(score_data['frequency'], frequency_values)
            score_data['m_score'] = self._calculate_quintile_score(float(score_data['monetary']), monetary_values)
            score_data['segment'] = self._classify_rfm_segment(
                score_data['r_score'],
                score_data['f_score'],
                score_data['m_score']
            )
        
        # Group by segment
        segments = {}
        for score_data in customer_scores:
            segment = score_data['segment']
            if segment not in segments:
                segments[segment] = {
                    'customers': [],
                    'total_revenue': Decimal('0.00'),
                    'total_recency': 0,
                    'total_frequency': 0
                }
            
            segments[segment]['customers'].append(score_data['customer'])
            segments[segment]['total_revenue'] += score_data['monetary']
            segments[segment]['total_recency'] += score_data['recency_days']
            segments[segment]['total_frequency'] += score_data['frequency']
        
        # Build segment list
        segment_list = []
        total_customers = len(customer_scores)
        
        segment_descriptions = {
            'Champions': 'Recent, frequent, high-value customers',
            'Loyal': 'Regular customers with good value',
            'Potential Loyalists': 'Recent customers with potential',
            'New Customers': 'Recently acquired, low frequency',
            'At Risk': 'Previously valuable, now inactive',
            'Cannot Lose Them': 'High-value but haven\'t purchased recently',
            'Hibernating': 'Low engagement across all metrics',
            'Lost': 'Churned customers'
        }
        
        for segment_name, data in segments.items():
            count = len(data['customers'])
            avg_recency = data['total_recency'] / count if count > 0 else 0
            avg_frequency = data['total_frequency'] / count if count > 0 else 0
            
            segment_list.append({
                'segment_name': segment_name,
                'description': segment_descriptions.get(segment_name, ''),
                'customer_count': count,
                'percentage': round(count / total_customers * 100, 2) if total_customers > 0 else 0,
                'avg_revenue': str((data['total_revenue'] / count).quantize(Decimal('0.01'))) if count > 0 else '0.00',
                'avg_recency_days': round(avg_recency, 1),
                'avg_frequency': round(avg_frequency, 1)
            })
        
        # Sort by customer count descending
        segment_list.sort(key=lambda x: x['customer_count'], reverse=True)
        
        return segment_list
    
    def _calculate_quintile_score(self, value, sorted_values, reverse=False) -> int:
        """Calculate quintile score (1-5) for a value"""
        if not sorted_values:
            return 3
        
        n = len(sorted_values)
        if n == 0:
            return 3
        
        # Find position in sorted list
        try:
            pos = sorted_values.index(value)
        except ValueError:
            # Value not in list, find closest
            pos = 0
            for i, v in enumerate(sorted_values):
                if value <= v:
                    pos = i
                    break
        
        # Convert to quintile (1-5)
        quintile = min(5, max(1, int(pos / (n / 5)) + 1))
        
        if reverse:
            quintile = 6 - quintile
        
        return quintile
    
    def _classify_rfm_segment(self, r: int, f: int, m: int) -> str:
        """Classify customer into RFM segment"""
        # Champions: High R, F, M
        if r >= 4 and f >= 4 and m >= 4:
            return 'Champions'
        
        # Loyal: Good R, good F, good M
        if r >= 3 and f >= 3 and m >= 3:
            return 'Loyal'
        
        # Potential Loyalists: Good R, moderate F, moderate M
        if r >= 3 and f >= 2 and m >= 2:
            return 'Potential Loyalists'
        
        # New Customers: High R, low F
        if r >= 4 and f <= 2:
            return 'New Customers'
        
        # At Risk: Low R, high F, high M
        if r <= 2 and f >= 3 and m >= 3:
            return 'At Risk'
        
        # Cannot Lose Them: Low R, very high F, very high M
        if r <= 2 and f >= 4 and m >= 4:
            return 'Cannot Lose Them'
        
        # Hibernating: Low across all
        if r <= 2 and f <= 2 and m <= 2:
            return 'Hibernating'
        
        # Default
        return 'Lost'
    
    def _build_tier_segments(self, queryset) -> List[Dict]:
        """Build tier-based segmentation (VIP, Regular, New, At-Risk)"""
        # Annotate with revenue
        customers = queryset.annotate(
            total_revenue=Coalesce(Sum('sales__total_amount'), Decimal('0.00')),
            last_purchase=Max('sales__created_at'),
            days_as_customer=Count('sales__created_at')
        )
        
        total_customers = customers.count()
        if total_customers == 0:
            return []
        
        # Sort by revenue
        sorted_by_revenue = list(customers.order_by('-total_revenue'))
        
        # Calculate total revenue
        total_revenue = sum(c.total_revenue or Decimal('0.00') for c in sorted_by_revenue)
        
        # Define tiers
        vip_count = max(1, int(total_customers * 0.2))  # Top 20%
        at_risk_threshold = timezone.now().date() - timedelta(days=90)
        
        tiers = {
            'VIP': {'customers': [], 'revenue': Decimal('0.00')},
            'Regular': {'customers': [], 'revenue': Decimal('0.00')},
            'New': {'customers': [], 'revenue': Decimal('0.00')},
            'At-Risk': {'customers': [], 'revenue': Decimal('0.00')}
        }
        
        new_customer_threshold = timezone.now().date() - timedelta(days=30)
        
        for idx, customer in enumerate(sorted_by_revenue):
            revenue = customer.total_revenue or Decimal('0.00')
            
            # Determine tier
            if idx < vip_count:
                tier = 'VIP'
            elif customer.last_purchase:
                last_date = customer.last_purchase.date() if isinstance(customer.last_purchase, datetime) else customer.last_purchase
                if last_date < at_risk_threshold:
                    tier = 'At-Risk'
                elif customer.created_at.date() > new_customer_threshold:
                    tier = 'New'
                else:
                    tier = 'Regular'
            else:
                tier = 'At-Risk'
            
            tiers[tier]['customers'].append(customer)
            tiers[tier]['revenue'] += revenue
        
        # Build segment list
        tier_list = []
        
        tier_criteria = {
            'VIP': 'Top 20% by revenue',
            'Regular': 'Active customers (not VIP, New, or At-Risk)',
            'New': 'Customers acquired in last 30 days',
            'At-Risk': 'No purchase in 90+ days'
        }
        
        for tier_name, data in tiers.items():
            count = len(data['customers'])
            revenue = data['revenue']
            
            tier_list.append({
                'tier': tier_name,
                'customer_count': count,
                'percentage': round(count / total_customers * 100, 2) if total_customers > 0 else 0,
                'total_revenue': str(revenue),
                'revenue_contribution': round(float(revenue) / float(total_revenue) * 100, 2) if total_revenue > 0 else 0,
                'criteria': tier_criteria.get(tier_name, '')
            })
        
        return tier_list
    
    def _build_credit_segments(self, queryset) -> List[Dict]:
        """Build credit utilization segments"""
        # Filter customers with credit limits
        credit_customers = queryset.filter(credit_limit__gt=0).annotate(
            utilization=Case(
                When(credit_limit=0, then=Value(0)),
                default=F('outstanding_balance') * 100 / F('credit_limit'),
                output_field=DecimalField()
            )
        )
        
        # Define segments
        segments = {
            'High Credit Users': {'min': 80, 'max': 100},
            'Moderate Credit Users': {'min': 50, 'max': 80},
            'Low Credit Users': {'min': 1, 'max': 50},
            'No Credit Used': {'min': 0, 'max': 1}
        }
        
        segment_list = []
        
        for segment_name, range_val in segments.items():
            segment_customers = credit_customers.filter(
                utilization__gte=range_val['min'],
                utilization__lt=range_val['max']
            )
            
            count = segment_customers.count()
            if count > 0:
                avg_util = segment_customers.aggregate(avg=Avg('utilization'))['avg'] or 0
                total_outstanding = segment_customers.aggregate(total=Sum('outstanding_balance'))['total'] or Decimal('0.00')
                
                segment_list.append({
                    'segment': segment_name,
                    'customer_count': count,
                    'avg_utilization': round(float(avg_util), 1),
                    'total_outstanding': str(total_outstanding),
                    'utilization_range': f"{range_val['min']}-{range_val['max']}%"
                })
        
        return segment_list


class PurchasePatternAnalysisReportView(BaseReportView):
    """
    Purchase Pattern Analysis Report
    
    GET /reports/api/customer/purchase-patterns/
    
    Analyzes customer buying behavior including frequency, basket size,
    category preferences, payment methods, and temporal patterns.
    
    Query Parameters:
    - customer_id: UUID (optional - specific customer)
    - start_date: YYYY-MM-DD (default: 90 days ago)
    - end_date: YYYY-MM-DD (default: today)
    - customer_type: RETAIL|WHOLESALE (optional)
    - grouping: daily|weekly|monthly (default: monthly)
    
    Response Format:
    {
        "success": true,
        "data": {
            "summary": {...},
            "purchase_frequency": {...},
            "basket_analysis": [...],
            "time_patterns": {...},
            "payment_preferences": [...],
            "category_preferences": [...]
        },
        "meta": {...}
    }
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Generate purchase pattern analysis report"""
        # Parse filters
        filters = self.parse_filters(request)
        customer_id = request.GET.get('customer_id')
        start_date = filters.get('start_date', timezone.now().date() - timedelta(days=90))
        end_date = filters.get('end_date', timezone.now().date())
        customer_type = request.GET.get('customer_type')
        grouping = request.GET.get('grouping', 'monthly')
        
        # Build queryset for sales
        sales_qs = Sale.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            payment_status__in=['paid', 'partial']
        )
        
        if customer_id:
            sales_qs = sales_qs.filter(customer_id=customer_id)
        if customer_type:
            sales_qs = sales_qs.filter(customer__customer_type=customer_type)
        
        # Build summary
        summary = self._build_summary(sales_qs, start_date, end_date)
        
        # Build frequency analysis
        purchase_frequency = self._build_frequency_analysis(sales_qs, start_date, end_date)
        
        # Build basket analysis
        basket_analysis = self._build_basket_analysis(sales_qs)
        
        # Build time patterns
        time_patterns = self._build_time_patterns(sales_qs)
        
        # Build payment preferences
        payment_preferences = self._build_payment_preferences(sales_qs)
        
        # Build category preferences
        category_preferences = self._build_category_preferences(sales_qs)
        
        return ReportResponse.success({
            'summary': summary,
            'purchase_frequency': purchase_frequency,
            'basket_analysis': basket_analysis,
            'time_patterns': time_patterns,
            'payment_preferences': payment_preferences,
            'category_preferences': category_preferences
        }, meta={
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'customer_id': customer_id,
            'customer_type': customer_type,
            'grouping': grouping
        })
    
    def _build_summary(self, sales_qs, start_date, end_date) -> Dict[str, Any]:
        """Build summary statistics"""
        stats = sales_qs.aggregate(
            total_transactions=Count('id'),
            unique_customers=Count('customer', distinct=True),
            total_revenue=Sum('total_amount'),
            total_items=Sum('saleitem__quantity')
        )
        
        total_transactions = stats['total_transactions'] or 0
        unique_customers = stats['unique_customers'] or 0
        total_revenue = stats['total_revenue'] or Decimal('0.00')
        total_items = stats['total_items'] or 0
        
        avg_basket = total_revenue / total_transactions if total_transactions > 0 else Decimal('0.00')
        avg_items = total_items / total_transactions if total_transactions > 0 else 0
        
        # Get most popular payment method
        payment_stats = sales_qs.values('primary_payment_method').annotate(
            count=Count('id')
        ).order_by('-count').first()
        
        most_popular_payment = payment_stats['primary_payment_method'] if payment_stats else None
        
        # Get busiest day
        day_stats = sales_qs.annotate(
            day_of_week=ExtractWeekDay('created_at')
        ).values('day_of_week').annotate(
            count=Count('id')
        ).order_by('-count').first()
        
        day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        busiest_day = day_names[day_stats['day_of_week'] - 1] if day_stats else None
        
        return {
            'total_transactions': total_transactions,
            'unique_customers': unique_customers,
            'avg_basket_size': str(avg_basket.quantize(Decimal('0.01'))),
            'avg_items_per_transaction': round(avg_items, 1),
            'most_popular_payment_method': most_popular_payment,
            'busiest_day': busiest_day
        }
    
    def _build_frequency_analysis(self, sales_qs, start_date, end_date) -> Dict[str, Any]:
        """Analyze purchase frequency"""
        total_days = (end_date - start_date).days + 1
        
        # Count transactions by period
        daily_count = sales_qs.filter(created_at__date=end_date).count()
        weekly_count = sales_qs.filter(
            created_at__date__gte=end_date - timedelta(days=7)
        ).count()
        monthly_count = sales_qs.filter(
            created_at__date__gte=end_date - timedelta(days=30)
        ).count()
        
        total_transactions = sales_qs.count()
        unique_customers = sales_qs.values('customer').distinct().count()
        
        avg_days_between = total_days / total_transactions if total_transactions > 1 else 0
        
        return {
            'daily': daily_count,
            'weekly': weekly_count,
            'monthly': monthly_count,
            'avg_days_between_purchases': round(avg_days_between, 1),
            'purchases_per_customer': round(total_transactions / unique_customers, 1) if unique_customers > 0 else 0
        }
    
    def _build_basket_analysis(self, sales_qs) -> List[Dict]:
        """Analyze basket sizes"""
        # Define basket size ranges
        ranges = [
            (0, 100, '0-100'),
            (100, 250, '100-250'),
            (250, 500, '250-500'),
            (500, 1000, '500-1000'),
            (1000, 999999, '1000+')
        ]
        
        total_transactions = sales_qs.count()
        
        basket_data = []
        
        for min_val, max_val, label in ranges:
            range_sales = sales_qs.filter(
                total_amount__gte=min_val,
                total_amount__lt=max_val
            )
            
            count = range_sales.count()
            if count > 0:
                avg_items = range_sales.aggregate(
                    avg=Avg('saleitem__quantity')
                )['avg'] or 0
                
                basket_data.append({
                    'basket_size_range': label,
                    'transaction_count': count,
                    'percentage': round(count / total_transactions * 100, 2) if total_transactions > 0 else 0,
                    'avg_items': round(avg_items, 1)
                })
        
        return basket_data
    
    def _build_time_patterns(self, sales_qs) -> Dict[str, List]:
        """Analyze temporal purchase patterns"""
        # By day of week
        day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
        
        by_day = sales_qs.annotate(
            day_of_week=ExtractWeekDay('created_at')
        ).values('day_of_week').annotate(
            transaction_count=Count('id'),
            total_revenue=Sum('total_amount')
        ).order_by('day_of_week')
        
        day_data = [
            {
                'day': day_names[item['day_of_week'] - 1],
                'transaction_count': item['transaction_count'],
                'total_revenue': str(item['total_revenue'] or Decimal('0.00'))
            }
            for item in by_day
        ]
        
        # By hour (if we have time data)
        by_hour = sales_qs.annotate(
            hour=ExtractHour('created_at')
        ).values('hour').annotate(
            transaction_count=Count('id')
        ).order_by('hour')
        
        hour_data = [
            {
                'hour': item['hour'],
                'transaction_count': item['transaction_count']
            }
            for item in by_hour
        ]
        
        return {
            'by_day_of_week': day_data,
            'by_hour': hour_data
        }
    
    def _build_payment_preferences(self, sales_qs) -> List[Dict]:
        """Analyze payment method preferences"""
        payment_data = sales_qs.values('primary_payment_method').annotate(
            transaction_count=Count('id'),
            total_value=Sum('total_amount')
        ).order_by('-transaction_count')
        
        total_transactions = sales_qs.count()
        
        return [
            {
                'payment_method': item['primary_payment_method'],
                'transaction_count': item['transaction_count'],
                'percentage': round(item['transaction_count'] / total_transactions * 100, 2) if total_transactions > 0 else 0,
                'avg_transaction_value': str((item['total_value'] / item['transaction_count']).quantize(Decimal('0.01'))) if item['transaction_count'] > 0 else '0.00'
            }
            for item in payment_data
        ]
    
    def _build_category_preferences(self, sales_qs) -> List[Dict]:
        """Analyze category purchase preferences"""
        # Get all sale items with category info
        category_data = SaleItem.objects.filter(
            sale__in=sales_qs
        ).values(
            'product__category__name'
        ).annotate(
            purchase_count=Count('id'),
            total_quantity=Sum('quantity'),
            total_spend=Sum(F('quantity') * F('unit_price'), output_field=DecimalField())
        ).order_by('-purchase_count')
        
        total_purchases = SaleItem.objects.filter(sale__in=sales_qs).count()
        
        return [
            {
                'category': item['product__category__name'] or 'Uncategorized',
                'purchase_count': item['purchase_count'],
                'percentage': round(item['purchase_count'] / total_purchases * 100, 2) if total_purchases > 0 else 0,
                'total_quantity': item['total_quantity'],
                'avg_spend': str((item['total_spend'] / item['purchase_count']).quantize(Decimal('0.01'))) if item['purchase_count'] > 0 else '0.00'
            }
            for item in category_data[:10]  # Top 10 categories
        ]


class CustomerRetentionMetricsReportView(BaseReportView):
    """
    Customer Retention Metrics Report
    
    GET /reports/api/customer/retention/
    
    Tracks customer loyalty, churn, and repeat purchase behavior with
    cohort analysis and retention trends over time.
    
    Query Parameters:
    - start_date: YYYY-MM-DD (default: 12 months ago)
    - end_date: YYYY-MM-DD (default: today)
    - cohort_period: month|quarter|year (default: month)
    - customer_type: RETAIL|WHOLESALE (optional)
    
    Response Format:
    {
        "success": true,
        "data": {
            "summary": {...},
            "cohort_analysis": [...],
            "retention_trends": [...],
            "repeat_purchase_analysis": {...}
        },
        "meta": {...}
    }
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Generate customer retention metrics report"""
        # Parse filters
        filters = self.parse_filters(request)
        start_date = filters.get('start_date', timezone.now().date() - timedelta(days=365))
        end_date = filters.get('end_date', timezone.now().date())
        cohort_period = request.GET.get('cohort_period', 'month')
        customer_type = request.GET.get('customer_type')
        
        # Build queryset
        customer_qs = Customer.objects.all()
        if customer_type:
            customer_qs = customer_qs.filter(customer_type=customer_type)
        
        # Build summary
        summary = self._build_summary(customer_qs, start_date, end_date)
        
        # Build cohort analysis
        cohort_analysis = self._build_cohort_analysis(customer_qs, start_date, end_date, cohort_period)
        
        # Build retention trends
        retention_trends = self._build_retention_trends(customer_qs, start_date, end_date)
        
        # Build repeat purchase analysis
        repeat_purchase_analysis = self._build_repeat_purchase_analysis(customer_qs)
        
        return ReportResponse.success({
            'summary': summary,
            'cohort_analysis': cohort_analysis,
            'retention_trends': retention_trends,
            'repeat_purchase_analysis': repeat_purchase_analysis
        }, meta={
            'date_range': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'cohort_period': cohort_period,
            'customer_type': customer_type
        })
    
    def _build_summary(self, customer_qs, start_date, end_date) -> Dict[str, Any]:
        """Build summary retention metrics"""
        # Total customers
        total_customers = customer_qs.count()
        
        # Active customers (purchased in last 90 days)
        ninety_days_ago = timezone.now().date() - timedelta(days=90)
        active_customers = customer_qs.filter(
            sales__created_at__date__gte=ninety_days_ago,
            sales__payment_status__in=['paid', 'partial']
        ).distinct().count()
        
        # Churned customers (no purchase in 90+ days but had purchases before)
        churned_customers = customer_qs.filter(
            sales__created_at__date__lt=ninety_days_ago
        ).exclude(
            sales__created_at__date__gte=ninety_days_ago
        ).distinct().count()
        
        # Calculate rates
        retention_rate = (active_customers / total_customers * 100) if total_customers > 0 else 0
        churn_rate = (churned_customers / total_customers * 100) if total_customers > 0 else 0
        
        # Repeat purchase rate
        customers_with_multiple = customer_qs.annotate(
            purchase_count=Count('sales', filter=Q(sales__payment_status__in=['paid', 'partial']))
        ).filter(purchase_count__gte=2).count()
        
        repeat_rate = (customers_with_multiple / total_customers * 100) if total_customers > 0 else 0
        
        # Average customer lifespan
        customers_with_purchases = customer_qs.annotate(
            first_purchase=Min('sales__created_at'),
            last_purchase=Max('sales__created_at')
        ).filter(first_purchase__isnull=False, last_purchase__isnull=False)
        
        lifespans = []
        for customer in customers_with_purchases:
            first = customer.first_purchase.date() if isinstance(customer.first_purchase, datetime) else customer.first_purchase
            last = customer.last_purchase.date() if isinstance(customer.last_purchase, datetime) else customer.last_purchase
            lifespans.append((last - first).days)
        
        avg_lifespan = sum(lifespans) / len(lifespans) if lifespans else 0
        
        # New customers in period
        new_customers = customer_qs.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        ).count()
        
        # Returning customers (had purchase before period and during period)
        returning_customers = customer_qs.filter(
            created_at__date__lt=start_date,
            sales__created_at__date__gte=start_date,
            sales__created_at__date__lte=end_date,
            sales__payment_status__in=['paid', 'partial']
        ).distinct().count()
        
        return {
            'total_customers': total_customers,
            'active_customers': active_customers,
            'churned_customers': churned_customers,
            'retention_rate': round(retention_rate, 2),
            'churn_rate': round(churn_rate, 2),
            'repeat_purchase_rate': round(repeat_rate, 2),
            'avg_customer_lifespan_days': round(avg_lifespan, 1),
            'new_customers_this_period': new_customers,
            'returning_customers': returning_customers
        }
    
    def _build_cohort_analysis(self, customer_qs, start_date, end_date, period: str) -> List[Dict]:
        """Build cohort retention analysis"""
        # Get customers with their first purchase month
        customers_with_first = customer_qs.annotate(
            first_purchase=Min('sales__created_at')
        ).filter(first_purchase__isnull=False)
        
        # Group by cohort period
        cohorts = {}
        
        for customer in customers_with_first:
            first_date = customer.first_purchase.date() if isinstance(customer.first_purchase, datetime) else customer.first_purchase
            
            # Determine cohort key based on period
            if period == 'month':
                cohort_key = first_date.strftime('%Y-%m')
            elif period == 'quarter':
                quarter = (first_date.month - 1) // 3 + 1
                cohort_key = f"{first_date.year}-Q{quarter}"
            else:  # year
                cohort_key = str(first_date.year)
            
            if cohort_key not in cohorts:
                cohorts[cohort_key] = {
                    'customers': [],
                    'initial_count': 0
                }
            
            cohorts[cohort_key]['customers'].append(customer)
            cohorts[cohort_key]['initial_count'] += 1
        
        # Calculate retention for each cohort
        cohort_data = []
        
        for cohort_key in sorted(cohorts.keys()):
            cohort = cohorts[cohort_key]
            initial_count = cohort['initial_count']
            
            # Check how many are still active
            ninety_days_ago = timezone.now().date() - timedelta(days=90)
            current_active = sum(
                1 for c in cohort['customers']
                if c.sales.filter(created_at__date__gte=ninety_days_ago, payment_status__in=['paid', 'partial']).exists()
            )
            
            churned = initial_count - current_active
            
            cohort_data.append({
                'cohort': cohort_key,
                'initial_customers': initial_count,
                'current_active': current_active,
                'churned': churned,
                'retention_rate': round(current_active / initial_count * 100, 2) if initial_count > 0 else 0
            })
        
        return cohort_data[:12]  # Last 12 periods
    
    def _build_retention_trends(self, customer_qs, start_date, end_date) -> List[Dict]:
        """Build monthly retention trends"""
        # Get monthly data
        current_date = start_date
        trends = []
        
        while current_date <= end_date:
            month_end = min(
                date(current_date.year + (current_date.month // 12), ((current_date.month % 12) + 1), 1) - timedelta(days=1),
                end_date
            )
            
            # Customers at start of month
            starting_customers = customer_qs.filter(
                created_at__date__lt=current_date
            ).count()
            
            # New customers this month
            new_customers = customer_qs.filter(
                created_at__date__gte=current_date,
                created_at__date__lte=month_end
            ).count()
            
            # Active at end (made purchase in last 90 days from month end)
            active_threshold = month_end - timedelta(days=90)
            ending_customers = customer_qs.filter(
                created_at__date__lte=month_end,
                sales__created_at__date__gte=active_threshold,
                sales__created_at__date__lte=month_end,
                sales__payment_status__in=['paid', 'partial']
            ).distinct().count()
            
            # Churned (existed before but didn't purchase)
            churned = max(0, starting_customers + new_customers - ending_customers)
            
            # Calculate rates
            retention_rate = ((ending_customers - new_customers) / starting_customers * 100) if starting_customers > 0 else 0
            churn_rate = (churned / starting_customers * 100) if starting_customers > 0 else 0
            
            trends.append({
                'period': current_date.strftime('%Y-%m'),
                'starting_customers': starting_customers,
                'new_customers': new_customers,
                'churned_customers': churned,
                'ending_customers': ending_customers,
                'retention_rate': round(retention_rate, 2),
                'churn_rate': round(churn_rate, 2)
            })
            
            # Move to next month
            if current_date.month == 12:
                current_date = date(current_date.year + 1, 1, 1)
            else:
                current_date = date(current_date.year, current_date.month + 1, 1)
        
        return trends
    
    def _build_repeat_purchase_analysis(self, customer_qs) -> Dict[str, Any]:
        """Analyze repeat purchase behavior"""
        # Annotate with purchase counts
        customers_with_counts = customer_qs.annotate(
            purchase_count=Count('sales', filter=Q(sales__payment_status__in=['paid', 'partial']))
        )
        
        one_time = customers_with_counts.filter(purchase_count=1).count()
        repeat = customers_with_counts.filter(purchase_count__gte=2).count()
        
        total = customer_qs.count()
        
        # Average purchases per customer
        avg_purchases = customers_with_counts.aggregate(
            avg=Avg('purchase_count')
        )['avg'] or 0
        
        return {
            'one_time_buyers': one_time,
            'repeat_buyers': repeat,
            'repeat_rate': round(repeat / total * 100, 2) if total > 0 else 0,
            'avg_purchases_per_customer': round(avg_purchases, 1)
        }
