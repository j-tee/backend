"""
Audit log export service for compliance and security tracking
"""
from __future__ import annotations

from typing import Dict, Any
from django.db.models import QuerySet, Count
from django.utils import timezone
from datetime import datetime

from sales.models import AuditLog
from .base import BaseDataExporter


class AuditLogExporter(BaseDataExporter):
    """Export audit logs for compliance and security tracking"""
    
    def build_queryset(self, filters: Dict[str, Any]) -> QuerySet:
        """Build filtered audit log queryset"""
        queryset = AuditLog.objects.select_related(
            'user',
            'sale',
            'sale__business',
            'customer',
            'payment',
            'refund',
        )
        
        # Filter by business through sales
        # Note: AuditLog doesn't have direct business link, so we filter through related objects
        if self.business_ids is not None:
            if not self.business_ids:
                # User has no business access
                return AuditLog.objects.none()
            
            # Filter by sales from user's businesses OR events by the user themselves
            from django.db.models import Q
            queryset = queryset.filter(
                Q(sale__business_id__in=self.business_ids) |
                Q(customer__business_id__in=self.business_ids) |
                Q(user__memberships__business_id__in=self.business_ids)
            ).distinct()
        
        # Date range filters (required)
        if filters.get('start_date'):
            start_datetime = timezone.make_aware(
                datetime.combine(filters['start_date'], datetime.min.time())
            )
            queryset = queryset.filter(timestamp__gte=start_datetime)
        
        if filters.get('end_date'):
            end_datetime = timezone.make_aware(
                datetime.combine(filters['end_date'], datetime.max.time())
            )
            queryset = queryset.filter(timestamp__lte=end_datetime)
        
        # Event type filter
        if filters.get('event_type'):
            queryset = queryset.filter(event_type=filters['event_type'])
        
        # User filter
        if filters.get('user_id'):
            queryset = queryset.filter(user_id=filters['user_id'])
        
        # Entity filters
        if filters.get('sale_id'):
            queryset = queryset.filter(sale_id=filters['sale_id'])
        
        if filters.get('customer_id'):
            queryset = queryset.filter(customer_id=filters['customer_id'])
        
        return queryset.order_by('-timestamp')
    
    def serialize_data(self, queryset: QuerySet, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Convert audit logs to export-ready format"""
        if filters is None:
            filters = {}
        
        # Summary calculations
        total_events = queryset.count()
        
        # Event type breakdown
        event_breakdown = queryset.values('event_type').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # User activity breakdown
        user_breakdown = queryset.values(
            'user__id',
            'user__email',
            'user__name'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:10]  # Top 10 users
        
        # Date range
        first_event = queryset.order_by('timestamp').first()
        last_event = queryset.order_by('-timestamp').first()
        
        summary = {
            'export_date': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_events': total_events,
            'date_range_start': filters.get('start_date', '').strftime('%Y-%m-%d') if filters.get('start_date') else '',
            'date_range_end': filters.get('end_date', '').strftime('%Y-%m-%d') if filters.get('end_date') else '',
            'first_event_time': first_event.timestamp.strftime('%Y-%m-%d %H:%M:%S') if first_event else '',
            'last_event_time': last_event.timestamp.strftime('%Y-%m-%d %H:%M:%S') if last_event else '',
            'unique_users': queryset.values('user').distinct().count(),
            'unique_event_types': queryset.values('event_type').distinct().count(),
        }
        
        # Add event type breakdown to summary
        for idx, event in enumerate(event_breakdown[:10], 1):  # Top 10 event types
            event_label = dict(AuditLog.EVENT_TYPES).get(event['event_type'], event['event_type'])
            summary[f'event_{idx}_type'] = event_label
            summary[f'event_{idx}_count'] = event['count']
        
        # Add user breakdown to summary
        for idx, user in enumerate(user_breakdown, 1):
            user_name = user.get('user__name') or user.get('user__email') or 'Unknown'
            summary[f'user_{idx}_name'] = user_name
            summary[f'user_{idx}_count'] = user['count']
        
        # Detailed audit log entries
        audit_data = []
        
        for log in queryset:
            # Determine entity reference
            entity_type = ''
            entity_id = ''
            entity_name = ''
            
            if log.sale:
                entity_type = 'Sale'
                entity_id = str(log.sale.id)
                entity_name = f"Sale #{log.sale.id}"
            elif log.customer:
                entity_type = 'Customer'
                entity_id = str(log.customer.id)
                entity_name = log.customer.name
            elif log.payment:
                entity_type = 'Payment'
                entity_id = str(log.payment.id)
                entity_name = f"Payment #{log.payment.id}"
            elif log.refund:
                entity_type = 'Refund'
                entity_id = str(log.refund.id)
                entity_name = f"Refund #{log.refund.id}"
            
            # Get event type label
            event_label = dict(AuditLog.EVENT_TYPES).get(log.event_type, log.event_type)
            
            # Parse event data
            event_details = self._format_event_data(log.event_data)
            
            audit_row = {
                'log_id': str(log.id),
                'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'event_type': log.event_type,
                'event_label': event_label,
                'user_email': log.user.email if log.user else '',
                'user_name': log.user.name if (log.user and hasattr(log.user, 'name')) else '',
                'entity_type': entity_type,
                'entity_id': entity_id,
                'entity_name': entity_name,
                'description': log.description or '',
                'event_details': event_details,
                'ip_address': log.ip_address or '',
                'user_agent': log.user_agent or '',
            }
            
            audit_data.append(audit_row)
        
        return {
            'summary': summary,
            'audit_logs': audit_data,
        }
    
    def _format_event_data(self, event_data: dict) -> str:
        """Format event_data JSON into readable string"""
        if not event_data:
            return ''
        
        # Format key-value pairs
        details = []
        for key, value in event_data.items():
            # Skip internal fields
            if key.startswith('_'):
                continue
            
            # Format key
            formatted_key = key.replace('_', ' ').title()
            
            # Format value
            if isinstance(value, dict):
                # Nested dict - just show keys
                formatted_value = ', '.join(value.keys())
            elif isinstance(value, list):
                formatted_value = f"{len(value)} items"
            else:
                formatted_value = str(value)
            
            details.append(f"{formatted_key}: {formatted_value}")
        
        return '; '.join(details)
