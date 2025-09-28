from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    RoleViewSet, UserViewSet, UserProfileViewSet, AuditLogViewSet,
    LoginView, LogoutView, ChangePasswordView
)

router = DefaultRouter()
router.register(r'roles', RoleViewSet)
router.register(r'users', UserViewSet)
router.register(r'profiles', UserProfileViewSet)
router.register(r'audit-logs', AuditLogViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
    path('api/auth/login/', LoginView.as_view(), name='login'),
    path('api/auth/logout/', LogoutView.as_view(), name='logout'),
    path('api/auth/change-password/', ChangePasswordView.as_view(), name='change-password'),
]