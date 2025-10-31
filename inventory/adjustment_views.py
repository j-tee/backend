"""
ViewSets for Stock Adjustment System
"""

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError
from decimal import Decimal

from .stock_adjustments import (
    StockAdjustment,
    StockAdjustmentPhoto,
    StockAdjustmentDocument,
    StockCount,
    StockCountItem
)
from .adjustment_serializers import (
    StockAdjustmentSerializer,
    StockAdjustmentCreateSerializer,
    StockAdjustmentPhotoSerializer,
    StockAdjustmentDocumentSerializer,
    StockCountSerializer,
    StockCountItemSerializer,
    StockAdjustmentSummarySerializer,
    ShrinkageSummarySerializer
)
from .transfer_services import create_paired_transfer_adjustments
from accounts.models import BusinessMembership
from .models import StockProduct, Stock, Product, Warehouse


class StockAdjustmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing stock adjustments.
    
    Supports:
    - List adjustments with filtering
    - Create new adjustments
    - Approve/reject pending adjustments
    - View adjustment history
    - Summary statistics
    """
    
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['adjustment_type', 'status', 'requires_approval', 'stock_product']
    search_fields = ['reason', 'reference_number', 'stock_product__product__name']
    ordering_fields = ['created_at', 'total_cost', 'quantity']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter by user's business"""
        user = self.request.user
        
        # Get user's business via membership
        membership = BusinessMembership.objects.filter(
            user=user,
            is_active=True
        ).first()
        
        if not membership:
            return StockAdjustment.objects.none()
        
        queryset = StockAdjustment.objects.filter(
            business=membership.business
        ).exclude(
            # Exclude legacy TRANSFER_IN/OUT types - use Transfer model instead
            adjustment_type__in=['TRANSFER_IN', 'TRANSFER_OUT']
        ).select_related(
            'stock_product',
            'stock_product__product',
            'stock_product__stock',
            'stock_product__warehouse',
            'created_by',
            'approved_by'
        ).prefetch_related(
            'photos',
            'documents'
        )
        
        # Filter by status if provided
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        # Filter by warehouse
        warehouse_id = self.request.query_params.get('warehouse')
        if warehouse_id:
            queryset = queryset.filter(stock_product__warehouse__id=warehouse_id)
        
        return queryset
    
    def get_serializer_class(self):
        """Use different serializer for creation"""
        if self.action == 'create':
            return StockAdjustmentCreateSerializer
        return StockAdjustmentSerializer
    
    def update(self, request, *args, **kwargs):
        """Update an adjustment - only allowed for PENDING status"""
        instance = self.get_object()
        
        if instance.status != 'PENDING':
            return Response(
                {'error': f'Cannot edit adjustment with status: {instance.status}. Only PENDING adjustments can be edited.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Use create serializer for updates to enforce validation
        serializer = StockAdjustmentCreateSerializer(
            instance,
            data=request.data,
            partial=kwargs.get('partial', False)
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        # Return with standard serializer
        return Response(StockAdjustmentSerializer(instance).data)
    
    def partial_update(self, request, *args, **kwargs):
        """Partial update - delegates to update with partial=True"""
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """
        Approve a pending adjustment and immediately apply it to stock.
        
        This combines the approval and completion steps to ensure
        stock levels are updated immediately upon approval.
        """
        adjustment = self.get_object()
        
        if adjustment.status != 'PENDING':
            return Response(
                {'error': f'Cannot approve adjustment with status: {adjustment.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Approve the adjustment (this may approve/complete linked transfer pair)
            adjustment.approve(request.user)

            # Refresh to get the latest status (approve() may complete linked adjustments)
            try:
                adjustment.refresh_from_db()
            except Exception:
                pass

            # Only call complete() if the adjustment is still APPROVED (not already COMPLETED)
            if adjustment.status == 'APPROVED':
                try:
                    adjustment.complete()
                except DjangoValidationError as e:
                    # Return a consumable error to the frontend instead of a 500
                    return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

            serializer = self.get_serializer(adjustment)
            return Response(serializer.data)

        except DjangoValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            # Unexpected error - return 500 with a concise message
            return Response({'error': f'Failed to approve adjustment: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a pending adjustment"""
        adjustment = self.get_object()
        
        if adjustment.status != 'PENDING':
            return Response(
                {'error': f'Cannot reject adjustment with status: {adjustment.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        adjustment.reject(request.user)
        serializer = self.get_serializer(adjustment)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete an approved adjustment"""
        adjustment = self.get_object()
        
        if adjustment.status != 'APPROVED':
            return Response(
                {'error': f'Cannot complete adjustment with status: {adjustment.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            adjustment.complete()
            serializer = self.get_serializer(adjustment)
            return Response(serializer.data)
        
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def pending(self, request):
        """Get all pending adjustments"""
        queryset = self.get_queryset().filter(status='PENDING')
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get summary statistics for adjustments"""
        queryset = self.get_queryset()
        
        # Overall stats
        overall = queryset.aggregate(
            total_adjustments=Count('id'),
            total_increase=Sum('quantity', filter=Q(quantity__gt=0)),
            total_decrease=Sum('quantity', filter=Q(quantity__lt=0)),
            total_cost_impact=Sum('total_cost')
        )
        
        # By type
        by_type = queryset.values('adjustment_type').annotate(
            count=Count('id'),
            total_quantity=Sum('quantity'),
            total_cost=Sum('total_cost')
        ).order_by('-total_cost')
        
        # By status
        by_status = queryset.values('status').annotate(
            count=Count('id')
        )
        
        return Response({
            'overall': overall,
            'by_type': list(by_type),
            'by_status': list(by_status)
        })
    
    @action(detail=False, methods=['get'])
    def shrinkage(self, request):
        """Get shrinkage report (theft, loss, damage, etc.)"""
        queryset = self.get_queryset()
        
        shrinkage_types = [
            'THEFT', 'LOSS', 'DAMAGE', 'EXPIRED',
            'SPOILAGE', 'WRITE_OFF'
        ]
        
        shrinkage = queryset.filter(
            status='COMPLETED',
            adjustment_type__in=shrinkage_types
        )
        
        # Overall shrinkage
        overall = shrinkage.aggregate(
            total_units=Sum('quantity'),
            total_cost=Sum('total_cost'),
            total_incidents=Count('id')
        )
        
        # By type
        by_type = shrinkage.values('adjustment_type').annotate(
            count=Count('id'),
            total_quantity=Sum('quantity'),
            total_cost=Sum('total_cost')
        ).order_by('-total_cost')
        
        # By product (top 10 most affected)
        by_product = shrinkage.values(
            'stock_product__product__name',
            'stock_product__product__code'
        ).annotate(
            total_quantity=Sum('quantity'),
            total_cost=Sum('total_cost'),
            incidents=Count('id')
        ).order_by('-total_cost')[:10]
        
        return Response({
            'overall': overall,
            'by_type': list(by_type),
            'top_affected_products': list(by_product)
        })
    
    @action(detail=False, methods=['post'])
    def bulk_approve(self, request):
        """Approve multiple adjustments at once"""
        adjustment_ids = request.data.get('adjustment_ids', [])
        
        if not adjustment_ids:
            return Response(
                {'error': 'No adjustment IDs provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        queryset = self.get_queryset().filter(
            id__in=adjustment_ids,
            status='PENDING'
        )
        
        approved = []
        failed = []
        
        for adjustment in queryset:
            try:
                adjustment.approve(request.user)
                
                # Try to complete if no further approval needed
                if not adjustment.requires_approval:
                    adjustment.complete()
                
                approved.append(str(adjustment.id))
            except Exception as e:
                failed.append({
                    'id': str(adjustment.id),
                    'error': str(e)
                })
        
        return Response({
            'approved': approved,
            'failed': failed,
            'total_approved': len(approved),
            'total_failed': len(failed)
        })

    @action(detail=False, methods=['post'], url_path='transfer')
    def transfer(self, request):
        """
        DEPRECATED: This endpoint creates legacy TRANSFER_IN/TRANSFER_OUT adjustments.
        
        Use the new Transfer API instead: POST /inventory/api/transfers/
        
        This endpoint is disabled as of the legacy transfer system removal.
        All transfers should now use the Transfer model.
        """
        return Response({
            'error': 'This endpoint is deprecated. Use POST /inventory/api/transfers/ instead.',
            'detail': 'The legacy TRANSFER_IN/TRANSFER_OUT adjustment system has been replaced with the unified Transfer model.',
            'new_endpoint': '/inventory/api/transfers/',
            'documentation': 'See Transfer API documentation for the new transfer workflow.'
        }, status=status.HTTP_410_GONE)


class StockAdjustmentPhotoViewSet(viewsets.ModelViewSet):
    """ViewSet for managing adjustment photos"""
    
    serializer_class = StockAdjustmentPhotoSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter by user's business"""
        user = self.request.user
        membership = BusinessMembership.objects.filter(
            user=user,
            is_active=True
        ).first()
        
        if not membership:
            return StockAdjustmentPhoto.objects.none()
        
        return StockAdjustmentPhoto.objects.filter(
            adjustment__business=membership.business
        ).select_related('adjustment', 'uploaded_by')
    
    def perform_create(self, serializer):
        """Set uploaded_by"""
        serializer.save(uploaded_by=self.request.user)


class StockAdjustmentDocumentViewSet(viewsets.ModelViewSet):
    """ViewSet for managing adjustment documents"""
    
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter by user's business"""
        user = self.request.user
        membership = BusinessMembership.objects.filter(
            user=user,
            is_active=True
        ).first()
        
        if not membership:
            return StockAdjustmentDocument.objects.none()
        
        return StockAdjustmentDocument.objects.filter(
            adjustment__business=membership.business
        ).select_related('adjustment', 'uploaded_by')
    
    def perform_create(self, serializer):
        """Set uploaded_by"""
        serializer.save(uploaded_by=self.request.user)


class StockCountViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing stock counts.
    
    Stock counts are used for physical inventory verification
    and to identify discrepancies that need adjustments.
    """
    
    serializer_class = StockCountSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['status', 'storefront', 'warehouse']
    ordering_fields = ['count_date', 'created_at']
    ordering = ['-count_date']
    
    def get_queryset(self):
        """Filter by user's business"""
        user = self.request.user
        membership = BusinessMembership.objects.filter(
            user=user,
            is_active=True
        ).first()
        
        if not membership:
            return StockCount.objects.none()
        
        return StockCount.objects.filter(
            business=membership.business
        ).select_related(
            'storefront',
            'warehouse',
            'created_by'
        ).prefetch_related('items')
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Complete the stock count"""
        stock_count = self.get_object()
        
        if stock_count.status != 'IN_PROGRESS':
            return Response(
                {'error': f'Cannot complete count with status: {stock_count.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        stock_count.complete()
        serializer = self.get_serializer(stock_count)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def create_adjustments(self, request, pk=None):
        """Create adjustments for all discrepancies in this count"""
        stock_count = self.get_object()
        
        if stock_count.status != 'COMPLETED':
            return Response(
                {'error': 'Stock count must be completed before creating adjustments'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        items_with_discrepancy = stock_count.items.filter(
            adjustment_created__isnull=True
        ).exclude(discrepancy=0)
        
        created_adjustments = []
        
        for item in items_with_discrepancy:
            adjustment = item.create_adjustment(request.user)
            if adjustment:
                created_adjustments.append(adjustment)
        
        return Response({
            'adjustments_created': len(created_adjustments),
            'adjustment_ids': [str(adj.id) for adj in created_adjustments]
        })
    
    @action(detail=True, methods=['get'])
    def discrepancies(self, request, pk=None):
        """Get all items with discrepancies"""
        stock_count = self.get_object()
        
        items = stock_count.items.exclude(discrepancy=0)
        serializer = StockCountItemSerializer(items, many=True)
        
        return Response(serializer.data)


class StockCountItemViewSet(viewsets.ModelViewSet):
    """ViewSet for managing individual count items"""
    
    serializer_class = StockCountItemSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['stock_count']
    
    def get_queryset(self):
        """Filter by user's business"""
        user = self.request.user
        membership = BusinessMembership.objects.filter(
            user=user,
            is_active=True
        ).first()
        
        if not membership:
            return StockCountItem.objects.none()
        
        return StockCountItem.objects.filter(
            stock_count__business=membership.business
        ).select_related(
            'stock_count',
            'stock_product',
            'stock_product__product'
        )
    
    @action(detail=True, methods=['post'])
    def create_adjustment(self, request, pk=None):
        """Create an adjustment for this count item's discrepancy"""
        item = self.get_object()
        
        if not item.has_discrepancy:
            return Response(
                {'error': 'No discrepancy to adjust'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if item.adjustment_created:
            return Response(
                {'error': 'Adjustment already created for this item'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        adjustment = item.create_adjustment(request.user)
        
        from .adjustment_serializers import StockAdjustmentSerializer
        serializer = StockAdjustmentSerializer(adjustment)
        
        return Response(serializer.data)
