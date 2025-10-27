"""
MovementTracker Service - Unified Stock Movement Tracking

This service provides a unified interface for tracking all stock movements
across the system, abstracting away the underlying data sources (old StockAdjustment
records and new Transfer records).

Purpose:
- Aggregate movements from multiple sources (StockAdjustment, Transfer, Sales)
- Provide consistent movement data for reports and analytics
- Support transition from old to new transfer system without breaking reports
- Maintain historical data continuity

Usage:
    from reports.services import MovementTracker
    
    movements = MovementTracker.get_movements(
        business_id=business_id,
        warehouse_id=warehouse_id,
        start_date='2025-10-01',
        end_date='2025-10-31'
    )
"""

from decimal import Decimal
from typing import List, Dict, Optional, Any
from datetime import datetime, date
from django.db.models import Q, Sum, F, Value, CharField, Case, When
from django.db.models.functions import Coalesce
from django.utils import timezone


class MovementTracker:
    """
    Unified service for tracking all stock movements across the system.
    
    This class abstracts the complexity of querying multiple data sources
    (old StockAdjustment transfers, new Transfer records, and sales) to
    provide a consistent view of stock movements.
    """
    
    # Movement type constants
    MOVEMENT_TYPE_TRANSFER = 'transfer'
    MOVEMENT_TYPE_SALE = 'sale'
    MOVEMENT_TYPE_ADJUSTMENT = 'adjustment'
    MOVEMENT_TYPE_SHRINKAGE = 'shrinkage'
    
    # Adjustment types that represent shrinkage
    SHRINKAGE_TYPES = [
        'THEFT',
        'DAMAGE',
        'EXPIRED',
        'SPOILAGE',
        'LOSS',
        'WRITE_OFF'
    ]
    
    @classmethod
    def get_movements(
        cls,
        business_id: str,
        warehouse_id: Optional[str] = None,
        product_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        movement_types: Optional[List[str]] = None,
        include_cancelled: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get all stock movements matching the specified criteria.
        
        Args:
            business_id: UUID of the business
            warehouse_id: Optional UUID of warehouse to filter by
            product_id: Optional UUID of product to filter by
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering
            movement_types: Optional list of movement types to include
            include_cancelled: Whether to include cancelled transfers
            
        Returns:
            List of movement dictionaries with standardized fields:
            - id: Movement identifier
            - type: Movement type (transfer/sale/adjustment/shrinkage)
            - source_type: Original source ('legacy_adjustment', 'new_transfer', 'sale')
            - date: Movement date
            - product_id: Product UUID
            - product_name: Product name
            - product_sku: Product SKU
            - quantity: Quantity moved (absolute value)
            - direction: 'in' or 'out'
            - source_location: Source warehouse/storefront name
            - destination_location: Destination warehouse/storefront name
            - reference_number: Reference/tracking number
            - unit_cost: Unit cost (if available)
            - total_value: Total value of movement
            - reason: Reason/notes for movement
            - created_by: User who created the movement
            - status: Movement status
        """
        movements = []
        
        # 1. Get movements from old StockAdjustment system
        legacy_movements = cls._get_legacy_adjustment_movements(
            business_id=business_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            start_date=start_date,
            end_date=end_date,
            movement_types=movement_types
        )
        movements.extend(legacy_movements)
        
        # 2. Get movements from new Transfer system (if available)
        try:
            new_transfer_movements = cls._get_new_transfer_movements(
                business_id=business_id,
                warehouse_id=warehouse_id,
                product_id=product_id,
                start_date=start_date,
                end_date=end_date,
                include_cancelled=include_cancelled
            )
            movements.extend(new_transfer_movements)
        except ImportError:
            # Transfer model not yet deployed, skip
            pass
        
        # 3. Get movements from sales (if requested)
        if not movement_types or cls.MOVEMENT_TYPE_SALE in movement_types:
            sale_movements = cls._get_sale_movements(
                business_id=business_id,
                warehouse_id=warehouse_id,
                product_id=product_id,
                start_date=start_date,
                end_date=end_date
            )
            movements.extend(sale_movements)
        
        # Sort by date (most recent first)
        movements.sort(key=lambda x: x.get('date', datetime.min), reverse=True)
        
        return movements
    
    @classmethod
    def get_summary(
        cls,
        business_id: str,
        warehouse_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Get summary statistics for stock movements.
        
        Args:
            business_id: UUID of the business
            warehouse_id: Optional UUID of warehouse to filter by
            start_date: Optional start date for filtering
            end_date: Optional end date for filtering
            
        Returns:
            Dictionary with summary statistics:
            - total_movements: Total number of movements
            - transfers_count: Number of transfers
            - sales_count: Number of sales
            - adjustments_count: Number of adjustments
            - shrinkage_count: Number of shrinkage events
            - total_quantity_transferred: Total quantity transferred
            - total_quantity_sold: Total quantity sold
            - total_shrinkage_quantity: Total shrinkage quantity
            - total_value_transferred: Total value transferred
            - total_value_sold: Total value sold
            - total_shrinkage_value: Total shrinkage value
        """
        movements = cls.get_movements(
            business_id=business_id,
            warehouse_id=warehouse_id,
            start_date=start_date,
            end_date=end_date
        )
        
        summary = {
            'total_movements': len(movements),
            'transfers_count': 0,
            'sales_count': 0,
            'adjustments_count': 0,
            'shrinkage_count': 0,
            'total_quantity_transferred': 0,
            'total_quantity_sold': 0,
            'total_shrinkage_quantity': 0,
            'total_value_transferred': Decimal('0.00'),
            'total_value_sold': Decimal('0.00'),
            'total_shrinkage_value': Decimal('0.00'),
        }
        
        for movement in movements:
            movement_type = movement.get('type')
            quantity = movement.get('quantity', 0)
            total_value = movement.get('total_value', Decimal('0.00'))
            
            if movement_type == cls.MOVEMENT_TYPE_TRANSFER:
                summary['transfers_count'] += 1
                summary['total_quantity_transferred'] += quantity
                summary['total_value_transferred'] += total_value
            elif movement_type == cls.MOVEMENT_TYPE_SALE:
                summary['sales_count'] += 1
                summary['total_quantity_sold'] += quantity
                summary['total_value_sold'] += total_value
            elif movement_type == cls.MOVEMENT_TYPE_SHRINKAGE:
                summary['shrinkage_count'] += 1
                summary['total_shrinkage_quantity'] += quantity
                summary['total_shrinkage_value'] += total_value
            elif movement_type == cls.MOVEMENT_TYPE_ADJUSTMENT:
                summary['adjustments_count'] += 1
        
        return summary
    
    @classmethod
    def _get_legacy_adjustment_movements(
        cls,
        business_id: str,
        warehouse_id: Optional[str] = None,
        product_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        movement_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Get movements from old StockAdjustment system."""
        from inventory.stock_adjustments import StockAdjustment
        
        # Build query filters
        filters = Q(stock_product__product__business_id=business_id)
        
        if warehouse_id:
            filters &= Q(stock_product__warehouse_id=warehouse_id)
        
        if product_id:
            filters &= Q(stock_product__product_id=product_id)
        
        if start_date:
            filters &= Q(created_at__date__gte=start_date)
        
        if end_date:
            filters &= Q(created_at__date__lte=end_date)
        
        # Filter by adjustment types based on requested movement types
        if movement_types:
            type_filters = Q()
            if cls.MOVEMENT_TYPE_TRANSFER in movement_types:
                type_filters |= Q(adjustment_type__in=['TRANSFER_IN', 'TRANSFER_OUT'])
            if cls.MOVEMENT_TYPE_SHRINKAGE in movement_types:
                type_filters |= Q(adjustment_type__in=cls.SHRINKAGE_TYPES)
            if cls.MOVEMENT_TYPE_ADJUSTMENT in movement_types:
                # Include other adjustment types
                type_filters |= Q(
                    ~Q(adjustment_type__in=['TRANSFER_IN', 'TRANSFER_OUT'] + cls.SHRINKAGE_TYPES)
                )
            filters &= type_filters
        
        # Query adjustments
        adjustments = StockAdjustment.objects.filter(filters).select_related(
            'stock_product',
            'stock_product__product',
            'stock_product__warehouse',
            'created_by'
        ).order_by('-created_at')
        
        movements = []
        for adj in adjustments:
            # Determine movement type
            if adj.adjustment_type in ['TRANSFER_IN', 'TRANSFER_OUT']:
                movement_type = cls.MOVEMENT_TYPE_TRANSFER
            elif adj.adjustment_type in cls.SHRINKAGE_TYPES:
                movement_type = cls.MOVEMENT_TYPE_SHRINKAGE
            else:
                movement_type = cls.MOVEMENT_TYPE_ADJUSTMENT
            
            # Determine direction
            direction = 'in' if adj.quantity > 0 else 'out'
            
            # Get product details safely
            product = adj.stock_product.product if adj.stock_product else None
            warehouse = adj.stock_product.warehouse if adj.stock_product else None
            
            movement = {
                'id': str(adj.id),
                'type': movement_type,
                'source_type': 'legacy_adjustment',
                'date': adj.created_at,
                'product_id': str(product.id) if product else None,
                'product_name': product.name if product else 'Unknown',
                'product_sku': product.sku if product else None,
                'quantity': abs(adj.quantity),
                'direction': direction,
                'source_location': warehouse.name if warehouse and direction == 'out' else None,
                'destination_location': warehouse.name if warehouse and direction == 'in' else None,
                'reference_number': adj.reference_number or f"ADJ-{str(adj.id)[:8]}",
                'unit_cost': adj.unit_cost,
                'total_cost': adj.total_cost,
                'total_value': abs(adj.total_cost) if adj.total_cost else Decimal('0.00'),
                'reason': adj.reason or adj.get_adjustment_type_display(),
                'created_by': adj.created_by.name if adj.created_by else None,
                'status': adj.status,
                'adjustment_type': adj.adjustment_type,
            }
            
            movements.append(movement)
        
        return movements
    
    @classmethod
    def _get_new_transfer_movements(
        cls,
        business_id: str,
        warehouse_id: Optional[str] = None,
        product_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        include_cancelled: bool = False
    ) -> List[Dict[str, Any]]:
        """Get movements from new Transfer system."""
        from inventory.transfer_models import Transfer, TransferItem
        
        # Build query filters
        filters = Q(business_id=business_id)
        
        # Only include completed transfers (or pending/in_transit if specified)
        if not include_cancelled:
            filters &= Q(status__in=['pending', 'in_transit', 'completed'])
        
        if warehouse_id:
            filters &= (
                Q(source_warehouse_id=warehouse_id) |
                Q(destination_warehouse_id=warehouse_id)
            )
        
        if start_date:
            filters &= Q(created_at__date__gte=start_date)
        
        if end_date:
            filters &= Q(created_at__date__lte=end_date)
        
        # Query transfers
        transfers = Transfer.objects.filter(filters).select_related(
            'source_warehouse',
            'destination_warehouse',
            'destination_storefront',
            'created_by',
            'received_by'
        ).prefetch_related('items__product').order_by('-created_at')
        
        movements = []
        for transfer in transfers:
            # Get location names
            source_location = transfer.source_warehouse.name if transfer.source_warehouse else None
            
            if transfer.destination_warehouse:
                destination_location = transfer.destination_warehouse.name
            elif transfer.destination_storefront:
                destination_location = transfer.destination_storefront.name
            else:
                destination_location = None
            
            # Create a movement entry for each item in the transfer
            for item in transfer.items.all():
                # Skip if filtering by product and this isn't it
                if product_id and str(item.product_id) != str(product_id):
                    continue
                
                movement = {
                    'id': f"{transfer.id}-{item.id}",
                    'type': cls.MOVEMENT_TYPE_TRANSFER,
                    'source_type': 'new_transfer',
                    'date': transfer.received_date or transfer.created_at,
                    'product_id': str(item.product.id),
                    'product_name': item.product.name,
                    'product_sku': item.product.sku,
                    'quantity': item.quantity,
                    'direction': 'both',  # Transfers move stock from source to destination
                    'source_location': source_location,
                    'destination_location': destination_location,
                    'reference_number': transfer.reference_number,
                    'unit_cost': item.unit_cost,
                    'total_cost': item.total_cost,
                    'total_value': item.total_cost,
                    'reason': transfer.notes or 'Stock transfer',
                    'created_by': transfer.created_by.name if transfer.created_by else None,
                    'received_by': transfer.received_by.name if transfer.received_by else None,
                    'status': transfer.status,
                    'transfer_type': transfer.transfer_type,
                    'transfer_id': str(transfer.id),
                }
                
                movements.append(movement)
        
        return movements
    
    @classmethod
    def _get_sale_movements(
        cls,
        business_id: str,
        warehouse_id: Optional[str] = None,
        product_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[Dict[str, Any]]:
        """Get movements from sales."""
        try:
            from sales.models import Sale, SaleItem
        except ImportError:
            return []
        
        # Build query filters
        filters = Q(sale__business_id=business_id)
        
        if warehouse_id:
            # Sales are from storefronts
            filters &= Q(sale__storefront_id=warehouse_id)
        
        if product_id:
            filters &= Q(product_id=product_id)
        
        if start_date:
            filters &= Q(sale__created_at__date__gte=start_date)
        
        if end_date:
            filters &= Q(sale__created_at__date__lte=end_date)
        
        # Query sale items
        sale_items = SaleItem.objects.filter(filters).select_related(
            'sale',
            'sale__storefront',
            'product',
            'sale__user'
        ).order_by('-sale__created_at')
        
        movements = []
        for item in sale_items:
            sale = item.sale
            
            # Determine source location
            if sale.storefront:
                source_location = sale.storefront.name
            else:
                source_location = 'Unknown'
            
            movement = {
                'id': str(item.id),
                'type': cls.MOVEMENT_TYPE_SALE,
                'source_type': 'sale',
                'date': sale.created_at.date(),
                'product_id': str(item.product.id),
                'product_name': item.product.name,
                'product_sku': item.product.sku,
                'quantity': item.quantity,
                'direction': 'out',
                'source_location': source_location,
                'destination_location': 'Customer',
                'reference_number': sale.receipt_number,
                'unit_cost': item.unit_cost if hasattr(item, 'unit_cost') else None,
                'total_value': item.total_price,
                'reason': f"Sale - {sale.get_type_display()}",
                'created_by': sale.user.name if sale.user else None,
                'status': sale.status,
                'sale_id': str(sale.id),
                'sale_type': sale.type,
            }
            
            movements.append(movement)
        
        return movements
