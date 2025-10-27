# Frontend Error Fix: unit_price.toFixed is not a function

## Error Message
```
Uncaught TypeError: item.unit_price.toFixed is not a function
    children SaleCart.tsx:161
    SaleCart SaleCart.tsx:119
```

## Root Cause

**Backend sends decimal values as strings** to preserve precision:
```json
{
  "unit_price": "60.00",    // ✅ String (correct from backend)
  "total_price": "60.00",   // ✅ String (correct from backend)
  "discount_amount": "0.00" // ✅ String (correct from backend)
}
```

**Frontend tries to call `.toFixed()` on string**:
```typescript
// ❌ WRONG: unit_price is a string, not a number
item.unit_price.toFixed(2)  // TypeError!
```

---

## The Fix

### Option 1: Parse to Number First (Recommended)
```typescript
// ✅ CORRECT: Parse string to number, then format
parseFloat(item.unit_price).toFixed(2)

// Or use Number()
Number(item.unit_price).toFixed(2)
```

### Option 2: Use the String Directly
If the backend already formats with 2 decimals, just use the string:
```typescript
// ✅ CORRECT: Backend already formatted it
item.unit_price  // "60.00"
```

### Option 3: Create a Helper Function
```typescript
// utils/formatters.ts
export const formatCurrency = (value: string | number): string => {
  const num = typeof value === 'string' ? parseFloat(value) : value;
  return num.toFixed(2);
};

// In component
formatCurrency(item.unit_price)  // "60.00"
```

---

## Fix Your SaleCart.tsx

### Current Code (Line 161 - BROKEN)
```typescript
// ❌ This causes the error
<span>GH₵ {item.unit_price.toFixed(2)}</span>
```

### Fixed Code
```typescript
// ✅ Option 1: Parse then format
<span>GH₵ {parseFloat(item.unit_price).toFixed(2)}</span>

// ✅ Option 2: Use string directly (backend already has 2 decimals)
<span>GH₵ {item.unit_price}</span>

// ✅ Option 3: Use helper function
<span>GH₵ {formatCurrency(item.unit_price)}</span>
```

---

## Complete Fix for All Decimal Fields

Find and replace all instances in your component:

### Before (BROKEN)
```typescript
// Line ~161
<span>GH₵ {item.unit_price.toFixed(2)}</span>
<span>GH₵ {item.total_price.toFixed(2)}</span>
<span>GH₵ {sale.subtotal.toFixed(2)}</span>
<span>GH₵ {sale.total_amount.toFixed(2)}</span>
```

### After (FIXED)
```typescript
// Parse all decimal strings to numbers
<span>GH₵ {parseFloat(item.unit_price).toFixed(2)}</span>
<span>GH₵ {parseFloat(item.total_price).toFixed(2)}</span>
<span>GH₵ {parseFloat(sale.subtotal).toFixed(2)}</span>
<span>GH₵ {parseFloat(sale.total_amount).toFixed(2)}</span>
```

---

## Better Approach: Create TypeScript Interfaces

### Define Proper Types
```typescript
// types/sale.ts
export interface SaleItem {
  id: string;
  product: string;
  product_name: string;
  product_sku: string;
  quantity: number;           // Backend sends as number
  unit_price: string;         // Backend sends as string!
  discount_amount: string;    // Backend sends as string!
  total_price: string;        // Backend sends as string!
  // ... other fields
}

export interface Sale {
  id: string;
  subtotal: string;           // Backend sends as string!
  discount_amount: string;    // Backend sends as string!
  total_amount: string;       // Backend sends as string!
  // ... other fields
  sale_items: SaleItem[];
}
```

### Create Formatter Utilities
```typescript
// utils/currency.ts
export const formatPrice = (price: string | number): string => {
  const num = typeof price === 'string' ? parseFloat(price) : price;
  return num.toFixed(2);
};

export const formatCurrency = (price: string | number): string => {
  return `GH₵ ${formatPrice(price)}`;
};

// Usage in component
import { formatCurrency, formatPrice } from '@/utils/currency';

<span>{formatCurrency(item.unit_price)}</span>  // "GH₵ 60.00"
<span>GH₵ {formatPrice(item.total_price)}</span> // "GH₵ 60.00"
```

---

## Why Backend Sends Strings

Django REST Framework serializes `DecimalField` as **strings** to:
1. **Preserve precision** - JavaScript numbers can lose precision with large decimals
2. **Avoid floating point errors** - `0.1 + 0.2 = 0.30000000000000004` in JavaScript
3. **Match database storage** - PostgreSQL NUMERIC stored as strings in JSON

