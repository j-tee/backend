from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.db.models import Sum, Q, Count, Avg
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.utils import timezone
from decimal import Decimal, InvalidOperation
import csv

from .models import (
    Customer, Sale, SaleItem, Payment, Refund, RefundItem,
    CreditTransaction, StockReservation, AuditLog
)
from .serializers import (
    CustomerSerializer, SaleSerializer, SaleItemSerializer,
    PaymentSerializer, RefundSerializer, RefundItemSerializer,
    CreditTransactionSerializer, AuditLogSerializer,
    AddSaleItemSerializer, CompleteSaleSerializer,
    StockAvailabilitySerializer, RecordPaymentSerializer
)
from .filters import SaleFilter
from inventory.models import StockProduct, StoreFront


class CustomerViewSet(viewsets.ModelViewSet):
    """ViewSet for Customer CRUD operations"""
    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter customers by user's business"""
        from accounts.models import BusinessMembership
        
        user = self.request.user
        membership = BusinessMembership.objects.filter(
            user=user,
            is_active=True
        ).first()
        
        if membership:
            return Customer.objects.filter(business=membership.business)
        return Customer.objects.none()
    
    def perform_create(self, serializer):
        """Set created_by to current user"""
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def credit_status(self, request, pk=None):
        """Get customer credit status"""
        customer = self.get_object()
        can_purchase, message = customer.can_purchase(Decimal('0'))
        
        return Response({
            'customer_id': customer.id,
            'customer_name': customer.name,
            'credit_limit': customer.credit_limit,
            'outstanding_balance': customer.outstanding_balance,
            'available_credit': customer.available_credit,
            'credit_terms_days': customer.credit_terms_days,
            'credit_blocked': customer.credit_blocked,
            'overdue_balance': customer.get_overdue_balance(),
            'can_purchase': can_purchase,
            'message': message
        })


