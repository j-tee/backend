from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction
from django.db.models import Sum, Q
from decimal import Decimal

from .models import (
    Customer, Sale, SaleItem, Payment, Refund, RefundItem,
    CreditTransaction, StockReservation, AuditLog
)
from .serializers import (
    CustomerSerializer, SaleSerializer, SaleItemSerializer,
    PaymentSerializer, RefundSerializer, RefundItemSerializer,
    CreditTransactionSerializer, AuditLogSerializer,
    AddSaleItemSerializer, CompleteSaleSerializer,
    StockAvailabilitySerializer
)
from inventory.models import StockProduct, StoreFront


class CustomerViewSet(viewsets.ModelViewSet):
    """ViewSet for Customer CRUD operations"""
    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter customers by user's business"""
        user = self.request.user
        if hasattr(user, 'business'):
            return Customer.objects.filter(business=user.business)
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
    
    def get_queryset(self):
        """Filter sales by user's business and optional filters"""
        user = self.request.user
        queryset = Sale.objects.select_related(
            'business', 'storefront', 'user', 'customer'
        ).prefetch_related('sale_items__product')
        
        if hasattr(user, 'business'):
            queryset = queryset.filter(business=user.business)
        else:
            queryset = Sale.objects.none()
        
        # Filter by status
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by storefront
        storefront_filter = self.request.query_params.get('storefront')
        if storefront_filter:
            queryset = queryset.filter(storefront_id=storefront_filter)
        
        # Filter by customer
        customer_filter = self.request.query_params.get('customer')
        if customer_filter:
            queryset = queryset.filter(customer_id=customer_filter)
        
        return queryset.order_by('-created_at')
    
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


class SaleItemViewSet(viewsets.ModelViewSet):
    """ViewSet for SaleItem operations"""
    serializer_class = SaleItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter sale items"""
        user = self.request.user
        queryset = SaleItem.objects.select_related('sale', 'product', 'stock_product')
        
        if hasattr(user, 'business'):
            queryset = queryset.filter(sale__business=user.business)
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
        user = self.request.user
        queryset = Payment.objects.select_related('sale', 'customer')
        
        if hasattr(user, 'business'):
            queryset = queryset.filter(sale__business=user.business)
        else:
            queryset = Payment.objects.none()
        
        return queryset.order_by('-payment_date')


class RefundViewSet(viewsets.ModelViewSet):
    """ViewSet for Refund operations"""
    serializer_class = RefundSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter refunds"""
        user = self.request.user
        queryset = Refund.objects.select_related('sale')
        
        if hasattr(user, 'business'):
            queryset = queryset.filter(sale__business=user.business)
        else:
            queryset = Refund.objects.none()
        
        return queryset.order_by('-created_at')


class CreditTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for CreditTransaction (read-only)"""
    serializer_class = CreditTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter credit transactions"""
        user = self.request.user
        queryset = CreditTransaction.objects.select_related('customer')
        
        if hasattr(user, 'business'):
            queryset = queryset.filter(customer__business=user.business)
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
        user = self.request.user
        queryset = AuditLog.objects.select_related('user', 'sale', 'customer')
        
        if hasattr(user, 'business'):
            queryset = queryset.filter(
                Q(sale__business=user.business) |
                Q(customer__business=user.business)
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
