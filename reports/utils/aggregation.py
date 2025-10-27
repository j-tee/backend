"""
Aggregation Utilities for Reports

Provides common aggregation patterns and calculations.
"""

from typing import List, Dict, Any, Optional
from decimal import Decimal
from django.db.models import Sum, Avg, Count, Min, Max, Q, F
from django.db.models.functions import TruncDate, TruncMonth, Coalesce


class AggregationHelper:
    """Helper class for common aggregation operations"""
    
    @staticmethod
    def calculate_percentage(part: Decimal, whole: Decimal, decimal_places: int = 2) -> Decimal:
        """
        Calculate percentage safely
        
        Args:
            part: Part value
            whole: Whole value
            decimal_places: Number of decimal places
            
        Returns:
            Percentage as Decimal
        """
        if not whole or whole == 0:
            return Decimal('0.00')
        
        percentage = (part / whole) * 100
        return round(percentage, decimal_places)
    
    @staticmethod
    def calculate_growth_rate(
        current: Decimal,
        previous: Decimal,
        decimal_places: int = 2
    ) -> Decimal:
        """
        Calculate growth rate between two periods
        
        Args:
            current: Current period value
            previous: Previous period value
            decimal_places: Number of decimal places
            
        Returns:
            Growth rate as percentage
        """
        if not previous or previous == 0:
            return Decimal('0.00') if not current else Decimal('100.00')
        
        growth = ((current - previous) / previous) * 100
        return round(growth, decimal_places)
    
    @staticmethod
    def safe_divide(
        numerator: Decimal,
        denominator: Decimal,
        decimal_places: int = 2,
        default: Decimal = Decimal('0.00')
    ) -> Decimal:
        """
        Safely divide two numbers
        
        Args:
            numerator: Numerator
            denominator: Denominator
            decimal_places: Number of decimal places
            default: Default value if division by zero
            
        Returns:
            Result of division or default
        """
        if not denominator or denominator == 0:
            return default
        
        result = numerator / denominator
        return round(result, decimal_places)
    
    @staticmethod
    def sum_field(queryset, field_name: str) -> Decimal:
        """
        Sum a field in queryset
        
        Args:
            queryset: Django queryset
            field_name: Field to sum
            
        Returns:
            Sum as Decimal
        """
        result = queryset.aggregate(total=Sum(field_name))['total']
        return Decimal(str(result)) if result else Decimal('0.00')
    
    @staticmethod
    def avg_field(queryset, field_name: str, decimal_places: int = 2) -> Decimal:
        """
        Average a field in queryset
        
        Args:
            queryset: Django queryset
            field_name: Field to average
            decimal_places: Number of decimal places
            
        Returns:
            Average as Decimal
        """
        result = queryset.aggregate(avg=Avg(field_name))['avg']
        if result:
            return round(Decimal(str(result)), decimal_places)
        return Decimal('0.00')
    
    @staticmethod
    def count_queryset(queryset) -> int:
        """
        Count items in queryset
        
        Args:
            queryset: Django queryset
            
        Returns:
            Count
        """
        return queryset.count()
    
    @staticmethod
    def group_by_date(
        queryset,
        date_field: str,
        value_field: str,
        aggregation: str = 'sum'
    ) -> List[Dict[str, Any]]:
        """
        Group queryset by date and aggregate values
        
        Args:
            queryset: Django queryset
            date_field: Date field to group by
            value_field: Field to aggregate
            aggregation: Type of aggregation ('sum', 'avg', 'count')
            
        Returns:
            List of dictionaries with date and aggregated value
        """
        agg_func = {
            'sum': Sum(value_field),
            'avg': Avg(value_field),
            'count': Count(value_field),
        }.get(aggregation, Sum(value_field))
        
        return list(
            queryset
            .annotate(date=TruncDate(date_field))
            .values('date')
            .annotate(value=agg_func)
            .order_by('date')
        )
    
    @staticmethod
    def group_by_month(
        queryset,
        date_field: str,
        value_field: str,
        aggregation: str = 'sum'
    ) -> List[Dict[str, Any]]:
        """
        Group queryset by month and aggregate values
        
        Args:
            queryset: Django queryset
            date_field: Date field to group by
            value_field: Field to aggregate
            aggregation: Type of aggregation ('sum', 'avg', 'count')
            
        Returns:
            List of dictionaries with month and aggregated value
        """
        agg_func = {
            'sum': Sum(value_field),
            'avg': Avg(value_field),
            'count': Count(value_field),
        }.get(aggregation, Sum(value_field))
        
        return list(
            queryset
            .annotate(month=TruncMonth(date_field))
            .values('month')
            .annotate(value=agg_func)
            .order_by('month')
        )
    
    @staticmethod
    def top_n(
        queryset,
        group_field: str,
        value_field: str,
        n: int = 10,
        aggregation: str = 'sum'
    ) -> List[Dict[str, Any]]:
        """
        Get top N items by aggregated value
        
        Args:
            queryset: Django queryset
            group_field: Field to group by
            value_field: Field to aggregate
            n: Number of top items
            aggregation: Type of aggregation ('sum', 'avg', 'count')
            
        Returns:
            List of top N items
        """
        agg_func = {
            'sum': Sum(value_field),
            'avg': Avg(value_field),
            'count': Count(value_field),
        }.get(aggregation, Sum(value_field))
        
        return list(
            queryset
            .values(group_field)
            .annotate(value=agg_func)
            .order_by('-value')[:n]
        )


class PercentageCalculator:
    """Calculate percentage distributions"""
    
    @staticmethod
    def add_percentage_to_list(
        items: List[Dict[str, Any]],
        value_key: str = 'value',
        percentage_key: str = 'percentage'
    ) -> List[Dict[str, Any]]:
        """
        Add percentage field to list of items based on their values
        
        Args:
            items: List of dictionaries containing values
            value_key: Key for value field
            percentage_key: Key for percentage field to add
            
        Returns:
            Modified list with percentages
        """
        total = sum(Decimal(str(item.get(value_key, 0))) for item in items)
        
        for item in items:
            value = Decimal(str(item.get(value_key, 0)))
            item[percentage_key] = float(
                AggregationHelper.calculate_percentage(value, total)
            )
        
        return items


class RankingHelper:
    """Helper for ranking and sorting operations"""
    
    @staticmethod
    def add_rank_to_list(
        items: List[Dict[str, Any]],
        value_key: str = 'value',
        rank_key: str = 'rank',
        descending: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Add rank field to list of items
        
        Args:
            items: List of dictionaries
            value_key: Key to rank by
            rank_key: Key for rank field to add
            descending: Whether to rank in descending order (highest = 1)
            
        Returns:
            Modified list with ranks
        """
        # Sort items
        sorted_items = sorted(
            items,
            key=lambda x: Decimal(str(x.get(value_key, 0))),
            reverse=descending
        )
        
        # Add ranks
        for rank, item in enumerate(sorted_items, start=1):
            item[rank_key] = rank
        
        return sorted_items
