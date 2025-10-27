"""
Sales Filters for advanced querying
"""
from django_filters import rest_framework as filters
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from django.db.models import Q

from .models import Sale


class SaleFilter(filters.FilterSet):
    """Advanced filtering for Sales"""
    
    # Date range filters
    date_from = filters.DateTimeFilter(field_name='created_at', lookup_expr='gte')
    date_to = filters.DateTimeFilter(field_name='created_at', lookup_expr='lte')
    
    # Quick date range filter
    date_range = filters.CharFilter(method='filter_date_range')
    
    # Status filter (allow multiple)
    status = filters.MultipleChoiceFilter(
        choices=Sale.STATUS_CHOICES,
        conjoined=False  # OR logic
    )
    
    # Type filter
    type = filters.ChoiceFilter(
        choices=Sale.TYPE_CHOICES
    )
    
    # Payment type filter
    payment_type = filters.ChoiceFilter(
        field_name='payment_type',
        choices=Sale.PAYMENT_TYPE_CHOICES
    )
    
    # Amount range filters
    amount_min = filters.NumberFilter(field_name='total_amount', lookup_expr='gte')
    amount_max = filters.NumberFilter(field_name='total_amount', lookup_expr='lte')
    amount = filters.NumberFilter(method='filter_amount')
    
    # Storefront filter with permission validation
    storefront = filters.UUIDFilter(
        field_name='storefront__id',
        method='filter_storefront'
    )
    
    # Customer filter
    customer = filters.UUIDFilter(field_name='customer__id')
    
    # User/Cashier filter
    user = filters.UUIDFilter(field_name='user__id')
    
    # Search filter (receipt, customer name, product name)
    search = filters.CharFilter(method='filter_search')
    
    # Credit payment tracking filters
    has_outstanding_balance = filters.BooleanFilter(
        method='filter_outstanding_balance',
        label='Has Outstanding Balance'
    )
    
    payment_status = filters.ChoiceFilter(
        method='filter_payment_status',
        choices=[
            ('unpaid', 'Unpaid'),
            ('partial', 'Partially Paid'),
            ('paid', 'Fully Paid'),
        ],
        label='Payment Status (Credit Sales)'
    )
    
    def filter_date_range(self, queryset, name, value):
        """Filter by predefined date ranges"""
        now = timezone.now()
        
        if value == 'today':
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return queryset.filter(created_at__gte=start)
        
        elif value == 'yesterday':
            start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            end = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return queryset.filter(created_at__gte=start, created_at__lt=end)
        
        elif value == 'this_week':
            start = now - timedelta(days=now.weekday())
            start = start.replace(hour=0, minute=0, second=0, microsecond=0)
            return queryset.filter(created_at__gte=start)
        
        elif value == 'last_week':
            end = now - timedelta(days=now.weekday())
            end = end.replace(hour=0, minute=0, second=0, microsecond=0)
            start = end - timedelta(days=7)
            return queryset.filter(created_at__gte=start, created_at__lt=end)
        
        elif value == 'this_month':
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return queryset.filter(created_at__gte=start)
        
        elif value == 'last_month':
            # First day of current month
            end = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            # First day of last month
            if end.month == 1:
                start = end.replace(year=end.year-1, month=12)
            else:
                start = end.replace(month=end.month-1)
            return queryset.filter(created_at__gte=start, created_at__lt=end)
        
        elif value == 'last_30_days':
            start = now - timedelta(days=30)
            return queryset.filter(created_at__gte=start)
        
        elif value == 'last_90_days':
            start = now - timedelta(days=90)
            return queryset.filter(created_at__gte=start)
        
        elif value == 'this_year':
            start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            return queryset.filter(created_at__gte=start)
        
        elif value == 'last_year':
            end = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            start = end.replace(year=end.year-1)
            return queryset.filter(created_at__gte=start, created_at__lt=end)
        
        return queryset
    
    def filter_amount(self, queryset, name, value):
        """Filter by exact amount or within range"""
        try:
            amount = Decimal(str(value))
            # Allow ±5 tolerance for floating point matching
            return queryset.filter(
                Q(total_amount=amount) |
                Q(total_amount__gte=amount - Decimal('5'), total_amount__lte=amount + Decimal('5'))
            )
        except:
            return queryset
    
    def filter_search(self, queryset, name, value):
        """Search across receipt number, customer name, and product names"""
        if not value:
            return queryset
        
        search_term = value.strip()
        
        return queryset.filter(
            Q(receipt_number__icontains=search_term) |
            Q(customer__name__icontains=search_term) |
            Q(sale_items__product__name__icontains=search_term) |
            Q(sale_items__product__sku__icontains=search_term)
        ).distinct()
    
    def filter_storefront(self, queryset, name, value):
        """
        Validate user has access to requested storefront before applying filter.
        This ensures users can only filter to storefronts they have permission to view.
        """
        if not value:
            return queryset
        
        # Check if user has access to this storefront
        user = self.request.user
        if user.can_access_storefront(value):
            return queryset.filter(storefront__id=value)
        
        # User doesn't have access - return no results
        return queryset.none()
    
    def filter_outstanding_balance(self, queryset, name, value):
        """Filter sales with outstanding balances"""
        if value:
            return queryset.filter(amount_due__gt=Decimal('0.00'))
        return queryset.filter(amount_due=Decimal('0.00'))
    
    def filter_payment_status(self, queryset, name, value):
        """Filter by payment status for credit sales"""
        if value == 'unpaid':
            return queryset.filter(
                payment_type='CREDIT',
                amount_paid=Decimal('0.00'),
                amount_due__gt=Decimal('0.00')
            )
        elif value == 'partial':
            return queryset.filter(
                payment_type='CREDIT',
                amount_paid__gt=Decimal('0.00'),
                amount_due__gt=Decimal('0.00')
            )
        elif value == 'paid':
            return queryset.filter(
                payment_type='CREDIT',
                amount_due=Decimal('0.00')
            )
        return queryset
    
    class Meta:
        model = Sale
        fields = [
            'storefront', 'customer', 'user', 'status', 'type', 
            'payment_type', 'date_from', 'date_to', 'date_range',
            'amount_min', 'amount_max', 'amount', 'search',
            'has_outstanding_balance', 'payment_status'
        ]
