from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BusinessSettingsViewSet

# Create a simple custom route since we only have one settings object per business
app_name = 'settings'

urlpatterns = [
    path('api/settings/', BusinessSettingsViewSet.as_view({
        'get': 'list',
        'patch': 'partial_update',
        'put': 'update',
        'post': 'create'
    }), name='settings-detail'),
    path('api/settings/reset_to_defaults/', BusinessSettingsViewSet.as_view({
        'post': 'reset_to_defaults'
    }), name='settings-reset'),
]
