from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet, WarehouseViewSet, StoreFrontViewSet, BatchViewSet,
    ProductViewSet, BatchProductViewSet, InventoryViewSet, TransferViewSet,
    StockAlertViewSet, BusinessWarehouseViewSet, BusinessStoreFrontViewSet,
    StoreFrontEmployeeViewSet, WarehouseEmployeeViewSet,
    InventorySummaryView, BatchArrivalReportView
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
router.register(r'business-warehouses', BusinessWarehouseViewSet)
router.register(r'business-storefronts', BusinessStoreFrontViewSet)
router.register(r'storefront-employees', StoreFrontEmployeeViewSet)
router.register(r'warehouse-employees', WarehouseEmployeeViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
    path('api/reports/inventory-summary/', InventorySummaryView.as_view(), name='inventory-summary'),
    path('api/reports/batch-arrivals/', BatchArrivalReportView.as_view(), name='batch-arrivals'),
]