# Stock Movements Enhancement - Implementation Plan

**Date:** November 1, 2025  
**Status:** 🚀 IN PROGRESS  
**Priority:** HIGH  
**Architecture:** Backend-Heavy (All Business Logic Server-Side)

---

## 📋 Executive Summary

This document outlines the implementation plan for enhancing the Stock Movements reporting system with advanced analytics, product drill-down, and dashboard capabilities. **All business logic, calculations, and aggregations will be handled server-side** using optimized SQL queries and Django ORM.

---

## 🏗️ Current System Analysis

### Existing Infrastructure ✅

**Endpoints:**
- `GET /reports/api/inventory/movements/` - Stock Movement History (existing)
- `GET /reports/api/inventory/movements/export/` - Export movements (existing)

**Services:**
- `MovementTracker` class - Unified movement tracking via raw SQL UNION
- Aggregates from 3 sources: Sales, Transfers, StockAdjustments

**Current Capabilities:**
- ✅ Date range filtering
- ✅ Warehouse filtering
- ✅ Product filtering (basic)
- ✅ Category filtering
- ✅ Search by product name/SKU
- ✅ Movement type filtering
- ✅ Time series grouping (daily/weekly/monthly)
- ✅ Pagination
- ✅ Summary statistics (total_in, total_out, net_change)
- ✅ Warehouse grouping
- ✅ Category grouping

### Gaps to Address ⚠️

**Missing Capabilities:**
- ❌ Multi-product filtering (`product_ids` parameter)
- ❌ Product search autocomplete endpoint
- ❌ Quick filters (top sellers, most adjusted, shrinkage leaders)
- ❌ Product-specific movement summary
- ❌ Advanced analytics (top sellers ranking, movement breakdown percentages)
- ❌ Daily trend analysis with all movement types
- ❌ Value-based calculations (shrinkage cost impact)
- ❌ Stock velocity metrics

---

## 🎯 Implementation Phases

---

## **PHASE 1: Enhanced Product Filtering** ⭐

### Scope: Extend existing endpoint with multi-product support

**Changes Required:**
1. ✅ Update `StockMovementHistoryReportView.get()` to accept `product_ids`
2. ✅ Update `MovementTracker.get_movements()` to filter by multiple products
3. ✅ Update SQL UNION queries to support `product_id IN (...)` clause

**Files to Modify:**
- `reports/views/inventory_reports.py` - Add `product_ids` parameter parsing
- `reports/services/movement_tracker.py` - Update SQL WHERE clauses

**Implementation:**

```python
# reports/views/inventory_reports.py (line ~810)

# Parse filters
product_id = request.GET.get('product_id')
product_ids = request.GET.get('product_ids')  # NEW: comma-separated UUIDs

# Resolve product filter
product_filter = None
if product_ids:
    # Multi-product filter takes precedence
    product_filter = [p.strip() for p in product_ids.split(',') if p.strip()]
elif product_id:
    # Single product filter
    product_filter = [product_id]

# Pass to MovementTracker
movements, pagination = self._build_movements(
    ...
    product_ids=product_filter,  # NEW parameter
    ...
)
```

```python
# reports/services/movement_tracker.py (update SQL queries)

@classmethod
def get_movements(
    cls,
    business_id: str,
    product_ids: Optional[List[str]] = None,  # Changed from product_id
    ...
):
    # Build WHERE clause for products
    if product_ids:
        product_placeholders = ','.join(['%s'] * len(product_ids))
        product_where = f"AND product_id IN ({product_placeholders})"
        params.extend(product_ids)
    else:
        product_where = ""
    
    # Apply to all 3 UNION queries (sales, transfers, adjustments)
```

**Testing:**
```bash
# Single product
curl "http://localhost:8000/reports/api/inventory/movements/?product_id=uuid"

# Multiple products
curl "http://localhost:8000/reports/api/inventory/movements/?product_ids=uuid1,uuid2,uuid3"
```

**Estimated Time:** 4 hours  
**Priority:** CRITICAL  
**Risk:** LOW (extends existing functionality)

---

## **PHASE 2: Product Search & Quick Filters** ⭐⭐

### Scope: New endpoints for product discovery and filtering

**New Endpoints:**
1. `GET /reports/api/inventory/products/search/` - Product autocomplete
2. `GET /reports/api/inventory/movements/quick-filters/` - Pre-filtered product lists

**Files to Create:**
- `reports/views/product_search.py` (new file)
- Update `reports/urls.py` to register new endpoints

**2.1 Product Search Implementation:**

