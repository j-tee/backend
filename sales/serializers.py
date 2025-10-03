"""
Serializers for Sales API
"""
from rest_framework import serializers
from decimal import Decimal
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import (
    Customer, Sale, SaleItem, Payment, Refund, RefundItem, 
    CreditTransaction, StockReservation, AuditLog
)
from inventory.models import Product, StockProduct, StoreFront
from accounts.models import Business


class CustomerSerializer(serializers.ModelSerializer):
    """Serializer for Customer model"""
    available_credit = serializers.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        read_only=True
    )
    overdue_balance = serializers.SerializerMethodField()
    
    class Meta:
        model = Customer
        fields = [
            'id', 'business', 'name', 'email', 'phone', 'address',
            'customer_type', 'credit_limit', 'outstanding_balance',
            'available_credit', 'credit_terms_days', 'credit_blocked',
            'contact_person', 'is_active', 'created_by', 'created_at',
            'updated_at', 'overdue_balance'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'outstanding_balance']
    
    def get_overdue_balance(self, obj):
        """Get overdue balance for the customer"""
        return str(obj.get_overdue_balance())
    
    def validate(self, data):
        """Validate customer data"""
        # Ensure business is set from request user if not provided
        request = self.context.get('request')
        if request and not data.get('business'):
            if hasattr(request.user, 'business'):
                data['business'] = request.user.business
        
        return data


class SaleItemSerializer(serializers.ModelSerializer):
    """Serializer for SaleItem model"""
    product_name = serializers.CharField(read_only=True)
    product_sku = serializers.CharField(read_only=True)
    base_amount = serializers.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        read_only=True
    )
    gross_amount = serializers.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        read_only=True
    )
    profit_amount = serializers.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        read_only=True
    )
    profit_margin = serializers.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        read_only=True
    )
    
    class Meta:
        model = SaleItem
        fields = [
            'id', 'sale', 'product', 'stock', 'stock_product',
            'quantity', 'unit_price', 'discount_percentage', 'discount_amount',
            'tax_rate', 'tax_amount', 'total_price', 'product_name',
            'product_sku', 'base_amount', 'gross_amount', 'profit_amount',
            'profit_margin', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'total_price', 'product_name', 'product_sku',
            'tax_amount', 'created_at', 'updated_at'
        ]
    
    def validate(self, data):
        """Validate sale item"""
        # Check stock availability
        if data.get('stock_product'):
            stock_product = data['stock_product']
            quantity = data.get('quantity', Decimal('0'))
            
            # Get available quantity
            available = stock_product.get_available_quantity()
            
            # If updating, add back the current item's quantity to available
            if self.instance:
                # Get current reservation for this item
                sale_id = self.instance.sale.id if self.instance.sale else None
                if sale_id:
                    current_reservations = StockReservation.objects.filter(
                        cart_session_id=str(sale_id),
                        stock_product=stock_product,
                        status='ACTIVE'
                    ).aggregate(total=Sum('quantity'))
                    current_reserved = current_reservations['total'] or Decimal('0')
                    available += current_reserved
            
            if available < quantity:
                raise serializers.ValidationError({
                    'quantity': f'Insufficient stock. Available: {available}, Requested: {quantity}'
                })
        
        return data


