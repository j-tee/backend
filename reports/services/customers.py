"""
Customer data export service with credit aging analysis
"""
from __future__ import annotations

from decimal import Decimal
from typing import Dict, Any
from django.db.models import Sum, Q, QuerySet, Count
from django.utils import timezone
from datetime import timedelta

from sales.models import Customer, Sale, CreditTransaction
from .base import BaseDataExporter


class CustomerExporter(BaseDataExporter):
    """Export customer data with credit history and aging analysis"""
    
    def build_queryset(self, filters: Dict[str, Any]) -> QuerySet:
        """Build filtered customer queryset"""
        queryset = Customer.objects.select_related('business', 'created_by').prefetch_related(
            'sales',
            'credit_transactions'
        )
        
        # Filter by business
        if self.business_ids is not None:
            if not self.business_ids:
                # User has no business access
                return Customer.objects.none()
            queryset = queryset.filter(business_id__in=self.business_ids)
        
        # Customer type filter
        if filters.get('customer_type'):
            queryset = queryset.filter(customer_type=filters['customer_type'])
        
        # Credit status filter
        credit_status = filters.get('credit_status')
        if credit_status == 'blocked':
            queryset = queryset.filter(credit_blocked=True)
        elif credit_status == 'active':
            queryset = queryset.filter(credit_blocked=False, is_active=True)
        elif credit_status == 'overdue':
            # Will filter in Python after calculating overdue amounts
            pass
        
        # Minimum outstanding balance filter
        if filters.get('min_outstanding_balance'):
            min_balance = Decimal(str(filters['min_outstanding_balance']))
            queryset = queryset.filter(outstanding_balance__gte=min_balance)
        
        # Active status
        if filters.get('is_active') is not None:
            queryset = queryset.filter(is_active=filters['is_active'])
        else:
            # Default to active customers only
            queryset = queryset.filter(is_active=True)
        
        return queryset.order_by('name')
    
    def serialize_data(self, queryset: QuerySet, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Convert customers to export-ready format"""
        if filters is None:
            filters = {}
        
        # Summary calculations
        total_customers = queryset.count()
        retail_count = queryset.filter(customer_type='RETAIL').count()
        wholesale_count = queryset.filter(customer_type='WHOLESALE').count()
        
        # Credit statistics
        total_credit_limit = queryset.aggregate(
            total=Sum('credit_limit')
        )['total'] or Decimal('0.00')
        
        total_outstanding = queryset.aggregate(
            total=Sum('outstanding_balance')
        )['total'] or Decimal('0.00')
        
        blocked_count = queryset.filter(credit_blocked=True).count()
        
        summary = {
            'total_customers': total_customers,
            'retail_customers': retail_count,
            'wholesale_customers': wholesale_count,
            'total_credit_limit': total_credit_limit,
            'total_outstanding_balance': total_outstanding,
            'total_available_credit': total_credit_limit - total_outstanding,
            'blocked_customers': blocked_count,
            'active_customers': queryset.filter(is_active=True).count(),
        }
        
        # Customer details with aging analysis
        customers_data = []
        aging_buckets = {
            'current': Decimal('0.00'),      # 0-30 days
            '31_60': Decimal('0.00'),        # 31-60 days
            '61_90': Decimal('0.00'),        # 61-90 days
            'over_90': Decimal('0.00'),      # Over 90 days
        }
        
        for customer in queryset:
            # Calculate aging
            aging = self._calculate_aging(customer)
            
            # Add to buckets
            aging_buckets['current'] += aging['current']
            aging_buckets['31_60'] += aging['31_60']
            aging_buckets['61_90'] += aging['61_90']
            aging_buckets['over_90'] += aging['over_90']
            
            # Get sales statistics
            sales_stats = self._get_sales_statistics(customer)
            
            customer_row = {
                'customer_id': str(customer.id),
                'name': customer.name,
                'email': customer.email or '',
                'phone': customer.phone or '',
                'address': customer.address or '',
                'customer_type': customer.customer_type,
                'contact_person': customer.contact_person or '',
                
                # Credit information
                'credit_limit': str(customer.credit_limit),
                'outstanding_balance': str(customer.outstanding_balance),
                'available_credit': str(customer.available_credit),
                'credit_terms_days': customer.credit_terms_days,
                'credit_blocked': 'Yes' if customer.credit_blocked else 'No',
                
                # Aging buckets
                'aging_current': str(aging['current']),
                'aging_31_60': str(aging['31_60']),
                'aging_61_90': str(aging['61_90']),
                'aging_over_90': str(aging['over_90']),
                'total_overdue': str(aging['total_overdue']),
                'oldest_invoice_days': aging['oldest_days'],
                
                # Sales statistics
                'total_sales_count': sales_stats['count'],
                'total_sales_amount': str(sales_stats['total_amount']),
                'average_sale_amount': str(sales_stats['average_amount']),
                'last_sale_date': sales_stats['last_sale_date'],
                'first_sale_date': sales_stats['first_sale_date'],
                
                # Status
                'is_active': 'Yes' if customer.is_active else 'No',
                'created_at': customer.created_at.strftime('%Y-%m-%d'),
                'created_by': customer.created_by.name if (customer.created_by and hasattr(customer.created_by, 'name')) else '',
            }
            
            customers_data.append(customer_row)
        
        # Add aging summary to overall summary
        summary['aging_current'] = aging_buckets['current']
        summary['aging_31_60'] = aging_buckets['31_60']
        summary['aging_61_90'] = aging_buckets['61_90']
        summary['aging_over_90'] = aging_buckets['over_90']
        summary['total_overdue'] = (
            aging_buckets['31_60'] + 
            aging_buckets['61_90'] + 
            aging_buckets['over_90']
        )
        
        # Credit transactions (if requested)
        credit_transactions = []
        if filters.get('include_credit_history', True):
            credit_transactions = self._get_credit_transactions(queryset)
        
        return {
            'summary': summary,
            'customers': customers_data,
            'credit_transactions': credit_transactions,
            'generated_at': timezone.now(),
        }
    
    def _calculate_aging(self, customer: Customer) -> Dict[str, Any]:
        """Calculate aging buckets for customer's outstanding balances"""
        now = timezone.now()
        
        # Get all unpaid/partially paid credit sales
        credit_sales = Sale.objects.filter(
            customer=customer,
            payment_type='CREDIT',
            status__in=['PENDING', 'PARTIAL']
        ).order_by('created_at')
        
        aging = {
            'current': Decimal('0.00'),      # 0-30 days
            '31_60': Decimal('0.00'),
            '61_90': Decimal('0.00'),
            'over_90': Decimal('0.00'),
            'total_overdue': Decimal('0.00'),
            'oldest_days': 0,
        }
        
        oldest_date = None
        
        for sale in credit_sales:
            days_old = (now.date() - sale.created_at.date()).days
            amount_due = sale.amount_due
            
            if days_old <= 30:
                aging['current'] += amount_due
            elif days_old <= 60:
                aging['31_60'] += amount_due
                aging['total_overdue'] += amount_due
            elif days_old <= 90:
                aging['61_90'] += amount_due
                aging['total_overdue'] += amount_due
            else:
                aging['over_90'] += amount_due
                aging['total_overdue'] += amount_due
            
            if oldest_date is None or sale.created_at < oldest_date:
                oldest_date = sale.created_at
        
        if oldest_date:
            aging['oldest_days'] = (now.date() - oldest_date.date()).days
        
        return aging
    
    def _get_sales_statistics(self, customer: Customer) -> Dict[str, Any]:
        """Get sales statistics for customer"""
        sales = Sale.objects.filter(
            customer=customer,
            status__in=['COMPLETED', 'PARTIAL', 'PENDING']
        )
        
        stats = sales.aggregate(
            count=Count('id'),
            total=Sum('total_amount')
        )
        
        count = stats['count'] or 0
        total = stats['total'] or Decimal('0.00')
        
        # Get first and last sale dates
        first_sale = sales.order_by('created_at').first()
        last_sale = sales.order_by('-created_at').first()
        
        return {
            'count': count,
            'total_amount': total,
            'average_amount': (total / count) if count > 0 else Decimal('0.00'),
            'first_sale_date': first_sale.created_at.strftime('%Y-%m-%d') if first_sale else '',
            'last_sale_date': last_sale.created_at.strftime('%Y-%m-%d') if last_sale else '',
        }
    
    def _get_credit_transactions(self, customers: QuerySet) -> list:
        """Get credit transaction history for customers"""
        transactions = []
        
        for customer in customers:
            customer_transactions = CreditTransaction.objects.filter(
                customer=customer
            ).order_by('-created_at')[:50]  # Last 50 transactions per customer
            
            for txn in customer_transactions:
                transactions.append({
                    'customer_name': customer.name,
                    'date': txn.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'transaction_type': txn.transaction_type,
                    'amount': str(txn.amount),
                    'balance_before': str(txn.balance_before),
                    'balance_after': str(txn.balance_after),
                    'reference': txn.reference_id or '',
                })
        
        return transactions
