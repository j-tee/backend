from rest_framework import viewsets, status, permissions, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, CharFilter, BooleanFilter, UUIDFilter
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum, Count
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.utils import timezone
from decimal import Decimal
from accounts.models import Business, BusinessMembership, BusinessInvitation
from accounts.serializers import (
    BusinessInvitationSerializer,
    BusinessMembershipDetailSerializer,
    BusinessMembershipUpdateSerializer,
    MembershipStorefrontAssignmentSerializer,
)
from accounts.utils import send_business_invitation_email, EmailDeliveryError
from .models import (
    Category, Warehouse, StoreFront, Product, Supplier, Stock, StockProduct,
    Inventory, Transfer, StockAlert,
    BusinessWarehouse, BusinessStoreFront, StoreFrontEmployee, WarehouseEmployee
)
from .serializers import (
    CategorySerializer, WarehouseSerializer, StoreFrontSerializer, 
    StockSerializer, StockProductSerializer, SupplierSerializer, ProductSerializer,
    InventorySerializer, TransferSerializer, StockAlertSerializer,
    InventorySummarySerializer, StockArrivalReportSerializer,
    BusinessWarehouseSerializer, BusinessStoreFrontSerializer,
    StoreFrontEmployeeSerializer, WarehouseEmployeeSerializer,
    ProfitProjectionSerializer, ProfitScenarioSerializer,
    StockProductProfitProjectionSerializer, ProductProfitProjectionSerializer,
    BulkProfitProjectionSerializer, BulkProfitProjectionResponseSerializer
)


User = get_user_model()


class CustomPageNumberPagination(PageNumberPagination):
    """Custom pagination class that allows configurable page size."""
    page_size = 25  # Default page size
    page_size_query_param = 'page_size'
    max_page_size = 100  # Maximum allowed page size


class ProductFilter(FilterSet):
    """Filter class for Product model."""
    search = CharFilter(method='filter_search', label='Search in name and SKU')
    category = UUIDFilter(field_name='category_id')
    is_active = BooleanFilter(field_name='is_active')

    class Meta:
        model = Product
        fields = ['search', 'category', 'is_active']

    def filter_search(self, queryset, name, value):
        """Search in product name and SKU."""
        if not value:
            return queryset
        return queryset.filter(
            Q(name__icontains=value) | Q(sku__icontains=value)
        )


class StockProductFilter(FilterSet):
    """Filter class for StockProduct model."""
    product = UUIDFilter(field_name='product_id')
    stock = UUIDFilter(field_name='stock_id')
    supplier = UUIDFilter(field_name='supplier_id')
    has_quantity = BooleanFilter(method='filter_has_quantity', label='Has quantity greater than 0')
    search = CharFilter(method='filter_search', label='Search in product name/SKU')

    class Meta:
        model = StockProduct
        fields = ['product', 'stock', 'supplier', 'has_quantity', 'search']

    def filter_has_quantity(self, queryset, name, value):
        """Filter stock products that have quantity > 0."""
        if value:
            return queryset.filter(quantity__gt=0)
        return queryset

    def filter_search(self, queryset, name, value):
        """Search in product name and SKU."""
        if not value:
            return queryset
        return queryset.filter(
            Q(product__name__icontains=value) | Q(product__sku__icontains=value)
        )


class StockFilter(FilterSet):
    """Filter class for Stock (batch) model."""
    warehouse = UUIDFilter(field_name='warehouse_id')
    search = CharFilter(method='filter_search', label='Search in description or reference')

    class Meta:
        model = Stock
        fields = ['warehouse', 'search']

    def filter_search(self, queryset, name, value):
        """Search in description."""
        if not value:
            return queryset
        return queryset.filter(description__icontains=value)


def _business_ids_for_user(user):
    ids = set()
    if getattr(user, 'account_type', None) == getattr(User, 'ACCOUNT_OWNER', 'OWNER'):
        ids.update(user.owned_businesses.values_list('id', flat=True))
    ids.update(
        user.business_memberships.filter(is_active=True).values_list('business_id', flat=True)
    )
    return list(ids)


def _get_primary_business_for_owner(user):
    if getattr(user, 'account_type', None) != getattr(User, 'ACCOUNT_OWNER', 'OWNER'):
        return None
    return user.owned_businesses.first()


def _ensure_business_admin(user, business):
    if user.is_superuser or getattr(user, 'is_platform_super_admin', False):
        return

    membership = BusinessMembership.objects.filter(
        business=business,
        user=user,
        is_active=True,
    ).first()

    if not membership or membership.role not in {BusinessMembership.OWNER, BusinessMembership.ADMIN}:
        raise PermissionDenied('You do not have permission to manage this business.')


