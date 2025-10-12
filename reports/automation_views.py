"""
Export Automation API Views (Phase 5)

Provides endpoints for:
- Managing export schedules (CRUD)
- Viewing export history
- Configuring notification settings
- Manually triggering scheduled exports
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination

from django.utils import timezone
from django.db.models import Q

from reports.models import ExportSchedule, ExportHistory, ExportNotificationSettings
from reports.serializers import (
    ExportScheduleSerializer,
    ExportScheduleCreateSerializer,
    ExportHistorySerializer,
    ExportHistoryDetailSerializer,
    ExportNotificationSettingsSerializer,
    TriggerExportSerializer
)
from reports.services import ScheduledExportRunner, ExportFileStorage


class ExportHistoryPagination(PageNumberPagination):
    """Pagination for export history"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class ExportScheduleViewSet(viewsets.ModelViewSet):
    """
    API endpoints for managing export schedules.
    
    list: Get all schedules for the user's business
    create: Create a new export schedule
    retrieve: Get details of a specific schedule
    update: Update an existing schedule
    partial_update: Partially update a schedule
    destroy: Delete a schedule
    activate: Activate a schedule
    deactivate: Deactivate a schedule
    trigger: Manually trigger a schedule
    """
    
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter schedules by user's business"""
        user = self.request.user
        
        # Get user's business memberships
        business_ids = user.business_memberships.values_list('business_id', flat=True)
        
        queryset = ExportSchedule.objects.filter(
            business_id__in=business_ids
        ).select_related('business', 'created_by').order_by('-created_at')
        
        # Filter by status if requested
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        # Filter by export type if requested
        export_type = self.request.query_params.get('export_type')
        if export_type:
            queryset = queryset.filter(export_type=export_type.upper())
        
        # Filter by frequency if requested
        frequency = self.request.query_params.get('frequency')
        if frequency:
            queryset = queryset.filter(frequency=frequency.upper())
        
        return queryset
    
    def get_serializer_class(self):
        """Use different serializers for different actions"""
        if self.action in ['create', 'update', 'partial_update']:
            return ExportScheduleCreateSerializer
        return ExportScheduleSerializer
    
    def perform_create(self, serializer):
        """Set business and created_by when creating schedule"""
        user = self.request.user
        
        # Get user's first business (or you could accept business_id in request)
        business = user.business_memberships.first().business
        
        serializer.save(
            business=business,
            created_by=user
        )
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a schedule"""
        schedule = self.get_object()
        
        if schedule.is_active:
            return Response(
                {'detail': 'Schedule is already active'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        schedule.is_active = True
        
        # Recalculate next run time
        from reports.services import ScheduleCalculator
        calculator = ScheduleCalculator()
        schedule.next_run_at = calculator.calculate_next_run(schedule)
        
        schedule.save()
        
        serializer = self.get_serializer(schedule)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a schedule"""
        schedule = self.get_object()
        
        if not schedule.is_active:
            return Response(
                {'detail': 'Schedule is already inactive'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        schedule.is_active = False
        schedule.next_run_at = None
        schedule.save()
        
        serializer = self.get_serializer(schedule)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def trigger(self, request, pk=None):
        """Manually trigger a scheduled export"""
        schedule = self.get_object()
        
        # Validate request data
        trigger_serializer = TriggerExportSerializer(data=request.data)
        trigger_serializer.is_valid(raise_exception=True)
        
        # Execute the export
        runner = ScheduledExportRunner()
        
        try:
            history = runner.execute_schedule(schedule, trigger='MANUAL')
            
            # Return history details
            history_serializer = ExportHistoryDetailSerializer(history)
            return Response(history_serializer.data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {'detail': f'Export failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Get upcoming scheduled exports"""
        queryset = self.get_queryset().filter(
            is_active=True,
            next_run_at__isnull=False
        ).order_by('next_run_at')[:10]
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Get overdue scheduled exports"""
        now = timezone.now()
        
        queryset = self.get_queryset().filter(
            is_active=True,
            next_run_at__lt=now
        ).order_by('next_run_at')
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class ExportHistoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoints for viewing export history.
    
    list: Get all export history for the user's business
    retrieve: Get details of a specific export execution
    download: Download the export file
    statistics: Get export statistics
    """
    
    permission_classes = [IsAuthenticated]
    pagination_class = ExportHistoryPagination
    
    def get_queryset(self):
        """Filter history by user's business"""
        user = self.request.user
        
        # Get user's business memberships
        business_ids = user.business_memberships.values_list('business_id', flat=True)
        
        queryset = ExportHistory.objects.filter(
            business_id__in=business_ids
        ).select_related('business', 'user', 'schedule').order_by('-created_at')
        
        # Filter by export type if requested
        export_type = self.request.query_params.get('export_type')
        if export_type:
            queryset = queryset.filter(export_type=export_type.upper())
        
        # Filter by format if requested
        format_type = self.request.query_params.get('format')
        if format_type:
            queryset = queryset.filter(format=format_type.lower())
        
        # Filter by status if requested
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter.upper())
        
        # Filter by trigger type if requested
        trigger = self.request.query_params.get('trigger')
        if trigger:
            queryset = queryset.filter(trigger=trigger.upper())
        
        # Filter by schedule if requested
        schedule_id = self.request.query_params.get('schedule_id')
        if schedule_id:
            queryset = queryset.filter(schedule_id=schedule_id)
        
        # Filter by date range if requested
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        return queryset
    
    def get_serializer_class(self):
        """Use detailed serializer for retrieve action"""
        if self.action == 'retrieve':
            return ExportHistoryDetailSerializer
        return ExportHistorySerializer
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Download the export file"""
        history = self.get_object()
        
        if not history.file_path:
            return Response(
                {'detail': 'Export file not available'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if history.status != 'COMPLETED' and history.status != 'EMAILED':
            return Response(
                {'detail': 'Export is not complete'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get file from storage
        storage = ExportFileStorage()
        
        try:
            file_content = storage.get_export_file(history.file_path)
            
            # Determine content type
            content_types = {
                'excel': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'csv': 'text/csv',
                'pdf': 'application/pdf'
            }
            content_type = content_types.get(history.format, 'application/octet-stream')
            
            # Return file as response
            from django.http import HttpResponse
            response = HttpResponse(file_content, content_type=content_type)
            response['Content-Disposition'] = f'attachment; filename="{history.file_name}"'
            
            return response
            
        except Exception as e:
            return Response(
                {'detail': f'Failed to retrieve file: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get export statistics"""
        queryset = self.get_queryset()
        
        # Overall statistics
        total_exports = queryset.count()
        successful_exports = queryset.filter(
            status__in=['COMPLETED', 'EMAILED']
        ).count()
        failed_exports = queryset.filter(status='FAILED').count()
        
        # Statistics by export type
        by_type = {}
        for export_type in ['SALES', 'CUSTOMERS', 'INVENTORY', 'AUDIT_LOGS']:
            type_queryset = queryset.filter(export_type=export_type)
            by_type[export_type] = {
                'total': type_queryset.count(),
                'successful': type_queryset.filter(status__in=['COMPLETED', 'EMAILED']).count(),
                'failed': type_queryset.filter(status='FAILED').count()
            }
        
        # Statistics by format
        by_format = {}
        for format_type in ['excel', 'csv', 'pdf']:
            format_queryset = queryset.filter(format=format_type)
            by_format[format_type] = {
                'total': format_queryset.count(),
                'successful': format_queryset.filter(status__in=['COMPLETED', 'EMAILED']).count(),
                'failed': format_queryset.filter(status='FAILED').count()
            }
        
        # Recent activity (last 7 days)
        from datetime import timedelta
        seven_days_ago = timezone.now() - timedelta(days=7)
        recent_exports = queryset.filter(created_at__gte=seven_days_ago).count()
        
        # Average file size
        completed_exports = queryset.filter(
            status__in=['COMPLETED', 'EMAILED'],
            file_size__isnull=False
        )
        
        if completed_exports.exists():
            from django.db.models import Avg
            avg_file_size = completed_exports.aggregate(Avg('file_size'))['file_size__avg']
            avg_file_size_mb = avg_file_size / (1024 * 1024) if avg_file_size else 0
        else:
            avg_file_size_mb = 0
        
        return Response({
            'total_exports': total_exports,
            'successful_exports': successful_exports,
            'failed_exports': failed_exports,
            'success_rate': (successful_exports / total_exports * 100) if total_exports > 0 else 0,
            'by_type': by_type,
            'by_format': by_format,
            'recent_exports_7_days': recent_exports,
            'average_file_size_mb': round(avg_file_size_mb, 2)
        })
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Get recent export history (last 10)"""
        queryset = self.get_queryset()[:10]
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class ExportNotificationSettingsViewSet(viewsets.ViewSet):
    """
    API endpoints for managing export notification settings.
    
    retrieve: Get notification settings for the business
    update: Update notification settings
    """
    
    permission_classes = [IsAuthenticated]
    
    def retrieve(self, request):
        """Get notification settings for user's business"""
        user = request.user
        
        # Get user's business
        business = user.business_memberships.first().business
        
        # Get or create notification settings
        settings, created = ExportNotificationSettings.objects.get_or_create(
            business=business,
            defaults={
                'notify_on_success': True,
                'notify_on_failure': True,
                'default_recipients': [],
                'from_name': business.name,
                'reply_to_email': ''
            }
        )
        
        serializer = ExportNotificationSettingsSerializer(settings)
        return Response(serializer.data)
    
    def update(self, request):
        """Update notification settings"""
        user = request.user
        
        # Get user's business
        business = user.business_memberships.first().business
        
        # Get or create notification settings
        settings, created = ExportNotificationSettings.objects.get_or_create(
            business=business
        )
        
        # Update settings
        serializer = ExportNotificationSettingsSerializer(settings, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(serializer.data)
