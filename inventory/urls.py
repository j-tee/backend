from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet, WarehouseViewSet, StoreFrontViewSet,
    ProductViewSet, StockViewSet, StockProductViewSet, SupplierViewSet,
    TransferRequestViewSet,
    StockAlertViewSet, BusinessWarehouseViewSet, BusinessStoreFrontViewSet,
    StoreFrontEmployeeViewSet, WarehouseEmployeeViewSet,
    InventorySummaryView, StockArrivalReportView, EmployeeWorkspaceView, OwnerWorkspaceView, ProfitProjectionViewSet,
    BusinessInvitationListCreateView, BusinessInvitationResendView, BusinessInvitationRevokeView,
    BusinessMembershipListView, BusinessMembershipDetailView, BusinessMembershipStorefrontAssignmentView,
    WarehouseStockAvailabilityView, StockAvailabilityView,
)
from .adjustment_views import (
    StockAdjustmentViewSet,
    StockAdjustmentPhotoViewSet,
    StockAdjustmentDocumentViewSet,
    StockCountViewSet,
    StockCountItemViewSet,
)
from .transfer_views import (
    WarehouseTransferViewSet,
    StorefrontTransferViewSet,
    TransferWorkflowViewSet,
)

router = DefaultRouter()
router.register(r'categories', CategoryViewSet)
router.register(r'warehouses', WarehouseViewSet)
router.register(r'storefronts', StoreFrontViewSet)
router.register(r'products', ProductViewSet)
router.register(r'stock', StockViewSet)
router.register(r'stock-products', StockProductViewSet)
router.register(r'transfer-requests', TransferRequestViewSet)
router.register(r'stock-alerts', StockAlertViewSet)
router.register(r'business-warehouses', BusinessWarehouseViewSet)
router.register(r'business-storefronts', BusinessStoreFrontViewSet)
router.register(r'storefront-employees', StoreFrontEmployeeViewSet)
router.register(r'warehouse-employees', WarehouseEmployeeViewSet)
router.register(r'profit-projections', ProfitProjectionViewSet, basename='profit-projections')
router.register(r'suppliers', SupplierViewSet)
# Stock Adjustment endpoints
router.register(r'stock-adjustments', StockAdjustmentViewSet, basename='stock-adjustments')
router.register(r'adjustment-photos', StockAdjustmentPhotoViewSet, basename='adjustment-photos')
router.register(r'adjustment-documents', StockAdjustmentDocumentViewSet, basename='adjustment-documents')
router.register(r'stock-counts', StockCountViewSet, basename='stock-counts')
router.register(r'stock-count-items', StockCountItemViewSet, basename='stock-count-items')
# Phase 4: New Transfer endpoints (replaces legacy stock-adjustments/transfer)
router.register(r'warehouse-transfers', WarehouseTransferViewSet, basename='warehouse-transfers')
router.register(r'storefront-transfers', StorefrontTransferViewSet, basename='storefront-transfers')
router.register(r'transfers', TransferWorkflowViewSet, basename='transfers')

urlpatterns = [
    path('api/stock/availability/', WarehouseStockAvailabilityView.as_view(), name='warehouse-stock-availability'),
    path('api/storefronts/<uuid:storefront_id>/stock-products/<uuid:product_id>/availability/', 
         StockAvailabilityView.as_view(), 
         name='stock-availability'),
    path('api/', include(router.urls)),
    path(
        'api/businesses/<uuid:business_id>/invitations/',
        BusinessInvitationListCreateView.as_view(),
        name='business-invitations'
    ),
    path(
        'api/invitations/<uuid:invitation_id>/resend/',
        BusinessInvitationResendView.as_view(),
        name='business-invitations-resend'
    ),
    path(
        'api/invitations/<uuid:invitation_id>/revoke/',
        BusinessInvitationRevokeView.as_view(),
        name='business-invitations-revoke'
    ),
    path(
        'api/businesses/<uuid:business_id>/memberships/',
        BusinessMembershipListView.as_view(),
        name='business-memberships'
    ),
    path(
        'api/memberships/<uuid:membership_id>/',
        BusinessMembershipDetailView.as_view(),
        name='business-membership-detail'
    ),
    path(
        'api/memberships/<uuid:membership_id>/storefronts/',
        BusinessMembershipStorefrontAssignmentView.as_view(),
        name='business-membership-storefronts'
    ),
    path('api/reports/inventory-summary/', InventorySummaryView.as_view(), name='inventory-summary'),
    path('api/reports/stock-arrivals/', StockArrivalReportView.as_view(), name='stock-arrivals'),
    path('api/employee/workspace/', EmployeeWorkspaceView.as_view(), name='employee-workspace'),
    path('api/owner/workspace/', OwnerWorkspaceView.as_view(), name='owner-workspace'),
    # Removed separate inter-warehouse transfer endpoints; now handled by stock-adjustments/transfer action
]