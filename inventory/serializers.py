from decimal import Decimal

from rest_framework import serializers
from .models import (
    Category, Warehouse, StoreFront, Product, Supplier, Stock, StockProduct,
    Inventory, Transfer, StockAlert,
    BusinessWarehouse, BusinessStoreFront, StoreFrontEmployee, WarehouseEmployee
)


class CategorySerializer(serializers.ModelSerializer):
    children = serializers.StringRelatedField(many=True, read_only=True)
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'description', 'parent', 'children', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class WarehouseSerializer(serializers.ModelSerializer):
    manager_name = serializers.CharField(source='manager.name', read_only=True)
    
    class Meta:
        model = Warehouse
        fields = ['id', 'name', 'location', 'manager', 'manager_name', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class StoreFrontSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.name', read_only=True)
    manager_name = serializers.CharField(source='manager.name', read_only=True)
    
    class Meta:
        model = StoreFront
        fields = ['id', 'user', 'user_name', 'name', 'location', 'manager', 'manager_name', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
        extra_kwargs = {
            'user': {'read_only': True},
        }


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'sku', 'description', 'category', 'category_name',
            'unit', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = [
            'id', 'name', 'contact_person', 'email', 'phone_number',
            'address', 'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class StockProductSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    supplier_name = serializers.SerializerMethodField()
    landed_unit_cost = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_tax_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    total_additional_cost = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    total_landed_cost = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    projected_wholesale_profit = serializers.SerializerMethodField()
    projected_retail_profit = serializers.SerializerMethodField()

    class Meta:
        model = StockProduct
        fields = [
            'id', 'stock', 'warehouse_name', 'product', 'product_name', 'product_sku',
            'supplier', 'supplier_name', 'expiry_date', 'quantity', 'unit_cost', 'unit_tax_rate',
            'unit_tax_amount', 'unit_additional_cost', 'retail_price', 'wholesale_price', 'landed_unit_cost', 'total_tax_amount',
            'total_additional_cost', 'total_landed_cost', 'projected_wholesale_profit', 'projected_retail_profit', 'description', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at', 'landed_unit_cost', 'total_tax_amount', 'total_additional_cost',
            'total_landed_cost', 'warehouse_name', 'product_name', 'product_sku', 'supplier_name',
            'projected_wholesale_profit', 'projected_retail_profit'
        ]

    def get_supplier_name(self, obj):
        supplier = obj.supplier or obj.effective_supplier
        return supplier.name if supplier else None

    def _calculate_effective_tax_amount(self, obj) -> Decimal:
        """Calculate the effective tax amount per unit."""
        if obj.unit_tax_amount is not None:
            return obj.unit_tax_amount
        if obj.unit_tax_rate and obj.unit_cost:
            return (obj.unit_cost * obj.unit_tax_rate) / Decimal('100.00')
        return Decimal('0.00')

    def _additional_cost_per_unit(self, obj) -> Decimal:
        return obj.unit_additional_cost or Decimal('0.00')

    def _profit_per_unit(self, selling_price: Decimal, cost_per_unit: Decimal) -> Decimal:
        return selling_price - cost_per_unit

    def _total_profit(self, profit_per_unit: Decimal, quantity: int) -> Decimal:
        return (profit_per_unit * Decimal(quantity)).quantize(Decimal('0.01'))

    def get_projected_wholesale_profit(self, obj):
        if not (obj.wholesale_price and obj.unit_cost and obj.quantity):
            return Decimal('0.00')

        tax_per_unit = self._calculate_effective_tax_amount(obj)
        additional_cost = self._additional_cost_per_unit(obj)
        cost_per_unit = obj.unit_cost + tax_per_unit + additional_cost
        profit_per_unit = self._profit_per_unit(obj.wholesale_price, cost_per_unit)
        return self._total_profit(profit_per_unit, obj.quantity)

    def get_projected_retail_profit(self, obj):
        if not (obj.retail_price and obj.unit_cost and obj.quantity):
            return Decimal('0.00')

        tax_per_unit = self._calculate_effective_tax_amount(obj)
        additional_cost = self._additional_cost_per_unit(obj)
        cost_per_unit = obj.unit_cost + tax_per_unit + additional_cost
        profit_per_unit = self._profit_per_unit(obj.retail_price, cost_per_unit)
        return self._total_profit(profit_per_unit, obj.quantity)


class StockSerializer(serializers.ModelSerializer):
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    items = StockProductSerializer(many=True, read_only=True)

    class Meta:
        model = Stock
        fields = [
            'id', 'warehouse', 'warehouse_name', 'arrival_date', 'description', 'created_at', 'updated_at',
            'items'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'warehouse_name', 'items']


class InventorySerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    stock_arrival_date = serializers.SerializerMethodField()
    stock_supplier = serializers.SerializerMethodField()
    stock_expiry_date = serializers.DateField(source='stock.expiry_date', read_only=True)
    stock_unit_cost = serializers.DecimalField(source='stock.unit_cost', max_digits=12, decimal_places=2, read_only=True)
    stock_landed_unit_cost = serializers.DecimalField(source='stock.landed_unit_cost', max_digits=12, decimal_places=2, read_only=True)
    stock_total_tax_amount = serializers.DecimalField(source='stock.total_tax_amount', max_digits=14, decimal_places=2, read_only=True)
    stock_total_landed_cost = serializers.DecimalField(source='stock.total_landed_cost', max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = Inventory
        fields = [
            'id', 'product', 'product_name', 'product_sku', 'stock', 'stock_arrival_date',
            'stock_supplier', 'stock_expiry_date', 'stock_unit_cost', 'stock_landed_unit_cost',
            'stock_total_tax_amount', 'stock_total_landed_cost', 'warehouse', 'warehouse_name',
            'quantity', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_stock_arrival_date(self, obj):
        if not obj.stock or not obj.stock.stock:
            return None
        arrival = obj.stock.stock.arrival_date
        return arrival.isoformat() if arrival else None

    def get_stock_supplier(self, obj):
        if not obj.stock:
            return None
        supplier = obj.stock.supplier or obj.stock.effective_supplier
        if supplier:
            return supplier.name
        return None


class TransferSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    from_warehouse_name = serializers.CharField(source='from_warehouse.name', read_only=True)
    to_storefront_name = serializers.CharField(source='to_storefront.name', read_only=True)
    requested_by_name = serializers.CharField(source='requested_by.name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.name', read_only=True)
    stock_arrival_date = serializers.SerializerMethodField()
    stock_supplier = serializers.SerializerMethodField()
    stock_expiry_date = serializers.DateField(source='stock.expiry_date', read_only=True)
    stock_landed_unit_cost = serializers.DecimalField(source='stock.landed_unit_cost', max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Transfer
        fields = [
            'id', 'product', 'product_name', 'product_sku', 'stock', 'stock_arrival_date',
            'stock_supplier', 'stock_expiry_date', 'stock_landed_unit_cost', 'from_warehouse', 'from_warehouse_name',
            'to_storefront', 'to_storefront_name', 'quantity', 'status', 'requested_by',
            'requested_by_name', 'approved_by', 'approved_by_name', 'note', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_stock_arrival_date(self, obj):
        if not obj.stock or not obj.stock.stock:
            return None
        arrival = obj.stock.stock.arrival_date
        return arrival.isoformat() if arrival else None

    def get_stock_supplier(self, obj):
        if not obj.stock:
            return None
        supplier = obj.stock.supplier or obj.stock.effective_supplier
        if supplier:
            return supplier.name
        return None


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