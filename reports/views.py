from __future__ import annotations

from copy import deepcopy
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from .exporters import EXPORTER_MAP
from .serializers import InventoryValuationReportRequestSerializer
from .services.inventory import InventoryValuationReportBuilder


class InventoryValuationReportView(APIView):
    """Generate printable/downloadable inventory valuation reports."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        serializer = InventoryValuationReportRequestSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        export_format = validated.get('format', 'excel')
        filters = deepcopy(validated)
        filters.pop('format', None)

        builder = InventoryValuationReportBuilder(user=request.user)
        report_payload = builder.build(filters=filters)

        exporter_class = EXPORTER_MAP[export_format]
        exporter = exporter_class()
        file_bytes = exporter.export(report_payload)

        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"inventory-valuation-{timestamp}.{exporter.file_extension}"

        response = HttpResponse(file_bytes, content_type=exporter.content_type)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
