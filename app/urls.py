"""
URL configuration for SaaS POS Backend project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from accounts.views import BusinessInvitationInfoView, BusinessInvitationAcceptView
from .views import landing_page, api_docs
from subscriptions.views import calculate_subscription_pricing, subscription_status

urlpatterns = [
    path('', landing_page, name='landing'),
    path('api/docs/', api_docs, name='api-docs'),
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('inventory/', include('inventory.urls')),
    path('sales/', include('sales.urls')),
    path('bookkeeping/', include('bookkeeping.urls')),
    path('subscriptions/', include('subscriptions.urls')),
    path('reports/', include('reports.urls')),
    path('settings/', include('settings.urls')),
    path('ai/', include('ai_features.urls')),
    path('auth/invitations/<str:token>/', BusinessInvitationInfoView.as_view(), name='invitation-info'),
    path('auth/invitations/<str:token>/accept/', BusinessInvitationAcceptView.as_view(), name='invitation-accept'),
    # Subscription API aliases at root level for frontend compatibility
    path('api/pricing/calculate/', calculate_subscription_pricing, name='root-pricing-calculate'),
    path('api/subscription/status/', subscription_status, name='root-subscription-status'),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
