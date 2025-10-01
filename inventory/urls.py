from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet, WarehouseViewSet, StoreFrontViewSet,
    ProductViewSet, StockViewSet, StockProductViewSet, SupplierViewSet, InventoryViewSet, TransferViewSet,
    StockAlertViewSet, BusinessWarehouseViewSet, BusinessStoreFrontViewSet,
    StoreFrontEmployeeViewSet, WarehouseEmployeeViewSet,
    InventorySummaryView, StockArrivalReportView, OwnerWorkspaceView, ProfitProjectionViewSet
)

router = DefaultRouter()
router.register(r'categories', CategoryViewSet)
router.register(r'warehouses', WarehouseViewSet)
router.register(r'storefronts', StoreFrontViewSet)
router.register(r'products', ProductViewSet)
router.register(r'stock', StockViewSet)
router.register(r'stock-products', StockProductViewSet)
router.register(r'inventory', InventoryViewSet)
router.register(r'transfers', TransferViewSet)
router.register(r'stock-alerts', StockAlertViewSet)
router.register(r'business-warehouses', BusinessWarehouseViewSet)
router.register(r'business-storefronts', BusinessStoreFrontViewSet)
router.register(r'storefront-employees', StoreFrontEmployeeViewSet)
router.register(r'warehouse-employees', WarehouseEmployeeViewSet)
router.register(r'profit-projections', ProfitProjectionViewSet, basename='profit-projections')
router.register(r'suppliers', SupplierViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
    path('api/reports/inventory-summary/', InventorySummaryView.as_view(), name='inventory-summary'),
    path('api/reports/stock-arrivals/', StockArrivalReportView.as_view(), name='stock-arrivals'),
    path('api/owner/workspace/', OwnerWorkspaceView.as_view(), name='owner-workspace'),
]