"""
Export scheduling and automation models

These models enable automated, scheduled exports with email delivery
and comprehensive tracking for the data retention compliance system.
"""

from django.db import models
from django.contrib.auth import get_user_model
from accounts.models import Business
import uuid

User = get_user_model()


class ExportSchedule(models.Model):
    """
    Scheduled export configuration for automated data exports
    """
    
    FREQUENCY_CHOICES = [
        ('DAILY', 'Daily'),
        ('WEEKLY', 'Weekly'),
        ('MONTHLY', 'Monthly'),
    ]
    
    EXPORT_TYPE_CHOICES = [
        ('SALES', 'Sales Export'),
        ('CUSTOMERS', 'Customer Export'),
        ('INVENTORY', 'Inventory Export'),
        ('AUDIT_LOGS', 'Audit Logs Export'),
    ]
    
    FORMAT_CHOICES = [
        ('excel', 'Excel'),
        ('csv', 'CSV'),
        ('pdf', 'PDF'),
    ]
    
    WEEKDAY_CHOICES = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='export_schedules'
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_export_schedules'
    )
    
    # Schedule configuration
    name = models.CharField(max_length=255, help_text="Descriptive name for this schedule")
    export_type = models.CharField(max_length=20, choices=EXPORT_TYPE_CHOICES)
    format = models.CharField(max_length=10, choices=FORMAT_CHOICES, default='excel')
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES)
    
    # Timing
    hour = models.IntegerField(
        default=2,
        help_text="Hour of day to run (0-23, UTC)"
    )
    day_of_week = models.IntegerField(
        null=True,
        blank=True,
        choices=WEEKDAY_CHOICES,
        help_text="Day of week for weekly exports (0=Monday)"
    )
    day_of_month = models.IntegerField(
        null=True,
        blank=True,
        help_text="Day of month for monthly exports (1-28)"
    )
    
    # Email configuration
    recipients = models.JSONField(
        default=list,
        help_text="List of email addresses to send exports to"
    )
    include_creator_email = models.BooleanField(
        default=True,
        help_text="Include the schedule creator's email in recipients"
    )
    email_subject = models.CharField(
        max_length=255,
        blank=True,
        help_text="Custom email subject (optional)"
    )
    email_message = models.TextField(
        blank=True,
        help_text="Custom email message (optional)"
    )
    
    # Export filters (stored as JSON)
    filters = models.JSONField(
        default=dict,
        blank=True,
        help_text="Export-specific filters (date ranges, customer types, etc.)"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'export_schedules'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['business', 'is_active']),
            models.Index(fields=['next_run_at']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_frequency_display()})"
    
    def get_recipients_list(self):
        """Get full list of recipients including creator if enabled"""
        recipients = list(self.recipients)
        
        if self.include_creator_email and self.created_by:
            creator_email = self.created_by.email
            if creator_email and creator_email not in recipients:
                recipients.append(creator_email)
        
        return recipients


class ExportHistory(models.Model):
    """
    Track all export executions for audit and history
    """
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('EMAILED', 'Emailed'),
    ]
    
    TRIGGER_CHOICES = [
        ('MANUAL', 'Manual'),
        ('SCHEDULED', 'Scheduled'),
        ('API', 'API'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='export_history'
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='export_history',
        help_text="User who triggered the export (null for scheduled)"
    )
    schedule = models.ForeignKey(
        ExportSchedule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='executions',
        help_text="Associated schedule (null for manual exports)"
    )
    
    # Export details
    export_type = models.CharField(max_length=20)
    format = models.CharField(max_length=10)
    trigger = models.CharField(max_length=10, choices=TRIGGER_CHOICES, default='MANUAL')
    
    # Execution details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # File details
    file_name = models.CharField(max_length=255, blank=True)
    file_size = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="File size in bytes"
    )
    file_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Path to stored file (S3, local, etc.)"
    )
    
    # Export statistics
    record_count = models.IntegerField(
        null=True,
        blank=True,
        help_text="Number of records exported"
    )
    filters_applied = models.JSONField(
        default=dict,
        blank=True,
        help_text="Filters used for this export"
    )
    
    # Email details
    email_sent = models.BooleanField(default=False)
    email_recipients = models.JSONField(
        default=list,
        blank=True,
        help_text="List of email addresses that received this export"
    )
    email_sent_at = models.DateTimeField(null=True, blank=True)
    
    # Error tracking
    error_message = models.TextField(blank=True)
    error_traceback = models.TextField(blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'export_history'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['business', 'created_at']),
            models.Index(fields=['schedule', 'status']),
            models.Index(fields=['user', 'created_at']),
        ]
        verbose_name_plural = 'Export histories'
    
    def __str__(self):
        return f"{self.export_type} - {self.format} ({self.status})"
    
    @property
    def duration_seconds(self):
        """Calculate export duration in seconds"""
        if self.completed_at and self.started_at:
            delta = self.completed_at - self.started_at
            return delta.total_seconds()
        return None
    
    @property
    def file_size_mb(self):
        """Get file size in megabytes"""
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return None


class ExportNotificationSettings(models.Model):
    """
    Per-business notification preferences for exports
    """
    
    business = models.OneToOneField(
        Business,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='export_notification_settings'
    )
    
    # Email settings
    notify_on_success = models.BooleanField(
        default=True,
        help_text="Send email when scheduled export succeeds"
    )
    notify_on_failure = models.BooleanField(
        default=True,
        help_text="Send email when scheduled export fails"
    )
    
    # Default recipients
    default_recipients = models.JSONField(
        default=list,
        blank=True,
        help_text="Default email recipients for all exports"
    )
    
    # Email customization
    from_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Custom 'from' name for export emails"
    )
    reply_to_email = models.EmailField(
        blank=True,
        help_text="Reply-to email address"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'export_notification_settings'
    
    def __str__(self):
        return f"Notification settings for {self.business.name}"