class CategoryViewSet(viewsets.ModelViewSet):
    """ViewSet for managing product categories"""
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]


class WarehouseViewSet(viewsets.ModelViewSet):
    """ViewSet for managing warehouses"""
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Warehouse.objects.select_related('manager', 'business_link__business')
        user = self.request.user
        if user.is_superuser:
            return queryset

        business_ids = _business_ids_for_user(user)
        if not business_ids:
            return queryset.none()
        return queryset.filter(business_link__business_id__in=business_ids)

    def perform_create(self, serializer):
        user = self.request.user
        business = _get_primary_business_for_owner(user)
        if business is None:
            raise PermissionDenied('Only business owners with an active business can create warehouses.')

        warehouse = serializer.save()
        try:
            BusinessWarehouse.objects.create(business=business, warehouse=warehouse)
        except IntegrityError:
            raise ValidationError({'warehouse': 'This warehouse is already linked to a business.'})

        WarehouseEmployee.objects.get_or_create(
            business=business,
            warehouse=warehouse,
            user=user,
            defaults={'role': BusinessMembership.OWNER, 'is_active': True}
        )

    def perform_update(self, serializer):
        if self.request.user.is_superuser:
            serializer.save()
            return

        instance = self.get_object()
        if instance.business_link and instance.business_link.business_id not in _business_ids_for_user(self.request.user):
            raise PermissionDenied('You do not have permission to update this warehouse.')
        serializer.save()

    def perform_destroy(self, instance):
        if self.request.user.is_superuser:
            instance.delete()
            return

        if instance.business_link and instance.business_link.business_id not in _business_ids_for_user(self.request.user):
            raise PermissionDenied('You do not have permission to delete this warehouse.')
        instance.delete()


class StoreFrontViewSet(viewsets.ModelViewSet):
    """ViewSet for managing store fronts"""
    queryset = StoreFront.objects.all()
    serializer_class = StoreFrontSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = StoreFront.objects.select_related('user', 'manager', 'business_link__business')
        user = self.request.user
        if user.is_superuser:
            return queryset

        business_ids = _business_ids_for_user(user)
        if not business_ids:
            return queryset.none()
        return queryset.filter(business_link__business_id__in=business_ids)

    def perform_create(self, serializer):
        user = self.request.user
        business = _get_primary_business_for_owner(user)
        if business is None:
            raise PermissionDenied('Only business owners with an active business can create store fronts.')

        storefront = serializer.save(user=user)
        try:
            BusinessStoreFront.objects.create(business=business, storefront=storefront)
        except IntegrityError:
            raise ValidationError({'storefront': 'This store front is already linked to a business.'})

        StoreFrontEmployee.objects.get_or_create(
            business=business,
            storefront=storefront,
            user=user,
            defaults={'role': BusinessMembership.OWNER, 'is_active': True}
        )

    def perform_update(self, serializer):
        if self.request.user.is_superuser:
            serializer.save()
            return

        instance = self.get_object()
        if instance.business_link and instance.business_link.business_id not in _business_ids_for_user(self.request.user):
            raise PermissionDenied('You do not have permission to update this store front.')
        serializer.save()

    def perform_destroy(self, instance):
        if self.request.user.is_superuser:
            instance.delete()
            return

        if instance.business_link and instance.business_link.business_id not in _business_ids_for_user(self.request.user):
            raise PermissionDenied('You do not have permission to delete this store front.')
        instance.delete()


class ProductViewSet(viewsets.ModelViewSet):
    """ViewSet for managing products with pagination, filtering, and ordering."""
    queryset = Product.objects.select_related('category', 'business').all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CustomPageNumberPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'sku']
    ordering_fields = ['name', 'sku', 'created_at', 'updated_at']
    ordering = ['name']  # Default ordering by name

    def get_queryset(self):
        queryset = Product.objects.select_related('category', 'business')
        user = self.request.user
        if user.is_superuser:
            return queryset

        business_ids = _business_ids_for_user(user)
        if not business_ids:
            return queryset.none()
        return queryset.filter(business_id__in=business_ids)

    def perform_create(self, serializer):
        user = self.request.user
        business = _get_primary_business_for_owner(user)
        if business is None:
            raise PermissionDenied('Only business owners with an active business can create products.')
        serializer.save(business=business)

    def perform_update(self, serializer):
        if self.request.user.is_superuser:
            serializer.save()
            return

        instance = self.get_object()
        business_ids = _business_ids_for_user(self.request.user)
        if instance.business_id not in business_ids:
            raise PermissionDenied('You do not have permission to update this product.')
        serializer.save()

    def perform_destroy(self, instance):
        if self.request.user.is_superuser:
            instance.delete()
            return

        business_ids = _business_ids_for_user(self.request.user)
        if instance.business_id not in business_ids:
            raise PermissionDenied('You do not have permission to delete this product.')
        instance.delete()


