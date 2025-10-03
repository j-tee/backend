from collections import defaultdict
from uuid import UUID

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
    Inventory, StoreFrontInventory, Transfer, TransferLineItem, TransferAuditEntry, TransferRequest, StockAlert,
    BusinessWarehouse, BusinessStoreFront, StoreFrontEmployee, WarehouseEmployee
)
from .serializers import (
    CategorySerializer, WarehouseSerializer, StoreFrontSerializer, 
    StockSerializer, StockProductSerializer, SupplierSerializer, ProductSerializer,
    InventorySerializer, TransferSerializer, TransferRequestSerializer, StockAlertSerializer,
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
    if not getattr(user, 'is_authenticated', False):
        return []

    ids = set()

    owned_qs = getattr(user, 'owned_businesses', None)
    if owned_qs is not None and getattr(user, 'account_type', None) == getattr(User, 'ACCOUNT_OWNER', 'OWNER'):
        ids.update(owned_qs.values_list('id', flat=True))

    memberships_qs = getattr(user, 'business_memberships', None)
    if memberships_qs is not None:
        ids.update(
            memberships_qs.filter(is_active=True).values_list('business_id', flat=True)
        )

    return list(ids)


def _filter_queryset_by_business(queryset, request, business_lookup, allowed_business_ids=None):
    business_param = request.query_params.get('business') or request.query_params.get('business_id')

    if business_param:
        try:
            business_uuid = UUID(business_param)
        except (TypeError, ValueError):
            raise ValidationError({'business': 'Invalid business id supplied.'})

        if allowed_business_ids is not None:
            normalized_allowed = {str(bid) for bid in allowed_business_ids}
            if str(business_uuid) not in normalized_allowed:
                return queryset.none()

        return queryset.filter(**{business_lookup: business_uuid})

    if allowed_business_ids is not None:
        if not allowed_business_ids:
            return queryset.none()
        return queryset.filter(**{f'{business_lookup}__in': allowed_business_ids})

    return queryset


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
        if user.is_superuser or getattr(user, 'is_platform_super_admin', False):
            return _filter_queryset_by_business(queryset, self.request, 'business_link__business_id')

        business_ids = _business_ids_for_user(user)
        if not business_ids:
            return queryset.none()

        return _filter_queryset_by_business(
            queryset,
            self.request,
            'business_link__business_id',
            allowed_business_ids=business_ids,
        )

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
        if user.is_superuser or getattr(user, 'is_platform_super_admin', False):
            return _filter_queryset_by_business(queryset, self.request, 'business_link__business_id')

        business_ids = _business_ids_for_user(user)
        if not business_ids:
            return queryset.none()

        return _filter_queryset_by_business(
            queryset,
            self.request,
            'business_link__business_id',
            allowed_business_ids=business_ids,
        )

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
    """Manage warehouse → storefront transfers with workflow actions."""

    queryset = Transfer.objects.select_related(
        'business', 'source_warehouse', 'destination_storefront',
        'requested_by', 'approved_by', 'fulfilled_by'
    ).prefetch_related('line_items__product', 'audit_entries__actor')
    serializer_class = TransferSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'source_warehouse', 'destination_storefront']
    search_fields = ['reference', 'line_items__product__name', 'line_items__product__sku']
    ordering_fields = ['created_at', 'updated_at', 'reference']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_superuser or getattr(user, 'is_platform_super_admin', False):
            return queryset

        business_ids = _business_ids_for_user(user)
        if not business_ids:
            return queryset.none()

        return queryset.filter(business_id__in=business_ids)

    def perform_create(self, serializer):
        warehouse = serializer.validated_data.get('source_warehouse')
        link = getattr(warehouse, 'business_link', None)
        business = link.business if link else serializer.validated_data.get('business')
        self._ensure_membership(business)
        serializer.save(requested_by=self.request.user, business=business)

    def perform_update(self, serializer):
        transfer = self.get_object()
        self._ensure_membership(transfer.business)
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        transfer = self.get_object()
        if not transfer.is_editable:
            raise ValidationError('Only draft or rejected transfers can be deleted.')
        self._ensure_membership(
            transfer.business,
            allowed_roles={BusinessMembership.OWNER, BusinessMembership.ADMIN, BusinessMembership.MANAGER}
        )
        transfer.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _ensure_membership(self, business: Business | None, allowed_roles: set[str] | None = None):
        user = self.request.user
        if user.is_superuser or getattr(user, 'is_platform_super_admin', False):
            return None

        if business is None:
            raise PermissionDenied('Unable to resolve business context for this transfer.')

        membership = BusinessMembership.objects.filter(
            business=business,
            user=user,
            is_active=True,
        ).first()

        if not membership:
            raise PermissionDenied('You are not a member of this business.')

        if allowed_roles and membership.role not in allowed_roles:
            raise PermissionDenied('You do not have the required role for this action.')

        return membership

    def _apply_line_item_updates(self, transfer: Transfer, payload, field_name: str):
        if not payload:
            return

        line_map = {str(item.id): item for item in transfer.line_items.all()}
        updates = []

        for item in payload:
            item_id = item.get('id')
            if not item_id:
                raise ValidationError({'line_items': 'Each adjustment must include an "id" field.'})
            line = line_map.get(str(item_id))
            if not line:
                raise ValidationError({'line_items': f'Line item {item_id} was not found for this transfer.'})
            if field_name not in item:
                continue
            value = item[field_name]
            if value is None:
                continue
            if int(value) < 0:
                raise ValidationError({'line_items': f'{field_name} cannot be negative.'})
            setattr(line, field_name, int(value))
            updates.append(line)

        for line in updates:
            line.save(update_fields=[field_name, 'updated_at'])

    def _manager_roles(self):
        return {BusinessMembership.OWNER, BusinessMembership.ADMIN, BusinessMembership.MANAGER}

    def _confirm_roles(self):
        return self._manager_roles()

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        transfer = self.get_object()
        self._ensure_membership(transfer.business)
        transfer.submit(request.user)
        transfer.refresh_from_db()
        return Response(self.get_serializer(transfer).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        transfer = self.get_object()
        self._ensure_membership(transfer.business, allowed_roles=self._manager_roles())
        self._apply_line_item_updates(transfer, request.data.get('line_items', []), 'approved_quantity')
        transfer.approve(request.user)
        transfer.refresh_from_db()
        return Response(self.get_serializer(transfer).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        transfer = self.get_object()
        self._ensure_membership(transfer.business, allowed_roles=self._manager_roles())
        reason = request.data.get('reason')
        if not reason:
            raise ValidationError({'reason': 'This field is required.'})
        transfer.reject(request.user, reason)
        transfer.refresh_from_db()
        return Response(self.get_serializer(transfer).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='dispatch')
    def dispatch_transfer(self, request, pk=None):
        transfer = self.get_object()
        self._ensure_membership(transfer.business, allowed_roles=self._manager_roles())
        self._apply_line_item_updates(transfer, request.data.get('line_items', []), 'fulfilled_quantity')
        with transaction.atomic():
            transfer.dispatch(request.user)
        transfer.refresh_from_db()
        return Response(self.get_serializer(transfer).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        transfer = self.get_object()
        self._ensure_membership(transfer.business, allowed_roles=self._manager_roles())
        self._apply_line_item_updates(transfer, request.data.get('line_items', []), 'fulfilled_quantity')
        with transaction.atomic():
            transfer.complete(request.user)
        transfer.refresh_from_db()
        return Response(self.get_serializer(transfer).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        transfer = self.get_object()
        self._ensure_membership(transfer.business, allowed_roles=self._manager_roles())
        reason = request.data.get('reason')
        transfer.cancel(request.user, reason)
        transfer.refresh_from_db()
        return Response(self.get_serializer(transfer).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='confirm-receipt')
    def confirm_receipt(self, request, pk=None):
        transfer = self.get_object()
        request_link = getattr(transfer, 'request', None)
        if request_link and request.user == request_link.requested_by:
            self._ensure_membership(transfer.business)
        elif request.user == transfer.requested_by:
            self._ensure_membership(transfer.business)
        else:
            self._ensure_membership(transfer.business, allowed_roles=self._confirm_roles())
        notes = request.data.get('notes')
        transfer.confirm_receipt(request.user, notes)
        transfer.refresh_from_db()
        return Response(self.get_serializer(transfer).data, status=status.HTTP_200_OK)


class TransferRequestViewSet(viewsets.ModelViewSet):
    """Manage storefront-originated transfer requests."""

    queryset = TransferRequest.objects.select_related(
        'business', 'storefront', 'storefront__business_link__business',
        'requested_by', 'fulfilled_by', 'cancelled_by'
    ).prefetch_related('line_items__product')
    serializer_class = TransferRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CustomPageNumberPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'storefront', 'priority']
    search_fields = ['notes', 'line_items__product__name', 'line_items__product__sku']
    ordering_fields = ['created_at', 'updated_at', 'priority']
    ordering = ['-created_at']

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_superuser or getattr(user, 'is_platform_super_admin', False):
            return queryset

        business_ids = _business_ids_for_user(user)
        if not business_ids:
            return queryset.none()

        return queryset.filter(business_id__in=business_ids)

    def _creator_roles(self):
        return {
            BusinessMembership.OWNER,
            BusinessMembership.ADMIN,
            BusinessMembership.MANAGER,
            BusinessMembership.STAFF,
        }

    def _manager_roles(self):
        return {BusinessMembership.OWNER, BusinessMembership.ADMIN, BusinessMembership.MANAGER}

    def _ensure_membership(self, business: Business, allowed_roles: set[str] | None = None):
        user = self.request.user
        if user.is_superuser or getattr(user, 'is_platform_super_admin', False):
            return None

        membership = BusinessMembership.objects.filter(
            business=business,
            user=user,
            is_active=True,
        ).first()

        if not membership:
            raise PermissionDenied('You are not a member of this business.')

        if allowed_roles and membership.role not in allowed_roles:
            raise PermissionDenied('You do not have the required role for this action.')

        return membership

    def perform_create(self, serializer):
        storefront = serializer.validated_data.get('storefront')
        if storefront is None:
            raise ValidationError({'storefront': 'This field is required.'})

        link = getattr(storefront, 'business_link', None)
        if not link:
            raise ValidationError({'storefront': 'Storefront must belong to an active business.'})

        business = link.business
        self._ensure_membership(business, allowed_roles=self._creator_roles())
        serializer.save(business=business, requested_by=self.request.user)

    def perform_update(self, serializer):
        instance = self.get_object()
        user = self.request.user
        if user == instance.requested_by and instance.status == TransferRequest.STATUS_NEW:
            self._ensure_membership(instance.business)
        else:
            self._ensure_membership(instance.business, allowed_roles=self._manager_roles())
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        raise ValidationError('Transfer requests cannot be deleted. Use the cancel action instead.')

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        transfer_request = self.get_object()
        if transfer_request.status not in {TransferRequest.STATUS_NEW, TransferRequest.STATUS_ASSIGNED}:
            raise ValidationError({'status': 'Only new or assigned requests can be cancelled.'})

        if transfer_request.status == TransferRequest.STATUS_NEW and request.user == transfer_request.requested_by:
            self._ensure_membership(transfer_request.business)
        else:
            self._ensure_membership(transfer_request.business, allowed_roles=self._manager_roles())

        transfer_request.mark_cancelled(request.user)
        transfer_request.refresh_from_db()
        return Response(self.get_serializer(transfer_request).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def fulfill(self, request, pk=None):
        transfer_request = self.get_object()
        if transfer_request.status != TransferRequest.STATUS_ASSIGNED:
            raise ValidationError({'status': 'Only assigned requests can be fulfilled.'})

        transfer = transfer_request._current_transfer()
        if not transfer:
            raise ValidationError({'linked_transfer': 'Request is not linked to a transfer.'})
        if transfer.status not in {Transfer.STATUS_IN_TRANSIT, Transfer.STATUS_COMPLETED}:
            raise ValidationError({'linked_transfer': 'Linked transfer must be in transit or completed before fulfillment.'})

        if request.user == transfer_request.requested_by:
            self._ensure_membership(transfer_request.business)
        else:
            self._ensure_membership(transfer_request.business, allowed_roles=self._manager_roles())

        transfer_request.mark_fulfilled(request.user)
        transfer_request.refresh_from_db()
        return Response(self.get_serializer(transfer_request).data, status=status.HTTP_200_OK)

class StockAvailabilityView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        warehouse_id = request.query_params.get('warehouse')
        product_id = request.query_params.get('product')
        quantity_param = request.query_params.get('quantity', '0')

        missing = [param for param, value in [('warehouse', warehouse_id), ('product', product_id)] if not value]
        if missing:
            raise ValidationError({field: 'This field is required.' for field in missing})

        try:
            requested_quantity = int(quantity_param)
        except (TypeError, ValueError):
            raise ValidationError({'quantity': 'Quantity must be an integer.'})

        if requested_quantity < 0:
            raise ValidationError({'quantity': 'Quantity must be zero or greater.'})

        warehouse = get_object_or_404(Warehouse.objects.select_related('business_link__business'), id=warehouse_id)
        product = get_object_or_404(Product.objects.select_related('business'), id=product_id)

        link = getattr(warehouse, 'business_link', None)
        if not link:
            raise ValidationError({'warehouse': 'Warehouse is not linked to a business.'})

        business = link.business

        if product.business_id != business.id:
            raise ValidationError({'product': 'Product does not belong to the warehouse business.'})

        user = request.user
        if not (user.is_superuser or getattr(user, 'is_platform_super_admin', False)):
            business_ids = _business_ids_for_user(user)
            if business.id not in business_ids:
                raise PermissionDenied('You do not have access to this business.')

        available_quantity = Transfer.available_quantity(warehouse, product)
        is_available = available_quantity >= requested_quantity

        if is_available:
            message = 'Sufficient stock on hand.'
        else:
            message = f"Only {available_quantity} units available at {warehouse.name}."

        return Response(
            {
                'warehouse': str(warehouse.id),
                'product': str(product.id),
                'requested_quantity': requested_quantity,
                'available_quantity': available_quantity,
                'is_available': is_available,
                'message': message,
            },
            status=status.HTTP_200_OK,
        )


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


class EmployeeWorkspaceView(APIView):
    """Provide per-employee workspace data scoped by memberships and assignments."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        business_ids = _business_ids_for_user(user)

        empty_response = Response(
            {
                'businesses': [],
                'warehouses': [],
                'storefronts': [],
                'pending_approvals': [],
                'incoming_transfers': [],
                'my_transfer_requests': [],
            },
            status=status.HTTP_200_OK,
        )

        if not business_ids:
            return empty_response

        memberships = list(
            BusinessMembership.objects.filter(
                business_id__in=business_ids,
                user=user,
                is_active=True,
            ).select_related('business')
        )

        if not memberships:
            return empty_response

        manager_roles = {BusinessMembership.OWNER, BusinessMembership.ADMIN, BusinessMembership.MANAGER}

        warehouse_assignments = defaultdict(set)
        for assignment in WarehouseEmployee.objects.filter(user=user, is_active=True, business_id__in=business_ids):
            warehouse_assignments[assignment.business_id].add(assignment.warehouse_id)

        storefront_assignments = defaultdict(set)
        for assignment in StoreFrontEmployee.objects.filter(user=user, is_active=True, business_id__in=business_ids):
            storefront_assignments[assignment.business_id].add(assignment.storefront_id)

        all_warehouses = list(
            Warehouse.objects.select_related('business_link__business').filter(
                business_link__business_id__in=business_ids
            )
        )
        warehouses_by_business = defaultdict(list)
        for warehouse in all_warehouses:
            link = getattr(warehouse, 'business_link', None)
            if not link:
                continue
            warehouses_by_business[link.business_id].append(warehouse)

        all_storefronts = list(
            StoreFront.objects.select_related('business_link__business').filter(
                business_link__business_id__in=business_ids
            )
        )
        storefronts_by_business = defaultdict(list)
        for storefront in all_storefronts:
            link = getattr(storefront, 'business_link', None)
            if not link:
                continue
            storefronts_by_business[link.business_id].append(storefront)

        contexts: dict[str, dict] = {}
        all_warehouse_ids: set = set()
        all_storefront_ids: set = set()
        non_manager_storefront_ids: set = set()
        manager_business_ids: set = set()
        non_manager_business_ids: set = set()

        for membership in memberships:
            business = membership.business
            business_id = business.id
            is_manager = membership.role in manager_roles

            warehouses = list(warehouses_by_business.get(business_id, []))
            storefronts = list(storefronts_by_business.get(business_id, []))

            if is_manager:
                manager_business_ids.add(business_id)
            else:
                non_manager_business_ids.add(business_id)
                assigned_warehouses = warehouse_assignments.get(business_id, set())
                assigned_storefronts = storefront_assignments.get(business_id, set())
                warehouses = [warehouse for warehouse in warehouses if warehouse.id in assigned_warehouses]
                storefronts = [storefront for storefront in storefronts if storefront.id in assigned_storefronts]
                non_manager_storefront_ids.update(storefront.id for storefront in storefronts)

            warehouse_ids = [warehouse.id for warehouse in warehouses]
            storefront_ids = [storefront.id for storefront in storefronts]

            all_warehouse_ids.update(warehouse_ids)
            all_storefront_ids.update(storefront_ids)

            contexts[business_id] = {
                'membership': membership,
                'warehouses': warehouses,
                'storefronts': storefronts,
                'warehouse_ids': warehouse_ids,
                'storefront_ids': storefront_ids,
                'is_manager': is_manager,
            }

        if not contexts:
            return empty_response

        warehouse_stock_map = {}
        if all_warehouse_ids:
            for row in Inventory.objects.filter(warehouse_id__in=all_warehouse_ids).values('warehouse_id').annotate(total=Sum('quantity')):
                warehouse_stock_map[row['warehouse_id']] = int(row['total'] or 0)

        storefront_stock_map = {}
        if all_storefront_ids:
            for row in StoreFrontInventory.objects.filter(storefront_id__in=all_storefront_ids).values('storefront_id').annotate(total=Sum('quantity')):
                storefront_stock_map[row['storefront_id']] = int(row['total'] or 0)

        storefront_pending_map = {}
        if all_storefront_ids:
            pending_qs = TransferRequest.objects.filter(
                storefront_id__in=all_storefront_ids,
                status__in=[TransferRequest.STATUS_NEW, TransferRequest.STATUS_ASSIGNED],
            )
            for row in pending_qs.values('storefront_id').annotate(total=Count('id')):
                storefront_pending_map[row['storefront_id']] = int(row['total'] or 0)

        def _build_status_counts(queryset):
            counts = defaultdict(dict)
            for row in queryset.values('business_id', 'status').annotate(total=Count('id')):
                counts[row['business_id']][row['status']] = int(row['total'] or 0)
            return counts

        manager_request_counts = {}
        if manager_business_ids:
            manager_request_counts = _build_status_counts(
                TransferRequest.objects.filter(business_id__in=manager_business_ids)
            )

        non_manager_request_counts = {}
        if non_manager_business_ids:
            request_filter = Q(requested_by=user)
            if non_manager_storefront_ids:
                request_filter |= Q(storefront_id__in=non_manager_storefront_ids)
            non_manager_request_counts = _build_status_counts(
                TransferRequest.objects.filter(business_id__in=non_manager_business_ids).filter(request_filter)
            )

        manager_transfer_counts = {}
        if manager_business_ids:
            manager_transfer_counts = _build_status_counts(
                Transfer.objects.filter(business_id__in=manager_business_ids)
            )

        non_manager_transfer_counts = {}
        if non_manager_business_ids and non_manager_storefront_ids:
            non_manager_transfer_counts = _build_status_counts(
                Transfer.objects.filter(
                    business_id__in=non_manager_business_ids,
                    destination_storefront_id__in=non_manager_storefront_ids,
                )
            )

        my_transfer_requests = [
            {
                'id': str(request_obj.id),
                'status': request_obj.status,
                'priority': request_obj.priority,
                'storefront': str(request_obj.storefront_id),
                'storefront_name': request_obj.storefront.name,
                'linked_transfer_reference': request_obj.linked_transfer_reference,
                'created_at': request_obj.created_at.isoformat(),
            }
            for request_obj in TransferRequest.objects.filter(requested_by=user)
            .select_related('storefront')
            .order_by('-created_at')[:10]
        ]

        pending_approvals = []
        if manager_business_ids:
            pending_approvals = [
                {
                    'id': str(transfer.id),
                    'reference': transfer.reference,
                    'status': transfer.status,
                    'destination_storefront': str(transfer.destination_storefront_id),
                    'destination_storefront_name': transfer.destination_storefront.name,
                    'created_at': transfer.created_at.isoformat(),
                }
                for transfer in Transfer.objects.filter(
                    business_id__in=manager_business_ids,
                    status=Transfer.STATUS_REQUESTED,
                )
                .select_related('destination_storefront')
                .order_by('created_at')[:10]
            ]

        incoming_transfers = []
        incoming_storefront_ids = all_storefront_ids
        if incoming_storefront_ids:
            incoming_transfers = [
                {
                    'id': str(transfer.id),
                    'reference': transfer.reference,
                    'status': transfer.status,
                    'destination_storefront': str(transfer.destination_storefront_id),
                    'destination_storefront_name': transfer.destination_storefront.name,
                    'completed_at': transfer.completed_at.isoformat() if transfer.completed_at else None,
                    'received_at': transfer.received_at.isoformat() if transfer.received_at else None,
                }
                for transfer in Transfer.objects.filter(
                    destination_storefront_id__in=incoming_storefront_ids,
                    status__in=[Transfer.STATUS_IN_TRANSIT, Transfer.STATUS_COMPLETED],
                )
                .select_related('destination_storefront')
                .order_by('-created_at')[:10]
            ]

        businesses_payload = []
        warehouses_payload = []
        storefronts_payload = []
        seen_warehouse_ids = set()
        seen_storefront_ids = set()

        request_status_template = {status: 0 for status, _ in TransferRequest.STATUS_CHOICES}
        transfer_status_template = {
            Transfer.STATUS_DRAFT: 0,
            Transfer.STATUS_REQUESTED: 0,
            Transfer.STATUS_APPROVED: 0,
            Transfer.STATUS_IN_TRANSIT: 0,
            Transfer.STATUS_COMPLETED: 0,
            Transfer.STATUS_REJECTED: 0,
            Transfer.STATUS_CANCELLED: 0,
        }

        for business_id, context in contexts.items():
            membership = context['membership']
            business = membership.business
            is_manager = context['is_manager']

            request_counts = request_status_template.copy()
            source_counts = manager_request_counts if is_manager else non_manager_request_counts
            for status_key, total in source_counts.get(business_id, {}).items():
                request_counts[status_key] = total

            transfer_counts = transfer_status_template.copy()
            transfer_source_counts = manager_transfer_counts if is_manager else non_manager_transfer_counts
            for status_key, total in transfer_source_counts.get(business_id, {}).items():
                if status_key in transfer_counts:
                    transfer_counts[status_key] = total

            warehouse_stock_total = sum(warehouse_stock_map.get(warehouse_id, 0) for warehouse_id in context['warehouse_ids'])
            storefront_stock_total = sum(storefront_stock_map.get(storefront_id, 0) for storefront_id in context['storefront_ids'])

            businesses_payload.append(
                {
                    'id': str(business.id),
                    'name': business.name,
                    'role': membership.role,
                    'storefront_count': len(context['storefronts']),
                    'warehouse_count': len(context['warehouses']),
                    'transfer_requests': {
                        'by_status': request_counts,
                    },
                    'transfers': {
                        'by_status': transfer_counts,
                    },
                    'stock': {
                        'warehouse_on_hand': warehouse_stock_total,
                        'storefront_on_hand': storefront_stock_total,
                    },
                }
            )

            scope_label = 'manager' if is_manager else 'assigned'

            for warehouse in context['warehouses']:
                if warehouse.id in seen_warehouse_ids:
                    continue
                link = getattr(warehouse, 'business_link', None)
                business_name = link.business.name if link and link.business else None
                warehouses_payload.append(
                    {
                        'id': str(warehouse.id),
                        'name': warehouse.name,
                        'business': str(link.business_id) if link else None,
                        'business_name': business_name,
                        'scope': scope_label,
                        'stock_on_hand': warehouse_stock_map.get(warehouse.id, 0),
                    }
                )
                seen_warehouse_ids.add(warehouse.id)

            for storefront in context['storefronts']:
                if storefront.id in seen_storefront_ids:
                    continue
                link = getattr(storefront, 'business_link', None)
                business_name = link.business.name if link and link.business else None
                storefronts_payload.append(
                    {
                        'id': str(storefront.id),
                        'name': storefront.name,
                        'business': str(link.business_id) if link else None,
                        'business_name': business_name,
                        'scope': scope_label,
                        'inventory_on_hand': storefront_stock_map.get(storefront.id, 0),
                        'pending_requests': storefront_pending_map.get(storefront.id, 0),
                    }
                )
                seen_storefront_ids.add(storefront.id)

        return Response(
            {
                'businesses': businesses_payload,
                'warehouses': warehouses_payload,
                'storefronts': storefronts_payload,
                'pending_approvals': pending_approvals,
                'incoming_transfers': incoming_transfers,
                'my_transfer_requests': my_transfer_requests,
            },
            status=status.HTTP_200_OK,
        )


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
