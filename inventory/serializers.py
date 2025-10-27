from decimal import Decimal
from django.db.models import Sum
from rest_framework import serializers

from .models import (
    Category,
    Warehouse,
    StoreFront,
    Product,
    Supplier,
    Stock,
    StockProduct,
    TransferRequest,
    TransferRequestLineItem,
    StockAlert,
    BusinessWarehouse,
    BusinessStoreFront,
    StoreFrontEmployee,
    WarehouseEmployee,
)


class CategorySerializer(serializers.ModelSerializer):
    children = serializers.StringRelatedField(many=True, read_only=True)

    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'parent', 'children', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class WarehouseSerializer(serializers.ModelSerializer):
    manager_name = serializers.CharField(source='manager.name', read_only=True)
    business_id = serializers.SerializerMethodField()
    business_name = serializers.SerializerMethodField()

    class Meta:
        model = Warehouse
        fields = [
            'id', 'name', 'location', 'manager', 'manager_name',
            'business_id', 'business_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'manager_name', 'business_id', 'business_name']

    def get_business_id(self, obj):
        link = getattr(obj, 'business_link', None)
        return str(link.business_id) if link and link.business_id else None

    def get_business_name(self, obj):
        link = getattr(obj, 'business_link', None)
        business = getattr(link, 'business', None)
        return business.name if business else None


class StoreFrontSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='user.name', read_only=True)
    manager_name = serializers.CharField(source='manager.name', read_only=True)
    business_id = serializers.SerializerMethodField()
    business_name = serializers.SerializerMethodField()

    class Meta:
        model = StoreFront
        fields = [
            'id', 'user', 'owner_name', 'name', 'location', 'manager', 'manager_name',
            'business_id', 'business_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at', 'owner_name', 'manager_name', 'business_id', 'business_name']

    def get_business_id(self, obj):
        link = getattr(obj, 'business_link', None)
        return str(link.business_id) if link and link.business_id else None

    def get_business_name(self, obj):
        link = getattr(obj, 'business_link', None)
        business = getattr(link, 'business', None)
        return business.name if business else None


class SupplierSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(source='business.name', read_only=True)

    class Meta:
        model = Supplier
        fields = [
            'id', 'business', 'business_name', 'name', 'contact_person', 'email',
            'phone_number', 'address', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'business_name']


class ProductSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(source='business.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'business', 'business_name', 'name', 'sku', 'barcode', 'description',
            'category', 'category_name', 'unit', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'business_name', 'category_name']


class StockProductSerializer(serializers.ModelSerializer):
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    landed_unit_cost = serializers.SerializerMethodField()
    total_base_cost = serializers.SerializerMethodField()
    total_tax_amount = serializers.SerializerMethodField()
    total_additional_cost = serializers.SerializerMethodField()
    total_landed_cost = serializers.SerializerMethodField()
    expected_profit_amount = serializers.SerializerMethodField()
    expected_profit_margin = serializers.SerializerMethodField()
    expected_total_profit = serializers.SerializerMethodField()
    projected_retail_profit = serializers.SerializerMethodField()
    projected_wholesale_profit = serializers.SerializerMethodField()

    class Meta:
        model = StockProduct
        fields = [
            'id', 'stock', 'warehouse', 'warehouse_name', 'product', 'product_name', 'product_sku',
            'supplier', 'supplier_name', 'expiry_date', 'quantity', 'unit_cost', 'unit_tax_rate',
            'unit_tax_amount', 'unit_additional_cost', 'retail_price', 'wholesale_price',
            'description', 'landed_unit_cost', 'total_base_cost', 'total_tax_amount',
            'total_additional_cost', 'total_landed_cost', 'expected_profit_amount',
            'expected_profit_margin', 'expected_total_profit', 'projected_retail_profit',
            'projected_wholesale_profit', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'warehouse_name', 'product_name', 'product_sku', 'supplier_name',
            'landed_unit_cost', 'total_base_cost', 'total_tax_amount', 'total_additional_cost',
            'total_landed_cost', 'expected_profit_amount', 'expected_profit_margin',
            'expected_total_profit', 'projected_retail_profit', 'projected_wholesale_profit',
            'created_at', 'updated_at'
        ]

    def get_landed_unit_cost(self, obj):
        return obj.landed_unit_cost

    def get_total_base_cost(self, obj):
        return obj.total_base_cost

    def get_total_tax_amount(self, obj):
        return obj.total_tax_amount

    def get_total_additional_cost(self, obj):
        return obj.total_additional_cost

    def get_total_landed_cost(self, obj):
        return obj.total_landed_cost

    def get_expected_profit_amount(self, obj):
        return obj.expected_profit_amount

    def get_expected_profit_margin(self, obj):
        return obj.expected_profit_margin

    def get_expected_total_profit(self, obj):
        return obj.expected_total_profit

    def get_projected_retail_profit(self, obj):
        """Calculate total profit if all units sold at retail price"""
        if not obj.retail_price or obj.retail_price <= Decimal('0.00'):
            return Decimal('0.00')
        profit_per_unit = obj.retail_price - obj.landed_unit_cost
        return profit_per_unit * obj.quantity

    def get_projected_wholesale_profit(self, obj):
        """Calculate total profit if all units sold at wholesale price"""
        if not obj.wholesale_price or obj.wholesale_price <= Decimal('0.00'):
            return Decimal('0.00')
        profit_per_unit = obj.wholesale_price - obj.landed_unit_cost
        return profit_per_unit * obj.quantity


