from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Iterable, List, Optional

from django.db.models import QuerySet
from django.utils import timezone

from inventory.models import Inventory


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

        for record in queryset:
            stock = record.stock
            unit_cost = quantize(stock.unit_cost) if stock else quantize(record.product.cost)
            unit_tax_rate = quantize(stock.unit_tax_rate) if stock else Decimal('0.00')
            unit_tax_amount = quantize(stock.unit_tax_amount) if stock else Decimal('0.00')
            unit_additional = quantize(stock.unit_additional_cost) if stock else Decimal('0.00')

            quantity = int(record.quantity or 0)
            total_tax = quantize(unit_tax_amount * quantity)
            total_additional = quantize(unit_additional * quantity)
            inventory_value = quantize((unit_cost + unit_tax_amount + unit_additional) * quantity)

            row = InventoryReportRow(
                product_name=record.product.name,
                product_sku=record.product.sku,
                warehouse_name=record.warehouse.name,
                stock_reference=stock.reference_code if stock else None,
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
            totals['product_ids'].add(record.product_id)
            totals['warehouse_ids'].add(record.warehouse_id)

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

    def _apply_filters(self, filters: Dict[str, Any]) -> QuerySet[Inventory]:
        queryset = Inventory.objects.select_related('product', 'warehouse', 'stock').order_by(
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
