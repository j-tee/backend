# Frontend Quick Start: Stock Product Search

**⏱️ Reading Time:** 5 minutes  
**🎯 Goal:** Get stock product search working in Create Adjustment modal

---

## 🚀 Quick Implementation (Copy & Paste Ready)

### Step 1: Add API Service (2 minutes)

**File:** `src/services/inventoryService.ts`

```typescript
/**
 * Search stock products server-side
 * @param params Search parameters
 * @returns Search results with count
 */
export const searchStockProducts = async (params: {
  q?: string
  limit?: number
  warehouse?: string
  has_quantity?: boolean
}) => {
  const queryString = new URLSearchParams(
    Object.entries(params)
      .filter(([_, value]) => value !== undefined && value !== '')
      .map(([key, value]) => [key, String(value)])
  ).toString()

  const response = await fetch(
    `${API_BASE_URL}/inventory/api/stock-products/search/?${queryString}`,
    {
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${getAuthToken()}`,
      },
    }
  )

  if (!response.ok) {
    throw new Error('Failed to search stock products')
  }

  return response.json()
}
```

---

### Step 2: Update Modal Component (5 minutes)

**File:** `src/features/dashboard/components/CreateAdjustmentModal.tsx`

#### 2.1 Add State
```typescript
// Add these new state variables
const [searchResults, setSearchResults] = useState<StockProduct[]>([])
const [isSearching, setIsSearching] = useState(false)
const [searchError, setSearchError] = useState<string | null>(null)
```

#### 2.2 Add Search Handler
```typescript
import { useCallback } from 'react'
import { debounce } from 'lodash'

// Add this debounced search handler
const handleSearchProducts = useCallback(
  debounce(async (searchTerm: string) => {
    try {
      setIsSearching(true)
      setSearchError(null)
      
      const response = await searchStockProducts({ 
        q: searchTerm, 
        limit: 50 
      })
      
      setSearchResults(response.results || [])
    } catch (error) {
      setSearchError('Failed to search products')
      console.error('Search error:', error)
    } finally {
      setIsSearching(false)
    }
  }, 300),
  []
)
```

#### 2.3 Update Search Input
```typescript
// Replace existing search input handler
const handleSearchInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
  const value = e.target.value
  setProductSearchTerm(value)
  handleSearchProducts(value) // Call server-side search
}
```

#### 2.4 Load Initial Products
```typescript
// Add useEffect to load initial products when modal opens
useEffect(() => {
  if (show) {
    handleSearchProducts('') // Load first 50 products
  }
}, [show, handleSearchProducts])
```

#### 2.5 Update Dropdown
```typescript
// Replace filteredStockProducts with searchResults
<Form.Select
  required
  value={formData.stock_product}
  onChange={handleChange('stock_product')}
  disabled={isSubmitting || isSearching}
>
  <option value="">
    {isSearching 
      ? 'Searching...' 
      : `${searchResults.length} product(s) found - Select one...`}
  </option>
  
  {searchResults.length === 0 && !isSearching && productSearchTerm ? (
    <option disabled>No products match your search</option>
  ) : (
    searchResults.map(sp => (
      <option key={sp.id} value={sp.id}>
        {sp.product_name}
        {sp.product_code && ` - ${sp.product_code}`}
        {sp.warehouse_name && ` (${sp.warehouse_name})`}
        {` - Qty: ${sp.quantity}`}
      </option>
    ))
  )}
</Form.Select>

{/* Show loading indicator */}
{isSearching && (
  <Form.Text className="text-muted">
    <Spinner animation="border" size="sm" /> Searching...
  </Form.Text>
)}

{/* Show success message */}
{!isSearching && searchResults.length > 0 && (
  <Form.Text className="text-success">
    ✓ Found {searchResults.length} product(s)
  </Form.Text>
)}

{/* Show error message */}
{searchError && (
  <Alert variant="warning" className="mt-2">
    {searchError}
  </Alert>
)}
```

---

### Step 3: Clean Up Old Code (2 minutes)

**File:** `src/features/dashboard/pages/ManageStocksPage.tsx`

#### 3.1 Remove Old State
```typescript
// DELETE these lines:
const [allStockProductsForModal, setAllStockProductsForModal] = useState<StockProduct[]>([])
const [isLoadingAllStockProducts, setIsLoadingAllStockProducts] = useState(false)
```

#### 3.2 Simplify Modal Open
```typescript
// REPLACE this:
const handleOpenCreateAdjustmentModal = async () => {
  setShowCreateAdjustmentModal(true)
  setIsLoadingAllStockProducts(true)
  const response = await fetchStockProducts({ page: 1, page_size: 1000 })
  setAllStockProductsForModal(response.results)
  setIsLoadingAllStockProducts(false)
}

