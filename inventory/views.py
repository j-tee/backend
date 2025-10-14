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
from django.db.models.functions import Coalesce
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
    StoreFrontInventory, TransferRequest, StockAlert,
    BusinessWarehouse, BusinessStoreFront, StoreFrontEmployee, WarehouseEmployee
)
from .serializers import (
    CategorySerializer, WarehouseSerializer, StoreFrontSerializer, 
    StockSerializer, StockProductSerializer, SupplierSerializer, ProductSerializer,
    StorefrontSaleProductSerializer,
    TransferRequestSerializer, StockAlertSerializer,
    InventorySummarySerializer, StockArrivalReportSerializer,
    BusinessWarehouseSerializer, BusinessStoreFrontSerializer,
    StoreFrontEmployeeSerializer, WarehouseEmployeeSerializer,
    ProfitProjectionSerializer, ProfitScenarioSerializer,
    StockProductProfitProjectionSerializer, ProductProfitProjectionSerializer,
    BulkProfitProjectionSerializer, BulkProfitProjectionResponseSerializer
)

# Import sales models for availability calculation
try:
    from sales.models import StockReservation, Sale, SaleItem
    SALES_APP_AVAILABLE = True
except ImportError:
    StockReservation = None
    Sale = None
    SaleItem = None
    SALES_APP_AVAILABLE = False

from .stock_adjustments import StockAdjustment


User = get_user_model()


class CustomPageNumberPagination(PageNumberPagination):
    """Custom pagination class that allows configurable page size."""
    page_size = 25  # Default page size
    page_size_query_param = 'page_size'
    max_page_size = 100  # Maximum allowed page size


