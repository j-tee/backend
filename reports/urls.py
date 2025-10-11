from django.urls import path

from .views import InventoryValuationReportView, SalesExportView

urlpatterns = [
    path('inventory/valuation/', InventoryValuationReportView.as_view(), name='inventory-valuation-report'),
    path('sales/export/', SalesExportView.as_view(), name='sales-export'),
]