// WITH this:
const handleOpenCreateAdjustmentModal = () => {
  setShowCreateAdjustmentModal(true)
  // Modal handles loading internally now
}
```

#### 3.3 Remove stockProducts Prop
```typescript
// REMOVE stockProducts prop from modal:
<CreateAdjustmentModal
  show={showCreateAdjustmentModal}
  onClose={() => setShowCreateAdjustmentModal(false)}
  // stockProducts={allStockProductsForModal} // DELETE THIS LINE
  onSubmit={handleCreateAdjustment}
  isSubmitting={createAdjustmentStatus === 'loading'}
  error={createAdjustmentError}
/>
```

---

## ✅ Testing Checklist (2 minutes)

After implementation, verify:

- [ ] Modal opens quickly (no 1000-product loading delay)
- [ ] Searching for "10mm" shows results
- [ ] Search updates as you type (debounced)
- [ ] "Searching..." indicator appears while loading
- [ ] Selecting a product works correctly
- [ ] Empty search shows first 50 products
- [ ] "No results" message shows when appropriate
- [ ] Error handling works (disconnect network and search)

---

## 🐛 Troubleshooting

### "0 products found" still appears
**Check:**
1. Network tab - is API returning results?
2. Console - any JavaScript errors?
3. Search term - is it at least 1 character?

**Fix:** Check that `searchResults` state is being updated correctly

### Search is too slow
**Check:**
1. Network tab - how long is API taking?
2. Is debounce set to 300ms?

**Fix:** If API is slow, talk to backend team about optimization

### Products not loading on modal open
**Check:**
1. Is `useEffect` hook firing?
2. Is `handleSearchProducts('')` being called?

**Fix:** Add console.log to verify hook execution

---

## 📊 Before vs After Comparison

### Before ❌
```typescript
// Loads 1000 products when modal opens (slow!)
const handleOpenModal = async () => {
  setShowModal(true)
  setIsLoading(true)
  const response = await fetchStockProducts({ page: 1, page_size: 1000 })
  setProducts(response.results)
  setIsLoading(false)
}
```

**Problems:**
- Takes 2-5 seconds to load
- Doesn't work with > 1000 products
- Wastes bandwidth
- Client-side search can miss results

### After ✅
```typescript
// Searches server-side as user types (fast!)
const handleSearch = debounce(async (term: string) => {
  setIsSearching(true)
  const response = await searchStockProducts({ q: term, limit: 50 })
  setSearchResults(response.results)
  setIsSearching(false)
}, 300)
```

**Benefits:**
- Instant modal opening
- Works with millions of products
- Only transfers needed data
- More accurate server-side search

---

## 🎯 Expected Behavior

1. **Modal Opens** → Loads first 50 products (< 100ms)
2. **User Types "10mm"** → Shows "Searching..." indicator
3. **After 300ms** → API call to `/inventory/api/stock-products/search/?q=10mm`
4. **Results Arrive** → Dropdown shows matching products
5. **User Selects** → Product selected, form continues normally

---

## 📦 Dependencies

Install lodash for debounce (if not already installed):

```bash
npm install lodash
npm install --save-dev @types/lodash
```

Or use custom debounce (no dependencies):

```typescript
function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
) {
  let timeout: NodeJS.Timeout | null = null
  return (...args: Parameters<T>) => {
    if (timeout) clearTimeout(timeout)
    timeout = setTimeout(() => func(...args), wait)
  }
}
```

---

## 🚀 Deployment

1. **Test locally** with `npm run dev`
2. **Test on staging** with real data
3. **Monitor performance** in production
4. **Rollback** if needed (keep old code for 1 week)

---

## 📚 Full Documentation

For complete details, see:
- **API Spec:** `STOCK_PRODUCT_SEARCH_API_SPECIFICATION.md`
- **Backend Requirements:** `BACKEND-STOCK-PRODUCT-SEARCH-REQUIREMENTS.md`
- **Detailed Frontend Guide:** `FRONTEND-STOCK-PRODUCT-SEARCH-IMPLEMENTATION.md`

---

**That's it!** 🎉 You now have server-side stock product search working.

**Questions?** Check the full documentation or contact the backend team.

**Last Updated:** October 10, 2025
