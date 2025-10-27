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
    BusinessInvitationInfoView,
    BusinessInvitationAcceptView,
)

router = DefaultRouter()
router.register(r'roles', RoleViewSet)
router.register(r'users', UserViewSet)
router.register(r'profiles', UserProfileViewSet)
router.register(r'audit-logs', AuditLogViewSet)
router.register(r'businesses', BusinessViewSet)
router.register(r'business-memberships', BusinessMembershipViewSet)

urlpatterns = [
    # Existing API routes
    path('api/', include(router.urls)),
    
    # Authentication routes
    path('api/auth/login/', LoginView.as_view(), name='login'),
    path('api/auth/logout/', LogoutView.as_view(), name='logout'),
    path('api/auth/change-password/', ChangePasswordView.as_view(), name='change-password-old'),
    path('api/auth/password-reset/request/', RequestPasswordResetView.as_view(), name='password-reset-request'),
    path('api/auth/password-reset/confirm/', ConfirmPasswordResetView.as_view(), name='password-reset-confirm'),
    path('api/auth/register/', RegisterUserView.as_view(), name='register-user'),
    path('api/auth/verify-email/', VerifyEmailView.as_view(), name='verify-email'),
    path('api/auth/register-business/', RegisterBusinessView.as_view(), name='register-business'),
    path('api/auth/invitations/<str:token>/', BusinessInvitationInfoView.as_view(), name='business-invitation-info'),
    path('api/auth/invitations/<str:token>/accept/', BusinessInvitationAcceptView.as_view(), name='business-invitation-accept'),
    
    # RBAC Management routes (new)
    path('api/', include('accounts.rbac_urls')),
    
    # Account Management routes (new)
    path('api/', include('accounts.account_urls')),
]
