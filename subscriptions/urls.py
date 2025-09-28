from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SubscriptionPlanViewSet, SubscriptionViewSet, SubscriptionPaymentViewSet,
    PaymentGatewayConfigViewSet, WebhookEventViewSet, UsageTrackingViewSet,
    InvoiceViewSet, PaymentWebhookView, SubscriptionReportView
)

router = DefaultRouter()
router.register(r'plans', SubscriptionPlanViewSet)
router.register(r'subscriptions', SubscriptionViewSet)
router.register(r'payments', SubscriptionPaymentViewSet)
router.register(r'gateway-configs', PaymentGatewayConfigViewSet)
router.register(r'webhook-events', WebhookEventViewSet)
router.register(r'usage-tracking', UsageTrackingViewSet)
router.register(r'invoices', InvoiceViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
    path('api/webhooks/payment/', PaymentWebhookView.as_view(), name='payment-webhook'),
    path('api/reports/subscriptions/', SubscriptionReportView.as_view(), name='subscription-report'),
]