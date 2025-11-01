"""
Warehouse Analytics API View

Provides comprehensive warehouse performance metrics including:
- Stock turnover ratios
- Dead stock analysis
- Storage utilization
- Movement tracking
- Top performing products
- Slow movers identification
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db.models import Sum, Avg, Count, F, Q, Case, When, Value, DecimalField, IntegerField, Max
from django.db.models.functions import Coalesce
from django.core.cache import cache
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import logging

from inventory.models import Warehouse, Product, StockProduct
from sales.models import Sale, SaleItem
from accounts.models import Business

logger = logging.getLogger(__name__)


class WarehouseAnalyticsAPIView(APIView):
    """
    GET /reports/api/inventory/warehouse-analytics/
    
    Comprehensive warehouse analytics endpoint providing:
    - Performance metrics (turnover, dead stock, utilization)
    - Top performing products
    - Slow moving products
    - Movement statistics
    
    Query Parameters:
    - start_date (required): YYYY-MM-DD
    - end_date (required): YYYY-MM-DD
    - warehouse_id (optional): UUID
    - warehouse_type (optional): "warehouse" or "storefront"
    - export_format (optional): "csv" or "pdf"
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Handle GET request for warehouse analytics"""
        try:
            # Get query parameters
            start_date = request.GET.get('start_date')
            end_date = request.GET.get('end_date')
            warehouse_id = request.GET.get('warehouse_id')
            warehouse_type = request.GET.get('warehouse_type')
            export_format = request.GET.get('export_format')
            
            # Validate required parameters
            if not start_date or not end_date:
                return Response({
                    'success': False,
                    'error': 'Missing required parameters',
                    'message': 'start_date and end_date are required'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Parse dates
            try:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            except ValueError:
                return Response({
                    'success': False,
                    'error': 'Invalid date format',
                    'message': 'Dates must be in YYYY-MM-DD format'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Validate date range
            if end_date_obj < start_date_obj:
                return Response({
                    'success': False,
                    'error': 'Invalid date range',
                    'message': 'End date must be after start date'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Get user's business
            try:
                business = request.user.business_memberships.first().business
            except (AttributeError, Business.DoesNotExist):
                return Response({
                    'success': False,
                    'error': 'Business not found',
                    'message': 'User is not associated with a business'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Check cache
            cache_key = f"warehouse_analytics:{business.id}:{start_date}:{end_date}:{warehouse_id or 'all'}:{warehouse_type or 'all'}"
            cached_data = cache.get(cache_key)
            
            if cached_data and not export_format:
                return Response({
                    'success': True,
                    'cached': True,
                    'data': cached_data
                })
            
            # Query warehouses
            warehouses_query = Warehouse.objects.filter(
                business=business,
                is_active=True
            )
            
            if warehouse_id:
                warehouses_query = warehouses_query.filter(id=warehouse_id)
            
            if warehouse_type:
                warehouses_query = warehouses_query.filter(warehouse_type=warehouse_type)
            
            # Build analytics data
            warehouse_data = []
            
            for warehouse in warehouses_query:
                # Calculate metrics
                metrics = self._calculate_warehouse_metrics(
                    warehouse=warehouse,
                    business=business,
                    start_date=start_date_obj,
                    end_date=end_date_obj
                )
                
                # Get top products
                top_products = self._get_top_products(
                    warehouse=warehouse,
                    business=business,
                    start_date=start_date_obj,
                    end_date=end_date_obj,
                    limit=10
                )
                
                # Get slow movers
                slow_movers = self._get_slow_movers(
                    warehouse=warehouse,
                    business=business,
                    days_threshold=90,
                    limit=10
                )
                
                warehouse_data.append({
                    'warehouse_id': str(warehouse.id),
                    'warehouse_name': warehouse.name,
                    'warehouse_type': warehouse.warehouse_type,
                    'metrics': metrics,
                    'top_products': top_products,
                    'slow_movers': slow_movers
                })
            
            response_data = {
                'warehouses': warehouse_data
            }
            
            # Cache the response for 15 minutes
            cache.set(cache_key, response_data, 900)  # 15 minutes
            
            # Handle export formats
            if export_format == 'csv':
                return self._export_csv(warehouse_data, start_date, end_date)
            elif export_format == 'pdf':
                return self._export_pdf(warehouse_data, start_date, end_date)
            
            return Response({
                'success': True,
                'cached': False,
                'data': response_data
            })
            
        except Exception as e:
            logger.error(f"Error in warehouse analytics: {str(e)}", exc_info=True)
            return Response({
                'success': False,
                'error': 'Internal server error',
                'message': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def _calculate_warehouse_metrics(self, warehouse, business, start_date, end_date):
        """
        Calculate comprehensive metrics for a warehouse.
        
        Returns dict with:
        - total_products
        - total_stock_value
        - stock_turnover_ratio
        - average_days_in_stock
        - dead_stock_count
        - dead_stock_value
        - stock_accuracy
        - storage_utilization
        - movements (inbound, outbound, transfers_in, transfers_out)
        """
        
        # Total unique products with stock
        total_products = StockProduct.objects.filter(
            warehouse=warehouse,
            quantity__gt=0
        ).values('product').distinct().count()
        
        # Total stock value (quantity × cost_price)
        stock_value_data = StockProduct.objects.filter(
            warehouse=warehouse
        ).annotate(
            item_value=F('quantity') * F('product__cost_price')
        ).aggregate(
            total=Coalesce(Sum('item_value'), Value(0), output_field=DecimalField())
        )
        total_stock_value = float(stock_value_data['total'])
        
        # Stock turnover ratio = COGS / Average Inventory Value
        # COGS = total cost of items sold in period
        cogs_data = SaleItem.objects.filter(
            sale__storefront=warehouse,
            sale__sale_date__range=[start_date, end_date],
            sale__status__in=['COMPLETED', 'PARTIAL']
        ).annotate(
            item_cost=F('quantity') * F('product__cost_price')
        ).aggregate(
            total=Coalesce(Sum('item_cost'), Value(0), output_field=DecimalField())
        )
        cogs = float(cogs_data['total'])
        
        # Average inventory value (beginning + ending) / 2
        # For simplicity, use current value (ending) and assume similar beginning
        avg_inventory_value = total_stock_value
        
        stock_turnover_ratio = round(
            (cogs / avg_inventory_value) if avg_inventory_value > 0 else 0.0,
            2
        )
        
        # Average days in stock (approximate from last_restocked_date)
        avg_days_data = StockProduct.objects.filter(
            warehouse=warehouse,
            quantity__gt=0,
            last_restocked_date__isnull=False
        ).aggregate(
            avg_days=Avg(
                (timezone.now().date() - F('last_restocked_date')).total_seconds() / 86400
            )
        )
        average_days_in_stock = int(avg_days_data['avg_days'] or 0)
        
        # Dead stock: products with no sales in 180+ days
        dead_stock_threshold = timezone.now().date() - timedelta(days=180)
        
        # Find products with last sale before threshold or never sold
        dead_stock = StockProduct.objects.filter(
            warehouse=warehouse,
            quantity__gt=0
        ).filter(
            Q(product__id__in=self._get_products_with_no_recent_sales(
                warehouse, dead_stock_threshold
            ))
        )
        
        dead_stock_count = dead_stock.count()
        
        dead_stock_value_data = dead_stock.annotate(
            item_value=F('quantity') * F('product__cost_price')
        ).aggregate(
            total=Coalesce(Sum('item_value'), Value(0), output_field=DecimalField())
        )
        dead_stock_value = float(dead_stock_value_data['total'])
        
        # Stock accuracy (if we have cycle count data, otherwise default to high accuracy)
        # For now, return a placeholder - implement cycle count tracking separately
        stock_accuracy = 98.0  # Default assumption
        
        # Storage utilization (products / max_capacity × 100)
        # Assuming max_capacity is in number of product slots/SKUs
        max_capacity = getattr(warehouse, 'max_capacity', 1000)  # Default if not set
        storage_utilization = round(
            (total_products / max_capacity * 100) if max_capacity > 0 else 0.0,
            1
        )
        
        # Movement counts
        movements = self._calculate_movements(
            warehouse=warehouse,
            start_date=start_date,
            end_date=end_date
        )
        
        return {
            'total_products': total_products,
            'total_stock_value': round(total_stock_value, 2),
            'stock_turnover_ratio': stock_turnover_ratio,
            'average_days_in_stock': average_days_in_stock,
            'dead_stock_count': dead_stock_count,
            'dead_stock_value': round(dead_stock_value, 2),
            'stock_accuracy': stock_accuracy,
            'storage_utilization': storage_utilization,
            'movements': movements
        }
    
    def _get_products_with_no_recent_sales(self, warehouse, threshold_date):
        """Get product IDs that haven't sold since threshold_date"""
        
        # Get products that have recent sales
        products_with_recent_sales = SaleItem.objects.filter(
            sale__storefront=warehouse,
            sale__sale_date__gte=threshold_date,
            sale__status__in=['COMPLETED', 'PARTIAL']
        ).values_list('product_id', flat=True).distinct()
        
        # Get all products in warehouse
        all_products = StockProduct.objects.filter(
            warehouse=warehouse,
            quantity__gt=0
        ).values_list('product_id', flat=True)
        
        # Return products without recent sales
        return set(all_products) - set(products_with_recent_sales)
    
    def _calculate_movements(self, warehouse, start_date, end_date):
        """
        Calculate movement counts by type.
        
        Returns:
        - inbound: Sales, purchases, transfers in
        - outbound: Sales out, transfers out
        - transfers_in: Specific transfers in
        - transfers_out: Specific transfers out
        """
        
        # Inbound: Sales (to this storefront)
        inbound = SaleItem.objects.filter(
            sale__storefront=warehouse,
            sale__sale_date__range=[start_date, end_date]
        ).aggregate(count=Count('id'))['count'] or 0
        
        # Outbound: Same as inbound for storefronts (sales are outbound to customers)
        outbound = inbound
        
        # Transfers in: Check InventoryTransfer where destination is this warehouse
        from inventory.models import InventoryTransfer
        transfers_in = InventoryTransfer.objects.filter(
            destination_warehouse=warehouse,
            transfer_date__range=[start_date, end_date],
            status='COMPLETED'
        ).aggregate(count=Count('id'))['count'] or 0
        
        # Transfers out: Check InventoryTransfer where source is this warehouse
        transfers_out = InventoryTransfer.objects.filter(
            source_warehouse=warehouse,
            transfer_date__range=[start_date, end_date],
            status='COMPLETED'
        ).aggregate(count=Count('id'))['count'] or 0
        
        return {
            'inbound': inbound,
            'outbound': outbound,
            'transfers_in': transfers_in,
            'transfers_out': transfers_out
        }
    
    def _get_top_products(self, warehouse, business, start_date, end_date, limit=10):
        """
        Get top performing products by turnover rate.
        
        Turnover rate = total_sales / current_quantity
        """
        
        # Get products with sales in the period
        top_products = StockProduct.objects.filter(
            warehouse=warehouse,
            quantity__gt=0
        ).annotate(
            total_sales=Coalesce(
                Sum(
                    'product__saleitem__quantity',
                    filter=Q(
                        product__saleitem__sale__storefront=warehouse,
                        product__saleitem__sale__sale_date__range=[start_date, end_date],
                        product__saleitem__sale__status__in=['COMPLETED', 'PARTIAL']
                    )
                ),
                Value(0),
                output_field=DecimalField()
            ),
            item_value=F('quantity') * F('product__cost_price'),
            turnover_calc=Case(
                When(quantity__gt=0, then=F('total_sales') * 1.0 / F('quantity')),
                default=Value(0),
                output_field=DecimalField()
            )
        ).filter(
            total_sales__gt=0
        ).order_by('-turnover_calc')[:limit]
        
        return [
            {
                'product_id': str(sp.product.id),
                'product_name': sp.product.name,
                'quantity': sp.quantity,
                'value': round(float(sp.item_value), 2),
                'turnover_rate': round(float(sp.turnover_calc), 2)
            }
            for sp in top_products
        ]
    
    def _get_slow_movers(self, warehouse, business, days_threshold=90, limit=10):
        """
        Get slow moving products (no sales in days_threshold days).
        """
        
        threshold_date = timezone.now().date() - timedelta(days=days_threshold)
        
        # Get products with no recent sales
        slow_product_ids = self._get_products_with_no_recent_sales(warehouse, threshold_date)
        
        # Get stock products for these items
        slow_movers = StockProduct.objects.filter(
            warehouse=warehouse,
            product_id__in=slow_product_ids,
            quantity__gt=0
        ).annotate(
            item_value=F('quantity') * F('product__cost_price')
        ).annotate(
            # Get last sale date for this product at this warehouse
            last_sale_date_calc=Coalesce(
                Max(
                    'product__saleitem__sale__sale_date',
                    filter=Q(
                        product__saleitem__sale__storefront=warehouse,
                        product__saleitem__sale__status__in=['COMPLETED', 'PARTIAL']
                    )
                ),
                Value(timezone.now().date() - timedelta(days=999))
            ),
            days_since_sale_calc=Case(
                When(
                    last_sale_date_calc__isnull=False,
                    then=(timezone.now().date() - F('last_sale_date_calc')).total_seconds() / 86400
                ),
                default=Value(999),
                output_field=IntegerField()
            )
        ).order_by('-days_since_sale_calc')[:limit]
        
        result = []
        for sp in slow_movers:
            # Calculate days since last sale manually for accuracy
            last_sale = SaleItem.objects.filter(
                product=sp.product,
                sale__storefront=warehouse,
                sale__status__in=['COMPLETED', 'PARTIAL']
            ).order_by('-sale__sale_date').first()
            
            if last_sale:
                days_since = (timezone.now().date() - last_sale.sale.sale_date).days
            else:
                days_since = 999  # Never sold
            
            result.append({
                'product_id': str(sp.product.id),
                'product_name': sp.product.name,
                'quantity': sp.quantity,
                'value': round(float(sp.item_value), 2),
                'days_since_last_sale': days_since
            })
        
        return result
    
    def _export_csv(self, warehouse_data, start_date, end_date):
        """Export warehouse analytics as CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="warehouse_analytics_{start_date}_{end_date}.csv"'
        
        writer = csv.writer(response)
        
        # Header row
        writer.writerow([
            'Warehouse Name',
            'Type',
            'Total Products',
            'Stock Value',
            'Turnover Ratio',
            'Dead Stock Count',
            'Dead Stock Value',
            'Avg Days in Stock',
            'Storage Utilization'
        ])
        
        # Data rows
        for warehouse in warehouse_data:
            metrics = warehouse['metrics']
            writer.writerow([
                warehouse['warehouse_name'],
                warehouse['warehouse_type'],
                metrics['total_products'],
                metrics['total_stock_value'],
                metrics['stock_turnover_ratio'],
                metrics['dead_stock_count'],
                metrics['dead_stock_value'],
                metrics['average_days_in_stock'],
                metrics['storage_utilization']
            ])
        
        return response
    
    def _export_pdf(self, warehouse_data, start_date, end_date):
        """Export warehouse analytics as PDF"""
        from django.http import HttpResponse
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib import colors
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from io import BytesIO
        
        # Create PDF buffer
        buffer = BytesIO()
        
        # Create PDF document
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a1a1a'),
            spaceAfter=30,
            alignment=1  # Center
        )
        
        elements.append(Paragraph('Warehouse Analytics Report', title_style))
        elements.append(Paragraph(f'Period: {start_date} to {end_date}', styles['Normal']))
        elements.append(Paragraph(f'Generated: {timezone.now().strftime("%Y-%m-%d %H:%M")}', styles['Normal']))
        elements.append(Spacer(1, 0.5*inch))
        
        # Create table data
        table_data = [
            ['Warehouse', 'Type', 'Products', 'Stock Value', 'Turnover', 'Dead Stock']
        ]
        
        for warehouse in warehouse_data:
            metrics = warehouse['metrics']
            table_data.append([
                warehouse['warehouse_name'],
                warehouse['warehouse_type'],
                str(metrics['total_products']),
                f"₵{metrics['total_stock_value']:,.2f}",
                str(metrics['stock_turnover_ratio']),
                f"{metrics['dead_stock_count']} (₵{metrics['dead_stock_value']:,.2f})"
            ])
        
        # Create table
        table = Table(table_data, colWidths=[2*inch, 1*inch, 0.8*inch, 1.2*inch, 0.8*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(table)
        
        # Build PDF
        doc.build(elements)
        
        # Get PDF value
        pdf = buffer.getvalue()
        buffer.close()
        
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="warehouse_analytics_{start_date}_{end_date}.pdf"'
        response.write(pdf)
        
        return response
