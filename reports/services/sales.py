"""
Sales data export service
"""
from __future__ import annotations

from decimal import Decimal
from typing import Dict, Any
from django.db.models import Sum, Q, QuerySet
from django.utils import timezone

from sales.models import Sale, SaleItem
from .base import BaseDataExporter


class SalesExporter(BaseDataExporter):
    """Export sales data with line items, payments, and refunds"""
    
    def build_queryset(self, filters: Dict[str, Any]) -> QuerySet:
        """Build filtered sales queryset"""
        queryset = Sale.objects.select_related(
            'business', 'storefront', 'customer', 'user'
        ).prefetch_related(
            'sale_items__product',
            'sale_items__product__category',
            'payments',
            'refunds'
        )
        
        # Filter by business
        if self.business_ids is not None:
            if not self.business_ids:
                # User has no business access
                return Sale.objects.none()
            queryset = queryset.filter(business_id__in=self.business_ids)
        
        # Date range (required)
        if filters.get('start_date'):
            # Make timezone-aware
            from datetime import datetime, time
            start_datetime = timezone.make_aware(
                datetime.combine(filters['start_date'], time.min)
            )
            queryset = queryset.filter(created_at__gte=start_datetime)
        if filters.get('end_date'):
            # Include the entire end date
            from datetime import datetime, time
            end_datetime = timezone.make_aware(
                datetime.combine(filters['end_date'], time.max)
            )
            queryset = queryset.filter(created_at__lte=end_datetime)
        
        # Storefront filter
        if filters.get('storefront_id'):
            queryset = queryset.filter(storefront_id=filters['storefront_id'])
        
        # Customer filter
        if filters.get('customer_id'):
            queryset = queryset.filter(customer_id=filters['customer_id'])
        
        # Sale type
        if filters.get('sale_type'):
            queryset = queryset.filter(type=filters['sale_type'])
        
        # Status filter
        if filters.get('status'):
            queryset = queryset.filter(status=filters['status'])
        else:
            # Exclude DRAFT by default
            queryset = queryset.exclude(status='DRAFT')
        
        return queryset.order_by('-created_at')
    
    def serialize_data(self, queryset: QuerySet) -> Dict[str, Any]:
        """Convert sales to export-ready format"""
        
        # Summary calculations
        summary = {
            'total_sales': queryset.count(),
            'total_revenue': queryset.aggregate(
                total=Sum('total_amount')
            )['total'] or Decimal('0.00'),
            'total_tax': queryset.aggregate(
                total=Sum('tax_amount')
            )['total'] or Decimal('0.00'),
            'total_discounts': queryset.aggregate(
                total=Sum('discount_amount')
            )['total'] or Decimal('0.00'),
            'amount_paid': queryset.aggregate(
                total=Sum('amount_paid')
            )['total'] or Decimal('0.00'),
            'amount_refunded': queryset.aggregate(
                total=Sum('amount_refunded')
            )['total'] or Decimal('0.00'),
            'outstanding_balance': queryset.aggregate(
                total=Sum('amount_due')
            )['total'] or Decimal('0.00'),
        }
        
        # Calculate COGS and profit from line items
        # Note: These are calculated properties, so we need to iterate
        total_cogs = Decimal('0.00')
        total_profit = Decimal('0.00')
        
        for sale in queryset:
            for item in sale.sale_items.select_related('product', 'stock_product').all():
                unit_cost = item.unit_cost
                quantity = item.quantity
                cogs = unit_cost * quantity
                profit = item.total_profit_amount
                
                total_cogs += cogs
                total_profit += profit
        
        summary['total_cogs'] = total_cogs
        summary['total_profit'] = total_profit
        
        # Calculate profit margin
        if summary['total_revenue'] > 0:
            summary['profit_margin_percent'] = float(
                (summary['total_profit'] / summary['total_revenue']) * 100
            )
        else:
            summary['profit_margin_percent'] = 0.0
        
        # Calculate net sales (revenue - tax - discounts)
        summary['net_sales'] = (
            summary['total_revenue'] - 
            summary['total_tax'] - 
            summary['total_discounts']
        )
        
        # Detail rows (sales with line items)
        sales_data = []
        for sale in queryset:
            sale_row = {
                'receipt_number': sale.receipt_number or str(sale.id)[:8],
                'date': sale.created_at.strftime('%Y-%m-%d'),
                'time': sale.created_at.strftime('%H:%M:%S'),
                'storefront': sale.storefront.name if sale.storefront else '',
                'cashier': sale.user.name if (sale.user and hasattr(sale.user, 'name')) else (sale.user.email if sale.user else ''),
                'customer_name': sale.customer.name if sale.customer else 'Walk-in',
                'customer_type': sale.customer.customer_type if sale.customer else 'RETAIL',
                'sale_type': sale.type,
                'status': sale.status,
                'subtotal': str(sale.subtotal),
                'discount': str(sale.discount_amount),
                'tax': str(sale.tax_amount),
                'total': str(sale.total_amount),
                'amount_paid': str(sale.amount_paid),
                'amount_refunded': str(sale.amount_refunded),
                'amount_due': str(sale.amount_due),
                'payment_type': sale.payment_type,
                'notes': sale.notes or '',
            }
            
            # Line items for this sale
            items = []
            for item in sale.sale_items.select_related('product', 'product__category', 'stock_product').all():
                unit_cost = item.unit_cost
                total_cost = unit_cost * item.quantity
                profit = item.total_profit_amount
                margin_percent = 0.0
                if item.total_price > 0:
                    margin_percent = float((profit / item.total_price) * 100)
                
                items.append({
                    'product_name': item.product.name,
                    'sku': item.product.sku,
                    'category': item.product.category.name if item.product.category else '',
                    'quantity': str(item.quantity),
                    'unit_price': str(item.unit_price),
                    'total_price': str(item.total_price),
                    'cogs': str(total_cost.quantize(Decimal('0.01'))),
                    'profit': str(profit.quantize(Decimal('0.01'))),
                    'margin_percent': f'{margin_percent:.2f}',
                })
            
            sale_row['items'] = items
            sales_data.append(sale_row)
        
        return {
            'summary': summary,
            'sales': sales_data,
            'generated_at': timezone.now(),
            'filters_applied': self._format_filters(filters_data=queryset.query.where if hasattr(queryset, 'query') else {}),
        }
    
    def _format_filters(self, filters_data) -> Dict[str, str]:
        """Format filters for display in export"""
        # This is a placeholder - can be enhanced to show actual filters applied
        return {}
