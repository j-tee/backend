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
from django.db.models import (
    Sum,
    Count,
    F,
    Q,
    Case,
    When,
    Value,
    DecimalField,
    IntegerField,
    DateTimeField,
    ExpressionWrapper,
    OuterRef,
    Subquery,
)
from django.db.models.functions import Coalesce, Cast
from django.core.cache import cache
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import logging

from inventory.models import Warehouse, StockProduct, StoreFront, StoreFrontInventory
from inventory.transfer_models import Transfer
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
            
            # Query warehouses and storefronts
            # Note: In this system, Warehouse and StoreFront are separate models
            # We need to query both and combine them
            
            warehouses_list = []
            storefronts_list = []
            
            # Get warehouses
            warehouses = Warehouse.objects.filter(
                business_link__business=business,
                business_link__is_active=True
            )
            
            # Get storefronts
            storefronts = StoreFront.objects.filter(
                business_link__business=business,
                business_link__is_active=True
            )
            
            # Filter by warehouse_id if provided
            if warehouse_id:
                warehouses = warehouses.filter(id=warehouse_id)
                storefronts = storefronts.filter(id=warehouse_id)
            
            # Filter by warehouse_type if provided
            if warehouse_type:
                if warehouse_type == 'warehouse':
                    storefronts = StoreFront.objects.none()  # Exclude storefronts
                elif warehouse_type == 'storefront':
                    warehouses = Warehouse.objects.none()  # Exclude warehouses
            
            # Build warehouse data list
            all_locations = []
            
            # Add warehouses
            for warehouse in warehouses:
                all_locations.append({
                    'obj': warehouse,
                    'type': 'warehouse'
                })
            
            # Add storefronts
            for storefront in storefronts:
                all_locations.append({
                    'obj': storefront,
                    'type': 'storefront'
                })
            
            # Build analytics data
            warehouse_data = []
            
            for location_data in all_locations:
                location = location_data['obj']
                location_type = location_data['type']
                
                # Calculate metrics
                metrics = self._calculate_warehouse_metrics(
                    warehouse=location,
                    warehouse_type=location_type,
                    business=business,
                    start_date=start_date_obj,
                    end_date=end_date_obj
                )
                
                # Get top products
                top_products = self._get_top_products(
                    warehouse=location,
                    warehouse_type=location_type,
                    business=business,
                    start_date=start_date_obj,
                    end_date=end_date_obj,
                    limit=10
                )
                
                # Get slow movers
                slow_movers = self._get_slow_movers(
                    warehouse=location,
                    warehouse_type=location_type,
                    business=business,
                    days_threshold=90,
                    limit=10
                )
                
                warehouse_data.append({
                    'warehouse_id': str(location.id),
                    'warehouse_name': location.name,
                    'warehouse_type': location_type,
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
    
    def _calculate_warehouse_metrics(self, warehouse, warehouse_type, business, start_date, end_date):
        """
        Calculate comprehensive metrics for a warehouse or storefront.
        
        warehouse_type: 'warehouse' or 'storefront'
        
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
        
        if warehouse_type == 'storefront':
            inventory_qs = StoreFrontInventory.objects.filter(
                storefront=warehouse,
                quantity__gt=0
            )
            unit_cost_subquery = StockProduct.objects.filter(
                product_id=OuterRef('product_id'),
                stock__business=business
            ).order_by('-created_at').values('unit_cost')[:1]
            annotated_inventory = inventory_qs.annotate(
                effective_unit_cost=Coalesce(
                    Subquery(
                        unit_cost_subquery,
                        output_field=DecimalField(max_digits=12, decimal_places=2)
                    ),
                    Value(Decimal('0.00')),
                    output_field=DecimalField(max_digits=12, decimal_places=2)
                ),
                quantity_decimal=Cast(
                    F('quantity'),
                    DecimalField(max_digits=18, decimal_places=4)
                )
            )
        else:
            inventory_qs = StockProduct.objects.filter(
                warehouse=warehouse,
                calculated_quantity__gt=0
            )
            annotated_inventory = inventory_qs.annotate(
                effective_unit_cost=Coalesce(
                    F('unit_cost'),
                    Value(Decimal('0.00')),
                    output_field=DecimalField(max_digits=12, decimal_places=2)
                ),
                quantity_decimal=Cast(
                    F('calculated_quantity'),
                    DecimalField(max_digits=18, decimal_places=4)
                )
            )

        annotated_inventory = annotated_inventory.annotate(
            item_value=ExpressionWrapper(
                F('quantity_decimal') * F('effective_unit_cost'),
                output_field=DecimalField(max_digits=18, decimal_places=4)
            )
        )

        total_products = annotated_inventory.values('product_id').distinct().count()

        stock_value_data = annotated_inventory.aggregate(
            total=Coalesce(
                Sum('item_value'),
                Value(Decimal('0.00')),
                output_field=DecimalField(max_digits=18, decimal_places=4)
            )
        )
        total_stock_value = float(stock_value_data['total'])
        
        # Stock turnover ratio = COGS / Average Inventory Value
        # COGS = total cost of items sold in period
        # For storefronts, sales happen there; for warehouses, track outbound movements
        if warehouse_type == 'storefront':
            cogs_data = SaleItem.objects.filter(
                sale__storefront=warehouse,
                sale__created_at__date__range=[start_date, end_date],
                sale__status__in=['COMPLETED', 'PARTIAL']
            ).annotate(
                item_cost=ExpressionWrapper(
                    Cast(F('quantity'), DecimalField(max_digits=18, decimal_places=4)) *
                    Coalesce(F('stock_product__unit_cost'), Value(Decimal('0.00'))),
                    output_field=DecimalField(max_digits=18, decimal_places=4)
                )
            ).aggregate(
                total=Coalesce(
                    Sum('item_cost'),
                    Value(Decimal('0.00')),
                    output_field=DecimalField(max_digits=18, decimal_places=4)
                )
            )
        else:
            # For warehouses, COGS would be from transfers out or adjustments
            # Since we don't track direct sales from warehouses, use zero
            cogs_data = {'total': Decimal('0.00')}
        
        cogs = float(cogs_data['total'])
        
        # Average inventory value (beginning + ending) / 2
        # For simplicity, use current value (ending) and assume similar beginning
        avg_inventory_value = total_stock_value
        
        stock_turnover_ratio = round(
            (cogs / avg_inventory_value) if avg_inventory_value > 0 else 0.0,
            2
        )
        
        # Average days in stock (approximate from stock arrival or inventory updates)
        days_in_stock: list[int] = []
        today = timezone.now().date()

        if warehouse_type == 'storefront':
            inventory_dates = StoreFrontInventory.objects.filter(
                storefront=warehouse,
                quantity__gt=0
            ).values_list('created_at', 'updated_at')

            for created_at, updated_at in inventory_dates:
                restock_dt = (updated_at or created_at)
                if not restock_dt:
                    continue
                restock_date = restock_dt.date() if hasattr(restock_dt, 'date') else restock_dt
                days_in_stock.append(max((today - restock_date).days, 0))
        else:
            stock_dates = StockProduct.objects.filter(
                warehouse=warehouse,
                calculated_quantity__gt=0
            ).values_list('stock__arrival_date', 'created_at')

            for arrival_date, created_at in stock_dates:
                restock_date = arrival_date or (created_at.date() if created_at else None)
                if not restock_date:
                    continue
                days_in_stock.append(max((today - restock_date).days, 0))

        average_days_in_stock = int(sum(days_in_stock) / len(days_in_stock)) if days_in_stock else 0
        
        # Dead stock: products with no sales in 180+ days
        dead_stock_threshold = timezone.now().date() - timedelta(days=180)
        
        # Find products with last sale before threshold or never sold
        dead_stock_ids = self._get_products_with_no_recent_sales(
            warehouse, warehouse_type, dead_stock_threshold
        )
        dead_stock = annotated_inventory.filter(product_id__in=dead_stock_ids)
        dead_stock_count = dead_stock.count()

        dead_stock_value_data = dead_stock.aggregate(
            total=Coalesce(
                Sum('item_value'),
                Value(Decimal('0.00')),
                output_field=DecimalField(max_digits=18, decimal_places=4)
            )
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
            warehouse_type=warehouse_type,
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
    
    def _get_products_with_no_recent_sales(self, warehouse, warehouse_type, threshold_date):
        """Get product IDs that haven't sold since threshold_date"""
        
        # Only check sales for storefronts
        if warehouse_type == 'storefront':
            # Get products that have recent sales
            products_with_recent_sales = SaleItem.objects.filter(
                sale__storefront=warehouse,
                sale__created_at__date__gte=threshold_date,
                sale__status__in=['COMPLETED', 'PARTIAL']
            ).values_list('product_id', flat=True).distinct()
            all_products = StoreFrontInventory.objects.filter(
                storefront=warehouse,
                quantity__gt=0
            ).values_list('product_id', flat=True)
        else:
            # For warehouses, no direct sales, so all are "dead stock" by this metric
            products_with_recent_sales = []
            all_products = StockProduct.objects.filter(
                warehouse=warehouse,
                calculated_quantity__gt=0
            ).values_list('product_id', flat=True)
        
        # Return products without recent sales
        return set(all_products) - set(products_with_recent_sales)
    
    def _calculate_movements(self, warehouse, warehouse_type, start_date, end_date):
        """
        Calculate movement counts by type.
        
        Returns:
        - inbound: Sales, purchases, transfers in
        - outbound: Sales out, transfers out
        - transfers_in: Specific transfers in
        - transfers_out: Specific transfers out
        """
        
        # For storefronts: inbound/outbound are sales
        if warehouse_type == 'storefront':
            # Inbound: Sales (to this storefront)
            sales_count = SaleItem.objects.filter(
                sale__storefront=warehouse,
                sale__created_at__date__range=[start_date, end_date]
            ).aggregate(count=Count('id'))['count'] or 0
            inbound = sales_count
            outbound = sales_count

            transfers_in = Transfer.objects.filter(
                destination_storefront=warehouse,
                status=Transfer.STATUS_COMPLETED,
                completed_at__date__range=[start_date, end_date]
            ).count()
            transfers_out = 0  # Storefronts do not initiate transfers in current workflow
            inbound += transfers_in
        else:
            # For warehouses: no direct sales, initialize counts
            inbound = 0
            outbound = 0

            transfers_in = Transfer.objects.filter(
                destination_warehouse=warehouse,
                status=Transfer.STATUS_COMPLETED,
                completed_at__date__range=[start_date, end_date]
            ).count()
            transfers_out = Transfer.objects.filter(
                source_warehouse=warehouse,
                status=Transfer.STATUS_COMPLETED,
                completed_at__date__range=[start_date, end_date]
            ).count()
            inbound += transfers_in
            outbound += transfers_out
        
        return {
            'inbound': inbound,
            'outbound': outbound,
            'transfers_in': transfers_in,
            'transfers_out': transfers_out
        }
    
    def _get_top_products(self, warehouse, warehouse_type, business, start_date, end_date, limit=10):
        """
        Get top performing products by turnover rate.
        
        Turnover rate = total_sales / current_quantity
        """
        
        # Only calculate for storefronts where sales happen
        if warehouse_type != 'storefront':
            return []
        
        inventory_quantity_subquery = StoreFrontInventory.objects.filter(
            storefront=warehouse,
            product_id=OuterRef('product_id')
        ).values('quantity')[:1]

        unit_cost_subquery = StockProduct.objects.filter(
            product_id=OuterRef('product_id'),
            stock__business=business
        ).order_by('-created_at').values('unit_cost')[:1]

        top_products = SaleItem.objects.filter(
            sale__storefront=warehouse,
            sale__created_at__date__range=[start_date, end_date],
            sale__status__in=['COMPLETED', 'PARTIAL']
        ).values(
            'product_id',
            'product__name'
        ).annotate(
            total_sales=Coalesce(
                Sum('quantity'),
                Value(Decimal('0.00')),
                output_field=DecimalField(max_digits=18, decimal_places=4)
            ),
            inventory_quantity=Coalesce(
                Subquery(
                    inventory_quantity_subquery,
                    output_field=IntegerField()
                ),
                Value(0),
                output_field=IntegerField()
            ),
            unit_cost=Coalesce(
                Subquery(
                    unit_cost_subquery,
                    output_field=DecimalField(max_digits=12, decimal_places=2)
                ),
                Value(Decimal('0.00')),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            )
        ).annotate(
            quantity_decimal=Cast(F('inventory_quantity'), DecimalField(max_digits=18, decimal_places=4)),
            total_sales_decimal=Cast(F('total_sales'), DecimalField(max_digits=18, decimal_places=4))
        ).annotate(
            item_value=ExpressionWrapper(
                F('quantity_decimal') * F('unit_cost'),
                output_field=DecimalField(max_digits=18, decimal_places=4)
            ),
            turnover_calc=Case(
                When(
                    inventory_quantity__gt=0,
                    then=ExpressionWrapper(
                        F('total_sales_decimal') / F('quantity_decimal'),
                        output_field=DecimalField(max_digits=18, decimal_places=4)
                    )
                ),
                default=Value(Decimal('0.00')),
                output_field=DecimalField(max_digits=18, decimal_places=4)
            )
        ).filter(
            total_sales__gt=0,
            inventory_quantity__gt=0
        ).order_by('-turnover_calc')[:limit]

        return [
            {
                'product_id': str(item['product_id']),
                'product_name': item['product__name'],
                'quantity': int(item['inventory_quantity'] or 0),
                'value': round(float(item['item_value'] or Decimal('0.00')), 2),
                'turnover_rate': round(float(item['turnover_calc'] or Decimal('0.00')), 2)
            }
            for item in top_products
        ]
    
    def _get_slow_movers(self, warehouse, warehouse_type, business, days_threshold=90, limit=10):
        """
        Get slow moving products (no sales in days_threshold days).
        """
        
        # Only calculate for storefronts where sales happen
        if warehouse_type != 'storefront':
            return []
        
        threshold_date = timezone.now().date() - timedelta(days=days_threshold)
        
        # Get products with no recent sales
        slow_product_ids = list(
            self._get_products_with_no_recent_sales(warehouse, warehouse_type, threshold_date)
        )

        if not slow_product_ids:
            return []

        last_sale_subquery = SaleItem.objects.filter(
            sale__storefront=warehouse,
            sale__status__in=['COMPLETED', 'PARTIAL'],
            product_id=OuterRef('product_id')
        ).order_by('-sale__created_at').values('sale__created_at')[:1]

        unit_cost_subquery = StockProduct.objects.filter(
            product_id=OuterRef('product_id'),
            stock__business=business
        ).order_by('-created_at').values('unit_cost')[:1]

        slow_inventory = StoreFrontInventory.objects.filter(
            storefront=warehouse,
            quantity__gt=0,
            product_id__in=slow_product_ids
        ).select_related('product').annotate(
            last_sale_date=Subquery(
                last_sale_subquery,
                output_field=DateTimeField()
            ),
            unit_cost=Coalesce(
                Subquery(
                    unit_cost_subquery,
                    output_field=DecimalField(max_digits=12, decimal_places=2)
                ),
                Value(Decimal('0.00')),
                output_field=DecimalField(max_digits=12, decimal_places=2)
            ),
            quantity_decimal=Cast(
                F('quantity'),
                DecimalField(max_digits=18, decimal_places=4)
            )
        ).annotate(
            item_value=ExpressionWrapper(
                F('quantity_decimal') * F('unit_cost'),
                output_field=DecimalField(max_digits=18, decimal_places=4)
            )
        ).order_by('last_sale_date', 'product__name')[:limit]

        today = timezone.now().date()
        result = []

        for entry in slow_inventory:
            last_sale_date = entry.last_sale_date
            if last_sale_date:
                if isinstance(last_sale_date, datetime):
                    last_sale_date = last_sale_date.date()
                days_since = max((today - last_sale_date).days, 0)
            else:
                days_since = 999  # Never sold

            result.append({
                'product_id': str(entry.product.id),
                'product_name': entry.product.name,
                'quantity': int(entry.quantity or 0),
                'value': round(float(entry.item_value or Decimal('0.00')), 2),
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
