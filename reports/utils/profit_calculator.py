"""
Profit Calculation Utilities for Reports

Mirrors the profit calculation logic from sales.views.summary()
to ensure consistency across all reports.
"""

from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict
from typing import Dict
from django.db.models import QuerySet

from sales.models import SaleItem
from inventory.models import StockProduct


class ProfitCalculator:
    """
    Calculate profit metrics for sales
    
    Uses the same logic as the sales summary endpoint to ensure
    consistency across the application.
    """
    
    @staticmethod
    def to_decimal(value) -> Decimal:
        """Convert value to Decimal safely"""
        if value is None:
            return Decimal('0.00')
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except (Exception,):
            return Decimal('0.00')
    
    @staticmethod
    def calculate_sale_costs(sale_queryset: QuerySet) -> Dict[str, Dict[str, Decimal]]:
        """
        Calculate COGS, taxes, and discounts for sales
        
        Args:
            sale_queryset: QuerySet of Sale objects
            
        Returns:
            Dictionary with sale_id as key and dict of costs as value
            {
                sale_id: {
                    'cogs': Decimal,
                    'tax': Decimal,
                    'discount': Decimal,
                    'profit': Decimal
                }
            }
        """
        sale_ids = list(sale_queryset.values_list('id', flat=True))
        
        # Get all sale items
        sale_items = list(
            SaleItem.objects.filter(sale_id__in=sale_ids)
            .select_related('product', 'stock_product')
        )
        
        # Prefetch fallback stock products for items without a stock_product reference
        missing_product_ids = {
            item.product_id
            for item in sale_items
            if item.stock_product_id is None
        }
        
        fallback_stock = {}
        if missing_product_ids:
            for stock_product in (
                StockProduct.objects
                .filter(product_id__in=missing_product_ids)
                .order_by('product_id', '-created_at')
            ):
                if stock_product.product_id not in fallback_stock:
                    fallback_stock[stock_product.product_id] = stock_product
        
        # Calculate costs per sale
        sale_costs = defaultdict(lambda: Decimal('0.00'))
        sale_line_tax = defaultdict(lambda: Decimal('0.00'))
        sale_line_discount = defaultdict(lambda: Decimal('0.00'))
        
        for item in sale_items:
            quantity = ProfitCalculator.to_decimal(item.quantity)
            stock_product = item.stock_product or fallback_stock.get(item.product_id)
            
            if stock_product:
                unit_cost = (
                    ProfitCalculator.to_decimal(stock_product.unit_cost)
                    + ProfitCalculator.to_decimal(getattr(stock_product, 'unit_tax_amount', None))
                    + ProfitCalculator.to_decimal(getattr(stock_product, 'unit_additional_cost', None))
                )
            else:
                unit_cost = ProfitCalculator.to_decimal(item.product.get_latest_cost())
            
            sale_costs[item.sale_id] += (unit_cost * quantity)
            sale_line_tax[item.sale_id] += ProfitCalculator.to_decimal(item.tax_amount)
            sale_line_discount[item.sale_id] += ProfitCalculator.to_decimal(item.discount_amount)
        
        # Calculate profit for each sale
        results = {}
        for sale in sale_queryset:
            sale_tax_total = sale_line_tax[sale.id] + ProfitCalculator.to_decimal(sale.tax_amount)
            sale_discount_total = sale_line_discount[sale.id] + ProfitCalculator.to_decimal(sale.discount_amount)
            cogs = sale_costs[sale.id]
            total_amount = ProfitCalculator.to_decimal(sale.total_amount)
            net_revenue = total_amount - sale_tax_total
            profit = net_revenue - cogs
            
            results[sale.id] = {
                'cogs': cogs,
                'tax': sale_tax_total,
                'discount': sale_discount_total,
                'profit': profit,
                'net_revenue': net_revenue,
            }
        
        return results
    
    @staticmethod
    def calculate_total_profit(sale_queryset: QuerySet) -> Decimal:
        """
        Calculate total profit for a queryset of sales
        
        Args:
            sale_queryset: QuerySet of Sale objects
            
        Returns:
            Total profit as Decimal
        """
        sale_costs = ProfitCalculator.calculate_sale_costs(sale_queryset)
        total_profit = sum(
            costs['profit'] for costs in sale_costs.values()
        )
        return ProfitCalculator.to_decimal(total_profit)
    
    @staticmethod
    def calculate_profit_margin(total_profit: Decimal, total_revenue: Decimal) -> Decimal:
        """
        Calculate profit margin percentage
        
        Args:
            total_profit: Total profit amount
            total_revenue: Total revenue amount
            
        Returns:
            Profit margin as percentage (0-100)
        """
        if not total_revenue or total_revenue <= Decimal('0.00'):
            return Decimal('0.00')
        
        margin = (total_profit / total_revenue * Decimal('100.00'))
        return margin.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
