# 🎨 Frontend Integration Guide: Server-Side Catalog Filtering

**For**: Frontend Team  
**Date**: October 14, 2025  
**Status**: Ready for Integration

---

## 🎯 What Changed

The catalog endpoints now support **server-side filtering and pagination**. This means:

- ❌ **Remove** client-side filtering logic
- ✅ **Add** query parameters to API calls
- ✅ **Add** pagination support

**Result**: Faster page loads, better UX, scales to 10,000+ products

---

## 📡 Updated API Endpoints

### 1. Single Storefront Catalog

**URL**: `/inventory/api/storefronts/{storefrontId}/sale-catalog/`

**New Query Parameters**:
```typescript
interface CatalogFilters {
  search?: string          // Search by name, SKU, or barcode
  category?: UUID          // Filter by category ID
  min_price?: number       // Minimum price (inclusive)
  max_price?: number       // Maximum price (inclusive)
  in_stock_only?: boolean  // Only show in-stock (default: true)
  page?: number            // Page number (default: 1)
  page_size?: number       // Items per page (default: 50, max: 200)
}
```

**New Response Format**:
```typescript
interface SaleCatalogResponse {
  count: number            // Total items matching filters
  next: string | null      // URL for next page
  previous: string | null  // URL for previous page
  page_size: number        // Items per page
  total_pages: number      // Total number of pages
  current_page: number     // Current page number
  products: SaleCatalogItem[]
}
```

### 2. Multi-Storefront Catalog

**URL**: `/inventory/api/storefronts/multi-storefront-catalog/`

**New Query Parameters**:
```typescript
interface MultiStorefrontCatalogFilters extends CatalogFilters {
  storefront?: UUID | UUID[]  // Filter to specific storefront(s)
}
```

**New Response Format**:
```typescript
interface MultiStorefrontCatalogResponse {
  count: number
  next: string | null
  previous: string | null
  page_size: number
  total_pages: number
  current_page: number
  storefronts: Array<{ id: UUID; name: string }>
  products: MultiStorefrontCatalogItem[]
}
```

---

## 🔧 How to Update Your Code

### Step 1: Update Service Layer

**Before** (`src/services/inventoryService.ts`):
```typescript
export const fetchSaleCatalog = async (storefrontId: UUID) => {
  const { data } = await httpClient.get<{ products: SaleCatalogItem[] }>(
    `/inventory/api/storefronts/${storefrontId}/sale-catalog/`
  )
  return data
}
```

**After**:
```typescript
export interface CatalogFilters {
  search?: string
  category?: UUID
  min_price?: number
  max_price?: number
  in_stock_only?: boolean
  page?: number
  page_size?: number
}

export interface SaleCatalogResponse {
  count: number
  next: string | null
  previous: string | null
  page_size: number
  total_pages: number
  current_page: number
  products: SaleCatalogItem[]
}

export const fetchSaleCatalog = async (
  storefrontId: UUID,
  filters?: CatalogFilters
) => {
  const { data } = await httpClient.get<SaleCatalogResponse>(
    `/inventory/api/storefronts/${storefrontId}/sale-catalog/`,
    { params: filters }  // ✨ Add query parameters
  )
  return data
}
```

### Step 2: Update Component

**Before** (`ProductSearchPanel.tsx`):
```typescript
const searchProducts = useCallback(async (rawQuery: string) => {
  const lowerQuery = rawQuery.toLowerCase()
  
  // ❌ Client-side filtering - REMOVE THIS
  const matches = catalog.filter((item) =>
    item.name.toLowerCase().includes(lowerQuery) ||
    item.sku.toLowerCase().includes(lowerQuery) ||
    (item.barcode ? item.barcode.toLowerCase().includes(lowerQuery) : false)
  )
  
  setProducts(matches)
}, [catalog])
```

**After**:
```typescript
const searchProducts = useCallback(async (rawQuery: string) => {
  const trimmedQuery = rawQuery.trim()
  
  if (trimmedQuery.length < 2) {
    setProducts([])
    return
  }
  
  try {
    setLoading(true)
    setError(null)
    
    // ✅ Server-side search
    const response = await fetchSaleCatalog(storefrontId!, {
      search: trimmedQuery,
      in_stock_only: true,
      page_size: 50,
    })
    
    setProducts(response.products)
    setTotalCount(response.count)  // For pagination UI
    
  } catch (err) {
    console.error('Search error:', err)
    setError('Failed to search products')
  } finally {
    setLoading(false)
  }
}, [storefrontId])
```

### Step 3: Add Pagination Support

```typescript
const [currentPage, setCurrentPage] = useState(1)
const [totalPages, setTotalPages] = useState(1)

const loadPage = useCallback(async (page: number) => {
  const response = await fetchSaleCatalog(storefrontId!, {
    search: searchQuery,
    category: selectedCategory,
    page: page,
    page_size: 50,
  })
  
  setProducts(response.products)
  setCurrentPage(response.current_page)
  setTotalPages(response.total_pages)
}, [storefrontId, searchQuery, selectedCategory])

// In your JSX:
<Pagination
  currentPage={currentPage}
  totalPages={totalPages}
  onPageChange={loadPage}
/>
```

---

## 🎨 Example: Complete Implementation

