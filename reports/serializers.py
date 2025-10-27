from rest_framework import serializers
from reports.models import ExportSchedule, ExportHistory, ExportNotificationSettings


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
    
    STOCK_STATUS_CHOICES = (
        ('in_stock', 'In Stock'),
        ('low_stock', 'Low Stock'),
        ('out_of_stock', 'Out of Stock'),
    )
    
    format = serializers.ChoiceField(choices=FORMAT_CHOICES, default='excel')
    storefront_id = serializers.UUIDField(required=False)
    category = serializers.CharField(required=False)
    stock_status = serializers.ChoiceField(choices=STOCK_STATUS_CHOICES, required=False)
    min_quantity = serializers.IntegerField(required=False, min_value=0)
    exclude_zero_value = serializers.BooleanField(default=False)
    include_movement_history = serializers.BooleanField(default=False)
    movement_start_date = serializers.DateField(required=False)
    movement_end_date = serializers.DateField(required=False)
    
    def validate(self, data):
        # If movement history requested, validate date range
        if data.get('movement_start_date') and data.get('movement_end_date'):
            if data['movement_start_date'] > data['movement_end_date']:
                raise serializers.ValidationError(
                    "movement_start_date must be before or equal to movement_end_date"
                )
        return data


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


# ============================================================================
# EXPORT AUTOMATION SERIALIZERS (Phase 5)
# ============================================================================

class ExportScheduleSerializer(serializers.ModelSerializer):
    """Serializer for export schedule listing and details"""
    
    created_by_name = serializers.CharField(source='created_by.name', read_only=True)
    next_run_display = serializers.SerializerMethodField()
    last_run_display = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    
    class Meta:
        model = ExportSchedule
        fields = [
            'id', 'name', 'export_type', 'format', 'frequency',
            'hour', 'day_of_week', 'day_of_month',
            'recipients', 'include_creator_email', 'email_subject', 'email_message',
            'filters', 'is_active', 'last_run_at', 'next_run_at',
            'created_at', 'updated_at', 'created_by', 'created_by_name',
            'next_run_display', 'last_run_display', 'status_display'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'last_run_at', 'next_run_at']
    
    def get_next_run_display(self, obj):
        """Human-readable next run time"""
        if not obj.next_run_at:
            return "Not scheduled"
        from django.utils import timezone
        now = timezone.now()
        if obj.next_run_at < now:
            return "Overdue"
        delta = obj.next_run_at - now
        hours = delta.total_seconds() / 3600
        if hours < 24:
            return f"In {int(hours)} hours"
        days = int(hours / 24)
        return f"In {days} days"
    
    def get_last_run_display(self, obj):
        """Human-readable last run time"""
        if not obj.last_run_at:
            return "Never run"
        from django.utils import timezone
        now = timezone.now()
        delta = now - obj.last_run_at
        hours = delta.total_seconds() / 3600
        if hours < 24:
            return f"{int(hours)} hours ago"
        days = int(hours / 24)
        return f"{days} days ago"
    
    def get_status_display(self, obj):
        """Current status of the schedule"""
        if not obj.is_active:
            return "Inactive"
        from django.utils import timezone
        now = timezone.now()
        if obj.next_run_at and obj.next_run_at < now:
            return "Overdue"
        return "Active"


class ExportScheduleCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating export schedules"""
    
    class Meta:
        model = ExportSchedule
        fields = [
            'name', 'export_type', 'format', 'frequency',
            'hour', 'day_of_week', 'day_of_month',
            'recipients', 'include_creator_email', 'email_subject', 'email_message',
            'filters', 'is_active'
        ]
    
    def validate_recipients(self, value):
        """Validate email recipients list"""
        if not isinstance(value, list):
            raise serializers.ValidationError("Recipients must be a list of email addresses")
        
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError as DjangoValidationError
        
        for email in value:
            try:
                validate_email(email)
            except DjangoValidationError:
                raise serializers.ValidationError(f"Invalid email address: {email}")
        
        return value
    
    def validate_hour(self, value):
        """Validate hour is within range"""
        if value < 0 or value > 23:
            raise serializers.ValidationError("Hour must be between 0 and 23")
        return value
    
    def validate_day_of_week(self, value):
        """Validate day of week for weekly schedules"""
        if value is not None and (value < 0 or value > 6):
            raise serializers.ValidationError("Day of week must be between 0 (Monday) and 6 (Sunday)")
        return value
    
    def validate_day_of_month(self, value):
        """Validate day of month for monthly schedules"""
        if value is not None and (value < 1 or value > 28):
            raise serializers.ValidationError("Day of month must be between 1 and 28")
        return value
    
    def validate(self, data):
        """Cross-field validation"""
        frequency = data.get('frequency')
        
        # Weekly schedules must have day_of_week
        if frequency == 'WEEKLY' and data.get('day_of_week') is None:
            raise serializers.ValidationError({
                'day_of_week': 'Day of week is required for weekly schedules'
            })
        
        # Monthly schedules must have day_of_month
        if frequency == 'MONTHLY' and data.get('day_of_month') is None:
            raise serializers.ValidationError({
                'day_of_month': 'Day of month is required for monthly schedules'
            })
        
        # Daily schedules should not have day_of_week or day_of_month
        if frequency == 'DAILY':
            if data.get('day_of_week') is not None:
                raise serializers.ValidationError({
                    'day_of_week': 'Day of week should not be set for daily schedules'
                })
            if data.get('day_of_month') is not None:
                raise serializers.ValidationError({
                    'day_of_month': 'Day of month should not be set for daily schedules'
                })
        
        # Validate filters based on export type
        filters = data.get('filters', {})
        export_type = data.get('export_type')
        
        if export_type == 'SALES':
            # Sales exports should have date range in filters
            if 'start_date' not in filters or 'end_date' not in filters:
                raise serializers.ValidationError({
                    'filters': 'Sales exports require start_date and end_date in filters'
                })
        
        elif export_type == 'AUDIT_LOGS':
            # Audit log exports require date range
            if 'start_date' not in filters or 'end_date' not in filters:
                raise serializers.ValidationError({
                    'filters': 'Audit log exports require start_date and end_date in filters'
                })
        
        return data
    
    def create(self, validated_data):
        """Create schedule and calculate next run time"""
        from reports.services import ScheduleCalculator
        
        schedule = ExportSchedule.objects.create(**validated_data)
        
        # Calculate next run time
        calculator = ScheduleCalculator()
        schedule.next_run_at = calculator.calculate_next_run(schedule)
        schedule.save(update_fields=['next_run_at'])
        
        return schedule
    
    def update(self, instance, validated_data):
        """Update schedule and recalculate next run time if needed"""
        from reports.services import ScheduleCalculator
        
        # Track if schedule timing changed
        timing_changed = any([
            validated_data.get('frequency') != instance.frequency,
            validated_data.get('hour') != instance.hour,
            validated_data.get('day_of_week') != instance.day_of_week,
            validated_data.get('day_of_month') != instance.day_of_month,
        ])
        
        # Update instance
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Recalculate next run if timing changed and schedule is active
        if timing_changed and instance.is_active:
            calculator = ScheduleCalculator()
            instance.next_run_at = calculator.calculate_next_run(instance)
            instance.save(update_fields=['next_run_at'])
        
        return instance


class ExportHistorySerializer(serializers.ModelSerializer):
    """Serializer for export history records"""
    
    user_name = serializers.CharField(source='user.name', read_only=True)
    schedule_name = serializers.CharField(source='schedule.name', read_only=True)
    duration_display = serializers.SerializerMethodField()
    file_size_display = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    
    class Meta:
        model = ExportHistory
        fields = [
            'id', 'export_type', 'format', 'trigger', 'status',
            'started_at', 'completed_at', 'created_at',
            'file_name', 'file_size', 'file_path', 'record_count',
            'filters_applied', 'email_sent', 'email_recipients', 'email_sent_at',
            'error_message', 'user', 'user_name', 'schedule', 'schedule_name',
            'duration_display', 'file_size_display', 'status_display',
            'duration_seconds', 'file_size_mb'
        ]
        read_only_fields = ['id', 'created_at', 'duration_seconds', 'file_size_mb']
    
    def get_duration_display(self, obj):
        """Human-readable duration"""
        duration = obj.duration_seconds
        if duration is None:
            return "N/A"
        if duration < 60:
            return f"{int(duration)}s"
        minutes = int(duration / 60)
        seconds = int(duration % 60)
        return f"{minutes}m {seconds}s"
    
    def get_file_size_display(self, obj):
        """Human-readable file size"""
        size_mb = obj.file_size_mb
        if size_mb is None:
            return "N/A"
        if size_mb < 1:
            return f"{int(size_mb * 1024)} KB"
        return f"{size_mb:.2f} MB"
    
    def get_status_display(self, obj):
        """User-friendly status"""
        status_map = {
            'PENDING': 'Pending',
            'PROCESSING': 'Processing...',
            'COMPLETED': 'Completed',
            'FAILED': 'Failed',
            'EMAILED': 'Emailed'
        }
        return status_map.get(obj.status, obj.status)


class ExportHistoryDetailSerializer(ExportHistorySerializer):
    """Detailed serializer with error traceback"""
    
    class Meta(ExportHistorySerializer.Meta):
        fields = ExportHistorySerializer.Meta.fields + ['error_traceback']


class ExportNotificationSettingsSerializer(serializers.ModelSerializer):
    """Serializer for export notification settings"""
    
    class Meta:
        model = ExportNotificationSettings
        fields = [
            'notify_on_success', 'notify_on_failure',
            'default_recipients', 'from_name', 'reply_to_email'
        ]
    
    def validate_default_recipients(self, value):
        """Validate default recipients list"""
        if not isinstance(value, list):
            raise serializers.ValidationError("Default recipients must be a list of email addresses")
        
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError as DjangoValidationError
        
        for email in value:
            try:
                validate_email(email)
            except DjangoValidationError:
                raise serializers.ValidationError(f"Invalid email address: {email}")
        
        return value
    
    def validate_reply_to_email(self, value):
        """Validate reply-to email"""
        if value:
            from django.core.validators import validate_email
            from django.core.exceptions import ValidationError as DjangoValidationError
            try:
                validate_email(value)
            except DjangoValidationError:
                raise serializers.ValidationError("Invalid reply-to email address")
        return value


class TriggerExportSerializer(serializers.Serializer):
    """Serializer for manually triggering a scheduled export"""
    
    schedule_id = serializers.UUIDField(required=True)
    send_email = serializers.BooleanField(default=True)
    override_recipients = serializers.ListField(
        child=serializers.EmailField(),
        required=False
    )

