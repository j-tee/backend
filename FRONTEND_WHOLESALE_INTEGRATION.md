# Frontend Integration: Wholesale & Retail Sales

Quick reference guide for implementing wholesale/retail toggle in your frontend.

---

## 🎯 Quick Start (5 Steps)

### Step 1: Add State for Sale Type

```typescript
// In your SalesPage.tsx or similar component
const [saleType, setSaleType] = useState<'RETAIL' | 'WHOLESALE'>('RETAIL');
const [currentSale, setCurrentSale] = useState<Sale | null>(null);
```

### Step 2: Create Sale with Type

```typescript
const createNewSale = async () => {
  const response = await fetch('/sales/api/sales/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Token ${authToken}`
    },
    body: JSON.stringify({
      storefront: storefrontId,
      type: saleType,  // ← 'RETAIL' or 'WHOLESALE'
      status: 'DRAFT'
    })
  });
  
  const sale = await response.json();
  setCurrentSale(sale);
};
```

### Step 3: Add Toggle Button UI

```tsx
<div className="sale-type-selector">
  <button
    className={`toggle-btn ${saleType === 'RETAIL' ? 'active' : ''}`}
    onClick={() => handleSaleTypeChange('RETAIL')}
    disabled={currentSale && currentSale.status !== 'DRAFT'}
  >
    🛒 Retail Sale
  </button>
  
  <button
    className={`toggle-btn ${saleType === 'WHOLESALE' ? 'active' : ''}`}
    onClick={() => handleSaleTypeChange('WHOLESALE')}
    disabled={currentSale && currentSale.status !== 'DRAFT'}
  >
    📦 Wholesale Sale
  </button>
