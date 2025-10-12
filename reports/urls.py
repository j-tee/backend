from django.urls import path, include
from rest_framework.routers import DefaultRouter

# Export views (existing)
from .views.exports import (
    InventoryValuationReportView, 
    SalesExportView, 
    CustomerExportView, 
    InventoryExportView,
    AuditLogExportView,
)

# Automation views (existing - Phase 5)
from .views.automation import (
    ExportScheduleViewSet,
    ExportHistoryViewSet,
    ExportNotificationSettingsViewSet,
)

# Analytical Report views (NEW)
from .views.sales_reports import (
    SalesSummaryReportView,
    ProductPerformanceReportView,
    CustomerAnalyticsReportView,
    RevenueTrendsReportView,
)

# Financial Report views (NEW - Phase 3)
from .views.financial_reports import (
    RevenueProfitReportView,
    ARAgingReportView,
    CollectionRatesReportView,
    CashFlowReportView,
)

# Inventory Report views (NEW - Phase 4)
from .views.inventory_reports import (
    StockLevelsSummaryReportView,
    LowStockAlertsReportView,
    StockMovementHistoryReportView,
    WarehouseAnalyticsReportView,
)

# Router for automation viewsets
router = DefaultRouter()
router.register(r'schedules', ExportScheduleViewSet, basename='export-schedule')
router.register(r'history', ExportHistoryViewSet, basename='export-history')

urlpatterns = [
    # ===== DATA EXPORTS =====
    # (POST endpoints that return binary files)
    path('api/exports/inventory-valuation/', InventoryValuationReportView.as_view(), name='inventory-valuation-export'),
    path('api/exports/sales/', SalesExportView.as_view(), name='sales-export'),
    path('api/exports/customers/', CustomerExportView.as_view(), name='customer-export'),
    path('api/exports/inventory/', InventoryExportView.as_view(), name='inventory-export'),
    path('api/exports/audit/', AuditLogExportView.as_view(), name='audit-log-export'),
    
    # ===== EXPORT AUTOMATION (Phase 5) =====
    path('api/automation/', include(router.urls)),
    path('api/automation/notifications/', 
         ExportNotificationSettingsViewSet.as_view({'get': 'retrieve', 'put': 'update'}), 
         name='export-notifications'),
    
    # ===== ANALYTICAL REPORTS (Phase 1+) =====
    # (GET endpoints that return JSON analytics)
    
    # Sales Reports (Phase 2) - Complete
    path('api/sales/summary/', SalesSummaryReportView.as_view(), name='sales-summary-report'),
    path('api/sales/products/', ProductPerformanceReportView.as_view(), name='product-performance-report'),
    path('api/sales/customer-analytics/', CustomerAnalyticsReportView.as_view(), name='customer-analytics-report'),
    path('api/sales/revenue-trends/', RevenueTrendsReportView.as_view(), name='revenue-trends-report'),
    
    # Financial Reports (Phase 3) - Complete
    path('api/financial/revenue-profit/', RevenueProfitReportView.as_view(), name='revenue-profit-report'),
    path('api/financial/ar-aging/', ARAgingReportView.as_view(), name='ar-aging-report'),
    path('api/financial/collection-rates/', CollectionRatesReportView.as_view(), name='collection-rates-report'),
    path('api/financial/cash-flow/', CashFlowReportView.as_view(), name='cash-flow-report'),
    
    # Inventory Reports (Phase 4) - In Progress
    path('api/inventory/stock-levels/', StockLevelsSummaryReportView.as_view(), name='stock-levels-report'),
    path('api/inventory/low-stock-alerts/', LowStockAlertsReportView.as_view(), name='low-stock-alerts-report'),
    path('api/inventory/movements/', StockMovementHistoryReportView.as_view(), name='stock-movements-report'),
    path('api/inventory/warehouse-analytics/', WarehouseAnalyticsReportView.as_view(), name='warehouse-analytics-report'),
    
    # Customer Reports (Phase 5) - Coming soon
    # path('api/customer/top-customers/', ...),
    # path('api/customer/purchase-patterns/', ...),
    # path('api/customer/credit-utilization/', ...),
    # path('api/customer/segmentation/', ...),
]
