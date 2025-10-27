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
        Create a paired inter-warehouse transfer (creates TRANSFER_OUT and TRANSFER_IN adjustments).

        Expected payload:
        {
            "from_stock_product_id": "<uuid>",
            "to_stock_product_id": "<uuid>",
            "quantity": 5,
            "unit_cost": 12.34,            # optional, will be taken from from_stock_product if omitted
            "reference_number": "REF123", # optional
            "reason": "Moving stock",
            "requires_approval": true,     # optional (default: true)
            "auto_complete": false         # optional: if true, attempt to approve and complete immediately
        }
        """
        data = request.data or {}

        from_id = data.get('from_stock_product_id')
        to_id = data.get('to_stock_product_id')
        # Support frontend payload form: product + warehouse ids
        product_id = data.get('product_id')
        from_warehouse_id = data.get('from_warehouse_id')
        to_warehouse_id = data.get('to_warehouse_id')
        quantity = data.get('quantity')
        unit_cost = data.get('unit_cost')
        reference_number = data.get('reference_number')
        reason = data.get('reason')
        requires_approval = data.get('requires_approval', True)
        auto_complete = data.get('auto_complete', False)

        if not ((from_id and to_id) or (product_id and from_warehouse_id and to_warehouse_id)) or quantity is None:
            return Response({'error': 'from_stock_product_id/to_stock_product_id or product_id+from_warehouse_id+to_warehouse_id and quantity are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            quantity = int(quantity)
            if quantity <= 0:
                raise ValueError()
        except Exception:
            return Response({'error': 'quantity must be a positive integer'}, status=status.HTTP_400_BAD_REQUEST)

        # Resolve StockProduct either by direct stock_product ids or by product+warehouse ids
        from_sp = None
        to_sp = None
        ambiguity_warnings = []
        try:
            if from_id and to_id:
                from_sp = StockProduct.objects.select_related('warehouse', 'product').get(id=from_id)
                to_sp = StockProduct.objects.select_related('warehouse', 'product').get(id=to_id)
            else:
                # Lookup by product and warehouse — use filter then pick best candidate
                from_qs = StockProduct.objects.select_related('warehouse', 'product').filter(product__id=product_id, warehouse__id=from_warehouse_id)
                to_qs = StockProduct.objects.select_related('warehouse', 'product').filter(product__id=product_id, warehouse__id=to_warehouse_id)

                if not from_qs.exists():
                    return Response({'error': 'source stock product for given product/warehouse not found'}, status=status.HTTP_404_NOT_FOUND)
                # If destination stock product doesn't exist, we'll create one (zero quantity)
                create_destination_if_missing = False
                if not to_qs.exists():
                    create_destination_if_missing = True

                # Prefer a candidate with enough quantity for the source
                # Prefer candidates with sufficient calculated quantity (working quantity)
                sufficient_qs = from_qs.filter(calculated_quantity__gte=quantity)
                if sufficient_qs.exists():
                    from_sp = sufficient_qs.order_by('-calculated_quantity').first()
                    if from_qs.count() > 1:
                        ambiguity_warnings.append('multiple source stock entries found; selected one with sufficient quantity')
                else:
                    # No candidate has enough quantity; pick the one with highest quantity (best-effort)
                    from_sp = from_qs.order_by('-calculated_quantity').first()
                    if from_qs.count() > 1:
                        ambiguity_warnings.append('multiple source stock entries found; selected one with highest quantity')

                # For destination, prefer the one with highest existing quantity (or first)
                if to_qs.count() == 1:
                    to_sp = to_qs.first()
                else:
                    to_sp = to_qs.order_by('-calculated_quantity').first()
                    ambiguity_warnings.append('multiple destination stock entries found; selected one with highest calculated quantity')
        except StockProduct.DoesNotExist:
            return Response({'error': 'stock product for given product/warehouse not found'}, status=status.HTTP_404_NOT_FOUND)

        # Determine unit_cost if not provided, and coerce to Decimal
        if unit_cost is None:
            # Prefer landed_unit_cost then unit_cost
            unit_cost = getattr(from_sp, 'landed_unit_cost', None) or getattr(from_sp, 'unit_cost', 0) or 0

        try:
            # Convert to Decimal safely (handles Decimal, float or string)
            unit_cost = Decimal(str(unit_cost)) if unit_cost is not None else Decimal('0.00')
        except Exception:
            unit_cost = Decimal('0.00')

        # New behavior: always create a new destination Stock + StockProduct for the transfer.
        # Copy all relevant fields from the source StockProduct except created_at/updated_at.
        try:
            prod = Product.objects.get(id=product_id) if product_id else from_sp.product
            dest_wh = Warehouse.objects.get(id=to_warehouse_id) if to_warehouse_id else (to_sp.warehouse if to_sp else None)
            if dest_wh is None:
                return Response({'error': 'destination warehouse could not be resolved'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': f'failed to resolve product/warehouse: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        # Validate source has enough working (calculated) quantity
        if (getattr(from_sp, 'calculated_quantity', None) or 0) < quantity:
            return Response({'error': 'source does not have enough available quantity for this transfer'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from django.db import transaction
            with transaction.atomic():
                # Create a new Stock for destination, copying arrival_date/description from source stock where present
                new_stock = Stock.objects.create(
                    arrival_date=getattr(from_sp.stock, 'arrival_date', None),
                    description=(getattr(from_sp.stock, 'description', None) or 'Auto-created stock batch for transfer')
                )

                # Build kwargs copying fields from source (destination quantity = transferred quantity)
                sp_kwargs = dict(
                    stock=new_stock,
                    warehouse=dest_wh,
                    product=prod,
                    supplier=getattr(from_sp, 'supplier', None),
                    expiry_date=getattr(from_sp, 'expiry_date', None),
                    # Historically we created the destination batch with the
                    # transferred quantity. Keep that behavior here: the
                    # incoming transfer may be represented on the intake. The
                    # completion logic in StockAdjustment.complete() special-
                    # cases TRANSFER_IN to avoid double-counting when the
                    # intake already includes the transferred units.
                    quantity=quantity,
                    unit_cost=unit_cost or getattr(from_sp, 'unit_cost', Decimal('0.00')),
                    unit_tax_rate=getattr(from_sp, 'unit_tax_rate', None),
                    unit_tax_amount=getattr(from_sp, 'unit_tax_amount', None),
                    unit_additional_cost=getattr(from_sp, 'unit_additional_cost', None),
                    retail_price=getattr(from_sp, 'retail_price', None),
                    wholesale_price=getattr(from_sp, 'wholesale_price', None),
                    description=getattr(from_sp, 'description', None),
                )

                # Create the destination StockProduct (this is the new batch representing the transferred items)
                new_to_sp = StockProduct.objects.create(**sp_kwargs)
                to_sp = new_to_sp
                ambiguity_warnings.append('created a new destination stock product record for this transfer')

                # Do NOT alter the source intake `quantity` field. We preserve the
                # intake quantity as the system of record. Transfer effects are
                # recorded via StockAdjustment records which update
                # StockProduct.calculated_quantity when completed.
                # Refresh source to ensure latest read, but do not modify it here.
                try:
                    from_sp.refresh_from_db()
                except Exception:
                    pass

        except AssertionError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': f'Failed to perform transfer: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Generate a transfer reference if none provided
        if not reference_number:
            import uuid
            reference_number = f"IWT-{uuid.uuid4().hex[:10].upper()}"

        # Create paired adjustments
        try:
            out_adj, in_adj = create_paired_transfer_adjustments(
                from_stock_product=from_sp,
                to_stock_product=to_sp,
                quantity=quantity,
                unit_cost=unit_cost,
                reference_number=reference_number,
                reason=reason,
                created_by=request.user,
                requires_approval=bool(requires_approval),
            )
        except AssertionError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': f'Failed to create transfer adjustments: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Optionally approve and complete immediately
        auto_errors = []
        if auto_complete:
            for adj in (out_adj, in_adj):
                try:
                    # Approve
                    adj.approve(request.user)
                    # Complete to apply stock changes
                    adj.complete()
                except Exception as e:
                    auto_errors.append({'id': str(adj.id), 'error': str(e)})

        # Build frontend-friendly response
        response_payload = {
            'success': True,
            'transfer_reference': reference_number,
            'out_adjustment_id': str(out_adj.id),
            'in_adjustment_id': str(in_adj.id),
            'source_stock_id': str(from_sp.id),
            'dest_stock_id': str(to_sp.id),
            'message': f"Transferred {quantity} units of {from_sp.product.name} from {from_sp.warehouse.name} to {to_sp.warehouse.name}."
        }

        if auto_errors:
            response_payload['auto_complete_errors'] = auto_errors

        if ambiguity_warnings:
            response_payload['warnings'] = ambiguity_warnings

        return Response(response_payload, status=status.HTTP_201_CREATED)


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
