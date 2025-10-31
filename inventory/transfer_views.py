"""
Transfer API Views (Phase 4)

ViewSets for the new Transfer system endpoints.
Replaces legacy StockAdjustment TRANSFER_IN/TRANSFER_OUT pairs.
"""

from decimal import Decimal

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError, PermissionDenied
from django.db.models import Q, Prefetch
from django.db import transaction
from django.utils import timezone

from inventory.transfer_models import Transfer, TransferItem
from inventory.transfer_serializers import (
    WarehouseTransferSerializer,
    StorefrontTransferSerializer,
    TransferCompleteSerializer,
    TransferCancelSerializer,
)
from accounts.models import BusinessMembership
from inventory.models import Warehouse, StoreFront, StockProduct, TransferRequest


def _business_ids_for_user(user):
    """Return list of business IDs the user belongs to."""
    if not getattr(user, 'is_authenticated', False):
        return []

    ids = set()

    owned_qs = getattr(user, 'owned_businesses', None)
    if owned_qs is not None:
        ids.update(owned_qs.values_list('id', flat=True))

    memberships_qs = getattr(user, 'business_memberships', None)
    if memberships_qs is not None:
        ids.update(
            memberships_qs.filter(is_active=True).values_list('business_id', flat=True)
        )

    return list(ids)