### Example Precision Issue
```javascript
// JavaScript floating point problem
0.1 + 0.2                    // 0.30000000000000004 ❌

// With strings from backend
parseFloat("0.1") + parseFloat("0.2")  // Still 0.30000000000000004
// But backend already calculated: "0.30" ✅
```

**Best practice**: Let backend handle calculations, frontend just displays.

---

## Quick Fix Script

Run this in your SaleCart.tsx:

### Find
```typescript
\.toFixed\(
```

### Replace Each Instance
```typescript
// If the variable is a decimal from backend:
parseFloat(VARIABLE).toFixed(
```

### Example Replacements
```typescript
// Before
item.unit_price.toFixed(2)
item.total_price.toFixed(2)
sale.subtotal.toFixed(2)
sale.discount_amount.toFixed(2)
sale.total_amount.toFixed(2)

// After
parseFloat(item.unit_price).toFixed(2)
parseFloat(item.total_price).toFixed(2)
parseFloat(sale.subtotal).toFixed(2)
parseFloat(sale.discount_amount).toFixed(2)
parseFloat(sale.total_amount).toFixed(2)
```

---

## All Decimal Fields from Backend

These fields come as **strings** from the backend:

### SaleItem
- ✅ `unit_price` - string
- ✅ `discount_amount` - string
- ✅ `tax_amount` - string
- ✅ `total_price` - string
- ✅ `base_amount` - string
- ✅ `gross_amount` - string
- ✅ `profit_amount` - string
- ✅ `profit_margin` - string
- ❌ `quantity` - number (integer)

### Sale
- ✅ `subtotal` - string
- ✅ `discount_amount` - string
- ✅ `tax_amount` - string
- ✅ `total_amount` - string
- ✅ `amount_paid` - string
- ✅ `amount_due` - string

### Customer
- ✅ `credit_limit` - string
- ✅ `outstanding_balance` - string
- ✅ `available_credit` - string

### StockProduct
- ✅ `purchase_price` - string
- ✅ `wholesale_price` - string
- ✅ `retail_price` - string
- ❌ `quantity` - number (integer)

---

## Testing the Fix

### Before Fix
```
❌ TypeError: item.unit_price.toFixed is not a function
```

### After Fix
```
✅ Displays: GH₵ 60.00
✅ No errors in console
```

### Test These Scenarios
1. Add item to cart → Unit price displays correctly
2. Multiple items → All prices display correctly
3. Apply discount → Discount amount displays correctly
4. View total → Total amount displays correctly

---

## TypeScript Strict Mode (Optional)

If using TypeScript strict mode, create proper types:

```typescript
// types/api.ts
// Backend decimal fields are always strings
type DecimalString = string;

export interface SaleItemAPI {
  id: string;
  product: string;
  product_name: string;
  product_sku: string;
  quantity: number;
  unit_price: DecimalString;      // "60.00"
  discount_amount: DecimalString; // "0.00"
  total_price: DecimalString;     // "60.00"
}

// For internal use, you might want numbers
export interface SaleItemDisplay {
  id: string;
  product: string;
  product_name: string;
  product_sku: string;
  quantity: number;
  unit_price: number;      // 60.00
  discount_amount: number; // 0.00
  total_price: number;     // 60.00
}

// Converter function
export const toDisplaySaleItem = (api: SaleItemAPI): SaleItemDisplay => ({
  ...api,
  unit_price: parseFloat(api.unit_price),
  discount_amount: parseFloat(api.discount_amount),
  total_price: parseFloat(api.total_price),
});
```

---

## Summary

**Problem**: Backend sends decimals as strings, frontend tried to call number methods on them

**Solution**: Parse strings to numbers before using number methods:
```typescript
// ❌ Wrong
item.unit_price.toFixed(2)

// ✅ Correct
parseFloat(item.unit_price).toFixed(2)

// ✅ Or just use the string (already formatted)
item.unit_price
```

**Files to Fix**: 
- `SaleCart.tsx` (line ~161 and any other places using `.toFixed()`)
- Any other component displaying prices

**Quick Fix**: Find all `.toFixed(` and add `parseFloat()` wrapper for backend decimal fields.

---

**Last Updated**: October 4, 2025, 01:00  
**Issue**: Frontend TypeError on decimal fields  
**Status**: ✅ Solution provided
