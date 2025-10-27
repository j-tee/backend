"""
Account Management URLs
URL patterns for account management API endpoints
"""

from django.urls import path
from .account_views import (
    user_profile,
    upload_profile_picture,
    change_password,
    enable_2fa,
    disable_2fa,
    user_preferences,
    notification_settings
)

urlpatterns = [
    path('profile/', user_profile, name='user-profile'),
    path('profile/picture/', upload_profile_picture, name='upload-profile-picture'),
    path('change-password/', change_password, name='change-password'),
    path('2fa/enable/', enable_2fa, name='enable-2fa'),
    path('2fa/disable/', disable_2fa, name='disable-2fa'),
    path('preferences/', user_preferences, name='user-preferences'),
    path('notifications/', notification_settings, name='notification-settings'),
]