```typescript
// src/features/dashboard/components/sales/ProductSearchPanel.tsx

import { useState, useCallback } from 'react'
import { fetchSaleCatalog, CatalogFilters } from '@/services/inventoryService'

export const ProductSearchPanel = ({ storefrontId }: Props) => {
  const [products, setProducts] = useState<Product[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  // Pagination state
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const [totalCount, setTotalCount] = useState(0)
  
  // Filter state
  const [filters, setFilters] = useState<CatalogFilters>({
    search: '',
    in_stock_only: true,
    page: 1,
    page_size: 50,
  })
  
  const searchProducts = useCallback(async (newFilters: Partial<CatalogFilters>) => {
    const updatedFilters = { ...filters, ...newFilters, page: 1 }
    setFilters(updatedFilters)
    
    if (updatedFilters.search && updatedFilters.search.length < 2) {
      setProducts([])
      return
    }
    
    try {
      setLoading(true)
      setError(null)
      
      const response = await fetchSaleCatalog(storefrontId, updatedFilters)
      
      setProducts(response.products)
      setCurrentPage(response.current_page)
      setTotalPages(response.total_pages)
      setTotalCount(response.count)
      
    } catch (err) {
      console.error('Search error:', err)
      setError('Failed to search products')
      setProducts([])
    } finally {
      setLoading(false)
    }
  }, [storefrontId, filters])
  
  const handleSearchChange = useCallback((query: string) => {
    searchProducts({ search: query })
  }, [searchProducts])
  
  const handleCategoryChange = useCallback((categoryId: UUID | null) => {
    searchProducts({ category: categoryId || undefined })
  }, [searchProducts])
  
  const handlePriceRangeChange = useCallback((min: number | null, max: number | null) => {
    searchProducts({
      min_price: min || undefined,
      max_price: max || undefined,
    })
  }, [searchProducts])
  
  const handlePageChange = useCallback(async (page: number) => {
    const updatedFilters = { ...filters, page }
    setFilters(updatedFilters)
    
    try {
      setLoading(true)
      const response = await fetchSaleCatalog(storefrontId, updatedFilters)
      
      setProducts(response.products)
      setCurrentPage(response.current_page)
      
      // Scroll to top
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (err) {
      console.error('Pagination error:', err)
    } finally {
      setLoading(false)
    }
  }, [storefrontId, filters])
  
  return (
    <div>
      {/* Search Input */}
      <SearchInput
        value={filters.search}
        onChange={handleSearchChange}
        placeholder="Search by name, SKU, or barcode..."
      />
      
      {/* Category Filter */}
      <CategoryFilter
        selectedCategory={filters.category}
        onChange={handleCategoryChange}
      />
      
      {/* Price Range Filter */}
      <PriceRangeFilter
        min={filters.min_price}
        max={filters.max_price}
        onChange={handlePriceRangeChange}
      />
      
      {/* Results Count */}
      {!loading && (
        <div className="results-info">
          Found {totalCount} products
          {filters.search && ` matching "${filters.search}"`}
        </div>
      )}
      
      {/* Loading State */}
      {loading && <LoadingSpinner />}
      
      {/* Error State */}
      {error && <ErrorMessage message={error} />}
      
      {/* Products Grid */}
      <ProductGrid products={products} />
      
      {/* Pagination */}
      {totalPages > 1 && (
        <Pagination
          currentPage={currentPage}
          totalPages={totalPages}
          totalCount={totalCount}
          pageSize={filters.page_size}
          onPageChange={handlePageChange}
        />
      )}
    </div>
  )
}
```

---

## ⚠️ Migration Checklist

### Before Deployment

- [ ] Update `inventoryService.ts` with new types and filters
- [ ] Remove client-side filtering logic from components
- [ ] Add pagination state management
- [ ] Add pagination UI components
- [ ] Test with small datasets (< 50 products)
- [ ] Test with medium datasets (100-500 products)
- [ ] Test with large datasets (1000+ products)
- [ ] Test all filter combinations
- [ ] Test pagination navigation
- [ ] Verify loading states work correctly
- [ ] Verify error handling works

### After Deployment

- [ ] Monitor API response times
- [ ] Monitor error rates
- [ ] Gather user feedback
- [ ] Optimize based on usage patterns

---

## 🐛 Common Issues & Solutions

### Issue 1: "No products found" even with data

**Cause**: `in_stock_only` defaults to `true`  
**Solution**: Explicitly set `in_stock_only: false` to include out-of-stock

### Issue 2: Pagination doesn't update

**Cause**: Not updating `page` state correctly  
**Solution**: Make sure to update page state before making API call

### Issue 3: Filters not working

**Cause**: Invalid UUID format or decimal values  
**Solution**: Backend gracefully ignores invalid values, check browser console

### Issue 4: Slow search performance

**Cause**: Searching every keystroke  
**Solution**: Add debouncing (wait 300ms after user stops typing)

```typescript
import { useMemo, useCallback } from 'react'
import { debounce } from 'lodash'

const debouncedSearch = useMemo(
  () => debounce((query: string) => {
    searchProducts({ search: query })
  }, 300),
  [searchProducts]
)

const handleSearchChange = useCallback((query: string) => {
  debouncedSearch(query)
}, [debouncedSearch])
```

---

## 📊 Performance Tips

1. **Debounce search input** (300ms recommended)
2. **Cache results** for recently used queries
3. **Show loading states** immediately
4. **Prefetch next page** when user scrolls near bottom
5. **Use optimistic updates** for better UX
6. **Monitor API response times** and adjust page size

---

## 🔗 Resources

- **API Documentation**: `CATALOG_FILTERING_IMPLEMENTATION_COMPLETE.md`
- **Backend Code**: `inventory/views.py`
- **Test Examples**: `tests/test_catalog_filtering.py`
- **Swagger UI**: `http://localhost:8000/api/schema/swagger-ui/`

---

## 💬 Questions?

Contact the backend team or open a GitHub issue.

**Happy coding! 🚀**
