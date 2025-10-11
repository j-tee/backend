from django.urls import path

from .views import InventoryValuationReportView, SalesExportView, CustomerExportView, InventoryExportView

urlpatterns = [
    path('inventory/valuation/', InventoryValuationReportView.as_view(), name='inventory-valuation-report'),
    path('sales/export/', SalesExportView.as_view(), name='sales-export'),
    path('customers/export/', CustomerExportView.as_view(), name='customer-export'),
    path('inventory/export/', InventoryExportView.as_view(), name='inventory-export'),
]