class SaleSerializer(serializers.ModelSerializer):
    """Serializer for Sale model"""
    sale_items = SaleItemSerializer(many=True, read_only=True)
    storefront_name = serializers.CharField(source='storefront.name', read_only=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True, allow_null=True)
    user_name = serializers.CharField(source='user.name', read_only=True, allow_null=True)
    
    class Meta:
        model = Sale
        fields = [
            'id', 'business', 'storefront', 'storefront_name', 'user', 'user_name',
            'customer', 'customer_name', 'receipt_number', 'type', 'status',
            'subtotal', 'discount_amount', 'tax_amount', 'total_amount',
            'amount_paid', 'amount_due', 'payment_type', 'manager_override',
            'override_reason', 'override_by', 'notes', 'cart_session_id',
            'created_at', 'updated_at', 'completed_at', 'sale_items'
        ]
        read_only_fields = [
            'id', 'receipt_number', 'subtotal', 'total_amount', 'amount_due',
            'created_at', 'updated_at', 'completed_at'
        ]
    
    def validate(self, data):
        """Validate sale data"""
        # Ensure business is set from request user if not provided
        request = self.context.get('request')
        if request and not data.get('business'):
            if hasattr(request.user, 'business'):
                data['business'] = request.user.business
        
        # Ensure user is set from request if not provided
        if request and not data.get('user'):
            data['user'] = request.user
        
        # Validate credit sale has customer
        if data.get('payment_type') == 'CREDIT' and not data.get('customer'):
            raise serializers.ValidationError({
                'customer': 'Customer is required for credit sales'
            })
        
        # Check credit limit if credit sale
        if data.get('payment_type') == 'CREDIT' and data.get('customer'):
            customer = data['customer']
            # Calculate total (will be set properly later)
            total = data.get('total_amount', Decimal('0'))
            
            can_purchase, message = customer.can_purchase(
                total, 
                force=data.get('manager_override', False)
            )
            
            if not can_purchase and not data.get('manager_override'):
                raise serializers.ValidationError({
                    'customer': message
                })
        
        return data
    
    def create(self, validated_data):
        """Create sale with DRAFT status by default"""
        if 'status' not in validated_data:
            validated_data['status'] = 'DRAFT'
        
        sale = super().create(validated_data)
        
        # Log creation
        request = self.context.get('request')
        if request:
            AuditLog.log_event(
                event_type='sale.created',
                user=request.user,
                sale=sale,
                event_data={
                    'receipt_number': sale.receipt_number,
                    'type': sale.type,
                    'payment_type': sale.payment_type
                },
                description=f'Sale {sale.receipt_number} created',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
        
        return sale


class StockReservationSerializer(serializers.ModelSerializer):
    """Serializer for StockReservation model"""
    product_name = serializers.CharField(source='stock_product.product.name', read_only=True)
    
    class Meta:
        model = StockReservation
        fields = [
            'id', 'stock_product', 'product_name', 'quantity',
            'cart_session_id', 'status', 'created_at', 'expires_at',
            'released_at'
        ]
        read_only_fields = ['id', 'status', 'created_at', 'expires_at', 'released_at']


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for Payment model"""
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'sale', 'customer', 'customer_name', 'amount_paid',
            'payment_date', 'payment_method', 'status', 'transaction_id',
            'reference_number', 'processed_by', 'notes', 'created_at',
            'updated_at'
        ]
        read_only_fields = ['id', 'payment_date', 'created_at', 'updated_at']


class RefundItemSerializer(serializers.ModelSerializer):
    """Serializer for RefundItem model"""
    product_name = serializers.CharField(source='sale_item.product_name', read_only=True)
    
    class Meta:
        model = RefundItem
        fields = ['id', 'refund', 'sale_item', 'product_name', 'quantity', 'amount']
        read_only_fields = ['id']


class RefundSerializer(serializers.ModelSerializer):
    """Serializer for Refund model"""
    refund_items = RefundItemSerializer(many=True, read_only=True)
    sale_receipt = serializers.CharField(source='sale.receipt_number', read_only=True)
    
    class Meta:
        model = Refund
        fields = [
            'id', 'sale', 'sale_receipt', 'refund_type', 'amount', 'reason',
            'status', 'requested_by', 'approved_by', 'processed_by',
            'created_at', 'updated_at', 'refund_items'
        ]
        read_only_fields = [
            'id', 'status', 'approved_by', 'processed_by',
            'created_at', 'updated_at'
        ]


class CreditTransactionSerializer(serializers.ModelSerializer):
    """Serializer for CreditTransaction model"""
    customer_name = serializers.CharField(source='customer.name', read_only=True)
    
    class Meta:
        model = CreditTransaction
        fields = [
            'id', 'customer', 'customer_name', 'transaction_type', 'amount',
            'balance_before', 'balance_after', 'reference_id', 'description',
            'created_by', 'created_at'
        ]
        read_only_fields = [
            'id', 'balance_before', 'balance_after', 'created_at'
        ]


class AuditLogSerializer(serializers.ModelSerializer):
    """Serializer for AuditLog (read-only)"""
    user_name = serializers.CharField(source='user.name', read_only=True, allow_null=True)
    sale_receipt = serializers.CharField(source='sale.receipt_number', read_only=True, allow_null=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True, allow_null=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id', 'event_type', 'sale', 'sale_receipt', 'sale_item',
            'customer', 'customer_name', 'payment', 'refund', 'user',
            'user_name', 'ip_address', 'user_agent', 'event_data',
            'description', 'timestamp'
        ]
        read_only_fields = '__all__'


# Action serializers for specific endpoints

class AddSaleItemSerializer(serializers.Serializer):
    """Serializer for adding items to a sale"""
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    stock_product = serializers.PrimaryKeyRelatedField(
        queryset=StockProduct.objects.all(),
        required=False,
        allow_null=True
    )
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0'))
    discount_percentage = serializers.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0'),
        min_value=Decimal('0'),
        max_value=Decimal('100')
    )
    tax_rate = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0'),
        min_value=Decimal('0'),
        max_value=Decimal('100')
    )


class CompleteSaleSerializer(serializers.Serializer):
    """Serializer for completing a sale (checkout)"""
    payment_type = serializers.ChoiceField(choices=Sale.PAYMENT_TYPE_CHOICES)
    payments = PaymentSerializer(many=True, required=False)
    discount_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        min_value=Decimal('0')
    )
    tax_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0'),
        min_value=Decimal('0')
    )
    notes = serializers.CharField(required=False, allow_blank=True)


class StockAvailabilitySerializer(serializers.Serializer):
    """Serializer for stock availability response"""
    product_id = serializers.UUIDField()
    product_name = serializers.CharField()
    stock_product_id = serializers.UUIDField()
    quantity = serializers.DecimalField(max_digits=10, decimal_places=2)
    available = serializers.DecimalField(max_digits=10, decimal_places=2)
    reserved = serializers.DecimalField(max_digits=10, decimal_places=2)
    unreserved = serializers.DecimalField(max_digits=10, decimal_places=2)
    retail_price = serializers.DecimalField(max_digits=12, decimal_places=2)
    wholesale_price = serializers.DecimalField(max_digits=12, decimal_places=2)
