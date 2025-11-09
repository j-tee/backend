"""
Sales Analytical Reports

Endpoints for sales analysis and insights.
"""

from decimal import Decimal
from datetime import date, datetime, timedelta
from typing import Dict, Any, List
import csv
import io
from django.http import HttpResponse
from django.db.models import Sum, Count, Avg, Q, F
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from django.db.models.functions import ExtractHour, TruncDate
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status as http_status

from sales.models import Sale, SaleItem, Payment
from reports.services.report_base import BaseReportView
from reports.utils.response import ReportResponse, ReportError
from reports.utils.aggregation import AggregationHelper, PercentageCalculator
from reports.utils.profit_calculator import ProfitCalculator


"""
Sales Analytical Reports

Endpoints for sales analysis and insights.
"""

from decimal import Decimal
from datetime import date, timedelta
from typing import Dict, Any, List
from django.db.models import Sum, Count, Avg, Q, F
from django.db.models.functions import ExtractHour, TruncDate
from rest_framework.permissions import IsAuthenticated

from sales.models import Sale, SaleItem, Payment
from reports.services.report_base import BaseReportView
from reports.utils.response import ReportResponse, ReportError
from reports.utils.aggregation import AggregationHelper, PercentageCalculator
from reports.utils.profit_calculator import ProfitCalculator


