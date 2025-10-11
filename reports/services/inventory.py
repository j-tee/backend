from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Iterable, List, Optional

from django.db.models import QuerySet
from django.utils import timezone

from inventory.models import StockProduct, StoreFront, StoreFrontInventory, BusinessStoreFront
from .base import BaseDataExporter


TWOPLACES = Decimal('0.01')


def quantize(value: Optional[Decimal]) -> Decimal:
    if value is None:
        return Decimal('0.00')
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


@dataclass
class InventoryReportRow:
    product_name: str
    product_sku: str
    warehouse_name: str
    stock_reference: Optional[str]
    quantity: int
    unit_cost: Decimal
    unit_tax_rate: Decimal
    unit_tax_amount: Decimal
    unit_additional_cost: Decimal
    total_tax_amount: Decimal
    total_additional_cost: Decimal
    inventory_value: Decimal

    def as_list(self) -> List[Any]:
        return [
            self.product_name,
            self.product_sku,
            self.warehouse_name,
            self.stock_reference or 'N/A',
            self.quantity,
            quantize(self.unit_cost),
            quantize(self.unit_tax_rate),
            quantize(self.unit_tax_amount),
            quantize(self.unit_additional_cost),
            quantize(self.total_tax_amount),
            quantize(self.total_additional_cost),
            quantize(self.inventory_value),
        ]


