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
    ReportStorefrontListView,
)

# Analytical report views - Financial (Phase 3)
from .financial_reports import (
    RevenueProfitReportView,
    ARAgingReportView,
    CollectionRatesReportView,
    CashFlowReportView,
)

# Analytical report views - Inventory (Phase 4)
from .inventory_reports import (
    StockLevelsSummaryReportView,
    LowStockAlertsReportView,
    StockMovementHistoryReportView,
    WarehouseAnalyticsReportView,
)

# Analytical report views - Customer (Phase 5)
from .customer_reports import (
    CustomerLifetimeValueReportView,
    CustomerSegmentationReportView,
    PurchasePatternAnalysisReportView,
    CustomerRetentionMetricsReportView,
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
    'ReportStorefrontListView',
    
    # Financial Reports
    'RevenueProfitReportView',
    'ARAgingReportView',
    'CollectionRatesReportView',
    'CashFlowReportView',
    
    # Inventory Reports
    'StockLevelsSummaryReportView',
    'LowStockAlertsReportView',
    'StockMovementHistoryReportView',
    'WarehouseAnalyticsReportView',
    
    # Customer Reports
    'CustomerLifetimeValueReportView',
    'CustomerSegmentationReportView',
    'PurchasePatternAnalysisReportView',
    'CustomerRetentionMetricsReportView',
]
