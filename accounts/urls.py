from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RoleViewSet,
    UserViewSet,
    UserProfileViewSet,
    AuditLogViewSet,
    BusinessViewSet,
    BusinessMembershipViewSet,
    LoginView,
    LogoutView,
    ChangePasswordView,
    RequestPasswordResetView,
    ConfirmPasswordResetView,
    RegisterUserView,
    VerifyEmailView,
    RegisterBusinessView,
)

router = DefaultRouter()
router.register(r'roles', RoleViewSet)
router.register(r'users', UserViewSet)
router.register(r'profiles', UserProfileViewSet)
router.register(r'audit-logs', AuditLogViewSet)
router.register(r'businesses', BusinessViewSet)
router.register(r'business-memberships', BusinessMembershipViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
    path('api/auth/login/', LoginView.as_view(), name='login'),
    path('api/auth/logout/', LogoutView.as_view(), name='logout'),
    path('api/auth/change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('api/auth/password-reset/request/', RequestPasswordResetView.as_view(), name='password-reset-request'),
    path('api/auth/password-reset/confirm/', ConfirmPasswordResetView.as_view(), name='password-reset-confirm'),
    path('api/auth/register/', RegisterUserView.as_view(), name='register-user'),
    path('api/auth/verify-email/', VerifyEmailView.as_view(), name='verify-email'),
    path('api/auth/register-business/', RegisterBusinessView.as_view(), name='register-business'),
]