from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CustomerViewSet, SaleViewSet, SaleItemViewSet, PaymentViewSet,
    RefundViewSet, RefundItemViewSet, CreditTransactionViewSet,
    SalesReportView, CustomerCreditReportView
)

router = DefaultRouter()
router.register(r'customers', CustomerViewSet)
router.register(r'sales', SaleViewSet)
router.register(r'sale-items', SaleItemViewSet)
router.register(r'payments', PaymentViewSet)
router.register(r'refunds', RefundViewSet)
router.register(r'refund-items', RefundItemViewSet)
router.register(r'credit-transactions', CreditTransactionViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
    path('api/reports/sales/', SalesReportView.as_view(), name='sales-report'),
    path('api/reports/customer-credit/', CustomerCreditReportView.as_view(), name='customer-credit-report'),
]