from collections import defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db import transaction
from django.db.models import Sum, Q, Count, Avg
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
import csv
from django.core.exceptions import ValidationError

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
                except ValidationError as exc:
                    error_details = getattr(exc, 'params', {}) or {}
                    developer_message = getattr(exc, 'message', None) or str(exc)
                    return Response(
                        {
                            'error': 'Unable to add item due to stock restrictions.',
                            'code': 'INSUFFICIENT_STOCK',
                            'developer_message': developer_message,
                            'details': error_details,
                        },
                        status=status.HTTP_400_BAD_REQUEST
                    )
                except Exception as exc:
                    return Response(
                        {
                            'error': 'Unable to add item at this time.',
                            'code': 'ADD_ITEM_ERROR',
                            'developer_message': str(exc),
                            'details': {},
                        },
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
    def abandon(self, request, pk=None):
        """Cancel a draft sale and release any active stock reservations."""
        sale = self.get_object()
        allowed_statuses = {'DRAFT', 'CANCELLED'}

        with transaction.atomic():
            sale.refresh_from_db()

            original_status = sale.status
            already_finalized = original_status not in allowed_statuses

            active_reservations = list(
                StockReservation.objects.select_for_update()
                .filter(
                    cart_session_id=str(sale.id),
                    status='ACTIVE'
                )
                .select_related('stock_product__product')
            )

            released_payload = []
            total_released = Decimal('0.00')
            now = timezone.now()

            for reservation in active_reservations:
                quantity = Decimal(reservation.quantity)
                total_released += quantity
                released_payload.append({
                    'reservation_id': str(reservation.id),
                    'stock_product_id': str(reservation.stock_product_id),
                    'product_id': str(reservation.stock_product.product_id),
                    'product_name': reservation.stock_product.product.name if reservation.stock_product and reservation.stock_product.product else None,
                    'quantity': str(quantity),
                    'expires_at': reservation.expires_at.isoformat() if reservation.expires_at else None,
                })

            if active_reservations:
                reservation_ids = [reservation.id for reservation in active_reservations]
                StockReservation.objects.filter(id__in=reservation_ids).update(
                    status='RELEASED',
                    released_at=now
                )

            status_changed = False
            if not already_finalized and sale.status != 'CANCELLED':
                sale.status = 'CANCELLED'
                sale.completed_at = None
                sale.save(update_fields=['status', 'completed_at', 'updated_at'])
                status_changed = True

                AuditLog.log_event(
                    event_type='sale.cancelled',
                    user=request.user,
                    sale=sale,
                    event_data={
                        'released_reservation_count': len(released_payload),
                        'released_quantity': str(total_released),
                    },
                    description=f'Sale {sale.id} cancelled and reservations released',
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT')
                )

        sale_data = SaleSerializer(sale, context={'request': request}).data

        if already_finalized:
            message = 'Sale already finalized; no status change applied.'
        elif status_changed:
            message = 'Sale cancelled and reservations released.'
        else:
            message = 'Sale already cancelled; reservations released if any.'

        return Response({
            'message': message,
            'sale': sale_data,
            'released': {
                'count': len(released_payload),
                'total_quantity': str(total_released),
                'reservations': released_payload,
            },
            'current_status': original_status,
            'status_changed': status_changed,
            'already_finalized': already_finalized,
        })
    
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

            # Recalculate totals after payments have been applied
            sale.calculate_totals()
            sale.save()

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
        two_places = Decimal('0.01')

        def to_decimal(value):
            if value is None:
                return Decimal('0.00')
            if isinstance(value, Decimal):
                return value
            try:
                return Decimal(str(value))
            except (InvalidOperation, TypeError):
                return Decimal('0.00')

        def to_money(value):
            return float(to_decimal(value).quantize(two_places, rounding=ROUND_HALF_UP))
        
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
        
        # Prepare sale and sale-item level analytics for profitability and credit tracking
        analysed_sales = queryset.exclude(status='DRAFT')
        sale_ids = list(analysed_sales.values_list('id', flat=True))
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

        sale_costs = defaultdict(lambda: Decimal('0.00'))
        sale_line_tax = defaultdict(lambda: Decimal('0.00'))
        sale_line_discount = defaultdict(lambda: Decimal('0.00'))

        for item in sale_items:
            quantity = to_decimal(item.quantity)
            stock_product = item.stock_product or fallback_stock.get(item.product_id)
            if stock_product:
                unit_cost = (
                    to_decimal(stock_product.unit_cost)
                    + to_decimal(getattr(stock_product, 'unit_tax_amount', None))
                    + to_decimal(getattr(stock_product, 'unit_additional_cost', None))
                )
            else:
                unit_cost = to_decimal(item.product.get_latest_cost())

            sale_costs[item.sale_id] += (unit_cost * quantity)
            sale_line_tax[item.sale_id] += to_decimal(item.tax_amount)
            sale_line_discount[item.sale_id] += to_decimal(item.discount_amount)

        total_sales_completed = Decimal('0.00')
        total_cogs_completed = Decimal('0.00')
        total_tax_completed = Decimal('0.00')
        total_discounts_completed = Decimal('0.00')
        gross_profit_completed = Decimal('0.00')

        total_sales_all = Decimal('0.00')
        total_tax_all = Decimal('0.00')
        total_cogs_all = Decimal('0.00')
        total_discounts_all = Decimal('0.00')
        gross_profit_all = Decimal('0.00')

        realized_revenue_total = Decimal('0.00')
        outstanding_revenue_total = Decimal('0.00')
        realized_profit_total = Decimal('0.00')
        outstanding_profit_total = Decimal('0.00')

        credit_total_amount = Decimal('0.00')
        credit_total_completed = Decimal('0.00')
        credit_amount_paid_total = Decimal('0.00')
        credit_amount_due_total = Decimal('0.00')
        credit_amount_due_partial = Decimal('0.00')
        credit_amount_due_pending = Decimal('0.00')
        credit_paid_completed = Decimal('0.00')
        credit_realized_profit = Decimal('0.00')
        credit_outstanding_profit = Decimal('0.00')

        for sale in analysed_sales:
            total_amount = to_decimal(sale.total_amount)
            paid = to_decimal(sale.amount_paid)
            due = to_decimal(sale.amount_due)
            sale_tax_total = sale_line_tax[sale.id] + to_decimal(sale.tax_amount)
            sale_discount_total = sale_line_discount[sale.id] + to_decimal(sale.discount_amount)
            cogs = sale_costs[sale.id]
            net_revenue = total_amount - sale_tax_total
            profit = net_revenue - cogs

            total_sales_all += total_amount
            total_tax_all += sale_tax_total
            total_cogs_all += cogs
            total_discounts_all += sale_discount_total
            gross_profit_all += profit

            denominator = total_amount if total_amount > Decimal('0.00') else (paid + due)
            paid_ratio = (paid / denominator) if denominator > Decimal('0.00') else Decimal('0.00')
            if paid_ratio > Decimal('1.00'):
                paid_ratio = Decimal('1.00')

            realized_profit = (profit * paid_ratio)
            outstanding_profit = profit - realized_profit
            if outstanding_profit < Decimal('0.00'):
                outstanding_profit = Decimal('0.00')

            realized_revenue_total += paid
            realized_profit_total += realized_profit
            outstanding_profit_total += outstanding_profit

            if sale.payment_type == 'CREDIT':
                outstanding_revenue_total += due
                credit_total_amount += total_amount
                credit_amount_paid_total += paid
                credit_amount_due_total += due
                credit_realized_profit += realized_profit
                credit_outstanding_profit += outstanding_profit

                if sale.status == 'COMPLETED':
                    credit_total_completed += total_amount
                    credit_paid_completed += paid
                elif sale.status == 'PARTIAL':
                    credit_amount_due_partial += due
                elif sale.status == 'PENDING':
                    credit_amount_due_pending += due

            if sale.status == 'COMPLETED':
                total_sales_completed += total_amount
                total_cogs_completed += cogs
                total_tax_completed += sale_tax_total
                total_discounts_completed += sale_discount_total
                gross_profit_completed += profit

        net_sales_completed = total_sales_completed - total_tax_completed
        summary['net_sales'] = to_money(net_sales_completed)

        summary['total_sales'] = to_money(total_sales_completed)
        summary['total_sales_all_statuses'] = to_money(total_sales_all)
        summary['total_cogs'] = to_money(total_cogs_completed)
        summary['total_cogs_all_statuses'] = to_money(total_cogs_all)
        summary['total_tax_collected'] = to_money(total_tax_completed)
        summary['total_tax_all_statuses'] = to_money(total_tax_all)
        summary['total_discounts'] = to_money(total_discounts_completed)
        summary['total_discounts_all_statuses'] = to_money(total_discounts_all)

        summary['total_profit'] = to_money(gross_profit_completed)
        summary['gross_profit_all_statuses'] = to_money(gross_profit_all)
        profit_margin = (gross_profit_completed / net_sales_completed * Decimal('100.00')) if net_sales_completed > Decimal('0.00') else Decimal('0.00')
        summary['profit_margin'] = round(float(profit_margin), 2)

        summary['realized_revenue'] = to_money(realized_revenue_total)
        summary['outstanding_revenue'] = to_money(outstanding_revenue_total)
        summary['realized_profit'] = to_money(realized_profit_total)
        summary['outstanding_profit'] = to_money(outstanding_profit_total)

        # Refresh cash/receivables snapshot
        summary['cash_at_hand'] = to_money(realized_revenue_total)
        summary['accounts_receivable'] = to_money(outstanding_revenue_total)

        total_assets = realized_revenue_total + outstanding_revenue_total
        summary['financial_position'] = {
            'cash_at_hand': to_money(realized_revenue_total),
            'accounts_receivable': to_money(outstanding_revenue_total),
            'total_assets': to_money(total_assets),
            'cash_percentage': round(float((realized_revenue_total / total_assets * Decimal('100.00')) if total_assets > Decimal('0.00') else Decimal('0.00')), 2),
            'receivables_percentage': round(float((outstanding_revenue_total / total_assets * Decimal('100.00')) if total_assets > Decimal('0.00') else Decimal('0.00')), 2),
        }

        summary['total_credit_sales'] = to_money(credit_total_amount)
        summary['unpaid_credit_count'] = summary['unpaid_credit_count'] or 0
        summary['credit_health'] = {
            'total_credit_sales': to_money(credit_total_amount),
            'completed_credit_sales': to_money(credit_total_completed),
            'amount_paid': to_money(credit_amount_paid_total),
            'amount_due': to_money(credit_amount_due_total),
            'unpaid_amount': to_money(credit_amount_due_pending),
            'partially_paid_amount': to_money(credit_amount_due_partial),
            'fully_paid_amount': to_money(credit_paid_completed),
            'realized_profit': to_money(credit_realized_profit),
            'outstanding_profit': to_money(credit_outstanding_profit),
            'collection_rate': round(float((credit_paid_completed / credit_total_completed * Decimal('100.00')) if credit_total_completed > Decimal('0.00') else Decimal('0.00')), 2),
        }

        summary['realized_credit_profit'] = to_money(credit_realized_profit)
        summary['outstanding_credit'] = to_money(credit_outstanding_profit)
        summary['cash_on_hand'] = to_money(realized_profit_total)

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

    @action(detail=False, methods=['get'], url_path='todays-stats')
    def todays_stats(self, request):
        """Return lightweight metrics for the Today's Stats widget."""
        base_queryset = self.get_queryset()

        date_param = request.query_params.get('date')
        parsed_date = parse_date(date_param) if date_param else None
        target_date = parsed_date or timezone.localdate()

        start_of_day = datetime.combine(target_date, time.min)
        end_of_day = start_of_day + timedelta(days=1)
        if timezone.is_naive(start_of_day):
            tz = timezone.get_current_timezone()
            start_of_day = timezone.make_aware(start_of_day, tz)
            end_of_day = timezone.make_aware(end_of_day, tz)

        date_scoped_queryset = base_queryset.filter(
            created_at__gte=start_of_day,
            created_at__lt=end_of_day
        )

        storefront_id = request.query_params.get('storefront')
        if storefront_id:
            date_scoped_queryset = date_scoped_queryset.filter(storefront__id=storefront_id)

        requested_statuses = request.query_params.getlist('status')
        valid_statuses = [choice[0] for choice in Sale.STATUS_CHOICES]
        statuses = [status for status in requested_statuses if status in valid_statuses]
        if not statuses:
            statuses = ['COMPLETED']

        status_queryset = date_scoped_queryset.filter(status__in=statuses)

        two_places = Decimal('0.01')

        def to_decimal(value):
            if value is None:
                return Decimal('0.00')
            if isinstance(value, Decimal):
                return value
            try:
                return Decimal(str(value))
            except (InvalidOperation, TypeError):
                return Decimal('0.00')

        def to_money(value):
            return float(to_decimal(value).quantize(two_places, rounding=ROUND_HALF_UP))

        aggregates = status_queryset.aggregate(
            total_sales=Sum('total_amount'),
            avg_transaction=Avg('total_amount')
        )

        transactions = status_queryset.count()
        total_sales = to_money(aggregates['total_sales'])
        avg_transaction = to_money(aggregates['avg_transaction']) if aggregates['avg_transaction'] is not None else 0.0

        cash_snapshot = date_scoped_queryset.aggregate(
            cash_at_hand=Sum('amount_paid', filter=Q(status__in=['COMPLETED', 'PARTIAL', 'PENDING'])),
            accounts_receivable=Sum('amount_due', filter=Q(payment_type='CREDIT', status__in=['PENDING', 'PARTIAL']))
        )

        cash_at_hand = to_money(cash_snapshot['cash_at_hand'])
        accounts_receivable = to_money(cash_snapshot['accounts_receivable'])

        partial_transactions = date_scoped_queryset.filter(status='PARTIAL').count()
        pending_transactions = date_scoped_queryset.filter(status='PENDING').count()

        status_breakdown = [
            {
                'status': item['status'],
                'count': item['count'],
                'total': to_money(item['total'])
            }
            for item in date_scoped_queryset.values('status').annotate(
                count=Count('id'),
                total=Sum('total_amount')
            ).order_by('-count')
        ]

        payment_breakdown = [
            {
                'payment_type': item['payment_type'],
                'count': item['count'],
                'total': to_money(item['total'])
            }
            for item in status_queryset.values('payment_type').annotate(
                count=Count('id'),
                total=Sum('total_amount')
            ).order_by('-total')
        ]

        credit_scope = date_scoped_queryset.filter(payment_type='CREDIT')
        credit_totals = credit_scope.aggregate(
            total_credit_sales=Sum('total_amount', filter=Q(status__in=statuses)),
            amount_paid=Sum('amount_paid'),
            outstanding_amount=Sum('amount_due', filter=Q(status__in=['PENDING', 'PARTIAL']))
        )

        credit_snapshot = {
            'total_credit_sales': to_money(credit_totals['total_credit_sales']),
            'amount_paid': to_money(credit_totals['amount_paid']),
            'outstanding_amount': to_money(credit_totals['outstanding_amount'])
        }

        return Response({
            'date': target_date.isoformat(),
            'storefront': storefront_id,
            'statuses': statuses,
            'transactions': transactions,
            'total_sales': total_sales,
            'avg_transaction': avg_transaction,
            'cash_at_hand': cash_at_hand,
            'accounts_receivable': accounts_receivable,
            'partial_transactions': partial_transactions,
            'pending_transactions': pending_transactions,
            'status_breakdown': status_breakdown,
            'payment_breakdown': payment_breakdown,
            'credit_snapshot': credit_snapshot
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
