"""
Product Movement Summary for Stock Movements Enhancement

This module provides detailed movement breakdowns for individual products,
showing sales, transfers, adjustments, and warehouse distribution.

This supports drill-down analysis where users can see:
- How much product moved via sales, transfers, adjustments
- Distribution across warehouses with percentages
- Net change calculations
- Value impact of movements
"""

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import connection
from decimal import Decimal
from typing import Dict, Any, List, Optional


class ProductMovementSummaryAPIView(APIView):
    """
    Product Movement Summary - Detailed breakdown by movement type
    
    GET /reports/api/inventory/products/{product_id}/movement-summary/
        ?start_date=2025-10-01
        &end_date=2025-10-31
        &warehouse_id=uuid  # Optional
    
    Query Parameters:
    - start_date: YYYY-MM-DD (required)
    - end_date: YYYY-MM-DD (required)
    - warehouse_id: Optional warehouse filter
    
    Response:
    {
        "success": true,
        "data": {
            "product": {
                "id": "uuid",
                "name": "Samsung TV 43\"",
                "sku": "ELEC-0005",
                "category": "Electronics"
            },
            "period": {
                "start_date": "2025-10-01",
                "end_date": "2025-10-31"
            },
            "movement_breakdown": {
                "sales": {
                    "quantity": -145.0,
                    "transaction_count": 87,
                    "value": 72500.00,
                    "percentage": 65.5
                },
                "transfers": {
                    "in": {
                        "quantity": 50.0,
                        "transaction_count": 3,
                        "value": 15000.00
                    },
                    "out": {
                        "quantity": -30.0,
                        "transaction_count": 2,
                        "value": -9000.00
                    },
                    "net": {
                        "quantity": 20.0,
                        "transaction_count": 5,
                        "value": 6000.00
                    },
                    "percentage": 9.0
                },
                "adjustments": {
                    "positive": {
                        "quantity": 25.0,
                        "transaction_count": 5,
                        "value": 7500.00
                    },
                    "negative": {
                        "quantity": -12.0,
                        "transaction_count": 3,
                        "value": -3600.00
                    },
                    "net": {
                        "quantity": 13.0,
                        "transaction_count": 8,
                        "value": 3900.00
                    },
                    "percentage": 5.9,
                    "by_type": {
                        "RESTOCK": {"quantity": 25.0, "count": 5},
                        "DAMAGE": {"quantity": -8.0, "count": 2},
                        "THEFT": {"quantity": -4.0, "count": 1}
                    }
                },
                "net_change": {
                    "quantity": -112.0,
                    "value": -56100.00
                }
            },
            "warehouse_distribution": [
                {
                    "warehouse_id": "uuid1",
                    "warehouse_name": "Main Warehouse",
                    "warehouse_type": "warehouse",
                    "sales": -85.0,
                    "transfers_net": 15.0,
                    "adjustments_net": 5.0,
                    "total_movement": -65.0,
                    "percentage": 58.0,
                    "current_stock": 120.0
                },
                {
                    "warehouse_id": "uuid2",
                    "warehouse_name": "Retail Store",
                    "warehouse_type": "storefront",
                    "sales": -60.0,
                    "transfers_net": 5.0,
                    "adjustments_net": 8.0,
                    "total_movement": -47.0,
                    "percentage": 42.0,
                    "current_stock": 80.0
                }
            ]
        }
    }
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, product_id):
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        warehouse_id = request.GET.get('warehouse_id')
        
        # Validation
        if not start_date or not end_date:
            return Response({
                'success': False,
                'error': 'start_date and end_date are required'
            }, status=400)
        
        # Get business
        business = request.user.primary_business
        if not business:
            return Response({
                'success': False,
                'error': 'No business associated with user'
            }, status=400)
        
        # Get product info
        product_info = self._get_product_info(product_id, str(business.id))
        if not product_info:
            return Response({
                'success': False,
                'error': 'Product not found'
            }, status=404)
        
        # Get movement breakdown
        breakdown = self._get_movement_breakdown(
            product_id=product_id,
            business_id=str(business.id),
            start_date=start_date,
            end_date=end_date,
            warehouse_id=warehouse_id
        )
        
        # Get warehouse distribution
        distribution = self._get_warehouse_distribution(
            product_id=product_id,
            business_id=str(business.id),
            start_date=start_date,
            end_date=end_date,
            warehouse_id=warehouse_id
        )
        
        return Response({
            'success': True,
            'data': {
                'product': product_info,
                'period': {
                    'start_date': start_date,
                    'end_date': end_date
                },
                'movement_breakdown': breakdown,
                'warehouse_distribution': distribution
            }
        })
    
    def _get_product_info(self, product_id: str, business_id: str) -> Optional[Dict[str, Any]]:
        """Get basic product information"""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    p.id::text,
                    p.name,
                    p.sku,
                    c.name as category_name
                FROM inventory_product p
                LEFT JOIN inventory_category c ON p.category_id = c.id
                WHERE p.id = %s AND p.business_id = %s
            """, [product_id, business_id])
            
            row = cursor.fetchone()
            if not row:
                return None
            
            return {
                'id': row[0],
                'name': row[1],
                'sku': row[2],
                'category': row[3]
            }
    
    def _get_movement_breakdown(
        self,
        product_id: str,
        business_id: str,
        start_date: str,
        end_date: str,
        warehouse_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate movement breakdown by type (sales, transfers, adjustments)
        """
        # Get sales data
        sales_data = self._get_sales_breakdown(
            product_id, business_id, start_date, end_date, warehouse_id
        )
        
        # Get transfer data
        transfer_data = self._get_transfer_breakdown(
            product_id, business_id, start_date, end_date, warehouse_id
        )
        
        # Get adjustment data
        adjustment_data = self._get_adjustment_breakdown(
            product_id, business_id, start_date, end_date, warehouse_id
        )
        
        # Calculate net change
        net_quantity = (
            sales_data['quantity'] +
            transfer_data['net']['quantity'] +
            adjustment_data['net']['quantity']
        )
        
        net_value = (
            sales_data['value'] +
            transfer_data['net']['value'] +
            adjustment_data['net']['value']
        )
        
        # Calculate percentages (based on absolute movement)
        total_absolute_movement = (
            abs(sales_data['quantity']) +
            abs(transfer_data['net']['quantity']) +
            abs(adjustment_data['net']['quantity'])
        )
        
        if total_absolute_movement > 0:
            sales_data['percentage'] = round(
                (abs(sales_data['quantity']) / total_absolute_movement) * 100, 1
            )
            transfer_data['percentage'] = round(
                (abs(transfer_data['net']['quantity']) / total_absolute_movement) * 100, 1
            )
            adjustment_data['percentage'] = round(
                (abs(adjustment_data['net']['quantity']) / total_absolute_movement) * 100, 1
            )
        else:
            sales_data['percentage'] = 0
            transfer_data['percentage'] = 0
            adjustment_data['percentage'] = 0
        
        return {
            'sales': sales_data,
            'transfers': transfer_data,
            'adjustments': adjustment_data,
            'net_change': {
                'quantity': float(net_quantity),
                'value': float(net_value)
            }
        }
    
    def _get_sales_breakdown(
        self,
        product_id: str,
        business_id: str,
        start_date: str,
        end_date: str,
        warehouse_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get sales movement data"""
        with connection.cursor() as cursor:
            where_conditions = [
                "s.business_id = %s",
                "si.product_id = %s",
                "s.created_at::date >= %s",
                "s.created_at::date <= %s",
                "s.status != 'CANCELLED'"
            ]
            params = [business_id, product_id, start_date, end_date]
            
            if warehouse_id:
                where_conditions.append("s.storefront_id = %s")
                params.append(warehouse_id)
            
            where_clause = " AND ".join(where_conditions)
            
            cursor.execute(f"""
                SELECT
                    COALESCE(SUM(si.quantity), 0) as total_quantity,
                    COUNT(DISTINCT s.id) as transaction_count,
                    COALESCE(SUM(si.total), 0) as total_value
                FROM sales_sale s
                JOIN sales_saleitem si ON si.sale_id = s.id
                WHERE {where_clause}
            """, params)
            
            row = cursor.fetchone()
            
            return {
                'quantity': -float(row[0]) if row[0] else 0,  # Negative for sales
                'transaction_count': int(row[1]) if row[1] else 0,
                'value': float(row[2]) if row[2] else 0
            }
    
    def _get_transfer_breakdown(
        self,
        product_id: str,
        business_id: str,
        start_date: str,
        end_date: str,
        warehouse_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get transfer movement data (in/out/net)"""
        with connection.cursor() as cursor:
            # Build base WHERE conditions
            base_conditions = [
                "t.business_id = %s",
                "ti.product_id = %s",
                "COALESCE(t.received_at, t.completed_at, t.created_at)::date >= %s",
                "COALESCE(t.received_at, t.completed_at, t.created_at)::date <= %s",
                "t.status != 'cancelled'"
            ]
            base_params = [business_id, product_id, start_date, end_date]
            
            # Transfers IN
            in_conditions = base_conditions.copy()
            in_params = base_params.copy()
            
            if warehouse_id:
                in_conditions.append("(t.destination_warehouse_id = %s OR t.destination_storefront_id = %s)")
                in_params.extend([warehouse_id, warehouse_id])
            
            in_where = " AND ".join(in_conditions)
            
            cursor.execute(f"""
                SELECT
                    COALESCE(SUM(ti.quantity), 0) as total_quantity,
                    COUNT(DISTINCT t.id) as transaction_count,
                    COALESCE(SUM(ti.quantity * ti.cost), 0) as total_value
                FROM inventory_transfer t
                JOIN inventory_transferitem ti ON ti.transfer_id = t.id
                WHERE {in_where}
            """, in_params)
            
            in_row = cursor.fetchone()
            transfers_in = {
                'quantity': float(in_row[0]) if in_row[0] else 0,
                'transaction_count': int(in_row[1]) if in_row[1] else 0,
                'value': float(in_row[2]) if in_row[2] else 0
            }
            
            # Transfers OUT
            out_conditions = base_conditions.copy()
            out_params = base_params.copy()
            
            if warehouse_id:
                out_conditions.append("t.source_warehouse_id = %s")
                out_params.append(warehouse_id)
            
            out_where = " AND ".join(out_conditions)
            
            cursor.execute(f"""
                SELECT
                    COALESCE(SUM(ti.quantity), 0) as total_quantity,
                    COUNT(DISTINCT t.id) as transaction_count,
                    COALESCE(SUM(ti.quantity * ti.cost), 0) as total_value
                FROM inventory_transfer t
                JOIN inventory_transferitem ti ON ti.transfer_id = t.id
                WHERE {out_where}
            """, out_params)
            
            out_row = cursor.fetchone()
            transfers_out = {
                'quantity': -float(out_row[0]) if out_row[0] else 0,  # Negative for outbound
                'transaction_count': int(out_row[1]) if out_row[1] else 0,
                'value': -float(out_row[2]) if out_row[2] else 0
            }
            
            # Net transfers
            net_quantity = transfers_in['quantity'] + transfers_out['quantity']
            net_value = transfers_in['value'] + transfers_out['value']
            net_count = transfers_in['transaction_count'] + transfers_out['transaction_count']
            
            return {
                'in': transfers_in,
                'out': transfers_out,
                'net': {
                    'quantity': float(net_quantity),
                    'transaction_count': int(net_count),
                    'value': float(net_value)
                }
            }
    
    def _get_adjustment_breakdown(
        self,
        product_id: str,
        business_id: str,
        start_date: str,
        end_date: str,
        warehouse_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get adjustment movement data (positive/negative/net + by type)"""
        with connection.cursor() as cursor:
            where_conditions = [
                "sa.business_id = %s",
                "sp.product_id = %s",
                "sa.created_at::date >= %s",
                "sa.created_at::date <= %s",
                "sa.adjustment_type NOT IN ('TRANSFER_IN', 'TRANSFER_OUT')"
            ]
            params = [business_id, product_id, start_date, end_date]
            
            if warehouse_id:
                where_conditions.append("w.id = %s")
                params.append(warehouse_id)
            
            where_clause = " AND ".join(where_conditions)
            
            # Positive adjustments
            cursor.execute(f"""
                SELECT
                    COALESCE(SUM(sa.quantity), 0) as total_quantity,
                    COUNT(sa.id) as transaction_count,
                    COALESCE(SUM(sa.total_cost), 0) as total_value
                FROM inventory_stockadjustment sa
                JOIN inventory_stockproduct sp ON sa.stock_product_id = sp.id
                JOIN inventory_warehouse w ON sp.warehouse_id = w.id
                WHERE {where_clause} AND sa.quantity > 0
            """, params)
            
            pos_row = cursor.fetchone()
            positive = {
                'quantity': float(pos_row[0]) if pos_row[0] else 0,
                'transaction_count': int(pos_row[1]) if pos_row[1] else 0,
                'value': float(pos_row[2]) if pos_row[2] else 0
            }
            
            # Negative adjustments
            cursor.execute(f"""
                SELECT
                    COALESCE(SUM(sa.quantity), 0) as total_quantity,
                    COUNT(sa.id) as transaction_count,
                    COALESCE(SUM(sa.total_cost), 0) as total_value
                FROM inventory_stockadjustment sa
                JOIN inventory_stockproduct sp ON sa.stock_product_id = sp.id
                JOIN inventory_warehouse w ON sp.warehouse_id = w.id
                WHERE {where_clause} AND sa.quantity < 0
            """, params)
            
            neg_row = cursor.fetchone()
            negative = {
                'quantity': float(neg_row[0]) if neg_row[0] else 0,
                'transaction_count': int(neg_row[1]) if neg_row[1] else 0,
                'value': float(neg_row[2]) if neg_row[2] else 0
            }
            
            # By adjustment type
            cursor.execute(f"""
                SELECT
                    sa.adjustment_type,
                    SUM(sa.quantity) as total_quantity,
                    COUNT(sa.id) as transaction_count
                FROM inventory_stockadjustment sa
                JOIN inventory_stockproduct sp ON sa.stock_product_id = sp.id
                JOIN inventory_warehouse w ON sp.warehouse_id = w.id
                WHERE {where_clause}
                GROUP BY sa.adjustment_type
                ORDER BY ABS(SUM(sa.quantity)) DESC
            """, params)
            
            by_type = {}
            for row in cursor.fetchall():
                by_type[row[0]] = {
                    'quantity': float(row[1]),
                    'count': int(row[2])
                }
            
            # Net adjustments
            net_quantity = positive['quantity'] + negative['quantity']
            net_value = positive['value'] + negative['value']
            net_count = positive['transaction_count'] + negative['transaction_count']
            
            return {
                'positive': positive,
                'negative': negative,
                'net': {
                    'quantity': float(net_quantity),
                    'transaction_count': int(net_count),
                    'value': float(net_value)
                },
                'by_type': by_type
            }
    
    def _get_warehouse_distribution(
        self,
        product_id: str,
        business_id: str,
        start_date: str,
        end_date: str,
        warehouse_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get movement distribution across warehouses/storefronts
        Shows how movement is distributed geographically
        """
        with connection.cursor() as cursor:
            # Build comprehensive query that gets all movements per warehouse
            # Uses UNION to combine sales, transfers in/out, and adjustments
            
            # Build warehouse filter for all subqueries
            warehouse_filter = ""
            if warehouse_id:
                warehouse_filter = f"AND warehouse_id = '{warehouse_id}'"
            
            query = f"""
            WITH warehouse_movements AS (
                -- Sales from storefronts
                SELECT 
                    s.storefront_id as warehouse_id,
                    -SUM(si.quantity) as sales_quantity,
                    0 as transfers_in,
                    0 as transfers_out,
                    0 as adjustments_positive,
                    0 as adjustments_negative
                FROM sales_sale s
                JOIN sales_saleitem si ON si.sale_id = s.id
                WHERE s.business_id = %s
                    AND si.product_id = %s
                    AND s.created_at::date >= %s
                    AND s.created_at::date <= %s
                    AND s.status != 'CANCELLED'
                    {warehouse_filter.replace('warehouse_id', 's.storefront_id') if warehouse_filter else ''}
                GROUP BY s.storefront_id
                
                UNION ALL
                
                -- Transfers IN (destination warehouse)
                SELECT 
                    COALESCE(t.destination_warehouse_id, t.destination_storefront_id) as warehouse_id,
                    0 as sales_quantity,
                    SUM(ti.quantity) as transfers_in,
                    0 as transfers_out,
                    0 as adjustments_positive,
                    0 as adjustments_negative
                FROM inventory_transfer t
                JOIN inventory_transferitem ti ON ti.transfer_id = t.id
                WHERE t.business_id = %s
                    AND ti.product_id = %s
                    AND COALESCE(t.received_at, t.completed_at, t.created_at)::date >= %s
                    AND COALESCE(t.received_at, t.completed_at, t.created_at)::date <= %s
                    AND t.status != 'cancelled'
                    AND COALESCE(t.destination_warehouse_id, t.destination_storefront_id) IS NOT NULL
                    {warehouse_filter.replace('warehouse_id', 'COALESCE(t.destination_warehouse_id, t.destination_storefront_id)') if warehouse_filter else ''}
                GROUP BY COALESCE(t.destination_warehouse_id, t.destination_storefront_id)
                
                UNION ALL
                
                -- Transfers OUT (source warehouse)
                SELECT 
                    t.source_warehouse_id as warehouse_id,
                    0 as sales_quantity,
                    0 as transfers_in,
                    -SUM(ti.quantity) as transfers_out,
                    0 as adjustments_positive,
                    0 as adjustments_negative
                FROM inventory_transfer t
                JOIN inventory_transferitem ti ON ti.transfer_id = t.id
                WHERE t.business_id = %s
                    AND ti.product_id = %s
                    AND COALESCE(t.received_at, t.completed_at, t.created_at)::date >= %s
                    AND COALESCE(t.received_at, t.completed_at, t.created_at)::date <= %s
                    AND t.status != 'cancelled'
                    AND t.source_warehouse_id IS NOT NULL
                    {warehouse_filter.replace('warehouse_id', 't.source_warehouse_id') if warehouse_filter else ''}
                GROUP BY t.source_warehouse_id
                
                UNION ALL
                
                -- Positive adjustments
                SELECT 
                    w.id as warehouse_id,
                    0 as sales_quantity,
                    0 as transfers_in,
                    0 as transfers_out,
                    SUM(CASE WHEN sa.quantity > 0 THEN sa.quantity ELSE 0 END) as adjustments_positive,
                    0 as adjustments_negative
                FROM inventory_stockadjustment sa
                JOIN inventory_stockproduct sp ON sa.stock_product_id = sp.id
                JOIN inventory_warehouse w ON sp.warehouse_id = w.id
                WHERE sa.business_id = %s
                    AND sp.product_id = %s
                    AND sa.created_at::date >= %s
                    AND sa.created_at::date <= %s
                    AND sa.adjustment_type NOT IN ('TRANSFER_IN', 'TRANSFER_OUT')
                    {warehouse_filter.replace('warehouse_id', 'w.id') if warehouse_filter else ''}
                GROUP BY w.id
                
                UNION ALL
                
                -- Negative adjustments
                SELECT 
                    w.id as warehouse_id,
                    0 as sales_quantity,
                    0 as transfers_in,
                    0 as transfers_out,
                    0 as adjustments_positive,
                    SUM(CASE WHEN sa.quantity < 0 THEN sa.quantity ELSE 0 END) as adjustments_negative
                FROM inventory_stockadjustment sa
                JOIN inventory_stockproduct sp ON sa.stock_product_id = sp.id
                JOIN inventory_warehouse w ON sp.warehouse_id = w.id
                WHERE sa.business_id = %s
                    AND sp.product_id = %s
                    AND sa.created_at::date >= %s
                    AND sa.created_at::date <= %s
                    AND sa.adjustment_type NOT IN ('TRANSFER_IN', 'TRANSFER_OUT')
                    {warehouse_filter.replace('warehouse_id', 'w.id') if warehouse_filter else ''}
                GROUP BY w.id
            ),
            aggregated_movements AS (
                SELECT
                    warehouse_id,
                    SUM(sales_quantity) as total_sales,
                    SUM(transfers_in + transfers_out) as total_transfers_net,
                    SUM(adjustments_positive + adjustments_negative) as total_adjustments_net,
                    SUM(sales_quantity + transfers_in + transfers_out + adjustments_positive + adjustments_negative) as total_movement
                FROM warehouse_movements
                WHERE warehouse_id IS NOT NULL
                GROUP BY warehouse_id
            )
            SELECT
                w.id::text as warehouse_id,
                w.name as warehouse_name,
                CASE 
                    WHEN w.is_storefront THEN 'storefront'
                    ELSE 'warehouse'
                END as warehouse_type,
                COALESCE(am.total_sales, 0) as sales,
                COALESCE(am.total_transfers_net, 0) as transfers_net,
                COALESCE(am.total_adjustments_net, 0) as adjustments_net,
                COALESCE(am.total_movement, 0) as total_movement,
                COALESCE(sp.current_quantity, 0) as current_stock
            FROM aggregated_movements am
            JOIN inventory_warehouse w ON am.warehouse_id = w.id
            LEFT JOIN inventory_stockproduct sp ON sp.warehouse_id = w.id AND sp.product_id = %s
            WHERE w.business_id = %s
            ORDER BY ABS(am.total_movement) DESC
            """
            
            # Execute with parameters (6 sets of the same 4 params + 2 final params)
            params = [
                business_id, product_id, start_date, end_date,  # Sales
                business_id, product_id, start_date, end_date,  # Transfers IN
                business_id, product_id, start_date, end_date,  # Transfers OUT
                business_id, product_id, start_date, end_date,  # Adjustments positive
                business_id, product_id, start_date, end_date,  # Adjustments negative
                product_id, business_id  # Final JOIN
            ]
            
            cursor.execute(query, params)
            
            results = []
            total_absolute_movement = 0
            
            # First pass: collect data and calculate total
            rows = cursor.fetchall()
            for row in rows:
                total_absolute_movement += abs(float(row[6]))
            
            # Second pass: build results with percentages
            for row in rows:
                total_movement = float(row[6])
                percentage = 0
                if total_absolute_movement > 0:
                    percentage = round((abs(total_movement) / total_absolute_movement) * 100, 1)
                
                results.append({
                    'warehouse_id': row[0],
                    'warehouse_name': row[1],
                    'warehouse_type': row[2],
                    'sales': float(row[3]),
                    'transfers_net': float(row[4]),
                    'adjustments_net': float(row[5]),
                    'total_movement': total_movement,
                    'percentage': percentage,
                    'current_stock': float(row[7])
                })
            
            return results
