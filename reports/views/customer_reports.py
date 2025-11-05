"""
Customer Analytical Reports

Endpoints for customer analytics and relationship management.
Tracks customer lifetime value, segmentation, purchase patterns, and retention metrics.
"""

import calendar
import csv
import io
from collections import defaultdict, Counter
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import BytesIO
from typing import Dict, Any, List, Tuple, Optional, Set
from datetime import timedelta, date, datetime
from django.core.cache import cache
from django.db.models import Sum, Count, Avg, Q, F, Min, Max, DecimalField, Case, When, Value, IntegerField, CharField, DateTimeField
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth, ExtractWeekDay, Coalesce
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from sales.models import Customer, Sale, SaleItem, Payment, AccountsReceivable, ARPayment
from inventory.models import Product
from settings.models import BusinessSettings
from reports.services.report_base import BaseReportView
from reports.utils.response import ReportResponse, ReportError
from reports.utils.aggregation import AggregationHelper
from reports.utils.profit_calculator import ProfitCalculator


class TopCustomersReportView(BaseReportView):
    """Top Customers dashboard endpoint adhering to frontend contract."""

    permission_classes = [IsAuthenticated]

    DEFAULT_LIMIT = 10
    MAX_LIMIT = 50
    VALID_SEGMENTS = {'all', 'vip', 'at_risk', 'loyalty'}

    def get(self, request):
        filters = self.parse_filters(request, default_days=None)
        if (error_response := filters.get('error_response')):
            return error_response

        business_id = filters.get('business_id')
        start_date = filters.get('start_date')
        end_date = filters.get('end_date')

        if start_date is None or end_date is None:
            error = ReportError.create(
                ReportError.MISSING_REQUIRED_PARAM,
                "Both start_date and end_date are required",
                {'missing': ['start_date', 'end_date']}
            )
            return ReportResponse.error(error)

        limit, error_response = self._parse_limit(request.GET.get('limit'))
        if error_response:
            return error_response

        segment = request.GET.get('segment', 'all').lower()
        if segment not in self.VALID_SEGMENTS:
            error = ReportError.create(
                ReportError.INVALID_FILTER,
                "Invalid segment provided",
                {'segment': segment}
            )
            return ReportResponse.error(error)

        export_format = request.GET.get('export_format')
        if export_format:
            export_format = export_format.lower()
            if export_format not in {'csv', 'pdf'}:
                error = ReportError.create(
                    ReportError.INVALID_FILTER,
                    "Unsupported export_format value",
                    {'export_format': export_format}
                )
                return ReportResponse.error(error)

        storefront_filters, error_response = self.get_storefront_filters(
            request,
            business_id=business_id
        )
        if error_response:
            return error_response

        storefront_ids = storefront_filters['ids']

        customer_metrics = self._build_customer_metrics(
            business_id,
            start_date,
            end_date,
            storefront_ids
        )

        filtered_metrics: List[Dict[str, Any]] = []
        if customer_metrics:
            filtered_metrics = self._apply_segment_filter(customer_metrics, segment)
            filtered_metrics = sorted(filtered_metrics, key=self._build_sort_key)

        top_metrics = filtered_metrics[:limit]
        serialized_customers = [self._serialize_customer(item) for item in top_metrics]
        summary = self._build_summary(filtered_metrics)

        filters_payload = {
            'segment': segment,
            'limit': limit,
            'storefront_id': storefront_filters['primary'],
            'storefront_ids': storefront_ids,
            'storefront_names': storefront_filters['names'],
        }

        metadata = {
            'segment': segment,
            'limit_applied': limit,
            'total_available': len(filtered_metrics),
            'returned_records': len(serialized_customers),
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'generated_at': timezone.now().isoformat(),
            'filters_applied': filters_payload,
        }

        if export_format == 'csv':
            return self._build_csv_response(
                summary,
                serialized_customers,
                start_date,
                end_date,
                storefront_filters
            )
        if export_format == 'pdf':
            return self._build_pdf_response(
                summary,
                serialized_customers,
                start_date,
                end_date,
                storefront_filters
            )

        payload = {
            'success': True,
            'data': {
                'summary': summary,
                'customers': serialized_customers,
                'metadata': metadata
            },
            'error': None
        }

        return Response(payload, status=status.HTTP_200_OK)

    def _parse_limit(self, limit_param: Optional[str]) -> Tuple[int, Optional[Response]]:
        limit = self.DEFAULT_LIMIT
        if limit_param is None:
            return limit, None
        try:
            limit = int(limit_param)
        except (TypeError, ValueError):
            error = ReportError.create(
                ReportError.INVALID_FILTER,
                "limit must be an integer",
                {'limit': limit_param}
            )
            return self.DEFAULT_LIMIT, ReportResponse.error(error)
        if limit < 1 or limit > self.MAX_LIMIT:
            error = ReportError.create(
                ReportError.INVALID_FILTER,
                f"limit must be between 1 and {self.MAX_LIMIT}",
                {'limit': limit_param}
            )
            return self.DEFAULT_LIMIT, ReportResponse.error(error)
        return limit, None

    def _build_customer_metrics(
        self,
        business_id: int,
        start_date: date,
        end_date: date,
        storefront_ids: List[str]
    ) -> List[Dict[str, Any]]:
        sale_filters = Q(
            sales__status__in=[Sale.STATUS_COMPLETED, Sale.STATUS_PARTIAL],
            sales__created_at__date__gte=start_date,
            sales__created_at__date__lte=end_date
        )
        if storefront_ids:
            sale_filters &= Q(sales__storefront_id__in=storefront_ids)

        customers_qs = (
            Customer.objects.filter(business_id=business_id)
            .annotate(
                gross_revenue=Coalesce(Sum('sales__total_amount', filter=sale_filters), Decimal('0.00')),
                refunded_amount=Coalesce(Sum('sales__amount_refunded', filter=sale_filters), Decimal('0.00')),
                total_purchases=Count('sales', filter=sale_filters),
                first_purchase=Min('sales__created_at', filter=sale_filters),
                last_purchase=Max('sales__created_at', filter=sale_filters)
            )
            .filter(total_purchases__gt=0)
        )

        customers = list(customers_qs)
        if not customers:
            return []

        customer_ids = [customer.id for customer in customers if customer.id]
        sales_dates = self._get_sales_dates(
            business_id,
            customer_ids,
            start_date,
            end_date,
            storefront_ids
        )
        favorite_categories = self._get_favorite_categories(
            business_id,
            customer_ids,
            start_date,
            end_date,
            storefront_ids
        )

        metrics: List[Dict[str, Any]] = []

        for customer in customers:
            net_revenue = (customer.gross_revenue or Decimal('0.00')) - (customer.refunded_amount or Decimal('0.00'))
            if net_revenue <= Decimal('0.00'):
                continue

            total_purchases = int(customer.total_purchases or 0)
            first_purchase = self._normalize_date(customer.first_purchase)
            last_purchase = self._normalize_date(customer.last_purchase)

            average_order_value = Decimal('0.00')
            if total_purchases > 0:
                average_order_value = net_revenue / Decimal(total_purchases)

            order_dates = sales_dates.get(customer.id, [])
            purchase_frequency = self._calculate_purchase_frequency(order_dates)
            favorite_category = favorite_categories.get(customer.id, '')

            metrics.append({
                'customer_id': str(customer.id),
                'customer_name': customer.name or '',
                'email': customer.email or '',
                'phone': customer.phone or '',
                'total_revenue': net_revenue,
                'total_purchases': total_purchases,
                'average_order_value': average_order_value,
                'first_purchase_date': first_purchase,
                'last_purchase_date': last_purchase,
                'customer_lifetime_days': self._calculate_lifetime_days(first_purchase, last_purchase, start_date, end_date),
                'purchase_frequency': purchase_frequency,
                'favorite_category': favorite_category or '',
                'credit_limit': customer.credit_limit or Decimal('0.00'),
                'credit_used': self._calculate_credit_used(customer),
                'loyalty_tier': self._determine_loyalty_tier(net_revenue, total_purchases),
                'status': self._determine_status(last_purchase, end_date)
            })

        return metrics

    def _apply_segment_filter(self, metrics: List[Dict[str, Any]], segment: str) -> List[Dict[str, Any]]:
        if segment == 'all':
            return metrics
        if segment == 'vip':
            return [item for item in metrics if item['loyalty_tier'] in {'gold', 'platinum'}]
        if segment == 'at_risk':
            return [item for item in metrics if item['status'] == 'at-risk']
        if segment == 'loyalty':
            return [item for item in metrics if item['loyalty_tier'] != 'standard']
        return metrics

    def _build_sort_key(self, item: Dict[str, Any]) -> Tuple[Decimal, float, str]:
        revenue_key = -item['total_revenue']
        if item['last_purchase_date']:
            last_purchase_key = -float(item['last_purchase_date'].toordinal())
        else:
            last_purchase_key = float('inf')
        name_key = (item['customer_name'] or '').lower()
        return revenue_key, last_purchase_key, name_key

    def _build_summary(self, metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
        total_customers = len(metrics)
        total_revenue = sum((item['total_revenue'] for item in metrics), Decimal('0.00'))
        top_slice = metrics[:min(10, len(metrics))]
        top_revenue = sum((item['total_revenue'] for item in top_slice), Decimal('0.00'))

        if total_customers > 0 and total_revenue > Decimal('0.00'):
            average_value = total_revenue / Decimal(total_customers)
            top_percentage = (top_revenue / total_revenue) * Decimal('100')
        else:
            average_value = Decimal('0.00')
            top_percentage = Decimal('0.00')

        return {
            'total_customers': total_customers,
            'top_10_revenue': self._decimal_to_float(top_revenue),
            'top_10_percentage': self._format_percentage(top_percentage),
            'average_customer_value': self._decimal_to_float(average_value)
        }

    def _serialize_customer(self, item: Dict[str, Any]) -> Dict[str, Any]:
        return {
            'customer_id': item['customer_id'],
            'customer_name': item['customer_name'],
            'email': item['email'],
            'phone': item['phone'],
            'total_revenue': self._decimal_to_float(item['total_revenue']),
            'total_purchases': item['total_purchases'],
            'average_order_value': self._decimal_to_float(item['average_order_value']),
            'first_purchase_date': item['first_purchase_date'].isoformat() if item['first_purchase_date'] else None,
            'last_purchase_date': item['last_purchase_date'].isoformat() if item['last_purchase_date'] else None,
            'customer_lifetime_days': item['customer_lifetime_days'],
            'purchase_frequency': item['purchase_frequency'],
            'favorite_category': item['favorite_category'],
            'credit_limit': self._decimal_to_float(item['credit_limit']),
            'credit_used': self._decimal_to_float(item['credit_used']),
            'loyalty_tier': item['loyalty_tier'],
            'status': item['status']
        }

    def _build_csv_response(
        self,
        summary: Dict[str, Any],
        customers: List[Dict[str, Any]],
        start_date: date,
        end_date: date,
        storefront_filters: Dict[str, Any]
    ) -> HttpResponse:
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        filename = f"top-customers-{start_date.isoformat()}-to-{end_date.isoformat()}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow(['Top Customers Report'])
        writer.writerow([f'Period: {start_date} to {end_date}'])
        if storefront_filters and storefront_filters.get('ids'):
            labels = storefront_filters.get('names') or storefront_filters.get('ids')
            writer.writerow(['Storefront Scope', ', '.join(labels)])
        else:
            writer.writerow(['Storefront Scope', 'All storefronts'])
        writer.writerow([])

        writer.writerow([
            'Customer Name', 'Email', 'Phone', 'Total Revenue', 'Total Purchases', 'Average Order Value',
            'First Purchase', 'Last Purchase', 'Lifetime (days)', 'Purchase Frequency', 'Favorite Category',
            'Credit Limit', 'Credit Used', 'Loyalty Tier', 'Status'
        ])

        for customer in customers:
            writer.writerow([
                customer['customer_name'],
                customer['email'],
                customer['phone'],
                f"{customer['total_revenue']:.2f}",
                customer['total_purchases'],
                f"{customer['average_order_value']:.2f}",
                customer['first_purchase_date'] or '',
                customer['last_purchase_date'] or '',
                customer['customer_lifetime_days'],
                customer['purchase_frequency'],
                customer['favorite_category'],
                f"{customer['credit_limit']:.2f}",
                f"{customer['credit_used']:.2f}",
                customer['loyalty_tier'],
                customer['status']
            ])

        return response

    def _build_pdf_response(
        self,
        summary: Dict[str, Any],
        customers: List[Dict[str, Any]],
        start_date: date,
        end_date: date,
        storefront_filters: Dict[str, Any]
    ) -> HttpResponse:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, title='Top Customers Report')
        styles = getSampleStyleSheet()
        elements: List[Any] = []

        title = f"Top Customers Report ({start_date.isoformat()} to {end_date.isoformat()})"
        elements.append(Paragraph(title, styles['Title']))
        elements.append(Spacer(1, 12))

        if storefront_filters and storefront_filters.get('ids'):
            labels = storefront_filters.get('names') or storefront_filters.get('ids')
            elements.append(Paragraph(f"Storefront Scope: {', '.join(labels)}", styles['Normal']))
        else:
            elements.append(Paragraph("Storefront Scope: All storefronts", styles['Normal']))
        elements.append(Spacer(1, 12))

        summary_table = Table([
            ['Total Customers', summary['total_customers']],
            ['Top 10 Revenue', f"{summary['top_10_revenue']:.2f}"],
            ['Top 10 Percentage', f"{summary['top_10_percentage']:.1f}%"],
            ['Average Customer Value', f"{summary['average_customer_value']:.2f}"]
        ], colWidths=[200, 200])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f2937')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f3f4f6')]),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.grey)
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 16))

        table_data = [[
            'Customer Name', 'Email', 'Phone', 'Total Revenue', 'Total Purchases', 'Average Order Value',
            'First Purchase', 'Last Purchase', 'Lifetime (days)', 'Frequency', 'Favorite Category',
            'Credit Limit', 'Credit Used', 'Loyalty Tier', 'Status'
        ]]

        for customer in customers:
            table_data.append([
                customer['customer_name'],
                customer['email'],
                customer['phone'],
                f"{customer['total_revenue']:.2f}",
                customer['total_purchases'],
                f"{customer['average_order_value']:.2f}",
                customer['first_purchase_date'] or '',
                customer['last_purchase_date'] or '',
                customer['customer_lifetime_days'],
                customer['purchase_frequency'],
                customer['favorite_category'],
                f"{customer['credit_limit']:.2f}",
                f"{customer['credit_used']:.2f}",
                customer['loyalty_tier'],
                customer['status']
            ])

        report_table = Table(table_data, repeatRows=1)
        report_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#047857')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.grey)
        ]))
        elements.append(report_table)

        if not customers:
            elements.append(Spacer(1, 12))
            elements.append(Paragraph('No customer data available for the selected period.', styles['Normal']))

        doc.build(elements)
        pdf_data = buffer.getvalue()
        buffer.close()

        response = HttpResponse(content_type='application/pdf')
        filename = f"top-customers-{start_date.isoformat()}-to-{end_date.isoformat()}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.write(pdf_data)
        return response

    def _calculate_purchase_frequency(self, order_dates: List[date]) -> str:
        if len(order_dates) <= 1:
            return 'monthly'
        sorted_dates = sorted(order_dates)
        gaps = [
            (sorted_dates[idx] - sorted_dates[idx - 1]).days
            for idx in range(1, len(sorted_dates))
        ]
        average_gap = sum(gaps) / len(gaps) if gaps else 30
        if average_gap <= 10:
            return 'weekly'
        if average_gap <= 25:
            return 'bi-weekly'
        return 'monthly'

    def _calculate_lifetime_days(
        self,
        first_purchase: Optional[date],
        last_purchase: Optional[date],
        start_date: date,
        end_date: date
    ) -> int:
        lifetime_start = min([d for d in [first_purchase, start_date] if d is not None])
        lifetime_end_candidates = [d for d in [last_purchase, end_date] if d is not None]
        lifetime_end = max(lifetime_end_candidates) if lifetime_end_candidates else end_date
        return (lifetime_end - lifetime_start).days + 1

    def _calculate_credit_used(self, customer: Customer) -> Decimal:
        outstanding = customer.outstanding_balance or Decimal('0.00')
        credit_limit = customer.credit_limit or Decimal('0.00')
        if outstanding > credit_limit:
            return credit_limit
        return outstanding

    def _determine_loyalty_tier(self, total_revenue: Decimal, total_purchases: int) -> str:
        if total_revenue >= Decimal('20000') or total_purchases >= 40:
            return 'platinum'
        if total_revenue >= Decimal('10000') or total_purchases >= 25:
            return 'gold'
        if total_revenue >= Decimal('5000') or total_purchases >= 15:
            return 'silver'
        if total_revenue >= Decimal('2000') or total_purchases >= 8:
            return 'bronze'
        return 'standard'

    def _determine_status(self, last_purchase: Optional[date], end_date: date) -> str:
        if not last_purchase:
            return 'inactive'
        days_since_last = (end_date - last_purchase).days
        if days_since_last <= 60:
            return 'active'
        if days_since_last <= 120:
            return 'at-risk'
        return 'inactive'

    def _normalize_date(self, value: Any) -> Optional[date]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        return None

    def _get_sales_dates(
        self,
        business_id: int,
        customer_ids: List[Any],
        start_date: date,
        end_date: date,
        storefront_ids: List[str]
    ) -> Dict[Any, List[date]]:
        sales_map: Dict[Any, List[date]] = defaultdict(list)
        if not customer_ids:
            return sales_map

        sales_queryset = Sale.objects.filter(
            business_id=business_id,
            customer_id__in=customer_ids,
            status__in=[Sale.STATUS_COMPLETED, Sale.STATUS_PARTIAL],
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
        if storefront_ids:
            sales_queryset = sales_queryset.filter(storefront_id__in=storefront_ids)

        sales = sales_queryset.values('customer_id', 'created_at').order_by('customer_id', 'created_at')

        for sale in sales:
            customer_id = sale['customer_id']
            created_at = sale['created_at']
            if customer_id and created_at:
                sales_map[customer_id].append(created_at.date())

        return sales_map

    def _get_favorite_categories(
        self,
        business_id: int,
        customer_ids: List[Any],
        start_date: date,
        end_date: date,
        storefront_ids: List[str]
    ) -> Dict[Any, str]:
        favorites: Dict[Any, str] = {}
        if not customer_ids:
            return favorites

        sale_items_queryset = SaleItem.objects.filter(
            sale__business_id=business_id,
            sale__customer_id__in=customer_ids,
            sale__status__in=[Sale.STATUS_COMPLETED, Sale.STATUS_PARTIAL],
            sale__created_at__date__gte=start_date,
            sale__created_at__date__lte=end_date
        )
        if storefront_ids:
            sale_items_queryset = sale_items_queryset.filter(sale__storefront_id__in=storefront_ids)

        sale_items = (
            sale_items_queryset
            .values('sale__customer_id', 'product__category__name')
            .annotate(total_revenue=Coalesce(Sum('total_price'), Decimal('0.00')))
            .order_by('sale__customer_id', '-total_revenue')
        )

        for item in sale_items:
            customer_id = item['sale__customer_id']
            if customer_id not in favorites:
                favorites[customer_id] = item['product__category__name'] or ''

        return favorites

    def _decimal_to_float(self, value: Decimal) -> float:
        return float(value.quantize(Decimal('0.01')))

    def _format_percentage(self, value: Decimal) -> float:
        return float(value.quantize(Decimal('0.1'))) if value is not None else 0.0

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
        if (error_response := filters.get('error_response')):
            return error_response

        business_id = filters.get('business_id')
        start_date = filters.get('start_date')
        end_date = filters.get('end_date')
        customer_type = request.GET.get('customer_type')
        min_revenue = request.GET.get('min_revenue')
        min_profit = request.GET.get('min_profit')
        sort_by = request.GET.get('sort_by', 'revenue')

        min_revenue_value = None
        if min_revenue:
            try:
                min_revenue_value = Decimal(min_revenue)
            except (InvalidOperation, TypeError):
                error = ReportError.create(
                    ReportError.INVALID_FILTER,
                    "Invalid min_revenue value",
                    {'min_revenue': min_revenue}
                )
                return ReportResponse.error(error)

        min_profit_value = None
        if min_profit:
            try:
                min_profit_value = Decimal(min_profit)
            except (InvalidOperation, TypeError):
                error = ReportError.create(
                    ReportError.INVALID_FILTER,
                    "Invalid min_profit value",
                    {'min_profit': min_profit}
                )
                return ReportResponse.error(error)
        
        # Build queryset
        queryset = Customer.objects.filter(is_active=True, business_id=business_id)
        
        if customer_type:
            queryset = queryset.filter(customer_type=customer_type)
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)

        sale_filters = Q(
            sales__status__in=[
                Sale.STATUS_COMPLETED,
                Sale.STATUS_PARTIAL
            ]
        )
        if start_date:
            sale_filters &= Q(sales__created_at__date__gte=start_date)
        if end_date:
            sale_filters &= Q(sales__created_at__date__lte=end_date)
        
        # Annotate with lifetime metrics
        queryset = queryset.annotate(
            total_revenue=Coalesce(Sum('sales__total_amount', filter=sale_filters), Decimal('0.00')),
            total_orders=Count('sales', filter=sale_filters),
            first_purchase=Min('sales__created_at', filter=sale_filters),
            last_purchase=Max('sales__created_at', filter=sale_filters)
        )
        
        if min_revenue_value is not None:
            queryset = queryset.filter(total_revenue__gte=min_revenue_value)

        customers = list(queryset)
        customer_ids = [customer.id for customer in customers]

        profits_by_customer = self._calculate_customer_profits(
            business_id=business_id,
            customer_ids=customer_ids,
            start_date=start_date,
            end_date=end_date
        )

        for customer in customers:
            customer.total_profit = profits_by_customer.get(customer.id, Decimal('0.00'))

        if min_profit_value is not None:
            customers = [
                customer for customer in customers
                if customer.total_profit >= min_profit_value
            ]

        # Build summary and customer details from annotated data
        summary = self._build_summary(customers)
        customer_details = self._build_customer_details(customers, sort_by)
        
        # Apply pagination
        paginated_customers, pagination = self.paginate_data(customer_details, request)
        
        metadata = {
            'customer_type': customer_type,
            'min_revenue': min_revenue,
            'min_profit': min_profit,
            'sort_by': sort_by,
            'pagination': pagination
        }

        return ReportResponse.success(summary, paginated_customers, metadata)

    def paginate_data(self, data: List[Dict[str, Any]], request) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Paginate in-memory customer data for response payloads."""
        page, page_size = self.get_pagination_params(request)
        total_records = len(data)
        start = (page - 1) * page_size
        end = start + page_size
        paginated = data[start:end]

        total_pages = (total_records + page_size - 1) // page_size if page_size else 1
        pagination_meta = {
            'page': page,
            'page_size': page_size,
            'total_pages': total_pages,
            'total_records': total_records,
            'has_next': page < total_pages,
            'has_previous': page > 1
        }

        return paginated, pagination_meta

    def _calculate_customer_profits(
        self,
        business_id: int,
        customer_ids: List[Any],
        start_date: date = None,
        end_date: date = None
    ) -> Dict[Any, Decimal]:
        """Calculate profit totals per customer using sale cost utility."""
        if not customer_ids:
            return {}

        sales_qs = Sale.objects.filter(
            business_id=business_id,
            customer_id__in=customer_ids,
            status__in=[Sale.STATUS_COMPLETED, Sale.STATUS_PARTIAL]
        )

        if start_date:
            sales_qs = sales_qs.filter(created_at__date__gte=start_date)
        if end_date:
            sales_qs = sales_qs.filter(created_at__date__lte=end_date)

        sale_costs = ProfitCalculator.calculate_sale_costs(sales_qs)
        profits = defaultdict(lambda: Decimal('0.00'))

        for sale in sales_qs:
            profit = sale_costs.get(sale.id, {}).get('profit', Decimal('0.00'))
            profits[sale.customer_id] += ProfitCalculator.to_decimal(profit)

        return dict(profits)

    def _build_summary(self, customers: List[Customer]) -> Dict[str, Any]:
        """Build summary statistics."""
        total_customers = len(customers)

        total_revenue = Decimal('0.00')
        total_profit = Decimal('0.00')
        total_orders = 0

        for customer in customers:
            total_revenue += customer.total_revenue or Decimal('0.00')
            total_profit += getattr(customer, 'total_profit', Decimal('0.00')) or Decimal('0.00')
            total_orders += customer.total_orders or 0

        avg_clv = total_revenue / total_customers if total_customers > 0 else Decimal('0.00')
        avg_profit = total_profit / total_customers if total_customers > 0 else Decimal('0.00')

        top_customer = max(
            customers,
            key=lambda c: c.total_revenue or Decimal('0.00'),
            default=None
        )
        top_customer_revenue = top_customer.total_revenue if top_customer else Decimal('0.00')

        top_10_pct = self._calculate_top_percent_contribution(customers, 10)

        def _quantize(value: Decimal) -> str:
            return str(value.quantize(Decimal('0.01')))

        return {
            'total_customers': total_customers,
            'total_revenue': _quantize(total_revenue) if total_customers else '0.00',
            'total_profit': _quantize(total_profit) if total_customers else '0.00',
            'total_orders': total_orders,
            'average_clv': _quantize(avg_clv),
            'average_profit_per_customer': _quantize(avg_profit),
            'top_customer_revenue': _quantize(top_customer_revenue) if total_customers else '0.00',
            'top_10_percent_contribution': top_10_pct
        }

    def _calculate_top_percent_contribution(self, customers: List[Customer], percent: int) -> float:
        """Calculate revenue contribution from top X percent of customers."""
        if not customers:
            return 0.0

        total_customers = len(customers)
        total_revenue = Decimal('0.00')

        for customer in customers:
            total_revenue += customer.total_revenue or Decimal('0.00')

        if total_revenue <= Decimal('0.00'):
            return 0.0

        top_count = max(1, int(total_customers * percent / 100))
        sorted_customers = sorted(
            customers,
            key=lambda c: c.total_revenue or Decimal('0.00'),
            reverse=True
        )

        top_revenue = Decimal('0.00')
        for customer in sorted_customers[:top_count]:
            top_revenue += customer.total_revenue or Decimal('0.00')

        contribution = (top_revenue / total_revenue) * Decimal('100.00')
        return round(float(contribution), 2)

    def _build_customer_details(self, customers: List[Customer], sort_by: str) -> List[Dict]:
        """Build detailed customer metrics."""

        def format_decimal(value: Decimal) -> str:
            return str((value or Decimal('0.00')).quantize(Decimal('0.01')))

        details: List[Dict[str, Any]] = []

        for customer in customers:
            total_revenue = customer.total_revenue or Decimal('0.00')
            total_profit = getattr(customer, 'total_profit', Decimal('0.00')) or Decimal('0.00')
            total_orders = customer.total_orders or 0

            profit_margin = (
                float(total_profit / total_revenue * Decimal('100.00'))
                if total_revenue > Decimal('0.00') else 0.0
            )
            aov = total_revenue / total_orders if total_orders > 0 else Decimal('0.00')

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

            details.append({
                'customer_id': str(customer.id),
                'customer_name': customer.name,
                'customer_type': customer.customer_type,
                'email': customer.email,
                'phone': customer.phone,
                'total_revenue': format_decimal(total_revenue),
                'total_profit': format_decimal(total_profit),
                'profit_margin': round(profit_margin, 2),
                'total_orders': total_orders,
                'average_order_value': format_decimal(aov),
                'first_purchase_date': first_date.isoformat() if first_date else None,
                'last_purchase_date': last_date.isoformat() if last_date else None,
                'days_as_customer': days_as_customer,
                'purchase_frequency_days': round(purchase_frequency, 1),
                'rank': 0  # Placeholder, will be set after sorting
            })

        sort_key_map = {
            'revenue': lambda item: Decimal(item['total_revenue']),
            'profit': lambda item: Decimal(item['total_profit']),
            'orders': lambda item: item['total_orders'],
            'aov': lambda item: Decimal(item['average_order_value'])
        }

        if sort_by not in sort_key_map:
            sort_by = 'revenue'

        reverse = True
        details.sort(key=sort_key_map[sort_by], reverse=reverse)

        for idx, item in enumerate(details, start=1):
            item['rank'] = idx

        return details


class CustomerSegmentationReportView(BaseReportView):
    """
    Customer Segmentation API matching frontend contract.
    
    GET /reports/api/customer/segmentation/
    
    Delivers RFM-based segmentation insights, segment metadata, and
    recommended actions for CustomerSegmentationPage.tsx.
    
    Query Parameters:
    - segmentation_method: rfm|value|behavior (default: rfm)
    - start_date: YYYY-MM-DD (default: 90 days ago)
    - end_date: YYYY-MM-DD (default: today)
    - storefront_id: UUID (optional)
    - segment: segment code filter (optional)
    - export_format: csv|pdf (optional)
    
    Response Format:
    {
        "success": true,
        "data": {
            "method": "rfm",
            "insights": {...},
            "segments": [...]
        }
    }
    """
    
    permission_classes = [IsAuthenticated]
    default_date_range_days = 90
    max_date_range_days = 730
    CACHE_TIMEOUT = 600
    
    VALID_METHODS = {'rfm', 'value', 'behavior'}
    
    # RFM segment definitions
    RFM_SEGMENTS = {
        'Champions': {
            'code': 'R5F5M5',
            'description': 'Recent, frequent, high spenders',
            'condition': lambda r, f, m: r >= 4 and f >= 4 and m >= 4,
            'actions': [
                'Offer VIP loyalty perks',
                'Invite to referral programs',
                'Early access to new collections'
            ]
        },
        'Loyal Customers': {
            'code': 'R4F4M4',
            'description': 'Consistent, reliable purchasers',
            'condition': lambda r, f, m: r >= 3 and f >= 3 and m >= 3 and not (r >= 4 and f >= 4 and m >= 4),
            'actions': [
                'Cross-sell complementary products',
                'Provide exclusive deals',
                'Gather feedback for product development'
            ]
        },
        'Potential Loyalists': {
            'code': 'R4F2M3',
            'description': 'Recent customers with growth potential',
            'condition': lambda r, f, m: r >= 4 and 2 <= f < 4 and m >= 2,
            'actions': [
                'Onboarding nurture campaigns',
                'Educational content series',
                'Limited-time incentives'
            ]
        },
        'Promising': {
            'code': 'R3F2M2',
            'description': 'Moderate engagement, can be developed',
            'condition': lambda r, f, m: 3 <= r < 4 and 2 <= f < 3 and 2 <= m < 4,
            'actions': [
                'Encourage repeat purchases',
                'Highlight popular items',
                'Moderate discount offers'
            ]
        },
        'At Risk': {
            'code': 'R2F2M3',
            'description': 'Previously loyal but recent activity dipping',
            'condition': lambda r, f, m: r <= 2 and f >= 2 and m >= 3,
            'actions': [
                'Send win-back offers',
                'Trigger churn prevention drip',
                'Survey to understand drop-off'
            ]
        },
        'Need Attention': {
            'code': 'R2F3M3',
            'description': 'Valuable customers showing warning signs',
            'condition': lambda r, f, m: r <= 2 and f >= 3 and 2 <= m < 3,
            'actions': [
                'Personalized re-engagement emails',
                'Loyalty program reminders',
                'Special occasion outreach'
            ]
        },
        'New Customers': {
            'code': 'R5F1M1',
            'description': 'Recently acquired, low frequency',
            'condition': lambda r, f, m: r >= 4 and f <= 1,
            'actions': [
                'Welcome series automation',
                'First-purchase follow-up',
                'Product recommendations'
            ]
        },
        'Hibernating': {
            'code': 'R1F1M2',
            'description': 'Low engagement across all metrics',
            'condition': lambda r, f, m: r <= 2 and f <= 2 and m <= 2,
            'actions': [
                'Deep discount win-back',
                'Re-activation campaign',
                'Sunset messaging if unresponsive'
            ]
        }
    }
    
    def get(self, request):
        """Generate customer segmentation report matching frontend contract."""
        filters = self.parse_filters(request)
        if (error_response := filters.get('error_response')):
            return error_response
        
        business_id = filters.get('business_id')
        start_date = filters.get('start_date')
        end_date = filters.get('end_date') or timezone.now().date()
        if not start_date:
            start_date = end_date - timedelta(days=self.default_date_range_days)
        
        segmentation_method = request.GET.get('segmentation_method', 'rfm').lower()
        if segmentation_method not in self.VALID_METHODS:
            return Response({
                'success': False,
                'error': 'Invalid segmentation method',
                'message': f"method must be one of: {', '.join(sorted(self.VALID_METHODS))}"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        storefront_id = request.GET.get('storefront_id')
        segment_filter = request.GET.get('segment')
        export_format = request.GET.get('export_format')
        
        if export_format and export_format.lower() not in {'csv', 'pdf'}:
            return Response({
                'success': False,
                'error': 'Invalid export format',
                'message': "export_format must be 'csv' or 'pdf'"
            }, status=status.HTTP_400_BAD_REQUEST)
        
        cache_key = self._build_cache_key(
            business_id,
            start_date,
            end_date,
            segmentation_method,
            storefront_id
        )
        
        dataset = cache.get(cache_key)
        if dataset is None:
            dataset = self._calculate_segmentation(
                business_id=business_id,
                start_date=start_date,
                end_date=end_date,
                method=segmentation_method,
                storefront_id=storefront_id
            )
            cache.set(cache_key, dataset, self.CACHE_TIMEOUT)
        
        if segment_filter:
            dataset['segments'] = [
                seg for seg in dataset['segments']
                if seg['segment_code'] == segment_filter or seg['segment_name'] == segment_filter
            ]
        
        if export_format:
            if export_format.lower() == 'csv':
                return self._export_csv(dataset, start_date, end_date)
            elif export_format.lower() == 'pdf':
                return self._export_pdf(dataset, start_date, end_date)
        
        return Response({
            'success': True,
            'data': dataset
        }, status=status.HTTP_200_OK)
    
    def _calculate_segmentation(
        self,
        *,
        business_id: int,
        start_date: date,
        end_date: date,
        method: str,
        storefront_id: Optional[str]
    ) -> Dict[str, Any]:
        """Calculate segmentation based on method."""
        if method == 'rfm':
            return self._calculate_rfm_segmentation(
                business_id,
                start_date,
                end_date,
                storefront_id
            )
        elif method == 'value':
            # Future implementation
            return {
                'method': 'value',
                'insights': self._empty_insights(),
                'segments': []
            }
        elif method == 'behavior':
            # Future implementation
            return {
                'method': 'behavior',
                'insights': self._empty_insights(),
                'segments': []
            }
        else:
            return {
                'method': method,
                'insights': self._empty_insights(),
                'segments': []
            }
    
    def _calculate_rfm_segmentation(
        self,
        business_id: int,
        start_date: date,
        end_date: date,
        storefront_id: Optional[str]
    ) -> Dict[str, Any]:
        """Calculate RFM segmentation with scores and characteristics."""
        
        # Build base queryset for sales in period
        sales_qs = Sale.objects.filter(
            business_id=business_id,
            status__in=[Sale.STATUS_COMPLETED, Sale.STATUS_PARTIAL],
            customer__isnull=False
        ).annotate(
            order_date=Coalesce('completed_at', 'created_at', output_field=DateTimeField())
        ).filter(
            order_date__date__gte=start_date,
            order_date__date__lte=end_date
        )
        
        if storefront_id:
            sales_qs = sales_qs.filter(storefront_id=storefront_id)
        
        # Get customer IDs with activity in period
        customer_ids = set(sales_qs.values_list('customer_id', flat=True))
        
        if not customer_ids:
            return {
                'method': 'rfm',
                'insights': self._empty_insights(),
                'segments': []
            }
        
        # Fetch all sales for these customers to calculate lifetime metrics
        customer_sales_qs = Sale.objects.filter(
            business_id=business_id,
            customer_id__in=customer_ids,
            status__in=[Sale.STATUS_COMPLETED, Sale.STATUS_PARTIAL]
        ).select_related('customer')
        
        if storefront_id:
            customer_sales_qs = customer_sales_qs.filter(storefront_id=storefront_id)
        
        # Aggregate customer metrics
        customer_data = {}
        for sale in customer_sales_qs:
            cid = sale.customer_id
            order_date = sale.completed_at or sale.created_at
            net_revenue = (sale.total_amount or Decimal('0.00')) - (sale.amount_refunded or Decimal('0.00'))
            
            if cid not in customer_data:
                customer_data[cid] = {
                    'customer': sale.customer,
                    'order_dates': [],
                    'total_spend': Decimal('0.00'),
                    'order_count': 0
                }
            
            customer_data[cid]['order_dates'].append(order_date)
            customer_data[cid]['total_spend'] += net_revenue
            customer_data[cid]['order_count'] += 1
        
        # Calculate RFM metrics
        today = timezone.now()
        rfm_scores = []
        
        for cid, data in customer_data.items():
            if not data['order_dates']:
                continue
            
            most_recent = max(data['order_dates'])
            recency_days = (today - most_recent).days
            frequency = data['order_count']
            monetary = data['total_spend']
            
            rfm_scores.append({
                'customer_id': cid,
                'customer': data['customer'],
                'recency_days': recency_days,
                'frequency': frequency,
                'monetary': monetary,
                'order_dates': data['order_dates']
            })
        
        if not rfm_scores:
            return {
                'method': 'rfm',
                'insights': self._empty_insights(),
                'segments': []
            }
        
        # Calculate quintile scores
        recency_values = sorted([item['recency_days'] for item in rfm_scores])
        frequency_values = sorted([item['frequency'] for item in rfm_scores], reverse=True)
        monetary_values = sorted([float(item['monetary']) for item in rfm_scores], reverse=True)
        
        for item in rfm_scores:
            item['r_score'] = self._calculate_quintile_score(
                item['recency_days'],
                recency_values,
                reverse=True
            )
            item['f_score'] = self._calculate_quintile_score(
                item['frequency'],
                frequency_values,
                reverse=False
            )
            item['m_score'] = self._calculate_quintile_score(
                float(item['monetary']),
                monetary_values,
                reverse=False
            )
        
        # Classify into segments
        segments_data = defaultdict(lambda: {
            'customers': [],
            'total_revenue': Decimal('0.00'),
            'total_orders': 0,
            'recency_days_list': [],
            'frequency_list': [],
            'monetary_list': []
        })
        
        for item in rfm_scores:
            segment_name = self._classify_rfm_segment(
                item['r_score'],
                item['f_score'],
                item['m_score']
            )
            
            segment = segments_data[segment_name]
            segment['customers'].append(item)
            segment['total_revenue'] += item['monetary']
            segment['total_orders'] += item['frequency']
            segment['recency_days_list'].append(item['recency_days'])
            segment['frequency_list'].append(item['frequency'])
            segment['monetary_list'].append(float(item['monetary']))
        
        # Build segment output
        segments = []
        total_customers = len(rfm_scores)
        
        for segment_name, config in self.RFM_SEGMENTS.items():
            if segment_name not in segments_data:
                continue
            
            data = segments_data[segment_name]
            customer_count = len(data['customers'])
            
            if customer_count == 0:
                continue
            
            avg_recency = sum(data['recency_days_list']) / customer_count
            avg_frequency = sum(data['frequency_list']) / customer_count
            avg_monetary = sum(data['monetary_list']) / customer_count
            avg_order_value = float(data['total_revenue']) / data['total_orders'] if data['total_orders'] > 0 else 0
            
            # Calculate average RFM scores
            r_scores = [c['r_score'] for c in data['customers']]
            f_scores = [c['f_score'] for c in data['customers']]
            m_scores = [c['m_score'] for c in data['customers']]
            
            segments.append({
                'segment_name': segment_name,
                'segment_code': config['code'],
                'description': config['description'],
                'customer_count': customer_count,
                'total_revenue': float(data['total_revenue']),
                'average_order_value': round(avg_order_value, 2),
                'recency_score': round(sum(r_scores) / customer_count),
                'frequency_score': round(sum(f_scores) / customer_count),
                'monetary_score': round(sum(m_scores) / customer_count),
                'characteristics': {
                    'avg_days_since_last_purchase': int(round(avg_recency)),
                    'avg_purchase_frequency': round(avg_frequency, 1),
                    'avg_total_spend': round(avg_monetary, 2)
                },
                'recommended_actions': config['actions']
            })
        
        # Sort by total revenue descending
        segments.sort(key=lambda x: x['total_revenue'], reverse=True)
        
        # Calculate insights
        insights = self._calculate_insights(segments, rfm_scores)
        
        return {
            'method': 'rfm',
            'insights': insights,
            'segments': segments
        }
    
    def _calculate_quintile_score(
        self,
        value: float,
        sorted_values: List[float],
        reverse: bool = False
    ) -> int:
        """Calculate quintile score (1-5) for a value."""
        if not sorted_values or len(sorted_values) == 0:
            return 3
        
        n = len(sorted_values)
        
        # Find position in sorted list
        pos = 0
        for i, v in enumerate(sorted_values):
            if value <= v:
                pos = i
                break
            pos = i + 1
        
        # Convert to quintile (1-5)
        quintile = min(5, max(1, int((pos / n) * 5) + 1))
        
        if reverse:
            quintile = 6 - quintile
        
        return quintile
    
    def _classify_rfm_segment(self, r: int, f: int, m: int) -> str:
        """Classify customer into RFM segment based on scores."""
        for segment_name, config in self.RFM_SEGMENTS.items():
            if config['condition'](r, f, m):
                return segment_name
        
        # Default fallback
        return 'Hibernating'
    
    def _calculate_insights(
        self,
        segments: List[Dict[str, Any]],
        rfm_scores: List[Dict[str, Any]]
    ) -> Dict[str, Optional[str]]:
        """Calculate high-level insights from segments."""
        if not segments:
            return self._empty_insights()
        
        # Highest revenue segment
        highest_revenue = max(segments, key=lambda x: x['total_revenue'])
        
        # Largest segment by customer count
        largest = max(segments, key=lambda x: x['customer_count'])
        
        # Needs attention: segments with declining engagement
        attention_segments = ['At Risk', 'Need Attention', 'Hibernating']
        needs_attention_list = [
            seg for seg in segments
            if seg['segment_name'] in attention_segments
        ]
        needs_attention = max(
            needs_attention_list,
            key=lambda x: x['customer_count']
        )['segment_name'] if needs_attention_list else None
        
        # Fastest growing: use Potential Loyalists and New Customers as proxy
        growth_segments = ['Potential Loyalists', 'Promising', 'New Customers']
        growth_list = [
            seg for seg in segments
            if seg['segment_name'] in growth_segments
        ]
        fastest_growing = max(
            growth_list,
            key=lambda x: x['customer_count']
        )['segment_name'] if growth_list else None
        
        return {
            'highest_revenue_segment': highest_revenue['segment_name'],
            'largest_segment': largest['segment_name'],
            'fastest_growing_segment': fastest_growing,
            'needs_attention': needs_attention
        }
    
    def _empty_insights(self) -> Dict[str, Optional[str]]:
        """Return empty insights structure."""
        return {
            'highest_revenue_segment': None,
            'largest_segment': None,
            'fastest_growing_segment': None,
            'needs_attention': None
        }
    
    def _build_cache_key(
        self,
        business_id: int,
        start_date: date,
        end_date: date,
        method: str,
        storefront_id: Optional[str]
    ) -> str:
        """Build cache key for segmentation results."""
        return (
            f'customer_segmentation:{business_id}:'
            f'{start_date}:{end_date}:{method}:'
            f'{storefront_id or "all"}'
        )
    
    def _export_csv(
        self,
        dataset: Dict[str, Any],
        start_date: date,
        end_date: date
    ) -> HttpResponse:
        """Export segmentation data as CSV."""
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        
        writer.writerow(['Customer Segmentation Report'])
        writer.writerow([f'Method: {dataset["method"].upper()}'])
        writer.writerow([f'Period: {start_date} to {end_date}'])
        writer.writerow([])
        
        # Insights
        writer.writerow(['Insights'])
        insights = dataset['insights']
        writer.writerow(['Highest Revenue Segment', insights.get('highest_revenue_segment') or 'N/A'])
        writer.writerow(['Largest Segment', insights.get('largest_segment') or 'N/A'])
        writer.writerow(['Fastest Growing', insights.get('fastest_growing_segment') or 'N/A'])
        writer.writerow(['Needs Attention', insights.get('needs_attention') or 'N/A'])
        writer.writerow([])
        
        # Segments
        writer.writerow([
            'Segment Name',
            'Segment Code',
            'Description',
            'Customer Count',
            'Total Revenue',
            'Average Order Value',
            'Recency Score',
            'Frequency Score',
            'Monetary Score',
            'Avg Days Since Purchase',
            'Avg Purchase Frequency',
            'Avg Total Spend',
            'Recommended Actions'
        ])
        
        for segment in dataset['segments']:
            chars = segment['characteristics']
            actions = '; '.join(segment['recommended_actions'])
            
            writer.writerow([
                segment['segment_name'],
                segment['segment_code'],
                segment['description'],
                segment['customer_count'],
                f"{segment['total_revenue']:.2f}",
                f"{segment['average_order_value']:.2f}",
                segment['recency_score'],
                segment['frequency_score'],
                segment['monetary_score'],
                chars['avg_days_since_last_purchase'],
                chars['avg_purchase_frequency'],
                f"{chars['avg_total_spend']:.2f}",
                actions
            ])
        
        response = HttpResponse(buffer.getvalue(), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = (
            f'attachment; filename="customer-segmentation-{start_date}-to-{end_date}.csv"'
        )
        return response
    
    def _export_pdf(
        self,
        dataset: Dict[str, Any],
        start_date: date,
        end_date: date
    ) -> HttpResponse:
        """Export segmentation data as PDF."""
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(letter))
        styles = getSampleStyleSheet()
        elements = []
        
        # Title
        elements.append(Paragraph('Customer Segmentation Report', styles['Title']))
        elements.append(Paragraph(
            f'Method: {dataset["method"].upper()} | Period: {start_date} to {end_date}',
            styles['Normal']
        ))
        elements.append(Spacer(1, 12))
        
        # Insights
        insights = dataset['insights']
        insights_table = Table([
            ['Highest Revenue Segment', insights.get('highest_revenue_segment') or 'N/A'],
            ['Largest Segment', insights.get('largest_segment') or 'N/A'],
            ['Fastest Growing', insights.get('fastest_growing_segment') or 'N/A'],
            ['Needs Attention', insights.get('needs_attention') or 'N/A']
        ], colWidths=[200, 200])
        insights_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f3f4f6')),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.grey)
        ]))
        elements.append(insights_table)
        elements.append(Spacer(1, 16))
        
        # Segments
        table_data = [[
            'Segment',
            'Code',
            'Count',
            'Revenue',
            'AOV',
            'R',
            'F',
            'M',
            'Days',
            'Freq',
            'Spend'
        ]]
        
        for segment in dataset['segments']:
            chars = segment['characteristics']
            table_data.append([
                segment['segment_name'][:20],
                segment['segment_code'],
                segment['customer_count'],
                f"${segment['total_revenue']:,.0f}",
                f"${segment['average_order_value']:,.0f}",
                segment['recency_score'],
                segment['frequency_score'],
                segment['monetary_score'],
                chars['avg_days_since_last_purchase'],
                f"{chars['avg_purchase_frequency']:.1f}",
                f"${chars['avg_total_spend']:,.0f}"
            ])
        
        segments_table = Table(table_data, repeatRows=1)
        segments_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f2937')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.grey)
        ]))
        elements.append(segments_table)
        
        doc.build(elements)
        pdf_data = buffer.getvalue()
        buffer.close()
        
        response = HttpResponse(pdf_data, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="customer-segmentation-{start_date}-to-{end_date}.pdf"'
        )
        return response
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
            total_purchases=Count(
                'sales',
                filter=Q(
                    sales__status__in=[
                        Sale.STATUS_COMPLETED,
                        Sale.STATUS_PARTIAL
                    ]
                )
            ),
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


class CreditUtilizationReportView(BaseReportView):
    """Credit utilization analytics for the customer dashboard contract."""

    permission_classes = [IsAuthenticated]
    default_date_range_days = 90
    max_date_range_days = 365
    CACHE_TIMEOUT = 600
    DEFAULT_THRESHOLD = 80
    VALID_SEGMENTS = {'all', 'retail', 'wholesale'}
    VALID_SORT_FIELDS = {'utilization', 'amount', 'risk'}

    def get(self, request):
        filters = self.parse_filters(request)
        if (error_response := filters.get('error_response')):
            return error_response

        business_id = filters.get('business_id')
        start_date = filters.get('start_date')
        end_date = filters.get('end_date') or timezone.now().date()
        if not start_date:
            start_date = end_date - timedelta(days=self.default_date_range_days)

        threshold_param = request.GET.get('utilization_threshold', str(self.DEFAULT_THRESHOLD))
        try:
            utilization_threshold = int(threshold_param)
        except (TypeError, ValueError):
            return Response({
                'success': False,
                'error': 'Invalid utilization_threshold',
                'message': 'utilization_threshold must be an integer between 0 and 100'
            }, status=status.HTTP_400_BAD_REQUEST)

        if not 0 <= utilization_threshold <= 100:
            return Response({
                'success': False,
                'error': 'Invalid utilization_threshold',
                'message': 'utilization_threshold must be between 0 and 100'
            }, status=status.HTTP_400_BAD_REQUEST)

        sort_by = request.GET.get('sort_by', 'utilization').lower()
        if sort_by not in self.VALID_SORT_FIELDS:
            return Response({
                'success': False,
                'error': 'Invalid sort_by',
                'message': f"sort_by must be one of {', '.join(sorted(self.VALID_SORT_FIELDS))}"
            }, status=status.HTTP_400_BAD_REQUEST)

        segment = request.GET.get('segment', 'all').lower()
        if segment not in self.VALID_SEGMENTS:
            return Response({
                'success': False,
                'error': 'Invalid segment',
                'message': "segment must be one of 'retail', 'wholesale', or 'all'"
            }, status=status.HTTP_400_BAD_REQUEST)

        storefront_id = request.GET.get('storefront_id') or None

        export_format = request.GET.get('export_format')
        if export_format:
            export_format = export_format.lower()
            if export_format not in {'csv', 'pdf'}:
                return Response({
                    'success': False,
                    'error': 'Invalid export_format',
                    'message': "export_format must be 'csv' or 'pdf'"
                }, status=status.HTTP_400_BAD_REQUEST)

        cache_key = self._build_cache_key(
            business_id,
            start_date,
            end_date,
            segment,
            storefront_id,
            utilization_threshold
        )

        dataset = cache.get(cache_key)
        if dataset is None:
            customers = self._get_customers_queryset(business_id, segment)
            dataset = self._calculate_report(
                business_id=business_id,
                customers=customers,
                start_date=start_date,
                end_date=end_date,
                storefront_id=storefront_id,
                utilization_threshold=utilization_threshold
            )
            cache.set(cache_key, dataset, self.CACHE_TIMEOUT)

        customers_sorted = self._sort_customers(dataset['customers'], sort_by)

        if export_format == 'csv':
            return self._build_csv_response(
                dataset['summary'],
                customers_sorted,
                dataset['risk_distribution'],
                start_date,
                end_date
            )
        if export_format == 'pdf':
            return self._build_pdf_response(
                dataset['summary'],
                customers_sorted,
                dataset['risk_distribution'],
                start_date,
                end_date
            )

        page, page_size = self.get_pagination_params(request)
        total_count = len(customers_sorted)
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        customers_paginated = customers_sorted[start_index:end_index]

        total_pages = (total_count + page_size - 1) // page_size if page_size else 1
        pagination_meta = {
            'page': page,
            'page_size': page_size,
            'total_count': total_count,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_previous': page > 1
        }

        payload = {
            'success': True,
            'data': {
                'summary': dataset['summary'],
                'customers': customers_paginated,
                'risk_distribution': dataset['risk_distribution']
            },
            'meta': {
                'generated_at': timezone.now().isoformat(),
                'filters': {
                    'segment': segment,
                    'storefront_id': storefront_id,
                    'sort_by': sort_by,
                    'utilization_threshold': utilization_threshold,
                    'start_date': start_date.isoformat() if start_date else None,
                    'end_date': end_date.isoformat() if end_date else None
                },
                'pagination': pagination_meta
            }
        }
        return Response(payload, status=status.HTTP_200_OK)

    def _get_customers_queryset(self, business_id: int, segment: str) -> List[Customer]:
        queryset = Customer.objects.filter(
            business_id=business_id
        ).filter(
            Q(credit_limit__gt=0) | Q(outstanding_balance__gt=0)
        )

        if segment == 'retail':
            queryset = queryset.filter(customer_type='RETAIL')
        elif segment == 'wholesale':
            queryset = queryset.filter(customer_type='WHOLESALE')

        return list(queryset)

    def _calculate_report(
        self,
        *,
        business_id: int,
        customers: List[Customer],
        start_date: date,
        end_date: date,
        storefront_id: Optional[str],
        utilization_threshold: int
    ) -> Dict[str, Any]:
        if not customers:
            return {
                'summary': self._empty_summary(),
                'customers': [],
                'risk_distribution': {'low': 0, 'medium': 0, 'high': 0}
            }

        customer_lookup = {customer.id: customer for customer in customers}
        customer_ids = list(customer_lookup.keys())

        credit_used_map: Dict[Any, Decimal] = defaultdict(lambda: Decimal('0.00'))
        max_overdue_map: Dict[Any, int] = defaultdict(int)

        ar_queryset = self._get_accounts_receivable_queryset(
            business_id,
            customer_ids,
            start_date,
            end_date,
            storefront_id
        )

        for ar in ar_queryset:
            customer = customer_lookup.get(ar.customer_id)
            if not customer:
                continue

            sale_date = None
            if ar.sale and ar.sale.created_at:
                sale_date = ar.sale.created_at.date()
            elif ar.created_at:
                sale_date = ar.created_at.date()

            in_range = True
            if sale_date:
                if start_date and sale_date < start_date:
                    in_range = False
                if end_date and sale_date > end_date:
                    in_range = False

            outstanding = self._to_decimal(ar.amount_outstanding)
            if not in_range and outstanding <= 0:
                continue

            if outstanding > 0:
                credit_used_map[ar.customer_id] += outstanding

            overdue_days = self._compute_overdue_days(ar, customer, end_date)
            if overdue_days > max_overdue_map[ar.customer_id]:
                max_overdue_map[ar.customer_id] = overdue_days

        payments_map: Dict[Any, Dict[str, Any]] = {}
        payments_queryset = self._get_payments_queryset(
            business_id,
            customer_ids,
            start_date,
            end_date,
            storefront_id
        )

        for payment in payments_queryset.order_by('-payment_date'):
            customer_id = payment.accounts_receivable.customer_id
            if customer_id not in customer_lookup:
                continue
            if customer_id not in payments_map:
                payments_map[customer_id] = {
                    'date': payment.payment_date.date(),
                    'amount': self._to_decimal(payment.amount)
                }

        summary_totals = {
            'credit_extended': Decimal('0.00'),
            'credit_used': Decimal('0.00'),
            'utilization_sum': Decimal('0.00'),
            'over_threshold': 0,
            'at_limit': 0,
            'risk_counts': {'low': 0, 'medium': 0, 'high': 0}
        }

        customers_payload: List[Dict[str, Any]] = []
        decimal_threshold = Decimal(str(utilization_threshold))

        for customer in customers:
            customer_id = customer.id
            credit_limit = self._to_decimal(customer.credit_limit)
            credit_used = credit_used_map.get(customer_id, Decimal('0.00'))

            if credit_used == Decimal('0.00') and not storefront_id:
                credit_used = self._to_decimal(customer.outstanding_balance)

            if credit_used < Decimal('0.00'):
                credit_used = Decimal('0.00')

            credit_available = credit_limit - credit_used
            if credit_available < Decimal('0.00'):
                credit_available = Decimal('0.00')

            if credit_limit <= Decimal('0.00') and credit_used > Decimal('0.00'):
                utilization_value = Decimal('150.0')
            elif credit_limit > Decimal('0.00'):
                utilization_value = (credit_used / credit_limit) * Decimal('100')
            else:
                utilization_value = Decimal('0.0')

            if utilization_value > Decimal('150.0'):
                utilization_value = Decimal('150.0')

            max_overdue = max_overdue_map.get(customer_id, 0)

            payment_info = payments_map.get(customer_id)
            last_payment_date = payment_info['date'] if payment_info else None
            last_payment_amount = payment_info['amount'] if payment_info else Decimal('0.00')

            payment_history_score = self._calculate_payment_history_score(
                utilization_value,
                max_overdue,
                last_payment_date,
                end_date
            )

            risk_level = self._classify_risk_level(
                utilization_value,
                max_overdue,
                payment_history_score
            )
            recommended_action = self._determine_recommended_action(
                risk_level,
                utilization_value,
                max_overdue,
                payment_history_score
            )

            summary_totals['credit_extended'] += credit_limit
            summary_totals['credit_used'] += credit_used
            summary_totals['utilization_sum'] += utilization_value

            if utilization_value >= decimal_threshold:
                summary_totals['over_threshold'] += 1

            if credit_limit > Decimal('0.00') and credit_used >= credit_limit:
                summary_totals['at_limit'] += 1
            elif credit_limit <= Decimal('0.00') and credit_used > Decimal('0.00'):
                summary_totals['at_limit'] += 1

            summary_totals['risk_counts'][risk_level] += 1

            customers_payload.append({
                'customer_id': str(customer_id),
                'customer_name': customer.name or '',
                'credit_limit': self._decimal_to_float(credit_limit),
                'credit_used': self._decimal_to_float(credit_used),
                'credit_available': self._decimal_to_float(credit_available),
                'utilization_percentage': self._round_percentage(utilization_value),
                'outstanding_balance': self._decimal_to_float(credit_used),
                'days_overdue': int(max_overdue),
                'payment_history_score': payment_history_score,
                'risk_level': risk_level,
                'recommended_action': recommended_action,
                'last_payment_date': last_payment_date.isoformat() if last_payment_date else None,
                'last_payment_amount': self._decimal_to_float(last_payment_amount),
            })

        total_customers = len(customers_payload)
        if total_customers > 0:
            average_utilization = self._round_percentage(
                summary_totals['utilization_sum'] / Decimal(total_customers)
            )
        else:
            average_utilization = 0.0

        summary = {
            'total_customers_with_credit': total_customers,
            'total_credit_extended': self._decimal_to_float(summary_totals['credit_extended']),
            'total_credit_used': self._decimal_to_float(summary_totals['credit_used']),
            'average_utilization': average_utilization,
            'over_80_percent': summary_totals['over_threshold'],
            'at_limit': summary_totals['at_limit'],
            'credit_risk_high': summary_totals['risk_counts']['high']
        }

        risk_distribution = {
            'low': summary_totals['risk_counts']['low'],
            'medium': summary_totals['risk_counts']['medium'],
            'high': summary_totals['risk_counts']['high']
        }

        return {
            'summary': summary,
            'customers': customers_payload,
            'risk_distribution': risk_distribution
        }

    def _get_accounts_receivable_queryset(
        self,
        business_id: int,
        customer_ids: List[Any],
        start_date: date,
        end_date: date,
        storefront_id: Optional[str]
    ):
        queryset = AccountsReceivable.objects.filter(
            customer__business_id=business_id,
            customer_id__in=customer_ids
        )
        if storefront_id:
            queryset = queryset.filter(sale__storefront_id=storefront_id)

        date_filters = []
        if start_date:
            date_filters.append(Q(sale__created_at__date__gte=start_date))
        if end_date:
            date_filters.append(Q(sale__created_at__date__lte=end_date))

        if date_filters:
            combined = date_filters[0]
            for extra in date_filters[1:]:
                combined &= extra
            queryset = queryset.filter(combined | Q(amount_outstanding__gt=Decimal('0.00')))

        return queryset.select_related('sale', 'customer')

    def _get_payments_queryset(
        self,
        business_id: int,
        customer_ids: List[Any],
        start_date: date,
        end_date: date,
        storefront_id: Optional[str]
    ):
        queryset = ARPayment.objects.filter(
            accounts_receivable__customer__business_id=business_id,
            accounts_receivable__customer_id__in=customer_ids
        )
        if storefront_id:
            queryset = queryset.filter(accounts_receivable__sale__storefront_id=storefront_id)
        if start_date:
            queryset = queryset.filter(payment_date__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(payment_date__date__lte=end_date)
        return queryset.select_related('accounts_receivable__customer')

    def _compute_overdue_days(self, ar, customer: Customer, reference_date: date) -> int:
        if not reference_date:
            reference_date = timezone.now().date()

        due_date = ar.due_date
        if not due_date:
            if ar.sale and ar.sale.created_at:
                sale_date = ar.sale.created_at.date()
            elif ar.created_at:
                sale_date = ar.created_at.date()
            else:
                sale_date = reference_date
            credit_terms = customer.credit_terms_days or 0
            due_date = sale_date + timedelta(days=credit_terms)

        outstanding = self._to_decimal(ar.amount_outstanding)
        if outstanding <= 0 or not due_date or reference_date <= due_date:
            return 0

        return (reference_date - due_date).days

    def _calculate_payment_history_score(
        self,
        utilization: Decimal,
        max_days_overdue: int,
        last_payment_date: Optional[date],
        reference_date: date
    ) -> int:
        score = 100
        utilization_value = float(utilization)

        if utilization_value >= 110:
            score -= 25
        elif utilization_value >= 90:
            score -= 20
        elif utilization_value >= 75:
            score -= 12
        elif utilization_value >= 60:
            score -= 8
        elif utilization_value >= 40:
            score -= 4

        if max_days_overdue >= 60:
            score -= 30
        elif max_days_overdue >= 30:
            score -= 20
        elif max_days_overdue > 0:
            score -= 10

        if last_payment_date:
            days_since_payment = (reference_date - last_payment_date).days
            if days_since_payment > 90:
                score -= 20
            elif days_since_payment > 60:
                score -= 15
            elif days_since_payment > 30:
                score -= 10
            elif days_since_payment > 15:
                score -= 5
        else:
            score -= 15

        if utilization_value <= 60 and max_days_overdue == 0:
            score += 5

        return max(0, min(100, int(round(score))))

    def _classify_risk_level(
        self,
        utilization: Decimal,
        max_days_overdue: int,
        payment_history_score: int
    ) -> str:
        utilization_value = float(utilization)
        if utilization_value >= 90 or max_days_overdue > 30 or payment_history_score <= 60:
            return 'high'
        if (
            70 <= utilization_value < 90
            or 1 <= max_days_overdue <= 30
            or 61 <= payment_history_score <= 79
        ):
            return 'medium'
        return 'low'

    def _determine_recommended_action(
        self,
        risk_level: str,
        utilization: Decimal,
        max_days_overdue: int,
        payment_history_score: int
    ) -> str:
        utilization_value = float(utilization)

        if risk_level == 'high':
            if utilization_value >= 100 or max_days_overdue > 30:
                return 'reduce_limit'
            return 'monitor'

        if risk_level == 'medium':
            return 'monitor'

        if risk_level == 'low' and utilization_value <= 60 and payment_history_score >= 80:
            return 'increase_limit'

        return 'monitor'

    def _sort_customers(self, customers: List[Dict[str, Any]], sort_by: str) -> List[Dict[str, Any]]:
        if sort_by == 'utilization':
            return sorted(
                customers,
                key=lambda item: (
                    -item['utilization_percentage'],
                    -item['credit_used'],
                    (item['customer_name'] or '').lower()
                )
            )
        if sort_by == 'amount':
            return sorted(
                customers,
                key=lambda item: (
                    -item['credit_used'],
                    -item['utilization_percentage'],
                    (item['customer_name'] or '').lower()
                )
            )
        if sort_by == 'risk':
            risk_order = {'high': 0, 'medium': 1, 'low': 2}
            return sorted(
                customers,
                key=lambda item: (
                    risk_order.get(item['risk_level'], 3),
                    -item['utilization_percentage'],
                    -item['credit_used'],
                    (item['customer_name'] or '').lower()
                )
            )
        return customers

    def _decimal_to_float(self, value: Decimal) -> float:
        decimal_value = self._to_decimal(value)
        return float(decimal_value.quantize(Decimal('0.01')))

    def _round_percentage(self, value: Decimal) -> float:
        return float(self._to_decimal(value).quantize(Decimal('0.1')))

    def _to_decimal(self, value: Any) -> Decimal:
        if value is None:
            return Decimal('0.00')
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError):
            return Decimal('0.00')

    def _empty_summary(self) -> Dict[str, Any]:
        return {
            'total_customers_with_credit': 0,
            'total_credit_extended': 0,
            'total_credit_used': 0,
            'average_utilization': 0,
            'over_80_percent': 0,
            'at_limit': 0,
            'credit_risk_high': 0
        }

    def _build_cache_key(
        self,
        business_id: int,
        start_date: Optional[date],
        end_date: Optional[date],
        segment: str,
        storefront_id: Optional[str],
        utilization_threshold: int
    ) -> str:
        return (
            f'credit_utilization:{business_id}:'
            f'{start_date.isoformat() if start_date else "none"}:'
            f'{end_date.isoformat() if end_date else "none"}:'
            f'{segment}:'
            f'{storefront_id or "all"}:'
            f'{utilization_threshold}'
        )

    def _build_csv_response(
        self,
        summary: Dict[str, Any],
        customers: List[Dict[str, Any]],
        risk_distribution: Dict[str, int],
        start_date: date,
        end_date: date
    ) -> HttpResponse:
        buffer = io.StringIO()
        writer = csv.writer(buffer)

        writer.writerow(['Credit Utilization Report'])
        writer.writerow([f'Date Range: {start_date} to {end_date}'])
        writer.writerow([])

        writer.writerow(['Summary'])
        writer.writerow(['Total Customers With Credit', summary['total_customers_with_credit']])
        writer.writerow(['Total Credit Extended', f"{summary['total_credit_extended']:.2f}"])
        writer.writerow(['Total Credit Used', f"{summary['total_credit_used']:.2f}"])
        writer.writerow(['Average Utilization (%)', f"{summary['average_utilization']:.1f}%"])
        writer.writerow(['Customers Above Threshold', summary['over_80_percent']])
        writer.writerow(['Customers At Limit', summary['at_limit']])
        writer.writerow(['High Risk Customers', summary['credit_risk_high']])
        writer.writerow([])

        writer.writerow(['Risk Distribution'])
        writer.writerow(['Risk Level', 'Count'])
        for level in ['low', 'medium', 'high']:
            writer.writerow([level, risk_distribution.get(level, 0)])
        writer.writerow([])

        writer.writerow([
            'Customer Name',
            'Customer ID',
            'Credit Limit',
            'Credit Used',
            'Credit Available',
            'Utilization %',
            'Outstanding Balance',
            'Days Overdue',
            'Payment History Score',
            'Risk Level',
            'Recommended Action',
            'Last Payment Date',
            'Last Payment Amount'
        ])

        for item in customers:
            writer.writerow([
                item['customer_name'],
                item['customer_id'],
                f"{item['credit_limit']:.2f}",
                f"{item['credit_used']:.2f}",
                f"{item['credit_available']:.2f}",
                f"{item['utilization_percentage']:.1f}%",
                f"{item['outstanding_balance']:.2f}",
                item['days_overdue'],
                item['payment_history_score'],
                item['risk_level'],
                item['recommended_action'],
                item['last_payment_date'] or '',
                f"{item['last_payment_amount']:.2f}",
            ])

        response = HttpResponse(buffer.getvalue(), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = (
            f'attachment; filename="credit-utilization-{start_date}-to-{end_date}.csv"'
        )
        return response

    def _build_pdf_response(
        self,
        summary: Dict[str, Any],
        customers: List[Dict[str, Any]],
        risk_distribution: Dict[str, int],
        start_date: date,
        end_date: date
    ) -> HttpResponse:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, title='Credit Utilization Report')
        styles = getSampleStyleSheet()
        elements: List[Any] = []

        elements.append(Paragraph('Credit Utilization Report', styles['Title']))
        elements.append(Paragraph(f'Date Range: {start_date} to {end_date}', styles['Normal']))
        elements.append(Spacer(1, 12))

        summary_table = Table([
            ['Total Customers With Credit', summary['total_customers_with_credit']],
            ['Total Credit Extended', f"{summary['total_credit_extended']:.2f}"],
            ['Total Credit Used', f"{summary['total_credit_used']:.2f}"],
            ['Average Utilization (%)', f"{summary['average_utilization']:.1f}%"],
            ['Above Threshold', summary['over_80_percent']],
            ['At Limit', summary['at_limit']],
            ['High Risk Customers', summary['credit_risk_high']]
        ], colWidths=[220, 180])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#111827')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f3f4f6')]),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.grey)
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 16))

        risk_table = Table([
            ['Risk Level', 'Count'],
            ['Low', risk_distribution.get('low', 0)],
            ['Medium', risk_distribution.get('medium', 0)],
            ['High', risk_distribution.get('high', 0)]
        ], colWidths=[200, 200])
        risk_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#047857')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.grey)
        ]))
        elements.append(risk_table)
        elements.append(Spacer(1, 16))

        table_data = [[
            'Customer Name',
            'Credit Limit',
            'Credit Used',
            'Utilization %',
            'Days Overdue',
            'Risk',
            'Recommendation',
            'Last Payment',
            'Payment Amount'
        ]]

        for item in customers:
            table_data.append([
                item['customer_name'],
                f"{item['credit_limit']:.2f}",
                f"{item['credit_used']:.2f}",
                f"{item['utilization_percentage']:.1f}%",
                item['days_overdue'],
                item['risk_level'].title(),
                item['recommended_action'].replace('_', ' ').title(),
                item['last_payment_date'] or '',
                f"{item['last_payment_amount']:.2f}"
            ])

        customers_table = Table(table_data, repeatRows=1)
        customers_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1d4ed8')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#eef2ff')]),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.grey)
        ]))
        elements.append(customers_table)

        doc.build(elements)
        pdf_data = buffer.getvalue()
        buffer.close()

        response = HttpResponse(pdf_data, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="credit-utilization-{start_date}-to-{end_date}.pdf"'
        )
        return response


class PurchasePatternAnalysisReportView(BaseReportView):
    """
    Customer Purchase Patterns API (reports/api/customer/purchase-patterns/)

    Delivers segment performance, behavioural metrics, product preferences, and
    channel mix in the structure required by the frontend dashboard. Supports
    optional CSV/PDF exports and caches heavy computations for 10 minutes.
    """

    permission_classes = [IsAuthenticated]
    default_date_range_days = None
    max_date_range_days = 365

    CACHE_TIMEOUT = 600
    CHANNEL_IN_STORE = 'in_store'
    CHANNEL_ONLINE = 'online'
    CHANNEL_PHONE = 'phone'

    SEGMENT_KEY_MAP = {
        'new': 'new_customers',
        'returning': 'returning_customers',
        'vip': 'vip_customers',
        'at_risk': 'at_risk_customers',
    }

    DAY_NAMES = list(calendar.day_name)

    def get(self, request):
        """Return JSON payload or export for purchase pattern analytics."""
        filters = self.parse_filters(
            request,
            default_days=self.default_date_range_days,
            max_days=self.max_date_range_days
        )
        if (error_response := filters.get('error_response')):
            return error_response

        business_id = filters.get('business_id')
        start_date = filters.get('start_date')
        end_date = filters.get('end_date')

        if not start_date or not end_date:
            error = ReportError.create(
                ReportError.MISSING_REQUIRED_PARAM,
                'start_date and end_date are required',
                {}
            )
            return ReportResponse.error(error)

        segment_raw = request.GET.get('segment')
        segment_filter = self._normalize_segment(segment_raw)
        if segment_raw and segment_filter is None:
            error = ReportError.create(
                ReportError.INVALID_FILTER,
                'Invalid segment value',
                {'segment': segment_raw}
            )
            return ReportResponse.error(error)

        storefront_id = request.GET.get('storefront_id')
        channel = request.GET.get('channel')
        if channel and channel not in {self.CHANNEL_IN_STORE, self.CHANNEL_ONLINE, self.CHANNEL_PHONE}:
            error = ReportError.create(
                ReportError.INVALID_FILTER,
                'Invalid channel value',
                {'channel': channel}
            )
            return ReportResponse.error(error)

        export_format = request.GET.get('export_format')
        if export_format:
            export_format = export_format.lower()
            if export_format not in {'csv', 'pdf'}:
                error = ReportError.create(
                    ReportError.INVALID_FILTER,
                    'export_format must be csv or pdf',
                    {'export_format': export_format}
                )
                return ReportResponse.error(error)

        currency_config = self._get_currency_config(business_id)
        self._set_currency_context(currency_config)

        cache_key = self._build_cache_key(
            business_id,
            start_date,
            end_date,
            segment_filter,
            storefront_id,
            channel,
            currency_config
        )

        payload = cache.get(cache_key)
        if payload is None:
            payload = self._calculate_purchase_patterns(
                business_id,
                start_date,
                end_date,
                segment_filter,
                storefront_id,
                channel
            )
            cache.set(cache_key, payload, self.CACHE_TIMEOUT)

        if export_format == 'csv':
            return self._export_csv(payload, start_date, end_date)
        if export_format == 'pdf':
            return self._export_pdf(payload, start_date, end_date)

        return Response({
            'success': True,
            'data': payload
        })

    def _calculate_purchase_patterns(
        self,
        business_id: int,
        start_date: date,
        end_date: date,
        segment_filter: Optional[str],
        storefront_id: Optional[str],
        channel: Optional[str]
    ) -> Dict[str, Any]:
        sales_qs = self._get_sales_queryset(
            business_id,
            start_date,
            end_date,
            storefront_id,
            channel
        )

        sales = list(
            sales_qs.select_related('customer', 'storefront').prefetch_related(
                'sale_items__product__category'
            )
        )

        sale_records, customer_ids = self._collect_sale_records(sales)
        if not sale_records:
            return self._empty_payload()

        history_map = self._get_customer_history(
            business_id,
            customer_ids,
            storefront_id,
            channel
        )

        segments = self._determine_segments(
            history_map,
            start_date,
            end_date,
            customer_ids
        )

        aggregate_all = self._aggregate_sales(sale_records)
        segments_summary = self._build_segments_summary(
            segments,
            aggregate_all,
            history_map,
            end_date
        )

        selected_ids = segments.get(segment_filter, set()) if segment_filter else None
        aggregate_filtered = self._aggregate_sales(sale_records, selected_ids)

        purchase_behavior = self._build_purchase_behavior(aggregate_filtered)
        product_preferences = self._build_product_preferences(aggregate_filtered)
        channel_preferences = self._build_channel_preferences(aggregate_filtered)

        if segment_filter:
            segments_summary = self._apply_segment_filter(segments_summary, segment_filter)

        return {
            'segments': segments_summary,
            'purchase_behavior': purchase_behavior,
            'product_preferences': product_preferences,
            'channel_preferences': channel_preferences
        }

    def _get_sales_queryset(
        self,
        business_id: int,
        start_date: date,
        end_date: date,
        storefront_id: Optional[str],
        channel: Optional[str]
    ):
        queryset = Sale.objects.filter(
            business_id=business_id,
            status__in=[Sale.STATUS_COMPLETED, Sale.STATUS_PARTIAL],
            customer__isnull=False
        )

        queryset = queryset.annotate(
            order_date=Coalesce('completed_at', 'created_at', output_field=DateTimeField()),
            derived_channel=self._channel_case()
        ).filter(
            order_date__date__gte=start_date,
            order_date__date__lte=end_date
        )

        if storefront_id:
            queryset = queryset.filter(storefront_id=storefront_id)
        if channel:
            queryset = queryset.filter(derived_channel=channel)

        return queryset

    def _channel_case(self) -> Case:
        return Case(
            When(storefront__isnull=False, then=Value(self.CHANNEL_IN_STORE)),
            When(payment_type=Sale.PAYMENT_TYPE_MOBILE, then=Value(self.CHANNEL_PHONE)),
            default=Value(self.CHANNEL_ONLINE),
            output_field=CharField()
        )

    def _collect_sale_records(self, sales: List[Sale]) -> Tuple[List[Dict[str, Any]], set]:
        sale_records: List[Dict[str, Any]] = []
        customer_ids: set = set()

        for sale in sales:
            if not sale.customer_id:
                continue

            order_date = getattr(sale, 'order_date', None) or sale.completed_at or sale.created_at
            net_revenue = (sale.total_amount or Decimal('0.00')) - (sale.amount_refunded or Decimal('0.00'))

            categories = set()
            category_revenue = defaultdict(lambda: Decimal('0.00'))
            total_items = Decimal('0.00')

            for item in sale.sale_items.all():
                quantity = Decimal(item.quantity or 0)
                total_items += quantity
                category_name = (
                    item.product.category.name
                    if getattr(item.product, 'category', None)
                    else 'Uncategorized'
                )
                categories.add(category_name)
                line_total = Decimal(item.total_price or Decimal('0.00'))
                category_revenue[category_name] += line_total

            sale_records.append({
                'customer_id': sale.customer_id,
                'order_date': order_date,
                'net_revenue': net_revenue,
                'items': total_items,
                'categories': categories,
                'category_revenue': dict(category_revenue),
                'channel': getattr(sale, 'derived_channel', None) or self.CHANNEL_ONLINE,
            })
            customer_ids.add(sale.customer_id)

        return sale_records, customer_ids

    def _get_customer_history(
        self,
        business_id: int,
        customer_ids: Set[Any],
        storefront_id: Optional[str],
        channel: Optional[str]
    ) -> Dict[Any, Dict[str, Any]]:
        if not customer_ids:
            return {}

        queryset = Sale.objects.filter(
            business_id=business_id,
            status__in=[Sale.STATUS_COMPLETED, Sale.STATUS_PARTIAL],
            customer_id__in=customer_ids
        ).annotate(
            order_date=Coalesce('completed_at', 'created_at', output_field=DateTimeField()),
            derived_channel=self._channel_case()
        )

        if storefront_id:
            queryset = queryset.filter(storefront_id=storefront_id)
        if channel:
            queryset = queryset.filter(derived_channel=channel)

        net_revenue_expr = (F('total_amount') - F('amount_refunded'))

        history = {}
        for row in queryset.values('customer_id').annotate(
            first_purchase=Min('order_date'),
            last_purchase=Max('order_date'),
            lifetime_revenue=Sum(net_revenue_expr, output_field=DecimalField(max_digits=18, decimal_places=2)),
            total_orders=Count('id')
        ):
            history[row['customer_id']] = {
                'first_purchase': row['first_purchase'],
                'last_purchase': row['last_purchase'],
                'lifetime_revenue': row['lifetime_revenue'] or Decimal('0.00'),
                'total_orders': row['total_orders'] or 0
            }

        return history

    def _determine_segments(
        self,
        history_map: Dict[Any, Dict[str, Any]],
        start_date: date,
        end_date: date,
        active_customer_ids: Set[Any]
    ) -> Dict[str, Set[Any]]:
        segments = {
            'new': set(),
            'returning': set(),
            'vip': set(),
            'at_risk': set()
        }

        if not history_map:
            return segments

        active_ids = set(active_customer_ids)
        vip_candidates = [
            (cid, data['lifetime_revenue'])
            for cid, data in history_map.items()
            if cid in active_ids
        ]

        vip_candidates.sort(key=lambda item: item[1], reverse=True)
        if vip_candidates:
            vip_count = max(1, int(len(vip_candidates) * 0.1))
            segments['vip'] = {cid for cid, _ in vip_candidates[:vip_count]}

        for cid, data in history_map.items():
            if cid not in active_ids:
                continue

            first = data['first_purchase'].date() if data['first_purchase'] else None
            last = data['last_purchase'].date() if data['last_purchase'] else None

            if first and start_date <= first <= end_date:
                segments['new'].add(cid)
            if first and first < start_date:
                segments['returning'].add(cid)
            if last:
                days_since_last = (end_date - last).days
                if 61 <= days_since_last <= 120:
                    segments['at_risk'].add(cid)

        return segments

    def _aggregate_sales(
        self,
        sale_records: List[Dict[str, Any]],
        customer_filter: Optional[Set[Any]] = None
    ) -> Dict[str, Any]:
        if customer_filter is not None:
            customer_filter = set(customer_filter)
            if not customer_filter:
                return self._empty_aggregate()

        customer_stats: Dict[Any, Dict[str, Any]] = {}
        total_orders = 0
        total_revenue = Decimal('0.00')
        total_items = Decimal('0.00')
        order_totals: List[Decimal] = []
        cross_sell_orders = 0
        day_metrics = defaultdict(lambda: {'count': 0, 'revenue': Decimal('0.00')})
        hour_metrics = defaultdict(lambda: {'count': 0, 'revenue': Decimal('0.00')})
        channel_counts: Counter = Counter()
        category_stats: Dict[str, Dict[str, Any]] = {}

        for record in sale_records:
            cid = record['customer_id']
            if customer_filter is not None and cid not in customer_filter:
                continue

            total_orders += 1
            total_revenue += record['net_revenue']
            total_items += record['items']
            order_totals.append(record['net_revenue'])

            if len(record['categories']) >= 2:
                cross_sell_orders += 1

            channel_counts[record['channel']] += 1

            stats = customer_stats.setdefault(
                cid,
                {'orders': 0, 'revenue': Decimal('0.00'), 'items': Decimal('0.00'), 'order_dates': []}
            )
            stats['orders'] += 1
            stats['revenue'] += record['net_revenue']
            stats['items'] += record['items']
            if record['order_date']:
                stats['order_dates'].append(record['order_date'])
                day_index = record['order_date'].weekday()
                day_metrics[day_index]['count'] += 1
                day_metrics[day_index]['revenue'] += record['net_revenue']
                hour = record['order_date'].hour
                hour_metrics[hour]['count'] += 1
                hour_metrics[hour]['revenue'] += record['net_revenue']

            for category_name, revenue in record['category_revenue'].items():
                cat_stats = category_stats.setdefault(
                    category_name,
                    {
                        'revenue': Decimal('0.00'),
                        'customers': set(),
                        'order_counts': defaultdict(int)
                    }
                )
                cat_stats['revenue'] += revenue
                cat_stats['customers'].add(cid)
                cat_stats['order_counts'][cid] += 1

        return {
            'customer_stats': customer_stats,
            'total_orders': total_orders,
            'total_revenue': total_revenue,
            'total_items': total_items,
            'order_totals': order_totals,
            'cross_sell_orders': cross_sell_orders,
            'day_metrics': dict(day_metrics),
            'hour_metrics': dict(hour_metrics),
            'channel_counts': channel_counts,
            'category_stats': category_stats,
        }

    def _empty_aggregate(self) -> Dict[str, Any]:
        return {
            'customer_stats': {},
            'total_orders': 0,
            'total_revenue': Decimal('0.00'),
            'total_items': Decimal('0.00'),
            'order_totals': [],
            'cross_sell_orders': 0,
            'day_metrics': {},
            'hour_metrics': {},
            'channel_counts': Counter(),
            'category_stats': {},
        }

    def _build_segments_summary(
        self,
        segments: Dict[str, set],
        aggregate: Dict[str, Any],
        history_map: Dict[Any, Dict[str, Any]],
        end_date: date
    ) -> Dict[str, Dict[str, Any]]:
        customer_stats = aggregate['customer_stats']
        total_customers = len(customer_stats)
        total_revenue_all = aggregate['total_revenue']

        def metrics_for(segment_ids: set) -> Tuple[int, Decimal, int, Decimal]:
            count = len(segment_ids)
            revenue = Decimal('0.00')
            orders = 0
            for cid in segment_ids:
                stats = customer_stats.get(cid)
                if not stats:
                    continue
                revenue += stats['revenue']
                orders += stats['orders']
            avg_order_value = revenue / orders if orders else Decimal('0.00')
            return count, revenue, orders, avg_order_value

        new_ids = segments.get('new', set())
        new_count, new_revenue, new_orders, new_aov = metrics_for(new_ids)
        new_conversion = round((new_count / total_customers) * 100, 1) if total_customers else 0.0
        retained_new = sum(
            1 for cid in new_ids if customer_stats.get(cid, {}).get('orders', 0) > 1
        )
        new_retention = round((retained_new / new_count) * 100, 1) if new_count else 0.0

        returning_ids = segments.get('returning', set())
        returning_count, returning_revenue, returning_orders, returning_aov = metrics_for(returning_ids)
        recent_cutoff = end_date - timedelta(days=30)
        retained_returning = 0
        for cid in returning_ids:
            stats = customer_stats.get(cid)
            if not stats or not stats['order_dates']:
                continue
            most_recent = max(stats['order_dates']).date()
            if most_recent >= recent_cutoff:
                retained_returning += 1
        returning_retention = round((retained_returning / returning_count) * 100, 1) if returning_count else 0.0

        vip_ids = segments.get('vip', set())
        vip_count, vip_revenue, vip_orders, vip_aov = metrics_for(vip_ids)
        vip_percentage = (
            round((vip_revenue / total_revenue_all) * 100, 1)
            if total_revenue_all and vip_revenue
            else 0.0
        )

        at_risk_ids = segments.get('at_risk', set())
        at_risk_count, at_risk_revenue, at_risk_orders, at_risk_aov = metrics_for(at_risk_ids)
        last_purchase_days = []
        potential_lost_revenue = Decimal('0.00')
        for cid in at_risk_ids:
            history = history_map.get(cid)
            stats = customer_stats.get(cid)
            if history and history.get('last_purchase'):
                last_purchase_days.append((end_date - history['last_purchase'].date()).days)
            if stats and stats['orders']:
                potential_lost_revenue += stats['revenue'] / stats['orders']
        last_purchase_avg = round(sum(last_purchase_days) / len(last_purchase_days)) if last_purchase_days else 0

        return {
            'new_customers': {
                'count': new_count,
                'total_revenue': self._decimal_to_float(new_revenue),
                'average_order_value': self._decimal_to_float(new_aov),
                'conversion_rate': new_conversion,
                'retention_rate': new_retention
            },
            'returning_customers': {
                'count': returning_count,
                'total_revenue': self._decimal_to_float(returning_revenue),
                'average_order_value': self._decimal_to_float(returning_aov),
                'retention_rate': returning_retention
            },
            'vip_customers': {
                'count': vip_count,
                'total_revenue': self._decimal_to_float(vip_revenue),
                'average_order_value': self._decimal_to_float(vip_aov),
                'percentage_of_total': vip_percentage
            },
            'at_risk_customers': {
                'count': at_risk_count,
                'total_revenue': self._decimal_to_float(at_risk_revenue),
                'average_order_value': self._decimal_to_float(at_risk_aov),
                'last_purchase_days_avg': last_purchase_avg,
                'potential_lost_revenue': self._decimal_to_float(potential_lost_revenue)
            }
        }

    def _apply_segment_filter(
        self,
        segments_summary: Dict[str, Dict[str, Any]],
        segment_filter: str
    ) -> Dict[str, Dict[str, Any]]:
        selected_key = self.SEGMENT_KEY_MAP.get(segment_filter)
        if not selected_key:
            return segments_summary

        filtered = {}
        for key, values in segments_summary.items():
            if key == selected_key:
                filtered[key] = values
            else:
                filtered[key] = {field: 0 for field in values}
        return filtered

    def _build_purchase_behavior(self, aggregate: Dict[str, Any]) -> Dict[str, Any]:
        total_orders = aggregate['total_orders']
        if total_orders == 0:
            return {
                'average_time_between_purchases': 0,
                'peak_purchase_day': None,
                'peak_purchase_hour': None,
                'average_items_per_order': 0,
                'cross_sell_rate': 0,
                'up_sell_rate': 0
            }

        intervals = []
        for stats in aggregate['customer_stats'].values():
            dates = sorted(stats['order_dates'])
            for idx in range(1, len(dates)):
                intervals.append((dates[idx].date() - dates[idx - 1].date()).days)

        average_interval = round(sum(intervals) / len(intervals)) if intervals else 0

        avg_items = round(float(aggregate['total_items']) / total_orders, 1) if total_orders else 0

        avg_order_value = aggregate['total_revenue'] / total_orders if total_orders else Decimal('0.00')
        upsell_orders = sum(1 for total in aggregate['order_totals'] if total > avg_order_value)
        up_sell_rate = round((upsell_orders / total_orders) * 100, 1) if total_orders else 0.0

        cross_sell_rate = round(
            (aggregate['cross_sell_orders'] / total_orders) * 100,
            1
        ) if total_orders else 0.0

        peak_day = self._resolve_peak_label(aggregate['day_metrics'], label_type='day')
        peak_hour = self._resolve_peak_label(aggregate['hour_metrics'], label_type='hour')

        return {
            'average_time_between_purchases': average_interval,
            'peak_purchase_day': peak_day,
            'peak_purchase_hour': peak_hour,
            'average_items_per_order': avg_items,
            'cross_sell_rate': cross_sell_rate,
            'up_sell_rate': up_sell_rate
        }

    def _build_product_preferences(self, aggregate: Dict[str, Any]) -> List[Dict[str, Any]]:
        preferences: List[Dict[str, Any]] = []
        for category, stats in aggregate['category_stats'].items():
            customer_count = len(stats['customers'])
            if customer_count == 0:
                continue
            total_revenue = stats['revenue']
            repeat_customers = sum(1 for count in stats['order_counts'].values() if count >= 2)
            repeat_rate = round((repeat_customers / customer_count) * 100, 1) if customer_count else 0.0
            average_spend = total_revenue / customer_count if customer_count else Decimal('0.00')

            preferences.append({
                'category': category,
                'customer_count': customer_count,
                'total_revenue': self._decimal_to_float(total_revenue),
                'average_spend': self._decimal_to_float(average_spend),
                'repeat_purchase_rate': repeat_rate
            })

        preferences.sort(key=lambda item: item['total_revenue'], reverse=True)
        return preferences[:10]

    def _build_channel_preferences(self, aggregate: Dict[str, Any]) -> Dict[str, float]:
        total_orders = aggregate['total_orders']
        if total_orders == 0:
            return {
                self.CHANNEL_IN_STORE: 0,
                self.CHANNEL_ONLINE: 0,
                self.CHANNEL_PHONE: 0
            }

        return {
            self.CHANNEL_IN_STORE: round((aggregate['channel_counts'].get(self.CHANNEL_IN_STORE, 0) / total_orders) * 100, 1),
            self.CHANNEL_ONLINE: round((aggregate['channel_counts'].get(self.CHANNEL_ONLINE, 0) / total_orders) * 100, 1),
            self.CHANNEL_PHONE: round((aggregate['channel_counts'].get(self.CHANNEL_PHONE, 0) / total_orders) * 100, 1),
        }

    def _resolve_peak_label(self, metrics: Dict[int, Dict[str, Any]], label_type: str) -> Any:
        if not metrics:
            return None

        ordered = sorted(
            metrics.items(),
            key=lambda item: (item[1]['count'], item[1]['revenue']),
            reverse=True
        )
        key, _ = ordered[0]
        if label_type == 'day':
            return self.DAY_NAMES[key]
        return int(key)

    def _get_currency_config(self, business_id: int) -> Dict[str, Any]:
        default_regional = BusinessSettings.get_default_regional()
        default_currency = (default_regional.get('currency') or {}).copy()

        config: Dict[str, Any] = dict(default_currency)
        settings_obj = BusinessSettings.objects.filter(business_id=business_id).only('regional').first()
        if settings_obj and isinstance(settings_obj.regional, dict):
            currency_settings = settings_obj.regional.get('currency') or {}
            config.update(currency_settings)

        code = config.get('code') or default_currency.get('code') or 'USD'
        symbol = config.get('symbol') or default_currency.get('symbol') or '$'
        position = config.get('position') or default_currency.get('position') or 'before'
        decimal_places = config.get('decimalPlaces', default_currency.get('decimalPlaces', 2))
        if not isinstance(decimal_places, int) or decimal_places < 0:
            decimal_places = default_currency.get('decimalPlaces', 2) or 2

        config.update({
            'code': code,
            'symbol': symbol,
            'position': position,
            'decimalPlaces': decimal_places
        })
        return config

    def _set_currency_context(self, currency_config: Dict[str, Any]) -> None:
        decimal_places = currency_config.get('decimalPlaces', 2)
        if not isinstance(decimal_places, int) or decimal_places < 0:
            decimal_places = 2
        quantizer = Decimal('1') if decimal_places == 0 else Decimal('1') / (Decimal('10') ** decimal_places)
        self.currency_config = currency_config
        self.currency_decimal_places = decimal_places
        self.currency_quantizer = quantizer

    def _quantize_to_currency(self, value: Decimal | int | float | None) -> Decimal:
        if value is None:
            value = Decimal('0')
        elif not isinstance(value, Decimal):
            try:
                value = Decimal(str(value))
            except (InvalidOperation, ValueError):
                value = Decimal('0')

        decimal_places = getattr(self, 'currency_decimal_places', 2)
        quantizer = getattr(
            self,
            'currency_quantizer',
            Decimal('1') if decimal_places == 0 else Decimal('0.01')
        )

        return value.quantize(quantizer, rounding=ROUND_HALF_UP)

    def _decimal_to_float(self, value: Decimal | int | float | None) -> float:
        quantized = self._quantize_to_currency(value)
        return float(quantized)

    def _format_currency(self, value: Decimal | int | float | None, include_commas: bool = False) -> str:
        quantized = self._quantize_to_currency(value)
        decimal_places = getattr(self, 'currency_decimal_places', 2)
        format_spec = f"{{:,.{decimal_places}f}}" if include_commas else f"{{:.{decimal_places}f}}"
        return format_spec.format(quantized)

    def _empty_payload(self) -> Dict[str, Any]:
        return {
            'segments': {
                'new_customers': {
                    'count': 0,
                    'total_revenue': 0,
                    'average_order_value': 0,
                    'conversion_rate': 0,
                    'retention_rate': 0
                },
                'returning_customers': {
                    'count': 0,
                    'total_revenue': 0,
                    'average_order_value': 0,
                    'retention_rate': 0
                },
                'vip_customers': {
                    'count': 0,
                    'total_revenue': 0,
                    'average_order_value': 0,
                    'percentage_of_total': 0
                },
                'at_risk_customers': {
                    'count': 0,
                    'total_revenue': 0,
                    'average_order_value': 0,
                    'last_purchase_days_avg': 0,
                    'potential_lost_revenue': 0
                }
            },
            'purchase_behavior': {
                'average_time_between_purchases': 0,
                'peak_purchase_day': None,
                'peak_purchase_hour': None,
                'average_items_per_order': 0,
                'cross_sell_rate': 0,
                'up_sell_rate': 0
            },
            'product_preferences': [],
            'channel_preferences': {
                self.CHANNEL_IN_STORE: 0,
                self.CHANNEL_ONLINE: 0,
                self.CHANNEL_PHONE: 0
            }
        }

    def _normalize_segment(self, segment_value: Optional[str]) -> Optional[str]:
        if not segment_value:
            return None
        normalized = segment_value.strip().lower().replace('-', '_')
        return normalized if normalized in self.SEGMENT_KEY_MAP else None

    def _build_cache_key(
        self,
        business_id: int,
        start_date: date,
        end_date: date,
        segment_filter: Optional[str],
        storefront_id: Optional[str],
        channel: Optional[str],
        currency_config: Optional[Dict[str, Any]]
    ) -> str:
        currency_signature = 'default'
        if currency_config:
            code = currency_config.get('code') or currency_config.get('symbol') or 'default'
            decimal_places = currency_config.get('decimalPlaces')
            currency_signature = f"{code}-{decimal_places if decimal_places is not None else 'na'}"
        return (
            f'purchase_patterns:{business_id}:{start_date}:{end_date}:'
            f'{segment_filter or "all"}:{storefront_id or "all"}:{channel or "all"}:{currency_signature}'
        )

    def _export_csv(self, data: Dict[str, Any], start_date: date, end_date: date) -> HttpResponse:
        buffer = io.StringIO()
        writer = csv.writer(buffer)

        writer.writerow(['Customer Purchase Patterns Report'])
        writer.writerow([f'Date Range: {start_date} to {end_date}'])
        currency_meta = getattr(self, 'currency_config', {})
        writer.writerow([
            f"Currency: {currency_meta.get('code', '')} ({currency_meta.get('symbol', '')})"
        ])
        writer.writerow([])

        writer.writerow(['Segments'])
        writer.writerow([
            'Segment', 'Count', 'Total Revenue', 'Average Order Value',
            'Conversion Rate', 'Retention Rate', 'Percentage of Total',
            'Last Purchase Days Avg', 'Potential Lost Revenue'
        ])

        segment_labels = [
            ('new_customers', 'New Customers'),
            ('returning_customers', 'Returning Customers'),
            ('vip_customers', 'VIP Customers'),
            ('at_risk_customers', 'At-Risk Customers')
        ]

        for key, label in segment_labels:
            segment = data['segments'].get(key, {})
            writer.writerow([
                label,
                segment.get('count', 0),
                self._format_currency(segment.get('total_revenue', 0)),
                self._format_currency(segment.get('average_order_value', 0)),
                segment.get('conversion_rate', ''),
                segment.get('retention_rate', ''),
                segment.get('percentage_of_total', '') if key == 'vip_customers' else '',
                segment.get('last_purchase_days_avg', '') if key == 'at_risk_customers' else '',
                self._format_currency(segment.get('potential_lost_revenue', 0)) if key == 'at_risk_customers' else ''
            ])

        writer.writerow([])
        behavior = data['purchase_behavior']
        writer.writerow(['Purchase Behaviour'])
        writer.writerow(['Average Time Between Purchases', behavior.get('average_time_between_purchases', 0)])
        writer.writerow(['Peak Purchase Day', behavior.get('peak_purchase_day') or ''])
        writer.writerow(['Peak Purchase Hour', behavior.get('peak_purchase_hour') if behavior.get('peak_purchase_hour') is not None else ''])
        writer.writerow(['Average Items Per Order', behavior.get('average_items_per_order', 0)])
        writer.writerow(['Cross Sell Rate (%)', behavior.get('cross_sell_rate', 0)])
        writer.writerow(['Up Sell Rate (%)', behavior.get('up_sell_rate', 0)])

        writer.writerow([])
        writer.writerow(['Product Preferences'])
        writer.writerow(['Category', 'Customer Count', 'Total Revenue', 'Average Spend', 'Repeat Purchase Rate'])
        for item in data['product_preferences']:
            writer.writerow([
                item.get('category', ''),
                item.get('customer_count', 0),
                self._format_currency(item.get('total_revenue', 0)),
                self._format_currency(item.get('average_spend', 0)),
                item.get('repeat_purchase_rate', 0)
            ])

        writer.writerow([])
        writer.writerow(['Channel Preferences'])
        channel_prefs = data['channel_preferences']
        writer.writerow(['in_store', channel_prefs.get(self.CHANNEL_IN_STORE, 0)])
        writer.writerow(['online', channel_prefs.get(self.CHANNEL_ONLINE, 0)])
        writer.writerow(['phone', channel_prefs.get(self.CHANNEL_PHONE, 0)])

        response = HttpResponse(buffer.getvalue(), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = (
            f'attachment; filename="customer-purchase-patterns-{start_date}-to-{end_date}.csv"'
        )
        return response

    def _export_pdf(self, data: Dict[str, Any], start_date: date, end_date: date) -> HttpResponse:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []

        elements.append(Paragraph('Customer Purchase Patterns Report', styles['Title']))
        elements.append(Paragraph(f'Date Range: {start_date} to {end_date}', styles['Normal']))
        currency_meta = getattr(self, 'currency_config', {})
        elements.append(Paragraph(
            f"Currency: {currency_meta.get('code', '')} ({currency_meta.get('symbol', '')})",
            styles['Normal']
        ))
        elements.append(Spacer(1, 12))

        table_data = [
            [
                'Segment', 'Count', 'Total Revenue', 'Average Order Value',
                'Conversion Rate', 'Retention Rate', 'Pct of Total',
                'Last Purchase Days Avg', 'Potential Lost Revenue'
            ]
        ]

        segment_labels = [
            ('new_customers', 'New Customers'),
            ('returning_customers', 'Returning Customers'),
            ('vip_customers', 'VIP Customers'),
            ('at_risk_customers', 'At-Risk Customers')
        ]

        for key, label in segment_labels:
            segment = data['segments'].get(key, {})
            table_data.append([
                label,
                segment.get('count', 0),
                self._format_currency(segment.get('total_revenue', 0), include_commas=True),
                self._format_currency(segment.get('average_order_value', 0), include_commas=True),
                segment.get('conversion_rate', ''),
                segment.get('retention_rate', ''),
                f"{segment.get('percentage_of_total', 0):.1f}%" if key == 'vip_customers' else '',
                segment.get('last_purchase_days_avg', '') if key == 'at_risk_customers' else '',
                self._format_currency(segment.get('potential_lost_revenue', 0), include_commas=True) if key == 'at_risk_customers' else ''
            ])

        segments_table = Table(table_data, repeatRows=1)
        segments_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f2937')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
        ]))
        elements.append(segments_table)
        elements.append(Spacer(1, 16))

        behavior = data['purchase_behavior']
        behavior_lines = [
            f"Average Time Between Purchases: {behavior.get('average_time_between_purchases', 0)} days",
            f"Peak Purchase Day: {behavior.get('peak_purchase_day') or 'N/A'}",
            f"Peak Purchase Hour: {behavior.get('peak_purchase_hour') if behavior.get('peak_purchase_hour') is not None else 'N/A'}",
            f"Average Items Per Order: {behavior.get('average_items_per_order', 0)}",
            f"Cross Sell Rate: {behavior.get('cross_sell_rate', 0)}%",
            f"Up Sell Rate: {behavior.get('up_sell_rate', 0)}%",
        ]
        elements.append(Paragraph('Purchase Behaviour', styles['Heading2']))
        for line in behavior_lines:
            elements.append(Paragraph(line, styles['Normal']))
        elements.append(Spacer(1, 12))

        product_table_data = [['Category', 'Customer Count', 'Total Revenue', 'Average Spend', 'Repeat Purchase Rate']]
        for item in data['product_preferences']:
            product_table_data.append([
                item.get('category', ''),
                item.get('customer_count', 0),
                self._format_currency(item.get('total_revenue', 0), include_commas=True),
                self._format_currency(item.get('average_spend', 0), include_commas=True),
                f"{item.get('repeat_purchase_rate', 0):.1f}%"
            ])

        if len(product_table_data) > 1:
            product_table = Table(product_table_data, repeatRows=1)
            product_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
            ]))
            elements.append(Paragraph('Product Preferences', styles['Heading2']))
            elements.append(product_table)
            elements.append(Spacer(1, 12))

        channel_table = Table([
            ['Channel', 'Percentage'],
            ['In Store', f"{data['channel_preferences'].get(self.CHANNEL_IN_STORE, 0):.1f}%"],
            ['Online', f"{data['channel_preferences'].get(self.CHANNEL_ONLINE, 0):.1f}%"],
            ['Phone', f"{data['channel_preferences'].get(self.CHANNEL_PHONE, 0):.1f}%"],
        ], repeatRows=1)
        channel_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#059669')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
        ]))
        elements.append(Paragraph('Channel Preferences', styles['Heading2']))
        elements.append(channel_table)

        doc.build(elements)
        pdf_data = buffer.getvalue()
        buffer.close()

        response = HttpResponse(pdf_data, content_type='application/pdf')
        response['Content-Disposition'] = (
            f'attachment; filename="customer-purchase-patterns-{start_date}-to-{end_date}.pdf"'
        )
        return response


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
    default_date_range_days = 365
    max_date_range_days = 730
    
    def get(self, request):
        """Generate customer retention metrics report"""
        # Parse filters
        filters = self.parse_filters(request)
        if (error_response := filters.get('error_response')):
            return error_response

        business_id = filters.get('business_id')
        start_date = filters.get('start_date', timezone.now().date() - timedelta(days=365))
        end_date = filters.get('end_date', timezone.now().date())
        cohort_period = request.GET.get('cohort_period', 'month')
        customer_type = request.GET.get('customer_type')
        
        # Build queryset
        customer_qs = Customer.objects.filter(business_id=business_id)
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
            sales__status__in=[Sale.STATUS_COMPLETED, Sale.STATUS_PARTIAL]
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
            purchase_count=Count(
                'sales',
                filter=Q(
                    sales__status__in=[
                        Sale.STATUS_COMPLETED,
                        Sale.STATUS_PARTIAL
                    ]
                )
            )
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
            sales__status__in=[Sale.STATUS_COMPLETED, Sale.STATUS_PARTIAL]
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
                if c.sales.filter(
                    created_at__date__gte=ninety_days_ago,
                    status__in=[Sale.STATUS_COMPLETED, Sale.STATUS_PARTIAL]
                ).exists()
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
                sales__status__in=[Sale.STATUS_COMPLETED, Sale.STATUS_PARTIAL]
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
            purchase_count=Count(
                'sales',
                filter=Q(
                    sales__status__in=[
                        Sale.STATUS_COMPLETED,
                        Sale.STATUS_PARTIAL
                    ]
                )
            )
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