class SaleViewSet(viewsets.ModelViewSet):
    """ViewSet for Sale CRUD operations with cart functionality"""
    serializer_class = SaleSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_class = SaleFilter
    filter_backends = [DjangoFilterBackend]
    
    def get_queryset(self):
        """Filter sales by user's accessible storefronts and business."""
        from accounts.models import BusinessMembership
        from datetime import timedelta
        from django.utils import timezone
        
        user = self.request.user
        queryset = Sale.objects.select_related(
            'business', 'storefront', 'user', 'customer'
        ).prefetch_related(
            'sale_items__product',
            'sale_items__product__category',
            'sale_items__stock_product',
            'payments'
        )
        
        membership = BusinessMembership.objects.filter(
            user=user,
            is_active=True
        ).first()
        
        if membership:
            # Filter by business
            queryset = queryset.filter(business=membership.business)
            
            # Apply permission-based storefront filtering
            # Get storefronts user has access to
            user_storefronts = user.get_accessible_storefronts()
            
            # Only apply storefront filter if user has accessible storefronts
            if user_storefronts.exists():
                queryset = queryset.filter(storefront__in=user_storefronts)
            else:
                # User has no accessible storefronts - return empty
                queryset = Sale.objects.none()
        else:
            queryset = Sale.objects.none()
        
        # Apply additional custom filters
        
        # Filter by days outstanding (overdue credit sales)
        days_outstanding = self.request.query_params.get('days_outstanding')
        if days_outstanding:
            try:
                days = int(days_outstanding)
                cutoff_date = timezone.now() - timedelta(days=days)
                queryset = queryset.filter(
                    payment_type='CREDIT',
                    status__in=['PENDING', 'PARTIAL'],
                    completed_at__lte=cutoff_date
                )
            except (ValueError, TypeError):
                pass
        
        # Filter by minimum amount due
        min_amount_due = self.request.query_params.get('min_amount_due')
        if min_amount_due:
            try:
                queryset = queryset.filter(amount_due__gte=Decimal(min_amount_due))
            except (ValueError, TypeError, InvalidOperation):
                pass
        
        # Filter by maximum amount due
        max_amount_due = self.request.query_params.get('max_amount_due')
        if max_amount_due:
            try:
                queryset = queryset.filter(amount_due__lte=Decimal(max_amount_due))
            except (ValueError, TypeError, InvalidOperation):
                pass
        
        # Filter by customer ID
        customer_id = self.request.query_params.get('customer_id')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
        
        # Order by most recent first (completed_at for completed, created_at for drafts)
        return queryset.order_by('-completed_at', '-created_at')
    
    @action(detail=True, methods=['post'])
    def add_item(self, request, pk=None):
        """Add item to sale (cart)"""
        sale = self.get_object()
        
        # Validate sale is in DRAFT status
        if sale.status != 'DRAFT':
            return Response(
                {'error': 'Can only add items to draft sales'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = AddSaleItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        with transaction.atomic():
            # Create stock reservation if stock_product provided
            if data.get('stock_product'):
                stock_product = data['stock_product']
                
                try:
                    reservation = StockReservation.create_reservation(
                        stock_product=stock_product,
                        quantity=data['quantity'],
                        cart_session_id=str(sale.id),
                        expiry_minutes=30
                    )
                    
                    # Log reservation
                    AuditLog.log_event(
                        event_type='stock.reserved',
                        user=request.user,
                        sale=sale,
                        event_data={
                            'stock_product_id': str(stock_product.id),
                            'quantity': str(data['quantity']),
                            'reservation_id': str(reservation.id)
                        },
                        description=f'Reserved {data["quantity"]} units of {stock_product.product.name}',
                        ip_address=request.META.get('REMOTE_ADDR'),
                        user_agent=request.META.get('HTTP_USER_AGENT')
                    )
                except Exception as e:
                    return Response(
                        {'error': str(e)},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Create sale item
            sale_item = SaleItem.objects.create(
                sale=sale,
                product=data['product'],
                stock_product=data.get('stock_product'),
                quantity=data['quantity'],
                unit_price=data['unit_price'],
                discount_percentage=data.get('discount_percentage', Decimal('0')),
                tax_rate=data.get('tax_rate', Decimal('0'))
            )
            
            # Recalculate sale totals
            sale.calculate_totals()
            sale.save()
            
            # Log item addition
            AuditLog.log_event(
                event_type='sale_item.added',
                user=request.user,
                sale=sale,
                sale_item=sale_item,
                event_data={
                    'product_id': str(data['product'].id),
                    'quantity': str(data['quantity']),
                    'unit_price': str(data['unit_price'])
                },
                description=f'Added {data["quantity"]} x {data["product"].name} to sale',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
        
        return Response(
            SaleItemSerializer(sale_item).data,
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete sale (checkout)"""
        sale = self.get_object()
        
        serializer = CompleteSaleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        with transaction.atomic():
            # Update sale fields
            sale.payment_type = data['payment_type']
            sale.discount_amount = data.get('discount_amount', Decimal('0'))
            sale.tax_amount = data.get('tax_amount', Decimal('0'))
            if data.get('notes'):
                sale.notes = data['notes']
            
            # Recalculate totals
            sale.calculate_totals()
            sale.save()
            
            # Process payments if provided
            payments_data = data.get('payments', [])
            for payment_data in payments_data:
                Payment.objects.create(
                    sale=sale,
                    customer=sale.customer,
                    amount_paid=payment_data['amount_paid'],
                    payment_method=payment_data['payment_method'],
                    status='SUCCESSFUL',
                    processed_by=request.user
                )
                sale.amount_paid += payment_data['amount_paid']
            
            # Complete the sale
            try:
                sale.complete_sale()
                
                # Log completion
                AuditLog.log_event(
                    event_type='sale.completed',
                    user=request.user,
                    sale=sale,
                    event_data={
                        'receipt_number': sale.receipt_number,
                        'total_amount': str(sale.total_amount),
                        'payment_type': sale.payment_type,
                        'status': sale.status
                    },
                    description=f'Sale {sale.receipt_number} completed',
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT')
                )
                
                return Response(
                    SaleSerializer(sale).data,
                    status=status.HTTP_200_OK
                )
            except Exception as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Get sales summary with analytics
        
        Properly separates cash accounting from accrual accounting:
        - Cash at Hand: Actual cash received (amount_paid)
        - Accounts Receivable: Credit sales not yet paid (amount_due on credit sales)
        - Total Revenue: Total sales including both cash and credit
        """
        queryset = self.filter_queryset(self.get_queryset())
        
        # Calculate aggregates
        summary = queryset.aggregate(
            # Total revenue (accrual basis - all completed sales)
            total_sales=Sum('total_amount', filter=Q(status='COMPLETED')),
            total_refunds=Sum('total_amount', filter=Q(status='REFUNDED')),
            total_transactions=Count('id'),
            completed_transactions=Count('id', filter=Q(status='COMPLETED')),
            avg_transaction=Avg('total_amount', filter=Q(status='COMPLETED')),
            
            # Cash accounting - actual cash received
            cash_at_hand=Sum('amount_paid', filter=Q(status__in=['COMPLETED', 'PARTIAL', 'PENDING'])),
            
            # Accounts receivable - money owed (credit sales not yet paid)
            accounts_receivable=Sum('amount_due', filter=Q(
                payment_type='CREDIT',
                status__in=['PENDING', 'PARTIAL']
            )),
            
            # Total credit sales amount (what customers owe)
            total_credit_sales_amount=Sum('amount_due', filter=Q(
                payment_type='CREDIT',
                status__in=['PENDING', 'PARTIAL']
            )),
            
            # Count of unpaid credit sales
            unpaid_credit_count=Count('id', filter=Q(
                payment_type='CREDIT',
                status__in=['PENDING', 'PARTIAL']
            )),
            
            # Payment method breakdown (by total sale amount)
            cash_sales=Sum('total_amount', filter=Q(payment_type='CASH', status='COMPLETED')),
            card_sales=Sum('total_amount', filter=Q(payment_type='CARD', status='COMPLETED')),
            credit_sales_total=Sum('total_amount', filter=Q(payment_type='CREDIT', status='COMPLETED')),
            mobile_sales=Sum('total_amount', filter=Q(payment_type='MOBILE', status='COMPLETED')),
            
            # Credit sales breakdown
            credit_sales_unpaid=Sum('amount_due', filter=Q(
                payment_type='CREDIT',
                status='PENDING',
                amount_paid=Decimal('0.00')
            )),
            credit_sales_partial=Sum('amount_due', filter=Q(
                payment_type='CREDIT',
                status='PARTIAL'
            )),
            credit_sales_paid=Sum('amount_paid', filter=Q(
                payment_type='CREDIT',
                status='COMPLETED'
            )),
        )
        
        # Calculate net sales (accrual basis)
        total_sales = summary['total_sales'] or Decimal('0')
        total_refunds = summary['total_refunds'] or Decimal('0')
        summary['net_sales'] = total_sales - total_refunds
        
        # Financial position breakdown
        cash_at_hand = summary['cash_at_hand'] or Decimal('0')
        accounts_receivable = summary['accounts_receivable'] or Decimal('0')
        
        summary['financial_position'] = {
            'cash_at_hand': cash_at_hand,
            'accounts_receivable': accounts_receivable,
            'total_assets': cash_at_hand + accounts_receivable,
            'cash_percentage': round(float((cash_at_hand / (cash_at_hand + accounts_receivable) * 100) if (cash_at_hand + accounts_receivable) > 0 else 0), 2),
            'receivables_percentage': round(float((accounts_receivable / (cash_at_hand + accounts_receivable) * 100) if (cash_at_hand + accounts_receivable) > 0 else 0), 2),
        }
        
        # Credit sales health metrics
        credit_sales_unpaid = summary['credit_sales_unpaid'] or Decimal('0')
        credit_sales_partial = summary['credit_sales_partial'] or Decimal('0')
        credit_sales_paid = summary['credit_sales_paid'] or Decimal('0')
        
        summary['credit_health'] = {
            'total_credit_sales': summary['credit_sales_total'] or Decimal('0'),
            'unpaid_amount': credit_sales_unpaid,
            'partially_paid_amount': credit_sales_partial,
            'fully_paid_amount': credit_sales_paid,
            'collection_rate': round(float((credit_sales_paid / summary['credit_sales_total'] * 100) if summary['credit_sales_total'] else 0), 2),
        }
        
        # Calculate profit metrics
        from django.db.models import F, Sum as SumAgg, ExpressionWrapper, DecimalField, Case, When, Value
        from django.db.models.functions import Coalesce
        
        # Total profit from all completed sales
        # Profit = (unit_price - stock_product.unit_cost) * quantity
        # Note: Using base unit_cost. For full landed cost, would need unit_cost + unit_tax_amount + unit_additional_cost
        completed_sales_ids = queryset.filter(status='COMPLETED').values_list('id', flat=True)
        
        # Calculate using stock_product__unit_cost (base cost)
        total_profit = SaleItem.objects.filter(
            sale_id__in=completed_sales_ids,
            stock_product__isnull=False
        ).aggregate(
            profit=SumAgg(
                ExpressionWrapper(
                    (F('unit_price') - F('stock_product__unit_cost')) * F('quantity'),
                    output_field=DecimalField()
                )
            )
        )['profit'] or Decimal('0')
        
        # Outstanding credit profit (profit portion from unpaid amounts on credit sales)
        # For PENDING/PARTIAL sales, calculate profit proportional to amount_due
        unpaid_credit_sales = queryset.filter(
            payment_type='CREDIT',
            status__in=['PENDING', 'PARTIAL']
        )
        
        outstanding_credit_profit = Decimal('0')
        for sale in unpaid_credit_sales:
            # Calculate total profit for this sale
            sale_profit = SaleItem.objects.filter(
                sale_id=sale.id,
                stock_product__isnull=False
            ).aggregate(
                profit=SumAgg(
                    ExpressionWrapper(
                        (F('unit_price') - F('stock_product__unit_cost')) * F('quantity'),
                        output_field=DecimalField()
                    )
                )
            )['profit'] or Decimal('0')
            
            # Calculate the profit portion that's still outstanding
            # If 40% is unpaid (amount_due/total_amount), then 40% of profit is outstanding
            if sale.total_amount > 0:
                outstanding_ratio = sale.amount_due / sale.total_amount
                outstanding_credit_profit += sale_profit * outstanding_ratio
        
        # Realized profit from credit sales (profit from amounts already paid)
        credit_sales_ids = queryset.filter(payment_type='CREDIT').values_list('id', flat=True)
        total_credit_profit = SaleItem.objects.filter(
            sale_id__in=credit_sales_ids,
            stock_product__isnull=False
        ).aggregate(
            profit=SumAgg(
                ExpressionWrapper(
                    (F('unit_price') - F('stock_product__unit_cost')) * F('quantity'),
                    output_field=DecimalField()
                )
            )
        )['profit'] or Decimal('0')
        
        realized_credit_profit = total_credit_profit - outstanding_credit_profit
        
        # Cash on hand (total profit minus outstanding credit profit)
        # This now properly includes the realized portion of credit sales profit
        cash_on_hand_profit = total_profit - outstanding_credit_profit
        
        # Add credit management metrics to summary
        summary['total_profit'] = total_profit
        summary['outstanding_credit'] = outstanding_credit_profit
        summary['realized_credit_profit'] = realized_credit_profit
        summary['cash_on_hand'] = cash_on_hand_profit
        summary['total_credit_sales'] = summary['total_credit_sales_amount'] or Decimal('0')
        summary['unpaid_credit_count'] = summary['unpaid_credit_count'] or 0
        
        # Status breakdown
        status_breakdown = queryset.values('status').annotate(
            count=Count('id'),
            total=Sum('total_amount')
        ).order_by('-count')
        
        # Daily trend (for the filtered date range)
        daily_trend = queryset.filter(
            status='COMPLETED'
        ).annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            sales=Sum('total_amount'),
            transactions=Count('id')
        ).order_by('date')[:90]  # Limit to 90 days for performance
        
        # Top customers
        top_customers = queryset.filter(
            status='COMPLETED',
            customer__isnull=False
        ).values(
            'customer__id',
            'customer__name'
        ).annotate(
            total_spent=Sum('total_amount'),
            transaction_count=Count('id')
        ).order_by('-total_spent')[:10]
        
        # Payment method breakdown
        payment_breakdown = queryset.filter(
            status='COMPLETED'
        ).values('payment_type').annotate(
            count=Count('id'),
            total=Sum('total_amount')
        ).order_by('-total')
        
        # Sale type breakdown
        type_breakdown = queryset.filter(
            status='COMPLETED'
        ).values('type').annotate(
            count=Count('id'),
            total=Sum('total_amount')
        ).order_by('-total')
        
        return Response({
            'summary': summary,
            'status_breakdown': list(status_breakdown),
            'daily_trend': list(daily_trend),
            'top_customers': list(top_customers),
            'payment_breakdown': list(payment_breakdown),
            'type_breakdown': list(type_breakdown),
        })
    
    @action(detail=False, methods=['get'])
    def export(self, request):
        """Export sales to CSV"""
        queryset = self.filter_queryset(self.get_queryset())
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="sales_export.csv"'
        
        writer = csv.writer(response)
        
        # Header
        writer.writerow([
            'Receipt Number',
            'Date',
            'Completed At',
            'Storefront',
            'Customer',
            'Customer Type',
            'Items Count',
            'Subtotal',
            'Discount',
            'Tax',
            'Total',
            'Paid',
            'Due',
            'Payment Type',
            'Status',
            'Cashier',
            'Notes'
        ])
        
        # Data rows
        for sale in queryset.select_related('storefront', 'customer', 'user').prefetch_related('sale_items'):
            writer.writerow([
                sale.receipt_number or '',
                sale.created_at.strftime('%Y-%m-%d %H:%M') if sale.created_at else '',
                sale.completed_at.strftime('%Y-%m-%d %H:%M') if sale.completed_at else '',
                sale.storefront.name if sale.storefront else '',
                sale.customer.name if sale.customer else 'Walk-in',
                sale.type,
                sale.sale_items.count(),
                float(sale.subtotal),
                float(sale.discount_amount),
                float(sale.tax_amount),
                float(sale.total_amount),
                float(sale.amount_paid),
                float(sale.amount_due),
                sale.payment_type,
                sale.status,
                sale.user.name if sale.user else '',
                sale.notes or ''
            ])
        
        return response
    
    @action(detail=True, methods=['post'])
    def record_payment(self, request, pk=None):
        """
        Record a payment against a sale
        
        POST /sales/api/sales/{sale_id}/record_payment/
        Body:
        {
            "amount_paid": "100.00",
            "payment_method": "CASH",
            "reference_number": "TXN12345",
            "notes": "First installment"
        }
        """
        sale = self.get_object()
        
        serializer = RecordPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        with transaction.atomic():
            # Validate sale has customer for credit tracking
            if not sale.customer:
                return Response(
                    {'error': 'Cannot record payment for sale without customer'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate payment amount
            if data['amount_paid'] > sale.amount_due:
                return Response(
                    {
                        'error': f'Payment amount ({data["amount_paid"]}) exceeds amount due ({sale.amount_due})',
                        'amount_due': str(sale.amount_due),
                        'amount_paid_requested': str(data["amount_paid"])
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate sale isn't already fully paid
            if sale.amount_due == Decimal('0.00'):
                return Response(
                    {'error': 'Sale is already fully paid'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create payment record
            payment = Payment.objects.create(
                sale=sale,
                customer=sale.customer,
                amount_paid=data['amount_paid'],
                payment_method=data['payment_method'],
                reference_number=data.get('reference_number', ''),
                notes=data.get('notes', ''),
                status='SUCCESSFUL',
                processed_by=request.user
            )
            
            # Update sale amounts
            sale.amount_paid += data['amount_paid']
            sale.amount_due = sale.total_amount - sale.amount_paid
            if sale.amount_due < Decimal('0.00'):
                sale.amount_due = Decimal('0.00')
            
            # Update sale status based on payment
            if sale.amount_due == Decimal('0.00'):
                sale.status = 'COMPLETED'
            elif sale.amount_paid > Decimal('0.00'):
                sale.status = 'PARTIAL'
            
            sale.save()
            
            # Update customer balance
            sale.customer.outstanding_balance -= data['amount_paid']
            if sale.customer.outstanding_balance < Decimal('0.00'):
                sale.customer.outstanding_balance = Decimal('0.00')
            sale.customer.save()
            
            # Log payment
            AuditLog.log_event(
                event_type='payment.recorded',
                user=request.user,
                sale=sale,
                event_data={
                    'payment_id': str(payment.id),
                    'amount': str(payment.amount_paid),
                    'method': payment.payment_method,
                    'new_balance_due': str(sale.amount_due),
                    'new_status': sale.status
                },
                description=f'Payment of {payment.amount_paid} recorded for sale {sale.receipt_number}',
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            return Response({
                'message': 'Payment recorded successfully',
                'payment': PaymentSerializer(payment).data,
                'sale': SaleSerializer(sale).data
            })


class SaleItemViewSet(viewsets.ModelViewSet):
    """ViewSet for SaleItem operations"""
    serializer_class = SaleItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter sale items"""
        from accounts.models import BusinessMembership
        
        user = self.request.user
        queryset = SaleItem.objects.select_related('sale', 'product', 'stock_product')
        
        membership = BusinessMembership.objects.filter(
            user=user,
            is_active=True
        ).first()
        
        if membership:
            queryset = queryset.filter(sale__business=membership.business)
        else:
            queryset = SaleItem.objects.none()
        
        # Filter by sale
        sale_filter = self.request.query_params.get('sale')
        if sale_filter:
            queryset = queryset.filter(sale_id=sale_filter)
        
        return queryset


class PaymentViewSet(viewsets.ModelViewSet):
    """ViewSet for Payment operations"""
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter payments"""
        from accounts.models import BusinessMembership
        
        user = self.request.user
        queryset = Payment.objects.select_related('sale', 'customer')
        
        membership = BusinessMembership.objects.filter(
            user=user,
            is_active=True
        ).first()
        
        if membership:
            queryset = queryset.filter(sale__business=membership.business)
        else:
            queryset = Payment.objects.none()
        
        return queryset.order_by('-payment_date')


class RefundViewSet(viewsets.ModelViewSet):
    """ViewSet for Refund operations"""
    serializer_class = RefundSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter refunds"""
        from accounts.models import BusinessMembership
        
        user = self.request.user
        queryset = Refund.objects.select_related('sale')
        
        membership = BusinessMembership.objects.filter(
            user=user,
            is_active=True
        ).first()
        
        if membership:
            queryset = queryset.filter(sale__business=membership.business)
        else:
            queryset = Refund.objects.none()
        
        return queryset.order_by('-created_at')


class CreditTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for CreditTransaction (read-only)"""
    serializer_class = CreditTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter credit transactions"""
        from accounts.models import BusinessMembership
        
        user = self.request.user
        queryset = CreditTransaction.objects.select_related('customer')
        
        membership = BusinessMembership.objects.filter(
            user=user,
            is_active=True
        ).first()
        
        if membership:
            queryset = queryset.filter(customer__business=membership.business)
        else:
            queryset = CreditTransaction.objects.none()
        
        # Filter by customer
        customer_filter = self.request.query_params.get('customer')
        if customer_filter:
            queryset = queryset.filter(customer_id=customer_filter)
        
        return queryset.order_by('-created_at')


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for AuditLog (read-only)"""
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter audit logs"""
        from accounts.models import BusinessMembership
        
        user = self.request.user
        queryset = AuditLog.objects.select_related('user', 'sale', 'customer')
        
        membership = BusinessMembership.objects.filter(
            user=user,
            is_active=True
        ).first()
        
        if membership:
            queryset = queryset.filter(
                Q(sale__business=membership.business) |
                Q(customer__business=membership.business)
            )
        else:
            queryset = AuditLog.objects.none()
        
        # Filter by event type
        event_type_filter = self.request.query_params.get('event_type')
        if event_type_filter:
            queryset = queryset.filter(event_type=event_type_filter)
        
        # Filter by sale
        sale_filter = self.request.query_params.get('sale')
        if sale_filter:
            queryset = queryset.filter(sale_id=sale_filter)
        
        return queryset.order_by('-timestamp')
