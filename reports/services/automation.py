"""
Export Automation Services (Phase 5)

This module provides services for:
- Calculating next run times for scheduled exports
- Executing scheduled exports
- Sending export emails
- Managing export files (local/S3 storage)
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import os
import traceback

from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils import timezone
from django.core.files.storage import default_storage

from reports.models import ExportSchedule, ExportHistory, ExportNotificationSettings


class ScheduleCalculator:
    """Calculate next run times for export schedules"""
    
    def calculate_next_run(self, schedule: ExportSchedule) -> datetime:
        """
        Calculate the next run time for a schedule.
        
        Args:
            schedule: ExportSchedule instance
            
        Returns:
            datetime: Next scheduled run time (UTC)
        """
        now = timezone.now()
        
        if schedule.frequency == 'DAILY':
            return self._calculate_daily_next_run(now, schedule.hour)
        elif schedule.frequency == 'WEEKLY':
            return self._calculate_weekly_next_run(now, schedule.hour, schedule.day_of_week)
        elif schedule.frequency == 'MONTHLY':
            return self._calculate_monthly_next_run(now, schedule.hour, schedule.day_of_month)
        else:
            raise ValueError(f"Unknown frequency: {schedule.frequency}")
    
    def _calculate_daily_next_run(self, now: datetime, hour: int) -> datetime:
        """Calculate next daily run time"""
        next_run = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        
        # If the time has passed today, schedule for tomorrow
        if next_run <= now:
            next_run += timedelta(days=1)
        
        return next_run
    
    def _calculate_weekly_next_run(self, now: datetime, hour: int, day_of_week: int) -> datetime:
        """Calculate next weekly run time"""
        # Calculate days until target day of week
        current_day = now.weekday()
        days_ahead = day_of_week - current_day
        
        # If target day is today but time has passed, or target day is in the past, schedule for next week
        next_run = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        
        if days_ahead < 0:
            # Target day is earlier in the week, schedule for next week
            days_ahead += 7
        elif days_ahead == 0 and next_run <= now:
            # Target day is today but time has passed, schedule for next week
            days_ahead = 7
        
        next_run += timedelta(days=days_ahead)
        return next_run
    
    def _calculate_monthly_next_run(self, now: datetime, hour: int, day_of_month: int) -> datetime:
        """Calculate next monthly run time"""
        next_run = now.replace(day=day_of_month, hour=hour, minute=0, second=0, microsecond=0)
        
        # If the time has passed this month, schedule for next month
        if next_run <= now:
            # Move to next month
            if now.month == 12:
                next_run = next_run.replace(year=now.year + 1, month=1)
            else:
                next_run = next_run.replace(month=now.month + 1)
        
        return next_run


class ScheduledExportRunner:
    """Execute scheduled exports"""
    
    def __init__(self):
        self.calculator = ScheduleCalculator()
        self.email_service = EmailDeliveryService()
        self.storage_service = ExportFileStorage()
    
    def run_due_schedules(self) -> Dict[str, Any]:
        """
        Find and execute all due scheduled exports.
        
        Returns:
            dict: Summary of execution results
        """
        now = timezone.now()
        
        # Find all active schedules that are due
        due_schedules = ExportSchedule.objects.filter(
            is_active=True,
            next_run_at__lte=now
        ).select_related('business', 'created_by')
        
        results = {
            'total_found': due_schedules.count(),
            'successful': 0,
            'failed': 0,
            'executions': []
        }
        
        for schedule in due_schedules:
            try:
                history = self.execute_schedule(schedule)
                
                if history.status in ['COMPLETED', 'EMAILED']:
                    results['successful'] += 1
                else:
                    results['failed'] += 1
                
                results['executions'].append({
                    'schedule_id': str(schedule.id),
                    'schedule_name': schedule.name,
                    'history_id': str(history.id),
                    'status': history.status
                })
                
            except Exception as e:
                results['failed'] += 1
                results['executions'].append({
                    'schedule_id': str(schedule.id),
                    'schedule_name': schedule.name,
                    'error': str(e)
                })
        
        return results
    
    def execute_schedule(self, schedule: ExportSchedule, trigger: str = 'SCHEDULED') -> ExportHistory:
        """
        Execute a single scheduled export.
        
        Args:
            schedule: ExportSchedule to execute
            trigger: How this execution was triggered (SCHEDULED, MANUAL, API)
            
        Returns:
            ExportHistory: Record of the execution
        """
        # Create history record
        history = ExportHistory.objects.create(
            business=schedule.business,
            user=schedule.created_by,
            schedule=schedule,
            export_type=schedule.export_type,
            format=schedule.format,
            trigger=trigger,
            status='PENDING',
            filters_applied=schedule.filters
        )
        
        try:
            # Update status to processing
            history.status = 'PROCESSING'
            history.started_at = timezone.now()
            history.save(update_fields=['status', 'started_at'])
            
            # Execute the export
            file_content, file_name, record_count = self._execute_export(schedule, history)
            
            # Save the file
            file_path = self.storage_service.save_export_file(
                file_content=file_content,
                file_name=file_name,
                business_id=schedule.business.id,
                history_id=history.id
            )
            
            # Update history with results
            history.status = 'COMPLETED'
            history.completed_at = timezone.now()
            history.file_name = file_name
            history.file_size = len(file_content)
            history.file_path = file_path
            history.record_count = record_count
            history.save(update_fields=[
                'status', 'completed_at', 'file_name', 'file_size', 'file_path', 'record_count'
            ])
            
            # Send email if configured
            recipients = schedule.get_recipients_list()
            if recipients:
                email_sent = self.email_service.send_export_email(
                    history=history,
                    recipients=recipients,
                    file_content=file_content,
                    custom_subject=schedule.email_subject,
                    custom_message=schedule.email_message
                )
                
                if email_sent:
                    history.status = 'EMAILED'
                    history.email_sent = True
                    history.email_recipients = recipients
                    history.email_sent_at = timezone.now()
                    history.save(update_fields=[
                        'status', 'email_sent', 'email_recipients', 'email_sent_at'
                    ])
            
            # Update schedule's last run and calculate next run
            schedule.last_run_at = timezone.now()
            schedule.next_run_at = self.calculator.calculate_next_run(schedule)
            schedule.save(update_fields=['last_run_at', 'next_run_at'])
            
            return history
            
        except Exception as e:
            # Record the error
            history.status = 'FAILED'
            history.completed_at = timezone.now()
            history.error_message = str(e)
            history.error_traceback = traceback.format_exc()
            history.save(update_fields=['status', 'completed_at', 'error_message', 'error_traceback'])
            
            # Send failure notification if configured
            notification_settings = self._get_notification_settings(schedule.business)
            if notification_settings and notification_settings.notify_on_failure:
                recipients = notification_settings.default_recipients
                if recipients:
                    self.email_service.send_failure_notification(
                        history=history,
                        recipients=recipients,
                        error_message=str(e)
                    )
            
            # Still update schedule timing
            schedule.last_run_at = timezone.now()
            schedule.next_run_at = self.calculator.calculate_next_run(schedule)
            schedule.save(update_fields=['last_run_at', 'next_run_at'])
            
            raise
    
    def _execute_export(self, schedule: ExportSchedule, history: ExportHistory) -> tuple:
        """
        Execute the actual export using the appropriate exporter.
        
        Returns:
            tuple: (file_content, file_name, record_count)
        """
        # Lazy import to avoid circular dependency
        from reports.exporters import EXPORTER_MAP
        
        # Get the exporter
        exporter_key = f"{schedule.export_type.lower()}_{schedule.format}"
        exporter_class = EXPORTER_MAP.get(exporter_key)
        
        if not exporter_class:
            raise ValueError(f"No exporter found for {exporter_key}")
        
        # Initialize exporter
        exporter = exporter_class(business=schedule.business)
        
        # Apply filters
        filters = schedule.filters or {}
        
        # Execute export based on type
        if schedule.export_type == 'SALES':
            file_content = exporter.generate_sales_export(**filters)
            file_name = exporter.get_filename()
            record_count = exporter.get_record_count()
            
        elif schedule.export_type == 'CUSTOMERS':
            file_content = exporter.generate_customer_export(**filters)
            file_name = exporter.get_filename()
            record_count = exporter.get_record_count()
            
        elif schedule.export_type == 'INVENTORY':
            file_content = exporter.generate_inventory_export(**filters)
            file_name = exporter.get_filename()
            record_count = exporter.get_record_count()
            
        elif schedule.export_type == 'AUDIT_LOGS':
            file_content = exporter.generate_audit_export(**filters)
            file_name = exporter.get_filename()
            record_count = exporter.get_record_count()
        else:
            raise ValueError(f"Unknown export type: {schedule.export_type}")
        
        return file_content, file_name, record_count
    
    def _get_notification_settings(self, business) -> Optional[ExportNotificationSettings]:
        """Get notification settings for a business"""
        try:
            return ExportNotificationSettings.objects.get(business=business)
        except ExportNotificationSettings.DoesNotExist:
            return None


class EmailDeliveryService:
    """Handle email delivery for exports"""
    
    def send_export_email(
        self,
        history: ExportHistory,
        recipients: List[str],
        file_content: bytes,
        custom_subject: Optional[str] = None,
        custom_message: Optional[str] = None
    ) -> bool:
        """
        Send export file via email.
        
        Args:
            history: ExportHistory record
            recipients: List of email addresses
            file_content: Binary content of the export file
            custom_subject: Optional custom email subject
            custom_message: Optional custom email message
            
        Returns:
            bool: True if email sent successfully
        """
        try:
            # Get notification settings for from_name and reply_to
            notification_settings = self._get_notification_settings(history.business)
            
            # Prepare email subject
            if custom_subject:
                subject = custom_subject
            else:
                subject = f"Scheduled Export: {history.get_export_type_display()} ({history.format.upper()})"
            
            # Prepare email body
            context = {
                'export_type': history.get_export_type_display(),
                'format': history.format.upper(),
                'business_name': history.business.name,
                'record_count': history.record_count,
                'file_name': history.file_name,
                'file_size_mb': history.file_size_mb,
                'duration': history.duration_seconds,
                'custom_message': custom_message
            }
            
            # Render HTML email
            html_message = render_to_string('reports/emails/export_success.html', context)
            
            # Create email
            from_email = settings.DEFAULT_FROM_EMAIL
            if notification_settings and notification_settings.from_name:
                from_email = f"{notification_settings.from_name} <{settings.DEFAULT_FROM_EMAIL}>"
            
            email = EmailMessage(
                subject=subject,
                body=html_message,
                from_email=from_email,
                to=recipients,
                reply_to=[notification_settings.reply_to_email] if notification_settings and notification_settings.reply_to_email else None
            )
            email.content_subtype = 'html'
            
            # Attach the export file
            email.attach(history.file_name, file_content, self._get_content_type(history.format))
            
            # Send email
            email.send(fail_silently=False)
            
            return True
            
        except Exception as e:
            # Log the error but don't fail the export
            print(f"Failed to send export email: {str(e)}")
            return False
    
    def send_failure_notification(
        self,
        history: ExportHistory,
        recipients: List[str],
        error_message: str
    ) -> bool:
        """
        Send notification about failed export.
        
        Args:
            history: ExportHistory record
            recipients: List of email addresses
            error_message: Error message to include
            
        Returns:
            bool: True if email sent successfully
        """
        try:
            notification_settings = self._get_notification_settings(history.business)
            
            subject = f"Export Failed: {history.get_export_type_display()}"
            
            context = {
                'export_type': history.get_export_type_display(),
                'format': history.format.upper(),
                'business_name': history.business.name,
                'error_message': error_message,
                'schedule_name': history.schedule.name if history.schedule else 'Manual Export'
            }
            
            html_message = render_to_string('reports/emails/export_failure.html', context)
            
            from_email = settings.DEFAULT_FROM_EMAIL
            if notification_settings and notification_settings.from_name:
                from_email = f"{notification_settings.from_name} <{settings.DEFAULT_FROM_EMAIL}>"
            
            email = EmailMessage(
                subject=subject,
                body=html_message,
                from_email=from_email,
                to=recipients,
                reply_to=[notification_settings.reply_to_email] if notification_settings and notification_settings.reply_to_email else None
            )
            email.content_subtype = 'html'
            email.send(fail_silently=False)
            
            return True
            
        except Exception as e:
            print(f"Failed to send failure notification: {str(e)}")
            return False
    
    def _get_notification_settings(self, business) -> Optional[ExportNotificationSettings]:
        """Get notification settings for a business"""
        try:
            return ExportNotificationSettings.objects.get(business=business)
        except ExportNotificationSettings.DoesNotExist:
            return None
    
    def _get_content_type(self, format: str) -> str:
        """Get MIME content type for export format"""
        content_types = {
            'excel': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'csv': 'text/csv',
            'pdf': 'application/pdf'
        }
        return content_types.get(format, 'application/octet-stream')


class ExportFileStorage:
    """Manage export file storage (local or S3)"""
    
    def save_export_file(
        self,
        file_content: bytes,
        file_name: str,
        business_id: str,
        history_id: str
    ) -> str:
        """
        Save export file to storage.
        
        Args:
            file_content: Binary content of the file
            file_name: Name of the file
            business_id: Business UUID
            history_id: ExportHistory UUID
            
        Returns:
            str: Storage path of the saved file
        """
        # Build storage path
        storage_path = self._build_storage_path(business_id, history_id, file_name)
        
        # Save using Django's default storage (can be configured for S3)
        saved_path = default_storage.save(storage_path, file_content)
        
        return saved_path
    
    def get_export_file(self, file_path: str) -> bytes:
        """
        Retrieve export file from storage.
        
        Args:
            file_path: Path to the file in storage
            
        Returns:
            bytes: File content
        """
        with default_storage.open(file_path, 'rb') as f:
            return f.read()
    
    def delete_export_file(self, file_path: str) -> bool:
        """
        Delete export file from storage.
        
        Args:
            file_path: Path to the file in storage
            
        Returns:
            bool: True if deleted successfully
        """
        try:
            default_storage.delete(file_path)
            return True
        except Exception as e:
            print(f"Failed to delete file {file_path}: {str(e)}")
            return False
    
    def cleanup_old_exports(self, days_to_keep: int = 30) -> Dict[str, Any]:
        """
        Clean up export files older than specified days.
        
        Args:
            days_to_keep: Number of days to keep exports
            
        Returns:
            dict: Cleanup results
        """
        cutoff_date = timezone.now() - timedelta(days=days_to_keep)
        
        old_exports = ExportHistory.objects.filter(
            created_at__lt=cutoff_date,
            file_path__isnull=False
        )
        
        results = {
            'total_found': old_exports.count(),
            'deleted': 0,
            'failed': 0,
            'space_freed_mb': 0
        }
        
        for export in old_exports:
            try:
                # Track file size before deletion
                if export.file_size:
                    results['space_freed_mb'] += export.file_size_mb
                
                # Delete the file
                if self.delete_export_file(export.file_path):
                    # Clear file path in history record
                    export.file_path = None
                    export.save(update_fields=['file_path'])
                    results['deleted'] += 1
                else:
                    results['failed'] += 1
                    
            except Exception as e:
                results['failed'] += 1
                print(f"Failed to cleanup export {export.id}: {str(e)}")
        
        return results
    
    def _build_storage_path(self, business_id: str, history_id: str, file_name: str) -> str:
        """Build storage path for export file"""
        # Format: exports/{business_id}/{year}/{month}/{history_id}_{filename}
        now = timezone.now()
        return os.path.join(
            'exports',
            str(business_id),
            str(now.year),
            f"{now.month:02d}",
            f"{history_id}_{file_name}"
        )