class InventoryValuationReportBuilder:
    """Prepare valuation metrics for inventory lots."""

    summary_headers = [
        'Total Rows',
        'Distinct Products',
        'Distinct Warehouses',
        'Total Quantity',
        'Total Tax',
        'Total Additional Cost',
        'Inventory Value',
    ]

    detail_headers = [
        'Product',
        'SKU',
        'Warehouse',
        'Stock Ref',
        'Quantity',
        'Unit Cost',
        'Tax Rate %',
        'Unit Tax',
        'Unit Additional Cost',
        'Total Tax',
        'Total Additional Cost',
        'Inventory Value',
    ]

    def __init__(self, *, user):
        self.user = user

    def build(self, *, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        filters = filters or {}
        queryset = self._apply_filters(filters)

        rows: List[InventoryReportRow] = []
        totals = {
            'total_rows': 0,
            'total_quantity': 0,
            'total_tax_amount': Decimal('0.00'),
            'total_additional_cost': Decimal('0.00'),
            'inventory_value': Decimal('0.00'),
            'product_ids': set(),
            'warehouse_ids': set(),
        }

        for stock_product in queryset:
            unit_cost = quantize(stock_product.unit_cost)
            unit_tax_rate = quantize(stock_product.unit_tax_rate) if stock_product.unit_tax_rate else Decimal('0.00')
            unit_tax_amount = quantize(stock_product.unit_tax_amount) if stock_product.unit_tax_amount else Decimal('0.00')
            unit_additional = quantize(stock_product.unit_additional_cost) if stock_product.unit_additional_cost else Decimal('0.00')

            quantity = int(stock_product.quantity or 0)
            total_tax = quantize(unit_tax_amount * quantity)
            total_additional = quantize(unit_additional * quantity)
            inventory_value = quantize((unit_cost + unit_tax_amount + unit_additional) * quantity)

            row = InventoryReportRow(
                product_name=stock_product.product.name,
                product_sku=stock_product.product.sku,
                warehouse_name=stock_product.warehouse.name,
                stock_reference=stock_product.description or f"Batch {stock_product.stock.arrival_date}" if stock_product.stock.arrival_date else "N/A",
                quantity=quantity,
                unit_cost=unit_cost,
                unit_tax_rate=unit_tax_rate,
                unit_tax_amount=unit_tax_amount,
                unit_additional_cost=unit_additional,
                total_tax_amount=total_tax,
                total_additional_cost=total_additional,
                inventory_value=inventory_value,
            )
            rows.append(row)

            totals['total_rows'] += 1
            totals['total_quantity'] += quantity
            totals['total_tax_amount'] += total_tax
            totals['total_additional_cost'] += total_additional
            totals['inventory_value'] += inventory_value
            totals['product_ids'].add(stock_product.product_id)
            totals['warehouse_ids'].add(stock_product.warehouse_id)

        summary = {
            'total_rows': totals['total_rows'],
            'distinct_products': len(totals['product_ids']),
            'distinct_warehouses': len(totals['warehouse_ids']),
            'total_quantity': totals['total_quantity'],
            'total_tax_amount': quantize(totals['total_tax_amount']),
            'total_additional_cost': quantize(totals['total_additional_cost']),
            'inventory_value': quantize(totals['inventory_value']),
        }

        return {
            'generated_at': timezone.now(),
            'filters': filters,
            'summary': summary,
            'rows': rows,
            'summary_headers': self.summary_headers,
            'detail_headers': self.detail_headers,
        }

    def _apply_filters(self, filters: Dict[str, Any]) -> QuerySet[StockProduct]:
        queryset = StockProduct.objects.select_related('product', 'warehouse', 'stock').order_by(
            'product__name', 'warehouse__name'
        )
        warehouse_id = filters.get('warehouse_id')
        product_id = filters.get('product_id')
        business_id = filters.get('business_id')
        min_quantity = filters.get('min_quantity')

        if warehouse_id:
            queryset = queryset.filter(warehouse_id=warehouse_id)
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        if business_id:
            queryset = queryset.filter(warehouse__business_link__business_id=business_id)
        if min_quantity is not None:
            queryset = queryset.filter(quantity__gte=min_quantity)

        return queryset


class InventoryExporter(BaseDataExporter):
    """Export inventory data with current stock levels and valuation"""
    
    def build_queryset(self, filters: Dict[str, Any]) -> QuerySet:
        """Build filtered inventory queryset"""
        queryset = StoreFrontInventory.objects.select_related(
            'product',
            'storefront',
            'storefront__business_link',
            'storefront__business_link__business',
        )
        
        # Filter by business through BusinessStoreFront
        if self.business_ids is not None:
            if not self.business_ids:
                # User has no business access
                return StoreFrontInventory.objects.none()
            queryset = queryset.filter(storefront__business_link__business_id__in=self.business_ids)
        
        # Storefront filter
        if filters.get('storefront_id'):
            queryset = queryset.filter(storefront_id=filters['storefront_id'])
        
        # Product category filter
        if filters.get('category'):
            queryset = queryset.filter(product__category__name__icontains=filters['category'])
        
        # Stock level filters
        if filters.get('stock_status'):
            status = filters['stock_status']
            if status == 'out_of_stock':
                queryset = queryset.filter(quantity=0)
            elif status == 'low_stock':
                # Products with low quantity (less than 10)
                queryset = queryset.filter(quantity__gt=0, quantity__lte=10)
            elif status == 'in_stock':
                queryset = queryset.filter(quantity__gt=10)
        
        # Minimum quantity filter
        if filters.get('min_quantity') is not None:
            queryset = queryset.filter(quantity__gte=filters['min_quantity'])
        
        # Exclude products with zero value if requested
        if filters.get('exclude_zero_value', False):
            queryset = queryset.exclude(quantity=0)
        
        return queryset.order_by('storefront__name', 'product__name')
    
    def serialize_data(self, queryset: QuerySet, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Convert inventory to export-ready format"""
        from django.db.models import Sum
        
        if filters is None:
            filters = {}
        
        # Summary calculations
        total_items = queryset.count()
        total_quantity = queryset.aggregate(
            total=Sum('quantity')
        )['total'] or 0
        
        # Calculate total value - need to get pricing from products
        total_value = Decimal('0.00')
        for item in queryset:
            # Get business from storefront
            business = item.storefront.business_link.business if hasattr(item.storefront, 'business_link') else None
            
            if business:
                # Get unit cost from StockProduct if available
                stock_product = StockProduct.objects.filter(
                    warehouse__business_link__business=business,
                    product=item.product
                ).first()
                
                unit_cost = stock_product.unit_cost if stock_product else Decimal('0.00')
                total_value += (item.quantity * unit_cost)
        
        # Stock status breakdown
        out_of_stock = queryset.filter(quantity=0).count()
        low_stock = queryset.filter(quantity__gt=0, quantity__lte=10).count()
        in_stock = queryset.filter(quantity__gt=10).count()
        
        # Storefront breakdown
        by_storefront = {}
        storefronts = queryset.values('storefront__id', 'storefront__name').distinct()
        
        for sf in storefronts:
            sf_items = queryset.filter(storefront__id=sf['storefront__id'])
            sf_quantity = sf_items.aggregate(total=Sum('quantity'))['total'] or 0
            sf_value = Decimal('0.00')
            
            # Get business for pricing
            first_item = sf_items.first()
            if first_item and hasattr(first_item.storefront, 'business_link'):
                business = first_item.storefront.business_link.business
                
                for item in sf_items:
                    stock_product = StockProduct.objects.filter(
                        warehouse__business_link__business=business,
                        product=item.product
                    ).first()
                    unit_cost = stock_product.unit_cost if stock_product else Decimal('0.00')
                    sf_value += (item.quantity * unit_cost)
            
            by_storefront[sf['storefront__name']] = {
                'items': sf_items.count(),
                'quantity': sf_quantity,
                'value': sf_value,
            }
        
        summary = {
            'export_date': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_unique_products': total_items,
            'total_quantity_in_stock': total_quantity,
            'total_inventory_value': total_value,
            'out_of_stock_items': out_of_stock,
            'low_stock_items': low_stock,
            'in_stock_items': in_stock,
            'storefronts_count': len(by_storefront),
        }
        
        # Add storefront details to summary
        for idx, (name, data) in enumerate(by_storefront.items(), 1):
            summary[f'storefront_{idx}_name'] = name
            summary[f'storefront_{idx}_items'] = data['items']
            summary[f'storefront_{idx}_quantity'] = data['quantity']
            summary[f'storefront_{idx}_value'] = data['value']
        
        # Stock product details
        stock_data = []
        
        for stock_item in queryset:
            product = stock_item.product
            
            # Get business and pricing from StockProduct
            business = stock_item.storefront.business_link.business if hasattr(stock_item.storefront, 'business_link') else None
            
            if business:
                stock_product = StockProduct.objects.filter(
                    warehouse__business_link__business=business,
                    product=product
                ).first()
                
                if stock_product:
                    unit_cost = stock_product.unit_cost
                    retail_price = stock_product.retail_price
                    wholesale_price = stock_product.wholesale_price
                else:
                    unit_cost = Decimal('0.00')
                    retail_price = Decimal('0.00')
                    wholesale_price = Decimal('0.00')
            else:
                unit_cost = Decimal('0.00')
                retail_price = Decimal('0.00')
                wholesale_price = Decimal('0.00')
            
            # Calculate value
            item_value = stock_item.quantity * unit_cost
            
            # Determine stock status
            if stock_item.quantity == 0:
                status = 'Out of Stock'
            elif stock_item.quantity <= 10:
                status = 'Low Stock'
            else:
                status = 'In Stock'
            
            stock_row = {
                'product_id': str(stock_item.product.id),
                'product_name': product.name,
                'sku': product.sku or '',
                'barcode': product.barcode or '',
                'storefront': stock_item.storefront.name,
                
                # Stock levels
                'quantity_in_stock': stock_item.quantity,
                'reorder_level': 10,  # Default reorder level
                'unit_of_measure': product.unit or 'unit',
                'stock_status': status,
                
                # Pricing
                'unit_cost': str(unit_cost),
                'selling_price': str(retail_price),
                'total_value': str(item_value),
                'profit_margin': str(retail_price - unit_cost),
                'margin_percentage': self._calculate_margin_percentage(unit_cost, retail_price),
                
                # Metadata
                'last_updated': stock_item.updated_at.strftime('%Y-%m-%d %H:%M'),
                'created_at': stock_item.created_at.strftime('%Y-%m-%d'),
                'created_by': '',  # StoreFrontInventory doesn't have created_by
            }
            
            stock_data.append(stock_row)
        
        # Stock movement history (if requested) - Not implemented yet for StoreFrontInventory
        movements = []
        if filters.get('include_movement_history', False):
            # TODO: Implement movement tracking for StoreFrontInventory
            pass
        
        return {
            'summary': summary,
            'stock_items': stock_data,
            'stock_movements': movements,
        }
    
    def _calculate_margin_percentage(self, cost: Decimal, price: Decimal) -> str:
        """Calculate profit margin percentage"""
        if price <= 0:
            return '0.00'
        
        margin = ((price - cost) / price) * 100
        return f"{margin:.2f}"
    
    def _get_stock_movements(
        self, 
        queryset: QuerySet, 
        filters: Dict[str, Any]
    ) -> list:
        """Get stock adjustment history for the products"""
        # Not implemented for StoreFrontInventory yet
        # TODO: Track movements in StoreFrontInventory model
        return []
