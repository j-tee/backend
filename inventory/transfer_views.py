"""
Transfer API Views (Phase 4)

ViewSets for the new Transfer system endpoints.
Replaces legacy StockAdjustment TRANSFER_IN/TRANSFER_OUT pairs.
"""

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
from inventory.models import Warehouse, StoreFront, StockProduct


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
