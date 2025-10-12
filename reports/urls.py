from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    InventoryValuationReportView, 
    SalesExportView, 
    CustomerExportView, 
    InventoryExportView,
    AuditLogExportView,
)
from .automation_views import (
    ExportScheduleViewSet,
    ExportHistoryViewSet,
    ExportNotificationSettingsViewSet,
)

# Router for automation viewsets
router = DefaultRouter()
router.register(r'schedules', ExportScheduleViewSet, basename='export-schedule')
router.register(r'history', ExportHistoryViewSet, basename='export-history')

urlpatterns = [
    # Export endpoints (existing)
    path('api/inventory/valuation/', InventoryValuationReportView.as_view(), name='inventory-valuation-report'),
    path('api/sales/export/', SalesExportView.as_view(), name='sales-export'),
    path('api/customers/export/', CustomerExportView.as_view(), name='customer-export'),
    path('api/inventory/export/', InventoryExportView.as_view(), name='inventory-export'),
    path('api/audit/export/', AuditLogExportView.as_view(), name='audit-log-export'),
    
    # Automation endpoints (Phase 5)
    path('api/automation/', include(router.urls)),
    path('api/automation/notifications/', 
         ExportNotificationSettingsViewSet.as_view({'get': 'retrieve', 'put': 'update'}), 
         name='export-notifications'),
]
