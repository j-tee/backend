from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SubscriptionPlanViewSet,
    SubscriptionViewSet,
    SubscriptionPaymentViewSet,
    InvoiceViewSet,
    AlertViewSet,
    SubscriptionStatsViewSet,
    PaymentWebhookView,
    SubscriptionPricingTierViewSet,
    TaxConfigurationViewSet,
    ServiceChargeViewSet,
    PaymentStatsViewSet,
    calculate_subscription_pricing,
    paystack_webhook,
    subscription_status,
)

router = DefaultRouter()
router.register(r'plans', SubscriptionPlanViewSet, basename='subscription-plan')
router.register(r'subscriptions', SubscriptionViewSet, basename='subscription')
router.register(r'payments', SubscriptionPaymentViewSet, basename='subscription-payment')
router.register(r'invoices', InvoiceViewSet, basename='invoice')
router.register(r'alerts', AlertViewSet, basename='alert')
router.register(r'stats', SubscriptionStatsViewSet, basename='subscription-stats')
# New flexible pricing endpoints
router.register(r'pricing-tiers', SubscriptionPricingTierViewSet, basename='pricing-tier')
router.register(r'tax-config', TaxConfigurationViewSet, basename='tax-config')
router.register(r'service-charges', ServiceChargeViewSet, basename='service-charge')
router.register(r'payment-stats', PaymentStatsViewSet, basename='payment-stats')

urlpatterns = [
    path('api/', include(router.urls)),
    path('api/webhooks/payment/', PaymentWebhookView.as_view(), name='payment-webhook'),
    # New endpoints for flexible pricing system
    path('api/pricing/calculate/', calculate_subscription_pricing, name='pricing-calculate'),
    path('api/webhooks/paystack/', paystack_webhook, name='paystack-webhook'),
    # Subscription status endpoint for frontend
    path('api/status/', subscription_status, name='subscription-status'),
]
