from __future__ import annotations

from copy import deepcopy
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.response import Response

from .exporters import EXPORTER_MAP
from .serializers import (
    InventoryValuationReportRequestSerializer,
    SalesExportRequestSerializer,
    CustomerExportRequestSerializer,
    InventoryExportRequestSerializer,
)
from .services.inventory import InventoryValuationReportBuilder, InventoryExporter
from .services.sales import SalesExporter
from .services.customers import CustomerExporter


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


class SalesExportView(APIView):
    """Export sales data to Excel/CSV/PDF"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        """
        Export sales data
        
        Request body:
        {
            "format": "excel",  // excel, csv, or pdf
            "start_date": "2025-01-01",
            "end_date": "2025-03-31",
            "storefront_id": "uuid" (optional),
            "customer_id": "uuid" (optional),
            "sale_type": "RETAIL" or "WHOLESALE" (optional),
            "status": "COMPLETED" (optional),
            "include_items": true
        }
        """
        serializer = SalesExportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        validated = serializer.validated_data
        export_format = validated.pop('format', 'excel')
        
        # Build data using sales exporter
        exporter = SalesExporter(user=request.user)
        
        try:
            data = exporter.export(validated)
        except Exception as e:
            return Response(
                {'error': f'Failed to generate export: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Check if any data was found
        if data['summary']['total_sales'] == 0:
            return Response(
                {'error': 'No sales found matching the specified criteria'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Generate file based on format
        if export_format == 'excel':
            file_exporter = EXPORTER_MAP['sales_excel']()
            file_bytes = file_exporter.export(data)
            content_type = file_exporter.content_type
            extension = file_exporter.file_extension
        elif export_format == 'csv':
            # CSV export - to be implemented
            return Response(
                {'error': 'CSV export not yet implemented'},
                status=status.HTTP_501_NOT_IMPLEMENTED
            )
        elif export_format == 'pdf':
            # PDF export - to be implemented
            return Response(
                {'error': 'PDF export not yet implemented'},
                status=status.HTTP_501_NOT_IMPLEMENTED
            )
        else:
            return Response(
                {'error': 'Invalid export format'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate filename
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        start_date = validated.get('start_date', '').strftime('%Y%m%d') if validated.get('start_date') else 'all'
        end_date = validated.get('end_date', '').strftime('%Y%m%d') if validated.get('end_date') else 'all'
        filename = f"sales_export_{start_date}_to_{end_date}_{timestamp}.{extension}"
        
        response = HttpResponse(file_bytes, content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response


class CustomerExportView(APIView):
    """Export customer data with credit aging analysis"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        """
        Export customer data
        
        Request body:
        {
            "format": "excel",  // excel or csv
            "customer_type": "RETAIL" or "WHOLESALE" (optional),
            "include_credit_history": true,
            "credit_status": "active|blocked|overdue" (optional),
            "min_outstanding_balance": 0.00 (optional)
        }
        """
        serializer = CustomerExportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        validated = serializer.validated_data
        export_format = validated.pop('format', 'excel')
        
        # Build data using customer exporter
        exporter = CustomerExporter(user=request.user)
        
        try:
            data = exporter.export(validated)
        except Exception as e:
            return Response(
                {'error': f'Failed to generate export: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Check if any data was found
        if data['summary']['total_customers'] == 0:
            return Response(
                {'error': 'No customers found matching the specified criteria'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Generate file based on format
        if export_format == 'excel':
            file_exporter = EXPORTER_MAP['customer_excel']()
            file_bytes = file_exporter.export(data)
            content_type = file_exporter.content_type
            extension = file_exporter.file_extension
        elif export_format == 'csv':
            # CSV export - to be implemented
            return Response(
                {'error': 'CSV export not yet implemented'},
                status=status.HTTP_501_NOT_IMPLEMENTED
            )
        else:
            return Response(
                {'error': 'Invalid export format'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate filename
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"customers_export_{timestamp}.{extension}"
        
        response = HttpResponse(file_bytes, content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response


class InventoryExportView(APIView):
    """Export inventory snapshot with stock levels and valuation"""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        """Generate inventory export"""
        serializer = InventoryExportRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data
        
        # Extract format
        export_format = validated.pop('format', 'excel')
        
        # CSV not yet implemented
        if export_format == 'csv':
            return Response(
                {'error': 'CSV format not yet implemented'},
                status=status.HTTP_501_NOT_IMPLEMENTED
            )
        
        try:
            # Create exporter
            exporter = InventoryExporter(user=request.user)
            
            # Export data
            data = exporter.export(validated)
            
            # Check if we have any stock items
            if not data.get('stock_items'):
                return Response(
                    {'error': 'No inventory items found for the given criteria'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Get appropriate exporter class
            exporter_class = EXPORTER_MAP.get(f'inventory_{export_format}')
            
            if not exporter_class:
                return Response(
                    {'error': f'Unsupported format: {export_format}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Generate file
            file_exporter = exporter_class()
            file_bytes = file_exporter.export(data)
            content_type = file_exporter.content_type
            extension = file_exporter.file_extension
            
        except Exception as e:
            return Response(
                {'error': f'Export failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Generate filename
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
        filename = f"inventory_export_{timestamp}.{extension}"
        
        response = HttpResponse(file_bytes, content_type=content_type)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
