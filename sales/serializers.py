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
        read_only=True,
        coerce_to_string=False
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
        extra_kwargs = {
            'business': {'required': False, 'allow_null': True},
            'email': {'required': False, 'allow_null': True},
            'phone': {'required': False, 'allow_null': True, 'allow_blank': True},
            'address': {'required': False, 'allow_null': True, 'allow_blank': True},
            'customer_type': {'required': False},
            'credit_limit': {'required': False},
            'credit_terms_days': {'required': False},
            'credit_blocked': {'required': False},
            'contact_person': {'required': False, 'allow_null': True, 'allow_blank': True},
            'is_active': {'required': False},
            'created_by': {'required': False, 'allow_null': True},
        }
    
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
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    product_category = serializers.CharField(source='product.category.name', read_only=True, allow_null=True)
    
    # ✅ FIX: Return numeric fields as numbers, not strings
    quantity = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2,
        coerce_to_string=False  # Return as number for frontend
    )
    unit_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        coerce_to_string=False
    )
    discount_percentage = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        coerce_to_string=False
    )
    discount_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        coerce_to_string=False
    )
    subtotal = serializers.DecimalField(
        source='base_amount',
        max_digits=12,
        decimal_places=2,
        read_only=True,
        coerce_to_string=False
    )
    tax_rate = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        coerce_to_string=False
    )
    tax_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        coerce_to_string=False
    )
    total_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        coerce_to_string=False
    )
    # Alias for backward compatibility (frontend expects 'total')
    total = serializers.DecimalField(
        source='total_price',
        max_digits=12,
        decimal_places=2,
        read_only=True,
        coerce_to_string=False
    )
    profit_margin = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        allow_null=True,
        coerce_to_string=False
    )
    
    cost_price = serializers.SerializerMethodField()
    notes = serializers.CharField(required=False, allow_blank=True, allow_null=True, default=None)
    
    class Meta:
        model = SaleItem
        fields = [
            'id', 'sale', 'product', 'stock', 'stock_product',
            'product_name', 'product_sku', 'product_category',
            'quantity', 'unit_price', 'discount_percentage', 'discount_amount',
            'subtotal', 'tax_rate', 'tax_amount', 'total_price', 'total',
            'cost_price', 'profit_margin', 'notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'total_price', 'total', 'product_name', 'product_sku',
            'tax_amount', 'created_at', 'updated_at'
        ]
    
    def get_cost_price(self, obj):
        """Get cost price from stock_product or return None"""
        if obj.stock_product:
            cost = obj.stock_product.unit_cost
            # Convert Decimal to float for JSON serialization
            return float(cost) if cost is not None else None
        return None
    
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


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for Payment model"""
    transaction_reference = serializers.CharField(source='transaction_id', read_only=True, allow_null=True)
    phone_number = serializers.SerializerMethodField()
    card_last_4 = serializers.SerializerMethodField()
    card_brand = serializers.SerializerMethodField()
    processed_at = serializers.DateTimeField(source='payment_date', read_only=True, allow_null=True)
    failed_at = serializers.SerializerMethodField()
    error_message = serializers.SerializerMethodField()
    
    # ✅ FIX: Return amount_paid as number
    amount_paid = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        coerce_to_string=False
    )
    
    class Meta:
        model = Payment
        fields = [
            'id', 'sale', 'customer', 'payment_method', 'amount_paid',
            'status', 'transaction_reference', 'phone_number',
            'card_last_4', 'card_brand', 'notes',
            'created_at', 'processed_at', 'failed_at', 'error_message'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_phone_number(self, obj):
        """Extract phone number for mobile money payments"""
        if obj.payment_method == 'MOBILE' and obj.reference_number:
            # Assuming reference_number contains phone for mobile payments
            return obj.reference_number
        return None
    
    def get_card_last_4(self, obj):
        """Extract last 4 digits for card payments"""
        if obj.payment_method == 'CARD' and obj.reference_number:
            # Assuming reference_number contains card info
            parts = obj.reference_number.split('_')
            if len(parts) > 1:
                return parts[-1][-4:] if len(parts[-1]) >= 4 else None
        return None
    
    def get_card_brand(self, obj):
        """Extract card brand for card payments"""
        if obj.payment_method == 'CARD' and obj.reference_number:
            # Assuming reference_number contains brand info
            parts = obj.reference_number.split('_')
            if len(parts) > 0:
                return parts[0].upper() if parts[0] in ['visa', 'mastercard', 'amex'] else None
        return None
    
    def get_failed_at(self, obj):
        """Return timestamp if payment failed"""
        if obj.status == 'FAILED':
            return obj.updated_at
        return None
    
    def get_error_message(self, obj):
        """Return error message if payment failed"""
        if obj.status == 'FAILED' and obj.notes:
            return obj.notes
        return None


class SaleSerializer(serializers.ModelSerializer):
    """Serializer for Sale model"""
    line_items = SaleItemSerializer(many=True, read_only=True, source='sale_items')
    items_detail = serializers.SerializerMethodField()
    payments = PaymentSerializer(many=True, read_only=True)
    
    # ✅ CRITICAL FIX: Add sale_number (alias for receipt_number)
    sale_number = serializers.CharField(source='receipt_number', read_only=True)
    
    # ✅ CRITICAL FIX: Use 'storefront' (not warehouse) - sales happen at storefronts
    storefront = serializers.CharField(source='storefront.name', read_only=True)
    storefront_name = serializers.CharField(source='storefront.name', read_only=True)  # Keep for backward compatibility
    
    customer_name = serializers.CharField(source='customer.name', read_only=True, allow_null=True)
    user_name = serializers.SerializerMethodField()
    
    # ✅ FIX: Return monetary amounts as numbers
    subtotal = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        coerce_to_string=False,
        required=False,
        default=0
    )
    discount_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        coerce_to_string=False,
        required=False,
        default=0
    )
    tax_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        coerce_to_string=False,
        required=False,
        default=0
    )
    total_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        coerce_to_string=False,
        read_only=True  # System-calculated
    )
    amount_paid = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        coerce_to_string=False,
        read_only=True  # System-managed via payments
    )
    amount_refunded = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        coerce_to_string=False,
        read_only=True  # System-managed via refunds
    )
    amount_due = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        coerce_to_string=False,
        read_only=True  # System-calculated
    )
    
    # Credit payment tracking fields
    payment_status = serializers.SerializerMethodField()
    payment_completion_percentage = serializers.SerializerMethodField()
    
    class Meta:
        model = Sale
        fields = [
            'id', 'business', 'storefront', 'storefront_name', 'user', 'user_name',
            'customer', 'customer_name', 'receipt_number', 'sale_number', 'type', 'status',
            'subtotal', 'discount_amount', 'tax_amount', 'total_amount',
            'amount_paid', 'amount_refunded', 'amount_due', 'payment_type', 'manager_override',
            'override_reason', 'override_by', 'notes', 'cart_session_id',
            'created_at', 'updated_at', 'completed_at', 'line_items', 'items_detail', 'payments',
            'payment_status', 'payment_completion_percentage'
        ]
        read_only_fields = [
            'id', 'receipt_number', 'sale_number', 'subtotal', 'total_amount', 'amount_due',
            'amount_paid', 'amount_refunded',  # System-managed fields
            'created_at', 'updated_at', 'completed_at'
        ]
    
    def get_user_name(self, obj):
        """Get user name"""
        if obj.user:
            return obj.user.name if hasattr(obj.user, 'name') else str(obj.user)
        return None
    
    def get_items_detail(self, obj):
        """Get detailed items payload for movement detail view"""
        return obj.get_items_detail()
    
    def get_payment_status(self, obj):
        """
        Return user-friendly payment status for credit sales
        """
        if obj.payment_type != 'CREDIT':
            return None  # Not applicable for non-credit sales
        
        if obj.amount_due == Decimal('0.00'):
            return 'Fully Paid'
        elif obj.amount_paid > Decimal('0.00'):
            return f'Partially Paid ({obj.amount_paid}/{obj.total_amount})'
        else:
            return 'Unpaid'
    
    def get_payment_completion_percentage(self, obj):
        """
        Calculate payment completion percentage
        """
        if obj.total_amount == Decimal('0.00'):
            return 100.0
        
        percentage = (obj.amount_paid / obj.total_amount) * Decimal('100.0')
        return round(float(percentage), 2)
    
    def validate(self, data):
        """Validate sale data"""
        # Ensure business is set from request user's BusinessMembership if not provided
        request = self.context.get('request')
        if request and not data.get('business'):
            from accounts.models import BusinessMembership
            membership = BusinessMembership.objects.filter(
                user=request.user,
                is_active=True
            ).first()
            if membership:
                data['business'] = membership.business
        
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
            try:
                AuditLog.log_event(
                    event_type='sale.created',
                    user=request.user,
                    sale=sale,
                    event_data={
                        'sale_id': str(sale.id),
                        'type': sale.type,
                        'payment_type': sale.payment_type,
                        'status': sale.status
                    },
                    description=f'Sale {sale.id} created as {sale.status}',
                    ip_address=request.META.get('REMOTE_ADDR'),
                    user_agent=request.META.get('HTTP_USER_AGENT')
                )
            except Exception as e:
                # Log the error but don't fail the sale creation
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to create audit log: {e}")
        
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
    unit_price = serializers.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        min_value=Decimal('0'),
        required=False,  # Now optional - will auto-determine based on sale type
        allow_null=True
    )
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
    
    def validate(self, data):
        """
        DATA INTEGRITY CHECK: Ensure product has storefront inventory before allowing sale.
        This prevents sales from happening without proper stock flow:
        Warehouse → Transfer Request → Fulfillment → StoreFront → Sales
        
        Also auto-determines price based on sale type (RETAIL vs WHOLESALE).
        """
        from inventory.models import StoreFrontInventory
        
        # Get storefront from context (should be passed from view)
        sale = self.context.get('sale')
        if not sale or not sale.storefront:
            # If no storefront context, skip validation (will fail elsewhere)
            return data
        
        product = data.get('product')
        quantity = data.get('quantity', Decimal('0'))
        storefront = sale.storefront
        stock_product = data.get('stock_product')
        
        # AUTO-DETERMINE PRICE based on sale type if not explicitly provided
        if data.get('unit_price') is None or data.get('unit_price') == Decimal('0'):
            # Get the latest stock product if not provided
            if not stock_product:
                stock_product = StockProduct.objects.filter(
                    product=product
                ).order_by('-created_at').first()
            
            if stock_product:
                # Use wholesale price if sale type is WHOLESALE, otherwise use retail price
                if sale.type == 'WHOLESALE':
                    if stock_product.wholesale_price and stock_product.wholesale_price > Decimal('0'):
                        data['unit_price'] = stock_product.wholesale_price
                    else:
                        # Fallback to retail if wholesale not set
                        data['unit_price'] = stock_product.retail_price
                else:  # RETAIL
                    data['unit_price'] = stock_product.retail_price
            else:
                raise serializers.ValidationError({
                    'unit_price': f'Could not determine price for product "{product.name}". No stock product found.'
                })
        
        # Check if product has storefront inventory
        try:
            storefront_inv = StoreFrontInventory.objects.get(
                storefront=storefront,
                product=product
            )
        except StoreFrontInventory.DoesNotExist:
            raise serializers.ValidationError({
                'product': f'Product "{product.name}" has not been transferred to storefront "{storefront.name}". '
                          f'Please create a transfer request and fulfill it first.'
            })
        
        # StoreFrontInventory.quantity is already the current inventory
        # (it gets decremented by commit_stock() when sales are completed)
        # So we just need to check the current quantity directly
        available_at_storefront = storefront_inv.quantity
        
        if available_at_storefront < quantity:
            raise serializers.ValidationError({
                'quantity': f'Insufficient storefront inventory for "{product.name}". '
                          f'Available: {available_at_storefront}, Requested: {quantity}. '
                          f'Create a transfer request to move more stock to this storefront.'
            })
        
        return data


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
    # AR system fields (for credit sales)
    due_date = serializers.DateField(required=False, allow_null=True)
    ar_notes = serializers.CharField(required=False, allow_blank=True)
    
    def validate(self, data):
        """Custom validation - skip payment validation for credit sales"""
        payment_type = data.get('payment_type')
        
        # For credit sales, payments should be empty (will create AR instead)
        if payment_type == 'CREDIT':
            # Remove payments data if sent (frontend might send it by mistake)
            data['payments'] = []
        
        return data




class RecordPaymentSerializer(serializers.Serializer):
    """Serializer for recording a payment against a sale"""
    amount_paid = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.01')
    )
    payment_method = serializers.ChoiceField(choices=Payment.PAYMENT_METHOD_CHOICES)
    reference_number = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=True
    )
    notes = serializers.CharField(
        required=False,
        allow_blank=True
    )


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


class RefundRequestItemSerializer(serializers.Serializer):
    """Single line item payload for sale refunds."""
    sale_item_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)


class SaleRefundSerializer(serializers.Serializer):
    """Serializer for processing a refund against an existing sale."""
    refund_type = serializers.ChoiceField(choices=Refund.REFUND_TYPE_CHOICES, default='PARTIAL')
    reason = serializers.CharField()
    items = RefundRequestItemSerializer(many=True)

    def validate_items(self, value):
        sale: Sale = self.context['sale']
        if not value:
            raise serializers.ValidationError('At least one item must be provided for a refund.')

        sale_items_map = {str(item.id): item for item in sale.sale_items.all()}
        validated = []

        for entry in value:
            sale_item = sale_items_map.get(str(entry['sale_item_id']))
            if not sale_item:
                raise serializers.ValidationError(f"Sale item {entry['sale_item_id']} does not belong to this sale.")

            refundable = sale_item.refundable_quantity
            if refundable <= 0:
                raise serializers.ValidationError(f"Sale item {sale_item.id} has no refundable quantity remaining.")

            quantity = entry['quantity']
            if quantity > refundable:
                raise serializers.ValidationError(
                    f"Only {refundable} units available to refund for item {sale_item.id}."
                )

            validated.append({'sale_item': sale_item, 'quantity': quantity})

        return validated