class BusinessInvitationListCreateView(generics.ListCreateAPIView):
    serializer_class = BusinessInvitationSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CustomPageNumberPagination

    def get_business(self):
        business = get_object_or_404(Business, id=self.kwargs['business_id'])
        _ensure_business_admin(self.request.user, business)
        return business

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['business'] = self.get_business()
        return context

    def get_queryset(self):
        business = self.get_business()
        queryset = BusinessInvitation.objects.filter(business=business).order_by('-created_at')
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param.upper())
        return queryset

    def perform_create(self, serializer):
        invitation = serializer.save()
        if not serializer._send_email:
            serializer.context['show_token'] = True
        elif serializer._send_email:
            try:
                send_business_invitation_email(invitation)
            except EmailDeliveryError as exc:
                raise ValidationError({'email': str(exc)}) from exc


class BusinessInvitationResendView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, invitation_id):
        invitation = get_object_or_404(BusinessInvitation, id=invitation_id)
        _ensure_business_admin(request.user, invitation.business)

        if invitation.status == BusinessInvitation.STATUS_ACCEPTED:
            return Response({'detail': 'Invitation already accepted.'}, status=status.HTTP_409_CONFLICT)
        if invitation.status == BusinessInvitation.STATUS_REVOKED:
            return Response({'detail': 'Invitation has been revoked.'}, status=status.HTTP_410_GONE)

        invitation.initialize_token()
        invitation.save(update_fields=['token', 'expires_at', 'updated_at'])

        try:
            send_business_invitation_email(invitation)
        except EmailDeliveryError as exc:
            raise ValidationError({'email': str(exc)}) from exc

        return Response({'detail': 'Invitation email resent.'}, status=status.HTTP_202_ACCEPTED)


class BusinessInvitationRevokeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, invitation_id):
        invitation = get_object_or_404(BusinessInvitation, id=invitation_id)
        _ensure_business_admin(request.user, invitation.business)

        if invitation.status == BusinessInvitation.STATUS_ACCEPTED:
            return Response({'detail': 'Cannot revoke an accepted invitation.'}, status=status.HTTP_409_CONFLICT)

        invitation.mark_revoked()
        return Response({'detail': 'Invitation revoked.'}, status=status.HTTP_200_OK)


class BusinessMembershipListView(generics.ListAPIView):
    serializer_class = BusinessMembershipDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CustomPageNumberPagination

    def get_business(self):
        business = get_object_or_404(Business, id=self.kwargs['business_id'])
        _ensure_business_admin(self.request.user, business)
        return business

    def get_queryset(self):
        business = self.get_business()
        queryset = BusinessMembership.objects.filter(business=business).select_related('user').order_by('-created_at')

        role = self.request.query_params.get('role')
        if role:
            queryset = queryset.filter(role=role)

        status_param = self.request.query_params.get('status')
        if status_param:
            status_upper = status_param.upper()
            if status_upper == 'ACTIVE':
                queryset = queryset.filter(is_active=True)
            elif status_upper == 'SUSPENDED':
                queryset = queryset.filter(is_active=False)

        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(user__name__icontains=search) | Q(user__email__icontains=search)
            )

        return queryset


class BusinessMembershipDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = BusinessMembershipDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    lookup_url_kwarg = 'membership_id'

    def get_queryset(self):
        return BusinessMembership.objects.select_related('business', 'user')

    def get_object(self):
        membership = super().get_object()
        _ensure_business_admin(self.request.user, membership.business)
        return membership

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return BusinessMembershipUpdateSerializer
        return BusinessMembershipDetailSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        membership = self.get_object()
        context['membership'] = membership
        return context

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        if request.method == 'PATCH':
            partial = True
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        detail_serializer = BusinessMembershipDetailSerializer(instance, context={'request': request})
        return Response(detail_serializer.data)

    def delete(self, request, *args, **kwargs):
        membership = self.get_object()
        membership.is_active = False
        membership.save(update_fields=['is_active', 'updated_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class BusinessMembershipStorefrontAssignmentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request, membership_id):
        membership = get_object_or_404(BusinessMembership.objects.select_related('business', 'user'), id=membership_id)
        _ensure_business_admin(request.user, membership.business)

        serializer = MembershipStorefrontAssignmentSerializer(data=request.data, context={'membership': membership, 'request': request})
        serializer.is_valid(raise_exception=True)
        storefront_ids = set(serializer.validated_data['storefronts'])

        now = timezone.now()
        with transaction.atomic():
            existing_assignments = list(StoreFrontEmployee.objects.filter(business=membership.business, user=membership.user))
            existing_ids = {assignment.storefront_id for assignment in existing_assignments}

            for assignment in existing_assignments:
                if assignment.storefront_id in storefront_ids:
                    if not assignment.is_active:
                        assignment.is_active = True
                        assignment.removed_at = None
                        assignment.assigned_at = now
                        assignment.save(update_fields=['is_active', 'removed_at', 'assigned_at'])
                else:
                    if assignment.is_active:
                        assignment.is_active = False
                        assignment.removed_at = now
                        assignment.save(update_fields=['is_active', 'removed_at'])

            to_create = storefront_ids - existing_ids
            for storefront_id in to_create:
                StoreFrontEmployee.objects.create(
                    business=membership.business,
                    storefront_id=storefront_id,
                    user=membership.user,
                    role=membership.role,
                    is_active=True,
                )

        detail_serializer = BusinessMembershipDetailSerializer(membership, context={'request': request})
        return Response(detail_serializer.data, status=status.HTTP_200_OK)


class StockViewSet(viewsets.ModelViewSet):
    """ViewSet for managing stock batches with pagination, filtering, and ordering."""
    queryset = Stock.objects.select_related('warehouse').all()
    serializer_class = StockSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CustomPageNumberPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = StockFilter
    search_fields = ['description']
    ordering_fields = ['arrival_date', 'created_at', 'updated_at']
    ordering = ['-arrival_date']  # Default ordering by newest arrivals first

    def get_queryset(self):
        queryset = Stock.objects.select_related('warehouse')
        user = self.request.user
        if user.is_superuser:
            return queryset.prefetch_related('items__product')

        business_ids = _business_ids_for_user(user)
        if not business_ids:
            return queryset.none()
        return queryset.filter(warehouse__business_link__business_id__in=business_ids).prefetch_related('items__product')

    def perform_create(self, serializer):
        user = self.request.user
        business = _get_primary_business_for_owner(user)
        if business is None:
            raise PermissionDenied('Only business owners with an active business can create stock receipts.')

        stock = serializer.save()
        BusinessWarehouse.objects.get_or_create(business=business, warehouse=stock.warehouse)

    def perform_update(self, serializer):
        if self.request.user.is_superuser:
            serializer.save()
            return

        instance = self.get_object()
        if instance.warehouse.business_link and instance.warehouse.business_link.business_id not in _business_ids_for_user(self.request.user):
            raise PermissionDenied('You do not have permission to update this stock receipt.')
        serializer.save()


class StockProductViewSet(viewsets.ModelViewSet):
    """Manage individual stock line items with pagination, filtering, and ordering."""

    queryset = StockProduct.objects.select_related('product', 'supplier', 'stock__warehouse').all()
    serializer_class = StockProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CustomPageNumberPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = StockProductFilter
    search_fields = ['product__name', 'product__sku', 'description']
    ordering_fields = ['quantity', 'unit_cost', 'landed_unit_cost', 'expiry_date', 'created_at', 'updated_at']
    ordering = ['-created_at']  # Default ordering by newest first

    def get_queryset(self):
        queryset = StockProduct.objects.select_related('product', 'supplier', 'stock__warehouse')
        user = self.request.user
        if user.is_superuser:
            return queryset

        business_ids = _business_ids_for_user(user)
        if not business_ids:
            return queryset.none()
        return queryset.filter(stock__warehouse__business_link__business_id__in=business_ids)

    def perform_create(self, serializer):
        user = self.request.user
        business = _get_primary_business_for_owner(user)
        if business is None:
            raise PermissionDenied('Only business owners with an active business can create stock line items.')

        # Validate that product and supplier belong to the same business
        product = serializer.validated_data.get('product')
        supplier = serializer.validated_data.get('supplier')
        
        if product and product.business_id != business.id:
            raise ValidationError({'product': 'Product does not belong to your business.'})
        if supplier and supplier.business_id != business.id:
            raise ValidationError({'supplier': 'Supplier does not belong to your business.'})

        stock = serializer.validated_data.get('stock')
        if stock and stock.warehouse:
            BusinessWarehouse.objects.get_or_create(business=business, warehouse=stock.warehouse)
        serializer.save()

    def perform_update(self, serializer):
        if self.request.user.is_superuser:
            serializer.save()
            return

        instance = self.get_object()
        business_ids = _business_ids_for_user(self.request.user)
        if instance.stock and instance.stock.warehouse and instance.stock.warehouse.business_link and instance.stock.warehouse.business_link.business_id not in business_ids:
            raise PermissionDenied('You do not have permission to update this stock item.')
        serializer.save()


class SupplierViewSet(viewsets.ModelViewSet):
    """ViewSet for managing suppliers with pagination and search."""
    queryset = Supplier.objects.select_related('business').all()
    serializer_class = SupplierSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CustomPageNumberPagination
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ['name', 'contact_person', 'email']
    ordering_fields = ['name', 'created_at', 'updated_at']
    ordering = ['name']  # Default ordering by name

    def get_queryset(self):
        queryset = Supplier.objects.select_related('business')
        user = self.request.user
        if user.is_superuser:
            return queryset

        business_ids = _business_ids_for_user(user)
        if not business_ids:
            return queryset.none()
        return queryset.filter(business_id__in=business_ids)

    def perform_create(self, serializer):
        user = self.request.user
        business = _get_primary_business_for_owner(user)
        if business is None:
            raise PermissionDenied('Only business owners with an active business can create suppliers.')
        serializer.save(business=business)

    def perform_update(self, serializer):
        if self.request.user.is_superuser:
            serializer.save()
            return

        instance = self.get_object()
        business_ids = _business_ids_for_user(self.request.user)
        if instance.business_id not in business_ids:
            raise PermissionDenied('You do not have permission to update this supplier.')
        serializer.save()

    def perform_destroy(self, instance):
        if self.request.user.is_superuser:
            instance.delete()
            return

        business_ids = _business_ids_for_user(self.request.user)
        if instance.business_id not in business_ids:
            raise PermissionDenied('You do not have permission to delete this supplier.')
        instance.delete()


class InventoryViewSet(viewsets.ModelViewSet):
    """ViewSet for managing inventory"""
    queryset = Inventory.objects.select_related('product', 'warehouse', 'stock__supplier', 'stock__stock', 'stock__warehouse').all()
    serializer_class = InventorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Inventory.objects.select_related(
            'product',
            'warehouse',
            'stock__supplier',
            'stock__stock',
            'stock__warehouse',
        )
        user = self.request.user
        if user.is_superuser or getattr(user, 'is_platform_super_admin', False):
            return queryset

        business_ids = _business_ids_for_user(user)
        if not business_ids:
            return queryset.none()

        return queryset.filter(
            Q(product__business_id__in=business_ids) |
            Q(warehouse__business_link__business_id__in=business_ids) |
            Q(stock__warehouse__business_link__business_id__in=business_ids)
        ).distinct()


class TransferViewSet(viewsets.ModelViewSet):
    """ViewSet for managing transfers"""
    queryset = Transfer.objects.select_related(
        'product', 'stock__stock', 'stock__supplier', 'from_warehouse', 'to_storefront',
        'requested_by', 'approved_by'
    ).all()
    serializer_class = TransferSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = Transfer.objects.select_related(
            'product',
            'stock__stock',
            'stock__supplier',
            'from_warehouse',
            'to_storefront',
            'requested_by',
            'approved_by',
        )
        user = self.request.user
        if user.is_superuser or getattr(user, 'is_platform_super_admin', False):
            return queryset

        business_ids = _business_ids_for_user(user)
        if not business_ids:
            return queryset.none()

        return queryset.filter(
            Q(product__business_id__in=business_ids) |
            Q(from_warehouse__business_link__business_id__in=business_ids) |
            Q(to_storefront__business_link__business_id__in=business_ids)
        ).distinct()


class StockAlertViewSet(viewsets.ModelViewSet):
    """ViewSet for managing stock alerts"""
    queryset = StockAlert.objects.all()
    serializer_class = StockAlertSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = StockAlert.objects.select_related('product', 'warehouse')
        user = self.request.user
        if user.is_superuser or getattr(user, 'is_platform_super_admin', False):
            return queryset

        business_ids = _business_ids_for_user(user)
        if not business_ids:
            return queryset.none()

        return queryset.filter(
            Q(product__business_id__in=business_ids) |
            Q(warehouse__business_link__business_id__in=business_ids)
        ).distinct()


class BusinessWarehouseViewSet(viewsets.ModelViewSet):
    """Manage warehouse-business associations"""
    queryset = BusinessWarehouse.objects.select_related('business', 'warehouse').all()
    serializer_class = BusinessWarehouseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = BusinessWarehouse.objects.select_related('business', 'warehouse')
        user = self.request.user
        if user.is_superuser or getattr(user, 'is_platform_super_admin', False):
            return queryset

        business_ids = _business_ids_for_user(user)
        if not business_ids:
            return queryset.none()

        return queryset.filter(business_id__in=business_ids)


class BusinessStoreFrontViewSet(viewsets.ModelViewSet):
    """Manage storefront-business associations"""
    queryset = BusinessStoreFront.objects.select_related('business', 'storefront', 'storefront__user').all()
    serializer_class = BusinessStoreFrontSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = BusinessStoreFront.objects.select_related('business', 'storefront', 'storefront__user')
        user = self.request.user
        if user.is_superuser or getattr(user, 'is_platform_super_admin', False):
            return queryset

        business_ids = _business_ids_for_user(user)
        if not business_ids:
            return queryset.none()

        return queryset.filter(business_id__in=business_ids)


class StoreFrontEmployeeViewSet(viewsets.ModelViewSet):
    """Manage storefront employee assignments"""
    queryset = StoreFrontEmployee.objects.select_related('business', 'storefront', 'user').all()
    serializer_class = StoreFrontEmployeeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = StoreFrontEmployee.objects.select_related('business', 'storefront', 'user')
        user = self.request.user
        if user.is_superuser or getattr(user, 'is_platform_super_admin', False):
            return queryset

        business_ids = _business_ids_for_user(user)
        if not business_ids:
            return queryset.none()

        return queryset.filter(business_id__in=business_ids)


class WarehouseEmployeeViewSet(viewsets.ModelViewSet):
    """Manage warehouse employee assignments"""
    queryset = WarehouseEmployee.objects.select_related('business', 'warehouse', 'user').all()
    serializer_class = WarehouseEmployeeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = WarehouseEmployee.objects.select_related('business', 'warehouse', 'user')
        user = self.request.user
        if user.is_superuser or getattr(user, 'is_platform_super_admin', False):
            return queryset

        business_ids = _business_ids_for_user(user)
        if not business_ids:
            return queryset.none()

        return queryset.filter(business_id__in=business_ids)


class InventorySummaryView(APIView):
    """View for inventory summary reports"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        # Basic implementation - can be expanded
        data = []
        return Response(data)


class StockArrivalReportView(APIView):
    """View for stock arrival reports"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        # Basic implementation - can be expanded
        data = []
        return Response(data)


class OwnerWorkspaceView(APIView):
    """Return consolidated store front and warehouse data for business owners."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        if getattr(user, 'account_type', None) != getattr(User, 'ACCOUNT_OWNER', 'OWNER'):
            raise PermissionDenied('Only business owners can access the owner workspace overview.')

        business = _get_primary_business_for_owner(user)
        if not business:
            return Response(
                {
                    'business': None,
                    'storefronts': [],
                    'warehouses': [],
                },
                status=status.HTTP_200_OK,
            )

        storefront_qs = StoreFront.objects.select_related('manager', 'user').filter(
            business_link__business=business
        )
        warehouse_qs = Warehouse.objects.select_related('manager').filter(
            business_link__business=business
        )

        storefront_data = StoreFrontSerializer(storefront_qs, many=True, context={'request': request}).data
        warehouse_data = WarehouseSerializer(warehouse_qs, many=True, context={'request': request}).data

        business_summary = {
            'id': str(business.id),
            'name': business.name,
            'storefront_count': len(storefront_data),
            'warehouse_count': len(warehouse_data),
        }

        return Response(
            {
                'business': business_summary,
                'storefronts': storefront_data,
                'warehouses': warehouse_data,
            },
            status=status.HTTP_200_OK,
        )


class ProfitProjectionViewSet(viewsets.ViewSet):
    """ViewSet for profit projection calculations"""
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Get base queryset for user's business"""
        user = self.request.user
        if user.is_superuser:
            return StockProduct.objects.select_related('product', 'supplier', 'stock__warehouse')

        business_ids = _business_ids_for_user(user)
        if not business_ids:
            return StockProduct.objects.none()
        return StockProduct.objects.filter(
            stock__warehouse__business_link__business_id__in=business_ids
        ).select_related('product', 'supplier', 'stock__warehouse')

    @action(detail=False, methods=['post'], url_path='stock-product')
    def stock_product_projection(self, request):
        """
        Calculate profit projection for a specific stock product with custom retail/wholesale percentages.
        
        POST data:
        {
            "stock_product_id": "uuid",
            "retail_percentage": 70.00,
            "wholesale_percentage": 30.00
        }
        """
        serializer = ProfitProjectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        stock_product_id = request.data.get('stock_product_id')
        retail_percentage = serializer.validated_data['retail_percentage']
        wholesale_percentage = serializer.validated_data['wholesale_percentage']
        
        try:
            stock_product = self.get_queryset().get(id=stock_product_id)
        except StockProduct.DoesNotExist:
            return Response(
                {'error': 'Stock product not found or access denied'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get all scenarios
        scenarios = stock_product.get_expected_profit_scenarios()
        
        # Get requested scenario
        requested_scenario = stock_product.get_expected_profit_for_scenario(
            retail_percentage, wholesale_percentage
        )
        
        response_data = {
            'stock_product_id': str(stock_product.id),
            'product_name': stock_product.product.name,
            'product_sku': stock_product.product.sku,
            'quantity': stock_product.quantity,
            'landed_unit_cost': stock_product.landed_unit_cost,
            'retail_price': stock_product.retail_price,
            'wholesale_price': stock_product.wholesale_price,
            'requested_scenario': requested_scenario,
            'retail_only': scenarios['retail_only'],
            'wholesale_only': scenarios['wholesale_only'],
            'mixed_scenarios': scenarios['mixed_scenarios'],
        }
        
        return Response(response_data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='product')
    def product_projection(self, request):
        """
        Calculate profit projection for a product (across all stock products) with custom retail/wholesale percentages.
        
        POST data:
        {
            "product_id": "uuid",
            "retail_percentage": 70.00,
            "wholesale_percentage": 30.00,
            "warehouse_id": "uuid (optional)",
            "supplier_id": "uuid (optional)"
        }
        """
        serializer = ProfitProjectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        product_id = request.data.get('product_id')
        retail_percentage = serializer.validated_data['retail_percentage']
        wholesale_percentage = serializer.validated_data['wholesale_percentage']
        warehouse_id = request.data.get('warehouse_id')
        supplier_id = request.data.get('supplier_id')
        
        # Get product and verify access
        try:
            product = Product.objects.filter(
                business_id__in=_business_ids_for_user(self.request.user)
            ).get(id=product_id)
        except Product.DoesNotExist:
            return Response(
                {'error': 'Product not found or access denied'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get profit summary for the product
        summary = product.get_expected_profit_summary(
            warehouse=warehouse_id,
            supplier=supplier_id,
            retail_percentage=retail_percentage,
            wholesale_percentage=wholesale_percentage
        )
        
        # Also get retail-only and wholesale-only summaries for comparison
        retail_only = product.get_expected_profit_summary(
            warehouse=warehouse_id,
            supplier=supplier_id,
            retail_percentage=Decimal('100.00'),
            wholesale_percentage=Decimal('0.00')
        )
        
        wholesale_only = product.get_expected_profit_summary(
            warehouse=warehouse_id,
            supplier=supplier_id,
            retail_percentage=Decimal('0.00'),
            wholesale_percentage=Decimal('100.00')
        )
        
        response_data = {
            'product_id': str(product.id),
            'product_name': product.name,
            'product_sku': product.sku,
            'total_quantity': summary['total_quantity'],
            'stock_products_count': summary['stock_products_count'],
            'requested_scenario': {
                'scenario': summary['scenario'],
                'total_expected_profit': summary['total_expected_profit'],
                'average_expected_margin': summary['average_expected_margin'],
            },
            'retail_only': {
                'scenario': retail_only['scenario'],
                'total_expected_profit': retail_only['total_expected_profit'],
                'average_expected_margin': retail_only['average_expected_margin'],
            },
            'wholesale_only': {
                'scenario': wholesale_only['scenario'],
                'total_expected_profit': wholesale_only['total_expected_profit'],
                'average_expected_margin': wholesale_only['average_expected_margin'],
            },
        }
        
        return Response(response_data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='bulk')
    def bulk_projection(self, request):
        """
        Calculate profit projections for multiple stock products in bulk.
        
        POST data:
        {
            "projections": [
                {
                    "stock_product_id": "uuid",
                    "retail_percentage": 70.00,
                    "wholesale_percentage": 30.00
                },
                {
                    "stock_product_id": "uuid",
                    "retail_percentage": 100.00,
                    "wholesale_percentage": 0.00
                }
            ]
        }
        """
        serializer = BulkProfitProjectionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        projections_data = serializer.validated_data['projections']
        response_projections = []
        
        for projection_data in projections_data:
            stock_product_id = projection_data['stock_product_id']
            retail_percentage = Decimal(str(projection_data.get('retail_percentage', Decimal('100.00'))))
            wholesale_percentage = Decimal(str(projection_data.get('wholesale_percentage', Decimal('0.00'))))
            
            try:
                stock_product = self.get_queryset().get(id=stock_product_id)
            except StockProduct.DoesNotExist:
                # Skip invalid stock products but continue processing others
                continue
            
            # Get all scenarios
            scenarios = stock_product.get_expected_profit_scenarios()
            
            # Get requested scenario
            requested_scenario = stock_product.get_expected_profit_for_scenario(
                retail_percentage, wholesale_percentage
            )
            
            projection_result = {
                'stock_product_id': str(stock_product.id),
                'product_name': stock_product.product.name,
                'product_sku': stock_product.product.sku,
                'quantity': stock_product.quantity,
                'landed_unit_cost': stock_product.landed_unit_cost,
                'retail_price': stock_product.retail_price,
                'wholesale_price': stock_product.wholesale_price,
                'requested_scenario': requested_scenario,
                'retail_only': scenarios['retail_only'],
                'wholesale_only': scenarios['wholesale_only'],
                'mixed_scenarios': scenarios['mixed_scenarios'],
            }
            
            response_projections.append(projection_result)
        
        return Response(
            {'projections': response_projections},
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['get'], url_path='scenarios')
    def available_scenarios(self, request):
        """
        Get list of predefined profit projection scenarios.
        
        Returns common retail/wholesale combinations that users can choose from.
        """
        scenarios = [
            {
                'id': 'retail_only',
                'name': 'Retail Only',
                'description': 'All units sold at retail price',
                'retail_percentage': 100.00,
                'wholesale_percentage': 0.00,
            },
            {
                'id': 'wholesale_only',
                'name': 'Wholesale Only',
                'description': 'All units sold at wholesale price',
                'retail_percentage': 0.00,
                'wholesale_percentage': 100.00,
            },
            {
                'id': 'mixed_90_10',
                'name': '90% Retail, 10% Wholesale',
                'description': '90% of units at retail, 10% at wholesale',
                'retail_percentage': 90.00,
                'wholesale_percentage': 10.00,
            },
            {
                'id': 'mixed_80_20',
                'name': '80% Retail, 20% Wholesale',
                'description': '80% of units at retail, 20% at wholesale',
                'retail_percentage': 80.00,
                'wholesale_percentage': 20.00,
            },
            {
                'id': 'mixed_70_30',
                'name': '70% Retail, 30% Wholesale',
                'description': '70% of units at retail, 30% at wholesale',
                'retail_percentage': 70.00,
                'wholesale_percentage': 30.00,
            },
            {
                'id': 'mixed_60_40',
                'name': '60% Retail, 40% Wholesale',
                'description': '60% of units at retail, 40% at wholesale',
                'retail_percentage': 60.00,
                'wholesale_percentage': 40.00,
            },
            {
                'id': 'mixed_50_50',
                'name': '50% Retail, 50% Wholesale',
                'description': '50% of units at retail, 50% at wholesale',
                'retail_percentage': 50.00,
                'wholesale_percentage': 50.00,
            },
            {
                'id': 'mixed_40_60',
                'name': '40% Retail, 60% Wholesale',
                'description': '40% of units at retail, 60% at wholesale',
                'retail_percentage': 40.00,
                'wholesale_percentage': 60.00,
            },
            {
                'id': 'mixed_30_70',
                'name': '30% Retail, 70% Wholesale',
                'description': '30% of units at retail, 70% at wholesale',
                'retail_percentage': 30.00,
                'wholesale_percentage': 70.00,
            },
            {
                'id': 'mixed_20_80',
                'name': '20% Retail, 80% Wholesale',
                'description': '20% of units at retail, 80% at wholesale',
                'retail_percentage': 20.00,
                'wholesale_percentage': 80.00,
            },
            {
                'id': 'mixed_10_90',
                'name': '10% Retail, 90% Wholesale',
                'description': '10% of units at retail, 90% at wholesale',
                'retail_percentage': 10.00,
                'wholesale_percentage': 90.00,
            },
        ]
        
        return Response({'scenarios': scenarios}, status=status.HTTP_200_OK)