class CatalogPagination(PageNumberPagination):
    """Pagination class for sale catalog endpoints."""
    page_size = 50  # Default page size for catalog
    page_size_query_param = 'page_size'
    max_page_size = 200  # Maximum allowed page size for catalog
    
    def get_paginated_response(self, data):
        """Return paginated response with additional metadata."""
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'page_size': self.page_size,
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            **data
        })


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
    warehouse = UUIDFilter(field_name='warehouse_id')  # Direct warehouse field on StockProduct
    supplier = UUIDFilter(field_name='supplier_id')
    has_quantity = BooleanFilter(method='filter_has_quantity', label='Has quantity greater than 0')
    search = CharFilter(method='filter_search', label='Search in product name/SKU')

    class Meta:
        model = StockProduct
        fields = ['product', 'stock', 'warehouse', 'supplier', 'has_quantity', 'search']

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
    search = CharFilter(method='filter_search', label='Search in description or reference')

    class Meta:
        model = Stock
        fields = ['search']  # Stock doesn't have warehouse directly anymore

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
    """
    Get the primary business for a user. 
    Checks both account_type=OWNER and BusinessMembership OWNER role.
    """
    # First check if user has account_type OWNER and owned_businesses
    if getattr(user, 'account_type', None) == getattr(User, 'ACCOUNT_OWNER', 'OWNER'):
        business = user.owned_businesses.first()
        if business:
            return business
    
    # Also check BusinessMembership for OWNER role
    owner_membership = BusinessMembership.objects.filter(
        user=user,
        role=BusinessMembership.OWNER,
        is_active=True
    ).select_related('business').first()
    
    return owner_membership.business if owner_membership else None


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

    @action(detail=True, methods=['get'], url_path='sale-catalog')
    def sale_catalog(self, request, pk=None):
        """
        Enhanced sale catalog with server-side filtering and pagination.
        
        Query Parameters:
        - search: Search by product name, SKU, or barcode (case-insensitive)
        - category: Filter by category ID (UUID)
        - min_price: Minimum retail price (inclusive)
        - max_price: Maximum retail price (inclusive)
        - in_stock_only: Show only products with available_quantity > 0 (default: true)
        - page: Page number for pagination (default: 1)
        - page_size: Items per page (default: 50, max: 200)
        - include_zero: Legacy parameter, opposite of in_stock_only
        """
        storefront = self.get_object()

        # Get query parameters with backward compatibility
        search_query = request.query_params.get('search', '').strip()
        category_id = request.query_params.get('category')
        min_price = request.query_params.get('min_price')
        max_price = request.query_params.get('max_price')
        
        # Handle in_stock_only with backward compatibility for include_zero
        include_zero = request.query_params.get('include_zero', '').lower() == 'true'
        in_stock_only_param = request.query_params.get('in_stock_only', '').lower()
        
        if in_stock_only_param == 'false':
            in_stock_only = False
        elif include_zero:
            in_stock_only = False
        else:
            in_stock_only = True  # Default to in-stock only

        # Build the base queryset with inventory aggregation
        inventory_qs = StoreFrontInventory.objects.filter(
            storefront=storefront
        ).select_related('product', 'product__category')
        
        # Filter: In stock only
        if in_stock_only:
            inventory_qs = inventory_qs.filter(quantity__gt=0)
        
        # Get inventory totals
        inventory_totals = {
            row['product_id']: row['total_quantity']
            for row in inventory_qs.values('product_id').annotate(total_quantity=Sum('quantity'))
        }
        
        if not inventory_totals:
            paginator = CatalogPagination()
            return paginator.get_paginated_response({'products': []})

        # Get stock products for the filtered inventory
        stock_products_qs = (
            StockProduct.objects.filter(product_id__in=inventory_totals.keys())
            .select_related('product', 'product__category')
        )
        
        # Apply filters on the product level
        if search_query:
            stock_products_qs = stock_products_qs.filter(
                Q(product__name__icontains=search_query) |
                Q(product__sku__icontains=search_query) |
                Q(product__barcode__icontains=search_query)
            )
        
        if category_id:
            try:
                category_uuid = UUID(category_id)
                stock_products_qs = stock_products_qs.filter(product__category_id=category_uuid)
            except (TypeError, ValueError):
                # Invalid UUID, ignore filter
                pass
        
        # Note: Price filters will be applied after aggregation since prices are on StockProduct
        stock_products_qs = stock_products_qs.order_by('product_id', '-created_at')
        
        # Build stock map with latest pricing
        stock_map: dict = {}
        for stock_product in stock_products_qs:
            product_id = stock_product.product_id
            entry = stock_map.setdefault(
                product_id,
                {
                    'product': stock_product.product,
                    'latest': None,
                    'stock_product_ids': [],
                }
            )

            entry['stock_product_ids'].append(stock_product.id)

            if entry['latest'] is None:
                entry['latest'] = stock_product

        # Build catalog items
        catalog_items = []
        for product_id, quantity in inventory_totals.items():
            if product_id not in stock_map:
                continue
            
            entry = stock_map[product_id]
            latest = entry['latest']
            product = entry['product']

            retail_price = latest.retail_price if latest and latest.retail_price is not None else Decimal('0.00')
            wholesale_price = latest.wholesale_price if latest and latest.wholesale_price is not None else None
            if wholesale_price is not None and wholesale_price <= Decimal('0.00'):
                wholesale_price = None
            
            # Apply price range filters
            if min_price:
                try:
                    min_price_decimal = Decimal(str(min_price))
                    if retail_price < min_price_decimal:
                        continue
                except (ValueError, TypeError, ArithmeticError):
                    pass
            
            if max_price:
                try:
                    max_price_decimal = Decimal(str(max_price))
                    if retail_price > max_price_decimal:
                        continue
                except (ValueError, TypeError, ArithmeticError):
                    pass

            catalog_items.append({
                'product_id': product.id,
                'product_name': product.name,
                'sku': product.sku or '',
                'barcode': product.barcode,
                'category_name': product.category.name if product.category else None,
                'unit': product.unit if hasattr(product, 'unit') else None,
                'product_image': product.image.url if hasattr(product, 'image') and product.image else None,
                'available_quantity': int(quantity),
                'retail_price': retail_price,
                'wholesale_price': wholesale_price,
                'stock_product_ids': entry['stock_product_ids'],
                'last_stocked_at': latest.created_at if latest else None,
            })

        # Sort by product name for consistent ordering
        catalog_items.sort(key=lambda item: item['product_name'].lower())

        # Apply pagination
        paginator = CatalogPagination()
        page = paginator.paginate_queryset(catalog_items, request)
        
        # Serialize paginated results
        serializer = StorefrontSaleProductSerializer(page, many=True)
        
        return paginator.get_paginated_response({'products': serializer.data})

    @action(detail=False, methods=['get'], url_path='multi-storefront-catalog')
    def multi_storefront_catalog(self, request):
        """
        Enhanced multi-storefront catalog with server-side filtering and pagination.
        
        For business owners: returns products from ALL storefronts in their business
        For employees: returns products from storefronts they're assigned to
        
        Query Parameters:
        - search: Search by product name, SKU, or barcode (case-insensitive)
        - category: Filter by category ID (UUID)
        - storefront: Filter to specific storefront(s) - can be repeated
        - min_price: Minimum retail price (inclusive)
        - max_price: Maximum retail price (inclusive)
        - in_stock_only: Show only products with total_available > 0 (default: true)
        - page: Page number for pagination (default: 1)
        - page_size: Items per page (default: 50, max: 200)
        - include_zero: Legacy parameter, opposite of in_stock_only
        """
        user = request.user
        
        # Get query parameters
        search_query = request.query_params.get('search', '').strip()
        category_id = request.query_params.get('category')
        storefront_filter = request.query_params.getlist('storefront')
        min_price = request.query_params.get('min_price')
        max_price = request.query_params.get('max_price')
        
        # Handle in_stock_only with backward compatibility for include_zero
        include_zero = request.query_params.get('include_zero', '').lower() == 'true'
        in_stock_only_param = request.query_params.get('in_stock_only', '').lower()
        
        if in_stock_only_param == 'false':
            in_stock_only = False
        elif include_zero:
            in_stock_only = False
        else:
            in_stock_only = True  # Default to in-stock only
        
        # Get accessible storefronts
        accessible_storefronts = []
        
        # Check if user is business owner/manager
        business_ids = _business_ids_for_user(user)
        if business_ids:
            # Business owner/manager - get all storefronts in their businesses
            accessible_storefronts = list(StoreFront.objects.filter(
                business_link__business_id__in=business_ids
            ).select_related('business_link__business'))
        else:
            # Regular employee - get assigned storefronts only
            from inventory.models import StoreFrontEmployee
            assigned_storefronts = StoreFrontEmployee.objects.filter(
                user=user,
                is_active=True
            ).select_related('storefront', 'storefront__business_link__business')
            accessible_storefronts = [emp.storefront for emp in assigned_storefronts]
        
        # Apply storefront filter if specified
        if storefront_filter:
            try:
                storefront_uuids = [UUID(sf_id) for sf_id in storefront_filter]
                accessible_storefronts = [
                    sf for sf in accessible_storefronts 
                    if sf.id in storefront_uuids
                ]
            except (TypeError, ValueError):
                # Invalid UUIDs, ignore filter
                pass
        
        if not accessible_storefronts:
            paginator = CatalogPagination()
            return paginator.get_paginated_response({
                'storefronts': [],
                'products': []
            })
        
        # Get all inventory items across storefronts
        inventory_qs = StoreFrontInventory.objects.filter(
            storefront__in=accessible_storefronts
        ).select_related('product', 'product__category', 'storefront')
        
        # Apply in-stock filter
        if in_stock_only:
            inventory_qs = inventory_qs.filter(quantity__gt=0)
        
        # Get stock products for pricing and additional filtering
        product_ids = set(inventory_qs.values_list('product_id', flat=True))
        
        if not product_ids:
            paginator = CatalogPagination()
            storefront_summary = [
                {
                    'id': str(sf.id),
                    'name': sf.name,
                }
                for sf in accessible_storefronts
            ]
            return paginator.get_paginated_response({
                'storefronts': storefront_summary,
                'products': []
            })
        
        stock_products_qs = (
            StockProduct.objects.filter(product_id__in=product_ids)
            .select_related('product', 'product__category')
        )
        
        # Apply search filter
        if search_query:
            stock_products_qs = stock_products_qs.filter(
                Q(product__name__icontains=search_query) |
                Q(product__sku__icontains=search_query) |
                Q(product__barcode__icontains=search_query)
            )
        
        # Apply category filter
        if category_id:
            try:
                category_uuid = UUID(category_id)
                stock_products_qs = stock_products_qs.filter(product__category_id=category_uuid)
            except (TypeError, ValueError):
                pass
        
        stock_products_qs = stock_products_qs.order_by('product_id', '-created_at')
        
        # Build stock map with latest pricing
        stock_map = {}
        for stock_product in stock_products_qs:
            product_id = stock_product.product_id
            if product_id not in stock_map:
                stock_map[product_id] = {
                    'product': stock_product.product,
                    'latest': stock_product,
                    'stock_product_ids': []
                }
            stock_map[product_id]['stock_product_ids'].append(stock_product.id)
        
        # Filter inventory to only include products that passed filters
        filtered_product_ids = set(stock_map.keys())
        inventory_items = inventory_qs.filter(product_id__in=filtered_product_ids)
        
        # Aggregate by product
        product_map = defaultdict(lambda: {
            'locations': [],
            'stock_product_ids': [],
            'total_available': 0,
        })
        
        for inv in inventory_items:
            product_id = inv.product_id
            product_key = str(product_id)
            
            if product_id not in stock_map:
                continue
            
            entry = stock_map[product_id]
            latest = entry['latest']
            product = entry['product']
            
            # Initialize product data if not already set
            if 'product_name' not in product_map[product_key]:
                retail_price = latest.retail_price if latest and latest.retail_price is not None else Decimal('0.00')
                wholesale_price = latest.wholesale_price if latest and latest.wholesale_price is not None else None
                if wholesale_price is not None and wholesale_price <= Decimal('0.00'):
                    wholesale_price = None
                
                # Apply price range filters
                skip_product = False
                if min_price:
                    try:
                        min_price_decimal = Decimal(str(min_price))
                        if retail_price < min_price_decimal:
                            skip_product = True
                    except (ValueError, TypeError, ArithmeticError):
                        pass
                
                if max_price:
                    try:
                        max_price_decimal = Decimal(str(max_price))
                        if retail_price > max_price_decimal:
                            skip_product = True
                    except (ValueError, TypeError, ArithmeticError):
                        pass
                
                if skip_product:
                    # Remove from product_map to skip this product
                    del product_map[product_key]
                    continue
                
                product_map[product_key].update({
                    'product_id': str(product.id),
                    'product_name': product.name,
                    'sku': product.sku or '',
                    'barcode': product.barcode,
                    'category_name': product.category.name if product.category else None,
                    'unit': product.unit if hasattr(product, 'unit') else None,
                    'product_image': product.image.url if hasattr(product, 'image') and product.image else None,
                    'retail_price': retail_price,
                    'wholesale_price': wholesale_price,
                    'last_stocked_at': latest.created_at.isoformat() if latest and latest.created_at else None,
                })
            
            # Add location data
            product_map[product_key]['total_available'] += inv.quantity
            product_map[product_key]['locations'].append({
                'storefront_id': str(inv.storefront.id),
                'storefront_name': inv.storefront.name,
                'available_quantity': int(inv.quantity),
            })
            
            # Add stock product IDs (unique)
            if entry['stock_product_ids']:
                existing_ids = set(product_map[product_key]['stock_product_ids'])
                for sp_id in entry['stock_product_ids']:
                    if sp_id not in existing_ids:
                        product_map[product_key]['stock_product_ids'].append(sp_id)
                        existing_ids.add(sp_id)
        
        # Convert to list and sort by product name
        products_list = list(product_map.values())
        products_list.sort(key=lambda x: x.get('product_name', '').lower())
        
        # Apply pagination
        paginator = CatalogPagination()
        page = paginator.paginate_queryset(products_list, request)
        
        # Prepare storefront summary
        storefront_summary = [
            {
                'id': str(sf.id),
                'name': sf.name,
            }
            for sf in accessible_storefronts
        ]
        
        return paginator.get_paginated_response({
            'storefronts': storefront_summary,
            'products': page
        })


