from django.urls import path

from .views import InventoryValuationReportView

urlpatterns = [
    path('inventory/valuation/', InventoryValuationReportView.as_view(), name='inventory-valuation-report'),
]
