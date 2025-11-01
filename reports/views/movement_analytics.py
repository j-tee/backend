"""
Movement Analytics Dashboard for Stock Movements Enhancement

This module provides high-level analytics and KPIs for stock movements,
designed to power executive dashboards and summary views.

Provides:
- Key performance indicators (KPIs)
- Movement trends over time
- Top movers (products with highest activity)
- Movement velocity metrics
- Warehouse performance comparison
- Shrinkage analysis
"""

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import connection
from django.core.cache import cache
from decimal import Decimal
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta


class MovementAnalyticsAPIView(APIView):
    """
    Movement Analytics Dashboard - Executive-level metrics and trends
    
    GET /reports/api/inventory/movements/analytics/
        ?start_date=2025-10-01
        &end_date=2025-10-31
        &warehouse_id=uuid  # Optional
        &category_id=uuid   # Optional
        &compare_previous=true  # Optional - compare with previous period
    
    Query Parameters:
    - start_date: YYYY-MM-DD (required)
    - end_date: YYYY-MM-DD (required)
    - warehouse_id: Optional warehouse filter
    - category_id: Optional category filter
    - compare_previous: Boolean - include previous period comparison (default: false)
    
    Response:
    {
        "success": true,
        "data": {
            "period": {
                "start_date": "2025-10-01",
                "end_date": "2025-10-31",
                "days": 31
            },
            "kpis": {
                "total_movements": 1547,
                "total_value": 458920.50,
                "unique_products": 234,
                "active_warehouses": 5,
                "movement_velocity": 49.9,
                "shrinkage_rate": 2.3
            },
            "movement_summary": {
                "sales": {
                    "quantity": 8450,
                    "value": 422500.00,
                    "transactions": 1245,
                    "percentage": 72.5
                },
                "transfers": {
                    "quantity": 2340,
                    "value": 70200.00,
                    "transactions": 234,
                    "percentage": 20.1
                },
                "adjustments": {
                    "quantity": 860,
                    "value": -33780.50,
                    "transactions": 68,
                    "percentage": 7.4
                }
            },
            "trends": {
                "daily": [...],
                "weekly": [...]
            },
            "top_movers": {
                "by_volume": [...],
                "by_value": [...],
                "by_velocity": [...]
            },
            "warehouse_performance": [...],
            "shrinkage_analysis": {
                "total_shrinkage": 267,
                "shrinkage_value": 13350.00,
                "top_shrinkage_products": [...],
                "shrinkage_by_type": {...}
            },
            "comparison": {
                "period": "previous",
                "changes": {...}
            }
        }
    }
    """
    permission_classes = [IsAuthenticated]
    
    # Cache duration in seconds (5 minutes)
    CACHE_DURATION = 300
    
    def get(self, request):
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        warehouse_id = request.GET.get('warehouse_id')
        category_id = request.GET.get('category_id')
        compare_previous = request.GET.get('compare_previous', 'false').lower() == 'true'
        
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
        
        # Generate cache key
        cache_key = self._generate_cache_key(
            str(business.id), start_date, end_date, warehouse_id, category_id
        )
        
        # Try to get from cache
        cached_data = cache.get(cache_key)
        if cached_data:
            return Response({
                'success': True,
                'data': cached_data,
                'cached': True
            })
        
        # Calculate period info
        period_info = self._calculate_period_info(start_date, end_date)
        
        # Get KPIs
        kpis = self._get_kpis(
            business_id=str(business.id),
            start_date=start_date,
            end_date=end_date,
            warehouse_id=warehouse_id,
            category_id=category_id
        )
        
        # Get movement summary
        movement_summary = self._get_movement_summary(
            business_id=str(business.id),
            start_date=start_date,
            end_date=end_date,
            warehouse_id=warehouse_id,
            category_id=category_id
        )
        
        # Get trends
        trends = self._get_trends(
            business_id=str(business.id),
            start_date=start_date,
            end_date=end_date,
            warehouse_id=warehouse_id,
            category_id=category_id
        )
        
        # Get top movers
        top_movers = self._get_top_movers(
            business_id=str(business.id),
            start_date=start_date,
            end_date=end_date,
            warehouse_id=warehouse_id,
            category_id=category_id
        )
        
        # Get warehouse performance
        warehouse_performance = self._get_warehouse_performance(
            business_id=str(business.id),
            start_date=start_date,
            end_date=end_date,
            category_id=category_id
        )
        
        # Get shrinkage analysis
        shrinkage_analysis = self._get_shrinkage_analysis(
            business_id=str(business.id),
            start_date=start_date,
            end_date=end_date,
            warehouse_id=warehouse_id,
            category_id=category_id
        )
        
        # Prepare response data
        response_data = {
            'period': period_info,
            'kpis': kpis,
            'movement_summary': movement_summary,
            'trends': trends,
            'top_movers': top_movers,
            'warehouse_performance': warehouse_performance,
            'shrinkage_analysis': shrinkage_analysis
        }
        
        # Add comparison if requested
        if compare_previous:
            comparison = self._get_period_comparison(
                business_id=str(business.id),
                start_date=start_date,
                end_date=end_date,
                current_kpis=kpis,
                warehouse_id=warehouse_id,
                category_id=category_id
            )
            response_data['comparison'] = comparison
        
        # Cache the result
        cache.set(cache_key, response_data, self.CACHE_DURATION)
        
        return Response({
            'success': True,
            'data': response_data,
            'cached': False
        })
    
    def _generate_cache_key(
        self,
        business_id: str,
        start_date: str,
        end_date: str,
        warehouse_id: Optional[str],
        category_id: Optional[str]
    ) -> str:
        """Generate cache key for analytics data"""
        key_parts = [
            'movement_analytics',
            business_id,
            start_date,
            end_date,
            warehouse_id or 'all',
            category_id or 'all'
        ]
        return ':'.join(key_parts)
    
    def _calculate_period_info(self, start_date: str, end_date: str) -> Dict[str, Any]:
        """Calculate period information"""
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        days = (end - start).days + 1
        
        return {
            'start_date': start_date,
            'end_date': end_date,
            'days': days
        }
    
    def _get_kpis(
        self,
        business_id: str,
        start_date: str,
        end_date: str,
        warehouse_id: Optional[str],
        category_id: Optional[str]
    ) -> Dict[str, Any]:
        """Calculate key performance indicators"""
        with connection.cursor() as cursor:
            # Build filters
            warehouse_filter = ""
            category_filter = ""
            params = [business_id, start_date, end_date]
            
            if warehouse_id:
                warehouse_filter = "AND warehouse_id = %s"
                params.append(warehouse_id)
            
            if category_id:
                category_filter = "AND p.category_id = %s"
            
            # Total movements, value, unique products
            cursor.execute(f"""
                WITH all_movements AS (
                    -- Sales
                    SELECT 
                        si.product_id,
                        s.storefront_id as warehouse_id,
                        si.quantity,
                        si.total as value
                    FROM sales_sale s
                    JOIN sales_saleitem si ON si.sale_id = s.id
                    WHERE s.business_id = %s
                        AND s.created_at::date >= %s
                        AND s.created_at::date <= %s
                        AND s.status != 'CANCELLED'
                        {warehouse_filter.replace('warehouse_id', 's.storefront_id') if warehouse_filter else ''}
                    
                    UNION ALL
                    
                    -- Transfers
                    SELECT 
                        ti.product_id,
                        COALESCE(t.destination_warehouse_id, t.destination_storefront_id) as warehouse_id,
                        ti.quantity,
                        ti.quantity * ti.cost as value
                    FROM inventory_transfer t
                    JOIN inventory_transferitem ti ON ti.transfer_id = t.id
                    WHERE t.business_id = %s
                        AND COALESCE(t.received_at, t.completed_at, t.created_at)::date >= %s
                        AND COALESCE(t.received_at, t.completed_at, t.created_at)::date <= %s
                        AND t.status != 'cancelled'
                    
                    UNION ALL
                    
                    -- Adjustments
                    SELECT 
                        sp.product_id,
                        w.id as warehouse_id,
                        sa.quantity,
                        sa.total_cost as value
                    FROM inventory_stockadjustment sa
                    JOIN inventory_stockproduct sp ON sa.stock_product_id = sp.id
                    JOIN inventory_warehouse w ON sp.warehouse_id = w.id
                    WHERE sa.business_id = %s
                        AND sa.created_at::date >= %s
                        AND sa.created_at::date <= %s
                        AND sa.adjustment_type NOT IN ('TRANSFER_IN', 'TRANSFER_OUT')
                        {warehouse_filter.replace('warehouse_id', 'w.id') if warehouse_filter else ''}
                )
                SELECT
                    COUNT(*) as total_movements,
                    COALESCE(SUM(ABS(value)), 0) as total_value,
                    COUNT(DISTINCT product_id) as unique_products,
                    COUNT(DISTINCT warehouse_id) as active_warehouses
                FROM all_movements
            """, params * 3)
            
            row = cursor.fetchone()
            
            total_movements = int(row[0]) if row[0] else 0
            total_value = float(row[1]) if row[1] else 0
            unique_products = int(row[2]) if row[2] else 0
            active_warehouses = int(row[3]) if row[3] else 0
            
            # Calculate movement velocity (movements per day)
            period_info = self._calculate_period_info(start_date, end_date)
            movement_velocity = round(total_movements / period_info['days'], 1) if period_info['days'] > 0 else 0
            
            # Calculate shrinkage rate
            shrinkage_rate = self._calculate_shrinkage_rate(
                business_id, start_date, end_date, warehouse_id, category_id
            )
            
            return {
                'total_movements': total_movements,
                'total_value': round(total_value, 2),
                'unique_products': unique_products,
                'active_warehouses': active_warehouses,
                'movement_velocity': movement_velocity,
                'shrinkage_rate': shrinkage_rate
            }
    
    def _calculate_shrinkage_rate(
        self,
        business_id: str,
        start_date: str,
        end_date: str,
        warehouse_id: Optional[str],
        category_id: Optional[str]
    ) -> float:
        """Calculate shrinkage rate as percentage of total movements"""
        shrinkage_types = ['THEFT', 'DAMAGE', 'EXPIRED', 'SPOILAGE', 'LOSS', 'WRITE_OFF']
        
        with connection.cursor() as cursor:
            where_conditions = [
                "sa.business_id = %s",
                "sa.created_at::date >= %s",
                "sa.created_at::date <= %s",
                "sa.adjustment_type = ANY(%s)"
            ]
            params = [business_id, start_date, end_date, shrinkage_types]
            
            if warehouse_id:
                where_conditions.append("w.id = %s")
                params.append(warehouse_id)
            
            where_clause = " AND ".join(where_conditions)
            
            cursor.execute(f"""
                SELECT COALESCE(SUM(ABS(sa.quantity)), 0) as shrinkage_quantity
                FROM inventory_stockadjustment sa
                JOIN inventory_stockproduct sp ON sa.stock_product_id = sp.id
                JOIN inventory_warehouse w ON sp.warehouse_id = w.id
                WHERE {where_clause}
            """, params)
            
            row = cursor.fetchone()
            shrinkage_quantity = float(row[0]) if row[0] else 0
            
            # Get total sales for comparison
            sales_conditions = [
                "s.business_id = %s",
                "s.created_at::date >= %s",
                "s.created_at::date <= %s",
                "s.status != 'CANCELLED'"
            ]
            sales_params = [business_id, start_date, end_date]
            
            if warehouse_id:
                sales_conditions.append("s.storefront_id = %s")
                sales_params.append(warehouse_id)
            
            sales_where = " AND ".join(sales_conditions)
            
            cursor.execute(f"""
                SELECT COALESCE(SUM(si.quantity), 0) as sales_quantity
                FROM sales_sale s
                JOIN sales_saleitem si ON si.sale_id = s.id
                WHERE {sales_where}
            """, sales_params)
            
            sales_row = cursor.fetchone()
            sales_quantity = float(sales_row[0]) if sales_row[0] else 0
            
            # Calculate shrinkage rate
            if sales_quantity > 0:
                shrinkage_rate = (shrinkage_quantity / sales_quantity) * 100
                return round(shrinkage_rate, 2)
            
            return 0.0
    
    def _get_movement_summary(
        self,
        business_id: str,
        start_date: str,
        end_date: str,
        warehouse_id: Optional[str],
        category_id: Optional[str]
    ) -> Dict[str, Any]:
        """Get high-level movement summary by type"""
        with connection.cursor() as cursor:
            warehouse_filter = ""
            params = [business_id, start_date, end_date]
            
            if warehouse_id:
                warehouse_filter = f"AND s.storefront_id = '{warehouse_id}'"
            
            # Sales
            cursor.execute(f"""
                SELECT
                    COALESCE(SUM(si.quantity), 0) as quantity,
                    COALESCE(SUM(si.total), 0) as value,
                    COUNT(DISTINCT s.id) as transactions
                FROM sales_sale s
                JOIN sales_saleitem si ON si.sale_id = s.id
                WHERE s.business_id = %s
                    AND s.created_at::date >= %s
                    AND s.created_at::date <= %s
                    AND s.status != 'CANCELLED'
                    {warehouse_filter}
            """, params)
            
            sales_row = cursor.fetchone()
            sales = {
                'quantity': float(sales_row[0]) if sales_row[0] else 0,
                'value': float(sales_row[1]) if sales_row[1] else 0,
                'transactions': int(sales_row[2]) if sales_row[2] else 0
            }
            
            # Transfers
            transfer_filter = ""
            if warehouse_id:
                transfer_filter = f"AND (t.source_warehouse_id = '{warehouse_id}' OR t.destination_warehouse_id = '{warehouse_id}' OR t.destination_storefront_id = '{warehouse_id}')"
            
            cursor.execute(f"""
                SELECT
                    COALESCE(SUM(ti.quantity), 0) as quantity,
                    COALESCE(SUM(ti.quantity * ti.cost), 0) as value,
                    COUNT(DISTINCT t.id) as transactions
                FROM inventory_transfer t
                JOIN inventory_transferitem ti ON ti.transfer_id = t.id
                WHERE t.business_id = %s
                    AND COALESCE(t.received_at, t.completed_at, t.created_at)::date >= %s
                    AND COALESCE(t.received_at, t.completed_at, t.created_at)::date <= %s
                    AND t.status != 'cancelled'
                    {transfer_filter}
            """, params)
            
            transfer_row = cursor.fetchone()
            transfers = {
                'quantity': float(transfer_row[0]) if transfer_row[0] else 0,
                'value': float(transfer_row[1]) if transfer_row[1] else 0,
                'transactions': int(transfer_row[2]) if transfer_row[2] else 0
            }
            
            # Adjustments
            adjustment_filter = ""
            if warehouse_id:
                adjustment_filter = f"AND w.id = '{warehouse_id}'"
            
            cursor.execute(f"""
                SELECT
                    COALESCE(SUM(ABS(sa.quantity)), 0) as quantity,
                    COALESCE(SUM(sa.total_cost), 0) as value,
                    COUNT(sa.id) as transactions
                FROM inventory_stockadjustment sa
                JOIN inventory_stockproduct sp ON sa.stock_product_id = sp.id
                JOIN inventory_warehouse w ON sp.warehouse_id = w.id
                WHERE sa.business_id = %s
                    AND sa.created_at::date >= %s
                    AND sa.created_at::date <= %s
                    AND sa.adjustment_type NOT IN ('TRANSFER_IN', 'TRANSFER_OUT')
                    {adjustment_filter}
            """, params)
            
            adjustment_row = cursor.fetchone()
            adjustments = {
                'quantity': float(adjustment_row[0]) if adjustment_row[0] else 0,
                'value': float(adjustment_row[1]) if adjustment_row[1] else 0,
                'transactions': int(adjustment_row[2]) if adjustment_row[2] else 0
            }
            
            # Calculate percentages
            total_quantity = sales['quantity'] + transfers['quantity'] + adjustments['quantity']
            
            if total_quantity > 0:
                sales['percentage'] = round((sales['quantity'] / total_quantity) * 100, 1)
                transfers['percentage'] = round((transfers['quantity'] / total_quantity) * 100, 1)
                adjustments['percentage'] = round((adjustments['quantity'] / total_quantity) * 100, 1)
            else:
                sales['percentage'] = 0
                transfers['percentage'] = 0
                adjustments['percentage'] = 0
            
            return {
                'sales': sales,
                'transfers': transfers,
                'adjustments': adjustments
            }
    
    def _get_trends(
        self,
        business_id: str,
        start_date: str,
        end_date: str,
        warehouse_id: Optional[str],
        category_id: Optional[str]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get movement trends over time (daily and weekly)"""
        # For simplicity, return daily trends
        # Weekly trends can be calculated by grouping daily data
        
        with connection.cursor() as cursor:
            warehouse_filter = ""
            params = [business_id, start_date, end_date]
            
            if warehouse_id:
                warehouse_filter = f"AND s.storefront_id = '{warehouse_id}'"
            
            # Daily sales trend
            cursor.execute(f"""
                SELECT
                    s.created_at::date as date,
                    COALESCE(SUM(si.quantity), 0) as quantity,
                    COALESCE(SUM(si.total), 0) as value,
                    COUNT(DISTINCT s.id) as transactions
                FROM sales_sale s
                JOIN sales_saleitem si ON si.sale_id = s.id
                WHERE s.business_id = %s
                    AND s.created_at::date >= %s
                    AND s.created_at::date <= %s
                    AND s.status != 'CANCELLED'
                    {warehouse_filter}
                GROUP BY s.created_at::date
                ORDER BY date
            """, params)
            
            daily_trends = []
            for row in cursor.fetchall():
                daily_trends.append({
                    'date': str(row[0]),
                    'quantity': float(row[1]),
                    'value': float(row[2]),
                    'transactions': int(row[3])
                })
            
            return {
                'daily': daily_trends,
                'weekly': []  # Can be calculated from daily if needed
            }
    
    def _get_top_movers(
        self,
        business_id: str,
        start_date: str,
        end_date: str,
        warehouse_id: Optional[str],
        category_id: Optional[str],
        limit: int = 10
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get top moving products by different metrics"""
        with connection.cursor() as cursor:
            warehouse_filter = ""
            params = [business_id, start_date, end_date, limit]
            
            if warehouse_id:
                warehouse_filter = f"AND s.storefront_id = '{warehouse_id}'"
            
            # Top by volume (quantity sold)
            cursor.execute(f"""
                SELECT
                    p.id::text,
                    p.name,
                    p.sku,
                    SUM(si.quantity) as total_quantity,
                    SUM(si.total) as total_value,
                    COUNT(DISTINCT s.id) as transaction_count
                FROM sales_sale s
                JOIN sales_saleitem si ON si.sale_id = s.id
                JOIN inventory_product p ON si.product_id = p.id
                WHERE s.business_id = %s
                    AND s.created_at::date >= %s
                    AND s.created_at::date <= %s
                    AND s.status != 'CANCELLED'
                    {warehouse_filter}
                GROUP BY p.id, p.name, p.sku
                ORDER BY total_quantity DESC
                LIMIT %s
            """, params)
            
            by_volume = []
            for row in cursor.fetchall():
                by_volume.append({
                    'product_id': row[0],
                    'product_name': row[1],
                    'sku': row[2],
                    'quantity': float(row[3]),
                    'value': float(row[4]),
                    'transactions': int(row[5])
                })
            
            # Top by value
            cursor.execute(f"""
                SELECT
                    p.id::text,
                    p.name,
                    p.sku,
                    SUM(si.quantity) as total_quantity,
                    SUM(si.total) as total_value,
                    COUNT(DISTINCT s.id) as transaction_count
                FROM sales_sale s
                JOIN sales_saleitem si ON si.sale_id = s.id
                JOIN inventory_product p ON si.product_id = p.id
                WHERE s.business_id = %s
                    AND s.created_at::date >= %s
                    AND s.created_at::date <= %s
                    AND s.status != 'CANCELLED'
                    {warehouse_filter}
                GROUP BY p.id, p.name, p.sku
                ORDER BY total_value DESC
                LIMIT %s
            """, params)
            
            by_value = []
            for row in cursor.fetchall():
                by_value.append({
                    'product_id': row[0],
                    'product_name': row[1],
                    'sku': row[2],
                    'quantity': float(row[3]),
                    'value': float(row[4]),
                    'transactions': int(row[5])
                })
            
            # Top by velocity (quantity per day)
            period_info = self._calculate_period_info(start_date, end_date)
            
            cursor.execute(f"""
                SELECT
                    p.id::text,
                    p.name,
                    p.sku,
                    SUM(si.quantity) as total_quantity,
                    SUM(si.total) as total_value,
                    COUNT(DISTINCT s.id) as transaction_count
                FROM sales_sale s
                JOIN sales_saleitem si ON si.sale_id = s.id
                JOIN inventory_product p ON si.product_id = p.id
                WHERE s.business_id = %s
                    AND s.created_at::date >= %s
                    AND s.created_at::date <= %s
                    AND s.status != 'CANCELLED'
                    {warehouse_filter}
                GROUP BY p.id, p.name, p.sku
                HAVING SUM(si.quantity) > 0
                ORDER BY (SUM(si.quantity) / %s) DESC
                LIMIT %s
            """, params[:3] + [period_info['days'], limit])
            
            by_velocity = []
            for row in cursor.fetchall():
                velocity = float(row[3]) / period_info['days'] if period_info['days'] > 0 else 0
                by_velocity.append({
                    'product_id': row[0],
                    'product_name': row[1],
                    'sku': row[2],
                    'quantity': float(row[3]),
                    'value': float(row[4]),
                    'transactions': int(row[5]),
                    'velocity': round(velocity, 2)
                })
            
            return {
                'by_volume': by_volume,
                'by_value': by_value,
                'by_velocity': by_velocity
            }
    
    def _get_warehouse_performance(
        self,
        business_id: str,
        start_date: str,
        end_date: str,
        category_id: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Get performance metrics per warehouse"""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    w.id::text,
                    w.name,
                    CASE WHEN w.is_storefront THEN 'storefront' ELSE 'warehouse' END as type,
                    COALESCE(SUM(si.quantity), 0) as sales_quantity,
                    COALESCE(SUM(si.total), 0) as sales_value,
                    COUNT(DISTINCT s.id) as transaction_count
                FROM inventory_warehouse w
                LEFT JOIN sales_sale s ON s.storefront_id = w.id 
                    AND s.business_id = %s
                    AND s.created_at::date >= %s
                    AND s.created_at::date <= %s
                    AND s.status != 'CANCELLED'
                LEFT JOIN sales_saleitem si ON si.sale_id = s.id
                WHERE w.business_id = %s
                GROUP BY w.id, w.name, w.is_storefront
                ORDER BY sales_quantity DESC
            """, [business_id, start_date, end_date, business_id])
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'warehouse_id': row[0],
                    'warehouse_name': row[1],
                    'warehouse_type': row[2],
                    'sales_quantity': float(row[3]),
                    'sales_value': float(row[4]),
                    'transaction_count': int(row[5])
                })
            
            return results
    
    def _get_shrinkage_analysis(
        self,
        business_id: str,
        start_date: str,
        end_date: str,
        warehouse_id: Optional[str],
        category_id: Optional[str]
    ) -> Dict[str, Any]:
        """Detailed shrinkage analysis"""
        shrinkage_types = ['THEFT', 'DAMAGE', 'EXPIRED', 'SPOILAGE', 'LOSS', 'WRITE_OFF']
        
        with connection.cursor() as cursor:
            where_conditions = [
                "sa.business_id = %s",
                "sa.created_at::date >= %s",
                "sa.created_at::date <= %s",
                "sa.adjustment_type = ANY(%s)"
            ]
            params = [business_id, start_date, end_date, shrinkage_types]
            
            if warehouse_id:
                where_conditions.append("w.id = %s")
                params.append(warehouse_id)
            
            where_clause = " AND ".join(where_conditions)
            
            # Total shrinkage
            cursor.execute(f"""
                SELECT
                    COALESCE(SUM(ABS(sa.quantity)), 0) as total_quantity,
                    COALESCE(SUM(ABS(sa.total_cost)), 0) as total_value
                FROM inventory_stockadjustment sa
                JOIN inventory_stockproduct sp ON sa.stock_product_id = sp.id
                JOIN inventory_warehouse w ON sp.warehouse_id = w.id
                WHERE {where_clause}
            """, params)
            
            row = cursor.fetchone()
            total_shrinkage = float(row[0]) if row[0] else 0
            shrinkage_value = float(row[1]) if row[1] else 0
            
            # Top shrinkage products
            cursor.execute(f"""
                SELECT
                    p.id::text,
                    p.name,
                    p.sku,
                    SUM(ABS(sa.quantity)) as shrinkage_quantity,
                    SUM(ABS(sa.total_cost)) as shrinkage_value
                FROM inventory_stockadjustment sa
                JOIN inventory_stockproduct sp ON sa.stock_product_id = sp.id
                JOIN inventory_product p ON sp.product_id = p.id
                JOIN inventory_warehouse w ON sp.warehouse_id = w.id
                WHERE {where_clause}
                GROUP BY p.id, p.name, p.sku
                ORDER BY shrinkage_quantity DESC
                LIMIT 10
            """, params)
            
            top_products = []
            for row in cursor.fetchall():
                top_products.append({
                    'product_id': row[0],
                    'product_name': row[1],
                    'sku': row[2],
                    'quantity': float(row[3]),
                    'value': float(row[4])
                })
            
            # Shrinkage by type
            cursor.execute(f"""
                SELECT
                    sa.adjustment_type,
                    SUM(ABS(sa.quantity)) as quantity,
                    SUM(ABS(sa.total_cost)) as value,
                    COUNT(sa.id) as count
                FROM inventory_stockadjustment sa
                JOIN inventory_stockproduct sp ON sa.stock_product_id = sp.id
                JOIN inventory_warehouse w ON sp.warehouse_id = w.id
                WHERE {where_clause}
                GROUP BY sa.adjustment_type
                ORDER BY quantity DESC
            """, params)
            
            by_type = {}
            for row in cursor.fetchall():
                by_type[row[0]] = {
                    'quantity': float(row[1]),
                    'value': float(row[2]),
                    'count': int(row[3])
                }
            
            return {
                'total_shrinkage': total_shrinkage,
                'shrinkage_value': shrinkage_value,
                'top_shrinkage_products': top_products,
                'shrinkage_by_type': by_type
            }
    
    def _get_period_comparison(
        self,
        business_id: str,
        start_date: str,
        end_date: str,
        current_kpis: Dict[str, Any],
        warehouse_id: Optional[str],
        category_id: Optional[str]
    ) -> Dict[str, Any]:
        """Compare current period with previous period"""
        # Calculate previous period dates
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        period_days = (end - start).days + 1
        
        prev_end = start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=period_days - 1)
        
        # Get previous period KPIs
        prev_kpis = self._get_kpis(
            business_id=business_id,
            start_date=prev_start.strftime('%Y-%m-%d'),
            end_date=prev_end.strftime('%Y-%m-%d'),
            warehouse_id=warehouse_id,
            category_id=category_id
        )
        
        # Calculate changes
        changes = {}
        for key in current_kpis:
            current_val = current_kpis[key]
            prev_val = prev_kpis.get(key, 0)
            
            if isinstance(current_val, (int, float)) and prev_val != 0:
                change_pct = ((current_val - prev_val) / prev_val) * 100
                changes[key] = {
                    'current': current_val,
                    'previous': prev_val,
                    'change': round(current_val - prev_val, 2),
                    'change_percentage': round(change_pct, 1)
                }
            else:
                changes[key] = {
                    'current': current_val,
                    'previous': prev_val,
                    'change': 0,
                    'change_percentage': 0
                }
        
        return {
            'period': 'previous',
            'previous_start_date': prev_start.strftime('%Y-%m-%d'),
            'previous_end_date': prev_end.strftime('%Y-%m-%d'),
            'changes': changes
        }
