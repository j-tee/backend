from django.db import transaction
from .stock_adjustments import StockAdjustment
from .models import StockProduct
from typing import Tuple


def create_paired_transfer_adjustments(
    from_stock_product: StockProduct,
    to_stock_product: StockProduct,
    quantity: int,
    unit_cost: float,
    reference_number: str = None,
    reason: str = None,
    created_by=None,
    requires_approval=True,
) -> Tuple[StockAdjustment, StockAdjustment]:
    """
    Create paired StockAdjustment records for inter-warehouse transfer.
    - from_stock_product: StockProduct to transfer FROM (decrease)
    - to_stock_product: StockProduct to transfer TO (increase)
    - quantity: Number of units to transfer (positive integer)
    - unit_cost: Cost per unit for both adjustments
    - reference_number: Optional reference for both adjustments
    - reason: Optional reason for both adjustments
    - created_by: User creating the adjustments
    - requires_approval: Whether approval is required
    Returns (out_adjustment, in_adjustment)
    """
    assert quantity > 0, "Quantity must be positive"
    with transaction.atomic():
        out_adj = StockAdjustment.objects.create(
            business=from_stock_product.product.business,
            stock_product=from_stock_product,
            adjustment_type='TRANSFER_OUT',
            quantity=-quantity,
            unit_cost=unit_cost,
            reason=reason or f"Transfer out to {to_stock_product.warehouse.name}",
            reference_number=reference_number,
            status='PENDING',
            requires_approval=requires_approval,
            created_by=created_by,
        )
        in_adj = StockAdjustment.objects.create(
            business=to_stock_product.product.business,
            stock_product=to_stock_product,
            adjustment_type='TRANSFER_IN',
            quantity=quantity,
            unit_cost=unit_cost,
            reason=reason or f"Transfer in from {from_stock_product.warehouse.name}",
            reference_number=reference_number,
            status='PENDING',
            requires_approval=requires_approval,
            created_by=created_by,
        )
        return out_adj, in_adj
