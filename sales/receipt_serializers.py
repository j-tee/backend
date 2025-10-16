"""
Receipt-specific serializers for generating detailed receipt/invoice data
"""
from rest_framework import serializers
from decimal import Decimal
from django.db.models import Sum

from .models import Sale, SaleItem
from inventory.models import StoreFront
from accounts.models import Business


class ReceiptLineItemSerializer(serializers.ModelSerializer):
    """Line item for receipt display"""
    product_name = serializers.CharField(source='product.name', read_only=True)
    sku = serializers.CharField(source='product.sku', read_only=True)
    quantity = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        coerce_to_string=False
    )
    unit_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        coerce_to_string=False
    )
    total_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        coerce_to_string=False
    )
    discount_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        coerce_to_string=False
    )
    
    class Meta:
        model = SaleItem
        fields = [
            'product_name', 'sku', 'quantity', 'unit_price',
            'discount_amount', 'total_price'
        ]


class ReceiptSerializer(serializers.ModelSerializer):
    """
    Comprehensive serializer for receipt/invoice generation
    Returns all data needed to print/display a receipt
    """
    # Business information
    business_name = serializers.CharField(source='business.name', read_only=True)
    business_tin = serializers.CharField(source='business.tin', read_only=True)
    business_email = serializers.CharField(source='business.email', read_only=True)
    business_phone_numbers = serializers.JSONField(source='business.phone_numbers', read_only=True)
    business_address = serializers.CharField(source='business.address', read_only=True)
    
    # Business settings (for currency and other preferences)
    business_settings = serializers.SerializerMethodField()
    
    # Storefront information
    storefront_name = serializers.CharField(source='storefront.name', read_only=True)
    storefront_location = serializers.CharField(source='storefront.location', read_only=True, allow_null=True)
    storefront_phone = serializers.CharField(source='storefront.phone', read_only=True, allow_null=True)
    
    # Customer information (may be null for walk-in customers)
    customer_id = serializers.UUIDField(source='customer.id', read_only=True, allow_null=True)
    customer_name = serializers.CharField(source='customer.name', read_only=True, allow_null=True)
    customer_email = serializers.CharField(source='customer.email', read_only=True, allow_null=True)
    customer_phone = serializers.CharField(source='customer.phone', read_only=True, allow_null=True)
    customer_address = serializers.CharField(source='customer.address', read_only=True, allow_null=True)
    customer_type = serializers.CharField(source='customer.customer_type', read_only=True, allow_null=True)
    
    # Cashier/Staff information
    served_by = serializers.SerializerMethodField()
    
    # Line items
    line_items = ReceiptLineItemSerializer(many=True, read_only=True, source='sale_items')
    
    # Payment information
    payment_type_display = serializers.CharField(source='get_payment_type_display', read_only=True)
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    
    # Amounts (ensure they're numbers, not strings)
    subtotal = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        coerce_to_string=False
    )
    discount_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        coerce_to_string=False
    )
    tax_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        coerce_to_string=False
    )
    total_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        coerce_to_string=False
    )
    amount_paid = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        coerce_to_string=False
    )
    amount_due = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        coerce_to_string=False
    )
    
    # Calculated fields
    change_given = serializers.SerializerMethodField()
    total_items = serializers.SerializerMethodField()
    total_quantity = serializers.SerializerMethodField()
    
    # Date formatting
    completed_at_formatted = serializers.SerializerMethodField()
    
    class Meta:
        model = Sale
        fields = [
            # Identification
            'id', 'receipt_number', 'type', 'type_display', 'status',
            
            # Business info
            'business_name', 'business_tin', 'business_email',
            'business_phone_numbers', 'business_address', 'business_settings',
            
            # Storefront info
            'storefront_name', 'storefront_location', 'storefront_phone',
            
            # Customer info
            'customer_id', 'customer_name', 'customer_email',
            'customer_phone', 'customer_address', 'customer_type',
            
            # Staff info
            'served_by',
            
            # Line items
            'line_items', 'total_items', 'total_quantity',
            
            # Financial details
            'subtotal', 'discount_amount', 'tax_amount', 'total_amount',
            'amount_paid', 'amount_due', 'change_given',
            
            # Payment info
            'payment_type', 'payment_type_display',
            
            # Dates
            'created_at', 'completed_at', 'completed_at_formatted',
            
            # Additional
            'notes'
        ]
    
    def get_business_settings(self, obj):
        """Get business settings including currency"""
        try:
            if hasattr(obj.business, 'settings'):
                return {
                    'regional': obj.business.settings.regional,
                    'receipt': obj.business.settings.receipt,
                }
        except Exception:
            pass
        # Return None if settings not available
        return None
    
    def get_served_by(self, obj):
        """Get the name of the staff member who processed the sale"""
        if obj.user:
            return getattr(obj.user, 'name', str(obj.user))
        return None
    
    def get_change_given(self, obj):
        """Calculate change given (only for CASH payments when overpaid)"""
        if obj.payment_type == 'CASH' and obj.amount_paid > obj.total_amount:
            return float(obj.amount_paid - obj.total_amount)
        return 0.00
    
    def get_total_items(self, obj):
        """Get total number of distinct items"""
        return obj.sale_items.count()
    
    def get_total_quantity(self, obj):
        """Get total quantity of all items"""
        total = obj.sale_items.aggregate(
            total=Sum('quantity')
        )['total']
        return float(total) if total else 0.00
    
    def get_completed_at_formatted(self, obj):
        """Format completion date for display"""
        if obj.completed_at:
            # Format: "11 Oct 2025, 09:15 AM"
            return obj.completed_at.strftime("%d %b %Y, %I:%M %p")
        return None


class ReceiptSummarySerializer(serializers.Serializer):
    """
    Summary data for receipt - useful for receipt list views
    """
    id = serializers.UUIDField()
    receipt_number = serializers.CharField()
    type = serializers.CharField()
    customer_name = serializers.CharField(allow_null=True)
    total_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        coerce_to_string=False
    )
    completed_at = serializers.DateTimeField()
    can_reprint = serializers.SerializerMethodField()
    
    def get_can_reprint(self, obj):
        """Check if receipt can be reprinted"""
        # Only allow reprinting of completed sales
        return obj.get('status') == 'COMPLETED'
