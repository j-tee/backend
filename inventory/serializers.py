from rest_framework import serializers
from .models import (
    Category, Warehouse, StoreFront, Product, Stock,
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


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = Product
        fields = [
            'id', 'name', 'sku', 'description', 'category', 'category_name',
            'unit', 'retail_price', 'wholesale_price', 'cost', 'is_active',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class StockSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    landed_unit_cost = serializers.DecimalField(source='landed_unit_cost', max_digits=12, decimal_places=2, read_only=True)
    total_tax_amount = serializers.DecimalField(source='total_tax_amount', max_digits=14, decimal_places=2, read_only=True)
    total_additional_cost = serializers.DecimalField(source='total_additional_cost', max_digits=14, decimal_places=2, read_only=True)
    total_landed_cost = serializers.DecimalField(source='total_landed_cost', max_digits=14, decimal_places=2, read_only=True)
    
    class Meta:
        model = Stock
        fields = [
            'id', 'warehouse', 'warehouse_name', 'product', 'product_name', 'product_sku',
            'supplier', 'reference_code', 'arrival_date', 'expiry_date',
            'quantity', 'unit_cost', 'unit_tax_rate', 'unit_tax_amount', 'unit_additional_cost',
            'landed_unit_cost', 'total_tax_amount', 'total_additional_cost', 'total_landed_cost',
            'description', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class InventorySerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    stock_reference_code = serializers.CharField(source='stock.reference_code', read_only=True)
    stock_supplier = serializers.CharField(source='stock.supplier', read_only=True)
    stock_expiry_date = serializers.DateField(source='stock.expiry_date', read_only=True)
    stock_unit_cost = serializers.DecimalField(source='stock.unit_cost', max_digits=12, decimal_places=2, read_only=True)
    stock_landed_unit_cost = serializers.DecimalField(source='stock.landed_unit_cost', max_digits=12, decimal_places=2, read_only=True)
    stock_total_tax_amount = serializers.DecimalField(source='stock.total_tax_amount', max_digits=14, decimal_places=2, read_only=True)
    stock_total_landed_cost = serializers.DecimalField(source='stock.total_landed_cost', max_digits=14, decimal_places=2, read_only=True)
    
    class Meta:
        model = Inventory
        fields = [
            'id', 'product', 'product_name', 'product_sku', 'stock', 'stock_reference_code',
            'stock_supplier', 'stock_expiry_date', 'stock_unit_cost', 'stock_landed_unit_cost',
            'stock_total_tax_amount', 'stock_total_landed_cost', 'warehouse', 'warehouse_name',
            'quantity', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TransferSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    from_warehouse_name = serializers.CharField(source='from_warehouse.name', read_only=True)
    to_storefront_name = serializers.CharField(source='to_storefront.name', read_only=True)
    requested_by_name = serializers.CharField(source='requested_by.name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.name', read_only=True)
    stock_reference_code = serializers.CharField(source='stock.reference_code', read_only=True)
    stock_supplier = serializers.CharField(source='stock.supplier', read_only=True)
    stock_expiry_date = serializers.DateField(source='stock.expiry_date', read_only=True)
    stock_landed_unit_cost = serializers.DecimalField(source='stock.landed_unit_cost', max_digits=12, decimal_places=2, read_only=True)
    
    class Meta:
        model = Transfer
        fields = [
            'id', 'product', 'product_name', 'product_sku', 'stock', 'stock_reference_code',
            'stock_supplier', 'stock_expiry_date', 'stock_landed_unit_cost', 'from_warehouse', 'from_warehouse_name',
            'to_storefront', 'to_storefront_name', 'quantity', 'status', 'requested_by',
            'requested_by_name', 'approved_by', 'approved_by_name', 'note', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


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