"""
Serializers for Stock Adjustment System
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from decimal import Decimal

from .stock_adjustments import (
    StockAdjustment,
    StockAdjustmentPhoto,
    StockAdjustmentDocument,
    StockCount,
    StockCountItem
)
from .models import StockProduct, StoreFront, Warehouse
from accounts.models import Business, BusinessMembership

User = get_user_model()


class StockAdjustmentPhotoSerializer(serializers.ModelSerializer):
    """Serializer for adjustment photos"""
    
    uploaded_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = StockAdjustmentPhoto
        fields = [
            'id', 'photo', 'description', 
            'uploaded_at', 'uploaded_by', 'uploaded_by_name'
        ]
        read_only_fields = ['id', 'uploaded_at', 'uploaded_by']
    
    def get_uploaded_by_name(self, obj):
        return obj.uploaded_by.name if obj.uploaded_by else None


class StockAdjustmentDocumentSerializer(serializers.ModelSerializer):
    """Serializer for adjustment documents"""
    
    uploaded_by_name = serializers.SerializerMethodField()
    document_type_display = serializers.CharField(source='get_document_type_display', read_only=True)
    
    class Meta:
        model = StockAdjustmentDocument
        fields = [
            'id', 'document', 'document_type', 'document_type_display',
            'description', 'uploaded_at', 'uploaded_by', 'uploaded_by_name'
        ]
        read_only_fields = ['id', 'uploaded_at', 'uploaded_by']
    
    def get_uploaded_by_name(self, obj):
        return obj.uploaded_by.name if obj.uploaded_by else None


class StockAdjustmentSerializer(serializers.ModelSerializer):
    """Serializer for stock adjustments"""
    
    # Related objects
    stock_product_details = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()
    
    # Display fields
    adjustment_type_display = serializers.CharField(source='get_adjustment_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    
    # Computed fields
    financial_impact = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    is_increase = serializers.BooleanField(read_only=True)
    is_decrease = serializers.BooleanField(read_only=True)
    
    # Nested data
    photos = StockAdjustmentPhotoSerializer(many=True, read_only=True)
    documents = StockAdjustmentDocumentSerializer(many=True, read_only=True)
    
    class Meta:
        model = StockAdjustment
        fields = [
            'id', 'business', 'stock_product', 'stock_product_details',
            'adjustment_type', 'adjustment_type_display',
            'quantity', 'unit_cost', 'total_cost',
            'reason', 'reference_number',
            'status', 'status_display', 'requires_approval',
            'created_by', 'created_by_name',
            'approved_by', 'approved_by_name',
            'created_at', 'approved_at', 'completed_at',
            'has_photos', 'has_documents',
            'related_sale',
            'financial_impact', 'is_increase', 'is_decrease',
            'photos', 'documents'
        ]
        read_only_fields = [
            'id', 'business', 'created_by', 'status',
            'total_cost', 'created_at', 'approved_at', 'completed_at',
            'approved_by', 'has_photos', 'has_documents'
        ]
    
    def get_stock_product_details(self, obj):
        """Get detailed info about the stock product"""
        sp = obj.stock_product
        return {
            'id': str(sp.id),
            'product_name': sp.product.name,
            'product_code': sp.product.sku,
            'quantity_at_creation': obj.quantity_before,  # Historical snapshot
            'current_quantity': sp.quantity,              # Real-time value
            'warehouse': sp.warehouse.name if sp.warehouse else None,
            'supplier': sp.supplier.name if sp.supplier else None,
            'unit_cost': str(sp.landed_unit_cost),
            'retail_price': str(sp.retail_price)
        }
    
    def get_created_by_name(self, obj):
        return obj.created_by.name if obj.created_by else None
    
    def get_approved_by_name(self, obj):
        return obj.approved_by.name if obj.approved_by else None
    
    def get_fields(self):
        """Override to set stock_product queryset based on user's business"""
        fields = super().get_fields()
        request = self.context.get('request')
        
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            # Get user's business
            membership = BusinessMembership.objects.filter(
                user=request.user,
                is_active=True
            ).first()
            
            if membership:
                # Filter stock products by the parent Stock business for authoritative scoping
                fields['stock_product'].queryset = StockProduct.objects.filter(
                    stock__business=membership.business
                ).select_related('product', 'supplier', 'warehouse', 'stock')
            else:
                # No business membership - return empty queryset
                fields['stock_product'].queryset = StockProduct.objects.none()
        
        return fields
    
    def validate(self, data):
        """Validate adjustment data"""
        request = self.context.get('request')
        
        # Set business from user's membership if not provided
        if request and not data.get('business'):
            membership = BusinessMembership.objects.filter(
                user=request.user,
                is_active=True
            ).first()
            if membership:
                data['business'] = membership.business
            else:
                raise serializers.ValidationError("User has no active business membership")
        
        # Set created_by
        if request and not data.get('created_by'):
            data['created_by'] = request.user
        
        # Validate stock_product belongs to business
        stock_product = data.get('stock_product')
        business = data.get('business')
        if stock_product and business:
            # Check if product belongs to business
            if stock_product.product.business != business:
                raise serializers.ValidationError(
                    "Stock product does not belong to this business"
                )
        
        # Validate quantity
        quantity = data.get('quantity')
        adjustment_type = data.get('adjustment_type')
        
        if quantity == 0:
            raise serializers.ValidationError("Quantity cannot be zero")
        
        # Validate negative quantity for decrease types
        decrease_types = [
            'THEFT', 'DAMAGE', 'EXPIRED', 'SPOILAGE', 'LOSS',
            'SAMPLE', 'WRITE_OFF', 'SUPPLIER_RETURN', 'TRANSFER_OUT'
        ]
        
        if adjustment_type in decrease_types and quantity > 0:
            # Auto-correct to negative
            data['quantity'] = -abs(quantity)
        
        # Validate positive quantity for increase types
        increase_types = [
            'CUSTOMER_RETURN', 'FOUND', 'CORRECTION_INCREASE', 'TRANSFER_IN'
        ]
        
        if adjustment_type in increase_types and quantity < 0:
            # Auto-correct to positive
            data['quantity'] = abs(quantity)
        
        # Check if adjustment would make stock negative
        if not self.instance:  # Only for creation
            stock_product = data.get('stock_product')
            quantity = data.get('quantity')
            
            if stock_product and quantity:
                new_quantity = stock_product.quantity + quantity
                if new_quantity < 0:
                    raise serializers.ValidationError(
                        f"This adjustment would result in negative stock. "
                        f"Current: {stock_product.quantity}, Adjustment: {quantity}, "
                        f"Result: {new_quantity}"
                    )
        
        # Set unit_cost from stock_product if not provided
        if not data.get('unit_cost') and stock_product:
            data['unit_cost'] = stock_product.landed_unit_cost
        
        # Determine if approval is required
        # ALL adjustments require approval for proper oversight
        # This ensures every stock change is reviewed before being applied
        data['requires_approval'] = True
        
        return data
    
    def create(self, validated_data):
        """Create adjustment - all adjustments now require approval"""
        # Capture quantity before adjustment (historical snapshot)
        stock_product = validated_data.get('stock_product')
        if stock_product and 'quantity_before' not in validated_data:
            validated_data['quantity_before'] = stock_product.quantity
        
        # Create the adjustment (will be PENDING and require approval)
        adjustment = super().create(validated_data)
        
        return adjustment