</div>
```

### Step 4: Handle Type Change

```typescript
const handleSaleTypeChange = async (newType: 'RETAIL' | 'WHOLESALE') => {
  if (!currentSale) {
    // No active sale - just update state
    setSaleType(newType);
    return;
  }
  
  if (currentSale.status !== 'DRAFT') {
    toast.error('Cannot change sale type after completion');
    return;
  }
  
  // Call backend to toggle sale type and update all prices
  const response = await fetch(
    `/sales/api/sales/${currentSale.id}/toggle_sale_type/`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Token ${authToken}`
      },
      body: JSON.stringify({ type: newType })
    }
  );
  
  const result = await response.json();
  
  // Update state
  setCurrentSale(result.sale);
  setSaleType(result.sale.type);
  
  // Show notification
  toast.success(result.message);
  
  // Optionally show price changes
  if (result.updated_items?.length > 0) {
    toast.info(`Updated ${result.updated_items.length} items`);
  }
};
```

### Step 5: Display Price Based on Type

```tsx
const ProductCard = ({ product }: { product: Product }) => {
  // Determine which price to show
  const activePrice = saleType === 'WHOLESALE'
    ? product.wholesale_price || product.retail_price
    : product.retail_price;
  
  const hasWholesale = product.wholesale_price !== null;
  
  return (
    <div className="product-card">
      <h3>{product.product_name}</h3>
      <p className="sku">{product.sku}</p>
      
      {/* Price Display */}
      <div className="price-section">
        {hasWholesale ? (
          <div className="dual-price">
            <div className={saleType === 'RETAIL' ? 'price active' : 'price'}>
              <span className="label">Retail:</span>
              <span className="amount">GH₵ {product.retail_price}</span>
            </div>
            <div className={saleType === 'WHOLESALE' ? 'price active' : 'price'}>
              <span className="label">Wholesale:</span>
              <span className="amount">GH₵ {product.wholesale_price}</span>
            </div>
          </div>
        ) : (
          <div className="single-price">
            <span className="amount">GH₵ {product.retail_price}</span>
          </div>
        )}
      </div>
      
      <button onClick={() => addToCart(product)}>
        Add to Cart - GH₵ {activePrice}
      </button>
    </div>
  );
};
```

---

## 🎨 CSS Styling Example

```css
/* Sale Type Toggle */
.sale-type-selector {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  padding: 12px;
  background: #f5f5f5;
  border-radius: 8px;
}

.toggle-btn {
  flex: 1;
  padding: 12px 24px;
  border: 2px solid #ddd;
  background: white;
  border-radius: 6px;
  font-size: 16px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.toggle-btn:hover:not(:disabled) {
  border-color: #999;
}

.toggle-btn.active {
  background: #2563eb;
  color: white;
  border-color: #2563eb;
}

.toggle-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Product Card Pricing */
.dual-price {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin: 8px 0;
}

.price {
  display: flex;
  justify-content: space-between;
  padding: 6px 12px;
  background: #f9f9f9;
  border-radius: 4px;
  opacity: 0.6;
  transition: all 0.2s;
}

.price.active {
  opacity: 1;
  background: #e0f2fe;
  border: 1px solid #0284c7;
}

.price .label {
  font-size: 12px;
  color: #666;
}

.price .amount {
  font-weight: 600;
  font-size: 14px;
}

.price.active .amount {
  color: #0284c7;
}
```

---

## 📱 Complete Example Component

```tsx
import React, { useState, useEffect } from 'react';
import { toast } from 'react-toastify';

interface Product {
  product_id: string;
  product_name: string;
  sku: string;
  retail_price: string;
  wholesale_price: string | null;
  total_available: number;
}

interface Sale {
  id: string;
  type: 'RETAIL' | 'WHOLESALE';
  status: string;
  total_amount: string;
}

const SalesPage: React.FC = () => {
  const [saleType, setSaleType] = useState<'RETAIL' | 'WHOLESALE'>('RETAIL');
  const [currentSale, setCurrentSale] = useState<Sale | null>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const authToken = localStorage.getItem('authToken');
  
  // Fetch products
  useEffect(() => {
    fetchProducts();
  }, []);
  
  const fetchProducts = async () => {
    const response = await fetch(
      '/inventory/api/storefronts/multi-storefront-catalog/',
      {
        headers: { 'Authorization': `Token ${authToken}` }
      }
    );
    const data = await response.json();
    setProducts(data.products);
  };
  
  // Create new sale
  const startNewSale = async () => {
    const storefrontId = 'your-storefront-id';  // Get from state
    
    const response = await fetch('/sales/api/sales/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Token ${authToken}`
      },
      body: JSON.stringify({
        storefront: storefrontId,
        type: saleType,
        status: 'DRAFT'
      })
    });
    
    const sale = await response.json();
    setCurrentSale(sale);
    toast.success(`New ${saleType} sale started`);
  };
  
  // Toggle sale type
  const toggleSaleType = async (newType: 'RETAIL' | 'WHOLESALE') => {
    if (!currentSale) {
      setSaleType(newType);
      return;
    }
    
    if (currentSale.status !== 'DRAFT') {
      toast.error('Cannot change sale type after completion');
      return;
    }
    
    try {
      const response = await fetch(
        `/sales/api/sales/${currentSale.id}/toggle_sale_type/`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Token ${authToken}`
          },
          body: JSON.stringify({ type: newType })
        }
      );
      
      const result = await response.json();
      setCurrentSale(result.sale);
      setSaleType(result.sale.type);
      toast.success(result.message);
    } catch (error) {
      toast.error('Failed to change sale type');
    }
  };
  
  // Add item to cart
  const addToCart = async (product: Product) => {
    if (!currentSale) {
      toast.error('Please start a sale first');
      return;
    }
    
    const response = await fetch(
      `/sales/api/sales/${currentSale.id}/add_item/`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Token ${authToken}`
        },
        body: JSON.stringify({
          product: product.product_id,
          quantity: 1
          // No unit_price - backend auto-determines based on sale type!
        })
      }
    );
    
    if (response.ok) {
      toast.success(`Added ${product.product_name} to cart`);
      // Refresh sale to get updated totals
      refreshSale();
    }
  };
  
  const refreshSale = async () => {
    if (!currentSale) return;
    
    const response = await fetch(
      `/sales/api/sales/${currentSale.id}/`,
      {
        headers: { 'Authorization': `Token ${authToken}` }
      }
    );
    const sale = await response.json();
    setCurrentSale(sale);
  };
  
  return (
    <div className="sales-page">
      {/* Sale Type Toggle */}
      <div className="sale-type-selector">
        <button
          className={`toggle-btn ${saleType === 'RETAIL' ? 'active' : ''}`}
          onClick={() => toggleSaleType('RETAIL')}
          disabled={currentSale && currentSale.status !== 'DRAFT'}
        >
          🛒 Retail Sale
        </button>
        <button
          className={`toggle-btn ${saleType === 'WHOLESALE' ? 'active' : ''}`}
          onClick={() => toggleSaleType('WHOLESALE')}
          disabled={currentSale && currentSale.status !== 'DRAFT'}
        >
          📦 Wholesale Sale
        </button>
      </div>
      
      {/* Current Sale Info */}
      {currentSale && (
        <div className="current-sale-info">
          <h3>{saleType} Sale</h3>
          <p>Total: GH₵ {currentSale.total_amount}</p>
        </div>
      )}
      
      {/* Start Sale Button */}
      {!currentSale && (
        <button onClick={startNewSale}>
          Start New {saleType} Sale
        </button>
      )}
      
      {/* Product Grid */}
      <div className="product-grid">
        {products.map(product => (
          <ProductCard
            key={product.product_id}
            product={product}
            saleType={saleType}
            onAddToCart={addToCart}
          />
        ))}
      </div>
    </div>
  );
};

