"""
Reports Views Package

Organizes view modules by functionality.
"""

# Export views (existing functionality)
from .exports import (
    InventoryValuationReportView,
    SalesExportView,
    CustomerExportView,
    InventoryExportView,
    AuditLogExportView,
)

# Automation views (existing functionality)
from .automation import (
    ExportScheduleViewSet,
    ExportHistoryViewSet,
    ExportNotificationSettingsViewSet,
)

# Analytical report views (NEW)
from .sales_reports import (
    SalesSummaryReportView,
    ProductPerformanceReportView,
    CustomerAnalyticsReportView,
    RevenueTrendsReportView,
)

__all__ = [
    # Exports
    'InventoryValuationReportView',
    'SalesExportView',
    'CustomerExportView',
    'InventoryExportView',
    'AuditLogExportView',
    
    # Automation
    'ExportScheduleViewSet',
    'ExportHistoryViewSet',
    'ExportNotificationSettingsViewSet',
    
    # Sales Reports
    'SalesSummaryReportView',
    'ProductPerformanceReportView',
    'CustomerAnalyticsReportView',
    'RevenueTrendsReportView',
]
