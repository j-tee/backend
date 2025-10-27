"""
Transfer API Serializers (Phase 4)

Serializers for the new Transfer system endpoints.
Replaces legacy StockAdjustment TRANSFER_IN/TRANSFER_OUT pairs.
"""

from decimal import Decimal
from rest_framework import serializers
from django.db import transaction
from django.utils import timezone

from inventory.transfer_models import Transfer, TransferItem
from inventory.models import Product, Warehouse, StoreFront


class TransferItemSerializer(serializers.ModelSerializer):
    """Serializer for individual transfer line items"""
    
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True, allow_null=True)
    total_cost = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True
    )
    
    # Make unit_cost optional since we auto-populate from source stock
    unit_cost = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        allow_null=True
    )
    
    class Meta:
        model = TransferItem
        fields = [
            'id',
            'product',
            'product_name',
            'product_sku',
            'quantity',
            'unit_cost',
            'total_cost',
            # Stock batch fields
            'supplier',
            'supplier_name',
            'expiry_date',
            'unit_tax_rate',
            'unit_tax_amount',
            'unit_additional_cost',
            'retail_price',
            'wholesale_price',
        ]
        read_only_fields = ['id', 'total_cost', 'supplier_name']
        extra_kwargs = {
            'supplier': {'required': False},
            'expiry_date': {'required': False},
            'unit_tax_rate': {'required': False},
            'unit_tax_amount': {'required': False},
            'unit_additional_cost': {'required': False},
            'retail_price': {'required': False},
            'wholesale_price': {'required': False},
        }
    
    def validate_quantity(self, value):
        """Ensure quantity is positive"""
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than 0")
        return value
    
    def validate_unit_cost(self, value):
        """Ensure unit cost is non-negative if provided"""
        if value is not None and value < 0:
            raise serializers.ValidationError("Unit cost cannot be negative")
        return value
    
    def validate_retail_price(self, value):
        """Ensure retail price is non-negative"""
        if value and value < 0:
            raise serializers.ValidationError("Retail price cannot be negative")
        return value
    
    def validate_wholesale_price(self, value):
        """Ensure wholesale price is non-negative"""
        if value and value < 0:
            raise serializers.ValidationError("Wholesale price cannot be negative")
        return value


