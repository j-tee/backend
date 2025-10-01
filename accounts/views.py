from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, ProtectedError
from django.conf import settings
from django.http import HttpResponseRedirect
from urllib.parse import urlencode
from rest_framework.exceptions import PermissionDenied
from .models import Role, User, UserProfile, AuditLog, Business, BusinessMembership
from .serializers import (
    RoleSerializer,
    UserSerializer,
    UserProfileSerializer,
    AuditLogSerializer,
    LoginSerializer,
    ChangePasswordSerializer,
    BusinessSerializer,
    BusinessMembershipSerializer,
    UserRegistrationSerializer,
    EmailVerificationSerializer,
    OwnerBusinessRegistrationSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
)


def get_managed_business_ids(user):
    """Return active business IDs where user is owner or admin."""
    if not user.is_authenticated:
        return []
    return list(
        user.business_memberships.filter(
            is_active=True,
            role__in=[BusinessMembership.OWNER, BusinessMembership.ADMIN],
        ).values_list('business_id', flat=True)
    )


class RoleViewSet(viewsets.ModelViewSet):
    """ViewSet for managing user roles"""
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_permissions(self):
        """Only admins can create, update, or delete roles"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [permissions.IsAuthenticated]
            return [permission() for permission in permission_classes]
        return super().get_permissions()

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response(
                {'detail': 'Role is assigned to existing users and cannot be deleted.'},
                status=status.HTTP_400_BAD_REQUEST,
            )


class UserViewSet(viewsets.ModelViewSet):
    """ViewSet for managing users"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def _ensure_can_modify(self, actor: User, target: User):
        if actor == target or actor.is_superuser or actor.is_admin():
            return

        managed_business_ids = get_managed_business_ids(actor)
        if not managed_business_ids:
            raise PermissionDenied('You do not have permission to modify this user.')

        has_membership = BusinessMembership.objects.filter(
            business_id__in=managed_business_ids,
            user=target,
            is_active=True,
        ).exists()

        if not has_membership:
            raise PermissionDenied('You do not have permission to modify this user.')
    
    def get_queryset(self):
        """Filter users based on permissions"""
        user = self.request.user
        queryset = User.objects.all()

        if user.is_superuser or user.is_admin():
            allowed_queryset = queryset
        else:
            managed_business_ids = get_managed_business_ids(user)
            if managed_business_ids:
                allowed_queryset = queryset.filter(
                    Q(id=user.id) |
                    Q(business_memberships__business_id__in=managed_business_ids)
                )
            else:
                allowed_queryset = queryset.filter(id=user.id)

        # Add search functionality
        search = self.request.query_params.get('search', None)
        if search:
            allowed_queryset = allowed_queryset.filter(
                Q(name__icontains=search) | 
                Q(email__icontains=search)
            )

        return (
            allowed_queryset
            .select_related('role')
            .prefetch_related('business_memberships__business')
            .distinct()
        )
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user's profile"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a user account"""
        user = self.get_object()
        self._ensure_can_modify(request.user, user)
        user.is_active = True
        user.save()
        return Response({'status': 'User activated'})
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a user account"""
        user = self.get_object()
        self._ensure_can_modify(request.user, user)
        user.is_active = False
        user.save()
        return Response({'status': 'User deactivated'})

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        self._ensure_can_modify(request.user, instance)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        self._ensure_can_modify(request.user, instance)
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self._ensure_can_modify(request.user, instance)
        return super().destroy(request, *args, **kwargs)


class UserProfileViewSet(viewsets.ModelViewSet):
    """ViewSet for managing user profiles"""
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Users can only see permitted profiles"""
        user = self.request.user

        if user.is_superuser or user.is_admin():
            return UserProfile.objects.select_related('user')

        managed_business_ids = get_managed_business_ids(user)
        if managed_business_ids:
            return UserProfile.objects.select_related('user').filter(
                Q(user=user) |
                Q(user__business_memberships__business_id__in=managed_business_ids)
            ).distinct()

        return UserProfile.objects.select_related('user').filter(user=user)

    def _ensure_can_modify(self, actor: User, profile: UserProfile):
        if actor == profile.user or actor.is_superuser or actor.is_admin():
            return

        managed_business_ids = get_managed_business_ids(actor)
        if not managed_business_ids:
            raise PermissionDenied('You do not have permission to modify this profile.')

        has_membership = BusinessMembership.objects.filter(
            business_id__in=managed_business_ids,
            user=profile.user,
            is_active=True,
        ).exists()

        if not has_membership:
            raise PermissionDenied('You do not have permission to modify this profile.')

    def update(self, request, *args, **kwargs):
        profile = self.get_object()
        self._ensure_can_modify(request.user, profile)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        profile = self.get_object()
        self._ensure_can_modify(request.user, profile)
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        profile = self.get_object()
        self._ensure_can_modify(request.user, profile)
        return super().destroy(request, *args, **kwargs)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing audit logs (read-only)"""
    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Only admins can view all audit logs"""
        queryset = AuditLog.objects.all()
        
        if not self.request.user.is_admin():
            # Regular users can only see their own actions
            queryset = queryset.filter(user=self.request.user)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(timestamp__gte=start_date)
        if end_date:
            queryset = queryset.filter(timestamp__lte=end_date)
        
        return queryset.select_related('user')


