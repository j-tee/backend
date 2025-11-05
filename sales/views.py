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

# Subscription enforcement
from subscriptions.permissions import RequiresActiveSubscription, RequiresSubscriptionForExports

from .models import (
    Customer, Sale, SaleItem, Payment, Refund, RefundItem,
    CreditTransaction, StockReservation, AuditLog,
    AccountsReceivable, ARPayment  # NEW: AR system models
)
from .serializers import (
    CustomerSerializer, SaleSerializer, SaleItemSerializer,
    PaymentSerializer, RefundSerializer, RefundItemSerializer,
    CreditTransactionSerializer, AuditLogSerializer,
    AddSaleItemSerializer, CompleteSaleSerializer,
    StockAvailabilitySerializer, RecordPaymentSerializer,
    SaleRefundSerializer
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
    
    def create(self, request, *args, **kwargs):
        """
        Create customer, or return existing one if unique constraint violated.
        This handles the walk-in customer case where we try to create it on every page load.
        """
        from django.db import IntegrityError
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        business = serializer.validated_data.get('business')
        phone = serializer.validated_data.get('phone')
        
        # If both business and phone are provided, check if customer already exists
        if business and phone:
            existing_customer = Customer.objects.filter(
                business=business,
                phone=phone
            ).first()
            
            if existing_customer:
                # Return existing customer with 200 OK
                response_serializer = self.get_serializer(existing_customer)
                return Response(response_serializer.data, status=status.HTTP_200_OK)
        
        # Try to create new customer
        try:
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        except IntegrityError as e:
            # If unique constraint violated, try to find and return existing customer
            if business and phone:
                existing_customer = Customer.objects.filter(
                    business=business,
                    phone=phone
                ).first()
                
                if existing_customer:
                    response_serializer = self.get_serializer(existing_customer)
                    return Response(response_serializer.data, status=status.HTTP_200_OK)
            
            # If still not found, raise the original error
            raise
    
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
    permission_classes = [permissions.IsAuthenticated, RequiresActiveSubscription]
    filterset_class = SaleFilter
    filter_backends = [DjangoFilterBackend]
    
    def get_permissions(self):
        """
        Use different permissions for export action.
        """
        if self.action == 'export':
            return [permissions.IsAuthenticated(), RequiresSubscriptionForExports()]
        return super().get_permissions()
    
    def perform_create(self, serializer):
        """
        Auto-assign walk-in customer if no customer is provided.
        Walk-in customers are guaranteed to exist (created when business is created).
        """
        from accounts.models import BusinessMembership
        
        customer = serializer.validated_data.get('customer')
        
        # If no customer provided, use walk-in customer
        if not customer:
            user = self.request.user
            membership = BusinessMembership.objects.filter(
                user=user,
                is_active=True
            ).first()
            
            if membership:
                # Get walk-in customer for this business
                WALK_IN_PHONE = '+233000000000'
                walk_in_customer = Customer.objects.filter(
                    business=membership.business,
                    phone=WALK_IN_PHONE
                ).first()
                
                if walk_in_customer:
                    serializer.validated_data['customer'] = walk_in_customer
        
        serializer.save(user=self.request.user)
    
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
        
        # Pass sale in context for storefront inventory validation
        serializer = AddSaleItemSerializer(data=request.data, context={'sale': sale})
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
                # Balance the equation: total_amount = amount_paid + amount_due
                # For cancelled sales: set amount_paid = total_amount and amount_due = 0
                sale.amount_paid = sale.total_amount
                sale.amount_due = Decimal('0')
                sale.save(update_fields=['status', 'completed_at', 'amount_paid', 'amount_due', 'updated_at'])
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
    def toggle_sale_type(self, request, pk=None):
        """
        Toggle sale type between RETAIL and WHOLESALE.
        Updates all sale items to use the appropriate pricing.
        Can only be done for DRAFT sales.
        """
        sale = self.get_object()
        
        # Validate sale is in DRAFT status
        if sale.status != 'DRAFT':
            return Response(
                {'error': 'Can only change sale type for draft sales'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get new type from request, or toggle automatically
        new_type = request.data.get('type')
        if new_type:
            if new_type not in ['RETAIL', 'WHOLESALE']:
                return Response(
                    {'error': 'Invalid sale type. Must be RETAIL or WHOLESALE'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            # Toggle: RETAIL -> WHOLESALE, WHOLESALE -> RETAIL
            new_type = 'WHOLESALE' if sale.type == 'RETAIL' else 'RETAIL'
        
        # If already the requested type, no changes needed
        if sale.type == new_type:
            return Response({
                'message': f'Sale already set to {new_type}',
                'sale': SaleSerializer(sale).data
            })
        
        old_type = sale.type
        
        with transaction.atomic():
            # Update sale type
            sale.type = new_type
            sale.save()
            
            # Update all sale items with new pricing
            updated_items = []
            for item in sale.sale_items.all():
                # Get stock product for this item
                stock_product = item.stock_product
                if not stock_product:
                    # Try to find latest stock product for the product
                    stock_product = StockProduct.objects.filter(
                        product=item.product
                    ).order_by('-created_at').first()
                
                if stock_product:
                    # Determine new price based on new sale type
                    if new_type == 'WHOLESALE':
                        if stock_product.wholesale_price and stock_product.wholesale_price > Decimal('0'):
                            new_price = stock_product.wholesale_price
                        else:
                            # Fallback to retail if wholesale not set
                            new_price = stock_product.retail_price
                    else:  # RETAIL
                        new_price = stock_product.retail_price
                    
                    # Update item price
                    old_price = item.unit_price
                    item.unit_price = new_price
                    item.save()
                    
                    updated_items.append({
                        'product_name': item.product.name,
                        'old_price': str(old_price),
                        'new_price': str(new_price)
                    })
            
            # Recalculate sale totals
            sale.calculate_totals()
            sale.save()
            
            # Log the change
            AuditLog.log_event(
                event_type='sale.type_changed',
                user=request.user,
                sale=sale,
                event_data={
                    'old_type': old_type,
                    'new_type': new_type,
                    'items_updated': len(updated_items),
                    'updated_items': updated_items
                },
                description=f'Sale type changed from {old_type} to {new_type}',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
        
        return Response({
            'message': f'Sale type changed from {old_type} to {new_type}',
            'sale': SaleSerializer(sale).data,
            'updated_items': updated_items
        })
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """
        Complete sale - routes to either payment flow or credit flow.
        
        Payment Flow (is_credit_sale=False):
            - Creates Payment records
            - Processes actual payments
            - Completes sale immediately if fully paid
        
        Credit Flow (is_credit_sale=True):
            - Creates AccountsReceivable record
            - Updates customer credit balance
            - Sale remains PENDING until payments received
        """
        sale = self.get_object()
        
        serializer = CompleteSaleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        
        # Determine if this is a credit sale
        is_credit = data.get('payment_type') == 'CREDIT'
        
        # Route to appropriate flow
        if is_credit:
            return self._complete_credit_sale(sale, request, data)
        else:
            return self._complete_payment_sale(sale, request, data)
    
    def _complete_payment_sale(self, sale, request, data):
        """
        PAYMENT FLOW - for cash/card/mobile sales.
        Creates Payment records and completes sale.
        """
        with transaction.atomic():
            # Update sale fields
            sale.payment_type = data['payment_type']
            sale.discount_amount = data.get('discount_amount', Decimal('0'))
            sale.tax_amount = data.get('tax_amount', Decimal('0'))
            sale.is_credit_sale = False  # Mark as payment sale
            if data.get('notes'):
                sale.notes = data['notes']
            
            # Validate payments exist for non-credit sales
            payments_data = data.get('payments', [])
            if not payments_data:
                return Response(
                    {'error': 'Payment sales must have payment records'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create Payment records
            total_paid = Decimal('0.00')
            for payment_data in payments_data:
                Payment.objects.create(
                    sale=sale,
                    customer=sale.customer,
                    amount_paid=payment_data['amount_paid'],
                    payment_method=payment_data['payment_method'],
                    status='SUCCESSFUL',
                    processed_by=request.user
                )
                total_paid += payment_data['amount_paid']
            
            sale.amount_paid = total_paid
            
            # Recalculate totals
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
                        'status': sale.status,
                        'flow': 'payment'
                    },
                    description=f'Sale {sale.receipt_number} completed via payment flow',
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
    
    def _complete_credit_sale(self, sale, request, data):
        """
        CREDIT FLOW - for AR sales.
        Creates AccountsReceivable record instead of Payment records.
        """
        with transaction.atomic():
            # Update sale fields
            sale.payment_type = 'CREDIT'
            sale.discount_amount = data.get('discount_amount', Decimal('0'))
            sale.tax_amount = data.get('tax_amount', Decimal('0'))
            sale.is_credit_sale = True  # Mark as credit sale
            sale.amount_paid = Decimal('0.00')  # No payment yet
            if data.get('notes'):
                sale.notes = data['notes']
            
            # Recalculate totals
            sale.calculate_totals()
            
            # Set amount_due to total (nothing paid yet)
            sale.amount_due = sale.total_amount
            sale.save()
            
            # Complete the sale (commits stock, generates receipt number)
            try:
                # Validate sale can be completed
                if sale.status != 'DRAFT':
                    raise ValidationError(f"Cannot complete sale with status {sale.status}")
                
                if not sale.sale_items.exists():
                    raise ValidationError("Cannot complete sale without items")
                
                # Generate receipt number if not set
                if not sale.receipt_number:
                    sale.receipt_number = sale.generate_receipt_number()
                
                # Commit stock
                sale.commit_stock()
                
                # Release reservations
                sale.release_reservations(delete=True)
                sale.cart_session_id = None
                
                # Set status to PENDING (awaiting payment)
                sale.status = 'PENDING'
                sale.completed_at = timezone.now()
                sale.save()
                
                # Get customer's old balance for audit trail
                old_balance = sale.customer.outstanding_balance if sale.customer else Decimal('0.00')
                
                # Create AR record
                due_date = data.get('due_date')  # Optional expected payment date
                
                ar = AccountsReceivable.objects.create(
                    sale=sale,
                    customer=sale.customer,
                    original_amount=sale.total_amount,
                    amount_paid=Decimal('0.00'),
                    amount_outstanding=sale.total_amount,
                    due_date=due_date,
                    created_by=request.user,
                    notes=data.get('ar_notes', '')
                )
                
                # Update customer balance
                if sale.customer:
                    sale.customer.outstanding_balance += sale.total_amount
                    sale.customer.save()
                    
                    # Create audit trail
                    CreditTransaction.objects.create(
                        customer=sale.customer,
                        transaction_type='CREDIT_SALE',
                        amount=sale.total_amount,
                        balance_before=old_balance,
                        balance_after=sale.customer.outstanding_balance,
                        reference_id=ar.id,  # Link to AR record
                        description=f'Credit sale {sale.receipt_number}',
                        created_by=request.user
                    )
                
                # Log completion
                AuditLog.log_event(
                    event_type='sale.completed',
                    user=request.user,
                    sale=sale,
                    event_data={
                        'receipt_number': sale.receipt_number,
                        'total_amount': str(sale.total_amount),
                        'payment_type': 'CREDIT',
                        'status': sale.status,
                        'flow': 'credit',
                        'ar_id': str(ar.id),
                        'amount_due': str(ar.amount_outstanding)
                    },
                    description=f'Credit sale {sale.receipt_number} completed via AR flow',
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT')
                )
                
                # Return sale data with AR info
                response_data = SaleSerializer(sale).data
                response_data['ar'] = {
                    'id': str(ar.id),
                    'amount_outstanding': str(ar.amount_outstanding),
                    'due_date': ar.due_date.isoformat() if ar.due_date else None,
                    'status': ar.status,
                    'aging_category': ar.aging_category
                }
                
                return Response(
                    response_data,
                    status=status.HTTP_200_OK
                )
                
            except Exception as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
    
    @action(detail=True, methods=['post'], url_path='ar-payment')
    def record_ar_payment(self, request, pk=None):
        """
        Record payment against credit sale AR.
        
        This endpoint is for recording payments when a customer pays back
        their credit. It creates an ARPayment record (not a Payment record)
        and automatically updates:
        - AR amounts and status
        - Customer outstanding balance
        - Sale amount_paid/amount_due/status
        - CreditTransaction audit trail
        
        Request body:
            {
                "amount": "500.00",
                "payment_method": "CASH" | "MOMO" | "CARD" | "BANK_TRANSFER" | "CHECK",
                "transaction_id": "optional_external_id",
                "reference_number": "optional_reference",
                "notes": "optional_notes"
            }
        """
        sale = self.get_object()
        
        # Validate it's a credit sale
        if not sale.is_credit_sale:
            return Response(
                {'error': 'This is not a credit sale. Use regular payment recording.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get AR record
        try:
            ar = sale.accounts_receivable
        except AccountsReceivable.DoesNotExist:
            return Response(
                {'error': 'AR record not found for this credit sale'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Validate AR not already fully paid
        if ar.status == 'PAID':
            return Response(
                {'error': 'AR is already fully paid'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get and validate payment data
        try:
            amount = Decimal(str(request.data.get('amount', '0')))
        except (InvalidOperation, ValueError):
            return Response(
                {'error': 'Invalid amount format'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        payment_method = request.data.get('payment_method')
        
        # Validate amount
        if amount <= 0:
            return Response(
                {'error': 'Payment amount must be greater than zero'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if amount > ar.amount_outstanding:
            return Response(
                {
                    'error': f'Payment amount ({amount}) exceeds outstanding balance ({ar.amount_outstanding})',
                    'amount': str(amount),
                    'outstanding': str(ar.amount_outstanding)
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate payment method
        valid_methods = ['CASH', 'MOMO', 'CARD', 'BANK_TRANSFER', 'CHECK']
        if payment_method not in valid_methods:
            return Response(
                {
                    'error': f'Invalid payment method. Must be one of: {", ".join(valid_methods)}',
                    'valid_methods': valid_methods
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Process the payment
        with transaction.atomic():
            # Get customer's old balance for audit
            old_balance = sale.customer.outstanding_balance if sale.customer else Decimal('0.00')
            
            # Create AR Payment (NOT regular Payment model!)
            ar_payment = ARPayment.objects.create(
                accounts_receivable=ar,
                amount=amount,
                payment_method=payment_method,
                transaction_id=request.data.get('transaction_id', ''),
                reference_number=request.data.get('reference_number', ''),
                received_by=request.user,
                notes=request.data.get('notes', '')
            )
            
            # ARPayment.save() automatically updates:
            # - AR.amount_paid (sum of all ar_payments)
            # - AR.amount_outstanding
            # - AR.status (PENDING → PARTIAL → PAID)
            # - Customer.outstanding_balance
            # - Sale.amount_paid/amount_due/status
            
            # Refresh to get updated values
            ar.refresh_from_db()
            sale.refresh_from_db()
            if sale.customer:
                sale.customer.refresh_from_db()
            
            # Create audit trail
            if sale.customer:
                CreditTransaction.objects.create(
                    customer=sale.customer,
                    transaction_type='PAYMENT',
                    amount=-amount,  # Negative because reducing balance
                    balance_before=old_balance,
                    balance_after=sale.customer.outstanding_balance,
                    reference_id=ar_payment.id,
                    description=f'AR payment for {sale.receipt_number} via {payment_method}',
                    created_by=request.user
                )
            
            # Log the payment
            AuditLog.log_event(
                event_type='payment.recorded',
                user=request.user,
                sale=sale,
                customer=sale.customer,
                event_data={
                    'ar_payment_id': str(ar_payment.id),
                    'amount': str(amount),
                    'payment_method': payment_method,
                    'ar_status': ar.status,
                    'remaining_balance': str(ar.amount_outstanding),
                    'sale_status': sale.status
                },
                description=f'AR payment of {amount} recorded for {sale.receipt_number}',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
        
        # Return success response with updated info
        return Response({
            'success': True,
            'ar_payment_id': str(ar_payment.id),
            'payment': {
                'amount': str(amount),
                'method': payment_method,
                'date': ar_payment.payment_date.isoformat(),
                'received_by': request.user.username
            },
            'ar': {
                'id': str(ar.id),
                'status': ar.status,
                'original_amount': str(ar.original_amount),
                'amount_paid': str(ar.amount_paid),
                'amount_outstanding': str(ar.amount_outstanding),
                'payment_percentage': str(ar.payment_percentage),
                'aging_category': ar.aging_category,
                'days_outstanding': ar.days_outstanding
            },
            'sale': {
                'id': str(sale.id),
                'receipt_number': sale.receipt_number,
                'status': sale.status,
                'amount_paid': str(sale.amount_paid),
                'amount_due': str(sale.amount_due)
            },
            'customer': {
                'id': str(sale.customer.id) if sale.customer else None,
                'name': sale.customer.name if sale.customer else None,
                'outstanding_balance': str(sale.customer.outstanding_balance) if sale.customer else '0.00'
            }
        }, status=status.HTTP_200_OK)

    
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
            refund_payouts=Sum('amount_refunded', filter=Q(status__in=['COMPLETED', 'PARTIAL', 'PENDING', 'REFUNDED'])),
            
            # Accounts receivable - money owed (credit sales not yet paid)
            # Updated to use new is_credit_sale flag instead of payment_type
            accounts_receivable=Sum('amount_due', filter=Q(
                is_credit_sale=True,
                status__in=['PENDING', 'PARTIAL']
            )),
            
            # Total credit sales amount (what customers owe)
            total_credit_sales_amount=Sum('amount_due', filter=Q(
                is_credit_sale=True,
                status__in=['PENDING', 'PARTIAL']
            )),
            
            # Count of unpaid credit sales
            unpaid_credit_count=Count('id', filter=Q(
                is_credit_sale=True,
                status__in=['PENDING', 'PARTIAL']
            )),
            
            # Payment method breakdown (by total sale amount)
            # Note: Credit is now tracked separately via is_credit_sale flag
            cash_sales=Sum('total_amount', filter=Q(payment_type='CASH', status='COMPLETED', is_credit_sale=False)),
            card_sales=Sum('total_amount', filter=Q(payment_type='CARD', status='COMPLETED', is_credit_sale=False)),
            mobile_sales=Sum('total_amount', filter=Q(payment_type='MOBILE', status='COMPLETED', is_credit_sale=False)),
            credit_sales_total=Sum('total_amount', filter=Q(is_credit_sale=True, status='COMPLETED')),
            
            # Credit sales breakdown using new is_credit_sale flag
            credit_sales_unpaid=Sum('amount_due', filter=Q(
                is_credit_sale=True,
                status='PENDING',
                amount_paid=Decimal('0.00')
            )),
            credit_sales_partial=Sum('amount_due', filter=Q(
                is_credit_sale=True,
                status='PARTIAL'
            )),
            credit_sales_paid=Sum('amount_paid', filter=Q(
                is_credit_sale=True,
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

        refunds_processed_total = Decimal('0.00')

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
            refunded = to_decimal(sale.amount_refunded)
            due = to_decimal(sale.amount_due)
            sale_tax_total = sale_line_tax[sale.id] + to_decimal(sale.tax_amount)
            sale_discount_total = sale_line_discount[sale.id] + to_decimal(sale.discount_amount)
            cogs = sale_costs[sale.id]
            net_revenue = total_amount - sale_tax_total
            profit = net_revenue - cogs

            if refunded < Decimal('0.00'):
                refunded = Decimal('0.00')
            refunds_processed_total += refunded

            net_paid = paid - refunded
            if net_paid < Decimal('0.00'):
                net_paid = Decimal('0.00')

            total_sales_all += total_amount
            total_tax_all += sale_tax_total
            total_cogs_all += cogs
            total_discounts_all += sale_discount_total
            gross_profit_all += profit

            denominator = total_amount if total_amount > Decimal('0.00') else (net_paid + due)
            paid_ratio = (net_paid / denominator) if denominator > Decimal('0.00') else Decimal('0.00')
            if paid_ratio > Decimal('1.00'):
                paid_ratio = Decimal('1.00')

            realized_profit = (profit * paid_ratio)
            outstanding_profit = profit - realized_profit
            if outstanding_profit < Decimal('0.00'):
                outstanding_profit = Decimal('0.00')

            realized_revenue_total += net_paid
            realized_profit_total += realized_profit
            outstanding_profit_total += outstanding_profit

            # Track credit sales using new is_credit_sale flag
            if sale.is_credit_sale:
                outstanding_revenue_total += due
                credit_total_amount += total_amount
                credit_amount_paid_total += net_paid
                credit_amount_due_total += due
                credit_realized_profit += realized_profit
                credit_outstanding_profit += outstanding_profit

                if sale.status == 'COMPLETED':
                    credit_total_completed += total_amount
                    credit_paid_completed += net_paid
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
        summary['refunds_processed'] = to_money(refunds_processed_total)
        summary['outstanding_revenue'] = to_money(outstanding_revenue_total)
        summary['realized_profit'] = to_money(realized_profit_total)
        summary['outstanding_profit'] = to_money(outstanding_profit_total)

        # Refresh cash/receivables snapshot
        cash_collected_gross = to_decimal(summary.get('cash_at_hand'))
        refund_payouts_total = to_decimal(summary.get('refund_payouts'))
        net_cash_available = realized_revenue_total
        if cash_collected_gross or refund_payouts_total:
            net_cash_available = cash_collected_gross - refund_payouts_total

        summary['cash_collected'] = to_money(cash_collected_gross)
        summary['cash_outflow_refunds'] = to_money(refund_payouts_total)
        summary['refund_payouts'] = to_money(refund_payouts_total)
        summary['cash_at_hand'] = to_money(net_cash_available)
        summary['accounts_receivable'] = to_money(outstanding_revenue_total)

        total_assets = net_cash_available + outstanding_revenue_total
        summary['financial_position'] = {
            'cash_at_hand': to_money(net_cash_available),
            'accounts_receivable': to_money(outstanding_revenue_total),
            'total_assets': to_money(total_assets),
            'cash_percentage': round(float((net_cash_available / total_assets * Decimal('100.00')) if total_assets > Decimal('0.00') else Decimal('0.00')), 2),
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

        # Detailed AR analytics from AccountsReceivable table
        # Get date-filtered AR records
        ar_queryset = AccountsReceivable.objects.filter(
            sale__in=queryset.values_list('id', flat=True)
        )
        
        # AR aging breakdown
        ar_aging = ar_queryset.aggregate(
            current_ar=Sum('amount_outstanding', filter=Q(aging_category='CURRENT')),
            days_1_30=Sum('amount_outstanding', filter=Q(aging_category='1-30_DAYS')),
            days_31_60=Sum('amount_outstanding', filter=Q(aging_category='31-60_DAYS')),
            days_61_90=Sum('amount_outstanding', filter=Q(aging_category='61-90_DAYS')),
            days_over_90=Sum('amount_outstanding', filter=Q(aging_category='OVER_90_DAYS')),
            
            count_current=Count('id', filter=Q(aging_category='CURRENT')),
            count_1_30=Count('id', filter=Q(aging_category='1-30_DAYS')),
            count_31_60=Count('id', filter=Q(aging_category='31-60_DAYS')),
            count_61_90=Count('id', filter=Q(aging_category='61-90_DAYS')),
            count_over_90=Count('id', filter=Q(aging_category='OVER_90_DAYS')),
        )
        
        # AR status breakdown
        ar_status = ar_queryset.aggregate(
            pending_amount=Sum('amount_outstanding', filter=Q(status='PENDING')),
            partial_amount=Sum('amount_outstanding', filter=Q(status='PARTIAL')),
            overdue_amount=Sum('amount_outstanding', filter=Q(status='OVERDUE')),
            
            pending_count=Count('id', filter=Q(status='PENDING')),
            partial_count=Count('id', filter=Q(status='PARTIAL')),
            overdue_count=Count('id', filter=Q(status='OVERDUE')),
            paid_count=Count('id', filter=Q(status='PAID')),
        )
        
        # Calculate total AR from queryset
        total_ar_outstanding = ar_queryset.aggregate(
            total=Sum('amount_outstanding')
        )['total'] or Decimal('0.00')
        
        # AR collection metrics
        ar_payments_total = ARPayment.objects.filter(
            accounts_receivable__in=ar_queryset
        ).aggregate(
            total_collected=Sum('amount'),
            payment_count=Count('id')
        )
        
        summary['ar_analytics'] = {
            # Aging breakdown
            'aging': {
                'current': {
                    'amount': to_money(ar_aging.get('current_ar') or Decimal('0.00')),
                    'count': ar_aging.get('count_current') or 0,
                },
                'days_1_30': {
                    'amount': to_money(ar_aging.get('days_1_30') or Decimal('0.00')),
                    'count': ar_aging.get('count_1_30') or 0,
                },
                'days_31_60': {
                    'amount': to_money(ar_aging.get('days_31_60') or Decimal('0.00')),
                    'count': ar_aging.get('count_31_60') or 0,
                },
                'days_61_90': {
                    'amount': to_money(ar_aging.get('days_61_90') or Decimal('0.00')),
                    'count': ar_aging.get('count_61_90') or 0,
                },
                'over_90_days': {
                    'amount': to_money(ar_aging.get('days_over_90') or Decimal('0.00')),
                    'count': ar_aging.get('count_over_90') or 0,
                },
            },
            
            # Status breakdown
            'status': {
                'pending': {
                    'amount': to_money(ar_status.get('pending_amount') or Decimal('0.00')),
                    'count': ar_status.get('pending_count') or 0,
                },
                'partial': {
                    'amount': to_money(ar_status.get('partial_amount') or Decimal('0.00')),
                    'count': ar_status.get('partial_count') or 0,
                },
                'overdue': {
                    'amount': to_money(ar_status.get('overdue_amount') or Decimal('0.00')),
                    'count': ar_status.get('overdue_count') or 0,
                },
                'paid': {
                    'count': ar_status.get('paid_count') or 0,
                },
            },
            
            # Summary metrics
            'total_outstanding': to_money(total_ar_outstanding),
            'total_collected': to_money(ar_payments_total.get('total_collected') or Decimal('0.00')),
            'payment_transactions': ar_payments_total.get('payment_count') or 0,
            
            # Health indicators
            'overdue_percentage': round(float(
                ((ar_status.get('overdue_amount') or Decimal('0.00')) / total_ar_outstanding * Decimal('100.00'))
                if total_ar_outstanding > Decimal('0.00') else Decimal('0.00')
            ), 2),
        }

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
        response = HttpResponse(content_type='text/csv; charset=utf-8')
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
            sale.calculate_totals()
            
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

    @action(detail=True, methods=['post'])
    def refund(self, request, pk=None):
        """Process a refund for an existing sale and restock inventory."""
        sale = self.get_object()

        serializer = SaleRefundSerializer(data=request.data, context={'sale': sale})
        serializer.is_valid(raise_exception=True)

        refund = sale.process_refund(
            user=request.user,
            items=serializer.validated_data['items'],
            reason=serializer.validated_data['reason'],
            refund_type=serializer.validated_data.get('refund_type', 'PARTIAL')
        )

        return Response({
            'message': 'Refund processed successfully',
            'refund': RefundSerializer(refund).data,
            'sale': SaleSerializer(sale).data
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """
        Cancel a sale and automatically handle all consequences.
        
        This endpoint:
        - Creates a full refund for all items
        - Restocks inventory to original location
        - Updates sale status to CANCELLED
        - Reverses customer credit balance (if applicable)
        - Creates comprehensive audit trail
        
        Request body:
        {
            "reason": "Customer changed mind", // required
            "restock": true  // optional, default: true
        }
        """
        sale = self.get_object()
        
        # Validate request
        reason = request.data.get('reason')
        if not reason:
            return Response(
                {'error': 'Reason is required for cancellation'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        restock = request.data.get('restock', True)
        
        try:
            with transaction.atomic():
                refund = sale.cancel_sale(
                    user=request.user,
                    reason=reason,
                    restock=restock
                )
                
                # Prepare response
                response_data = {
                    'message': 'Sale cancelled successfully',
                    'sale': SaleSerializer(sale).data,
                }
                
                if refund:
                    response_data['refund'] = RefundSerializer(refund).data
                
                return Response(response_data, status=status.HTTP_200_OK)
                
        except ValidationError as exc:
            return Response(
                {'error': str(exc)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as exc:
            return Response(
                {
                    'error': 'Failed to cancel sale',
                    'details': str(exc)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['get'])
    def receipt(self, request, pk=None):
        """
        Get comprehensive receipt/invoice data for a completed sale.
        
        This endpoint returns all information needed to display or print a receipt:
        - Business details (name, address, TIN, phone)
        - Storefront details
        - Customer information (if applicable)
        - Line items with products, quantities, and prices
        - Payment information
        - Totals and calculations
        
        Only completed sales can have receipts generated.
        
        Query parameters:
        - format: 'json' (default) or 'html' or 'pdf'
        
        Response includes:
        - Full business and storefront information
        - Customer details for personalized receipts
        - Complete line item breakdown
        - Payment method and amounts
        - Receipt number and timestamps
        - Sale type (RETAIL/WHOLESALE) for proper display
        """
        from .receipt_serializers import ReceiptSerializer
        from .receipt_generator import generate_receipt_html, generate_receipt_pdf
        
        sale = self.get_object()
        
        # Only allow receipt generation for completed sales
        if sale.status not in ['COMPLETED', 'PARTIAL', 'REFUNDED']:
            return Response(
                {
                    'error': 'Receipt can only be generated for completed sales',
                    'current_status': sale.status,
                    'allowed_statuses': ['COMPLETED', 'PARTIAL', 'REFUNDED']
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Serialize receipt data
        serializer = ReceiptSerializer(sale)
        receipt_data = serializer.data
        
        # Check requested format
        format_type = request.query_params.get('format', 'json').lower()
        
        if format_type == 'html':
            # Return HTML for printing
            html_content = generate_receipt_html(receipt_data)
            return HttpResponse(html_content, content_type='text/html')
        
        elif format_type == 'pdf':
            # Return PDF file (requires weasyprint)
            try:
                pdf_bytes = generate_receipt_pdf(receipt_data)
                response = HttpResponse(pdf_bytes, content_type='application/pdf')
                response['Content-Disposition'] = f'attachment; filename="receipt-{sale.receipt_number}.pdf"'
                return response
            except ImportError:
                return Response(
                    {
                        'error': 'PDF generation not available',
                        'message': 'WeasyPrint library is not installed. Install with: pip install weasyprint'
                    },
                    status=status.HTTP_501_NOT_IMPLEMENTED
                )
            except Exception as e:
                return Response(
                    {
                        'error': 'Failed to generate PDF',
                        'details': str(e)
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        else:
            # Default: return JSON
            return Response(receipt_data)
    
    @action(detail=True, methods=['post', 'patch'], url_path='update_customer')
    def update_customer(self, request, pk=None):
        """
        Update the customer on a DRAFT sale.
        
        This endpoint allows updating the customer associated with a sale
        that is still in DRAFT status. This is essential for POS workflows
        where the customer is selected after the sale is created.
        
        Security & Validation:
        - Only allows updating customer on DRAFT sales
        - Validates customer belongs to the same business
        - Prevents updating completed/cancelled sales
        - Maintains data integrity
        
        Request body:
        {
          "customer": "uuid-of-customer"  // Required: UUID of the customer
        }
        
        Returns:
        - 200 OK: Updated sale object with new customer information
        - 400 Bad Request: If sale is not DRAFT or customer field missing
        - 404 Not Found: If customer doesn't exist or doesn't belong to business
        
        Example:
        PATCH /sales/api/sales/{sale_id}/update-customer/
        {
          "customer": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        }
        
        Response:
        {
          "id": "sale-uuid",
          "customer": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
          "customer_name": "Fred Amugi",
          "status": "DRAFT",
          ...
        }
        """
        sale = self.get_object()
        
        # 1. Security Check: Only allow customer updates on DRAFT sales
        if sale.status != 'DRAFT':
            return Response(
                {
                    'error': 'Cannot update customer on a sale that is not in DRAFT status',
                    'current_status': sale.status,
                    'allowed_status': 'DRAFT',
                    'message': 'Customer can only be changed before the sale is completed. '
                              'To change customer on a completed sale, you must cancel and recreate it.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 2. Validate customer field is provided
        customer_id = request.data.get('customer')
        if not customer_id:
            return Response(
                {
                    'error': 'customer field is required',
                    'message': 'Please provide a customer UUID in the request body',
                    'example': {'customer': 'uuid-of-customer'}
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 3. Validate customer exists and belongs to the same business
        try:
            customer = Customer.objects.get(
                id=customer_id,
                business=sale.business
            )
        except Customer.DoesNotExist:
            return Response(
                {
                    'error': 'Customer not found or does not belong to this business',
                    'customer_id': str(customer_id),
                    'business_id': str(sale.business.id) if sale.business else None,
                    'message': 'The customer must exist and belong to the same business as the sale'
                },
                status=status.HTTP_404_NOT_FOUND
            )
        except ValidationError:
            return Response(
                {
                    'error': 'Invalid customer ID format',
                    'message': 'Customer ID must be a valid UUID'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 4. Store old customer for audit trail (optional)
        old_customer = sale.customer
        old_customer_name = old_customer.name if old_customer else None
        
        # 5. Update the customer
        sale.customer = customer
        sale.save(update_fields=['customer'])
        
        # 6. Log the change for audit trail
        AuditLog.log_event(
            event_type='sale.customer_updated',
            user=request.user,
            sale=sale,
            event_data={
                'old_customer_id': str(old_customer.id) if old_customer else None,
                'old_customer_name': old_customer_name,
                'new_customer_id': str(customer.id),
                'new_customer_name': customer.name,
                'sale_status': sale.status
            },
            description=f'Customer updated from "{old_customer_name}" to "{customer.name}" on sale {sale.id}',
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        # 7. Return updated sale with customer information
        serializer = self.get_serializer(sale)
        return Response({
            'message': f'Customer updated successfully to {customer.name}',
            'previous_customer': old_customer_name,
            'new_customer': customer.name,
            'sale': serializer.data
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
    permission_classes = [permissions.IsAuthenticated, RequiresActiveSubscription]
    
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