class SalesSummaryReportView(BaseReportView):
    """
    Sales Summary Report (Updated to match frontend contract)
    
    GET /reports/api/sales/summary/
    
    Query Parameters:
    - start_date: YYYY-MM-DD (default: 30 days ago)
    - end_date: YYYY-MM-DD (default: today)
    - storefront_id: UUID (optional)
    - sale_type: RETAIL or WHOLESALE (optional)
    - period_type: daily, weekly, monthly (default: daily)
    - compare_previous: boolean (default: true)
    - export_format: csv, excel, pdf (optional) - for export instead of JSON
    
    Returns (matching frontend SalesSummaryResponse):
    {
      "success": true,
      "data": {
        "summary": {...},
        "results": { // Modified to match frontend expectation
          "summary": {...},
          "breakdown": [...],
          "top_selling_hours": [...],
          "comparison": {...}
        },
        "metadata": {...}
      }
    }
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):

        # Check for export format request
        export_format = request.query_params.get('export_format', '').lower()

        if export_format in ['csv', 'excel', 'pdf']:
            return self._handle_export(request, export_format)
        
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
        storefront_filters, error_response = self.get_storefront_filters(
            request,
            business_id=business_id
        )
        if error_response:
            return error_response
        storefront_ids = storefront_filters['ids']
        if storefront_ids:
            queryset = queryset.filter(storefront_id__in=storefront_ids)
        
        sale_type = request.query_params.get('sale_type')
        if sale_type and sale_type in ['RETAIL', 'WHOLESALE']:
            queryset = queryset.filter(type=sale_type)
        
        # Only completed sales
        queryset = queryset.filter(status='COMPLETED')
        
        # Get period type
        period_type = request.query_params.get('period_type', 'daily')
        
        # Build comparison data if requested
        compare_previous = request.query_params.get('compare_previous', 'true').lower() == 'true'
        comparison_data = None
        growth_rate = 0.0
        
        if compare_previous:
            # Calculate previous period dates
            days_diff = (end_date - start_date).days + 1
            prev_end_date = start_date - timedelta(days=1)
            prev_start_date = prev_end_date - timedelta(days=days_diff - 1)
            
            # Get previous period queryset
            prev_queryset = Sale.objects.filter(
                business_id=business_id,
                status='COMPLETED',
                created_at__date__gte=prev_start_date,
                created_at__date__lte=prev_end_date
            )
            
            # Apply same filters
            if storefront_ids:
                prev_queryset = prev_queryset.filter(storefront_id__in=storefront_ids)
            if sale_type:
                prev_queryset = prev_queryset.filter(type=sale_type)
            
            comparison_data, growth_rate = self._build_comparison(
                queryset, prev_queryset, prev_start_date, prev_end_date
            )
        
        # Build summary (with growth rate from comparison)
        summary = self._build_summary(queryset, start_date, end_date, period_type, growth_rate)
        
        # Build breakdown (daily breakdown with frontend field names)
        breakdown = self._build_period_breakdown(queryset, period_type)
        
        # Build top selling hours
        top_selling_hours = self._build_hourly_analysis(queryset)
        
        # Build the nested results structure that frontend expects
        results_data = {
            'summary': summary,
            'breakdown': breakdown,
            'top_selling_hours': top_selling_hours,
        }
        
        if comparison_data:
            results_data['comparison'] = comparison_data
        
        # Build metadata
        filters_metadata = {
            'storefront_id': storefront_filters['primary'],
            'storefront_ids': storefront_ids,
            'storefront_names': storefront_filters['names'],
            'sale_type': sale_type,
            'period_type': period_type,
            'compare_previous': compare_previous,
        }

        metadata = self.build_metadata(
            start_date=start_date,
            end_date=end_date,
            filters=filters_metadata
        )
        
        # Return with standard response wrapper
        # Frontend expects: response.data.data.summary, response.data.data.breakdown, etc.
        # Custom response structure for sales summary (matches frontend contract)
        response_data = {
            "success": True,
            "data": {
                "summary": summary,
                "breakdown": breakdown,
                "top_selling_hours": top_selling_hours,
                "filters": filters_metadata,
                "metadata": {
                    "generated_at": datetime.utcnow().isoformat() + "Z",
                    **metadata,
                },
            },
            "error": None
        }
        
        # Add comparison if available
        if comparison_data:
            response_data["data"]["comparison"] = comparison_data
        
        return Response(response_data, status=http_status.HTTP_200_OK)
    
    def _build_summary(self, queryset, start_date, end_date, period_type, growth_rate) -> Dict[str, Any]:
        """Build summary metrics matching frontend SalesSummary interface"""
        
        # Total transactions (renamed from total_sales)
        total_transactions = queryset.count()
        
        # Total sales revenue
        total_sales = AggregationHelper.sum_field(queryset, 'total_amount')
        
        # Total discounts given
        total_discounts_given = AggregationHelper.sum_field(queryset, 'discount_amount')
        
        # Net sales (sales - discounts)
        net_sales = total_sales - total_discounts_given
        
        # Average transaction value (renamed from average_order_value)
        average_transaction_value = AggregationHelper.avg_field(queryset, 'total_amount')
        
        # Total items sold
        total_items_sold = SaleItem.objects.filter(
            sale__in=queryset
        ).aggregate(
            total=Sum('quantity')
        )['total'] or 0
        
        # Total unique customers
        total_customers = queryset.filter(
            customer__isnull=False
        ).values('customer').distinct().count()
        
        # Retail vs Wholesale breakdown
        retail_sales = queryset.filter(type='RETAIL')
        wholesale_sales = queryset.filter(type='WHOLESALE')
        
        retail_metrics = {
            'transactions': retail_sales.count(),
            'revenue': float(AggregationHelper.sum_field(retail_sales, 'total_amount')),
            'average_value': float(AggregationHelper.avg_field(retail_sales, 'total_amount')),
            'items_sold': SaleItem.objects.filter(sale__in=retail_sales).aggregate(total=Sum('quantity'))['total'] or 0,
        }
        
        wholesale_metrics = {
            'transactions': wholesale_sales.count(),
            'revenue': float(AggregationHelper.sum_field(wholesale_sales, 'total_amount')),
            'average_value': float(AggregationHelper.avg_field(wholesale_sales, 'total_amount')),
            'items_sold': SaleItem.objects.filter(sale__in=wholesale_sales).aggregate(total=Sum('quantity'))['total'] or 0,
        }
        
        return {
            'total_sales': float(total_sales),
            'total_transactions': total_transactions,
            'average_transaction_value': float(average_transaction_value),
            'total_items_sold': total_items_sold,
            'total_customers': total_customers,
            'total_discounts_given': float(total_discounts_given),
            'net_sales': float(net_sales),
            'growth_rate': float(growth_rate),
            'retail': retail_metrics,
            'wholesale': wholesale_metrics,
            'period': {
                'start': str(start_date),
                'end': str(end_date),
                'type': period_type
            }
        }
    
    def _build_period_breakdown(self, queryset, period_type) -> List[Dict[str, Any]]:
        """Build period breakdown matching frontend SalesBreakdown interface"""
        
        # Group by date
        daily_data = queryset.annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            revenue=Sum('total_amount'),
            transaction_count=Count('id')
        ).order_by('date')
        
        breakdown = []
        for item in daily_data:
            day_date = item['date']
            day_sales = queryset.filter(created_at__date=day_date)
            
            # Count items sold for this day
            items_sold = SaleItem.objects.filter(
                sale__in=day_sales
            ).aggregate(total=Sum('quantity'))['total'] or 0
            
            # Count unique customers for this day
            customers = day_sales.filter(
                customer__isnull=False
            ).values('customer').distinct().count()
            
            breakdown.append({
                'period': str(day_date),
                'sales': float(item['revenue']),
                'transactions': item['transaction_count'],
                'avg_value': float(item['revenue'] / item['transaction_count']) if item['transaction_count'] > 0 else 0.0,
                'items_sold': items_sold,
                'customers': customers
            })
        
        return breakdown
    
    def _build_hourly_analysis(self, queryset) -> List[Dict[str, Any]]:
        """Build hourly sales analysis matching frontend TopSellingHour interface"""
        
        # Group sales by hour of day
        hourly_data = queryset.annotate(
            hour=ExtractHour('created_at')
        ).values('hour').annotate(
            revenue=Sum('total_amount'),
            transaction_count=Count('id')
        ).order_by('-revenue')  # Sort by revenue descending
        
        # Convert to list and take top 10
        top_hours = []
        for item in hourly_data[:10]:
            top_hours.append({
                'hour': item['hour'],
                'sales': float(item['revenue']),
                'transactions': item['transaction_count']
            })
        
        return top_hours
    
    def _build_comparison(self, current_queryset, previous_queryset, prev_start, prev_end):
        """Build previous period comparison matching frontend PeriodComparison interface"""
        
        # Current period metrics
        current_sales = AggregationHelper.sum_field(current_queryset, 'total_amount')
        current_transactions = current_queryset.count()
        
        # Previous period metrics
        previous_sales = AggregationHelper.sum_field(previous_queryset, 'total_amount')
        previous_transactions = previous_queryset.count()
        
        # Calculate growth rate
        if previous_sales > 0:
            growth = ((current_sales - previous_sales) / previous_sales) * 100
        else:
            growth = 100.0 if current_sales > 0 else 0.0
        
        comparison = {
            'previous_period': {
                'start': str(prev_start),
                'end': str(prev_end),
                'total_sales': float(previous_sales),
                'total_transactions': previous_transactions,
                'growth': float(growth)
            }
        }
        
        return comparison, growth
    
    # Keep old methods for backward compatibility
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
        """Build daily sales breakdown (deprecated - kept for compatibility)"""
        
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
    
    def _handle_export(self, request, export_format):
        """Handle export requests in CSV, Excel, or PDF format"""
        # Get business ID
        business_id, error = self.get_business_or_error(request)
        if error:
            return Response(
                {'error': str(error)},
                status=http_status.HTTP_400_BAD_REQUEST
            )
        
        # Get date range
        start_date, end_date, error = self.get_date_range(request)
        if error:
            return Response(
                {'error': str(error)},
                status=http_status.HTTP_400_BAD_REQUEST
            )
        
        # Get base queryset
        queryset = Sale.objects.filter(business_id=business_id)
        
        # Apply date filter
        queryset = queryset.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
        
        # Apply optional filters
        storefront_filters, error_response = self.get_storefront_filters(
            request,
            business_id=business_id
        )
        if error_response:
            return error_response
        storefront_ids = storefront_filters['ids']
        if storefront_ids:
            queryset = queryset.filter(storefront_id__in=storefront_ids)
        
        sale_type = request.query_params.get('sale_type')
        if sale_type and sale_type in ['RETAIL', 'WHOLESALE']:
            queryset = queryset.filter(type=sale_type)
        
        # Only completed sales
        queryset = queryset.filter(status='COMPLETED')
        
        # Get period type
        period_type = request.query_params.get('period_type', 'daily')
        
        # Build data
        summary = self._build_summary(queryset, start_date, end_date, period_type, 0.0)
        breakdown = self._build_period_breakdown(queryset, period_type)
        top_hours = self._build_hourly_analysis(queryset)
        
        # Export based on format
        if export_format == 'csv':
            return self._export_csv(summary, breakdown, top_hours, start_date, end_date, storefront_filters)
        elif export_format == 'excel':
            return Response(
                {'error': 'Excel format not yet implemented. Please use CSV.'},
                status=http_status.HTTP_501_NOT_IMPLEMENTED
            )
        elif export_format == 'pdf':
            return self._export_pdf(summary, breakdown, top_hours, start_date, end_date, storefront_filters)
    
    def _export_csv(self, summary, breakdown, top_hours, start_date, end_date, storefront_filters=None):
        """Export sales summary as CSV"""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(['Sales Summary Report'])
        writer.writerow([f'Period: {start_date} to {end_date}'])
        if storefront_filters and storefront_filters.get('ids'):
            labels = storefront_filters.get('names') or storefront_filters.get('ids')
            writer.writerow(['Storefront Scope', ', '.join(labels)])
        else:
            writer.writerow(['Storefront Scope', 'All storefronts'])
        writer.writerow([f'Generated: {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}'])
        writer.writerow([])
        
        # Summary section
        writer.writerow(['SUMMARY METRICS'])
        writer.writerow(['Metric', 'Value'])
        writer.writerow(['Total Sales (Revenue)', f"${summary['total_sales']:,.2f}"])
        writer.writerow(['Total Transactions', summary['total_transactions']])
        writer.writerow(['Average Transaction Value', f"${summary['average_transaction_value']:,.2f}"])
        writer.writerow(['Total Items Sold', summary['total_items_sold']])
        writer.writerow(['Total Customers', summary['total_customers']])
        writer.writerow(['Total Discounts Given', f"${summary['total_discounts_given']:,.2f}"])
        writer.writerow(['Net Sales', f"${summary['net_sales']:,.2f}"])
        writer.writerow(['Growth Rate vs Previous Period', f"{summary['growth_rate']:.1f}%"])
        writer.writerow([])
        
        # Retail vs Wholesale breakdown
        writer.writerow(['SALES BY CHANNEL'])
        writer.writerow(['Channel', 'Transactions', 'Revenue', 'Avg Value', 'Items Sold'])
        writer.writerow([
            'Retail',
            summary['retail']['transactions'],
            f"${summary['retail']['revenue']:,.2f}",
            f"${summary['retail']['average_value']:,.2f}",
            summary['retail']['items_sold']
        ])
        writer.writerow([
            'Wholesale',
            summary['wholesale']['transactions'],
            f"${summary['wholesale']['revenue']:,.2f}",
            f"${summary['wholesale']['average_value']:,.2f}",
            summary['wholesale']['items_sold']
        ])
        writer.writerow([])
        
        # Daily breakdown section
        writer.writerow(['DAILY BREAKDOWN'])
        writer.writerow(['Date', 'Sales', 'Transactions', 'Avg Value', 'Items Sold', 'Customers'])
        
        for item in breakdown:
            writer.writerow([
                item['period'],
                f"${item['sales']:,.2f}",
                item['transactions'],
                f"${item['avg_value']:,.2f}",
                item['items_sold'],
                item['customers']
            ])
        
        writer.writerow([])
        
        # Top selling hours section
        writer.writerow(['TOP SELLING HOURS'])
        writer.writerow(['Hour', 'Sales', 'Transactions'])
        
        for item in top_hours:
            hour_str = f"{item['hour']}:00" if item['hour'] < 12 else f"{item['hour']}:00"
            writer.writerow([
                hour_str,
                f"${item['sales']:,.2f}",
                item['transactions']
            ])
        
        # Generate response
        output.seek(0)
        response = HttpResponse(output.getvalue(), content_type='text/csv; charset=utf-8')
        filename = f'sales-summary-{start_date}-to-{end_date}.csv'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response


    def _export_pdf(self, summary, breakdown, top_hours, start_date, end_date, storefront_filters=None):
        """Export sales summary as PDF"""
        # Create a buffer for the PDF
        buffer = io.BytesIO()
        
        # Create the PDF document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18,
        )
        
        # Container for the 'Flowable' objects
        elements = []
        
        # Define styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1f2937'),
            spaceAfter=30,
            alignment=TA_CENTER,
        )
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#374151'),
            spaceAfter=12,
            spaceBefore=12,
        )
        
        # Title
        title = Paragraph("Sales Summary Report", title_style)
        elements.append(title)
        
        # Period and date
        if storefront_filters and storefront_filters.get('ids'):
            labels = storefront_filters.get('names') or storefront_filters.get('ids')
            storefront_line = f"Storefronts: {', '.join(labels)}"
        else:
            storefront_line = "Storefronts: All storefronts"

        period_text = "<br/>".join([
            f"Period: {start_date} to {end_date}",
            storefront_line,
            f"Generated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ])
        period_para = Paragraph(period_text, styles['Normal'])
        elements.append(period_para)
        elements.append(Spacer(1, 0.3*inch))
        
        # Summary Metrics Section
        summary_heading = Paragraph("Summary Metrics", heading_style)
        elements.append(summary_heading)
        
        summary_data = [
            ['Metric', 'Value'],
            ['Total Sales (Revenue)', f"${summary['total_sales']:,.2f}"],
            ['Total Transactions', f"{summary['total_transactions']:,}"],
            ['Average Transaction Value', f"${summary['average_transaction_value']:,.2f}"],
            ['Total Items Sold', f"{summary['total_items_sold']:,}"],
            ['Total Customers', f"{summary['total_customers']:,}"],
            ['Total Discounts Given', f"${summary['total_discounts_given']:,.2f}"],
            ['Net Sales', f"${summary['net_sales']:,.2f}"],
            ['Growth Rate vs Previous Period', f"{summary['growth_rate']:.1f}%"],
        ]
        
        summary_table = Table(summary_data, colWidths=[3.5*inch, 2.5*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f3f4f6')]),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 0.3*inch))
        
        # Sales by Channel Section
        channel_heading = Paragraph("Sales by Channel", heading_style)
        elements.append(channel_heading)
        
        channel_data = [
            ['Channel', 'Transactions', 'Revenue', 'Avg Value', 'Items Sold'],
            [
                'Retail',
                f"{summary['retail']['transactions']:,}",
                f"${summary['retail']['revenue']:,.2f}",
                f"${summary['retail']['average_value']:,.2f}",
                f"{summary['retail']['items_sold']:,}"
            ],
            [
                'Wholesale',
                f"{summary['wholesale']['transactions']:,}",
                f"${summary['wholesale']['revenue']:,.2f}",
                f"${summary['wholesale']['average_value']:,.2f}",
                f"{summary['wholesale']['items_sold']:,}"
            ],
        ]
        
        channel_table = Table(channel_data, colWidths=[1.2*inch, 1.2*inch, 1.4*inch, 1.2*inch, 1.2*inch])
        channel_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10b981')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#d1fae5'), colors.HexColor('#ecfdf5')]),
        ]))
        elements.append(channel_table)
        elements.append(Spacer(1, 0.3*inch))
        
        # Daily Breakdown Section
        if breakdown:
            breakdown_heading = Paragraph("Daily Breakdown", heading_style)
            elements.append(breakdown_heading)
            
            breakdown_data = [['Date', 'Sales', 'Trans.', 'Avg Value', 'Items', 'Customers']]
            for item in breakdown[:15]:  # Limit to first 15 rows to fit on page
                breakdown_data.append([
                    item['period'],
                    f"${item['sales']:,.2f}",
                    str(item['transactions']),
                    f"${item['avg_value']:,.2f}",
                    str(item['items_sold']),
                    str(item['customers']),
                ])
            
            breakdown_table = Table(breakdown_data, colWidths=[1.2*inch, 1*inch, 0.8*inch, 1*inch, 0.8*inch, 1*inch])
            breakdown_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10b981')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f3f4f6')]),
            ]))
            elements.append(breakdown_table)
            elements.append(Spacer(1, 0.3*inch))
        
        # Top Selling Hours Section
        if top_hours:
            hours_heading = Paragraph("Top Selling Hours", heading_style)
            elements.append(hours_heading)
            
            hours_data = [['Hour', 'Sales', 'Transactions']]
            for item in top_hours[:10]:  # Top 10 hours
                hour_str = f"{item['hour']:02d}:00"
                hours_data.append([
                    hour_str,
                    f"${item['sales']:,.2f}",
                    str(item['transactions']),
                ])
            
            hours_table = Table(hours_data, colWidths=[2*inch, 2*inch, 2*inch])
            hours_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8b5cf6')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f3f4f6')]),
            ]))
            elements.append(hours_table)
        
        # Build PDF
        doc.build(elements)
        
        # Get PDF data
        pdf_data = buffer.getvalue()
        buffer.close()
        
        # Create response
        response = HttpResponse(pdf_data, content_type='application/pdf')
        filename = f'sales-summary-{start_date}-to-{end_date}.pdf'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response




class ProductPerformanceReportView(BaseReportView):
    """
    Product Performance Report with Retail/Wholesale Breakdown
    
    GET /reports/api/sales/products/
    
    Query Parameters:
    - start_date: YYYY-MM-DD (default: 30 days ago)
    - end_date: YYYY-MM-DD (default: today)
    - storefront_id: UUID (optional)
    - category: str (optional - filter by product category)
    - sale_type: RETAIL/WHOLESALE (optional)
    - export_format: csv/pdf/excel (optional - for exports)
    - limit: int (default: 50, max: 500)
    
    Returns:
    - Product performance metrics with retail/wholesale breakdown
    - Top selling products
    - Category breakdown
    - CSV/PDF export capability
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        # Get business ID
        business_id, error = self.get_business_or_error(request)
        if error:
            return ReportResponse.error(error)
        
        # Check for export request
        export_format = request.query_params.get('export_format')
        if export_format:
            return self._handle_export(request, business_id, export_format)
        
        # Get date range
        start_date, end_date, error = self.get_date_range(request)
        if error:
            return ReportResponse.error(error)
        
        # Build base queryset
        # Use completed_at if available, otherwise fall back to created_at for older records
        queryset = SaleItem.objects.filter(
            sale__business_id=business_id,
            sale__status='COMPLETED'
        ).filter(
            Q(sale__completed_at__date__gte=start_date, sale__completed_at__date__lte=end_date) |
            Q(sale__completed_at__isnull=True, sale__created_at__date__gte=start_date, sale__created_at__date__lte=end_date)
        ).select_related('product', 'sale')
        
        # Apply filters
        category = request.query_params.get('category')
        if category:
            queryset = queryset.filter(product__category=category)
        
        sale_type = request.query_params.get('sale_type')
        if sale_type:
            queryset = queryset.filter(sale__type=sale_type)

        storefront_filters, error_response = self.get_storefront_filters(
            request,
            business_id=business_id
        )
        if error_response:
            return error_response
        storefront_ids = storefront_filters['ids']
        if storefront_ids:
            queryset = queryset.filter(sale__storefront_id__in=storefront_ids)
        
        # Build response data
        summary = self._build_summary(queryset, start_date, end_date)
        products = self._build_product_breakdown(queryset)
        categories = self._build_category_breakdown(queryset)

        filters_payload = {
            'storefront_id': storefront_filters['primary'],
            'storefront_ids': storefront_ids,
            'storefront_names': storefront_filters['names'],
            'category': category,
            'sale_type': sale_type,
        }

        metadata = self.build_metadata(
            start_date=start_date,
            end_date=end_date,
            filters=filters_payload
        )

        response_payload = {
            'summary': summary,
            'products': products,
            'categories': categories,
            'period': {
                'start': str(start_date),
                'end': str(end_date),
                'type': 'custom'
            },
            'filters': filters_payload,
            'metadata': {
                'generated_at': timezone.now().isoformat() + 'Z',
                **metadata,
            }
        }

        return Response(response_payload, status=http_status.HTTP_200_OK)
    
    def _build_summary(self, queryset, start_date, end_date) -> Dict[str, Any]:
        """Build summary metrics with retail/wholesale breakdown"""
        
        # Total metrics
        total_revenue = float(queryset.aggregate(
            total=Sum(F('quantity') * F('unit_price'))
        )['total'] or 0)
        
        total_quantity = queryset.aggregate(
            total=Sum('quantity')
        )['total'] or 0
        
        total_products = queryset.values('product').distinct().count()
        
        total_transactions = queryset.values('sale').distinct().count()
        
        avg_items_per_transaction = float(queryset.values('sale').annotate(
            items=Sum('quantity')
        ).aggregate(avg=Avg('items'))['avg'] or 0)
        
        # Retail metrics
        retail_items = queryset.filter(sale__type='RETAIL')
        retail_metrics = {
            'revenue': float(retail_items.aggregate(
                total=Sum(F('quantity') * F('unit_price'))
            )['total'] or 0),
            'quantity': retail_items.aggregate(total=Sum('quantity'))['total'] or 0,
            'transactions': retail_items.values('sale').distinct().count(),
            'products': retail_items.values('product').distinct().count(),
        }
        
        # Wholesale metrics
        wholesale_items = queryset.filter(sale__type='WHOLESALE')
        wholesale_metrics = {
            'revenue': float(wholesale_items.aggregate(
                total=Sum(F('quantity') * F('unit_price'))
            )['total'] or 0),
            'quantity': wholesale_items.aggregate(total=Sum('quantity'))['total'] or 0,
            'transactions': wholesale_items.values('sale').distinct().count(),
            'products': wholesale_items.values('product').distinct().count(),
        }
        
        return {
            'total_revenue': total_revenue,
            'total_quantity': total_quantity,
            'total_products': total_products,
            'total_transactions': total_transactions,
            'avg_items_per_transaction': avg_items_per_transaction,
            'retail': retail_metrics,
            'wholesale': wholesale_metrics,
        }
    
    def _build_product_breakdown(self, queryset) -> List[Dict[str, Any]]:
        """Build per-product breakdown with retail/wholesale split"""
        
        # Group by product
        products = queryset.values(
            'product__id',
            'product__name',
            'product__sku',
            'product__category'
        ).annotate(
            total_revenue=Sum(F('quantity') * F('unit_price')),
            total_quantity=Sum('quantity'),
            total_transactions=Count('sale', distinct=True),
            avg_price=Avg('unit_price')
        ).order_by('-total_revenue')
        
        # Add retail/wholesale breakdown for each product
        result = []
        for product in products[:50]:  # Limit to top 50 products
            product_id = product['product__id']
            
            # Retail metrics
            retail = queryset.filter(
                product__id=product_id,
                sale__type='RETAIL'
            ).aggregate(
                revenue=Sum(F('quantity') * F('unit_price')),
                quantity=Sum('quantity'),
                transactions=Count('sale', distinct=True)
            )
            
            # Wholesale metrics
            wholesale = queryset.filter(
                product__id=product_id,
                sale__type='WHOLESALE'
            ).aggregate(
                revenue=Sum(F('quantity') * F('unit_price')),
                quantity=Sum('quantity'),
                transactions=Count('sale', distinct=True)
            )
            
            result.append({
                'product_id': str(product_id),
                'name': product['product__name'],
                'sku': product['product__sku'],
                'category': product['product__category'] or 'Uncategorized',
                'total_revenue': float(product['total_revenue'] or 0),
                'total_quantity': product['total_quantity'],
                'total_transactions': product['total_transactions'],
                'avg_price': float(product['avg_price'] or 0),
                'retail': {
                    'revenue': float(retail['revenue'] or 0),
                    'quantity': retail['quantity'] or 0,
                    'transactions': retail['transactions'] or 0,
                },
                'wholesale': {
                    'revenue': float(wholesale['revenue'] or 0),
                    'quantity': wholesale['quantity'] or 0,
                    'transactions': wholesale['transactions'] or 0,
                }
            })
        
        return result
    
    def _build_category_breakdown(self, queryset) -> List[Dict[str, Any]]:
        """Build per-category breakdown"""
        
        categories = queryset.values(
            'product__category'
        ).annotate(
            total_revenue=Sum(F('quantity') * F('unit_price')),
            total_quantity=Sum('quantity'),
            total_products=Count('product', distinct=True),
            total_transactions=Count('sale', distinct=True)
        ).order_by('-total_revenue')
        
        return [{
            'category': cat['product__category'] or 'Uncategorized',
            'revenue': float(cat['total_revenue'] or 0),
            'quantity': cat['total_quantity'],
            'products': cat['total_products'],
            'transactions': cat['total_transactions']
        } for cat in categories]
    
    def _handle_export(self, request, business_id, export_format):
        """Handle export requests"""
        
        if export_format not in ['csv', 'pdf', 'excel']:
            return Response(
                {'error': 'Invalid export format. Use csv, pdf, or excel.'},
                status=http_status.HTTP_400_BAD_REQUEST
            )
        
        # Get date range
        start_date, end_date, error = self.get_date_range(request)
        if error:
            return ReportResponse.error(error)
        
        # Build queryset
        # Use completed_at if available, otherwise fall back to created_at for older records
        queryset = SaleItem.objects.filter(
            sale__business_id=business_id,
            sale__status='COMPLETED'
        ).filter(
            Q(sale__completed_at__date__gte=start_date, sale__completed_at__date__lte=end_date) |
            Q(sale__completed_at__isnull=True, sale__created_at__date__gte=start_date, sale__created_at__date__lte=end_date)
        ).select_related('product', 'sale')
        
        # Apply filters
        category = request.query_params.get('category')
        if category:
            queryset = queryset.filter(product__category=category)
        
        sale_type = request.query_params.get('sale_type')
        if sale_type:
            queryset = queryset.filter(sale__type=sale_type)

        storefront_filters, error_response = self.get_storefront_filters(
            request,
            business_id=business_id
        )
        if error_response:
            return error_response
        storefront_ids = storefront_filters['ids']
        if storefront_ids:
            queryset = queryset.filter(sale__storefront_id__in=storefront_ids)
        
        # Build data
        summary = self._build_summary(queryset, start_date, end_date)
        products = self._build_product_breakdown(queryset)
        categories = self._build_category_breakdown(queryset)
        
        # Export based on format
        if export_format == 'csv':
            return self._export_csv(summary, products, categories, start_date, end_date, storefront_filters)
        elif export_format == 'excel':
            return Response(
                {'error': 'Excel format not yet implemented. Please use CSV.'},
                status=http_status.HTTP_501_NOT_IMPLEMENTED
            )
        elif export_format == 'pdf':
            return self._export_pdf(summary, products, categories, start_date, end_date, storefront_filters)
    
    def _export_csv(self, summary, products, categories, start_date, end_date, storefront_filters=None):
        """Export product performance as CSV"""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(['Product Performance Report'])
        writer.writerow([f'Period: {start_date} to {end_date}'])
        if storefront_filters and storefront_filters.get('ids'):
            labels = storefront_filters.get('names') or storefront_filters.get('ids')
            writer.writerow(['Storefront Scope', ', '.join(labels)])
        else:
            writer.writerow(['Storefront Scope', 'All storefronts'])
        writer.writerow([f'Generated: {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}'])
        writer.writerow([])
        
        # Summary section
        writer.writerow(['SUMMARY METRICS'])
        writer.writerow(['Metric', 'Value'])
        writer.writerow(['Total Revenue', f"${summary['total_revenue']:,.2f}"])
        writer.writerow(['Total Quantity Sold', f"{summary['total_quantity']:,}"])
        writer.writerow(['Total Products Sold', f"{summary['total_products']:,}"])
        writer.writerow(['Total Transactions', f"{summary['total_transactions']:,}"])
        writer.writerow(['Avg Items per Transaction', f"{summary['avg_items_per_transaction']:.1f}"])
        writer.writerow([])
        
        # Sales by Channel
        writer.writerow(['SALES BY CHANNEL'])
        writer.writerow(['Channel', 'Revenue', 'Quantity', 'Transactions', 'Products'])
        writer.writerow([
            'Retail',
            f"${summary['retail']['revenue']:,.2f}",
            f"{summary['retail']['quantity']:,}",
            f"{summary['retail']['transactions']:,}",
            f"{summary['retail']['products']:,}"
        ])
        writer.writerow([
            'Wholesale',
            f"${summary['wholesale']['revenue']:,.2f}",
            f"{summary['wholesale']['quantity']:,}",
            f"{summary['wholesale']['transactions']:,}",
            f"{summary['wholesale']['products']:,}"
        ])
        writer.writerow([])
        
        # Product breakdown
        writer.writerow(['TOP PRODUCTS'])
        writer.writerow([
            'Product', 'SKU', 'Category', 'Total Revenue', 'Quantity', 'Transactions',
            'Retail Revenue', 'Retail Qty', 'Wholesale Revenue', 'Wholesale Qty'
        ])
        
        for product in products:
            writer.writerow([
                product['name'],
                product['sku'],
                product['category'],
                f"${product['total_revenue']:,.2f}",
                product['total_quantity'],
                product['total_transactions'],
                f"${product['retail']['revenue']:,.2f}",
                product['retail']['quantity'],
                f"${product['wholesale']['revenue']:,.2f}",
                product['wholesale']['quantity']
            ])
        
        writer.writerow([])
        
        # Category breakdown
        writer.writerow(['CATEGORY BREAKDOWN'])
        writer.writerow(['Category', 'Revenue', 'Quantity', 'Products', 'Transactions'])
        
        for cat in categories:
            writer.writerow([
                cat['category'],
                f"${cat['revenue']:,.2f}",
                cat['quantity'],
                cat['products'],
                cat['transactions']
            ])
        
        # Generate response
        output.seek(0)
        response = HttpResponse(output.getvalue(), content_type='text/csv; charset=utf-8')
        filename = f'product-performance-{start_date}-to-{end_date}.csv'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
    
    def _export_pdf(self, summary, products, categories, start_date, end_date, storefront_filters=None):
        """Export product performance as PDF"""
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib.enums import TA_CENTER
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        
        # Create a buffer for the PDF
        buffer = io.BytesIO()
        
        # Create the PDF document in landscape for wider tables
        doc = SimpleDocTemplate(
            buffer,
            pagesize=landscape(letter),
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=18,
        )
        
        # Container for the 'Flowable' objects
        elements = []
        
        # Define styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1f2937'),
            spaceAfter=20,
            alignment=TA_CENTER,
        )
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#374151'),
            spaceAfter=12,
            spaceBefore=12,
        )
        
        # Title
        title = Paragraph("Product Performance Report", title_style)
        elements.append(title)
        
        if storefront_filters and storefront_filters.get('ids'):
            labels = storefront_filters.get('names') or storefront_filters.get('ids')
            storefront_line = f"Storefronts: {', '.join(labels)}"
        else:
            storefront_line = "Storefronts: All storefronts"

        # Period and date
        period_text = "<br/>".join([
            f"Period: {start_date} to {end_date}",
            storefront_line,
            f"Generated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ])
        period_para = Paragraph(period_text, styles['Normal'])
        elements.append(period_para)
        elements.append(Spacer(1, 0.2*inch))
        
        # Summary Metrics Section
        summary_heading = Paragraph("Summary Metrics", heading_style)
        elements.append(summary_heading)
        
        summary_data = [
            ['Metric', 'Value'],
            ['Total Revenue', f"${summary['total_revenue']:,.2f}"],
            ['Total Quantity Sold', f"{summary['total_quantity']:,}"],
            ['Total Products Sold', f"{summary['total_products']:,}"],
            ['Total Transactions', f"{summary['total_transactions']:,}"],
            ['Avg Items per Transaction', f"{summary['avg_items_per_transaction']:.1f}"],
        ]
        
        summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f3f4f6')]),
        ]))
        elements.append(summary_table)
        elements.append(Spacer(1, 0.2*inch))
        
        # Sales by Channel Section
        channel_heading = Paragraph("Sales by Channel", heading_style)
        elements.append(channel_heading)
        
        channel_data = [
            ['Channel', 'Revenue', 'Quantity', 'Transactions', 'Products'],
            [
                'Retail',
                f"${summary['retail']['revenue']:,.2f}",
                f"{summary['retail']['quantity']:,}",
                f"{summary['retail']['transactions']:,}",
                f"{summary['retail']['products']:,}"
            ],
            [
                'Wholesale',
                f"${summary['wholesale']['revenue']:,.2f}",
                f"{summary['wholesale']['quantity']:,}",
                f"{summary['wholesale']['transactions']:,}",
                f"{summary['wholesale']['products']:,}"
            ],
        ]
        
        channel_table = Table(channel_data, colWidths=[1.2*inch, 1.4*inch, 1.2*inch, 1.4*inch, 1.2*inch])
        channel_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10b981')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#d1fae5'), colors.HexColor('#ecfdf5')]),
        ]))
        elements.append(channel_table)
        elements.append(Spacer(1, 0.2*inch))
        
        # Top Products Section (limit to top 20 for PDF)
        products_heading = Paragraph("Top 20 Products", heading_style)
        elements.append(products_heading)
        
        products_data = [
            ['Product', 'SKU', 'Revenue', 'Qty', 'Retail $', 'Wholesale $']
        ]
        
        for product in products[:20]:
            products_data.append([
                product['name'][:30],  # Truncate long names
                product['sku'][:15],
                f"${product['total_revenue']:,.0f}",
                f"{product['total_quantity']:,}",
                f"${product['retail']['revenue']:,.0f}",
                f"${product['wholesale']['revenue']:,.0f}"
            ])
        
        products_table = Table(products_data, colWidths=[2.5*inch, 1*inch, 1*inch, 0.8*inch, 1*inch, 1*inch])
        products_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8b5cf6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f3f4f6')]),
        ]))
        elements.append(products_table)
        
        # Build PDF
        doc.build(elements)
        
        # Get PDF data
        pdf_data = buffer.getvalue()
        buffer.close()
        
        # Generate response
        response = HttpResponse(pdf_data, content_type='application/pdf')
        filename = f'product-performance-{start_date}-to-{end_date}.pdf'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response


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

        export_format = request.query_params.get('export_format', '').lower()
        
        # Get base queryset - completed sales with customers
        queryset = Sale.objects.filter(
            business_id=business_id,
            status='COMPLETED',
            customer__isnull=False,  # Only sales with customers
            created_at__date__gte=start_date,
            created_at__date__lte=end_date
        )
        
        # Apply optional filters
        storefront_filters, error_response = self.get_storefront_filters(
            request,
            business_id=business_id
        )
        if error_response:
            return error_response
        storefront_ids = storefront_filters['ids']
        if storefront_ids:
            queryset = queryset.filter(storefront_id__in=storefront_ids)

        filters_payload = {
            'storefront_id': storefront_filters['primary'],
            'storefront_ids': storefront_ids,
            'storefront_names': storefront_filters['names'],
            'sort_by': sort_by,
        }
        
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
        
        # Build summary - OVERALL
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
        
        # Build summary - RETAIL
        retail_queryset = queryset.filter(type='RETAIL')
        retail_customer_data = retail_queryset.values(
            'customer__id'
        ).annotate(
            order_count=Count('id')
        )
        
        retail_customers = retail_customer_data.count()
        retail_revenue = AggregationHelper.sum_field(retail_queryset, 'total_amount')
        retail_orders = retail_queryset.count()
        retail_avg_revenue_per_customer = AggregationHelper.safe_divide(
            retail_revenue,
            Decimal(str(retail_customers))
        ) if retail_customers > 0 else Decimal('0.00')
        
        # Build summary - WHOLESALE
        wholesale_queryset = queryset.filter(type='WHOLESALE')
        wholesale_customer_data = wholesale_queryset.values(
            'customer__id'
        ).annotate(
            order_count=Count('id')
        )
        
        wholesale_customers = wholesale_customer_data.count()
        wholesale_revenue = AggregationHelper.sum_field(wholesale_queryset, 'total_amount')
        wholesale_orders = wholesale_queryset.count()
        wholesale_avg_revenue_per_customer = AggregationHelper.safe_divide(
            wholesale_revenue,
            Decimal(str(wholesale_customers))
        ) if wholesale_customers > 0 else Decimal('0.00')
        
        summary = {
            # Overall metrics
            'total_customers': total_customers,
            'total_revenue': float(total_revenue),
            'total_orders': total_orders,
            'average_revenue_per_customer': float(avg_revenue_per_customer),
            'average_orders_per_customer': round(avg_orders_per_customer, 2),
            'repeat_customer_rate': float(repeat_rate),
            
            # Retail breakdown
            'retail': {
                'customers': retail_customers,
                'revenue': float(retail_revenue),
                'orders': retail_orders,
                'avg_revenue_per_customer': float(retail_avg_revenue_per_customer),
            },
            
            # Wholesale breakdown
            'wholesale': {
                'customers': wholesale_customers,
                'revenue': float(wholesale_revenue),
                'orders': wholesale_orders,
                'avg_revenue_per_customer': float(wholesale_avg_revenue_per_customer),
            },
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
        
        if export_format:
            return self._handle_export(
                export_format,
                summary,
                results,
                start_date,
                end_date,
                storefront_filters
            )

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
            filters=filters_payload
        )
        
        return ReportResponse.paginated(
            summary, paginated_results, metadata, page, page_size, total_count
        )

    def _handle_export(
        self,
        export_format: str,
        summary: Dict[str, Any],
        results: List[Dict[str, Any]],
        start_date: date,
        end_date: date,
        storefront_filters: Dict[str, Any],
    ) -> Response:
        if export_format == 'csv':
            return self._export_csv(summary, results, start_date, end_date, storefront_filters)
        if export_format == 'pdf':
            return Response(
                {
                    'error': 'PDF export not yet implemented. Please use CSV.'
                },
                status=http_status.HTTP_501_NOT_IMPLEMENTED
            )
        return Response(
            {'error': 'Invalid export format. Use csv or pdf.'},
            status=http_status.HTTP_400_BAD_REQUEST
        )

    def _export_csv(
        self,
        summary: Dict[str, Any],
        results: List[Dict[str, Any]],
        start_date: date,
        end_date: date,
        storefront_filters: Dict[str, Any],
    ) -> HttpResponse:
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(['Customer Analytics Report'])
        writer.writerow([f'Period: {start_date} to {end_date}'])
        if storefront_filters and storefront_filters.get('ids'):
            labels = storefront_filters.get('names') or storefront_filters.get('ids')
            writer.writerow(['Storefront Scope', ', '.join(labels)])
        else:
            writer.writerow(['Storefront Scope', 'All storefronts'])
        writer.writerow([f'Generated: {timezone.now().strftime("%Y-%m-%d %H:%M:%S") }'])
        writer.writerow([])

        writer.writerow(['SUMMARY METRICS'])
        writer.writerow(['Metric', 'Value'])
        writer.writerow(['Total Customers', summary['total_customers']])
        writer.writerow(['Total Revenue', f"${summary['total_revenue']:,.2f}"])
        writer.writerow(['Total Orders', summary['total_orders']])
        writer.writerow(['Average Revenue per Customer', f"${summary['average_revenue_per_customer']:,.2f}"])
        writer.writerow(['Average Orders per Customer', summary['average_orders_per_customer']])
        writer.writerow(['Repeat Customer Rate', f"{summary['repeat_customer_rate']:.1f}%"])
        writer.writerow([])

        writer.writerow(['RETAIL BREAKDOWN'])
        writer.writerow(['Customers', summary['retail']['customers']])
        writer.writerow(['Revenue', f"${summary['retail']['revenue']:,.2f}"])
        writer.writerow(['Orders', summary['retail']['orders']])
        writer.writerow(['Avg Revenue per Customer', f"${summary['retail']['avg_revenue_per_customer']:,.2f}"])
        writer.writerow([])

        writer.writerow(['WHOLESALE BREAKDOWN'])
        writer.writerow(['Customers', summary['wholesale']['customers']])
        writer.writerow(['Revenue', f"${summary['wholesale']['revenue']:,.2f}"])
        writer.writerow(['Orders', summary['wholesale']['orders']])
        writer.writerow(['Avg Revenue per Customer', f"${summary['wholesale']['avg_revenue_per_customer']:,.2f}"])
        writer.writerow([])

        writer.writerow(['CUSTOMER DETAILS'])
        writer.writerow([
            'Rank',
            'Customer Name',
            'Email',
            'Total Spent',
            'Orders',
            'Average Order Value',
            'Contribution %',
            'Days Since Last Purchase',
        ])

        for idx, record in enumerate(results, start=1):
            writer.writerow([
                idx,
                record['customer_name'] or '',
                record['customer_email'] or '',
                f"${record['total_spent']:,.2f}",
                record['order_count'],
                f"${record['average_order_value']:,.2f}",
                f"{record['contribution_percentage']:.1f}%",
                record['days_since_last_purchase'] if record['days_since_last_purchase'] is not None else '',
            ])

        output.seek(0)
        response = HttpResponse(output.getvalue(), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = (
            f'attachment; filename="customer-analytics-{start_date}-to-{end_date}.csv"'
        )
        return response


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

        export_format = request.query_params.get('export_format', '').lower()
        
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
        storefront_filters, error_response = self.get_storefront_filters(
            request,
            business_id=business_id
        )
        if error_response:
            return error_response
        storefront_ids = storefront_filters['ids']
        if storefront_ids:
            queryset = queryset.filter(storefront_id__in=storefront_ids)
        
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
            if storefront_ids:
                prev_queryset = prev_queryset.filter(storefront_id__in=storefront_ids)
            
            previous_data = {
                'start_date': prev_start,
                'end_date': prev_end,
                'queryset': prev_queryset
            }
        
        # Build summary
        summary = self._build_summary(queryset, start_date, end_date, previous_data)
        
        # Build results (time-series data)
        trends = self._build_time_series(queryset, grouping, start_date, end_date)
        
        # Build patterns (analytics insights)
        patterns = self._build_patterns(trends, summary)
        
        filters_payload = {
            'storefront_id': storefront_filters['primary'],
            'storefront_ids': storefront_ids,
            'storefront_names': storefront_filters['names'],
            'grouping': grouping,
            'compare_to_previous': compare,
        }

        # Build metadata
        metadata = self.build_metadata(
            start_date=start_date,
            end_date=end_date,
            filters=filters_payload
        )

        if export_format:
            return self._handle_export(
                export_format,
                summary,
                trends,
                patterns,
                start_date,
                end_date,
                grouping,
                storefront_filters,
            )
        
        # Return unified structure with summary, trends, and patterns
        return ReportResponse.success(
            summary=summary,
            results={'trends': trends, 'patterns': patterns},
            metadata=metadata
        )
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
        
        # Build RETAIL metrics
        retail_queryset = queryset.filter(type='RETAIL')
        retail_revenue = AggregationHelper.sum_field(retail_queryset, 'total_amount')
        retail_orders = retail_queryset.count()
        retail_profit = ProfitCalculator.calculate_total_profit(retail_queryset)
        retail_avg_order_value = AggregationHelper.safe_divide(
            retail_revenue,
            Decimal(str(retail_orders))
        ) if retail_orders > 0 else Decimal('0.00')
        retail_profit_margin = AggregationHelper.calculate_percentage(
            retail_profit, retail_revenue
        ) if retail_revenue > 0 else Decimal('0.00')
        
        # Build WHOLESALE metrics
        wholesale_queryset = queryset.filter(type='WHOLESALE')
        wholesale_revenue = AggregationHelper.sum_field(wholesale_queryset, 'total_amount')
        wholesale_orders = wholesale_queryset.count()
        wholesale_profit = ProfitCalculator.calculate_total_profit(wholesale_queryset)
        wholesale_avg_order_value = AggregationHelper.safe_divide(
            wholesale_revenue,
            Decimal(str(wholesale_orders))
        ) if wholesale_orders > 0 else Decimal('0.00')
        wholesale_profit_margin = AggregationHelper.calculate_percentage(
            wholesale_profit, wholesale_revenue
        ) if wholesale_revenue > 0 else Decimal('0.00')
        
        # Find peak day
        daily_sales = queryset.extra(
            select={'date': 'DATE(created_at)'}
        ).values('date').annotate(
            revenue=Sum('total_amount')
        ).order_by('-revenue').first()
        
        peak_day = daily_sales['date'] if daily_sales else None
        peak_revenue = Decimal(str(daily_sales['revenue'])) if daily_sales else Decimal('0.00')
        
        # Calculate overall profit margin
        profit_margin = AggregationHelper.calculate_percentage(
            total_profit, total_revenue
        ) if total_revenue > 0 else Decimal('0.00')
        
        summary = {
            'period_start': str(start_date),
            'period_end': str(end_date),
            'total_revenue': float(total_revenue),
            'total_profit': float(total_profit),
            'profit_margin': float(profit_margin),
            'total_orders': total_orders,
            'average_daily_revenue': float(avg_daily_revenue),
            'average_order_value': float(avg_order_value),
            'peak_day': str(peak_day) if peak_day else None,
            'peak_revenue': float(peak_revenue),
            
            # Retail breakdown
            'retail': {
                'revenue': float(retail_revenue),
                'profit': float(retail_profit),
                'profit_margin': float(retail_profit_margin),
                'orders': retail_orders,
                'avg_order_value': float(retail_avg_order_value),
            },
            
            # Wholesale breakdown
            'wholesale': {
                'revenue': float(wholesale_revenue),
                'profit': float(wholesale_profit),
                'profit_margin': float(wholesale_profit_margin),
                'orders': wholesale_orders,
                'avg_order_value': float(wholesale_avg_order_value),
            },
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
        
        # Group by period - OVERALL
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
        
        # Group by period - RETAIL
        retail_time_series = {}
        retail_data = queryset.filter(type='RETAIL').annotate(period=trunc_func).values('period').annotate(
            revenue=Sum('total_amount'),
            order_count=Count('id')
        )
        for item in retail_data:
            retail_time_series[str(item['period'])] = {
                'revenue': Decimal(str(item['revenue'] or 0)),
                'orders': item['order_count']
            }
        
        # Group by period - WHOLESALE
        wholesale_time_series = {}
        wholesale_data = queryset.filter(type='WHOLESALE').annotate(period=trunc_func).values('period').annotate(
            revenue=Sum('total_amount'),
            order_count=Count('id')
        )
        for item in wholesale_data:
            wholesale_time_series[str(item['period'])] = {
                'revenue': Decimal(str(item['revenue'] or 0)),
                'orders': item['order_count']
            }
        
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
            
            # Get retail/wholesale data for this period
            period_key = str(item['period'])
            retail_data = retail_time_series.get(period_key, {'revenue': Decimal('0'), 'orders': 0})
            wholesale_data = wholesale_time_series.get(period_key, {'revenue': Decimal('0'), 'orders': 0})
            
            # Get payment methods breakdown for this period
            if grouping == 'daily':
                period_sales = queryset.filter(created_at__date=item['period'])
            elif grouping == 'weekly':
                period_sales = queryset.annotate(week=TruncWeek('created_at')).filter(week=item['period'])
            elif grouping == 'monthly':
                period_sales = queryset.annotate(month=TruncMonth('created_at')).filter(month=item['period'])
            else:
                period_sales = queryset.filter(created_at__date=item['period'])
            
            # Get payment totals by method (using Sale.payment_type field)
            payment_breakdown = period_sales.values('payment_type').annotate(
                total=Sum('total_amount')
            )
            payment_methods = {
                'cash': Decimal('0'),
                'card': Decimal('0'),
                'credit': Decimal('0'),
                'gcash': Decimal('0'),
                'other': Decimal('0'),
            }
            for payment in payment_breakdown:
                method = payment['payment_type']
                if method:
                    method_lower = method.lower()
                    # Map payment types to our standard categories
                    if method_lower == 'cash':
                        payment_methods['cash'] = Decimal(str(payment['total'] or 0))
                    elif method_lower == 'card':
                        payment_methods['card'] = Decimal(str(payment['total'] or 0))
                    elif method_lower == 'credit':
                        payment_methods['credit'] = Decimal(str(payment['total'] or 0))
                    elif method_lower in ['mobile', 'gcash']:
                        payment_methods['gcash'] += Decimal(str(payment['total'] or 0))
                    else:
                        payment_methods['other'] += Decimal(str(payment['total'] or 0))
            
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
            
            # Convert period to ISO format string
            period_value = item['period']
            if period_value:
                # Check if it's already a date or needs conversion from datetime
                if hasattr(period_value, 'date') and not isinstance(period_value, date):
                    period_str = period_value.date().isoformat()
                else:
                    period_str = period_value.isoformat()
            else:
                period_str = None
            
            result = {
                'period': period_str,
                'revenue': float(revenue),
                'profit': float(profit),
                'profit_margin': float(profit_margin),
                'order_count': order_count,
                'average_order_value': float(
                    revenue / order_count if order_count > 0 else 0
                ),
                
                # Retail breakdown
                'retail': {
                    'revenue': float(retail_data['revenue']),
                    'orders': retail_data['orders'],
                    'avg_order_value': float(
                        retail_data['revenue'] / retail_data['orders'] if retail_data['orders'] > 0 else 0
                    ),
                },
                
                # Wholesale breakdown
                'wholesale': {
                    'revenue': float(wholesale_data['revenue']),
                    'orders': wholesale_data['orders'],
                    'avg_order_value': float(
                        wholesale_data['revenue'] / wholesale_data['orders'] if wholesale_data['orders'] > 0 else 0
                    ),
                },
                
                # Payment methods breakdown
                'payment_methods': {
                    'cash': float(payment_methods['cash']),
                    'card': float(payment_methods['card']),
                    'credit': float(payment_methods['credit']),
                    'gcash': float(payment_methods['gcash']),
                    'other': float(payment_methods['other']),
                },
            }
            
            if growth_rate is not None:
                result['growth_rate'] = growth_rate
                result['trend'] = trend
            
            results.append(result)
            prev_revenue = revenue
        
        return results
    
    def _build_patterns(
        self, trends: List[Dict[str, Any]], summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build analytics patterns and insights"""
        
        if not trends:
            return {
                'peak_day': None,
                'peak_revenue': 0.0,
                'lowest_day': None,
                'lowest_revenue': 0.0,
                'volatility': 'low',
                'overall_trend': 'stable',
                'growth_rate': 0.0,
            }
        
        # Find peak and lowest periods
        peak_period = max(trends, key=lambda x: x['revenue'])
        lowest_period = min(trends, key=lambda x: x['revenue'])
        
        # Calculate volatility based on revenue standard deviation
        revenues = [t['revenue'] for t in trends]
        avg_revenue = sum(revenues) / len(revenues)
        variance = sum((r - avg_revenue) ** 2 for r in revenues) / len(revenues)
        std_dev = variance ** 0.5
        coefficient_of_variation = (std_dev / avg_revenue * 100) if avg_revenue > 0 else 0
        
        if coefficient_of_variation < 15:
            volatility = 'low'
        elif coefficient_of_variation < 30:
            volatility = 'medium'
        else:
            volatility = 'high'
        
        # Determine overall trend
        first_revenue = trends[0]['revenue']
        last_revenue = trends[-1]['revenue']
        growth_rate = ((last_revenue - first_revenue) / first_revenue * 100) if first_revenue > 0 else 0
        
        if growth_rate > 5:
            overall_trend = 'upward'
        elif growth_rate < -5:
            overall_trend = 'downward'
        else:
            overall_trend = 'stable'
        
        return {
            'peak_day': peak_period['period'],
            'peak_revenue': peak_period['revenue'],
            'lowest_day': lowest_period['period'],
            'lowest_revenue': lowest_period['revenue'],
            'volatility': volatility,
            'overall_trend': overall_trend,
            'growth_rate': round(growth_rate, 2),
        }

    def _handle_export(
        self,
        export_format: str,
        summary: Dict[str, Any],
        trends: List[Dict[str, Any]],
        patterns: Dict[str, Any],
        start_date: date,
        end_date: date,
        grouping: str,
        storefront_filters: Dict[str, Any],
    ) -> Response:
        if export_format == 'csv':
            return self._export_csv(
                summary,
                trends,
                patterns,
                start_date,
                end_date,
                grouping,
                storefront_filters,
            )
        if export_format == 'pdf':
            return Response(
                {'error': 'PDF export not yet implemented. Please use CSV.'},
                status=http_status.HTTP_501_NOT_IMPLEMENTED
            )
        return Response(
            {'error': 'Invalid export format. Use csv or pdf.'},
            status=http_status.HTTP_400_BAD_REQUEST
        )

    def _export_csv(
        self,
        summary: Dict[str, Any],
        trends: List[Dict[str, Any]],
        patterns: Dict[str, Any],
        start_date: date,
        end_date: date,
        grouping: str,
        storefront_filters: Dict[str, Any],
    ) -> HttpResponse:
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(['Revenue Trends Report'])
        writer.writerow([f'Period: {start_date} to {end_date}'])
        if storefront_filters and storefront_filters.get('ids'):
            labels = storefront_filters.get('names') or storefront_filters.get('ids')
            writer.writerow(['Storefront Scope', ', '.join(labels)])
        else:
            writer.writerow(['Storefront Scope', 'All storefronts'])
        writer.writerow(['Grouping', grouping.title()])
        writer.writerow([f'Generated: {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}'])
        writer.writerow([])

        writer.writerow(['SUMMARY METRICS'])
        writer.writerow(['Metric', 'Value'])
        writer.writerow(['Total Revenue', f"${summary['total_revenue']:,.2f}"])
        writer.writerow(['Total Profit', f"${summary['total_profit']:,.2f}"])
        writer.writerow(['Profit Margin %', f"{summary['profit_margin']:.2f}%"])
        writer.writerow(['Total Orders', summary['total_orders']])
        writer.writerow(['Average Daily Revenue', f"${summary['average_daily_revenue']:,.2f}"])
        writer.writerow(['Average Order Value', f"${summary['average_order_value']:,.2f}"])
        writer.writerow(['Peak Day', summary['peak_day'] or 'N/A'])
        writer.writerow(['Peak Revenue', f"${summary['peak_revenue']:,.2f}"])
        writer.writerow([])

        writer.writerow(['RETAIL BREAKDOWN'])
        writer.writerow(['Revenue', f"${summary['retail']['revenue']:,.2f}"])
        writer.writerow(['Profit', f"${summary['retail']['profit']:,.2f}"])
        writer.writerow(['Profit Margin %', f"{summary['retail']['profit_margin']:.2f}%"])
        writer.writerow(['Orders', summary['retail']['orders']])
        writer.writerow(['Avg Order Value', f"${summary['retail']['avg_order_value']:,.2f}"])
        writer.writerow([])

        writer.writerow(['WHOLESALE BREAKDOWN'])
        writer.writerow(['Revenue', f"${summary['wholesale']['revenue']:,.2f}"])
        writer.writerow(['Profit', f"${summary['wholesale']['profit']:,.2f}"])
        writer.writerow(['Profit Margin %', f"{summary['wholesale']['profit_margin']:.2f}%"])
        writer.writerow(['Orders', summary['wholesale']['orders']])
        writer.writerow(['Avg Order Value', f"${summary['wholesale']['avg_order_value']:,.2f}"])
        writer.writerow([])

        if 'comparison' in summary and 'previous_period' in summary:
            writer.writerow(['PREVIOUS PERIOD COMPARISON'])
            writer.writerow(['Metric', 'Value'])
            writer.writerow(['Previous Revenue', f"${summary['previous_period']['revenue']:,.2f}"])
            writer.writerow(['Previous Profit', f"${summary['previous_period']['profit']:,.2f}"])
            writer.writerow(['Previous Orders', summary['previous_period']['orders']])
            writer.writerow(['Revenue Growth %', f"{summary['comparison']['revenue_growth']:.2f}%"])
            writer.writerow(['Order Growth %', f"{summary['comparison']['order_growth']:.2f}%"])
            writer.writerow(['Profit Growth %', f"{summary['comparison']['profit_growth']:.2f}%"])
            writer.writerow([])

        writer.writerow(['TIME SERIES (GROUPING: ' + grouping.title() + ')'])
        writer.writerow([
            'Period',
            'Revenue',
            'Profit',
            'Profit Margin %',
            'Orders',
            'Average Order Value',
            'Retail Revenue',
            'Retail Orders',
            'Wholesale Revenue',
            'Wholesale Orders',
            'Cash',
            'Card',
            'Credit',
            'GCash',
            'Other',
            'Growth Rate %',
            'Trend',
        ])

        for record in trends:
            writer.writerow([
                record['period'],
                f"${record['revenue']:,.2f}",
                f"${record['profit']:,.2f}",
                f"{record['profit_margin']:.2f}%",
                record['order_count'],
                f"${record['average_order_value']:,.2f}",
                f"${record['retail']['revenue']:,.2f}",
                record['retail']['orders'],
                f"${record['wholesale']['revenue']:,.2f}",
                record['wholesale']['orders'],
                f"${record['payment_methods']['cash']:,.2f}",
                f"${record['payment_methods']['card']:,.2f}",
                f"${record['payment_methods']['credit']:,.2f}",
                f"${record['payment_methods']['gcash']:,.2f}",
                f"${record['payment_methods']['other']:,.2f}",
                f"{record.get('growth_rate', 0.0):.2f}%" if record.get('growth_rate') is not None else 'N/A',
                record.get('trend', 'stable'),
            ])

        writer.writerow([])
        writer.writerow(['PATTERNS'])
        writer.writerow(['Metric', 'Value'])
        writer.writerow(['Peak Period', patterns.get('peak_day', 'N/A')])
        writer.writerow(['Peak Revenue', f"${patterns.get('peak_revenue', 0.0):,.2f}"])
        writer.writerow(['Lowest Period', patterns.get('lowest_day', 'N/A')])
        writer.writerow(['Lowest Revenue', f"${patterns.get('lowest_revenue', 0.0):,.2f}"])
        writer.writerow(['Volatility', patterns.get('volatility', 'N/A')])
        writer.writerow(['Overall Trend', patterns.get('overall_trend', 'N/A')])
        writer.writerow(['Growth Rate %', f"{patterns.get('growth_rate', 0.0):.2f}%"])

        output.seek(0)
        response = HttpResponse(output.getvalue(), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = (
            f'attachment; filename="revenue-trends-{start_date}-to-{end_date}.csv"'
        )
        return response


class ReportStorefrontListView(BaseReportView):
    """Return storefronts available to the current user for report filters."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        business_id, error = self.get_business_or_error(request)
        if error:
            return ReportResponse.error(error)

        accessible_storefronts = (
            request.user.get_accessible_storefronts()
            .filter(business_link__business_id=business_id, business_link__is_active=True)
            .order_by('name')
        )

        storefront_payload = [
            {
                'id': str(storefront.id),
                'name': storefront.name,
                'location': storefront.location,
            }
            for storefront in accessible_storefronts
        ]

        return Response(
            {
                'success': True,
                'data': storefront_payload,
                'metadata': {
                    'generated_at': timezone.now().isoformat() + 'Z',
                    'count': len(storefront_payload),
                },
                'error': None,
            },
            status=http_status.HTTP_200_OK
        )

