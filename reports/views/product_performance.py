"""
Product Performance Report View
Provides analytics on individual product sales performance with retail/wholesale breakdown
"""
import csv
import io
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List

from django.db.models import Sum, Count, Q, F, Avg
from django.http import HttpResponse
from django.utils.dateparse import parse_date
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from sales.models import Sale, SaleItem
from products.models import Product
from businesses.models import Business


class ProductPerformanceView(APIView):
    """
    Product Performance Report
    
    Query Parameters:
    - business_id (required): Business ID
    - start_date (optional): Start date (YYYY-MM-DD)
    - end_date (optional): End date (YYYY-MM-DD)
    - period (optional): Predefined period (today, yesterday, this_week, last_week, this_month, last_month, this_year)
    - category (optional): Filter by product category
    - product_id (optional): Filter by specific product
    - sale_type (optional): Filter by sale type (RETAIL, WHOLESALE)
    - export_format (optional): Export format (csv, pdf, excel)
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get product performance data or export"""
        # Get business
        business_id = request.query_params.get('business_id')
        if not business_id:
            return Response(
                {'error': 'business_id is required'},
                status=http_status.HTTP_400_BAD_REQUEST
            )
        
        try:
            business = Business.objects.get(id=business_id)
        except Business.DoesNotExist:
            return Response(
                {'error': 'Business not found'},
                status=http_status.HTTP_404_NOT_FOUND
            )
        
        # Check if export is requested
        export_format = request.query_params.get('export_format')
        if export_format:
            return self._handle_export(request, business, export_format)
        
        # Get date range
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        
        if start_date_str and end_date_str:
            start_date = parse_date(start_date_str)
            end_date = parse_date(end_date_str)
        else:
            # Default to all time (last 5 years) to ensure data is always visible
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=1825)  # ~5 years
        
        # Convert dates to timezone-aware datetime objects
        # Start of day for start_date
        start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
        # End of day for end_date
        end_datetime = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
        
        # Build queryset
        sale_items = SaleItem.objects.filter(
            sale__business=business,
            sale__completed_at__gte=start_datetime,
            sale__completed_at__lte=end_datetime,
            sale__status='COMPLETED'
        ).select_related('product', 'sale')
        
        # Apply filters
        category = request.query_params.get('category')
        if category:
            sale_items = sale_items.filter(product__category=category)
        
        product_id = request.query_params.get('product_id')
        if product_id:
            sale_items = sale_items.filter(product_id=product_id)
        
        sale_type = request.query_params.get('sale_type')
        if sale_type:
            sale_items = sale_items.filter(sale__type=sale_type)
        
        # Build response data
        summary = self._build_summary(sale_items, start_date, end_date)
        products = self._build_product_breakdown(sale_items)
        categories = self._build_category_breakdown(sale_items)
        
        return Response({
            'summary': summary,
            'products': products,
            'categories': categories,
            'period': {
                'start': str(start_date),
                'end': str(end_date),
                'type': 'custom'
            }
        })
    
    def _build_summary(self, sale_items, start_date, end_date) -> Dict[str, Any]:
        """Build summary metrics with retail/wholesale breakdown"""
        
        # Total metrics
        total_revenue = float(sale_items.aggregate(
            total=Sum(F('quantity') * F('unit_price'))
        )['total'] or 0)
        
        total_quantity = sale_items.aggregate(
            total=Sum('quantity')
        )['total'] or 0
        
        total_products = sale_items.values('product').distinct().count()
        
        total_transactions = sale_items.values('sale').distinct().count()
        
        avg_items_per_transaction = float(sale_items.values('sale').annotate(
            items=Sum('quantity')
        ).aggregate(avg=Avg('items'))['avg'] or 0)
        
        # Retail metrics
        retail_items = sale_items.filter(sale__type='RETAIL')
        retail_metrics = {
            'revenue': float(retail_items.aggregate(
                total=Sum(F('quantity') * F('unit_price'))
            )['total'] or 0),
            'quantity': retail_items.aggregate(total=Sum('quantity'))['total'] or 0,
            'transactions': retail_items.values('sale').distinct().count(),
            'products': retail_items.values('product').distinct().count(),
        }
        
        # Wholesale metrics
        wholesale_items = sale_items.filter(sale__type='WHOLESALE')
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
    
    def _build_product_breakdown(self, sale_items) -> List[Dict[str, Any]]:
        """Build per-product breakdown with retail/wholesale split"""
        
        # Group by product
        products = sale_items.values(
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
            retail = sale_items.filter(
                product__id=product_id,
                sale__type='RETAIL'
            ).aggregate(
                revenue=Sum(F('quantity') * F('unit_price')),
                quantity=Sum('quantity'),
                transactions=Count('sale', distinct=True)
            )
            
            # Wholesale metrics
            wholesale = sale_items.filter(
                product__id=product_id,
                sale__type='WHOLESALE'
            ).aggregate(
                revenue=Sum(F('quantity') * F('unit_price')),
                quantity=Sum('quantity'),
                transactions=Count('sale', distinct=True)
            )
            
            result.append({
                'product_id': product_id,
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
    
    def _build_category_breakdown(self, sale_items) -> List[Dict[str, Any]]:
        """Build per-category breakdown"""
        
        categories = sale_items.values(
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
    
    def _handle_export(self, request, business, export_format):
        """Handle export requests"""
        
        if export_format not in ['csv', 'pdf', 'excel']:
            return Response(
                {'error': 'Invalid export format. Use csv, pdf, or excel.'},
                status=http_status.HTTP_400_BAD_REQUEST
            )
        
        # Get date range
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        
        if start_date_str and end_date_str:
            start_date = parse_date(start_date_str)
            end_date = parse_date(end_date_str)
        else:
            # Default to all time (last 5 years) to ensure data is always visible
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=1825)  # ~5 years
        
        # Convert dates to timezone-aware datetime objects
        # Start of day for start_date
        start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
        # End of day for end_date
        end_datetime = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
        
        # Build queryset
        sale_items = SaleItem.objects.filter(
            sale__business=business,
            sale__completed_at__gte=start_datetime,
            sale__completed_at__lte=end_datetime,
            sale__status='COMPLETED'
        ).select_related('product', 'sale')
        
        # Apply filters
        category = request.query_params.get('category')
        if category:
            sale_items = sale_items.filter(product__category=category)
        
        product_id = request.query_params.get('product_id')
        if product_id:
            sale_items = sale_items.filter(product_id=product_id)
        
        sale_type = request.query_params.get('sale_type')
        if sale_type:
            sale_items = sale_items.filter(sale__type=sale_type)
        
        # Build data
        summary = self._build_summary(sale_items, start_date, end_date)
        products = self._build_product_breakdown(sale_items)
        categories = self._build_category_breakdown(sale_items)
        
        # Export based on format
        if export_format == 'csv':
            return self._export_csv(summary, products, categories, start_date, end_date)
        elif export_format == 'excel':
            return Response(
                {'error': 'Excel format not yet implemented. Please use CSV.'},
                status=http_status.HTTP_501_NOT_IMPLEMENTED
            )
        elif export_format == 'pdf':
            return self._export_pdf(summary, products, categories, start_date, end_date)
    
    def _export_csv(self, summary, products, categories, start_date, end_date):
        """Export product performance as CSV"""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(['Product Performance Report'])
        writer.writerow([f'Period: {start_date} to {end_date}'])
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
    
    def _export_pdf(self, summary, products, categories, start_date, end_date):
        """Export product performance as PDF"""
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
        
        # Period and date
        period_text = f"Period: {start_date} to {end_date}<br/>Generated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}"
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
