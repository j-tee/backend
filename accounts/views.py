from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.db.models import Q
from .models import Role, User, UserProfile, AuditLog, Business, BusinessMembership
from .serializers import (
    RoleSerializer, UserSerializer, UserProfileSerializer, AuditLogSerializer,
    LoginSerializer, ChangePasswordSerializer, BusinessSerializer,
    BusinessMembershipSerializer, BusinessRegistrationSerializer
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


class UserViewSet(viewsets.ModelViewSet):
    """ViewSet for managing users"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter users based on permissions"""
        queryset = User.objects.all()
        
        # Allow users to see their own profile
        if not self.request.user.is_admin():
            queryset = queryset.filter(id=self.request.user.id)
        
        # Add search functionality
        search = self.request.query_params.get('search', None)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(email__icontains=search)
            )
        
        return queryset.select_related('role')
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user's profile"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a user account"""
        user = self.get_object()
        user.is_active = True
        user.save()
        return Response({'status': 'User activated'})
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a user account"""
        user = self.get_object()
        user.is_active = False
        user.save()
        return Response({'status': 'User deactivated'})


class UserProfileViewSet(viewsets.ModelViewSet):
    """ViewSet for managing user profiles"""
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Users can only see their own profile"""
        if self.request.user.is_admin():
            return UserProfile.objects.all()
        return UserProfile.objects.filter(user=self.request.user)


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


class RegisterBusinessView(APIView):
    """Public endpoint for registering a user and business simultaneously."""
    permission_classes = [permissions.AllowAny]
    throttle_classes = []

    def post(self, request):
        serializer = BusinessRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            result = serializer.save()
            business_data = BusinessSerializer(result['business'], context={'request': request}).data
            user_data = UserSerializer(result['user'], context={'request': request}).data
            response_data = {
                'token': result['token'],
                'user': user_data,
                'business': business_data
            }
            return Response(response_data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