class TransferSerializer(serializers.ModelSerializer):
    """Base serializer for Transfer operations"""
    
    items = TransferItemSerializer(many=True)
    source_warehouse_name = serializers.CharField(
        source='source_warehouse.name',
        read_only=True
    )
    destination_warehouse_name = serializers.CharField(
        source='destination_warehouse.name',
        read_only=True,
        allow_null=True
    )
    destination_storefront_name = serializers.CharField(
        source='destination_storefront.name',
        read_only=True,
        allow_null=True
    )
    created_by_name = serializers.SerializerMethodField()
    completed_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Transfer
        fields = [
            'id',
            'business',
            'reference_number',
            'source_warehouse',
            'source_warehouse_name',
            'destination_warehouse',
            'destination_warehouse_name',
            'destination_storefront',
            'destination_storefront_name',
            'status',
            'expected_arrival_date',
            'notes',
            'items',
            'created_by',
            'created_by_name',
            'created_at',
            'completed_by',
            'completed_by_name',
            'completed_at',
        ]
        read_only_fields = [
            'id',
            'business',
            'reference_number',
            'status',
            'created_by',
            'created_at',
            'completed_by',
            'completed_at',
        ]
    
    def get_created_by_name(self, obj):
        """Get creator's display name"""
        if not obj.created_by:
            return None
        return (getattr(obj.created_by, 'name', None) or 
                getattr(obj.created_by, 'username', None) or 
                str(obj.created_by))
    
    def get_completed_by_name(self, obj):
        """Get completer's display name"""
        if not obj.completed_by:
            return None
        return (getattr(obj.completed_by, 'name', None) or 
                getattr(obj.completed_by, 'username', None) or 
                str(obj.completed_by))
    
    def validate_items(self, value):
        """Ensure at least one item is provided"""
        if not value:
            raise serializers.ValidationError("At least one item is required")
        
        # Check for duplicate products
        product_ids = [item['product'].id for item in value]
        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError("Duplicate products are not allowed")
        
        return value
    
    def validate(self, data):
        """Cross-field validation"""
        # Ensure either destination_warehouse or destination_storefront is set (not both)
        dest_warehouse = data.get('destination_warehouse')
        dest_storefront = data.get('destination_storefront')
        
        if dest_warehouse and dest_storefront:
            raise serializers.ValidationError(
                "Cannot specify both destination_warehouse and destination_storefront"
            )
        
        if not dest_warehouse and not dest_storefront:
            raise serializers.ValidationError(
                "Must specify either destination_warehouse or destination_storefront"
            )
        
        # Prevent self-transfer (warehouse to same warehouse)
        source_warehouse = data.get('source_warehouse')
        if dest_warehouse and source_warehouse == dest_warehouse:
            raise serializers.ValidationError(
                "Source and destination warehouse cannot be the same"
            )
        
        return data
    
    @transaction.atomic
    def create(self, validated_data):
        """Create Transfer with items, auto-populating missing fields from source stock"""
        from inventory.models import StockProduct
        
        items_data = validated_data.pop('items')
        request = self.context.get('request')
        
        # Set business and created_by from request
        if request and hasattr(request, 'user') and hasattr(request.user, 'primary_business'):
            validated_data['business'] = request.user.primary_business
            validated_data['created_by'] = request.user
        
        # Get source warehouse
        source_warehouse = validated_data.get('source_warehouse')
        
        # Create transfer
        transfer = Transfer.objects.create(**validated_data)
        
        # Create items with auto-populated fields from source stock
        for item_data in items_data:
            product = item_data['product']
            
            # Try to get source stock for this product
            source_stock = StockProduct.objects.filter(
                warehouse=source_warehouse,
                product=product,
                quantity__gt=0  # Only consider stocks with available quantity
            ).order_by('-created_at').first()  # Get most recent
            
            # Auto-populate missing fields from source stock
            if source_stock:
                # unit_cost - required field, use source if not provided
                if 'unit_cost' not in item_data or item_data.get('unit_cost') is None:
                    item_data['unit_cost'] = source_stock.unit_cost or Decimal('0.00')
                
                # Optional fields - only populate if not provided
                if 'supplier' not in item_data or item_data.get('supplier') is None:
                    item_data['supplier'] = source_stock.supplier
                
                if 'expiry_date' not in item_data or item_data.get('expiry_date') is None:
                    item_data['expiry_date'] = source_stock.expiry_date
                
                if 'unit_tax_rate' not in item_data or item_data.get('unit_tax_rate') is None:
                    item_data['unit_tax_rate'] = source_stock.unit_tax_rate
                
                if 'unit_tax_amount' not in item_data or item_data.get('unit_tax_amount') is None:
                    item_data['unit_tax_amount'] = source_stock.unit_tax_amount
                
                if 'unit_additional_cost' not in item_data or item_data.get('unit_additional_cost') is None:
                    item_data['unit_additional_cost'] = source_stock.unit_additional_cost
                
                if 'retail_price' not in item_data or item_data.get('retail_price') is None:
                    item_data['retail_price'] = source_stock.retail_price or Decimal('0.00')
                
                if 'wholesale_price' not in item_data or item_data.get('wholesale_price') is None:
                    item_data['wholesale_price'] = source_stock.wholesale_price or Decimal('0.00')
            else:
                # No source stock found - ensure required fields have defaults
                if 'unit_cost' not in item_data or item_data.get('unit_cost') is None:
                    item_data['unit_cost'] = Decimal('0.00')
                if 'retail_price' not in item_data or item_data.get('retail_price') is None:
                    item_data['retail_price'] = Decimal('0.00')
                if 'wholesale_price' not in item_data or item_data.get('wholesale_price') is None:
                    item_data['wholesale_price'] = Decimal('0.00')
            
            # Calculate total_cost
            item_data['total_cost'] = (item_data.get('unit_cost') or Decimal('0.00')) * item_data['quantity']
            
            # Create the transfer item
            item = TransferItem(transfer=transfer, **item_data)
            item.save(skip_validation=True)
        
        return transfer