```python
# reports/views/product_search.py (NEW FILE)

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q, F, Value, IntegerField, Case, When, Sum
from inventory.models import Product, StockProduct

class ProductSearchAPIView(APIView):
    """
    Product search with relevance ranking
    
    GET /reports/api/inventory/products/search/?q=samsung&limit=10
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        query = request.GET.get('q', '').strip()
        limit = min(int(request.GET.get('limit', 10)), 50)  # Max 50
        
        if len(query) < 2:
            return Response({
                'success': False,
                'error': 'Search query must be at least 2 characters'
            }, status=400)
        
        # Get business from request
        business = request.user.primary_business
        if not business:
            return Response({
                'success': False,
                'error': 'No business associated with user'
            }, status=400)
        
        # Search with relevance scoring
        products = Product.objects.filter(
            business=business
        ).filter(
            Q(name__icontains=query) |
            Q(sku__icontains=query) |
            Q(description__icontains=query)
        ).annotate(
            # Relevance scoring: exact matches score higher
            name_match=Case(
                When(name__iexact=query, then=Value(5)),
                When(name__istartswith=query, then=Value(4)),
                When(name__icontains=query, then=Value(3)),
                default=Value(0),
                output_field=IntegerField()
            ),
            sku_match=Case(
                When(sku__iexact=query, then=Value(3)),
                When(sku__istartswith=query, then=Value(2)),
                default=Value(0),
                output_field=IntegerField()
            ),
            relevance=F('name_match') + F('sku_match')
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
```

**2.2 Quick Filters Implementation:**

```python
# reports/views/product_search.py (ADD TO SAME FILE)

class QuickFiltersAPIView(APIView):
    """
    Quick filter presets for common scenarios
    
    GET /reports/api/inventory/movements/quick-filters/?filter_type=top_sellers&start_date=2025-10-01&end_date=2025-10-31
    """
    permission_classes = [IsAuthenticated]
    
    VALID_FILTERS = ['top_sellers', 'most_adjusted', 'high_transfers', 'shrinkage']
    
    def get(self, request):
        filter_type = request.GET.get('filter_type')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        limit = min(int(request.GET.get('limit', 10)), 50)
        
        if filter_type not in self.VALID_FILTERS:
            return Response({
                'success': False,
                'error': f'Invalid filter_type. Must be one of: {", ".join(self.VALID_FILTERS)}'
            }, status=400)
        
        business = request.user.primary_business
        if not business:
            return Response({'success': False, 'error': 'No business'}, status=400)
        
        # Call appropriate filter method
        method = getattr(self, f'_get_{filter_type}')
        product_ids = method(business.id, start_date, end_date, limit)
        
        return Response({
            'success': True,
            'data': {
                'filter_type': filter_type,
                'product_ids': product_ids,
                'count': len(product_ids)
            }
        })
    
    def _get_top_sellers(self, business_id, start_date, end_date, limit):
        """Products with highest sales volume"""
        from reports.services.movement_tracker import MovementTracker
        
        # Use raw SQL for performance
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT product_id, SUM(ABS(quantity)) as total_sold
                FROM (
                    {movements_sql}
                ) AS movements
                WHERE movement_type = 'sale'
                GROUP BY product_id
                ORDER BY total_sold DESC
                LIMIT %s
            """.format(movements_sql=MovementTracker._get_union_sql(...)),
                [business_id, start_date, end_date, limit]
            )
            return [str(row[0]) for row in cursor.fetchall()]
    
    def _get_most_adjusted(self, business_id, start_date, end_date, limit):
        """Products with most adjustment activity"""
        # Similar SQL query for adjustments
        pass
    
    def _get_high_transfers(self, business_id, start_date, end_date, limit):
        """Products with high transfer activity"""
        # Similar SQL query for transfers
        pass
    
    def _get_shrinkage(self, business_id, start_date, end_date, limit):
        """Products with negative adjustments (shrinkage)"""
        # Query for THEFT, DAMAGE, EXPIRED adjustments
        pass
```

**URL Registration:**

```python
# reports/urls.py (ADD)

from .views.product_search import ProductSearchAPIView, QuickFiltersAPIView

urlpatterns = [
    # ... existing patterns ...
    
    # Product Search & Quick Filters (Phase 2)
    path('api/inventory/products/search/', ProductSearchAPIView.as_view(), name='product-search'),
    path('api/inventory/movements/quick-filters/', QuickFiltersAPIView.as_view(), name='movement-quick-filters'),
]
```

**Estimated Time:** 8 hours  
**Priority:** HIGH  
**Risk:** LOW (new isolated endpoints)

---

## **PHASE 3: Product Movement Summary** ⭐⭐⭐

### Scope: Comprehensive per-product analytics

**New Endpoint:**
- `GET /reports/api/inventory/movements/product-summary/?product_id=uuid&start_date=...&end_date=...`

**File to Create:**
- `reports/views/product_analytics.py` (new file)

**Implementation:**

