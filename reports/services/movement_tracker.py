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
from typing import List, Dict, Optional, Any, Tuple, Iterator
from datetime import datetime, date

from django.db import connection


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

    # Legacy transfer adjustment types (old system)
    TRANSFER_ADJUSTMENT_TYPES = ['TRANSFER_IN', 'TRANSFER_OUT']
    
    @classmethod
    def get_movements(
        cls,
        business_id: str,
        warehouse_id: Optional[str] = None,
        product_id: Optional[str] = None,
        category_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        movement_types: Optional[List[str]] = None,
        search: Optional[str] = None,
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
        rows = cls._execute_union_query(
            business_id=business_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            category_id=category_id,
            start_date=start_date,
            end_date=end_date,
            movement_types=movement_types,
            adjustment_type=None,
            search=search,
            sort='date_desc',
            limit=None,
            offset=None,
            include_cancelled=include_cancelled
        )
        return [cls._normalize_row(row) for row in rows]

    @classmethod
    def get_paginated_movements(
        cls,
        *,
        business_id: str,
        warehouse_id: Optional[str] = None,
        product_id: Optional[str] = None,
        category_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        movement_types: Optional[List[str]] = None,
        adjustment_type: Optional[str] = None,
        search: Optional[str] = None,
        sort: str = 'date_desc',
        limit: int,
        offset: int,
        include_cancelled: bool = False
    ) -> List[Dict[str, Any]]:
        """Return a single page of movements."""
        rows = cls._execute_union_query(
            business_id=business_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            category_id=category_id,
            start_date=start_date,
            end_date=end_date,
            movement_types=movement_types,
            adjustment_type=adjustment_type,
            search=search,
            sort=sort,
            limit=limit,
            offset=offset,
            include_cancelled=include_cancelled
        )
        return [cls._normalize_row(row) for row in rows]

    @classmethod
    def count_movements(
        cls,
        *,
        business_id: str,
        warehouse_id: Optional[str] = None,
        product_id: Optional[str] = None,
        category_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        movement_types: Optional[List[str]] = None,
        adjustment_type: Optional[str] = None,
        search: Optional[str] = None,
        include_cancelled: bool = False
    ) -> int:
        """Return total number of movements matching filters."""
        sql, params = cls._build_union_query(
            business_id=business_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            category_id=category_id,
            start_date=start_date,
            end_date=end_date,
            movement_types=movement_types,
            adjustment_type=adjustment_type,
            search=search,
            sort=None,
            limit=None,
            offset=None,
            include_cancelled=include_cancelled,
            count=True,
            skip_order=True
        )
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            result = cursor.fetchone()
        return int(result[0]) if result else 0
    
    @classmethod
    def get_summary(
        cls,
        *,
        business_id: str,
        warehouse_id: Optional[str] = None,
        product_id: Optional[str] = None,
        category_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        movement_types: Optional[List[str]] = None,
        adjustment_type: Optional[str] = None,
        search: Optional[str] = None,
        include_cancelled: bool = False
    ) -> Dict[str, Any]:
        """Return summary statistics for movements matching the filters."""

        base_sql, params = cls._build_union_query(
            business_id=business_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            category_id=category_id,
            start_date=start_date,
            end_date=end_date,
            movement_types=movement_types,
            adjustment_type=adjustment_type,
            search=search,
            sort=None,
            limit=None,
            offset=None,
            include_cancelled=include_cancelled,
            count=False,
            skip_order=True
        )

        summary_sql = f"""
            WITH movements AS ({base_sql})
            SELECT
                COUNT(*) AS total_movements,
                SUM(CASE WHEN movement_type = 'transfer' THEN 1 ELSE 0 END) AS transfers_count,
                SUM(CASE WHEN movement_type = 'sale' THEN 1 ELSE 0 END) AS sales_count,
                SUM(CASE WHEN movement_type = 'adjustment' THEN 1 ELSE 0 END) AS adjustments_count,
                SUM(CASE WHEN movement_type = 'shrinkage' THEN 1 ELSE 0 END) AS shrinkage_count,
                SUM(CASE WHEN direction = 'in' THEN quantity ELSE 0 END) AS total_quantity_in,
                SUM(CASE WHEN direction = 'out' THEN quantity ELSE 0 END) AS total_quantity_out,
                SUM(CASE WHEN movement_type = 'shrinkage' THEN quantity ELSE 0 END) AS shrinkage_quantity,
                SUM(CASE WHEN movement_type = 'transfer' THEN quantity ELSE 0 END) AS transfer_quantity,
                SUM(CASE WHEN direction = 'in' THEN total_value ELSE 0 END) AS total_value_in,
                SUM(CASE WHEN direction = 'out' THEN total_value ELSE 0 END) AS total_value_out,
                SUM(CASE WHEN movement_type = 'transfer' THEN total_value ELSE 0 END) AS transfer_value,
                SUM(CASE WHEN movement_type = 'shrinkage' THEN total_value ELSE 0 END) AS shrinkage_value
            FROM movements
        """

        with connection.cursor() as cursor:
            cursor.execute(summary_sql, params)
            row = cursor.fetchone()

        if not row:
            return {
                'total_movements': 0,
                'transfers_count': 0,
                'sales_count': 0,
                'adjustments_count': 0,
                'shrinkage_count': 0,
                'total_quantity_in': Decimal('0'),
                'total_quantity_out': Decimal('0'),
                'net_quantity': Decimal('0'),
                'total_value_in': Decimal('0.00'),
                'total_value_out': Decimal('0.00'),
                'net_value': Decimal('0.00'),
                'total_quantity_transferred': Decimal('0'),
                'total_value_transferred': Decimal('0.00'),
                'shrinkage_quantity': Decimal('0'),
                'shrinkage_value': Decimal('0.00'),
                'total_shrinkage_quantity': Decimal('0'),
                'total_shrinkage_value': Decimal('0.00'),
            }

        (
            total_movements,
            transfers_count,
            sales_count,
            adjustments_count,
            shrinkage_count,
            total_quantity_in,
            total_quantity_out,
            shrinkage_quantity,
            transfer_quantity,
            total_value_in,
            total_value_out,
            transfer_value,
            shrinkage_value,
        ) = row

        total_quantity_in = Decimal(total_quantity_in or 0)
        total_quantity_out = Decimal(total_quantity_out or 0)
        shrinkage_quantity = Decimal(shrinkage_quantity or 0)
        transfer_quantity = Decimal(transfer_quantity or 0)
        total_value_in = Decimal(total_value_in or 0)
        total_value_out = Decimal(total_value_out or 0)
        transfer_value = Decimal(transfer_value or 0)
        shrinkage_value = Decimal(shrinkage_value or 0)

        net_quantity = total_quantity_in - total_quantity_out
        net_value = total_value_in - total_value_out

        return {
            'total_movements': int(total_movements or 0),
            'transfers_count': int(transfers_count or 0),
            'sales_count': int(sales_count or 0),
            'adjustments_count': int(adjustments_count or 0),
            'shrinkage_count': int(shrinkage_count or 0),
            'total_quantity_in': total_quantity_in,
            'total_quantity_out': total_quantity_out,
            'net_quantity': net_quantity,
            'total_value_in': total_value_in,
            'total_value_out': total_value_out,
            'net_value': net_value,
            'total_quantity_transferred': transfer_quantity,
            'total_value_transferred': transfer_value,
            'shrinkage_quantity': shrinkage_quantity,
            'shrinkage_value': shrinkage_value,
            'total_shrinkage_quantity': shrinkage_quantity,
            'total_shrinkage_value': shrinkage_value,
        }

    @classmethod
    def aggregate_by_warehouse(
        cls,
        *,
        business_id: str,
        warehouse_id: Optional[str] = None,
        product_id: Optional[str] = None,
        category_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        movement_types: Optional[List[str]] = None,
        adjustment_type: Optional[str] = None,
        search: Optional[str] = None,
        include_cancelled: bool = False
    ) -> Dict[str, Dict[str, Any]]:
        """Return aggregation of movements grouped by warehouse/location."""

        base_sql, params = cls._build_union_query(
            business_id=business_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            category_id=category_id,
            start_date=start_date,
            end_date=end_date,
            movement_types=movement_types,
            adjustment_type=adjustment_type,
            search=search,
            sort=None,
            limit=None,
            offset=None,
            include_cancelled=include_cancelled,
            count=False,
            skip_order=True
        )

        aggregation_sql = f"""
            WITH movements AS ({base_sql}),
            warehouse_entries AS (
                SELECT
                    movement_id,
                    source_location_id AS location_id,
                    source_location_name AS location_name,
                    CASE
                        WHEN direction IN ('out', 'both') THEN -quantity
                        ELSE 0
                    END AS net_quantity,
                    CASE
                        WHEN direction IN ('out', 'both') THEN quantity
                        ELSE 0
                    END AS units_out,
                    CASE
                        WHEN direction = 'in' THEN quantity
                        ELSE 0
                    END AS units_in
                FROM movements
                WHERE source_location_id IS NOT NULL

                UNION ALL

                SELECT
                    movement_id,
                    destination_location_id AS location_id,
                    destination_location_name AS location_name,
                    CASE
                        WHEN direction IN ('in', 'both') THEN quantity
                        WHEN direction = 'out' THEN -quantity
                        ELSE 0
                    END AS net_quantity,
                    CASE
                        WHEN direction = 'out' THEN quantity
                        ELSE 0
                    END AS units_out,
                    CASE
                        WHEN direction IN ('in', 'both') THEN quantity
                        ELSE 0
                    END AS units_in
                FROM movements
                WHERE destination_location_id IS NOT NULL
            )
            SELECT
                location_id,
                MAX(location_name) AS location_name,
                COUNT(DISTINCT movement_id) AS movements,
                SUM(net_quantity) AS net_change,
                SUM(units_in) AS units_in,
                SUM(units_out) AS units_out
            FROM warehouse_entries
            GROUP BY location_id
        """

        results: Dict[str, Dict[str, Any]] = {}

        with connection.cursor() as cursor:
            cursor.execute(aggregation_sql, params)
            for row in cursor.fetchall():
                location_id, location_name, movements_count, net_change, units_in, units_out = row
                if location_id is None:
                    continue
                results[str(location_id)] = {
                    'name': location_name,
                    'movements': int(movements_count or 0),
                    'net_change': float(net_change or 0),
                    'units_in': float(units_in or 0),
                    'units_out': float(units_out or 0),
                }

        return results

    @classmethod
    def aggregate_by_category(
        cls,
        *,
        business_id: str,
        warehouse_id: Optional[str] = None,
        product_id: Optional[str] = None,
        category_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        movement_types: Optional[List[str]] = None,
        adjustment_type: Optional[str] = None,
        search: Optional[str] = None,
        include_cancelled: bool = False
    ) -> Dict[str, Dict[str, Any]]:
        """Return aggregation of movements grouped by product category."""

        base_sql, params = cls._build_union_query(
            business_id=business_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            category_id=category_id,
            start_date=start_date,
            end_date=end_date,
            movement_types=movement_types,
            adjustment_type=adjustment_type,
            search=search,
            sort=None,
            limit=None,
            offset=None,
            include_cancelled=include_cancelled,
            count=False,
            skip_order=True
        )

        aggregation_sql = f"""
            WITH movements AS ({base_sql})
            SELECT
                category_id,
                MAX(category_name) AS category_name,
                COUNT(*) AS movements,
                SUM(CASE WHEN direction = 'in' THEN quantity ELSE 0 END) AS units_in,
                SUM(CASE WHEN direction = 'out' THEN quantity ELSE 0 END) AS units_out,
                SUM(CASE
                        WHEN direction = 'in' THEN quantity
                        WHEN direction = 'out' THEN -quantity
                        ELSE 0
                    END) AS net_change
            FROM movements
            WHERE category_id IS NOT NULL
            GROUP BY category_id
        """

        results: Dict[str, Dict[str, Any]] = {}

        with connection.cursor() as cursor:
            cursor.execute(aggregation_sql, params)
            for row in cursor.fetchall():
                cat_id, cat_name, movements_count, units_in, units_out, net_change = row
                if cat_id is None:
                    continue
                results[str(cat_id)] = {
                    'name': cat_name,
                    'movements': int(movements_count or 0),
                    'net_change': float(net_change or 0),
                    'units_in': float(units_in or 0),
                    'units_out': float(units_out or 0),
                }

        return results

    @classmethod
    def iter_movements(
        cls,
        *,
        business_id: str,
        warehouse_id: Optional[str] = None,
        product_id: Optional[str] = None,
        category_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        movement_types: Optional[List[str]] = None,
        adjustment_type: Optional[str] = None,
        search: Optional[str] = None,
        sort: str = 'date_desc',
        include_cancelled: bool = False,
        chunk_size: int = 500
    ) -> Iterator[Dict[str, Any]]:
        """Yield movements matching filters in chunks without loading all rows."""

        sql, params = cls._build_union_query(
            business_id=business_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            category_id=category_id,
            start_date=start_date,
            end_date=end_date,
            movement_types=movement_types,
            adjustment_type=adjustment_type,
            search=search,
            sort=sort,
            limit=None,
            offset=None,
            include_cancelled=include_cancelled,
            count=False,
            skip_order=False
        )

        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            columns = [col[0] for col in cursor.description]
            while True:
                rows = cursor.fetchmany(chunk_size)
                if not rows:
                    break
                for row in rows:
                    raw = dict(zip(columns, row))
                    yield cls._normalize_row(raw)
    
    @classmethod
    def _execute_union_query(
        cls,
        *,
        business_id: str,
        warehouse_id: Optional[str],
        product_id: Optional[str],
        category_id: Optional[str],
        start_date: Optional[date],
        end_date: Optional[date],
        movement_types: Optional[List[str]],
        adjustment_type: Optional[str],
        search: Optional[str],
        sort: str,
        limit: Optional[int],
        offset: Optional[int],
        include_cancelled: bool
    ) -> List[Dict[str, Any]]:
        sql, params = cls._build_union_query(
            business_id=business_id,
            warehouse_id=warehouse_id,
            product_id=product_id,
            category_id=category_id,
            start_date=start_date,
            end_date=end_date,
            movement_types=movement_types,
            adjustment_type=adjustment_type,
            search=search,
            sort=sort,
            limit=limit,
            offset=offset,
            include_cancelled=include_cancelled,
            count=False
        )
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            columns = [col[0] for col in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return results

    @classmethod
    def _normalize_row(cls, row: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize raw SQL row to legacy movement structure."""
        warehouse_id, warehouse_name = cls._resolve_primary_location(
            row.get('direction'),
            row.get('source_location_id'),
            row.get('source_location_name'),
            row.get('destination_location_id'),
            row.get('destination_location_name'),
        )

        # ✅ CRITICAL FIX: Determine correct detail endpoint based on source_type
        # This helps frontend route to the correct API for fetching details
        detail_endpoint_type = None
        if row['source_type'] == 'sale':
            detail_endpoint_type = 'sale'
        elif row['source_type'] == 'new_transfer':
            detail_endpoint_type = 'transfer'
        elif row['source_type'] == 'legacy_adjustment':
            # Old TRANSFER_IN/TRANSFER_OUT stored as StockAdjustments
            detail_endpoint_type = 'adjustment'

        return {
            'id': row['movement_id'],
            'type': row['movement_type'],
            'source_type': row['source_type'],
            'detail_endpoint_type': detail_endpoint_type,  # ✅ NEW: Explicit routing hint for frontend
            'date': row['movement_date'],
            'product_id': row['product_id'],
            'product_name': row['product_name'],
            'product_sku': row['product_sku'],
            'category_id': row['category_id'],
            'category': row['category_name'],
            'quantity': row['quantity'],
            'direction': row['direction'],
            'source_location': row['source_location_name'],
            'source_location_id': row['source_location_id'],
            'destination_location': row['destination_location_name'],
            'destination_location_id': row['destination_location_id'],
            'warehouse_id': warehouse_id,
            'warehouse_name': warehouse_name,
            'reference_number': row['reference_number'],
            'reference_id': row['reference_id'],
            'unit_cost': row['unit_cost'],
            'total_value': row['total_value'],
            'reason': row['notes'],
            'created_by': row['performed_by'],
            'performed_by_id': row.get('performed_by_id'),
            'performed_via': row.get('performed_via'),
            'performed_by_role': row.get('performed_by_role'),
            'status': row['status'],
            'adjustment_type': row['adjustment_type'],
            'sale_type': row['sale_type'],
            'transfer_type': row['transfer_type'],
            'sale_id': row['sale_id'],
            'transfer_id': row['transfer_id'],
            'adjustment_id': row['adjustment_id'],
        }

    @staticmethod
    def _resolve_primary_location(
        direction: Optional[str],
        source_id: Optional[str],
        source_name: Optional[str],
        destination_id: Optional[str],
        destination_name: Optional[str],
    ) -> Tuple[Optional[str], Optional[str]]:
        """Determine the primary warehouse/location identifier for a movement."""
        resolved_direction = (direction or '').lower()

        if resolved_direction == 'out':
            return source_id or destination_id, source_name or destination_name
        if resolved_direction == 'in':
            return destination_id or source_id, destination_name or source_name
        return source_id or destination_id, source_name or destination_name

    @classmethod
    def _build_union_query(
        cls,
        *,
        business_id: str,
        warehouse_id: Optional[str],
        product_id: Optional[str],
        category_id: Optional[str],
        start_date: Optional[date],
        end_date: Optional[date],
        movement_types: Optional[List[str]],
        adjustment_type: Optional[str],
        search: Optional[str],
        sort: Optional[str],
        limit: Optional[int],
        offset: Optional[int],
        include_cancelled: bool,
        count: bool,
        skip_order: bool = False,
    ) -> Tuple[str, Dict[str, Any]]:
        movement_types_set = None
        if movement_types:
            movement_types_set = {mt.lower() for mt in movement_types}

        include_adjustments = cls._should_include_adjustments(movement_types_set)
        include_transfers = cls._should_include_new_transfers(movement_types_set)
        include_sales = cls._should_include_sales(movement_types_set)

        params: Dict[str, Any] = {
            'business_id': business_id,
            'warehouse_id': warehouse_id,
            'product_id': product_id,
            'category_id': category_id,
            'start_date': start_date,
            'end_date': end_date,
            'adjustment_type_filter': adjustment_type,
            'search_term': f"%{search}%" if search else None,
            'movement_types': list(movement_types_set) if movement_types_set else None,
            'shrinkage_types': cls.SHRINKAGE_TYPES,
            'transfer_adjustment_types': cls.TRANSFER_ADJUSTMENT_TYPES,
            'include_cancelled': include_cancelled,
        }

        subqueries: List[str] = []

        if include_adjustments:
            subqueries.append(cls._adjustment_subquery())
        if include_transfers:
            subqueries.append(cls._transfer_subquery())
        if include_sales:
            subqueries.append(cls._sale_subquery())

        if not subqueries:
            # No sources selected; return empty result
            empty_sql = "SELECT 0 WHERE 1=0"
            return empty_sql, params

        union_sql = " UNION ALL ".join(subqueries)
        wrapped = f"SELECT * FROM ({union_sql}) AS movements WHERE 1=1"

        if params['movement_types']:
            wrapped += " AND movements.movement_type = ANY(%(movement_types)s)"

        if params['adjustment_type_filter']:
            wrapped += " AND movements.adjustment_type = %(adjustment_type_filter)s"

        if params['search_term']:
            wrapped += (
                " AND (movements.product_name ILIKE %(search_term)s "
                "OR movements.product_sku ILIKE %(search_term)s)"
            )

        order_clause = cls._resolve_sort_clause(sort) if sort else None

        if count:
            return f"SELECT COUNT(*) FROM ({wrapped}) AS count_sub", params

        if not skip_order and order_clause:
            wrapped += f" ORDER BY {order_clause}"

        if limit is not None:
            params['limit'] = limit
            params['offset'] = offset or 0
            wrapped += " LIMIT %(limit)s OFFSET %(offset)s"

        return wrapped, params

    @staticmethod
    def _resolve_sort_clause(sort: Optional[str]) -> str:
        if not sort:
            return 'movements.movement_date DESC'

        mapping = {
            'date_asc': 'movements.movement_date ASC',
            'quantity': 'movements.quantity DESC',
            'product': 'movements.product_name ASC',
        }
        return mapping.get(sort, 'movements.movement_date DESC')

    @classmethod
    def _should_include_adjustments(cls, movement_types: Optional[set]) -> bool:
        if not movement_types:
            return True
        return bool(movement_types.intersection({'transfer', 'adjustment', 'shrinkage'}))

    @classmethod
    def _should_include_new_transfers(cls, movement_types: Optional[set]) -> bool:
        if not movement_types:
            return True
        return 'transfer' in movement_types

    @classmethod
    def _should_include_sales(cls, movement_types: Optional[set]) -> bool:
        if not movement_types:
            return True
        return 'sale' in movement_types

    @classmethod
    def _adjustment_subquery(cls) -> str:
        return """
            SELECT
                sa.id::text AS movement_id,
                CASE
                    WHEN sa.adjustment_type = ANY(%(transfer_adjustment_types)s) THEN 'transfer'
                    WHEN sa.adjustment_type = ANY(%(shrinkage_types)s) THEN 'shrinkage'
                    ELSE 'adjustment'
                END AS movement_type,
                'legacy_adjustment' AS source_type,
                sa.created_at AS movement_date,
                p.id::text AS product_id,
                p.name AS product_name,
                p.sku AS product_sku,
                p.category_id::text AS category_id,
                c.name AS category_name,
                ABS(sa.quantity)::numeric AS quantity,
                CASE WHEN sa.quantity >= 0 THEN 'in' ELSE 'out' END AS direction,
                CASE WHEN sa.quantity < 0 THEN w.id::text ELSE NULL END AS source_location_id,
                CASE WHEN sa.quantity < 0 THEN w.name ELSE NULL END AS source_location_name,
                CASE WHEN sa.quantity >= 0 THEN w.id::text ELSE NULL END AS destination_location_id,
                CASE WHEN sa.quantity >= 0 THEN w.name ELSE NULL END AS destination_location_name,
                sa.reference_number,
                sa.id::text AS reference_id,
                NULL::text AS sale_id,
                NULL::text AS transfer_id,
                sa.id::text AS adjustment_id,
                u.name AS performed_by,
                sa.reason AS notes,
                sa.unit_cost,
                ABS(sa.total_cost)::numeric AS total_value,
                sa.adjustment_type,
                NULL::text AS sale_type,
                NULL::text AS transfer_type,
                sa.status AS status,
                u.id::text AS performed_by_id,
                CASE WHEN sa.created_by_id IS NULL THEN 'system' ELSE 'manual' END AS performed_via,
                NULL::text AS performed_by_role
            FROM stock_adjustments sa
            JOIN stock_products sp ON sa.stock_product_id = sp.id
            JOIN products p ON sp.product_id = p.id
            LEFT JOIN categories c ON p.category_id = c.id
            JOIN warehouses w ON sp.warehouse_id = w.id
            LEFT JOIN users u ON sa.created_by_id = u.id
            WHERE sa.business_id = %(business_id)s
              AND sa.adjustment_type NOT IN ('TRANSFER_IN', 'TRANSFER_OUT')
              AND (%(warehouse_id)s IS NULL OR w.id = %(warehouse_id)s)
              AND (%(product_id)s IS NULL OR p.id = %(product_id)s)
              AND (%(category_id)s IS NULL OR p.category_id = %(category_id)s)
              AND (%(start_date)s IS NULL OR sa.created_at::date >= %(start_date)s)
              AND (%(end_date)s IS NULL OR sa.created_at::date <= %(end_date)s)
        """

    @classmethod
    def _transfer_subquery(cls) -> str:
        return """
            SELECT
                (t.id::text || '-' || ti.id::text) AS movement_id,
                'transfer' AS movement_type,
                'new_transfer' AS source_type,
                COALESCE(t.received_at, t.completed_at, t.created_at) AS movement_date,
                p.id::text AS product_id,
                p.name AS product_name,
                p.sku AS product_sku,
                p.category_id::text AS category_id,
                c.name AS category_name,
                ti.quantity::numeric AS quantity,
                'both' AS direction,
                t.source_warehouse_id::text AS source_location_id,
                sw.name AS source_location_name,
                COALESCE(t.destination_warehouse_id::text, t.destination_storefront_id::text) AS destination_location_id,
                COALESCE(dw.name, ds.name) AS destination_location_name,
                t.reference_number,
                t.id::text AS reference_id,
                NULL::text AS sale_id,
                t.id::text AS transfer_id,
                NULL::text AS adjustment_id,
                uc.name AS performed_by,
                t.notes AS notes,
                ti.unit_cost,
                ti.total_cost AS total_value,
                NULL::text AS adjustment_type,
                NULL::text AS sale_type,
                t.transfer_type AS transfer_type,
                t.status AS status,
                uc.id::text AS performed_by_id,
                CASE WHEN t.created_by_id IS NULL THEN 'system' ELSE 'manual' END AS performed_via,
                NULL::text AS performed_by_role
            FROM inventory_transfer t
            JOIN inventory_transfer_item ti ON ti.transfer_id = t.id
            JOIN products p ON ti.product_id = p.id
            LEFT JOIN categories c ON p.category_id = c.id
            LEFT JOIN warehouses sw ON t.source_warehouse_id = sw.id
            LEFT JOIN warehouses dw ON t.destination_warehouse_id = dw.id
            LEFT JOIN storefronts ds ON t.destination_storefront_id = ds.id
            LEFT JOIN users uc ON t.created_by_id = uc.id
            WHERE t.business_id = %(business_id)s
              AND (%(product_id)s IS NULL OR ti.product_id = %(product_id)s)
              AND (%(category_id)s IS NULL OR p.category_id = %(category_id)s)
              AND (%(warehouse_id)s IS NULL
                   OR t.source_warehouse_id = %(warehouse_id)s
                   OR t.destination_warehouse_id = %(warehouse_id)s
                   OR t.destination_storefront_id = %(warehouse_id)s)
              AND (%(start_date)s IS NULL OR COALESCE(t.received_at, t.completed_at, t.created_at)::date >= %(start_date)s)
              AND (%(end_date)s IS NULL OR COALESCE(t.received_at, t.completed_at, t.created_at)::date <= %(end_date)s)
              AND (%(include_cancelled)s OR t.status <> 'cancelled')
        """

    @classmethod
    def _sale_subquery(cls) -> str:
        return """
            SELECT
                si.id::text AS movement_id,
                'sale' AS movement_type,
                'sale' AS source_type,
                s.created_at AS movement_date,
                p.id::text AS product_id,
                p.name AS product_name,
                p.sku AS product_sku,
                p.category_id::text AS category_id,
                c.name AS category_name,
                si.quantity::numeric AS quantity,
                'out' AS direction,
                s.storefront_id::text AS source_location_id,
                sf.name AS source_location_name,
                NULL::text AS destination_location_id,
                'Customer' AS destination_location_name,
                s.receipt_number AS reference_number,
                s.id::text AS reference_id,
                s.id::text AS sale_id,
                NULL::text AS transfer_id,
                NULL::text AS adjustment_id,
                u.name AS performed_by,
                CONCAT('Sale - ', s.type) AS notes,
                si.unit_price AS unit_cost,
                si.total_price AS total_value,
                NULL::text AS adjustment_type,
                s.type AS sale_type,
                NULL::text AS transfer_type,
                s.status AS status,
                u.id::text AS performed_by_id,
                CASE WHEN s.user_id IS NULL THEN 'system' ELSE 'manual' END AS performed_via,
                NULL::text AS performed_by_role
            FROM sales_items si
            JOIN sales s ON si.sale_id = s.id
            JOIN products p ON si.product_id = p.id
            LEFT JOIN categories c ON p.category_id = c.id
            LEFT JOIN storefronts sf ON s.storefront_id = sf.id
            LEFT JOIN users u ON s.user_id = u.id
            WHERE s.business_id = %(business_id)s
              AND (%(warehouse_id)s IS NULL OR s.storefront_id = %(warehouse_id)s)
              AND (%(product_id)s IS NULL OR si.product_id = %(product_id)s)
              AND (%(category_id)s IS NULL OR p.category_id = %(category_id)s)
              AND (%(start_date)s IS NULL OR s.created_at::date >= %(start_date)s)
              AND (%(end_date)s IS NULL OR s.created_at::date <= %(end_date)s)
        """
