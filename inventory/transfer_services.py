"""
DEPRECATED: Legacy transfer services for TRANSFER_IN/TRANSFER_OUT StockAdjustments.

This module is deprecated and should not be used for new code.
All transfers should use the new Transfer model instead.

Historical functionality preserved for reference only.
"""
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
    DEPRECATED: Use the Transfer model API instead.
    
    This function creates legacy TRANSFER_IN/TRANSFER_OUT adjustments.
    New code should use POST /inventory/api/transfers/ endpoint.
    
    Kept for historical reference only - do not use in new code.
    """
    raise DeprecationWarning(
        "create_paired_transfer_adjustments() is deprecated. "
        "Use the Transfer model and POST /inventory/api/transfers/ endpoint instead."
    )
