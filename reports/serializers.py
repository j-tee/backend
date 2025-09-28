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