```python
# reports/views/product_analytics.py (NEW FILE)

class ProductMovementSummaryAPIView(APIView):
    """
    Comprehensive movement summary for a single product
    
    All calculations performed server-side
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        product_id = request.GET.get('product_id')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        if not product_id:
            return Response({'success': False, 'error': 'product_id required'}, status=400)
        
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({'success': False, 'error': 'Product not found'}, status=404)
        
        # Use MovementTracker to get all movements
        movements = MovementTracker.get_movements(
            business_id=str(product.business_id),
            product_ids=[product_id],
            start_date=start_date,
            end_date=end_date
        )
        
        # Calculate movement breakdown
        breakdown = self._calculate_breakdown(movements)
        
        # Get current stock across all warehouses
        current_stock = self._get_current_stock(product)
        
        # Calculate warehouse distribution
        warehouse_dist = self._calculate_warehouse_distribution(product)
        
        return Response({
            'success': True,
            'data': {
                'product_id': str(product.id),
                'product_name': product.name,
                'sku': product.sku,
                'current_stock': current_stock,
                'movements': breakdown,
                'net_change': breakdown['net_change'],
                'by_warehouse': warehouse_dist
            }
        })
    
    def _calculate_breakdown(self, movements):
        """Categorize and sum movements by type"""
        sales = sum(abs(m['quantity']) for m in movements if m['type'] == 'sale')
        transfers_in = sum(m['quantity'] for m in movements if m['type'] == 'transfer' and m['direction'] == 'in')
        transfers_out = sum(abs(m['quantity']) for m in movements if m['type'] == 'transfer' and m['direction'] == 'out')
        adjustments_up = sum(m['quantity'] for m in movements if m['type'] == 'adjustment' and m['direction'] == 'in')
        adjustments_down = sum(abs(m['quantity']) for m in movements if m['type'] == 'adjustment' and m['direction'] == 'out')
        
        net_change = (transfers_in + adjustments_up) - (sales + transfers_out + adjustments_down)
        
        return {
            'sales': -sales,
            'transfers_in': transfers_in,
            'transfers_out': -transfers_out,
            'adjustments_up': adjustments_up,
            'adjustments_down': -adjustments_down,
            'net_change': net_change
        }
    
    def _get_current_stock(self, product):
        """Aggregate current stock across warehouses"""
        return StockProduct.objects.filter(
            product=product
        ).aggregate(total=Sum('current_quantity'))['total'] or 0
    
    def _calculate_warehouse_distribution(self, product):
        """Calculate stock distribution by warehouse with percentages"""
        total_stock = self._get_current_stock(product)
        
        if total_stock == 0:
            return []
        
        warehouse_stock = StockProduct.objects.filter(
            product=product,
            current_quantity__gt=0
        ).values(
            'warehouse_id',
            'warehouse__name'
        ).annotate(
            quantity=Sum('current_quantity')
        ).order_by('-quantity')
        
        distribution = []
        for item in warehouse_stock:
            percentage = (item['quantity'] / total_stock) * 100
            distribution.append({
                'warehouse_id': str(item['warehouse_id']),
                'warehouse_name': item['warehouse__name'],
                'quantity': float(item['quantity']),
                'percentage': round(percentage, 2)
            })
        
        return distribution
```

**Estimated Time:** 6 hours  
**Priority:** HIGH  
**Risk:** MEDIUM (complex calculations)

---

## **PHASE 4: Analytics Dashboard** ⭐⭐⭐⭐

### Scope: Pre-calculated analytics for dashboard

**New Endpoint:**
- `GET /reports/api/inventory/movements/analytics/?start_date=...&end_date=...`

**Implementation:** See requirements document for full details

**Key Features:**
- Top sellers ranking
- Movement breakdown with percentages
- Daily trend generation
- Shrinkage leaders with value impact
- Key metrics (velocity, turnover, etc.)

**Estimated Time:** 12 hours  
**Priority:** MEDIUM  
**Risk:** HIGH (performance-critical, complex SQL)

---

## 🗂️ Database Optimization

### Required Indexes

```python
# inventory/models.py

class StockMovement(models.Model):  # If using a model
    class Meta:
        indexes = [
            models.Index(fields=['product_id', 'created_at'], name='idx_movement_product_date'),
            models.Index(fields=['warehouse_id', 'created_at'], name='idx_movement_warehouse_date'),
            models.Index(fields=['reference_type', 'movement_type'], name='idx_movement_types'),
            models.Index(fields=['created_at'], name='idx_movement_date'),
        ]
```

**Note:** Since we use raw SQL UNION, ensure indexes exist on source tables:
- `sales_sale`: (product_id, created_at)
- `inventory_transfer`: (product_id, created_at)
- `inventory_stockadjustment`: (product_id, created_at)