class BusinessViewSet(viewsets.ModelViewSet):
    """ViewSet for managing businesses"""
    queryset = Business.objects.all().prefetch_related('memberships__user')
    serializer_class = BusinessSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        base_queryset = Business.objects.all().prefetch_related('memberships__user')
        if user.is_superuser or user.is_admin():
            return base_queryset
        return base_queryset.filter(memberships__user=user).distinct()

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class BusinessMembershipViewSet(viewsets.ModelViewSet):
    """ViewSet for managing business memberships"""
    queryset = BusinessMembership.objects.select_related('business', 'user').all()
    serializer_class = BusinessMembershipSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.is_admin():
            return self.queryset
        return self.queryset.filter(business__memberships__user=user).distinct()

    def perform_create(self, serializer):
        serializer.save(invited_by=self.request.user)


class LoginView(APIView):
    """User login view"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            token, created = Token.objects.get_or_create(user=user)
            
            return Response({
                'token': token.key,
                'user': UserSerializer(user).data
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    """User logout view"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            # Delete the user's token
            Token.objects.filter(user=request.user).delete()
            return Response({'message': 'Successfully logged out'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChangePasswordView(APIView):
    """Change user password view"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = request.user
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            
            # Delete all tokens to force re-login
            Token.objects.filter(user=user).delete()
            
            return Response({'message': 'Password changed successfully'}, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RequestPasswordResetView(APIView):
    """Initiate password reset by sending a token to the user's email."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                'message': 'If the email is associated with an account, password reset instructions have been sent.',
            },
            status=status.HTTP_200_OK,
        )


class ConfirmPasswordResetView(APIView):
    """Complete password reset by providing a valid token and new password."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({'message': 'Password updated successfully. You can now sign in.'}, status=status.HTTP_200_OK)


class RegisterUserView(APIView):
    """Endpoint for creating a user account with email verification."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {
                    'message': 'Account created. Check your email for the verification link.',
                    'user_id': str(user.id),
                    'account_type': user.account_type,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name='dispatch')
class VerifyEmailView(APIView):
    """Confirm email addresses using a verification token."""

    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def _validate_token(self, token, request):
        serializer = EmailVerificationSerializer(data={'token': token}, context={'request': request})
        if serializer.is_valid():
            user = serializer.save()
            return True, user, {}
        return False, None, serializer.errors

    def _redirect_with_status(self, status_value, message):
        frontend_base = getattr(settings, 'FRONTEND_URL', '').rstrip('/') or 'http://localhost:3000'
        params = urlencode({'status': status_value, 'message': message})
        return HttpResponseRedirect(f"{frontend_base}/verify-email?{params}")

    def get(self, request):
        token = request.query_params.get('token')
        if not token:
            return self._redirect_with_status('error', 'Verification token is missing.')

        success, user, errors = self._validate_token(token, request)
        if success:
            return self._redirect_with_status('success', 'Email verified successfully. You can now sign in.')

        # Extract the first error message to display to the user
        message = next(iter(errors.values()))[0] if errors else 'Invalid or expired verification token.'
        return self._redirect_with_status('error', message)

    def post(self, request):
        serializer = EmailVerificationSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {
                    'message': 'Email verified successfully. You can now log in.',
                    'user_id': str(user.id),
                    'account_type': user.account_type,
                },
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RegisterBusinessView(APIView):
    """Allow verified business owners to register their business."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user

        if user.account_type != User.ACCOUNT_OWNER:
            return Response({'detail': 'Only owner accounts can register a business.'}, status=status.HTTP_403_FORBIDDEN)

        if not user.email_verified:
            return Response({'detail': 'Verify your email before registering a business.'}, status=status.HTTP_403_FORBIDDEN)

        if user.owned_businesses.exists():
            return Response({'detail': 'You have already registered a business.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = OwnerBusinessRegistrationSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            business = serializer.save()
            response_data = {
                'business': BusinessSerializer(business, context={'request': request}).data,
                'user': UserSerializer(request.user, context={'request': request}).data,
            }
            return Response(response_data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
