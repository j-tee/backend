from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SubscriptionPlanViewSet,
    SubscriptionViewSet,
    SubscriptionPaymentViewSet,
    InvoiceViewSet,
    AlertViewSet,
    SubscriptionStatsViewSet,
    PaymentWebhookView
)

router = DefaultRouter()
router.register(r'plans', SubscriptionPlanViewSet, basename='subscription-plan')
router.register(r'subscriptions', SubscriptionViewSet, basename='subscription')
router.register(r'payments', SubscriptionPaymentViewSet, basename='subscription-payment')
router.register(r'invoices', InvoiceViewSet, basename='invoice')
router.register(r'alerts', AlertViewSet, basename='alert')
router.register(r'stats', SubscriptionStatsViewSet, basename='subscription-stats')

urlpatterns = [
    path('api/', include(router.urls)),
    path('api/webhooks/payment/', PaymentWebhookView.as_view(), name='payment-webhook'),
]