const ProductCard: React.FC<{
  product: Product;
  saleType: 'RETAIL' | 'WHOLESALE';
  onAddToCart: (product: Product) => void;
}> = ({ product, saleType, onAddToCart }) => {
  const activePrice = saleType === 'WHOLESALE'
    ? product.wholesale_price || product.retail_price
    : product.retail_price;
  
  const hasWholesale = product.wholesale_price !== null;
  
  return (
    <div className="product-card">
      <h3>{product.product_name}</h3>
      <p className="sku">{product.sku}</p>
      
      <div className="price-section">
        {hasWholesale ? (
          <div className="dual-price">
            <div className={saleType === 'RETAIL' ? 'price active' : 'price'}>
              <span className="label">Retail:</span>
              <span className="amount">GH₵ {product.retail_price}</span>
            </div>
            <div className={saleType === 'WHOLESALE' ? 'price active' : 'price'}>
              <span className="label">Wholesale:</span>
              <span className="amount">GH₵ {product.wholesale_price}</span>
            </div>
          </div>
        ) : (
          <div className="single-price">
            <span className="amount">GH₵ {product.retail_price}</span>
          </div>
        )}
      </div>
      
      <p className="stock">In stock: {product.total_available}</p>
      
      <button
        className="add-to-cart-btn"
        onClick={() => onAddToCart(product)}
      >
        Add to Cart - GH₵ {activePrice}
      </button>
    </div>
  );
};

export default SalesPage;
```

---

## ✅ Testing Checklist

After implementation, verify:

- [ ] Toggle button switches between RETAIL/WHOLESALE
- [ ] Creating sale uses selected type
- [ ] Products show correct price based on type
- [ ] Toggling mid-transaction updates all items
- [ ] Cannot toggle after sale completion
- [ ] Wholesale price shows if available, falls back to retail if not
- [ ] Sale total updates correctly when type changes
- [ ] Visual indicators clearly show active mode

---

## 🎯 Key Points

1. **Backend handles pricing** - Don't send `unit_price` when adding items, let backend auto-determine
2. **Toggle only for DRAFT sales** - Disable button once sale is completed
3. **Fallback to retail** - If wholesale price not set, backend uses retail price
4. **Show both prices** - Help user understand the price difference
5. **Clear visual feedback** - User should always know which mode they're in

---

**See Also**: `WHOLESALE_RETAIL_IMPLEMENTATION.md` for complete backend details
