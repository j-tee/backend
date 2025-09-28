from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet, WarehouseViewSet, StoreFrontViewSet, BatchViewSet,
    ProductViewSet, BatchProductViewSet, InventoryViewSet, TransferViewSet,
    StockAlertViewSet, InventorySummaryView, BatchArrivalReportView
)

router = DefaultRouter()
router.register(r'categories', CategoryViewSet)
router.register(r'warehouses', WarehouseViewSet)
router.register(r'storefronts', StoreFrontViewSet)
router.register(r'batches', BatchViewSet)
router.register(r'products', ProductViewSet)
router.register(r'batch-products', BatchProductViewSet)
router.register(r'inventory', InventoryViewSet)
router.register(r'transfers', TransferViewSet)
router.register(r'stock-alerts', StockAlertViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
    path('api/reports/inventory-summary/', InventorySummaryView.as_view(), name='inventory-summary'),
    path('api/reports/batch-arrivals/', BatchArrivalReportView.as_view(), name='batch-arrivals'),
]