class StockAdjustmentCreateSerializer(serializers.ModelSerializer):
    """Simplified serializer for creating/updating adjustments"""
    
    class Meta:
        model = StockAdjustment
        fields = [
            'stock_product', 'adjustment_type', 'quantity',
            'reason', 'reference_number', 'unit_cost'
        ]
    
    def get_fields(self):
        """Override to set stock_product queryset based on user's business"""
        fields = super().get_fields()
        request = self.context.get('request')
        
        if request and hasattr(request, 'user') and request.user.is_authenticated:
            # Get user's business
            membership = BusinessMembership.objects.filter(
                user=request.user,
                is_active=True
            ).first()
            
            if membership:
                # Filter stock products by user's business
                fields['stock_product'].queryset = StockProduct.objects.filter(
                    stock__business=membership.business
                ).select_related('product', 'supplier', 'warehouse', 'stock')
            else:
                # No business membership - return empty queryset
                fields['stock_product'].queryset = StockProduct.objects.none()
        
        return fields
    
    def validate(self, data):
        """Use the same validation as main serializer"""
        serializer = StockAdjustmentSerializer(context=self.context)
        return serializer.validate(data)
    
    def create(self, validated_data):
        """Use the same creation logic as main serializer"""
        serializer = StockAdjustmentSerializer(context=self.context)
        return serializer.create(validated_data)
    
    def update(self, instance, validated_data):
        """Update adjustment - only allowed for PENDING status"""
        if instance.status != 'PENDING':
            raise serializers.ValidationError(
                f"Cannot edit adjustment with status: {instance.status}. Only PENDING adjustments can be edited."
            )
        
        # Update fields
        instance.stock_product = validated_data.get('stock_product', instance.stock_product)
        instance.adjustment_type = validated_data.get('adjustment_type', instance.adjustment_type)
        instance.quantity = validated_data.get('quantity', instance.quantity)
        instance.reason = validated_data.get('reason', instance.reason)
        instance.reference_number = validated_data.get('reference_number', instance.reference_number)
        instance.unit_cost = validated_data.get('unit_cost', instance.unit_cost)
        
        # Recalculate total_cost
        instance.total_cost = instance.unit_cost * abs(instance.quantity)
        
        # Update quantity_before if stock_product changed
        if 'stock_product' in validated_data:
            instance.quantity_before = instance.stock_product.quantity
        
        instance.save()
        return instance


