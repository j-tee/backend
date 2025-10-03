from decimal import Decimal

from rest_framework import serializers
from .models import (
    Category, Warehouse, StoreFront, Product, Supplier, Stock, StockProduct,
    Inventory, StoreFrontInventory, Transfer, TransferLineItem, TransferAuditEntry, TransferRequest,
    TransferRequestLineItem, StockAlert,
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

class TransferAuditEntrySerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.name', read_only=True)

    class Meta:
        model = TransferAuditEntry
        fields = ['id', 'action', 'actor', 'actor_name', 'remarks', 'created_at']
        read_only_fields = fields


class TransferLineItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    _destroy = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = TransferLineItem
        fields = [
            'id', 'product', 'product_name', 'product_sku', 'requested_quantity',
            'approved_quantity', 'fulfilled_quantity', 'unit_of_measure', 'notes', '_destroy'
        ]
        read_only_fields = ['id', 'product_name', 'product_sku']

    def validate_requested_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError('Requested quantity must be greater than zero.')
        return value


class TransferRequestLineItemSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source='product.name', read_only=True)
    sku = serializers.CharField(source='product.sku', read_only=True)
    _destroy = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = TransferRequestLineItem
        fields = [
            'id', 'product', 'product_name', 'sku', 'requested_quantity',
            'unit_of_measure', 'notes', '_destroy'
        ]
        read_only_fields = ['id', 'product_name', 'sku']

    def validate_requested_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError('Requested quantity must be greater than zero.')
        return value


class TransferRequestSerializer(serializers.ModelSerializer):
    storefront_name = serializers.CharField(source='storefront.name', read_only=True)
    requested_by_name = serializers.CharField(source='requested_by.name', read_only=True)
    cancelled_by_name = serializers.CharField(source='cancelled_by.name', read_only=True, allow_null=True)
    linked_transfer = serializers.UUIDField(source='linked_transfer_id', allow_null=True, required=False)
    line_items = TransferRequestLineItemSerializer(many=True)

    class Meta:
        model = TransferRequest
        fields = [
            'id', 'business', 'storefront', 'storefront_name',
            'requested_by', 'requested_by_name',
            'priority', 'status', 'notes', 'linked_transfer', 'linked_transfer_reference',
            'assigned_at', 'fulfilled_at', 'fulfilled_by', 'cancelled_at', 'cancelled_by', 'cancelled_by_name',
            'created_at', 'updated_at', 'line_items'
        ]
        read_only_fields = [
            'id', 'business', 'requested_by', 'requested_by_name', 'cancelled_by_name', 'status',
            'linked_transfer_reference', 'assigned_at', 'fulfilled_at', 'fulfilled_by',
            'cancelled_at', 'cancelled_by', 'created_at', 'updated_at'
        ]

    def validate(self, attrs):
        storefront = attrs.get('storefront') or getattr(self.instance, 'storefront', None)

        if storefront:
            link = getattr(storefront, 'business_link', None)
            if not link:
                raise serializers.ValidationError({'storefront': 'Storefront must belong to an active business.'})
            attrs['business'] = link.business

        return super().validate(attrs)

    def _sync_line_items(self, request: TransferRequest, line_items_data):
        existing = {str(item.id): item for item in request.line_items.all()}
        seen = set()

        for item_data in line_items_data:
            destroy = item_data.pop('_destroy', False)
            item_id = item_data.get('id')
            item_id = str(item_id) if item_id else None

            if destroy:
                if item_id and item_id in existing:
                    existing[item_id].delete()
                    existing.pop(item_id, None)
                continue

            product = item_data.get('product')
            if product.business_id != request.business_id:
                raise serializers.ValidationError({'line_items': 'Products must belong to the request business.'})

            if item_id and item_id in existing:
                line = existing[item_id]
                for field in ['product', 'requested_quantity', 'unit_of_measure', 'notes']:
                    if field in item_data:
                        setattr(line, field, item_data[field])
                line.save()
                seen.add(item_id)
            else:
                TransferRequestLineItem.objects.create(request=request, **item_data)

        for item_id, line in existing.items():
            if item_id not in seen:
                line.delete()

    def create(self, validated_data):
        line_items_data = validated_data.pop('line_items', [])
        linked_transfer_id = validated_data.pop('linked_transfer_id', None)
        if not line_items_data:
            raise serializers.ValidationError({'line_items': 'At least one line item is required.'})

        request_user = getattr(self.context.get('request'), 'user', None)
        if request_user and not validated_data.get('requested_by'):
            validated_data['requested_by'] = request_user

        transfer_request = TransferRequest.objects.create(**validated_data)
        self._sync_line_items(transfer_request, line_items_data)

        if linked_transfer_id:
            self._update_linked_transfer(transfer_request, linked_transfer_id)

        return transfer_request

    def update(self, instance, validated_data):
        line_items_data = validated_data.pop('line_items', None)
        linked_transfer_id = validated_data.pop('linked_transfer_id', serializers.empty)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if line_items_data is not None:
            self._sync_line_items(instance, line_items_data)

        if linked_transfer_id is not serializers.empty:
            self._update_linked_transfer(instance, linked_transfer_id)

        return instance

    def _update_linked_transfer(self, instance: TransferRequest, linked_transfer_id):
        if linked_transfer_id:
            try:
                transfer = Transfer.objects.select_related('destination_storefront', 'business').get(id=linked_transfer_id)
            except Transfer.DoesNotExist as exc:
                raise serializers.ValidationError({'linked_transfer': 'Transfer not found.'}) from exc

            if transfer.business_id != instance.business_id:
                raise serializers.ValidationError({'linked_transfer': 'Transfer must belong to the same business as the request.'})
            if transfer.destination_storefront_id != instance.storefront_id:
                raise serializers.ValidationError({'linked_transfer': 'Transfer destination must match the request storefront.'})

            transfer.request = instance
            transfer.save(update_fields=['request', 'updated_at'])
            instance.mark_assigned(transfer)
        else:
            transfer = instance._current_transfer()
            if transfer:
                transfer.request = None
                transfer.save(update_fields=['request', 'updated_at'])
            instance.clear_assignment()


