"""
Product Search and Quick Filters for Stock Movements

This module provides endpoints for:
1. Product autocomplete search
2. Quick filter presets (top sellers, most adjusted, etc.)

These endpoints support the frontend Stock Movements enhancement,
allowing users to quickly find and filter products for drill-down analysis.
"""

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q, F, Value, IntegerField, Case, When, Sum, Count
from django.db import connection
from decimal import Decimal
from typing import List, Dict, Any

from inventory.models import Product, StockProduct
from reports.services.movement_tracker import MovementTracker


class ProductSearchAPIView(APIView):
    """
    Product search with relevance ranking for autocomplete
    
    GET /reports/api/inventory/products/search/?q=samsung&limit=10
    
    Query Parameters:
    - q: Search query (minimum 2 characters)
    - limit: Maximum results to return (default: 10, max: 50)
    
    Response:
    {
        "success": true,
        "data": [
            {
                "id": "uuid",
                "name": "Samsung TV 43\"",
                "sku": "ELEC-0005",
                "category": "Electronics",
                "current_stock": 404
            }
        ]
    }
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        query = request.GET.get('q', '').strip()
        limit = min(int(request.GET.get('limit', 10)), 50)  # Max 50 results
        
        # Validation
        if len(query) < 2:
            return Response({
                'success': False,
                'error': 'Search query must be at least 2 characters'
            }, status=400)
        
        # Get business from user
        business = request.user.primary_business
        if not business:
            return Response({
                'success': False,
                'error': 'No business associated with user'
            }, status=400)
        
        # Search with relevance scoring
        # Priority: Exact match > Starts with > Contains
        products = Product.objects.filter(
            business=business
        ).filter(
            Q(name__icontains=query) |
            Q(sku__icontains=query) |
            Q(description__icontains=query)
        ).annotate(
            # Relevance scoring for ranking
            name_exact=Case(
                When(name__iexact=query, then=Value(10)),
                default=Value(0),
                output_field=IntegerField()
            ),
            name_startswith=Case(
                When(name__istartswith=query, then=Value(7)),
                default=Value(0),
                output_field=IntegerField()
            ),
            name_contains=Case(
                When(name__icontains=query, then=Value(3)),
                default=Value(0),
                output_field=IntegerField()
            ),
            sku_exact=Case(
                When(sku__iexact=query, then=Value(8)),
                default=Value(0),
                output_field=IntegerField()
            ),
            sku_startswith=Case(
                When(sku__istartswith=query, then=Value(5)),
                default=Value(0),
                output_field=IntegerField()
            ),
            relevance=F('name_exact') + F('name_startswith') + F('name_contains') + 
                      F('sku_exact') + F('sku_startswith')
        ).order_by('-relevance', 'name')[:limit]
        
        # Calculate current stock for each product
        results = []
        for product in products:
            current_stock = StockProduct.objects.filter(
                product=product
            ).aggregate(total=Sum('current_quantity'))['total'] or 0
            
            results.append({
                'id': str(product.id),
                'name': product.name,
                'sku': product.sku,
                'category': product.category.name if product.category else None,
                'current_stock': float(current_stock)
            })
        
        return Response({
            'success': True,
            'data': results
        })


class QuickFiltersAPIView(APIView):
    """
    Quick filter presets for common product filtering scenarios
    
    GET /reports/api/inventory/movements/quick-filters/
        ?filter_type=top_sellers
        &start_date=2025-10-01
        &end_date=2025-10-31
        &limit=10
    
    Query Parameters:
    - filter_type: top_sellers|most_adjusted|high_transfers|shrinkage (required)
    - start_date: YYYY-MM-DD (required)
    - end_date: YYYY-MM-DD (required)
    - limit: Maximum products to return (default: 10, max: 50)
    - warehouse_id: Optional warehouse filter
    - category_id: Optional category filter
    
    Response:
    {
        "success": true,
        "data": {
            "filter_type": "top_sellers",
            "product_ids": ["uuid1", "uuid2", "uuid3"],
            "count": 3,
            "details": [
                {
                    "product_id": "uuid1",
                    "product_name": "Samsung TV 43\"",
                    "sku": "ELEC-0005",
                    "metric_value": 145,
                    "metric_label": "units_sold"
                }
            ]
        }
    }
    """
    permission_classes = [IsAuthenticated]
    
    VALID_FILTERS = ['top_sellers', 'most_adjusted', 'high_transfers', 'shrinkage']
    
    def get(self, request):
        filter_type = request.GET.get('filter_type')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        limit = min(int(request.GET.get('limit', 10)), 50)
        warehouse_id = request.GET.get('warehouse_id')
        category_id = request.GET.get('category_id')
        
        # Validation
        if filter_type not in self.VALID_FILTERS:
            return Response({
                'success': False,
                'error': f'Invalid filter_type. Must be one of: {", ".join(self.VALID_FILTERS)}'
            }, status=400)
        
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
        
        # Call appropriate filter method
        method_name = f'_get_{filter_type}'
        method = getattr(self, method_name)
        details = method(
            business_id=str(business.id),
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            warehouse_id=warehouse_id,
            category_id=category_id
        )
        
        # Extract just the product IDs
        product_ids = [item['product_id'] for item in details]
        
        return Response({
            'success': True,
            'data': {
                'filter_type': filter_type,
                'product_ids': product_ids,
                'count': len(product_ids),
                'details': details  # Include full details for frontend display
            }
        })
    
    def _get_top_sellers(
        self,
        business_id: str,
        start_date: str,
        end_date: str,
        limit: int,
        warehouse_id: str = None,
        category_id: str = None
    ) -> List[Dict[str, Any]]:
        """
        Find products with highest sales volume
        
        Returns list of products sorted by quantity sold (descending)
        """
        with connection.cursor() as cursor:
            # Build WHERE conditions
            where_conditions = [
                "s.business_id = %s",
                "s.created_at::date >= %s",
                "s.created_at::date <= %s",
                "s.status != 'CANCELLED'"  # Exclude cancelled sales
            ]
            params = [business_id, start_date, end_date]
            
            if warehouse_id:
                where_conditions.append("s.storefront_id = %s")
                params.append(warehouse_id)
            
            if category_id:
                where_conditions.append("p.category_id = %s")
                params.append(category_id)
            
            where_clause = " AND ".join(where_conditions)
            
            cursor.execute(f"""
                SELECT
                    p.id::text AS product_id,
                    p.name AS product_name,
                    p.sku AS product_sku,
                    SUM(si.quantity) AS total_sold
                FROM sales s
                JOIN sales_items si ON si.sale_id = s.id
                JOIN products p ON si.product_id = p.id
                WHERE {where_clause}
                GROUP BY p.id, p.name, p.sku
                ORDER BY total_sold DESC
                LIMIT %s
            """, params + [limit])
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'product_id': row[0],
                    'product_name': row[1],
                    'sku': row[2],
                    'metric_value': float(row[3]),
                    'metric_label': 'units_sold'
                })
            
            return results
    
    def _get_most_adjusted(
        self,
        business_id: str,
        start_date: str,
        end_date: str,
        limit: int,
        warehouse_id: str = None,
        category_id: str = None
    ) -> List[Dict[str, Any]]:
        """
        Find products with most adjustment activity (count of adjustments)
        
        Returns list of products sorted by adjustment count (descending)
        """
        with connection.cursor() as cursor:
            where_conditions = [
                "sa.business_id = %s",
                "sa.created_at::date >= %s",
                "sa.created_at::date <= %s",
                "sa.adjustment_type NOT IN ('TRANSFER_IN', 'TRANSFER_OUT')"
            ]
            params = [business_id, start_date, end_date]
            
            if warehouse_id:
                where_conditions.append("w.id = %s")
                params.append(warehouse_id)
            
            if category_id:
                where_conditions.append("p.category_id = %s")
                params.append(category_id)
            
            where_clause = " AND ".join(where_conditions)
            
            cursor.execute(f"""
                SELECT
                    p.id::text AS product_id,
                    p.name AS product_name,
                    p.sku AS product_sku,
                    COUNT(sa.id) AS adjustment_count
                FROM stock_adjustments sa
                JOIN stock_products sp ON sa.stock_product_id = sp.id
                JOIN products p ON sp.product_id = p.id
                JOIN warehouses w ON sp.warehouse_id = w.id
                WHERE {where_clause}
                GROUP BY p.id, p.name, p.sku
                ORDER BY adjustment_count DESC
                LIMIT %s
            """, params + [limit])
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'product_id': row[0],
                    'product_name': row[1],
                    'sku': row[2],
                    'metric_value': int(row[3]),
                    'metric_label': 'adjustment_count'
                })
            
            return results
    
    def _get_high_transfers(
        self,
        business_id: str,
        start_date: str,
        end_date: str,
        limit: int,
        warehouse_id: str = None,
        category_id: str = None
    ) -> List[Dict[str, Any]]:
        """
        Find products with high transfer activity (count of transfers)
        
        Returns list of products sorted by transfer count (descending)
        """
        with connection.cursor() as cursor:
            where_conditions = [
                "t.business_id = %s",
                "COALESCE(t.received_at, t.completed_at, t.created_at)::date >= %s",
                "COALESCE(t.received_at, t.completed_at, t.created_at)::date <= %s",
                "t.status != 'cancelled'"
            ]
            params = [business_id, start_date, end_date]
            
            if warehouse_id:
                where_conditions.append("(t.source_warehouse_id = %s OR t.destination_warehouse_id = %s OR t.destination_storefront_id = %s)")
                params.extend([warehouse_id, warehouse_id, warehouse_id])
            
            if category_id:
                where_conditions.append("p.category_id = %s")
                params.append(category_id)
            
            where_clause = " AND ".join(where_conditions)
            
            cursor.execute(f"""
                SELECT
                    p.id::text AS product_id,
                    p.name AS product_name,
                    p.sku AS product_sku,
                    COUNT(DISTINCT t.id) AS transfer_count
                FROM inventory_transfer t
                JOIN inventory_transfer_item ti ON ti.transfer_id = t.id
                JOIN products p ON ti.product_id = p.id
                WHERE {where_clause}
                GROUP BY p.id, p.name, p.sku
                ORDER BY transfer_count DESC
                LIMIT %s
            """, params + [limit])
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'product_id': row[0],
                    'product_name': row[1],
                    'sku': row[2],
                    'metric_value': int(row[3]),
                    'metric_label': 'transfer_count'
                })
            
            return results
    
    def _get_shrinkage(
        self,
        business_id: str,
        start_date: str,
        end_date: str,
        limit: int,
        warehouse_id: str = None,
        category_id: str = None
    ) -> List[Dict[str, Any]]:
        """
        Find products with negative adjustments (shrinkage/damage/theft)
        
        Returns list of products sorted by shrinkage quantity (descending)
        Includes value impact calculation
        """
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
            
            if category_id:
                where_conditions.append("p.category_id = %s")
                params.append(category_id)
            
            where_clause = " AND ".join(where_conditions)
            
            cursor.execute(f"""
                SELECT
                    p.id::text AS product_id,
                    p.name AS product_name,
                    p.sku AS product_sku,
                    SUM(ABS(sa.quantity)) AS shrinkage_quantity,
                    SUM(ABS(sa.total_cost)) AS shrinkage_value
                FROM stock_adjustments sa
                JOIN stock_products sp ON sa.stock_product_id = sp.id
                JOIN products p ON sp.product_id = p.id
                JOIN warehouses w ON sp.warehouse_id = w.id
                WHERE {where_clause}
                GROUP BY p.id, p.name, p.sku
                ORDER BY shrinkage_quantity DESC
                LIMIT %s
            """, params + [limit])
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'product_id': row[0],
                    'product_name': row[1],
                    'sku': row[2],
                    'metric_value': float(row[3]),
                    'metric_label': 'shrinkage_units',
                    'value_impact': float(row[4]) if row[4] else 0
                })
            
            return results