---

## 🧪 Testing Strategy

### Unit Tests

```python
# reports/tests/test_product_analytics.py

class ProductAnalyticsTestCase(TestCase):
    def test_movement_breakdown_calculation(self):
        """Verify movement breakdown calculates correctly"""
        pass
    
    def test_warehouse_distribution_percentages(self):
        """Verify percentages sum to 100%"""
        pass
    
    def test_top_sellers_ranking(self):
        """Verify ranking is correct"""
        pass
    
    def test_quick_filters(self):
        """Test all quick filter types"""
        pass
```

### Integration Tests

```bash
# Test all endpoints
pytest reports/tests/test_product_analytics.py -v
pytest reports/tests/test_product_search.py -v
```

---

## 📊 Performance Targets

| Endpoint | Max Response Time | Notes |
|----------|-------------------|-------|
| Product Search | 500ms | Autocomplete must be fast |
| Quick Filters | 2s | Pre-filtering acceptable delay |
| Product Summary | 2s | Per-product calculations |
| Analytics Dashboard | 3s | Consider caching |

### Caching Strategy

```python
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

class MovementAnalyticsAPIView(APIView):
    @method_decorator(cache_page(60 * 5))  # 5 minutes
    def get(self, request):
        # Dashboard data changes infrequently
        pass
```

---

## 📝 Implementation Checklist

### Phase 1: Enhanced Filtering ✅
- [ ] Update `StockMovementHistoryReportView` for `product_ids`
- [ ] Update `MovementTracker.get_movements()` SQL
- [ ] Update `_build_summary()` for multi-product
- [ ] Update `_build_time_series()` for multi-product
- [ ] Update `aggregate_by_warehouse()` for multi-product
- [ ] Update `aggregate_by_category()` for multi-product
- [ ] Test single product filter
- [ ] Test multi-product filter
- [ ] Update API documentation

### Phase 2: Search & Quick Filters 🔄
- [ ] Create `reports/views/product_search.py`
- [ ] Implement `ProductSearchAPIView`
- [ ] Implement `QuickFiltersAPIView`
- [ ] Implement `_get_top_sellers()`
- [ ] Implement `_get_most_adjusted()`
- [ ] Implement `_get_high_transfers()`
- [ ] Implement `_get_shrinkage()`
- [ ] Register URLs in `reports/urls.py`
- [ ] Write unit tests
- [ ] Test all filter types
- [ ] Update API documentation

### Phase 3: Product Summary ⏳
- [ ] Create `reports/views/product_analytics.py`
- [ ] Implement `ProductMovementSummaryAPIView`
- [ ] Implement `_calculate_breakdown()`
- [ ] Implement `_get_current_stock()`
- [ ] Implement `_calculate_warehouse_distribution()`
- [ ] Register URL
- [ ] Write unit tests
- [ ] Test with various products
- [ ] Verify percentage calculations
- [ ] Update API documentation

### Phase 4: Analytics Dashboard ⏳
- [ ] Extend `product_analytics.py` with analytics view
- [ ] Implement `MovementAnalyticsAPIView`
- [ ] Implement `_get_top_sellers()`
- [ ] Implement `_get_movement_breakdown()`
- [ ] Implement `_get_daily_trend()`
- [ ] Implement `_get_shrinkage_leaders()`
- [ ] Implement `_calculate_metrics()`
- [ ] Add caching layer
- [ ] Optimize SQL queries
- [ ] Register URL
- [ ] Write unit tests
- [ ] Load test with large datasets
- [ ] Update API documentation

---

## 🚀 Deployment Strategy

### Pre-Deployment
1. Run all tests: `pytest reports/tests/ -v`
2. Check query performance: `python manage.py test --debug-sql`
3. Review SQL execution plans
4. Update API documentation

### Deployment
1. Commit to development branch
2. Merge to main
3. GitHub Actions will deploy automatically
4. Monitor logs for errors
5. Verify all endpoints in production

### Post-Deployment
1. Monitor response times in production
2. Check database load
3. Verify caching is working
4. Collect frontend feedback

---

## 📞 Coordination Points

### Frontend Team Needs:
1. Exact response format examples (provided in requirements)
2. Error response format (consistent across all endpoints)
3. Pagination structure (reuse existing format)
4. Date format (ISO 8601: YYYY-MM-DD)

### Backend Team Delivers:
1. All 5 endpoints fully functional
2. Comprehensive API documentation
3. Unit test coverage > 80%
4. Performance optimization
5. Error handling

---

**Status:** Ready for Implementation  
**Next Step:** Begin Phase 1 - Enhanced Product Filtering  
**Estimated Total Time:** 30-40 hours  
**Target Completion:** November 15, 2025