class BaseTransferViewSet(viewsets.ModelViewSet):
    """Base viewset for Transfer operations"""
    
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Get transfers for user's business"""
        user = self.request.user
        
        if not hasattr(user, 'primary_business') or not user.primary_business:
            return Transfer.objects.none()
        
        queryset = Transfer.objects.filter(
            business=user.primary_business
        ).select_related(
            'source_warehouse',
            'destination_warehouse',
            'destination_storefront',
            'created_by',
            'completed_by',
        ).prefetch_related(
            Prefetch(
                'items',
                queryset=TransferItem.objects.select_related('product')
            )
        ).order_by('-created_at')
        
        # Apply status filter
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Apply source warehouse filter
        source_warehouse_id = self.request.query_params.get('source_warehouse')
        if source_warehouse_id:
            queryset = queryset.filter(source_warehouse_id=source_warehouse_id)
        
        # Apply date range filter
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        
        # Apply search filter
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(reference_number__icontains=search) |
                Q(notes__icontains=search)
            )
        
        return queryset
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """
        Complete a transfer
        
        POST /api/warehouse-transfers/{id}/complete/
        POST /api/storefront-transfers/{id}/complete/
        
        Body (optional):
        {
            "notes": "Additional completion notes"
        }
        """
        transfer = self.get_object()
        serializer = TransferCompleteSerializer(
            transfer,
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        # Return updated transfer
        response_serializer = self.get_serializer(transfer)
        return Response(response_serializer.data)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """
        Cancel a transfer
        
        POST /api/warehouse-transfers/{id}/cancel/
        POST /api/storefront-transfers/{id}/cancel/
        
        Body:
        {
            "reason": "Reason for cancellation"
        }
        """
        transfer = self.get_object()
        serializer = TransferCancelSerializer(
            transfer,
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        # Return updated transfer
        response_serializer = self.get_serializer(transfer)
        return Response(response_serializer.data)
    
    def perform_destroy(self, instance):
        """
        Hard delete a transfer with full inventory reversal.
        
        DELETE /api/warehouse-transfers/{id}/
        DELETE /api/storefront-transfers/{id}/
        
        Restrictions:
        - Can only delete transfers with status: pending, in_transit, or cancelled
        - Cannot delete completed transfers (use a separate reversal process)
        - Reverses all inventory changes if transfer was completed before cancellation
        
        Process:
        1. Validate transfer can be deleted
        2. If transfer was previously completed then cancelled:
           - Verify destination stock still exists
           - Delete destination StockProduct entries
           - Restore source warehouse quantities
        3. Delete TransferItem records
        4. Delete Transfer record
        
        Raises:
            ValidationError: If transfer cannot be deleted
        """
        # Validate status
        if instance.status == Transfer.STATUS_COMPLETED:
            raise ValidationError({
                'error': 'Cannot delete a completed transfer. Use the cancellation process first, '
                         'or create a reversal transfer instead.'
            })
        
        # Permissions check - only OWNER, ADMIN can delete transfers
        user = self.request.user
        if hasattr(user, 'primary_business'):
            membership = user.business_memberships.filter(
                business=instance.business,
                is_active=True
            ).first()
            
            if not membership or membership.role not in ['OWNER', 'ADMIN']:
                raise PermissionDenied(
                    'Only business owners and administrators can delete transfers.'
                )
        
        # Store reference for logging
        transfer_ref = instance.reference_number
        transfer_type = instance.get_transfer_type_display()
        transfer_id = str(instance.id)
        transfer_status = instance.status
        
        # Perform deletion with transaction
        with transaction.atomic():
            # Delete all transfer items (CASCADE will handle this, but explicit is clearer)
            item_count = instance.items.count()
            instance.items.all().delete()
            
            # Delete the transfer
            instance.delete()
        
        # Log the deletion (after successful transaction)
        from accounts.models import AuditLog
        AuditLog.objects.create(
            user=user,
            action='DELETE',
            model_name='Transfer',
            object_id=transfer_id,
            changes={
                'reference_number': transfer_ref,
                'type': transfer_type,
                'status': transfer_status,
                'items_count': item_count,
                'reason': 'Manual deletion via API'
            }
        )


class WarehouseTransferViewSet(BaseTransferViewSet):
    """
    ViewSet for warehouse-to-warehouse transfers
    
    Endpoints:
    - GET    /api/warehouse-transfers/          - List all warehouse transfers
    - POST   /api/warehouse-transfers/          - Create new warehouse transfer
    - GET    /api/warehouse-transfers/{id}/     - Get transfer details
    - PUT    /api/warehouse-transfers/{id}/     - Update transfer (pending only)
    - PATCH  /api/warehouse-transfers/{id}/     - Partial update (pending only)
    - DELETE /api/warehouse-transfers/{id}/     - Delete transfer (pending only)
    - POST   /api/warehouse-transfers/{id}/complete/ - Complete transfer
    - POST   /api/warehouse-transfers/{id}/cancel/   - Cancel transfer
    
    Query Parameters:
    - status: Filter by status (pending, in_transit, completed, cancelled)
    - source_warehouse: Filter by source warehouse ID
    - destination_warehouse: Filter by destination warehouse ID
    - start_date: Filter by created date >= (YYYY-MM-DD)
    - end_date: Filter by created date <= (YYYY-MM-DD)
    - search: Search in reference_number or notes
    """
    
    serializer_class = WarehouseTransferSerializer
    
    def get_queryset(self):
        """Filter for warehouse-to-warehouse transfers only"""
        queryset = super().get_queryset()
        queryset = queryset.filter(destination_warehouse__isnull=False)
        
        # Apply destination warehouse filter
        dest_warehouse_id = self.request.query_params.get('destination_warehouse')
        if dest_warehouse_id:
            queryset = queryset.filter(destination_warehouse_id=dest_warehouse_id)
        
        return queryset


class StorefrontTransferViewSet(BaseTransferViewSet):
    """
    ViewSet for warehouse-to-storefront transfers
    
    Endpoints:
    - GET    /api/storefront-transfers/          - List all storefront transfers
    - POST   /api/storefront-transfers/          - Create new storefront transfer
    - GET    /api/storefront-transfers/{id}/     - Get transfer details
    - PUT    /api/storefront-transfers/{id}/     - Update transfer (pending only)
    - PATCH  /api/storefront-transfers/{id}/     - Partial update (pending only)
    - DELETE /api/storefront-transfers/{id}/     - Delete transfer (pending only)
    - POST   /api/storefront-transfers/{id}/complete/ - Complete transfer
    - POST   /api/storefront-transfers/{id}/cancel/   - Cancel transfer
    
    Query Parameters:
    - status: Filter by status (pending, in_transit, completed, cancelled)
    - source_warehouse: Filter by source warehouse ID
    - destination_storefront: Filter by destination storefront ID
    - start_date: Filter by created date >= (YYYY-MM-DD)
    - end_date: Filter by created date <= (YYYY-MM-DD)
    - search: Search in reference_number or notes
    """
    
    serializer_class = StorefrontTransferSerializer
    
    def get_queryset(self):
        """Filter for warehouse-to-storefront transfers only"""
        queryset = super().get_queryset()
        queryset = queryset.filter(destination_storefront__isnull=False)
        
        # Apply destination storefront filter
        dest_storefront_id = self.request.query_params.get('destination_storefront')
        if dest_storefront_id:
            queryset = queryset.filter(destination_storefront_id=dest_storefront_id)
        
        return queryset


class TransferWorkflowViewSet(viewsets.ViewSet):
    """Legacy-compatible transfer workflow viewset bridging requests and transfers."""

    permission_classes = [IsAuthenticated]
    manager_roles = {BusinessMembership.OWNER, BusinessMembership.ADMIN, BusinessMembership.MANAGER}

    def get_queryset(self):
        user = self.request.user
        base_qs = Transfer.objects.select_related(
            'business', 'source_warehouse', 'destination_storefront'
        ).prefetch_related('items__product')

        if user.is_superuser:
            return base_qs

        business_ids = _business_ids_for_user(user)
        if not business_ids:
            return Transfer.objects.none()
        return base_qs.filter(business_id__in=business_ids)

    def _ensure_manager(self, business, user):
        if user.is_superuser:
            return

        membership = BusinessMembership.objects.filter(
            business=business,
            user=user,
            is_active=True,
        ).first()

        if not membership or membership.role not in self.manager_roles:
            raise PermissionDenied('You do not have permission to manage transfers for this business.')

    def _get_linked_request(self, transfer):
        return TransferRequest.objects.select_related('storefront', 'business').prefetch_related('line_items__product').filter(
            linked_transfer_id=transfer.id
        ).first()

    def _serialize_transfer(self, transfer, request_obj=None):
        if request_obj is None:
            request_obj = self._get_linked_request(transfer)

        line_items = []
        if request_obj is not None:
            for line in request_obj.line_items.all():
                line_items.append({
                    'id': str(line.id),
                    'product': str(line.product_id),
                    'product_name': line.product.name,
                    'requested_quantity': line.requested_quantity,
                    'transferred_quantity': line.requested_quantity,
                })
        else:
            for item in transfer.items.select_related('product').all():
                line_items.append({
                    'id': str(item.id),
                    'product': str(item.product_id),
                    'product_name': item.product.name,
                    'requested_quantity': item.quantity,
                    'transferred_quantity': item.quantity,
                })

        # ✅ CRITICAL FIX: Base payload with transfer_number
        payload = {
            'id': str(transfer.id),
            'reference': transfer.reference_number,
            'transfer_number': transfer.reference_number,  # ✅ Add transfer_number field
            'status': transfer.status.upper(),
            'request_id': str(request_obj.id) if request_obj else None,
            'created_at': transfer.created_at.isoformat(),
            'updated_at': transfer.updated_at.isoformat(),
            'line_items': line_items,
            'items_detail': transfer.get_items_detail(),  # Add items_detail for frontend modals
        }

        # ✅ CRITICAL FIX: Add specific location fields based on transfer type
        # Determine transfer type and set appropriate from/to fields
        if transfer.source_warehouse and transfer.destination_warehouse:
            # Warehouse → Warehouse transfer
            payload['from_warehouse'] = transfer.source_warehouse.name
            payload['to_warehouse'] = transfer.destination_warehouse.name
            payload['source_warehouse'] = str(transfer.source_warehouse_id)  # Keep for backward compatibility
        elif transfer.source_warehouse and transfer.destination_storefront:
            # Warehouse → Storefront transfer
            payload['from_warehouse'] = transfer.source_warehouse.name
            payload['to_storefront'] = transfer.destination_storefront.name
            payload['source_warehouse'] = str(transfer.source_warehouse_id)  # Keep for backward compatibility
            payload['destination_storefront'] = str(transfer.destination_storefront_id)  # Keep for backward compatibility
        # Note: Storefront → Warehouse would be handled here if that transfer type exists
        # elif transfer.source_storefront and transfer.destination_warehouse:
        #     payload['from_storefront'] = transfer.source_storefront.name
        #     payload['to_warehouse'] = transfer.destination_warehouse.name

        # Add user information if available
        if transfer.created_by:
            payload['created_by'] = transfer.created_by.name if hasattr(transfer.created_by, 'name') else str(transfer.created_by)

        payload['received_at'] = transfer.received_at.isoformat() if transfer.received_at else None
        payload['received_by'] = str(transfer.received_by_id) if transfer.received_by_id else None

        return payload

    def list(self, request):
        transfers = self.get_queryset().order_by('-created_at')[:50]
        data = [self._serialize_transfer(transfer) for transfer in transfers]
        return Response(data)

    def retrieve(self, request, pk=None):
        transfer = self.get_queryset().filter(id=pk).first()
        if not transfer:
            raise ValidationError({'transfer': 'Transfer not found or access denied.'})
        return Response(self._serialize_transfer(transfer))

    def create(self, request):
        payload = request.data

        request_id = payload.get('request_id')
        source_warehouse_id = payload.get('source_warehouse')
        destination_storefront_id = payload.get('destination_storefront')

        if not request_id:
            raise ValidationError({'request_id': 'This field is required.'})
        if not source_warehouse_id:
            raise ValidationError({'source_warehouse': 'This field is required.'})
        if not destination_storefront_id:
            raise ValidationError({'destination_storefront': 'This field is required.'})

        try:
            transfer_request = TransferRequest.objects.select_related(
                'storefront',
                'storefront__business_link__business',
                'business',
            ).prefetch_related('line_items__product').get(id=request_id)
        except TransferRequest.DoesNotExist:
            raise ValidationError({'request_id': 'Transfer request not found.'})

        if not transfer_request.line_items.exists():
            raise ValidationError({'request_id': 'Transfer request does not have any line items to fulfill.'})

        if str(transfer_request.storefront_id) != str(destination_storefront_id):
            raise ValidationError({'destination_storefront': 'Destination storefront must match the request storefront.'})

        if transfer_request.linked_transfer_id:
            raise ValidationError({'request_id': 'Transfer request already has a linked transfer.'})

        business = transfer_request.business
        self._ensure_manager(business, request.user)

        try:
            source_warehouse = Warehouse.objects.select_related('business_link__business').get(id=source_warehouse_id)
        except Warehouse.DoesNotExist:
            raise ValidationError({'source_warehouse': 'Source warehouse not found.'})

        warehouse_business = getattr(source_warehouse, 'business_link', None)
        if not warehouse_business or warehouse_business.business_id != business.id:
            raise ValidationError({'source_warehouse': 'Warehouse must belong to the same business as the request.'})

        with transaction.atomic():
            transfer = Transfer.objects.create(
                business=business,
                transfer_type=Transfer.TYPE_WAREHOUSE_TO_STOREFRONT,
                source_warehouse=source_warehouse,
                destination_storefront=transfer_request.storefront,
                created_by=request.user,
                notes=payload.get('notes')
            )

            for line_item in transfer_request.line_items.select_related('product'):
                source_stock = StockProduct.objects.filter(
                    warehouse=source_warehouse,
                    product=line_item.product,
                ).order_by('-created_at').first()

                if not source_stock:
                    raise ValidationError({
                        'line_items': f"Product '{line_item.product.name}' is not available in the source warehouse."
                    })

                if source_stock.quantity < line_item.requested_quantity:
                    raise ValidationError({
                        'line_items': (
                            f"Insufficient quantity for '{line_item.product.name}'. "
                            f"Available: {source_stock.quantity}, Requested: {line_item.requested_quantity}"
                        )
                    })

                if not source_stock.unit_cost or source_stock.unit_cost <= 0:
                    raise ValidationError({
                        'line_items': f"Source stock for '{line_item.product.name}' is missing a positive unit cost."
                    })

                item = TransferItem(
                    transfer=transfer,
                    product=line_item.product,
                    quantity=line_item.requested_quantity,
                    unit_cost=source_stock.unit_cost or Decimal('0.00'),
                    supplier=source_stock.supplier,
                    expiry_date=source_stock.expiry_date,
                    unit_tax_rate=source_stock.unit_tax_rate,
                    unit_tax_amount=source_stock.unit_tax_amount,
                    unit_additional_cost=source_stock.unit_additional_cost,
                    retail_price=source_stock.retail_price or Decimal('0.00'),
                    wholesale_price=source_stock.wholesale_price or Decimal('0.00'),
                )
                item.save()

            transfer_request.status = TransferRequest.STATUS_ASSIGNED
            transfer_request.assigned_at = timezone.now()
            transfer_request.linked_transfer_id = transfer.id
            transfer_request.linked_transfer_reference = transfer.reference_number
            transfer_request.save(update_fields=[
                'status', 'assigned_at', 'linked_transfer_id', 'linked_transfer_reference', 'updated_at'
            ])

        return Response(self._serialize_transfer(transfer, transfer_request), status=status.HTTP_201_CREATED)

    def _get_transfer_for_action(self, pk):
        transfer = self.get_queryset().filter(id=pk).first()
        if not transfer:
            raise ValidationError({'transfer': 'Transfer not found or access denied.'})
        return transfer

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        transfer = self._get_transfer_for_action(pk)
        # No state transition required for submit; keep as pending but touch updated_at
        transfer.updated_at = timezone.now()
        transfer.save(update_fields=['updated_at'])
        return Response(self._serialize_transfer(transfer))

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        transfer = self._get_transfer_for_action(pk)
        transfer.updated_at = timezone.now()
        transfer.save(update_fields=['updated_at'])
        return Response(self._serialize_transfer(transfer))

    @action(detail=True, methods=['post'], url_path='dispatch')
    def mark_dispatched(self, request, pk=None):
        transfer = self._get_transfer_for_action(pk)
        if transfer.status == Transfer.STATUS_CANCELLED:
            raise ValidationError({'status': 'Cannot dispatch a cancelled transfer.'})

        if transfer.status != Transfer.STATUS_IN_TRANSIT:
            transfer.status = Transfer.STATUS_IN_TRANSIT
            transfer.save(update_fields=['status', 'updated_at'])

        return Response(self._serialize_transfer(transfer))

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        transfer = self._get_transfer_for_action(pk)

        try:
            transfer.complete_transfer(completed_by=request.user)
        except ValidationError as exc:
            raise ValidationError({'items': exc.detail if hasattr(exc, 'detail') else exc.message})

        return Response(self._serialize_transfer(transfer))

    @action(detail=True, methods=['post'], url_path='confirm-receipt')
    def confirm_receipt(self, request, pk=None):
        transfer = self._get_transfer_for_action(pk)

        if transfer.status != Transfer.STATUS_COMPLETED:
            # Ensure inventory is updated if caller goes straight to confirmation
            transfer.complete_transfer(completed_by=request.user)

        transfer.received_at = timezone.now()
        transfer.received_by = request.user
        transfer.save(update_fields=['received_at', 'received_by', 'updated_at'])

        transfer_request = self._get_linked_request(transfer)
        if transfer_request is not None:
            transfer_request.status = TransferRequest.STATUS_FULFILLED
            transfer_request.fulfilled_at = timezone.now()
            transfer_request.fulfilled_by = request.user
            transfer_request.save(update_fields=['status', 'fulfilled_at', 'fulfilled_by', 'updated_at'])

        return Response(self._serialize_transfer(transfer, transfer_request))
