from rest_framework import serializers


class InventoryValuationReportRequestSerializer(serializers.Serializer):
    """Validate query parameters for the inventory valuation report."""

    FORMAT_CHOICES = (
        ('excel', 'Excel (.xlsx)'),
        ('pdf', 'PDF (.pdf)'),
        ('docx', 'Word (.docx)'),
    )

    format = serializers.ChoiceField(choices=FORMAT_CHOICES, default='excel')
    warehouse_id = serializers.UUIDField(required=False)
    product_id = serializers.UUIDField(required=False)
    business_id = serializers.UUIDField(required=False)
    min_quantity = serializers.IntegerField(required=False, min_value=0)

    def validate(self, attrs):
        # Ensure at least one filter is provided for large tenants (optional rule)
        return attrs


class SalesExportRequestSerializer(serializers.Serializer):
    """Serializer for sales export request parameters"""
    
    FORMAT_CHOICES = (
        ('excel', 'Excel (.xlsx)'),
        ('csv', 'CSV (.csv)'),
        ('pdf', 'PDF (.pdf)'),
    )
    
    format = serializers.ChoiceField(choices=FORMAT_CHOICES, default='excel')
    start_date = serializers.DateField(required=True)
    end_date = serializers.DateField(required=True)
    storefront_id = serializers.UUIDField(required=False)
    customer_id = serializers.UUIDField(required=False)
    sale_type = serializers.ChoiceField(
        choices=['RETAIL', 'WHOLESALE'],
        required=False
    )
    status = serializers.ChoiceField(
        choices=['DRAFT', 'PENDING', 'COMPLETED', 'PARTIAL', 'REFUNDED', 'CANCELLED'],
        required=False
    )
    include_items = serializers.BooleanField(default=True)
    
    def validate(self, data):
        if data['start_date'] > data['end_date']:
            raise serializers.ValidationError("start_date must be before or equal to end_date")
        
        # Check date range is not too large (max 1 year)
        from datetime import timedelta
        if (data['end_date'] - data['start_date']) > timedelta(days=365):
            raise serializers.ValidationError("Date range cannot exceed 365 days")
        
        return data


class CustomerExportRequestSerializer(serializers.Serializer):
    """Serializer for customer export request parameters"""
    
    FORMAT_CHOICES = (
        ('excel', 'Excel (.xlsx)'),
        ('csv', 'CSV (.csv)'),
    )
    
    format = serializers.ChoiceField(choices=FORMAT_CHOICES, default='excel')
    customer_type = serializers.ChoiceField(
        choices=['RETAIL', 'WHOLESALE'],
        required=False
    )
    include_credit_history = serializers.BooleanField(default=True)
    credit_status = serializers.ChoiceField(
        choices=['active', 'blocked', 'overdue'],
        required=False
    )
    min_outstanding_balance = serializers.DecimalField(
        required=False,
        max_digits=12,
        decimal_places=2,
        min_value=0
    )


class InventoryExportRequestSerializer(serializers.Serializer):
    """Serializer for inventory snapshot export"""
    
    FORMAT_CHOICES = (
        ('excel', 'Excel (.xlsx)'),
        ('csv', 'CSV (.csv)'),
    )
    
    format = serializers.ChoiceField(choices=FORMAT_CHOICES, default='excel')
    warehouse_id = serializers.UUIDField(required=False)
    storefront_id = serializers.UUIDField(required=False)
    category_id = serializers.UUIDField(required=False)
    include_zero_stock = serializers.BooleanField(default=False)
    min_value = serializers.DecimalField(
        required=False,
        max_digits=12,
        decimal_places=2,
        min_value=0
    )


class AuditLogExportRequestSerializer(serializers.Serializer):
    """Serializer for audit log export"""
    
    FORMAT_CHOICES = (
        ('excel', 'Excel (.xlsx)'),
        ('csv', 'CSV (.csv)'),
    )
    
    format = serializers.ChoiceField(choices=FORMAT_CHOICES, default='excel')
    start_date = serializers.DateField(required=True)
    end_date = serializers.DateField(required=True)
    event_type = serializers.CharField(required=False)
    user_id = serializers.UUIDField(required=False)
    
    def validate(self, data):
        if data['start_date'] > data['end_date']:
            raise serializers.ValidationError("start_date must be before or equal to end_date")
        return data