class ProductViewSet(viewsets.ModelViewSet):
    """ViewSet for managing products with pagination, filtering, and ordering."""
    queryset = Product.objects.select_related('category', 'business').all()
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CustomPageNumberPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'sku']  # General text search (name/SKU only)
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

    @action(detail=False, methods=['get'], url_path='by-barcode/(?P<barcode>[^/.]+)')
    def by_barcode(self, request, barcode=None):
        """
        Get product by BARCODE with available stock information
        Optimized for POS barcode scanning
        Only searches barcode field - separate from SKU
        """
        business_ids = _business_ids_for_user(request.user)
        
        # Find product by barcode (not SKU)
        product = Product.objects.filter(
            barcode=barcode,
            business_id__in=business_ids,
            is_active=True
        ).select_related('category', 'business').first()
        
        if not product:
            return Response(
                {'detail': f'Product with barcode {barcode} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get available stock for this product
        stock_products = StockProduct.objects.filter(
            product=product,
            quantity__gt=0
        ).select_related('stock', 'supplier').order_by('-created_at')
        
        # Serialize data
        product_data = ProductSerializer(product).data
        stock_data = StockProductSerializer(stock_products, many=True).data
        
        return Response({
            'product': product_data,
            'stock_products': stock_data,
            'has_stock': stock_products.exists(),
            'total_quantity': sum(sp.quantity for sp in stock_products)
        })

    @action(detail=True, methods=['get'], url_path='stock-reconciliation')
    def stock_reconciliation(self, request, pk=None):
        """Return aggregated stock metrics for banner reconciliation."""

        product = self.get_object()

        def to_decimal(value):
            if value is None:
                return Decimal('0')
            if isinstance(value, Decimal):
                return value
            return Decimal(str(value))

        def to_number(value):
            if isinstance(value, Decimal):
                if value == value.to_integral_value():
                    return int(value)
                return float(value)
            if value is None:
                return 0
            return value

        stock_products_qs = StockProduct.objects.filter(product=product).select_related('warehouse', 'stock')
        stock_products = list(stock_products_qs)
        warehouse_aggregate = stock_products_qs.aggregate(
            current_quantity=Coalesce(Sum('quantity'), 0)
        )

        storefront_qs = StoreFrontInventory.objects.filter(product=product).select_related('storefront')
        storefront_entries = list(storefront_qs)
        storefront_total = storefront_qs.aggregate(total=Coalesce(Sum('quantity'), 0))['total'] or 0

        # Build storefront breakdown with sellable and reserved
        storefront_breakdown = []
        for entry in storefront_entries:
            on_hand = to_decimal(entry.quantity)
            
            # Calculate reservations for this storefront
            reserved_qty = Decimal('0')
            if SALES_APP_AVAILABLE and StockReservation is not None and Sale is not None:
                # Get active reservations linked to sales at this storefront
                storefront_reservations = StockReservation.objects.filter(
                    stock_product__product=product,
                    status='ACTIVE'
                ).select_related('stock_product')
                
                for res in storefront_reservations:
                    try:
                        sale_uuid = UUID(str(res.cart_session_id))
                        sale = Sale.objects.filter(
                            id=sale_uuid,
                            storefront=entry.storefront,
                            status__in=['DRAFT', 'PENDING', 'PARTIAL']
                        ).first()
                        if sale:
                            reserved_qty += to_decimal(res.quantity)
                    except (ValueError, TypeError):
                        pass
            
            sellable_qty = on_hand - reserved_qty
            if sellable_qty < Decimal('0'):
                sellable_qty = Decimal('0')
            
            storefront_breakdown.append({
                'storefront_id': str(entry.storefront_id),
                'storefront_name': entry.storefront.name,
                'on_hand': to_number(on_hand),
                'sellable': to_number(sellable_qty),
                'reserved': to_number(reserved_qty),
            })

        completed_units = Decimal('0')
        completed_value = Decimal('0')
        completed_sales = set()
        if SALES_APP_AVAILABLE and SaleItem is not None:
            completed_items = SaleItem.objects.filter(
                product=product,
                sale__status=Sale.STATUS_COMPLETED
            ).select_related('sale', 'sale__storefront')
            for item in completed_items:
                completed_units += to_decimal(item.quantity)
                completed_value += to_decimal(item.total_price)
                completed_sales.add(str(item.sale_id))

        adjustments_qs = StockAdjustment.objects.filter(
            stock_product__product=product,
            status='COMPLETED'
        )
        negative_adjustments = adjustments_qs.filter(quantity__lt=0).aggregate(total=Coalesce(Sum('quantity'), 0))['total'] or 0
        positive_adjustments = adjustments_qs.filter(quantity__gt=0).aggregate(total=Coalesce(Sum('quantity'), 0))['total'] or 0
        shrinkage_units = abs(Decimal(str(negative_adjustments))) if negative_adjustments else Decimal('0')
        correction_units = Decimal(str(positive_adjustments)) if positive_adjustments else Decimal('0')

        reservation_details = []
        reservations_linked_units = Decimal('0')
        reservations_orphaned_units = Decimal('0')
        linked_count = 0
        orphaned_count = 0
        ACTIVE_SALE_STATUSES = {'DRAFT', 'PENDING', 'PARTIAL', 'COMPLETED'}
        if SALES_APP_AVAILABLE and StockReservation is not None:
            reservation_qs = StockReservation.objects.filter(
                stock_product__product=product,
                status='ACTIVE'
            ).select_related('stock_product__warehouse', 'stock_product__stock')
            reservations = list(reservation_qs)
            sale_lookup = {}
            sale_ids = []
            for reservation in reservations:
                sale_uuid = None
                if reservation.cart_session_id:
                    try:
                        sale_uuid = UUID(str(reservation.cart_session_id))
                    except (ValueError, TypeError):
                        sale_uuid = None
                if sale_uuid:
                    sale_ids.append(str(sale_uuid))
                reservation_details.append({
                    'id': str(reservation.id),
                    'quantity': to_number(reservation.quantity),
                    'cart_session_id': reservation.cart_session_id,
                    'linked_sale_id': str(sale_uuid) if sale_uuid else None,
                    'expires_at': reservation.expires_at,
                })

            if sale_ids:
                sale_lookup = {
                    str(sale.id): sale
                    for sale in Sale.objects.filter(id__in=sale_ids).only('id', 'status')
                }

            for detail, reservation in zip(reservation_details, reservations):
                quantity_decimal = to_decimal(reservation.quantity)
                linked_sale_id = detail['linked_sale_id']
                sale = sale_lookup.get(linked_sale_id) if linked_sale_id else None
                if sale and sale.status in ACTIVE_SALE_STATUSES:
                    reservations_linked_units += quantity_decimal
                    linked_count += 1
                else:
                    reservations_orphaned_units += quantity_decimal
                    orphaned_count += 1
        else:
            reservations = []

        storefront_total_decimal = to_decimal(storefront_total)
        recorded_quantity_decimal = to_decimal(warehouse_aggregate.get('current_quantity', 0))
        
        # Warehouse on hand = Recorded batch - Storefront on hand
        warehouse_on_hand = recorded_quantity_decimal - storefront_total_decimal
        
        # Calculate sellable storefront inventory (storefront - sold)
        storefront_sellable = storefront_total_decimal - completed_units

        # Reconciliation formula CORRECTED:
        # The recorded batch should equal: warehouse + storefront_transferred (not sellable)
        # Because sold units were part of the storefront_transferred, we don't add them separately
        # Formula: recorded_batch = warehouse_on_hand + storefront_on_hand (transferred)
        formula_baseline = (
            warehouse_on_hand
            + storefront_total_decimal  # Transferred quantity (fixed, doesn't change)
            - shrinkage_units
            + correction_units
            - reservations_linked_units
        )

        computed_initial_decimal = formula_baseline

        response = {
            'product': {
                'id': str(product.id),
                'name': product.name,
                'sku': product.sku,
            },
            'warehouse': {
                'recorded_quantity': to_number(recorded_quantity_decimal),
                'inventory_on_hand': to_number(warehouse_on_hand),
                'batches': [
                    {
                        'stock_product_id': str(sp.id),
                        'warehouse_id': str(sp.warehouse_id) if sp.warehouse_id else None,
                        'warehouse_name': sp.warehouse.name if sp.warehouse else None,
                        'quantity': sp.quantity,
                        'arrival_date': sp.stock.arrival_date if sp.stock else None,
                    }
                    for sp in stock_products
                ],
            },
            'storefront': {
                'total_on_hand': to_number(storefront_total_decimal),
                'sellable_now': to_number(storefront_sellable),  # NEW: Available for sale
                'breakdown': storefront_breakdown,
            },
            'sales': {
                'completed_units': to_number(completed_units),
                'completed_value': to_number(completed_value),
                'completed_sale_ids': sorted(completed_sales),
            },
            'adjustments': {
                'shrinkage_units': to_number(shrinkage_units),
                'correction_units': to_number(correction_units),
            },
            'reservations': {
                'linked_units': to_number(reservations_linked_units),
                'orphaned_units': to_number(reservations_orphaned_units),
                'linked_count': linked_count,
                'orphaned_count': orphaned_count,
                'details': reservation_details,
            },
            'formula': {
                'warehouse_inventory_on_hand': to_number(warehouse_on_hand),
                'storefront_on_hand': to_number(storefront_total_decimal),
                'storefront_sellable': to_number(storefront_sellable),
                'completed_sales_units': to_number(completed_units),
                'shrinkage_units': to_number(shrinkage_units),
                'correction_units': to_number(correction_units),
                'active_reservations_units': to_number(reservations_linked_units),
                'calculated_baseline': to_number(formula_baseline),
                'recorded_batch_quantity': to_number(recorded_quantity_decimal),
                'initial_batch_quantity': to_number(computed_initial_decimal),
                'baseline_vs_recorded_delta': to_number(recorded_quantity_decimal - formula_baseline),
                'formula_explanation': 'warehouse_on_hand + storefront_transferred - shrinkage + corrections - reservations',
            },
        }

        return Response(response, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='by-sku/(?P<sku>[^/.]+)')
    def by_sku(self, request, sku=None):
        """
        Get product by SKU with available stock information
        Only searches SKU field - separate from barcode
        """
        business_ids = _business_ids_for_user(request.user)
        
        # Find product by SKU (not barcode)
        product = Product.objects.filter(
            sku=sku,
            business_id__in=business_ids,
            is_active=True
        ).select_related('category', 'business').first()
        
        if not product:
            return Response(
                {'detail': f'Product with SKU {sku} not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get available stock for this product
        stock_products = StockProduct.objects.filter(
            product=product,
            quantity__gt=0
        ).select_related('stock', 'supplier').order_by('-created_at')
        
        # Serialize data
        product_data = ProductSerializer(product).data
        stock_data = StockProductSerializer(stock_products, many=True).data
        
        return Response({
            'product': product_data,
            'stock_products': stock_data,
            'has_stock': stock_products.exists(),
            'total_quantity': sum(sp.quantity for sp in stock_products)
        })

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
    queryset = Stock.objects.all()
    serializer_class = StockSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CustomPageNumberPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = StockFilter
    search_fields = ['description']
    ordering_fields = ['arrival_date', 'created_at', 'updated_at']
    ordering = ['-arrival_date']  # Default ordering by newest arrivals first

    def get_queryset(self):
        queryset = Stock.objects.all()
        user = self.request.user
        if user.is_superuser:
            return queryset.prefetch_related('items__product', 'items__warehouse')

        business_ids = _business_ids_for_user(user)
        if not business_ids:
            return queryset.none()
        # Filter by warehouse through stock items (StockProduct)
        return queryset.filter(items__warehouse__business_link__business_id__in=business_ids).distinct().prefetch_related('items__product', 'items__warehouse')

    def perform_create(self, serializer):
        user = self.request.user
        business = _get_primary_business_for_owner(user)
        if business is None:
            raise PermissionDenied('Only business owners with an active business can create stock receipts.')

        # Stock model no longer has warehouse field
        # Warehouse is now on StockProduct items
        serializer.save()

    def perform_update(self, serializer):
        if self.request.user.is_superuser:
            serializer.save()
            return

        instance = self.get_object()
        # Check permission through stock items' warehouses
        user_business_ids = _business_ids_for_user(self.request.user)
        stock_warehouses = instance.items.values_list('warehouse__business_link__business_id', flat=True).distinct()
        if not any(biz_id in user_business_ids for biz_id in stock_warehouses if biz_id):
            raise PermissionDenied('You do not have permission to update this stock receipt.')
        serializer.save()


class StockProductViewSet(viewsets.ModelViewSet):
    """Manage individual stock line items with pagination, filtering, and ordering."""

    queryset = StockProduct.objects.select_related('product', 'supplier', 'warehouse', 'stock').all()
    serializer_class = StockProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CustomPageNumberPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = StockProductFilter
    search_fields = ['product__name', 'product__sku', 'description']
    ordering_fields = ['quantity', 'unit_cost', 'landed_unit_cost', 'expiry_date', 'created_at', 'updated_at']
    ordering = ['-created_at']  # Default ordering by newest first

    def get_queryset(self):
        queryset = StockProduct.objects.select_related('product', 'supplier', 'warehouse', 'stock')
        user = self.request.user
        if user.is_superuser:
            return queryset

        business_ids = _business_ids_for_user(user)
        if not business_ids:
            return queryset.none()
        
        # Filter by warehouse business_link since warehouse is directly on StockProduct now
        return queryset.filter(warehouse__business_link__business_id__in=business_ids)

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
        
        # Check if warehouse belongs to user's business
        if instance.warehouse and instance.warehouse.business_link and instance.warehouse.business_link.business_id not in business_ids:
            raise PermissionDenied('You do not have permission to update this stock item.')
        serializer.save()

    @action(detail=False, methods=['get'], url_path='search')
    def search(self, request):
        """
        Server-side search for stock products by name, SKU, warehouse, or batch.
        
        Query params:
        - q or search: search query string
        - limit: max results (default 50, max 100)
        - warehouse: filter by warehouse ID
        - has_quantity: filter by quantity > 0
        - ordering: sort field (default: product__name)
        """
        # Get search query
        query = request.query_params.get('q') or request.query_params.get('search', '')
        
        # Get limit (default 50, max 100)
        try:
            limit = int(request.query_params.get('limit', 50))
            limit = min(limit, 100)  # Cap at 100
        except (TypeError, ValueError):
            limit = 50
        
        # Get warehouse filter
        warehouse_id = request.query_params.get('warehouse')
        
        # Get has_quantity filter
        has_quantity = request.query_params.get('has_quantity', '').lower() == 'true'
        
        # Get ordering (default: product__name)
        ordering = request.query_params.get('ordering', 'product__name')
        
        # Start with base queryset (already business-scoped from get_queryset)
        queryset = self.get_queryset()
        
        # Apply search filter if query provided
        if query:
            queryset = queryset.filter(
                Q(product__name__icontains=query) |
                Q(product__sku__icontains=query) |
                Q(warehouse__name__icontains=query) |
                Q(stock__batch_number__icontains=query)
            )
        
        # Apply warehouse filter
        if warehouse_id:
            try:
                warehouse_uuid = UUID(warehouse_id)
                queryset = queryset.filter(warehouse_id=warehouse_uuid)
            except (TypeError, ValueError):
                pass  # Ignore invalid UUID
        
        # Apply quantity filter
        if has_quantity:
            queryset = queryset.filter(quantity__gt=0)
        
        # Apply ordering
        try:
            queryset = queryset.order_by(ordering)
        except Exception:
            queryset = queryset.order_by('product__name')  # Fallback to default
        
        # Limit results
        queryset = queryset[:limit]
        
        # Serialize and return
        serializer = self.get_serializer(queryset, many=True)
        
        return Response({
            'results': serializer.data,
            'count': len(serializer.data)
        }, status=status.HTTP_200_OK)


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
        
        # Staff can only edit their own NEW requests
        if user == instance.requested_by and instance.status == TransferRequest.STATUS_NEW:
            self._ensure_membership(instance.business)
        else:
            # Managers can edit any request, including FULFILLED ones
            self._ensure_membership(instance.business, allowed_roles=self._manager_roles())
        
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        raise ValidationError('Transfer requests cannot be deleted. Use the cancel action instead.')

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        transfer_request = self.get_object()
        if transfer_request.status != TransferRequest.STATUS_NEW:
            raise ValidationError({'status': 'Only new requests can be cancelled.'})

        if request.user == transfer_request.requested_by:
            self._ensure_membership(transfer_request.business)
        else:
            self._ensure_membership(transfer_request.business, allowed_roles=self._manager_roles())

        transfer_request.mark_cancelled(request.user)
        transfer_request.refresh_from_db()
        return Response(self.get_serializer(transfer_request).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def fulfill(self, request, pk=None):
        transfer_request = self.get_object()
        if transfer_request.status == TransferRequest.STATUS_CANCELLED:
            raise ValidationError({'status': 'Cancelled requests cannot be fulfilled.'})

        if transfer_request.status == TransferRequest.STATUS_FULFILLED:
            return Response(self.get_serializer(transfer_request).data, status=status.HTTP_200_OK)

        if request.user == transfer_request.requested_by:
            self._ensure_membership(transfer_request.business)
        else:
            self._ensure_membership(transfer_request.business, allowed_roles=self._manager_roles())

        adjustments = transfer_request.apply_manual_inventory_fulfillment()
        transfer_request.status = TransferRequest.STATUS_FULFILLED
        transfer_request.fulfilled_at = timezone.now()
        transfer_request.fulfilled_by = request.user
        transfer_request.save(update_fields=['status', 'fulfilled_at', 'fulfilled_by', 'updated_at'])
        transfer_request.refresh_from_db()
        payload = self.get_serializer(transfer_request).data
        payload['_inventory_adjustments'] = adjustments
        return Response(payload, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='update-status')
    def update_status(self, request, pk=None):
        """Allow managers to manually update stock request status when needed."""
        transfer_request = self.get_object()
        self._ensure_membership(transfer_request.business, allowed_roles=self._manager_roles())
        
        new_status = request.data.get('status')
        if not new_status:
            raise ValidationError({'status': 'This field is required.'})
        
        valid_statuses = {
            TransferRequest.STATUS_NEW,
            TransferRequest.STATUS_FULFILLED,
            TransferRequest.STATUS_CANCELLED,
        }
        
        if new_status not in valid_statuses:
            raise ValidationError({
                'status': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
            })
        
        # Prevent moving from terminal states unless explicitly clearing them
        if transfer_request.status == TransferRequest.STATUS_FULFILLED and new_status != TransferRequest.STATUS_FULFILLED:
            if not request.data.get('force', False):
                raise ValidationError({
                    'status': 'Cannot change status from FULFILLED. Use force=true to override.'
                })
        
        old_status = transfer_request.status
        inventory_adjustments = None
        
        # Handle status-specific logic
        if new_status == TransferRequest.STATUS_CANCELLED:
            transfer_request.mark_cancelled(request.user)
        elif new_status == TransferRequest.STATUS_FULFILLED:
            # Allow manual fulfillment override
            if transfer_request.status != TransferRequest.STATUS_FULFILLED:
                inventory_adjustments = transfer_request.apply_manual_inventory_fulfillment()
                transfer_request.status = TransferRequest.STATUS_FULFILLED
                transfer_request.fulfilled_at = timezone.now()
                transfer_request.fulfilled_by = request.user
                transfer_request.save(update_fields=['status', 'fulfilled_at', 'fulfilled_by', 'updated_at'])
        elif new_status == TransferRequest.STATUS_NEW:
            # Reset to NEW (clear assignment)
            transfer_request.clear_assignment()
            if transfer_request.status != TransferRequest.STATUS_NEW:
                transfer_request.status = TransferRequest.STATUS_NEW
                transfer_request.save(update_fields=['status', 'updated_at'])
        
        transfer_request.refresh_from_db()
        
        return Response(
            {
                **self.get_serializer(transfer_request).data,
                '_status_change': {
                    'old_status': old_status,
                    'new_status': transfer_request.status,
                    'changed_by': request.user.name if hasattr(request.user, 'name') else str(request.user),
                },
                '_inventory_adjustments': inventory_adjustments,
            },
            status=status.HTTP_200_OK
        )

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

        available_quantity = (
            StockProduct.objects.filter(
                warehouse=warehouse,
                product=product
            ).aggregate(total=Sum('quantity'))['total'] or 0
        )
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
            for row in StockProduct.objects.filter(warehouse_id__in=all_warehouse_ids).values('warehouse_id').annotate(total=Sum('quantity')):
                warehouse_stock_map[row['warehouse_id']] = int(row['total'] or 0)

        storefront_stock_map = {}
        if all_storefront_ids:
            for row in StoreFrontInventory.objects.filter(storefront_id__in=all_storefront_ids).values('storefront_id').annotate(total=Sum('quantity')):
                storefront_stock_map[row['storefront_id']] = int(row['total'] or 0)

        storefront_pending_map = {}
        if all_storefront_ids:
            pending_qs = TransferRequest.objects.filter(
                storefront_id__in=all_storefront_ids,
                status=TransferRequest.STATUS_NEW,
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

        my_transfer_requests = [
            {
                'id': str(request_obj.id),
                'status': request_obj.status,
                'priority': request_obj.priority,
                'storefront': str(request_obj.storefront_id),
                'storefront_name': request_obj.storefront.name,
                'created_at': request_obj.created_at.isoformat(),
            }
            for request_obj in TransferRequest.objects.filter(requested_by=user)
            .select_related('storefront')
            .order_by('-created_at')[:10]
        ]

        businesses_payload = []
        warehouses_payload = []
        storefronts_payload = []
        seen_warehouse_ids = set()
        seen_storefront_ids = set()

        request_status_template = {status: 0 for status, _ in TransferRequest.STATUS_CHOICES}

        for business_id, context in contexts.items():
            membership = context['membership']
            business = membership.business
            is_manager = context['is_manager']

            request_counts = request_status_template.copy()
            source_counts = manager_request_counts if is_manager else non_manager_request_counts
            for status_key, total in source_counts.get(business_id, {}).items():
                request_counts[status_key] = total

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
            return StockProduct.objects.select_related('product', 'supplier', 'warehouse', 'stock')

        business_ids = _business_ids_for_user(user)
        if not business_ids:
            return StockProduct.objects.none()
        return StockProduct.objects.filter(
            warehouse__business_link__business_id__in=business_ids
        ).select_related('product', 'supplier', 'warehouse', 'stock')

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


class WarehouseStockAvailabilityView(APIView):
    """Legacy endpoint for warehouse-level availability checks used by transfers."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        warehouse_id = request.query_params.get('warehouse')
        product_id = request.query_params.get('product')
        requested_quantity_param = request.query_params.get('quantity')

        if not warehouse_id or not product_id:
            return Response(
                {'detail': 'warehouse and product query parameters are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            warehouse = Warehouse.objects.select_related('business_link__business').get(id=warehouse_id)
        except Warehouse.DoesNotExist:
            return Response({'detail': 'Warehouse not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            product = Product.objects.select_related('business').get(id=product_id)
        except Product.DoesNotExist:
            return Response({'detail': 'Product not found.'}, status=status.HTTP_404_NOT_FOUND)

        business_link = getattr(warehouse, 'business_link', None)
        business_id = business_link.business_id if business_link else None

        allowed_business_ids = _business_ids_for_user(request.user)
        if business_id and business_id not in allowed_business_ids:
            return Response({'detail': 'You do not have access to this warehouse.'}, status=status.HTTP_403_FORBIDDEN)

        if product.business_id and business_id and product.business_id != business_id:
            return Response(
                {'detail': 'Product does not belong to this warehouse business.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            requested_quantity = int(requested_quantity_param) if requested_quantity_param is not None else None
            if requested_quantity is not None and requested_quantity < 0:
                raise ValueError
        except (TypeError, ValueError):
            return Response({'detail': 'quantity must be a positive integer.'}, status=status.HTTP_400_BAD_REQUEST)

        available_quantity = (
            StockProduct.objects.filter(warehouse=warehouse, product=product)
            .aggregate(total=Sum('quantity'))
            .get('total')
        ) or 0

        is_available = True
        if requested_quantity is not None:
            is_available = available_quantity >= requested_quantity

        return Response(
            {
                'warehouse': str(warehouse.id),
                'product': str(product.id),
                'available_quantity': available_quantity,
                'requested_quantity': requested_quantity,
                'is_available': is_available,
            },
            status=status.HTTP_200_OK,
        )


class StockAvailabilityView(APIView):
    """Return storefront-level stock availability for a product."""

    permission_classes = [permissions.IsAuthenticated]

    @staticmethod
    def _decimal_to_native(value: Decimal) -> int | float:
        if value == value.to_integral_value():
            return int(value)
        return float(value)

    @staticmethod
    def _user_has_access(user, storefront: StoreFront) -> bool:
        if not getattr(user, 'is_authenticated', False):
            return False
        if user.is_superuser or getattr(user, 'is_platform_super_admin', False):
            return True
        if storefront.user_id == getattr(user, 'id', None):
            return True
        return StoreFrontEmployee.objects.filter(
            storefront=storefront,
            user=user,
            is_active=True,
        ).exists()

    def get(self, request, storefront_id, product_id):
        storefront = get_object_or_404(
            StoreFront.objects.select_related('business_link__business', 'user'),
            id=storefront_id,
        )

        if not self._user_has_access(request.user, storefront):
            return Response(
                {"detail": "You do not have access to this storefront."},
                status=status.HTTP_403_FORBIDDEN,
            )

        product = get_object_or_404(
            Product.objects.select_related('business'),
            id=product_id,
        )

        business_link = getattr(storefront, 'business_link', None)
        if business_link and product.business_id != business_link.business_id:
            return Response(
                {"detail": "Product does not belong to this storefront's business."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        inventory_entry = StoreFrontInventory.objects.filter(
            storefront=storefront,
            product=product,
        ).first()

        # StoreFrontInventory.quantity already represents current inventory
        # (it gets decremented by commit_stock() when sales are completed)
        # So we use it directly without subtracting sold items again
        total_available = Decimal(str(inventory_entry.quantity)) if inventory_entry else Decimal('0')
        if total_available < Decimal('0'):
            total_available = Decimal('0')

        reserved_quantity = Decimal('0')
        reservations_data: list[dict] = []

        if SALES_APP_AVAILABLE and StockReservation is not None and Sale is not None:
            now = timezone.now()
            reservations = (
                StockReservation.objects.filter(
                    stock_product__product=product,
                    status='ACTIVE',
                    expires_at__gt=now,
                )
                .select_related('stock_product')
            )

            reservation_sale_pairs: list[tuple] = []
            sale_ids: list[str] = []

            for reservation in reservations:
                try:
                    sale_uuid = str(UUID(str(reservation.cart_session_id)))
                except (TypeError, ValueError):
                    continue
                reservation_sale_pairs.append((reservation, sale_uuid))
                sale_ids.append(sale_uuid)

            sales_lookup = {}
            if sale_ids:
                sales = (
                    Sale.objects.filter(id__in=sale_ids)
                    .select_related('storefront', 'customer')
                )
                sales_lookup = {str(sale.id): sale for sale in sales}

            for reservation, sale_id in reservation_sale_pairs:
                sale = sales_lookup.get(sale_id)
                if not sale or sale.storefront_id != storefront_id:
                    continue

                quantity = Decimal(reservation.quantity)
                reserved_quantity += quantity
                reservations_data.append({
                    'id': str(reservation.id),
                    'quantity': self._decimal_to_native(quantity),
                    'sale_id': str(sale.id),
                    'customer_name': sale.customer.name if sale.customer else None,
                    'expires_at': reservation.expires_at.isoformat(),
                    'created_at': reservation.created_at.isoformat(),
                })

        unreserved_quantity = total_available - reserved_quantity
        if unreserved_quantity < Decimal('0'):
            unreserved_quantity = Decimal('0')

        stock_products = (
            StockProduct.objects.filter(product=product)
            .select_related('warehouse', 'stock')
            .order_by('-created_at')
        )

        batches_data = []
        for stock_product in stock_products:
            batches_data.append({
                'id': str(stock_product.id),
                'batch_number': getattr(stock_product, 'batch_number', None),
                'quantity': stock_product.quantity,
                'retail_price': str(stock_product.retail_price),
                'wholesale_price': str(stock_product.wholesale_price) if stock_product.wholesale_price else None,
                'expiry_date': stock_product.expiry_date.isoformat() if stock_product.expiry_date else None,
                'created_at': stock_product.created_at.isoformat(),
                'warehouse': stock_product.warehouse.name if stock_product.warehouse else None,
            })

        response_payload = {
            'total_available': self._decimal_to_native(total_available),
            'reserved_quantity': self._decimal_to_native(reserved_quantity),
            'unreserved_quantity': self._decimal_to_native(unreserved_quantity),
            'batches': batches_data,
            'reservations': reservations_data,
        }

        return Response(response_payload, status=status.HTTP_200_OK)