class StockCountItemSerializer(serializers.ModelSerializer):
    """Serializer for stock count items"""
    
    stock_product_details = serializers.SerializerMethodField()
    has_discrepancy = serializers.BooleanField(read_only=True)
    discrepancy_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    adjustment_created_id = serializers.UUIDField(source='adjustment_created.id', read_only=True)
    
    class Meta:
        model = StockCountItem
        fields = [
            'id', 'stock_product', 'stock_product_details',
            'system_quantity', 'counted_quantity', 'discrepancy',
            'has_discrepancy', 'discrepancy_percentage',
            'counter_name', 'notes', 'counted_at',
            'adjustment_created_id'
        ]
        read_only_fields = ['id', 'discrepancy', 'counted_at']
    
    def get_stock_product_details(self, obj):
        """Get product details"""
        sp = obj.stock_product
        return {
            'id': str(sp.id),
            'product_name': sp.product.name,
            'product_code': sp.product.sku,
            'warehouse': sp.warehouse.name if sp.warehouse else None,
            'current_quantity': sp.quantity
        }
    
    def validate(self, data):
        """Validate count item"""
        # Set system_quantity from current stock if not provided
        if not data.get('system_quantity'):
            stock_product = data.get('stock_product')
            if stock_product:
                data['system_quantity'] = stock_product.quantity
        
        return data


class StockCountSerializer(serializers.ModelSerializer):
    """Serializer for stock counts"""
    
    created_by_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    items = StockCountItemSerializer(many=True, read_only=True)
    
    # Summary stats
    total_items = serializers.SerializerMethodField()
    items_with_discrepancy = serializers.SerializerMethodField()
    total_discrepancy_value = serializers.SerializerMethodField()
    
    class Meta:
        model = StockCount
        fields = [
            'id', 'business', 'storefront', 'warehouse',
            'count_date', 'status', 'status_display', 'notes',
            'created_by', 'created_by_name',
            'created_at', 'completed_at',
            'items',
            'total_items', 'items_with_discrepancy', 'total_discrepancy_value'
        ]
        read_only_fields = ['id', 'created_at', 'completed_at']
    
    def get_created_by_name(self, obj):
        return obj.created_by.name if obj.created_by else None
    
    def get_total_items(self, obj):
        return obj.items.count()
    
    def get_items_with_discrepancy(self, obj):
        return obj.items.exclude(discrepancy=0).count()
    
    def get_total_discrepancy_value(self, obj):
        """Calculate total value of discrepancies"""
        from django.db.models import Sum, F
        
        result = obj.items.annotate(
            discrepancy_value=F('discrepancy') * F('stock_product__landed_unit_cost')
        ).aggregate(total=Sum('discrepancy_value'))
        
        return result['total'] or Decimal('0.00')
    
    def validate(self, data):
        """Validate stock count"""
        request = self.context.get('request')
        
        # Set business from user's membership
        if request and not data.get('business'):
            membership = BusinessMembership.objects.filter(
                user=request.user,
                is_active=True
            ).first()
            if membership:
                data['business'] = membership.business
        
        # Set created_by
        if request and not data.get('created_by'):
            data['created_by'] = request.user
        
        # Validate location belongs to business
        storefront = data.get('storefront')
        warehouse = data.get('warehouse')
        business = data.get('business')
        
        if storefront and business:
            # Check via business_link relationship
            if hasattr(storefront, 'business_link') and storefront.business_link:
                if storefront.business_link.business != business:
                    raise serializers.ValidationError("Storefront does not belong to this business")
        
        if warehouse and business:
            # Check via business_link relationship
            if hasattr(warehouse, 'business_link') and warehouse.business_link:
                if warehouse.business_link.business != business:
                    raise serializers.ValidationError("Warehouse does not belong to this business")
        
        return data


class StockAdjustmentSummarySerializer(serializers.Serializer):
    """Serializer for adjustment summary statistics"""
    
    total_adjustments = serializers.IntegerField()
    total_increase = serializers.IntegerField()
    total_decrease = serializers.IntegerField()
    total_cost_impact = serializers.DecimalField(max_digits=12, decimal_places=2)
    
    # Breakdown by type
    by_type = serializers.ListField(
        child=serializers.DictField()
    )


class ShrinkageSummarySerializer(serializers.Serializer):
    """Serializer for shrinkage summary"""
    
    units = serializers.IntegerField()
    cost = serializers.DecimalField(max_digits=12, decimal_places=2)
