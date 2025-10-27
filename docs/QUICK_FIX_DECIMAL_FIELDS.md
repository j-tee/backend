# 🚨 Quick Fix: SaleCart.tsx TypeError

## The Error
```
TypeError: item.unit_price.toFixed is not a function
```

## The Cause
Backend sends decimal values as **strings**, not numbers:
```json
{
  "unit_price": "60.00"   ← String, not number!
}
```

## The Fix (Line 161)

### ❌ Current Code (BROKEN)
```typescript
<span>GH₵ {item.unit_price.toFixed(2)}</span>
```

### ✅ Fixed Code (OPTION 1 - Parse to number)
```typescript
<span>GH₵ {parseFloat(item.unit_price).toFixed(2)}</span>
```

### ✅ Fixed Code (OPTION 2 - Use string directly)
```typescript
<span>GH₵ {item.unit_price}</span>
```

## Fix All Instances

Replace ALL occurrences in your file:

```typescript
// Unit prices
parseFloat(item.unit_price).toFixed(2)

// Total prices  
parseFloat(item.total_price).toFixed(2)

// Sale subtotal
parseFloat(sale.subtotal).toFixed(2)

// Sale total
parseFloat(sale.total_amount).toFixed(2)

// Discounts
parseFloat(sale.discount_amount).toFixed(2)
```

## Better Solution: Create Helper

```typescript
// At top of file
const formatPrice = (price: string | number) => {
  return typeof price === 'string' ? parseFloat(price).toFixed(2) : price.toFixed(2);
};

// Use everywhere
<span>GH₵ {formatPrice(item.unit_price)}</span>
<span>GH₵ {formatPrice(item.total_price)}</span>
<span>GH₵ {formatPrice(sale.total_amount)}</span>
```

## All Decimal Fields from Backend

These are **STRINGS**, not numbers:
- `unit_price` ✅ string
- `total_price` ✅ string
- `discount_amount` ✅ string
- `subtotal` ✅ string
- `total_amount` ✅ string
- `amount_paid` ✅ string
- `amount_due` ✅ string
- `retail_price` ✅ string
- `wholesale_price` ✅ string

These are **NUMBERS**:
- `quantity` ✅ number

## Test After Fix

1. Refresh page
2. Add item to cart
3. Should see: "GH₵ 60.00" (not error)
4. Check console: No errors ✅

---

**See full documentation**: `docs/frontend-decimal-fields-fix.md`