class WarehouseTransferSerializer(TransferSerializer):
    """Serializer for warehouse-to-warehouse transfers"""
    
    class Meta(TransferSerializer.Meta):
        fields = [
            'id',
            'business',
            'reference_number',
            'source_warehouse',
            'source_warehouse_name',
            'destination_warehouse',
            'destination_warehouse_name',
            'status',
            'notes',
            'items',
            'created_by',
            'created_by_name',
            'created_at',
            'completed_by',
            'completed_by_name',
            'completed_at',
        ]
    
    def validate(self, data):
        """Ensure destination_warehouse is set"""
        if not data.get('destination_warehouse'):
            raise serializers.ValidationError({
                'destination_warehouse': 'This field is required for warehouse transfers'
            })
        
        # Remove destination_storefront if present
        data.pop('destination_storefront', None)
        
        # Call parent validation
        return super().validate(data)
    
    def create(self, validated_data):
        """Set transfer_type for warehouse-to-warehouse transfers"""
        from inventory.transfer_models import Transfer
        validated_data['transfer_type'] = Transfer.TYPE_WAREHOUSE_TO_WAREHOUSE
        return super().create(validated_data)


class StorefrontTransferSerializer(TransferSerializer):
    """Serializer for warehouse-to-storefront transfers"""
    
    class Meta(TransferSerializer.Meta):
        fields = [
            'id',
            'business',
            'reference_number',
            'source_warehouse',
            'source_warehouse_name',
            'destination_storefront',
            'destination_storefront_name',
            'status',
            'notes',
            'items',
            'created_by',
            'created_by_name',
            'created_at',
            'completed_by',
            'completed_by_name',
            'completed_at',
        ]
    
    def validate(self, data):
        """Ensure destination_storefront is set"""
        if not data.get('destination_storefront'):
            raise serializers.ValidationError({
                'destination_storefront': 'This field is required for storefront transfers'
            })
        
        # Remove destination_warehouse if present
        data.pop('destination_warehouse', None)
        
        # Call parent validation
        return super().validate(data)
    
    def create(self, validated_data):
        """Set transfer_type for warehouse-to-storefront transfers"""
        from inventory.transfer_models import Transfer
        validated_data['transfer_type'] = Transfer.TYPE_WAREHOUSE_TO_STOREFRONT
        return super().create(validated_data)


class TransferCompleteSerializer(serializers.Serializer):
    """Serializer for completing a transfer"""
    
    notes = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=500,
        help_text="Optional notes about the completion"
    )
    
    def validate(self, data):
        """Validate transfer can be completed"""
        transfer = self.instance
        
        if transfer.status == 'completed':
            raise serializers.ValidationError("Transfer is already completed")
        
        if transfer.status == 'cancelled':
            raise serializers.ValidationError("Cannot complete a cancelled transfer")
        
        return data
    
    def save(self):
        """Complete the transfer"""
        transfer = self.instance
        request = self.context.get('request')
        notes = self.validated_data.get('notes', '')
        
        # Append completion notes if provided
        if notes:
            if transfer.notes:
                transfer.notes = f"{transfer.notes}\n\nCompletion notes: {notes}"
            else:
                transfer.notes = f"Completion notes: {notes}"
        
        # Complete transfer
        user = request.user if request and hasattr(request, 'user') else None
        transfer.complete_transfer(completed_by=user)
        
        return transfer


class TransferCancelSerializer(serializers.Serializer):
    """Serializer for cancelling a transfer"""
    
    reason = serializers.CharField(
        required=True,
        max_length=500,
        help_text="Reason for cancellation"
    )
    
    def validate(self, data):
        """Validate transfer can be cancelled"""
        transfer = self.instance
        
        if transfer.status == 'completed':
            raise serializers.ValidationError("Cannot cancel a completed transfer")
        
        if transfer.status == 'cancelled':
            raise serializers.ValidationError("Transfer is already cancelled")
        
        return data
    
    def save(self):
        """Cancel the transfer"""
        transfer = self.instance
        reason = self.validated_data['reason']
        
        # Append cancellation reason to notes
        cancellation_note = f"Cancelled: {reason}"
        if transfer.notes:
            transfer.notes = f"{transfer.notes}\n\n{cancellation_note}"
        else:
            transfer.notes = cancellation_note
        
        # Cancel transfer
        transfer.cancel_transfer()
        
        return transfer