class TransferSerializer(serializers.ModelSerializer):
    source_warehouse_name = serializers.CharField(source='source_warehouse.name', read_only=True)
    destination_storefront_name = serializers.CharField(source='destination_storefront.name', read_only=True)
    requested_by_name = serializers.CharField(source='requested_by.name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.name', read_only=True)
    fulfilled_by_name = serializers.CharField(source='fulfilled_by.name', read_only=True)
    received_by_name = serializers.CharField(source='received_by.name', read_only=True)
    line_items = TransferLineItemSerializer(many=True, required=False)
    audit_log = TransferAuditEntrySerializer(source='audit_entries', many=True, read_only=True)
    request_id = serializers.UUIDField(required=False, allow_null=True)
    request_reference = serializers.SerializerMethodField()

    class Meta:
        model = Transfer
        fields = [
            'id', 'reference', 'business', 'status', 'source_warehouse', 'source_warehouse_name',
            'destination_storefront', 'destination_storefront_name', 'notes', 'requested_by',
            'requested_by_name', 'approved_by', 'approved_by_name', 'fulfilled_by', 'fulfilled_by_name',
            'received_by', 'received_by_name', 'submitted_at', 'approved_at', 'dispatched_at',
            'completed_at', 'received_at', 'rejected_at', 'cancelled_at', 'request_id', 'request_reference',
            'line_items', 'audit_log', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'reference', 'business', 'status', 'requested_by', 'requested_by_name',
            'approved_by', 'approved_by_name', 'fulfilled_by', 'fulfilled_by_name', 'received_by', 'received_by_name',
            'submitted_at', 'approved_at', 'dispatched_at', 'completed_at', 'received_at',
            'rejected_at', 'cancelled_at', 'audit_log', 'created_at', 'updated_at', 'request_reference'
        ]

    def _get_business_from_warehouse(self, warehouse: Warehouse):
        link = getattr(warehouse, 'business_link', None)
        if not link:
            raise serializers.ValidationError({'source_warehouse': 'Warehouse is not linked to a business.'})
        return link.business

    def validate(self, attrs):
        warehouse = attrs.get('source_warehouse') or getattr(self.instance, 'source_warehouse', None)
        storefront = attrs.get('destination_storefront') or getattr(self.instance, 'destination_storefront', None)

        if not warehouse or not storefront:
            return attrs

        business = self._get_business_from_warehouse(warehouse)
        storefront_link = getattr(storefront, 'business_link', None)
        if not storefront_link or storefront_link.business_id != business.id:
            raise serializers.ValidationError({'destination_storefront': 'Storefront must belong to the same business as the warehouse.'})

        attrs['business'] = business
        return attrs

    def create(self, validated_data):
        line_items_data = validated_data.pop('line_items', [])
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user and not validated_data.get('requested_by'):
            validated_data['requested_by'] = user

        request_id = validated_data.pop('request_id', None)
        transfer_request = None
        destination_storefront = validated_data.get('destination_storefront')
        if request_id:
            transfer_request = self._resolve_transfer_request(request_id, destination_storefront)
            validated_data['request'] = transfer_request

        if not line_items_data and transfer_request:
            request_line_items = list(transfer_request.line_items.select_related('product'))
            if not request_line_items:
                raise serializers.ValidationError({'line_items': 'Linked request has no line items to clone.'})
            line_items_data = [
                {
                    'product': item.product,
                    'requested_quantity': item.requested_quantity,
                    'unit_of_measure': item.unit_of_measure,
                    'notes': item.notes,
                }
                for item in request_line_items
            ]

        warehouse = validated_data.get('source_warehouse')
        if warehouse:
            self._validate_line_item_availability(warehouse, line_items_data)

        transfer = Transfer.objects.create(**validated_data)
        self._sync_line_items(transfer, line_items_data)
        transfer.add_audit(TransferAuditEntry.ACTION_CREATED, user)

        if transfer_request:
            transfer_request.mark_assigned(transfer)

        return transfer

    def update(self, instance, validated_data):
        if not instance.is_editable and any(field in validated_data for field in ['source_warehouse', 'destination_storefront', 'line_items']):
            raise serializers.ValidationError('Only draft or rejected transfers may be edited.')

        line_items_data = validated_data.pop('line_items', None)
        request_id = validated_data.pop('request_id', serializers.empty)

        if line_items_data is not None:
            warehouse = validated_data.get('source_warehouse', instance.source_warehouse)
            self._validate_line_item_availability(warehouse, line_items_data, transfer=instance)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if line_items_data is not None:
            self._sync_line_items(instance, line_items_data)
            instance.add_audit(TransferAuditEntry.ACTION_UPDATED, getattr(self.context.get('request'), 'user', None))

        if request_id is not serializers.empty:
            if not instance.is_editable:
                raise serializers.ValidationError({'request_id': 'Only draft or rejected transfers may change their linked request.'})
            self._update_transfer_request_link(instance, request_id)

        return instance

    def _resolve_transfer_request(self, request_id, destination_storefront, transfer: Transfer | None = None) -> TransferRequest:
        try:
            transfer_request = TransferRequest.objects.select_related('storefront', 'business').get(id=request_id)
        except TransferRequest.DoesNotExist as exc:
            raise serializers.ValidationError({'request_id': 'Transfer request not found.'}) from exc

        if transfer_request.status not in {TransferRequest.STATUS_NEW, TransferRequest.STATUS_ASSIGNED}:
            raise serializers.ValidationError({'request_id': 'Request is already fulfilled or cancelled.'})

        current_transfer = transfer_request._current_transfer()
        if current_transfer and current_transfer != transfer:
            raise serializers.ValidationError({'request_id': 'Request is already linked to another transfer.'})

        if destination_storefront and transfer_request.storefront_id != destination_storefront.id:
            raise serializers.ValidationError({'request_id': 'Request storefront must match the transfer destination storefront.'})

        return transfer_request

    def _update_transfer_request_link(self, instance: Transfer, request_id):
        if request_id:
            transfer_request = self._resolve_transfer_request(request_id, instance.destination_storefront, transfer=instance)
            instance.request = transfer_request
            instance.save(update_fields=['request', 'updated_at'])
            transfer_request.mark_assigned(instance)
        else:
            transfer_request = getattr(instance, 'request', None)
            if transfer_request:
                transfer_request.clear_assignment()
            instance.request = None
            instance.save(update_fields=['request', 'updated_at'])

    def _sync_line_items(self, transfer: Transfer, line_items_data):
        existing = {str(item.id): item for item in transfer.line_items.all()}
        seen = set()

        for item_data in line_items_data:
            destroy = item_data.pop('_destroy', False)
            item_id = item_data.get('id')

            if item_id:
                item_id = str(item_id)

            if destroy:
                if item_id and item_id in existing:
                    existing[item_id].delete()
                continue

            product = item_data.get('product')
            if product.business_id != transfer.business_id:
                raise serializers.ValidationError({'line_items': f"Product {product} does not belong to the business."})

            if item_id and item_id in existing:
                line = existing[item_id]
                for field in ['product', 'requested_quantity', 'approved_quantity', 'fulfilled_quantity', 'unit_of_measure', 'notes']:
                    if field in item_data:
                        setattr(line, field, item_data[field])
                line.save()
                seen.add(item_id)
            else:
                TransferLineItem.objects.create(transfer=transfer, **item_data)

        if line_items_data is not None:
            for item_id, line in existing.items():
                if item_id not in seen:
                    line.delete()

    def _validate_line_item_availability(self, warehouse: Warehouse, line_items_data, transfer: Transfer | None = None):
        if not line_items_data:
            return

        existing_lines = {str(line.id): line for line in transfer.line_items.all()} if transfer else {}

        final_totals: dict[str, int] = {}
        product_lookup: dict[str, Product] = {}

        if transfer:
            for line in existing_lines.values():
                key = str(line.product_id)
                final_totals[key] = final_totals.get(key, 0) + line.requested_quantity
                product_lookup[key] = line.product

        line_context: list[tuple[int, Product | None]] = []

        for index, item_data in enumerate(line_items_data):
            item_id = item_data.get('id')
            item_id = str(item_id) if item_id else None
            destroy = item_data.get('_destroy', False)
            existing_line = existing_lines.get(item_id) if item_id else None

            if destroy:
                if existing_line:
                    key = str(existing_line.product_id)
                    final_totals[key] = final_totals.get(key, 0) - existing_line.requested_quantity
                    if final_totals.get(key, 0) <= 0:
                        final_totals.pop(key, None)
                line_context.append((index, None))
                continue

            product = item_data.get('product') or (existing_line.product if existing_line else None)
            if product is None:
                raise serializers.ValidationError({'line_items': {str(index): 'Product is required.'}})

            if existing_line:
                key = str(existing_line.product_id)
                final_totals[key] = final_totals.get(key, 0) - existing_line.requested_quantity
                if final_totals.get(key, 0) <= 0:
                    final_totals.pop(key, None)

            requested_quantity = item_data.get('requested_quantity')
            if requested_quantity is None:
                requested_quantity = existing_line.requested_quantity if existing_line else None

            if requested_quantity is None:
                raise serializers.ValidationError({'line_items': {str(index): 'Requested quantity is required.'}})

            if requested_quantity <= 0:
                raise serializers.ValidationError({'line_items': {str(index): 'Requested quantity must be greater than zero.'}})

            key = str(product.id)
            final_totals[key] = final_totals.get(key, 0) + requested_quantity
            product_lookup[key] = product
            line_context.append((index, product))

        shortages: dict[str, tuple[int, Product]] = {}
        for product_key, total_requested in final_totals.items():
            product = product_lookup.get(product_key)
            if not product:
                continue
            available = Transfer.available_quantity(warehouse, product, exclude_transfer=transfer)
            if total_requested > available:
                shortages[product_key] = (available, product)

        if not shortages:
            return

        errors: dict[str, str] = {}
        for index, product in line_context:
            if product is None:
                continue
            shortage = shortages.get(str(product.id))
            if shortage:
                available, product_obj = shortage
                errors[str(index)] = f"Only {available} units available for {product_obj.name} at {warehouse.name}."

        for product_key, (available, product_obj) in shortages.items():
            if '__all__' not in errors:
                errors['__all__'] = f"Requested quantity for {product_obj.name} exceeds available stock ({available})."

        raise serializers.ValidationError({'line_items': errors})

    def get_request_reference(self, obj: Transfer):
        request = getattr(obj, 'request', None)
        if not request:
            return None
        return request.linked_transfer_reference or obj.reference


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