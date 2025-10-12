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

# Analytical report views - Sales (Phase 2)
from .sales_reports import (
    SalesSummaryReportView,
    ProductPerformanceReportView,
    CustomerAnalyticsReportView,
    RevenueTrendsReportView,
)

# Analytical report views - Financial (Phase 3)
from .financial_reports import (
    RevenueProfitReportView,
    ARAgingReportView,
    CollectionRatesReportView,
    CashFlowReportView,
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
    
    # Financial Reports
    'RevenueProfitReportView',
    'ARAgingReportView',
    'CollectionRatesReportView',
    'CashFlowReportView',
]