class StockSerializer(serializers.ModelSerializer):
    items = StockProductSerializer(many=True, read_only=True)
    warehouse_id = serializers.SerializerMethodField()
    warehouse_name = serializers.SerializerMethodField()
    total_items = serializers.SerializerMethodField()
    total_quantity = serializers.SerializerMethodField()

    class Meta:
        model = Stock
        fields = [
            'id', 'arrival_date', 'description', 'warehouse_id', 'warehouse_name',
            'total_items', 'total_quantity', 'items', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'warehouse_id', 'warehouse_name', 'total_items', 'total_quantity', 'items']

    def _prefetched_items(self, obj):
        cache = getattr(obj, '_prefetched_objects_cache', {})
        if 'items' in cache:
            return cache['items']
        return None

    def _primary_item(self, obj):
        prefetched = self._prefetched_items(obj)
        if prefetched is not None:
            return prefetched[0] if prefetched else None
        return obj.items.select_related('warehouse').first()

    def get_warehouse_id(self, obj):
        item = self._primary_item(obj)
        return str(item.warehouse_id) if item and item.warehouse_id else None

    def get_warehouse_name(self, obj):
        item = self._primary_item(obj)
        return item.warehouse.name if item and item.warehouse else None

    def get_total_items(self, obj):
        prefetched = self._prefetched_items(obj)
        if prefetched is not None:
            return len(prefetched)
        return obj.items.count()

    def get_total_quantity(self, obj):
        prefetched = self._prefetched_items(obj)
        if prefetched is not None:
            return sum(item.quantity for item in prefetched)
        return obj.items.aggregate(total=Sum('quantity'))['total'] or 0


class StorefrontSaleProductSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    product_name = serializers.CharField()
    sku = serializers.CharField()
    category_name = serializers.CharField(allow_null=True)
    available_quantity = serializers.IntegerField()
    retail_price = serializers.DecimalField(max_digits=12, decimal_places=2)
    wholesale_price = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    stock_product_ids = serializers.ListField(child=serializers.UUIDField())
    last_stocked_at = serializers.DateTimeField(allow_null=True)


class TransferRequestLineItemSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(required=False)
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    _destroy = serializers.BooleanField(required=False, write_only=True, default=False)

    class Meta:
        model = TransferRequestLineItem
        fields = [
            'id', 'product', 'product_name', 'product_sku', 'requested_quantity',
            'unit_of_measure', 'notes', '_destroy', 'created_at', 'updated_at'
        ]
        read_only_fields = ['product_name', 'product_sku', 'created_at', 'updated_at']
        extra_kwargs = {
            'id': {'required': False, 'read_only': False},
        }


class TransferRequestSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(source='business.name', read_only=True)
    storefront_name = serializers.CharField(source='storefront.name', read_only=True)
    storefront_location = serializers.CharField(source='storefront.location', read_only=True)
    requested_by_name = serializers.CharField(source='requested_by.name', read_only=True)
    fulfilled_by_name = serializers.CharField(source='fulfilled_by.name', read_only=True)
    cancelled_by_name = serializers.CharField(source='cancelled_by.name', read_only=True)
    line_items = TransferRequestLineItemSerializer(many=True, required=False)

    class Meta:
        model = TransferRequest
        fields = [
            'id', 'business', 'business_name', 'storefront', 'storefront_name', 'storefront_location',
            'priority', 'status', 'notes', 'requested_by', 'requested_by_name',
            'fulfilled_at', 'fulfilled_by', 'fulfilled_by_name',
            'cancelled_at', 'cancelled_by', 'cancelled_by_name',
            'line_items', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'business', 'business_name', 'requested_by', 'requested_by_name',
            'fulfilled_at', 'fulfilled_by', 'fulfilled_by_name',
            'cancelled_at', 'cancelled_by', 'cancelled_by_name',
            'created_at', 'updated_at'
        ]

    def validate(self, attrs):
        storefront = attrs.get('storefront') or getattr(self.instance, 'storefront', None)
        business = attrs.get('business') or getattr(self.instance, 'business', None)
        if storefront:
            link = getattr(storefront, 'business_link', None)
            if not link or not link.business_id:
                raise serializers.ValidationError({'storefront': 'Storefront must belong to an active business.'})
            if business and link.business_id != business.id:
                raise serializers.ValidationError({'storefront': 'Storefront must belong to the provided business.'})
            attrs.setdefault('business', link.business)
        elif not storefront and not business and not getattr(self.instance, 'storefront_id', None):
            raise serializers.ValidationError({'storefront': 'This field is required.'})

        return attrs

    def create(self, validated_data):
        line_items_data = validated_data.pop('line_items', [])
        transfer_request = TransferRequest.objects.create(**validated_data)
        self._sync_line_items(transfer_request, line_items_data)
        return transfer_request

    def update(self, instance, validated_data):
        line_items_data = validated_data.pop('line_items', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if line_items_data is not None:
            self._sync_line_items(instance, line_items_data)

        return instance

    def _sync_line_items(self, transfer_request: TransferRequest, line_items_data):
        if line_items_data is None:
            return

        existing_items = {str(item.id): item for item in transfer_request.line_items.all()}
        seen_ids = set()

        for item in line_items_data:
            item_data = dict(item)
            destroy = item_data.pop('_destroy', False)
            item_id = item_data.pop('id', None)
            item_id = str(item_id) if item_id else None

            if destroy:
                if item_id and item_id in existing_items:
                    existing_items[item_id].delete()
                continue

            product = item_data.get('product')
            if product is None:
                raise serializers.ValidationError({'line_items': 'Each line item must include a product.'})
            if transfer_request.business_id and product.business_id != transfer_request.business_id:
                raise serializers.ValidationError({'line_items': f'Product {product.name} does not belong to the request business.'})

            requested_quantity = item_data.get('requested_quantity')
            if requested_quantity is None or requested_quantity <= 0:
                raise serializers.ValidationError({'line_items': 'Requested quantity must be greater than zero.'})

            if item_id and item_id in existing_items:
                line = existing_items[item_id]
                line.product = product
                line.requested_quantity = requested_quantity
                line.unit_of_measure = item_data.get('unit_of_measure')
                line.notes = item_data.get('notes')
                line.save(update_fields=['product', 'requested_quantity', 'unit_of_measure', 'notes', 'updated_at'])
                seen_ids.add(item_id)
            else:
                TransferRequestLineItem.objects.create(
                    request=transfer_request,
                    product=product,
                    requested_quantity=requested_quantity,
                    unit_of_measure=item_data.get('unit_of_measure'),
                    notes=item_data.get('notes'),
                )

        # Do not delete untouched items unless explicitly requested via _destroy


class StockAlertSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)

    class Meta:
        model = StockAlert
        fields = [
            'id', 'product', 'product_name', 'product_sku', 'warehouse', 'warehouse_name',
            'alert_type', 'current_quantity', 'threshold_quantity', 'is_resolved',
            'resolved_at', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'resolved_at']


class BusinessWarehouseSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(source='business.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)

    class Meta:
        model = BusinessWarehouse
        fields = [
            'id', 'business', 'business_name', 'warehouse', 'warehouse_name',
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'business_name', 'warehouse_name']


class BusinessStoreFrontSerializer(serializers.ModelSerializer):
    business_name = serializers.CharField(source='business.name', read_only=True)
    storefront_name = serializers.CharField(source='storefront.name', read_only=True)
    owner_name = serializers.CharField(source='storefront.user.name', read_only=True)

    class Meta:
        model = BusinessStoreFront
        fields = [
            'id', 'business', 'business_name', 'storefront', 'storefront_name',
            'owner_name', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'business_name', 'storefront_name', 'owner_name']


class StoreFrontEmployeeSerializer(serializers.ModelSerializer):
    storefront_name = serializers.CharField(source='storefront.name', read_only=True)
    user_name = serializers.CharField(source='user.name', read_only=True)
    business_name = serializers.CharField(source='business.name', read_only=True)

    class Meta:
        model = StoreFrontEmployee
        fields = [
            'id', 'business', 'business_name', 'storefront', 'storefront_name',
            'user', 'user_name', 'role', 'is_active', 'assigned_at', 'removed_at'
        ]
        read_only_fields = ['id', 'assigned_at', 'removed_at', 'business_name', 'storefront_name', 'user_name']


class WarehouseEmployeeSerializer(serializers.ModelSerializer):
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    user_name = serializers.CharField(source='user.name', read_only=True)
    business_name = serializers.CharField(source='business.name', read_only=True)

    class Meta:
        model = WarehouseEmployee
        fields = [
            'id', 'business', 'business_name', 'warehouse', 'warehouse_name',
            'user', 'user_name', 'role', 'is_active', 'assigned_at', 'removed_at'
        ]
        read_only_fields = ['id', 'assigned_at', 'removed_at', 'business_name', 'warehouse_name', 'user_name']


# Specialized serializers for specific use cases
class InventorySummarySerializer(serializers.Serializer):
    """Serializer for inventory summary reports"""
    product_id = serializers.UUIDField()
    product_name = serializers.CharField()
    product_sku = serializers.CharField()
    total_quantity = serializers.IntegerField()
    warehouse_count = serializers.IntegerField()
    last_updated = serializers.DateTimeField()


class StockArrivalReportSerializer(serializers.Serializer):
    """Serializer for stock arrival reports"""
    warehouse_id = serializers.UUIDField()
    warehouse_name = serializers.CharField()
    arrival_date = serializers.DateField()
    stock_count = serializers.IntegerField()
    total_quantity = serializers.IntegerField()
    suppliers = serializers.ListField(child=serializers.CharField())


class ProfitProjectionSerializer(serializers.Serializer):
    """Serializer for profit projection requests"""
    retail_percentage = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=0, max_value=100,
        help_text="Percentage of units expected to be sold at retail price (0-100)"
    )
    wholesale_percentage = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=0, max_value=100,
        help_text="Percentage of units expected to be sold at wholesale price (0-100)"
    )

    def validate(self, data):
        retail_pct = data.get('retail_percentage', 0)
        wholesale_pct = data.get('wholesale_percentage', 0)

        if retail_pct + wholesale_pct != 100:
            raise serializers.ValidationError(
                "Retail and wholesale percentages must sum to 100%"
            )

        return data


class ProfitScenarioSerializer(serializers.Serializer):
    """Serializer for individual profit scenarios"""
    scenario = serializers.CharField(read_only=True)
    description = serializers.CharField(read_only=True)
    retail_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    wholesale_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    retail_units = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    wholesale_units = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    avg_selling_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    profit_per_unit = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    profit_margin = serializers.DecimalField(max_digits=5, decimal_places=2, read_only=True)
    total_profit = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)


class StockProductProfitProjectionSerializer(serializers.Serializer):
    """Serializer for stock product profit projections"""
    stock_product_id = serializers.UUIDField(read_only=True)
    product_name = serializers.CharField(read_only=True)
    product_sku = serializers.CharField(read_only=True)
    quantity = serializers.IntegerField(read_only=True)
    landed_unit_cost = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    retail_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    wholesale_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    requested_scenario = ProfitScenarioSerializer(read_only=True)
    retail_only = ProfitScenarioSerializer(read_only=True)
    wholesale_only = ProfitScenarioSerializer(read_only=True)
    mixed_scenarios = ProfitScenarioSerializer(many=True, read_only=True)


class ProductProfitProjectionSerializer(serializers.Serializer):
    """Serializer for product-level profit projections (across all stock products)"""
    product_id = serializers.UUIDField(read_only=True)
    product_name = serializers.CharField(read_only=True)
    product_sku = serializers.CharField(read_only=True)
    total_quantity = serializers.IntegerField(read_only=True)
    stock_products_count = serializers.IntegerField(read_only=True)
    requested_scenario = serializers.DictField(read_only=True)
    retail_only = serializers.DictField(read_only=True)
    wholesale_only = serializers.DictField(read_only=True)


class BulkProfitProjectionSerializer(serializers.Serializer):
    """Serializer for bulk profit projection requests"""
    projections = serializers.ListField(
        child=serializers.DictField(),
        help_text="List of projection requests with stock_product_id and retail_percentage/wholesale_percentage"
    )

    def validate_projections(self, value):
        if not value:
            raise serializers.ValidationError("At least one projection must be provided")

        for i, projection in enumerate(value):
            if 'stock_product_id' not in projection:
                raise serializers.ValidationError(f"Projection {i}: stock_product_id is required")

            retail_pct = projection.get('retail_percentage', 100)
            wholesale_pct = projection.get('wholesale_percentage', 0)

            if retail_pct + wholesale_pct != 100:
                raise serializers.ValidationError(
                    f"Projection {i}: retail_percentage + wholesale_percentage must equal 100"
                )

        return value


class BulkProfitProjectionResponseSerializer(serializers.Serializer):
    """Serializer for bulk profit projection responses"""
    projections = StockProductProfitProjectionSerializer(many=True, read_only=True)