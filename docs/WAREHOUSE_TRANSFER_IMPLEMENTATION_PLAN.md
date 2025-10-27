# 🏗️ Warehouse Transfer System - Complete Implementation Plan

## 📋 Table of Contents
1. [Executive Summary](#executive-summary)
2. [Current State Analysis](#current-state-analysis)
3. [Implementation Phases](#implementation-phases)
4. [Frontend Integration Guide](#frontend-integration-guide)
5. [API Documentation](#api-documentation)
6. [Migration Strategy](#migration-strategy)
7. [Testing Checklist](#testing-checklist)
8. [Rollback Plan](#rollback-plan)

---

## 🎯 Executive Summary

### **Problem Statement**
Currently, warehouse-to-warehouse transfers and warehouse-to-storefront transfers are handled by different systems:
- **Warehouse → Warehouse**: Uses `StockAdjustment` with `TRANSFER_IN`/`TRANSFER_OUT` types
- **Warehouse → Storefront**: Uses `TransferRequest` model with manual fulfillment

This creates:
- ❌ Confusion for users (two different workflows)
- ❌ Incomplete reporting (movements scattered across different models)
- ❌ Data integrity risks (no atomic transfer operations)
- ❌ Difficult to audit transfer history

### **Proposed Solution**
Implement a **Unified Transfer System** with:
- ✅ Single `Transfer` model for both transfer types
- ✅ Clear type differentiation via `transfer_type` field
- ✅ Atomic transactions ensuring data integrity
- ✅ Unified movement tracking for reports
- ✅ Role-based permissions
- ✅ Backward compatibility during transition

### **Timeline**
- **Total Duration**: 6 weeks
- **Phases**: 6 distinct phases
- **Frontend Impact**: Medium (API changes, new endpoints)
- **Backend Changes**: Significant (new models, services, reports update)

---

## 📊 Current State Analysis

### **Existing Systems**

#### **System 1: StockAdjustment (Warehouse ↔ Warehouse)**
```python
# Current Implementation
StockAdjustment.objects.create(
    stock_product=source_stock,
    adjustment_type='TRANSFER_OUT',
    quantity=-10,
    reference_number='TRF-001',
    ...
)

StockAdjustment.objects.create(
    stock_product=dest_stock,
    adjustment_type='TRANSFER_IN',
    quantity=10,
    reference_number='TRF-001',
    ...
)
```

**Issues:**
- ❌ Two separate records for one logical transfer
- ❌ No FK relationship between OUT and IN
- ❌ If one fails, the other might succeed (data inconsistency)
- ❌ Hard to query "all transfers" - need to filter by type

#### **System 2: TransferRequest (Warehouse → Storefront)**
```python
# Current Implementation
transfer_request = TransferRequest.objects.create(
    business=business,
    storefront=storefront,
    requested_by=user,
    status='NEW',
)

# Manual fulfillment
transfer_request.apply_manual_inventory_fulfillment()
transfer_request.status = 'FULFILLED'
transfer_request.save()
```

**Issues:**
- ❌ Completely separate from warehouse transfers
- ❌ No unified "transfer history" view
- ❌ Different API endpoints for similar operations

### **Reports Currently Affected**

| Report | Current Data Source | Impact Level |
|--------|-------------------|--------------|
| Stock Movement History | `StockAdjustment` + `SaleItem` | 🔴 **HIGH** |
| Warehouse Analytics | `StockProduct` + `SaleItem` | 🟡 **MEDIUM** |
| Low Stock Alerts | `StockProduct` | ✅ **NONE** |
| Stock Levels Summary | `StockProduct` | ✅ **NONE** |

**Critical Finding:**
Stock Movement History report (`/reports/api/inventory/movements/`) will **NOT** show warehouse transfers if we remove `TRANSFER_IN`/`TRANSFER_OUT` from `StockAdjustment` without updating the report logic.

---

## 🚀 Implementation Phases

### **PHASE 1: Foundation & Abstraction Layer** (Week 1)

#### **Goal**
Create infrastructure without breaking existing functionality.

#### **Tasks**

##### **1.1 Create Movement Tracker Service**

**File**: `reports/services/movement_tracker.py` (NEW)

```python
"""
Unified Movement Tracking Service

Provides a single interface for all stock movements across the system.
This ensures reports and analytics have consistent data.

Usage:
    from reports.services.movement_tracker import MovementTracker
    
    movements = MovementTracker.get_movements(
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        warehouse_id='uuid-here',
    )
"""

from typing import List, Dict, Any, Optional
from datetime import date, datetime
from decimal import Decimal
from django.db.models import Q

from inventory.models import Product, StockProduct, Warehouse
from inventory.stock_adjustments import StockAdjustment
from sales.models import SaleItem


class MovementType:
    """Constants for movement types"""
    SALE = 'sale'
    ADJUSTMENT = 'adjustment'
    TRANSFER = 'transfer'
    TRANSFER_REQUEST = 'transfer_request'


class MovementTracker:
    """
    Unified interface for tracking all stock movements.
    
    Aggregates movements from multiple sources:
    - StockAdjustments (excluding transfers)
    - Transfers (warehouse-to-warehouse)
    - TransferRequests (warehouse-to-storefront)
    - Sales
    """
    
    @staticmethod
    def get_movements(
        start_date: date,
        end_date: date,
        warehouse_id: Optional[str] = None,
        product_id: Optional[str] = None,
        movement_type: Optional[str] = None,
        business_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all movements for a date range with optional filters.
        
        Args:
            start_date: Start of date range
            end_date: End of date range
            warehouse_id: Filter by warehouse (optional)
            product_id: Filter by product (optional)
            movement_type: Filter by movement type (optional)
            business_id: Filter by business (required for multi-tenant)
        
        Returns:
            List of movement dictionaries with standardized structure:
            {
                'movement_id': str,
                'movement_type': str,  # sale|adjustment|transfer
                'movement_subtype': str,  # THEFT|DAMAGE|... or null
                'product_id': str,
                'product_name': str,
                'warehouse_id': str,
                'warehouse_name': str,
                'quantity': int,  # Negative for outbound
                'quantity_before': int,
                'quantity_after': int,
                'unit_cost': Decimal,
                'total_value': Decimal,
                'reference_type': str,
                'reference_id': str,
                'reference_number': str,
                'performed_by': str,
                'performed_by_id': str,
                'created_at': datetime,
                'notes': str,
            }
        """
        movements = []
        
        # Get adjustments (excluding transfers for now)
        if movement_type in [None, MovementType.ADJUSTMENT]:
            movements.extend(
                MovementTracker._get_adjustment_movements(
                    start_date, end_date, warehouse_id, product_id, business_id
                )
            )
        
        # Get transfers (NEW - will be implemented in Phase 2)
        if movement_type in [None, MovementType.TRANSFER]:
            movements.extend(
                MovementTracker._get_transfer_movements(
                    start_date, end_date, warehouse_id, product_id, business_id
                )
            )
        
        # Get sales
        if movement_type in [None, MovementType.SALE]:
            movements.extend(
                MovementTracker._get_sale_movements(
                    start_date, end_date, warehouse_id, product_id, business_id
                )
            )
        
        # Sort by date descending
        movements.sort(key=lambda x: x['created_at'], reverse=True)
        
        return movements
    
    @staticmethod
    def _get_adjustment_movements(
        start_date, end_date, warehouse_id, product_id, business_id
    ) -> List[Dict]:
        """Get movements from StockAdjustment (excluding transfers)"""
        movements = []
        
        qs = StockAdjustment.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            status='COMPLETED'
        ).exclude(
            # Exclude transfers - they'll be tracked separately
            adjustment_type__in=['TRANSFER_IN', 'TRANSFER_OUT']
        ).select_related(
            'stock_product__product',
            'stock_product__warehouse',
            'created_by'
        )
        
        if business_id:
            qs = qs.filter(business_id=business_id)
        if warehouse_id:
            qs = qs.filter(stock_product__warehouse_id=warehouse_id)
        if product_id:
            qs = qs.filter(stock_product__product_id=product_id)
        
        for adj in qs:
            sp = adj.stock_product
            movements.append({
                'movement_id': str(adj.id),
                'movement_type': MovementType.ADJUSTMENT,
                'movement_subtype': adj.adjustment_type,
                'product_id': str(sp.product.id),
                'product_name': sp.product.name,
                'product_sku': sp.product.sku,
                'warehouse_id': str(sp.warehouse.id) if sp.warehouse else None,
                'warehouse_name': sp.warehouse.name if sp.warehouse else None,
                'quantity': adj.quantity,
                'quantity_before': adj.quantity_before,
                'quantity_after': adj.quantity_after,
                'unit_cost': adj.unit_cost,
                'total_value': adj.total_cost,
                'reference_type': 'adjustment',
                'reference_id': str(adj.id),
                'reference_number': adj.reference_number or f'ADJ-{adj.id}',
                'performed_by': adj.created_by.name if adj.created_by else None,
                'performed_by_id': str(adj.created_by.id) if adj.created_by else None,
                'created_at': adj.created_at,
                'notes': adj.notes,
            })
        
        return movements
    
    @staticmethod
    def _get_transfer_movements(
        start_date, end_date, warehouse_id, product_id, business_id
    ) -> List[Dict]:
        """
        Get movements from Transfer model (NEW - Phase 2).
        
        For now, this still uses StockAdjustment TRANSFER types.
        Will be updated in Phase 2 when Transfer model is created.
        """
        movements = []
        
        # Temporarily use StockAdjustment transfers
        qs = StockAdjustment.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lte=end_date,
            status='COMPLETED',
            adjustment_type__in=['TRANSFER_IN', 'TRANSFER_OUT']
        ).select_related(
            'stock_product__product',
            'stock_product__warehouse',
            'created_by'
        )
        
        if business_id:
            qs = qs.filter(business_id=business_id)
        if warehouse_id:
            qs = qs.filter(stock_product__warehouse_id=warehouse_id)
        if product_id:
            qs = qs.filter(stock_product__product_id=product_id)
        
        for adj in qs:
            sp = adj.stock_product
            movements.append({
                'movement_id': str(adj.id),
                'movement_type': MovementType.TRANSFER,
                'movement_subtype': adj.adjustment_type,
                'product_id': str(sp.product.id),
                'product_name': sp.product.name,
                'product_sku': sp.product.sku,
                'warehouse_id': str(sp.warehouse.id) if sp.warehouse else None,
                'warehouse_name': sp.warehouse.name if sp.warehouse else None,
                'quantity': adj.quantity,
                'quantity_before': adj.quantity_before,
                'quantity_after': adj.quantity_after,
                'unit_cost': adj.unit_cost,
                'total_value': adj.total_cost,
                'reference_type': 'transfer',
                'reference_id': str(adj.id),
                'reference_number': adj.reference_number or f'TRF-{adj.id}',
                'performed_by': adj.created_by.name if adj.created_by else None,
                'performed_by_id': str(adj.created_by.id) if adj.created_by else None,
                'created_at': adj.created_at,
                'notes': adj.notes,
            })
        
        return movements
    
    @staticmethod
    def _get_sale_movements(
        start_date, end_date, warehouse_id, product_id, business_id
    ) -> List[Dict]:
        """Get movements from sales"""
        movements = []
        
        qs = SaleItem.objects.filter(
            sale__created_at__date__gte=start_date,
            sale__created_at__date__lte=end_date,
            sale__status__in=['COMPLETED', 'PARTIAL']
        ).select_related(
            'product',
            'product__category',
            'sale',
            'sale__user',
            'stock_product__warehouse'
        )
        
        if product_id:
            qs = qs.filter(product_id=product_id)
        # Note: Sales don't directly filter by warehouse in current schema
        
        for item in qs:
            movements.append({
                'movement_id': str(item.id),
                'movement_type': MovementType.SALE,
                'movement_subtype': None,
                'product_id': str(item.product.id),
                'product_name': item.product.name,
                'product_sku': item.product.sku,
                'warehouse_id': str(item.stock_product.warehouse.id) if item.stock_product and item.stock_product.warehouse else None,
                'warehouse_name': item.stock_product.warehouse.name if item.stock_product and item.stock_product.warehouse else None,
                'quantity': -item.quantity,  # Negative for outbound
                'quantity_before': None,
                'quantity_after': None,
                'unit_cost': item.stock_product.unit_cost if item.stock_product else None,
                'total_value': item.total_price,
                'reference_type': 'sale',
                'reference_id': str(item.sale.id),
                'reference_number': item.sale.receipt_number or f'SALE-{item.sale.id}',
                'performed_by': item.sale.user.name if item.sale.user else None,
                'performed_by_id': str(item.sale.user.id) if item.sale.user else None,
                'created_at': item.sale.created_at,
                'notes': None,
            })
        
        return movements
    
    @staticmethod
    def get_summary(movements: List[Dict]) -> Dict[str, Any]:
        """
        Calculate summary statistics from movements.
        
        Args:
            movements: List of movements from get_movements()
        
        Returns:
            Summary dictionary with totals and breakdowns
        """
        total_in = sum(m['quantity'] for m in movements if m['quantity'] > 0)
        total_out = abs(sum(m['quantity'] for m in movements if m['quantity'] < 0))
        
        # Calculate shrinkage
        shrinkage_types = ['THEFT', 'DAMAGE', 'EXPIRED', 'SPOILAGE', 'LOSS', 'WRITE_OFF']
        shrinkage_movements = [
            m for m in movements 
            if m['movement_type'] == MovementType.ADJUSTMENT 
            and m['movement_subtype'] in shrinkage_types
        ]
        
        shrinkage_units = abs(sum(m['quantity'] for m in shrinkage_movements))
        shrinkage_value = sum(
            abs(m['total_value']) for m in shrinkage_movements 
            if m['total_value']
        )
        
        # Movement type breakdown
        by_type = {}
        for m in movements:
            key = m['movement_subtype'] or m['movement_type']
            if key not in by_type:
                by_type[key] = {
                    'count': 0,
                    'quantity': 0,
                    'value': Decimal('0.00')
                }
            by_type[key]['count'] += 1
            by_type[key]['quantity'] += m['quantity']
            if m['total_value']:
                by_type[key]['value'] += m['total_value']
        
        return {
            'total_movements': len(movements),
            'total_units_in': total_in,
            'total_units_out': total_out,
            'net_change': total_in - total_out,
            'shrinkage': {
                'units': shrinkage_units,
                'value': str(shrinkage_value),
                'percentage_of_outbound': round(
                    (shrinkage_units / total_out * 100) if total_out > 0 else 0,
                    2
                )
            },
            'by_type': {
                k: {
                    'count': v['count'],
                    'quantity': v['quantity'],
                    'value': str(v['value'])
                }
                for k, v in by_type.items()
            }
        }
```

##### **1.2 Create Constants File**

**File**: `inventory/constants.py` (NEW)

```python
"""
Inventory Module Constants

Centralized constants for inventory management.
"""


class TransferType:
    """Types of inventory transfers"""
    WAREHOUSE_TO_WAREHOUSE = 'warehouse_to_warehouse'
    WAREHOUSE_TO_STOREFRONT = 'warehouse_to_storefront'
    
    CHOICES = [
        (WAREHOUSE_TO_WAREHOUSE, 'Warehouse to Warehouse'),
        (WAREHOUSE_TO_STOREFRONT, 'Warehouse to Storefront'),
    ]


class TransferStatus:
    """Status workflow for transfers"""
    PENDING = 'pending'
    IN_TRANSIT = 'in_transit'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'
    
    CHOICES = [
        (PENDING, 'Pending'),
        (IN_TRANSIT, 'In Transit'),
        (COMPLETED, 'Completed'),
        (CANCELLED, 'Cancelled'),
    ]


class AdjustmentType:
    """Stock adjustment types (non-transfer)"""
    # Shrinkage (negative)
    THEFT = 'THEFT'
    DAMAGE = 'DAMAGE'
    EXPIRED = 'EXPIRED'
    SPOILAGE = 'SPOILAGE'
    LOSS = 'LOSS'
    WRITE_OFF = 'WRITE_OFF'
    SAMPLE = 'SAMPLE'
    SUPPLIER_RETURN = 'SUPPLIER_RETURN'
    
    # Positive
    CUSTOMER_RETURN = 'CUSTOMER_RETURN'
    FOUND = 'FOUND'
    CORRECTION_INCREASE = 'CORRECTION_INCREASE'
    
    # Either
    CORRECTION = 'CORRECTION'
    RECOUNT = 'RECOUNT'
    OTHER = 'OTHER'
    
    # Legacy (will be deprecated)
    TRANSFER_OUT = 'TRANSFER_OUT'
    TRANSFER_IN = 'TRANSFER_IN'
    
    SHRINKAGE_TYPES = [
        THEFT, DAMAGE, EXPIRED, SPOILAGE, LOSS, WRITE_OFF
    ]
```

#### **Deliverables**
- ✅ MovementTracker service created
- ✅ Constants file created
- ✅ No existing functionality broken
- ✅ Ready for Phase 2 integration

---

### **PHASE 2: Transfer Model Implementation** (Week 2)

#### **Goal**
Create new Transfer model with proper relationships and validation.

#### **Tasks**

##### **2.1 Create Transfer Models**

**File**: `inventory/transfer_models.py` (NEW)

```python
"""
Transfer Models

Unified transfer system for warehouse-to-warehouse and warehouse-to-storefront transfers.
Replaces the dual-write StockAdjustment approach for better data integrity.
"""

import uuid
from decimal import Decimal
from django.db import models, transaction
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import Business
from inventory.models import Warehouse, StoreFront, Product, Batch, StockProduct
from inventory.constants import TransferType, TransferStatus


User = get_user_model()


class Transfer(models.Model):
    """
    Unified transfer model for all inventory transfers.
    
    Supports:
    - Warehouse to Warehouse transfers
    - Warehouse to Storefront transfers (replaces TransferRequest fulfillment)
    
    Ensures atomicity: either both source and destination update, or neither.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name='transfers'
    )
    
    # Transfer type
    transfer_type = models.CharField(
        max_length=50,
        choices=TransferType.CHOICES,
        help_text='Type of transfer: warehouse-to-warehouse or warehouse-to-storefront'
    )
    
    # Source (always a warehouse)
    source_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name='outbound_transfers'
    )
    
    # Destination (either warehouse OR storefront, never both)
    destination_warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.PROTECT,
        related_name='inbound_transfers',
        null=True,
        blank=True,
        help_text='Destination warehouse for warehouse-to-warehouse transfers'
    )
    
    destination_storefront = models.ForeignKey(
        StoreFront,
        on_delete=models.PROTECT,
        related_name='inventory_transfers',
        null=True,
        blank=True,
        help_text='Destination storefront for warehouse-to-storefront transfers'
    )
    
    # Status workflow
    status = models.CharField(
        max_length=20,
        choices=TransferStatus.CHOICES,
        default=TransferStatus.PENDING
    )
    
    # Reference
    reference_number = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text='Unique reference number for this transfer (e.g., TRF-001)'
    )
    
    # Dates
    transfer_date = models.DateTimeField(
        default=timezone.now,
        help_text='Date when transfer was initiated'
    )
    received_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Date when destination confirmed receipt'
    )
    
    # Audit
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_transfers'
    )
    received_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='received_transfers'
    )
    
    # Notes
    notes = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'inventory_transfers'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['business', 'status']),
            models.Index(fields=['transfer_type', 'status']),
            models.Index(fields=['source_warehouse', 'status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.reference_number} - {self.get_transfer_type_display()}"
    
    def clean(self):
        """Validate transfer business rules"""
        super().clean()
        
        # Rule 1: Must have exactly one destination
        has_warehouse = self.destination_warehouse is not None
        has_storefront = self.destination_storefront is not None
        
        if not has_warehouse and not has_storefront:
            raise ValidationError(
                'Transfer must have either a destination warehouse or storefront.'
            )
        
        if has_warehouse and has_storefront:
            raise ValidationError(
                'Transfer cannot have both warehouse and storefront as destination.'
            )
        
        # Rule 2: Validate type matches destination
        if self.transfer_type == TransferType.WAREHOUSE_TO_WAREHOUSE:
            if not has_warehouse:
                raise ValidationError({
                    'destination_warehouse': 'Warehouse-to-warehouse transfer must have destination warehouse.'
                })
            if has_storefront:
                raise ValidationError({
                    'destination_storefront': 'Warehouse-to-warehouse transfer cannot have storefront destination.'
                })
            # Prevent self-transfer
            if self.source_warehouse == self.destination_warehouse:
                raise ValidationError(
                    'Source and destination warehouse cannot be the same.'
                )
        
        elif self.transfer_type == TransferType.WAREHOUSE_TO_STOREFRONT:
            if not has_storefront:
                raise ValidationError({
                    'destination_storefront': 'Warehouse-to-storefront transfer must have destination storefront.'
                })
            if has_warehouse:
                raise ValidationError({
                    'destination_warehouse': 'Warehouse-to-storefront transfer cannot have warehouse destination.'
                })
    
    def save(self, *args, **kwargs):
        """Validate before saving"""
        self.clean()
        super().save(*args, **kwargs)
    
    @transaction.atomic
    def complete_transfer(self, received_by_user=None):
        """
        Complete the transfer by updating stock levels at both source and destination.
        
        This is an atomic operation - either both succeed or both fail.
        
        Args:
            received_by_user: User confirming receipt (optional)
        
        Raises:
            ValidationError: If transfer cannot be completed (e.g., insufficient stock)
        """
        if self.status == TransferStatus.COMPLETED:
            raise ValidationError('Transfer is already completed.')
        
        if self.status == TransferStatus.CANCELLED:
            raise ValidationError('Cannot complete a cancelled transfer.')
        
        # Process each item
        for item in self.items.all():
            item.apply_to_inventory()
        
        # Update transfer status
        self.status = TransferStatus.COMPLETED
        self.received_date = timezone.now()
        if received_by_user:
            self.received_by = received_by_user
        self.save(update_fields=['status', 'received_date', 'received_by', 'updated_at'])
    
    @transaction.atomic
    def cancel_transfer(self, user=None, reason=''):
        """
        Cancel the transfer.
        
        If already completed, this will reverse the inventory changes.
        
        Args:
            user: User cancelling the transfer
            reason: Reason for cancellation
        """
        if self.status == TransferStatus.CANCELLED:
            raise ValidationError('Transfer is already cancelled.')
        
        # If completed, reverse inventory changes
        if self.status == TransferStatus.COMPLETED:
            for item in self.items.all():
                item.reverse_inventory_changes()
        
        # Update status
        self.status = TransferStatus.CANCELLED
        if reason:
            self.notes = f"{self.notes}\n\nCANCELLED: {reason}" if self.notes else f"CANCELLED: {reason}"
        self.save(update_fields=['status', 'notes', 'updated_at'])


class TransferItem(models.Model):
    """
    Individual items within a transfer.
    
    Tracks what products/batches are being transferred and in what quantity.
    """
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    transfer = models.ForeignKey(
        Transfer,
        on_delete=models.CASCADE,
        related_name='items'
    )
    
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='transfer_items'
    )
    
    batch = models.ForeignKey(
        Batch,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='transfer_items',
        help_text='Specific batch being transferred (optional for now)'
    )
    
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text='Number of units to transfer'
    )
    
    # Snapshot of values at transfer time
    unit_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text='Unit cost at time of transfer (for valuation)'
    )
    
    # Track actual received quantity (may differ from requested)
    received_quantity = models.PositiveIntegerField(
        default=0,
        help_text='Actual quantity received (0 until confirmed)'
    )
    
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'inventory_transfer_items'
        unique_together = ['transfer', 'product', 'batch']
    
    def __str__(self):
        return f"{self.product.name} x{self.quantity} ({self.transfer.reference_number})"
    
    @property
    def total_cost(self):
        """Calculate total cost of this line item"""
        return self.unit_cost * self.quantity
    
    @transaction.atomic
    def apply_to_inventory(self):
        """
        Apply this transfer item to inventory.
        
        For warehouse-to-warehouse:
          - Decrease source warehouse stock
          - Increase destination warehouse stock
        
        For warehouse-to-storefront:
          - Decrease source warehouse stock
          - Increase destination storefront inventory
        """
        transfer = self.transfer
        
        # Get source stock product
        source_stock = StockProduct.objects.select_for_update().filter(
            warehouse=transfer.source_warehouse,
            product=self.product
        ).first()
        
        if not source_stock:
            raise ValidationError(
                f'Product {self.product.name} not found in source warehouse {transfer.source_warehouse.name}'
            )
        
        if source_stock.quantity < self.quantity:
            raise ValidationError(
                f'Insufficient stock for {self.product.name}. '
                f'Available: {source_stock.quantity}, Requested: {self.quantity}'
            )
        
        # Decrease source
        source_stock.quantity -= self.quantity
        source_stock.save(update_fields=['quantity', 'updated_at'])
        
        # Increase destination
        if transfer.transfer_type == TransferType.WAREHOUSE_TO_WAREHOUSE:
            # Warehouse destination
            dest_stock, created = StockProduct.objects.select_for_update().get_or_create(
                warehouse=transfer.destination_warehouse,
                product=self.product,
                defaults={
                    'stock': source_stock.stock,
                    'quantity': 0,
                    'unit_cost': self.unit_cost,
                    'retail_price': source_stock.retail_price,
                    'wholesale_price': source_stock.wholesale_price,
                }
            )
            dest_stock.quantity += self.quantity
            dest_stock.save(update_fields=['quantity', 'updated_at'])
        
        else:  # WAREHOUSE_TO_STOREFRONT
            # Storefront destination
            from inventory.models import StoreFrontInventory
            
            dest_inv, created = StoreFrontInventory.objects.select_for_update().get_or_create(
                storefront=transfer.destination_storefront,
                product=self.product,
                defaults={'quantity': 0}
            )
            dest_inv.quantity += self.quantity
            dest_inv.save(update_fields=['quantity', 'updated_at'])
        
        # Update received quantity
        self.received_quantity = self.quantity
        self.save(update_fields=['received_quantity'])
    
    @transaction.atomic
    def reverse_inventory_changes(self):
        """Reverse inventory changes for cancellation"""
        transfer = self.transfer
        
        if self.received_quantity == 0:
            return  # Nothing to reverse
        
        # Reverse source (add back)
        source_stock = StockProduct.objects.select_for_update().filter(
            warehouse=transfer.source_warehouse,
            product=self.product
        ).first()
        
        if source_stock:
            source_stock.quantity += self.received_quantity
            source_stock.save(update_fields=['quantity', 'updated_at'])
        
        # Reverse destination (subtract)
        if transfer.transfer_type == TransferType.WAREHOUSE_TO_WAREHOUSE:
            dest_stock = StockProduct.objects.select_for_update().filter(
                warehouse=transfer.destination_warehouse,
                product=self.product
            ).first()
            if dest_stock:
                dest_stock.quantity = max(0, dest_stock.quantity - self.received_quantity)
                dest_stock.save(update_fields=['quantity', 'updated_at'])
        else:
            from inventory.models import StoreFrontInventory
            dest_inv = StoreFrontInventory.objects.select_for_update().filter(
                storefront=transfer.destination_storefront,
                product=self.product
            ).first()
            if dest_inv:
                dest_inv.quantity = max(0, dest_inv.quantity - self.received_quantity)
                dest_inv.save(update_fields=['quantity', 'updated_at'])
        
        # Reset received quantity
        self.received_quantity = 0
        self.save(update_fields=['received_quantity'])
```

##### **2.2 Create Migration**

**File**: `inventory/migrations/0019_create_transfer_models.py` (AUTO-GENERATED)

```bash
python manage.py makemigrations inventory
```

##### **2.3 Update Movement Tracker to Use Transfer Model**

Update `reports/services/movement_tracker.py`:

```python
# In _get_transfer_movements method, replace with:

@staticmethod
def _get_transfer_movements(
    start_date, end_date, warehouse_id, product_id, business_id
) -> List[Dict]:
    """Get movements from Transfer model"""
    from inventory.transfer_models import Transfer, TransferItem
    
    movements = []
    
    # Query transfers
    qs = Transfer.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
        status='completed'
    ).prefetch_related(
        'items__product',
        'items__product__category'
    )
    
    if business_id:
        qs = qs.filter(business_id=business_id)
    
    # Filter by warehouse (either source or destination)
    if warehouse_id:
        qs = qs.filter(
            Q(source_warehouse_id=warehouse_id) |
            Q(destination_warehouse_id=warehouse_id)
        )
    
    if product_id:
        qs = qs.filter(items__product_id=product_id).distinct()
    
    # Convert to movements
    for transfer in qs:
        for item in transfer.items.all():
            # Create outbound movement (source)
            if not warehouse_id or str(transfer.source_warehouse_id) == warehouse_id:
                movements.append({
                    'movement_id': f'{transfer.id}-out-{item.id}',
                    'movement_type': MovementType.TRANSFER,
                    'movement_subtype': transfer.transfer_type,
                    'product_id': str(item.product.id),
                    'product_name': item.product.name,
                    'product_sku': item.product.sku,
                    'warehouse_id': str(transfer.source_warehouse.id),
                    'warehouse_name': transfer.source_warehouse.name,
                    'quantity': -item.quantity,  # Negative for outbound
                    'quantity_before': None,
                    'quantity_after': None,
                    'unit_cost': item.unit_cost,
                    'total_value': -item.total_cost,
                    'reference_type': 'transfer',
                    'reference_id': str(transfer.id),
                    'reference_number': transfer.reference_number,
                    'performed_by': transfer.created_by.name if transfer.created_by else None,
                    'performed_by_id': str(transfer.created_by.id) if transfer.created_by else None,
                    'created_at': transfer.created_at,
                    'notes': f"{transfer.notes} [OUTBOUND]",
                    'destination': (
                        transfer.destination_warehouse.name 
                        if transfer.destination_warehouse 
                        else transfer.destination_storefront.name
                    )
                })
            
            # Create inbound movement (destination)
            dest_warehouse_id = (
                str(transfer.destination_warehouse.id) 
                if transfer.destination_warehouse 
                else None
            )
            
            if not warehouse_id or warehouse_id == dest_warehouse_id:
                movements.append({
                    'movement_id': f'{transfer.id}-in-{item.id}',
                    'movement_type': MovementType.TRANSFER,
                    'movement_subtype': transfer.transfer_type,
                    'product_id': str(item.product.id),
                    'product_name': item.product.name,
                    'product_sku': item.product.sku,
                    'warehouse_id': dest_warehouse_id,
                    'warehouse_name': (
                        transfer.destination_warehouse.name 
                        if transfer.destination_warehouse 
                        else None
                    ),
                    'quantity': item.quantity,  # Positive for inbound
                    'quantity_before': None,
                    'quantity_after': None,
                    'unit_cost': item.unit_cost,
                    'total_value': item.total_cost,
                    'reference_type': 'transfer',
                    'reference_id': str(transfer.id),
                    'reference_number': transfer.reference_number,
                    'performed_by': transfer.received_by.name if transfer.received_by else transfer.created_by.name if transfer.created_by else None,
                    'performed_by_id': str(transfer.received_by.id) if transfer.received_by else str(transfer.created_by.id) if transfer.created_by else None,
                    'created_at': transfer.received_date or transfer.created_at,
                    'notes': f"{transfer.notes} [INBOUND]",
                    'source': transfer.source_warehouse.name
                })
    
    return movements
```

#### **Deliverables**
- ✅ Transfer and TransferItem models created
- ✅ Database migration applied
- ✅ MovementTracker updated to use new model
- ✅ Backward compatibility maintained (old StockAdjustment transfers still work)

---

### **PHASE 3: Report Integration** (Week 3)

#### **Goal**
Update all reports to use unified MovementTracker.

#### **Tasks**

##### **3.1 Update Stock Movement History Report**

**File**: `reports/views/inventory_reports.py`

```python
# Replace the _build_summary, _build_time_series, _build_movements methods
# with calls to MovementTracker

from reports.services.movement_tracker import MovementTracker

class StockMovementHistoryReportView(BaseReportView):
    
    def get(self, request):
        """Generate stock movement history report"""
        # ... existing parameter parsing ...
        
        # NEW: Use MovementTracker
        movements = MovementTracker.get_movements(
            start_date=start_date,
            end_date=end_date,
            warehouse_id=warehouse_id,
            product_id=product_id,
            movement_type=movement_type,
            business_id=business_id,
        )
        
        # Get summary
        summary = MovementTracker.get_summary(movements)
        
        # Build time series (existing logic)
        time_series = self._build_time_series_from_movements(
            movements, grouping
        )
        
        # Apply pagination, search, filters
        filtered_movements = self._filter_movements(
            movements, search_term, category_id, sort_by
        )
        paginated, pagination = self._paginate_movements(
            filtered_movements, request
        )
        
        # Return response
        # ...
```

##### **3.2 Update Warehouse Analytics Report**

Update to consider transfers as "activity" for dead stock calculations.

##### **3.3 Add Transfer History Endpoint**

**File**: `reports/urls.py`

```python
path('api/inventory/transfer-history/', TransferHistoryReportView.as_view(), name='transfer-history-report'),
```

**File**: `reports/views/inventory_reports.py`

```python
class TransferHistoryReportView(BaseReportView):
    """
    Dedicated endpoint for transfer history.
    
    GET /reports/api/inventory/transfer-history/
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get transfer history with analytics"""
        # ... implementation ...
```

#### **Deliverables**
- ✅ All reports updated to use MovementTracker
- ✅ No data loss or inconsistencies
- ✅ New transfer history endpoint created
- ✅ Tests updated

---

### **PHASE 4: API Endpoints & Serializers** (Week 4)

#### **Goal**
Create frontend-friendly API endpoints with comprehensive documentation.

#### **Tasks**

##### **4.1 Create Transfer Serializers**

**File**: `inventory/transfer_serializers.py` (NEW)

```python
"""
Transfer Serializers

Handles serialization/deserialization for Transfer and TransferItem models.
"""

from rest_framework import serializers
from django.db import transaction

from inventory.transfer_models import Transfer, TransferItem
from inventory.models import Warehouse, StoreFront, Product, StockProduct
from inventory.constants import TransferType, TransferStatus


class TransferItemSerializer(serializers.ModelSerializer):
    """Serializer for individual transfer items"""
    
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_sku = serializers.CharField(source='product.sku', read_only=True)
    total_cost = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True
    )
    
    class Meta:
        model = TransferItem
        fields = [
            'id',
            'product',
            'product_name',
            'product_sku',
            'batch',
            'quantity',
            'received_quantity',
            'unit_cost',
            'total_cost',
            'notes',
        ]
        read_only_fields = ['id', 'received_quantity', 'total_cost']
    
    def validate(self, data):
        """Validate transfer item"""
        product = data.get('product')
        quantity = data.get('quantity')
        
        # Get transfer from context (set by parent serializer)
        transfer = self.context.get('transfer')
        
        if transfer and transfer.source_warehouse:
            # Check if product exists in source warehouse
            source_stock = StockProduct.objects.filter(
                warehouse=transfer.source_warehouse,
                product=product
            ).first()
            
            if not source_stock:
                raise serializers.ValidationError(
                    f'Product {product.name} not found in source warehouse.'
                )
            
            if source_stock.quantity < quantity:
                raise serializers.ValidationError(
                    f'Insufficient stock. Available: {source_stock.quantity}, '
                    f'Requested: {quantity}'
                )
            
            # Auto-set unit_cost if not provided
            if 'unit_cost' not in data:
                data['unit_cost'] = source_stock.landed_unit_cost
        
        return data


class TransferSerializer(serializers.ModelSerializer):
    """Serializer for Transfer model"""
    
    items = TransferItemSerializer(many=True)
    
    # Read-only fields for display
    source_warehouse_name = serializers.CharField(
        source='source_warehouse.name',
        read_only=True
    )
    destination_warehouse_name = serializers.CharField(
        source='destination_warehouse.name',
        read_only=True,
        allow_null=True
    )
    destination_storefront_name = serializers.CharField(
        source='destination_storefront.name',
        read_only=True,
        allow_null=True
    )
    created_by_name = serializers.CharField(
        source='created_by.name',
        read_only=True
    )
    received_by_name = serializers.CharField(
        source='received_by.name',
        read_only=True,
        allow_null=True
    )
    
    # Computed fields
    total_items = serializers.SerializerMethodField()
    total_quantity = serializers.SerializerMethodField()
    total_value = serializers.SerializerMethodField()
    
    class Meta:
        model = Transfer
        fields = [
            'id',
            'business',
            'transfer_type',
            'source_warehouse',
            'source_warehouse_name',
            'destination_warehouse',
            'destination_warehouse_name',
            'destination_storefront',
            'destination_storefront_name',
            'status',
            'reference_number',
            'transfer_date',
            'received_date',
            'created_by',
            'created_by_name',
            'received_by',
            'received_by_name',
            'notes',
            'items',
            'total_items',
            'total_quantity',
            'total_value',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'business',
            'status',
            'received_date',
            'received_by',
            'created_at',
            'updated_at',
        ]
    
    def get_total_items(self, obj):
        """Total number of line items"""
        return obj.items.count()
    
    def get_total_quantity(self, obj):
        """Total units across all items"""
        return sum(item.quantity for item in obj.items.all())
    
    def get_total_value(self, obj):
        """Total value of transfer"""
        return sum(item.total_cost for item in obj.items.all())
    
    def validate(self, data):
        """Validate transfer data"""
        transfer_type = data.get('transfer_type')
        dest_warehouse = data.get('destination_warehouse')
        dest_storefront = data.get('destination_storefront')
        source_warehouse = data.get('source_warehouse')
        
        # Validate destination based on type
        if transfer_type == TransferType.WAREHOUSE_TO_WAREHOUSE:
            if not dest_warehouse:
                raise serializers.ValidationError({
                    'destination_warehouse': 'Required for warehouse-to-warehouse transfers.'
                })
            if dest_storefront:
                raise serializers.ValidationError({
                    'destination_storefront': 'Should not be set for warehouse-to-warehouse transfers.'
                })
            if source_warehouse == dest_warehouse:
                raise serializers.ValidationError(
                    'Source and destination warehouse cannot be the same.'
                )
        
        elif transfer_type == TransferType.WAREHOUSE_TO_STOREFRONT:
            if not dest_storefront:
                raise serializers.ValidationError({
                    'destination_storefront': 'Required for warehouse-to-storefront transfers.'
                })
            if dest_warehouse:
                raise serializers.ValidationError({
                    'destination_warehouse': 'Should not be set for warehouse-to-storefront transfers.'
                })
        
        return data
    
    @transaction.atomic
    def create(self, validated_data):
        """Create transfer with items"""
        items_data = validated_data.pop('items')
        
        # Get business from source warehouse
        source_warehouse = validated_data['source_warehouse']
        business_link = source_warehouse.business_link
        if not business_link:
            raise serializers.ValidationError(
                'Source warehouse must be linked to a business.'
            )
        
        validated_data['business'] = business_link.business
        
        # Generate reference number if not provided
        if 'reference_number' not in validated_data:
            from django.utils import timezone
            timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
            validated_data['reference_number'] = f'TRF-{timestamp}'
        
        # Set creator
        request = self.context.get('request')
        if request and request.user:
            validated_data['created_by'] = request.user
        
        # Create transfer
        transfer = Transfer.objects.create(**validated_data)
        
        # Create items
        for item_data in items_data:
            TransferItem.objects.create(
                transfer=transfer,
                **item_data
            )
        
        return transfer
    
    @transaction.atomic
    def update(self, instance, validated_data):
        """Update transfer"""
        items_data = validated_data.pop('items', None)
        
        # Update transfer fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update items if provided
        if items_data is not None:
            # Delete existing items
            instance.items.all().delete()
            
            # Create new items
            for item_data in items_data:
                TransferItem.objects.create(
                    transfer=instance,
                    **item_data
                )
        
        return instance


class TransferListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for transfer lists"""
    
    source_warehouse_name = serializers.CharField(
        source='source_warehouse.name',
        read_only=True
    )
    destination_name = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(
        source='created_by.name',
        read_only=True
    )
    total_items = serializers.SerializerMethodField()
    total_quantity = serializers.SerializerMethodField()
    
    class Meta:
        model = Transfer
        fields = [
            'id',
            'reference_number',
            'transfer_type',
            'status',
            'source_warehouse_name',
            'destination_name',
            'total_items',
            'total_quantity',
            'transfer_date',
            'created_by_name',
            'created_at',
        ]
    
    def get_destination_name(self, obj):
        """Get destination name (warehouse or storefront)"""
        if obj.destination_warehouse:
            return obj.destination_warehouse.name
        elif obj.destination_storefront:
            return obj.destination_storefront.name
        return None
    
    def get_total_items(self, obj):
        return obj.items.count()
    
    def get_total_quantity(self, obj):
        return sum(item.quantity for item in obj.items.all())
```

##### **4.2 Create Transfer ViewSets**

**File**: `inventory/transfer_views.py` (NEW)

```python
"""
Transfer ViewSets

API endpoints for warehouse transfers.
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied, ValidationError
from django_filters.rest_framework import DjangoFilterBackend, FilterSet, CharFilter
from rest_framework.filters import SearchFilter, OrderingFilter

from inventory.transfer_models import Transfer, TransferItem
from inventory.transfer_serializers import (
    TransferSerializer,
    TransferListSerializer,
    TransferItemSerializer
)
from inventory.constants import TransferType, TransferStatus
from accounts.models import BusinessMembership


class TransferFilter(FilterSet):
    """Filter for Transfer queryset"""
    
    transfer_type = CharFilter(field_name='transfer_type')
    status = CharFilter(field_name='status')
    source_warehouse = CharFilter(field_name='source_warehouse_id')
    destination_warehouse = CharFilter(field_name='destination_warehouse_id')
    destination_storefront = CharFilter(field_name='destination_storefront_id')
    
    class Meta:
        model = Transfer
        fields = ['transfer_type', 'status', 'source_warehouse', 'destination_warehouse', 'destination_storefront']


class BaseTransferViewSet(viewsets.ModelViewSet):
    """Base ViewSet with common logic for transfers"""
    
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = TransferFilter
    search_fields = ['reference_number', 'notes']
    ordering_fields = ['created_at', 'transfer_date', 'status']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """Filter transfers by business membership"""
        user = self.request.user
        
        if user.is_superuser:
            return Transfer.objects.all()
        
        # Get businesses user belongs to
        memberships = BusinessMembership.objects.filter(
            user=user,
            is_active=True
        ).values_list('business_id', flat=True)
        
        if not memberships:
            return Transfer.objects.none()
        
        return Transfer.objects.filter(business_id__in=memberships)
    
    def get_serializer_class(self):
        """Use list serializer for list action"""
        if self.action == 'list':
            return TransferListSerializer
        return TransferSerializer
    
    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """
        Complete the transfer.
        
        POST /api/transfers/{id}/complete/
        
        Body (optional):
        {
            "notes": "Received in good condition"
        }
        """
        transfer = self.get_object()
        
        # Validate permissions
        if not self._can_complete_transfer(request.user, transfer):
            raise PermissionDenied('You do not have permission to complete this transfer.')
        
        # Validate status
        if transfer.status == TransferStatus.COMPLETED:
            return Response(
                {'detail': 'Transfer is already completed.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if transfer.status == TransferStatus.CANCELLED:
            return Response(
                {'detail': 'Cannot complete a cancelled transfer.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Add notes if provided
        if 'notes' in request.data:
            transfer.notes = f"{transfer.notes}\n\n{request.data['notes']}" if transfer.notes else request.data['notes']
            transfer.save(update_fields=['notes'])
        
        # Complete transfer
        try:
            transfer.complete_transfer(received_by_user=request.user)
        except ValidationError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Return updated transfer
        serializer = self.get_serializer(transfer)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """
        Cancel the transfer.
        
        POST /api/transfers/{id}/cancel/
        
        Body:
        {
            "reason": "Reason for cancellation"
        }
        """
        transfer = self.get_object()
        
        # Validate permissions
        if not self._can_cancel_transfer(request.user, transfer):
            raise PermissionDenied('You do not have permission to cancel this transfer.')
        
        reason = request.data.get('reason', '')
        
        try:
            transfer.cancel_transfer(user=request.user, reason=reason)
        except ValidationError as e:
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(transfer)
        return Response(serializer.data)
    
    def _can_complete_transfer(self, user, transfer):
        """Check if user can complete transfer"""
        if user.is_superuser:
            return True
        
        # Must be manager or admin
        membership = BusinessMembership.objects.filter(
            business=transfer.business,
            user=user,
            is_active=True
        ).first()
        
        if not membership:
            return False
        
        return membership.role in [
            BusinessMembership.OWNER,
            BusinessMembership.ADMIN,
            BusinessMembership.MANAGER
        ]
    
    def _can_cancel_transfer(self, user, transfer):
        """Check if user can cancel transfer"""
        # Same permissions as complete
        return self._can_complete_transfer(user, transfer)


class WarehouseTransferViewSet(BaseTransferViewSet):
    """
    ViewSet for warehouse-to-warehouse transfers.
    
    Endpoints:
    - GET /api/warehouse-transfers/
    - POST /api/warehouse-transfers/
    - GET /api/warehouse-transfers/{id}/
    - PUT /api/warehouse-transfers/{id}/
    - DELETE /api/warehouse-transfers/{id}/
    - POST /api/warehouse-transfers/{id}/complete/
    - POST /api/warehouse-transfers/{id}/cancel/
    """
    
    def get_queryset(self):
        """Filter to only warehouse-to-warehouse transfers"""
        base_qs = super().get_queryset()
        return base_qs.filter(transfer_type=TransferType.WAREHOUSE_TO_WAREHOUSE)
    
    def perform_create(self, serializer):
        """Set transfer type automatically"""
        serializer.save(transfer_type=TransferType.WAREHOUSE_TO_WAREHOUSE)


class StorefrontTransferViewSet(BaseTransferViewSet):
    """
    ViewSet for warehouse-to-storefront transfers.
    
    Endpoints:
    - GET /api/storefront-transfers/
    - POST /api/storefront-transfers/
    - GET /api/storefront-transfers/{id}/
    - PUT /api/storefront-transfers/{id}/
    - DELETE /api/storefront-transfers/{id}/
    - POST /api/storefront-transfers/{id}/complete/
    - POST /api/storefront-transfers/{id}/cancel/
    """
    
    def get_queryset(self):
        """Filter to only warehouse-to-storefront transfers"""
        base_qs = super().get_queryset()
        return base_qs.filter(transfer_type=TransferType.WAREHOUSE_TO_STOREFRONT)
    
    def perform_create(self, serializer):
        """Set transfer type automatically"""
        serializer.save(transfer_type=TransferType.WAREHOUSE_TO_STOREFRONT)


class TransferViewSet(BaseTransferViewSet):
    """
    General transfer ViewSet (all types).
    
    Endpoints:
    - GET /api/transfers/
    - GET /api/transfers/{id}/
    """
    
    # Read-only for general endpoint
    http_method_names = ['get', 'head', 'options']
```

##### **4.3 Update URL Configuration**

**File**: `inventory/urls.py`

```python
from inventory.transfer_views import (
    WarehouseTransferViewSet,
    StorefrontTransferViewSet,
    TransferViewSet,
)

# Add to router
router.register(r'warehouse-transfers', WarehouseTransferViewSet, basename='warehouse-transfer')
router.register(r'storefront-transfers', StorefrontTransferViewSet, basename='storefront-transfer')
router.register(r'transfers', TransferViewSet, basename='transfer')
```

#### **Deliverables**
- ✅ Transfer serializers created
- ✅ Transfer ViewSets created with proper permissions
- ✅ URL routing configured
- ✅ Complete/Cancel actions implemented

---

### **PHASE 5: Testing & Data Migration** (Week 5)

#### **Goal**
Ensure data integrity through comprehensive testing and safe migration.

#### **Tasks**

##### **5.1 Create Tests**

**File**: `inventory/tests/test_transfers.py` (NEW)

```python
"""
Tests for Transfer System
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
from rest_framework.test import APITestCase
from rest_framework import status

from accounts.models import Business, BusinessMembership
from inventory.models import Warehouse, Product, Category, StockProduct, Stock
from inventory.transfer_models import Transfer, TransferItem
from inventory.constants import TransferType, TransferStatus


User = get_user_model()


class TransferModelTest(TestCase):
    """Test Transfer model logic"""
    
    def setUp(self):
        """Set up test data"""
        # Create business
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            name='Test User'
        )
        self.business = Business.objects.create(
            name='Test Business',
            owner=self.user
        )
        
        # Create warehouses
        # ... (create test warehouses, products, stock)
    
    def test_warehouse_to_warehouse_transfer_validation(self):
        """Test warehouse-to-warehouse transfer requires destination warehouse"""
        # Should raise ValidationError if no destination warehouse
        pass
    
    def test_prevents_self_transfer(self):
        """Test cannot transfer to same warehouse"""
        # Should raise ValidationError
        pass
    
    def test_atomic_transfer_completion(self):
        """Test transfer completion is atomic"""
        # If any item fails, entire transfer should rollback
        pass
    
    # ... more tests


class TransferAPITest(APITestCase):
    """Test Transfer API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        # ... create test data
        pass
    
    def test_create_warehouse_transfer(self):
        """Test creating warehouse-to-warehouse transfer"""
        self.client.force_authenticate(self.user)
        
        data = {
            'source_warehouse': str(self.warehouse1.id),
            'destination_warehouse': str(self.warehouse2.id),
            'items': [
                {
                    'product': str(self.product.id),
                    'quantity': 10,
                }
            ],
            'notes': 'Test transfer'
        }
        
        response = self.client.post('/inventory/api/warehouse-transfers/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], TransferStatus.PENDING)
    
    def test_complete_transfer_updates_inventory(self):
        """Test completing transfer updates inventory correctly"""
        # ... test inventory updates
        pass
    
    def test_cancel_completed_transfer_reverses_inventory(self):
        """Test cancelling completed transfer reverses inventory changes"""
        # ... test reversal
        pass
    
    # ... more API tests
```

##### **5.2 Data Migration Strategy**

**Option A: Dual-Write Period (RECOMMENDED)**

Keep both systems running for 30 days:
1. New transfers use Transfer model
2. Old StockAdjustment TRANSFER types still supported
3. Reports show both
4. After validation period, deprecate old system

**Option B: One-Time Migration**

Migrate existing StockAdjustment transfers to Transfer model:

```python
# management/commands/migrate_transfers.py

from django.core.management.base import BaseCommand
from inventory.stock_adjustments import StockAdjustment
from inventory.transfer_models import Transfer, TransferItem


class Command(BaseCommand):
    help = 'Migrate StockAdjustment transfers to Transfer model'
    
    def handle(self, *args, **options):
        # Find paired transfers (same reference_number)
        transfer_pairs = {}
        
        transfers_qs = StockAdjustment.objects.filter(
            adjustment_type__in=['TRANSFER_IN', 'TRANSFER_OUT']
        ).order_by('reference_number', 'created_at')
        
        for adj in transfers_qs:
            ref = adj.reference_number
            if ref not in transfer_pairs:
                transfer_pairs[ref] = {'out': None, 'in': None}
            
            if adj.adjustment_type == 'TRANSFER_OUT':
                transfer_pairs[ref]['out'] = adj
            else:
                transfer_pairs[ref]['in'] = adj
        
        # Create Transfer records
        migrated = 0
        for ref, pair in transfer_pairs.items():
            if not pair['out'] or not pair['in']:
                self.stdout.write(
                    self.style.WARNING(f'Incomplete pair for {ref}')
                )
                continue
            
            # Create Transfer
            # ... (create transfer and items)
            migrated += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'Migrated {migrated} transfers')
        )
```

##### **5.3 Integration Tests**

Test end-to-end workflows:
1. Create transfer → Complete → Verify inventory
2. Create transfer → Cancel → Verify no changes
3. Reports show correct movements
4. Permissions enforced correctly

#### **Deliverables**
- ✅ Comprehensive unit tests
- ✅ API integration tests
- ✅ Migration script (if needed)
- ✅ Test coverage > 90%

---

### **PHASE 6: Deprecation & Cleanup** (Week 6)

#### **Goal**
Remove old StockAdjustment transfer types and finalize system.

#### **Tasks**

##### **6.1 Remove TRANSFER_IN/OUT from StockAdjustment**

**File**: `inventory/stock_adjustments.py`

```python
# Update ADJUSTMENT_TYPES - remove transfer types
ADJUSTMENT_TYPES = [
    # Negative adjustments (reduce stock)
    ('THEFT', 'Theft/Shrinkage'),
    ('DAMAGE', 'Damage/Breakage'),
    # ... keep others ...
    
    # REMOVED:
    # ('TRANSFER_OUT', 'Transfer Out'),
    # ('TRANSFER_IN', 'Transfer In'),
]
```

##### **6.2 Create Final Migration**

```bash
python manage.py makemigrations inventory
# This will remove transfer choices from StockAdjustment
```

##### **6.3 Update Admin**

Update Django admin to use new Transfer models.

##### **6.4 Documentation Cleanup**

Remove references to old transfer system from all docs.

#### **Deliverables**
- ✅ Old system fully deprecated
- ✅ No breaking changes
- ✅ All docs updated
- ✅ Production deployment successful

---

## 🎨 FRONTEND INTEGRATION GUIDE

### **Overview for Frontend Developers**

This section provides everything you need to integrate the new warehouse transfer system.

### **Breaking Changes Summary**

| What Changed | Old Behavior | New Behavior | Migration Required |
|-------------|--------------|--------------|-------------------|
| **Warehouse → Warehouse Transfers** | Use `POST /api/stock-adjustments/` (create 2 records) | Use `POST /api/warehouse-transfers/` (create 1 transfer) | ✅ **YES** |
| **Warehouse → Storefront Transfers** | Use `POST /api/transfer-requests/` then fulfill | Use `POST /api/storefront-transfers/` | ✅ **YES** |
| **Transfer History** | Query `stock-adjustments?adjustment_type=TRANSFER_*` | Query `/api/transfers/` | ✅ **YES** |
| **Movement Reports** | No changes (backend handles it) | No changes | ❌ **NO** |

### **New API Endpoints**

#### **1. Warehouse-to-Warehouse Transfers**

**Create Transfer:**
```http
POST /inventory/api/warehouse-transfers/
Content-Type: application/json
Authorization: Bearer <token>

{
  "source_warehouse": "uuid-of-source-warehouse",
  "destination_warehouse": "uuid-of-destination-warehouse",
  "items": [
    {
      "product": "uuid-of-product",
      "quantity": 100,
      "unit_cost": "25.50",  // Optional, auto-detected if omitted
      "notes": "Optional item notes"
    }
  ],
  "transfer_date": "2025-10-26T10:00:00Z",  // Optional, defaults to now
  "notes": "Transfer notes"
}
```

**Response (201 Created):**
```json
{
  "id": "uuid-of-transfer",
  "business": "uuid",
  "transfer_type": "warehouse_to_warehouse",
  "source_warehouse": "uuid",
  "source_warehouse_name": "Main Warehouse",
  "destination_warehouse": "uuid",
  "destination_warehouse_name": "Branch Warehouse",
  "destination_storefront": null,
  "destination_storefront_name": null,
  "status": "pending",
  "reference_number": "TRF-20251026100000",
  "transfer_date": "2025-10-26T10:00:00Z",
  "received_date": null,
  "created_by": "uuid",
  "created_by_name": "John Doe",
  "received_by": null,
  "received_by_name": null,
  "notes": "Transfer notes",
  "items": [
    {
      "id": "uuid",
      "product": "uuid",
      "product_name": "iPhone 15",
      "product_sku": "IPH15",
      "batch": null,
      "quantity": 100,
      "received_quantity": 0,
      "unit_cost": "25.50",
      "total_cost": "2550.00",
      "notes": "Optional item notes"
    }
  ],
  "total_items": 1,
  "total_quantity": 100,
  "total_value": "2550.00",
  "created_at": "2025-10-26T10:00:00Z",
  "updated_at": "2025-10-26T10:00:00Z"
}
```

**Complete Transfer:**
```http
POST /inventory/api/warehouse-transfers/{id}/complete/
Content-Type: application/json
Authorization: Bearer <token>

{
  "notes": "Received in good condition"  // Optional
}
```

**Response (200 OK):**
```json
{
  // Same as create response, but with:
  "status": "completed",
  "received_date": "2025-10-26T15:30:00Z",
  "received_by": "uuid",
  "received_by_name": "Jane Smith",
  "items": [
    {
      // ... item fields ...
      "received_quantity": 100  // Now equals quantity
    }
  ]
}
```

**List Transfers:**
```http
GET /inventory/api/warehouse-transfers/
GET /inventory/api/warehouse-transfers/?status=pending
GET /inventory/api/warehouse-transfers/?source_warehouse=uuid
GET /inventory/api/warehouse-transfers/?search=TRF-001
```

**Response (200 OK):**
```json
{
  "count": 50,
  "next": "http://api/warehouse-transfers/?page=2",
  "previous": null,
  "results": [
    {
      "id": "uuid",
      "reference_number": "TRF-20251026100000",
      "transfer_type": "warehouse_to_warehouse",
      "status": "completed",
      "source_warehouse_name": "Main Warehouse",
      "destination_name": "Branch Warehouse",
      "total_items": 3,
      "total_quantity": 250,
      "transfer_date": "2025-10-26T10:00:00Z",
      "created_by_name": "John Doe",
      "created_at": "2025-10-26T10:00:00Z"
    }
    // ... more transfers
  ]
}
```

#### **2. Warehouse-to-Storefront Transfers**

**Create Transfer:**
```http
POST /inventory/api/storefront-transfers/
Content-Type: application/json
Authorization: Bearer <token>

{
  "source_warehouse": "uuid-of-warehouse",
  "destination_storefront": "uuid-of-storefront",  // Note: storefront, not warehouse
  "items": [
    {
      "product": "uuid",
      "quantity": 50
    }
  ],
  "notes": "Restock for weekend sale"
}
```

**Response:** (Same structure as warehouse transfer)

#### **3. General Transfer Listing (All Types)**

```http
GET /inventory/api/transfers/
GET /inventory/api/transfers/?transfer_type=warehouse_to_warehouse
GET /inventory/api/transfers/?transfer_type=warehouse_to_storefront
GET /inventory/api/transfers/?status=pending
```

### **Frontend Implementation Examples**

#### **React Component: Create Transfer**

```typescript
// types/transfer.ts
export enum TransferType {
  WAREHOUSE_TO_WAREHOUSE = 'warehouse_to_warehouse',
  WAREHOUSE_TO_STOREFRONT = 'warehouse_to_storefront',
}

export enum TransferStatus {
  PENDING = 'pending',
  IN_TRANSIT = 'in_transit',
  COMPLETED = 'completed',
  CANCELLED = 'cancelled',
}

export interface TransferItem {
  product: string;
  quantity: number;
  unit_cost?: string;
  notes?: string;
}

export interface CreateTransferDTO {
  source_warehouse: string;
  destination_warehouse?: string;
  destination_storefront?: string;
  items: TransferItem[];
  transfer_date?: string;
  notes?: string;
}

export interface Transfer {
  id: string;
  transfer_type: TransferType;
  status: TransferStatus;
  reference_number: string;
  source_warehouse_name: string;
  destination_name: string;
  total_items: number;
  total_quantity: number;
  total_value: string;
  created_at: string;
  // ... more fields
}
```

```typescript
// api/transfers.ts
import axios from 'axios';

const API_BASE = '/inventory/api';

export const transfersAPI = {
  // Create warehouse-to-warehouse transfer
  createWarehouseTransfer: async (data: CreateTransferDTO): Promise<Transfer> => {
    const response = await axios.post(`${API_BASE}/warehouse-transfers/`, data);
    return response.data;
  },
  
  // Create warehouse-to-storefront transfer
  createStorefrontTransfer: async (data: CreateTransferDTO): Promise<Transfer> => {
    const response = await axios.post(`${API_BASE}/storefront-transfers/`, data);
    return response.data;
  },
  
  // Get transfer by ID
  getTransfer: async (id: string): Promise<Transfer> => {
    const response = await axios.get(`${API_BASE}/transfers/${id}/`);
    return response.data;
  },
  
  // List transfers
  listTransfers: async (params?: {
    transfer_type?: TransferType;
    status?: TransferStatus;
    page?: number;
  }): Promise<{ count: number; results: Transfer[] }> => {
    const response = await axios.get(`${API_BASE}/transfers/`, { params });
    return response.data;
  },
  
  // Complete transfer
  completeTransfer: async (id: string, notes?: string): Promise<Transfer> => {
    const response = await axios.post(
      `${API_BASE}/warehouse-transfers/${id}/complete/`,
      { notes }
    );
    return response.data;
  },
  
  // Cancel transfer
  cancelTransfer: async (id: string, reason: string): Promise<Transfer> => {
    const response = await axios.post(
      `${API_BASE}/warehouse-transfers/${id}/cancel/`,
      { reason }
    );
    return response.data;
  },
};
```

```tsx
// components/TransferForm.tsx
import React, { useState } from 'react';
import { transfersAPI } from '../api/transfers';
import { TransferType } from '../types/transfer';

interface TransferFormProps {
  transferType: TransferType;
}

export const TransferForm: React.FC<TransferFormProps> = ({ transferType }) => {
  const [sourceWarehouse, setSourceWarehouse] = useState('');
  const [destination, setDestination] = useState('');
  const [items, setItems] = useState([{ product: '', quantity: 0 }]);
  const [loading, setLoading] = useState(false);
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      const data = {
        source_warehouse: sourceWarehouse,
        ...(transferType === TransferType.WAREHOUSE_TO_WAREHOUSE
          ? { destination_warehouse: destination }
          : { destination_storefront: destination }),
        items: items.map(item => ({
          product: item.product,
          quantity: item.quantity,
        })),
      };
      
      const transfer = transferType === TransferType.WAREHOUSE_TO_WAREHOUSE
        ? await transfersAPI.createWarehouseTransfer(data)
        : await transfersAPI.createStorefrontTransfer(data);
      
      console.log('Transfer created:', transfer);
      // Handle success (e.g., show notification, redirect)
    } catch (error) {
      console.error('Error creating transfer:', error);
      // Handle error
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <form onSubmit={handleSubmit}>
      <div>
        <label>Source Warehouse</label>
        <select
          value={sourceWarehouse}
          onChange={(e) => setSourceWarehouse(e.target.value)}
          required
        >
          <option value="">Select warehouse...</option>
          {/* Populate from API */}
        </select>
      </div>
      
      <div>
        <label>
          {transferType === TransferType.WAREHOUSE_TO_WAREHOUSE
            ? 'Destination Warehouse'
            : 'Destination Storefront'}
        </label>
        <select
          value={destination}
          onChange={(e) => setDestination(e.target.value)}
          required
        >
          <option value="">Select destination...</option>
          {/* Populate from API */}
        </select>
      </div>
      
      {/* Items section */}
      <div>
        <h3>Items</h3>
        {items.map((item, index) => (
          <div key={index}>
            <select
              value={item.product}
              onChange={(e) => {
                const newItems = [...items];
                newItems[index].product = e.target.value;
                setItems(newItems);
              }}
              required
            >
              <option value="">Select product...</option>
              {/* Populate from API */}
            </select>
            
            <input
              type="number"
              min="1"
              value={item.quantity}
              onChange={(e) => {
                const newItems = [...items];
                newItems[index].quantity = parseInt(e.target.value);
                setItems(newItems);
              }}
              required
            />
            
            <button
              type="button"
              onClick={() => setItems(items.filter((_, i) => i !== index))}
            >
              Remove
            </button>
          </div>
        ))}
        
        <button
          type="button"
          onClick={() => setItems([...items, { product: '', quantity: 0 }])}
        >
          Add Item
        </button>
      </div>
      
      <button type="submit" disabled={loading}>
        {loading ? 'Creating...' : 'Create Transfer'}
      </button>
    </form>
  );
};
```

### **Validation & Error Handling**

**Common Error Responses:**

```json
// 400 Bad Request - Validation Error
{
  "destination_warehouse": ["Required for warehouse-to-warehouse transfers."],
  "items": [
    {
      "product": ["Insufficient stock. Available: 50, Requested: 100"]
    }
  ]
}

// 403 Forbidden - Permission Denied
{
  "detail": "You do not have permission to create transfers."
}

// 404 Not Found
{
  "detail": "Not found."
}
```

**Frontend Error Handling:**

```typescript
try {
  await transfersAPI.createWarehouseTransfer(data);
} catch (error) {
  if (axios.isAxiosError(error)) {
    if (error.response?.status === 400) {
      // Validation errors
      const errors = error.response.data;
      // Show field-specific errors
      Object.keys(errors).forEach(field => {
        console.error(`${field}: ${errors[field]}`);
      });
    } else if (error.response?.status === 403) {
      // Permission denied
      alert('You do not have permission to perform this action.');
    }
  }
}
```

### **Permissions & Role-Based UI**

**Role Matrix:**

| Action | Owner | Admin | Manager | Warehouse Staff | Cashier |
|--------|-------|-------|---------|----------------|---------|
| Create Warehouse Transfer | ✅ | ✅ | ✅ | ✅ | ❌ |
| Create Storefront Transfer | ✅ | ✅ | ✅ | ❌ | ❌ |
| Complete Transfer | ✅ | ✅ | ✅ | ❌ | ❌ |
| Cancel Transfer | ✅ | ✅ | ✅ | ❌ | ❌ |
| View Transfers | ✅ | ✅ | ✅ | ✅ | ✅ |

**Frontend Implementation:**

```typescript
// hooks/usePermissions.ts
import { useAuth } from './useAuth';

export const useTransferPermissions = () => {
  const { user } = useAuth();
  
  return {
    canCreateWarehouseTransfer: ['owner', 'admin', 'manager', 'warehouse_staff'].includes(user.role),
    canCreateStorefrontTransfer: ['owner', 'admin', 'manager'].includes(user.role),
    canCompleteTransfer: ['owner', 'admin', 'manager'].includes(user.role),
    canCancelTransfer: ['owner', 'admin', 'manager'].includes(user.role),
  };
};

// Usage in component
const TransferPage = () => {
  const permissions = useTransferPermissions();
  
  return (
    <div>
      {permissions.canCreateWarehouseTransfer && (
        <button onClick={createTransfer}>Create Transfer</button>
      )}
      {/* ... */}
    </div>
  );
};
```

### **Migration Guide for Existing Frontend**

#### **Step 1: Update API Calls**

**Old Code (DO NOT USE):**
```typescript
// ❌ OLD - Creating warehouse transfer via stock adjustments
const createTransfer = async () => {
  // Create OUT adjustment
  await axios.post('/api/stock-adjustments/', {
    adjustment_type: 'TRANSFER_OUT',
    quantity: -10,
    reference_number: 'TRF-001',
    // ...
  });
  
  // Create IN adjustment
  await axios.post('/api/stock-adjustments/', {
    adjustment_type: 'TRANSFER_IN',
    quantity: 10,
    reference_number: 'TRF-001',
    // ...
  });
};
```

**New Code (USE THIS):**
```typescript
// ✅ NEW - Using unified transfer API
const createTransfer = async () => {
  await transfersAPI.createWarehouseTransfer({
    source_warehouse: sourceId,
    destination_warehouse: destId,
    items: [{ product: productId, quantity: 10 }],
  });
};
```

#### **Step 2: Update Transfer Lists**

**Old Code:**
```typescript
// ❌ OLD - Query stock adjustments
const fetchTransfers = async () => {
  const response = await axios.get('/api/stock-adjustments/', {
    params: {
      adjustment_type: 'TRANSFER_OUT',
    },
  });
  // Need to pair with TRANSFER_IN records manually
};
```

**New Code:**
```typescript
// ✅ NEW - Query transfers directly
const fetchTransfers = async () => {
  const response = await transfersAPI.listTransfers({
    transfer_type: TransferType.WAREHOUSE_TO_WAREHOUSE,
  });
  // Single record per transfer, already complete
};
```

#### **Step 3: Update UI Components**

Replace transfer-related components to use new API structure.

---

## 📝 API Reference Summary

### **Endpoints**

| Endpoint | Method | Purpose | Auth Required |
|----------|--------|---------|---------------|
| `/api/warehouse-transfers/` | GET | List warehouse transfers | ✅ |
| `/api/warehouse-transfers/` | POST | Create warehouse transfer | ✅ |
| `/api/warehouse-transfers/{id}/` | GET | Get transfer details | ✅ |
| `/api/warehouse-transfers/{id}/` | PUT | Update transfer | ✅ |
| `/api/warehouse-transfers/{id}/complete/` | POST | Complete transfer | ✅ |
| `/api/warehouse-transfers/{id}/cancel/` | POST | Cancel transfer | ✅ |
| `/api/storefront-transfers/` | GET | List storefront transfers | ✅ |
| `/api/storefront-transfers/` | POST | Create storefront transfer | ✅ |
| `/api/storefront-transfers/{id}/` | GET | Get transfer details | ✅ |
| `/api/storefront-transfers/{id}/complete/` | POST | Complete transfer | ✅ |
| `/api/storefront-transfers/{id}/cancel/` | POST | Cancel transfer | ✅ |
| `/api/transfers/` | GET | List all transfers | ✅ |
| `/api/transfers/{id}/` | GET | Get transfer details | ✅ |

### **Query Parameters (List Endpoints)**

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `status` | string | Filter by status | `?status=pending` |
| `transfer_type` | string | Filter by type | `?transfer_type=warehouse_to_warehouse` |
| `source_warehouse` | UUID | Filter by source | `?source_warehouse=uuid` |
| `destination_warehouse` | UUID | Filter by destination warehouse | `?destination_warehouse=uuid` |
| `destination_storefront` | UUID | Filter by destination storefront | `?destination_storefront=uuid` |
| `search` | string | Search in reference number, notes | `?search=TRF-001` |
| `ordering` | string | Sort results | `?ordering=-created_at` |
| `page` | number | Pagination | `?page=2` |
| `page_size` | number | Items per page | `?page_size=50` |

---

## 🧪 Testing Checklist

### **Backend Tests**

- [ ] Transfer model validation (prevent self-transfer, require destination)
- [ ] Transfer creation with multiple items
- [ ] Atomic transfer completion (all items succeed or fail together)
- [ ] Inventory updates on completion
- [ ] Inventory reversal on cancellation
- [ ] Permissions enforcement
- [ ] MovementTracker integration
- [ ] Report accuracy

### **Frontend Tests**

- [ ] Create warehouse transfer form
- [ ] Create storefront transfer form
- [ ] Transfer list with filters
- [ ] Transfer detail view
- [ ] Complete transfer action
- [ ] Cancel transfer action
- [ ] Error handling
- [ ] Permission-based UI rendering

### **Integration Tests**

- [ ] End-to-end transfer workflow
- [ ] Movement appears in reports
- [ ] Concurrent transfers (race conditions)
- [ ] Transfer completion with insufficient stock
- [ ] Cross-browser compatibility

---

## 🔄 Rollback Plan

### **If Issues Arise**

#### **Phase 1-3 (Pre-Production)**
- Simply don't deploy to production
- No data migration needed
- Revert code changes

#### **Phase 4-5 (Production with Dual-Write)**
- Both systems operational
- Can switch back to StockAdjustment transfers
- No data loss

#### **Phase 6 (Full Migration)**
- Run reverse migration:
  ```bash
  python manage.py migrate inventory 0018  # Revert to before Transfer model
  ```
- Redeploy previous version
- Restore from database backup if needed

### **Monitoring**

Watch these metrics post-deployment:
- Transfer creation success rate
- Inventory accuracy
- Report data completeness
- API error rates
- User feedback

---

## 📞 Support & Questions

### **For Backend Developers**
- See phase implementation details above
- Review test cases in `inventory/tests/test_transfers.py`
- Check MovementTracker service documentation

### **For Frontend Developers**
- See Frontend Integration Guide section
- Review API reference
- Check TypeScript type definitions
- Test endpoints in Postman/Swagger

### **Reporting Issues**
When reporting issues, include:
1. Environment (dev/staging/production)
2. User role and permissions
3. Transfer type and status
4. Error messages or unexpected behavior
5. Steps to reproduce

---

## ✅ Implementation Completion Criteria

### **Phase 1 Complete When:**
- [ ] MovementTracker service created and tested
- [ ] Constants file created
- [ ] No existing functionality broken
- [ ] Code review approved

### **Phase 2 Complete When:**
- [ ] Transfer models created with validation
- [ ] Migrations applied successfully
- [ ] MovementTracker using Transfer model
- [ ] Unit tests passing

### **Phase 3 Complete When:**
- [ ] All reports updated
- [ ] Report tests passing
- [ ] Data accuracy verified

### **Phase 4 Complete When:**
- [ ] All API endpoints functional
- [ ] Serializers handle validation
- [ ] Permission checks working
- [ ] API tests passing

### **Phase 5 Complete When:**
- [ ] Test coverage > 90%
- [ ] Data migration (if needed) successful
- [ ] Integration tests passing
- [ ] Performance benchmarks met

### **Phase 6 Complete When:**
- [ ] Old system deprecated
- [ ] Documentation updated
- [ ] Production deployment successful
- [ ] No critical issues in monitoring

---

## 📚 Appendix

### **A. Database Schema Changes**

**New Tables:**
- `inventory_transfers`
- `inventory_transfer_items`

**Modified Tables:**
- `inventory_stock_adjustments` (remove TRANSFER_IN/OUT from choices)

**Indexes Added:**
- `idx_transfers_business_status`
- `idx_transfers_type_status`
- `idx_transfers_source_warehouse_status`
- `idx_transfers_created_at`

### **B. Environment Variables**

No new environment variables required.

### **C. Dependencies**

No new Python packages required. All functionality uses existing Django/DRF.

### **D. Performance Considerations**

- Transfers use database transactions (atomic)
- SELECT FOR UPDATE prevents race conditions
- Batch operations for multiple items
- Indexes on frequently queried fields

Expected performance:
- Transfer creation: < 500ms
- Transfer completion: < 1s
- Transfer list (50 items): < 200ms

---

**Document Version:** 1.0  
**Last Updated:** October 26, 2025  
**Status:** Ready for Implementation

