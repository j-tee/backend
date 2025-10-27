from rest_framework import serializers
from .stock_adjustments import StockAdjustment

class StockAdjustmentSerializer(serializers.ModelSerializer):
    adjustment_type_display = serializers.CharField(source='get_adjustment_type_display', read_only=True)

    class Meta:
        model = StockAdjustment
        fields = [
            'id', 'business', 'stock_product', 'adjustment_type', 'adjustment_type_display',
            'quantity', 'quantity_before', 'unit_cost', 'total_cost', 'reason', 'reference_number',
            'status', 'requires_approval', 'created_by', 'approved_by', 'created_at', 'approved_at',
            'completed_at', 'has_photos', 'has_documents', 'related_sale'
        ]
        read_only_fields = [
            'id', 'quantity_before', 'total_cost', 'created_by', 'approved_by',
            'created_at', 'approved_at', 'completed_at', 'adjustment_type_display'
        ]