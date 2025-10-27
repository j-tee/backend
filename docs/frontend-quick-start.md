# Frontend Quick Start Guide

## 🚀 Backend is Ready!

All core APIs for the POS frontend are **fully implemented and tested**. Here's what you can use immediately:

---

## ✅ Available Endpoints

### Base URLs
- **Inventory:** `http://localhost:8000/inventory/api/`
- **Sales:** `http://localhost:8000/sales/api/`
- **Accounts:** `http://localhost:8000/accounts/api/`

---

## 🔑 Quick Authentication Test

```bash
# Login
curl -X POST http://localhost:8000/accounts/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "your_user", "password": "your_password"}'

# Response includes token:
# {"token": "abc123...", "user": {...}, "business": {...}}
```

Use the token in all requests:
```bash
-H "Authorization: Token abc123..."
```

---

## 🛒 Core POS Workflow (Copy-Paste Ready)

### 1. Search Products (with Barcode Support!)

```bash
# Search by name/SKU
curl -H "Authorization: Token YOUR_TOKEN" \
  "http://localhost:8000/inventory/api/products/?search=milk"

# NEW! Barcode scan (optimized for POS)
curl -H "Authorization: Token YOUR_TOKEN" \
  "http://localhost:8000/inventory/api/products/by-barcode/1234567890123"

# Returns:
{
  "product": {...},
  "stock_products": [{...}],  # Available stock
  "has_stock": true,
  "total_quantity": 50.00
}
```

### 2. Create Cart

```bash
curl -X POST http://localhost:8000/sales/api/sales/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "storefront": "STOREFRONT_UUID",
    "type": "RETAIL",
    "payment_type": "CASH"
  }'

# Returns: {"id": "SALE_UUID", "status": "DRAFT", ...}
```

### 3. Add Items to Cart

```bash
curl -X POST http://localhost:8000/sales/api/sales/SALE_UUID/add_item/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "product": "PRODUCT_UUID",
    "stock_product": "STOCK_PRODUCT_UUID",
    "quantity": 2,
    "unit_price": 2.50
  }'

# Automatically:
# - Reserves stock for 30 minutes
# - Calculates totals
# - Validates stock availability
```

### 4. Complete Sale (Checkout)

```bash
curl -X POST http://localhost:8000/sales/api/sales/SALE_UUID/complete/ \
  -H "Authorization: Token YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "payment_type": "CASH",
    "amount_paid": 10.00
  }'

# Automatically:
# - Generates receipt number
# - Commits stock (deducts from inventory)
# - Releases reservations
# - Updates customer credit (if applicable)
# - Creates audit log
```

---

## 📦 Product & Stock APIs

```bash
# Get products with pagination
GET /inventory/api/products/?page=1&page_size=20

# Filter by category
GET /inventory/api/products/?category=CATEGORY_UUID

# Get active products only
GET /inventory/api/products/?is_active=true

# Check stock availability
GET /inventory/api/stock-products/?product=PRODUCT_UUID&has_quantity=true

# Get categories for filtering
GET /inventory/api/categories/
```

---

## 👥 Customer APIs

```bash
# Search customers
GET /sales/api/customers/?search=john

# Create customer
POST /sales/api/customers/
{
  "name": "John Smith",
  "phone": "+256700000000",
  "email": "john@example.com",
  "customer_type": "RETAIL",
  "credit_limit": 1000.00,
  "credit_terms_days": 30
}

# Check credit status
GET /sales/api/customers/CUSTOMER_UUID/credit_status/

# Returns:
{
  "credit_limit": 1000.00,
  "outstanding_balance": 250.00,
  "available_credit": 750.00,
  "can_purchase": true,
  "message": "Customer has available credit"
}
```

---

## 📊 Sales History

```bash
# List completed sales
GET /sales/api/sales/?status=COMPLETED

# Filter by date range
GET /sales/api/sales/?created_at__gte=2025-10-01T00:00:00Z&created_at__lte=2025-10-03T23:59:59Z

# Customer purchase history
GET /sales/api/sales/?customer=CUSTOMER_UUID&status=COMPLETED

# Get receipt details
GET /sales/api/sales/SALE_UUID/
```

---

## 🎯 What to Build in Your Frontend

### Phase 1: Product Search Component 🔴 HIGH PRIORITY

```jsx
// ProductSearch.jsx
const ProductSearch = ({ onAddToCart }) => {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);

  const searchProducts = debounce(async (query) => {
    setLoading(true);
    const response = await fetch(
      `/inventory/api/products/?search=${query}&is_active=true`,
      {
        headers: { 'Authorization': `Token ${token}` }
      }
    );
    const data = await response.json();
    setProducts(data.results);
    setLoading(false);
  }, 300);

  const handleBarcodeScan = async (barcode) => {
    const response = await fetch(
      `/inventory/api/products/by-barcode/${barcode}`,
      {
        headers: { 'Authorization': `Token ${token}` }
      }
    );
    const data = await response.json();
    
    if (data.has_stock) {
      onAddToCart(data.product, data.stock_products[0]);
    } else {
      alert('Product out of stock');
    }
  };

  return (
    <div>
      <input 
        type="text" 
        placeholder="Search or scan barcode..."
        onChange={(e) => searchProducts(e.target.value)}
      />
      {loading && <Spinner />}
      <ProductGrid products={products} onAddToCart={onAddToCart} />
    </div>
  );
};
```

### Phase 2: Cart Management Component 🔴 HIGH PRIORITY

```jsx
// SaleCart.jsx
const SaleCart = ({ saleId }) => {
  const [sale, setSale] = useState(null);

  const loadCart = async () => {
    const response = await fetch(`/sales/api/sales/${saleId}/`, {
      headers: { 'Authorization': `Token ${token}` }
    });
    const data = await response.json();
    setSale(data);
  };

  const addItem = async (product, stockProduct, quantity = 1) => {
    await fetch(`/sales/api/sales/${saleId}/add_item/`, {
      method: 'POST',
      headers: {
        'Authorization': `Token ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        product: product.id,
        stock_product: stockProduct.id,
        quantity: quantity,
        unit_price: stockProduct.retail_price
      })
    });
    loadCart();
  };

  const removeItem = async (itemId) => {
    await fetch(`/sales/api/sale-items/${itemId}/`, {
      method: 'DELETE',
      headers: { 'Authorization': `Token ${token}` }
    });
    loadCart();
  };

  const updateQuantity = async (itemId, newQuantity) => {
    await fetch(`/sales/api/sale-items/${itemId}/`, {
      method: 'PATCH',
      headers: {
        'Authorization': `Token ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ quantity: newQuantity })
    });
    loadCart();
  };

  return (
    <div>
      <h3>Cart Items</h3>
      {sale?.sale_items.map(item => (
        <CartItem 
          key={item.id}
          item={item}
          onUpdateQuantity={(qty) => updateQuantity(item.id, qty)}
          onRemove={() => removeItem(item.id)}
        />
      ))}
      <div className="totals">
        <div>Subtotal: {sale?.subtotal}</div>
        <div>Discount: {sale?.discount_amount}</div>
        <div>Total: {sale?.total_amount}</div>
      </div>
    </div>
  );
};
```

### Phase 3: Checkout Component 🔴 HIGH PRIORITY

```jsx
// Checkout.jsx
const Checkout = ({ saleId, onComplete }) => {
  const [paymentType, setPaymentType] = useState('CASH');
  const [amountPaid, setAmountPaid] = useState(0);

  const completeSale = async () => {
    const response = await fetch(`/sales/api/sales/${saleId}/complete/`, {
      method: 'POST',
      headers: {
        'Authorization': `Token ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        payment_type: paymentType,
        amount_paid: parseFloat(amountPaid)
      })
    });
    
    const result = await response.json();
    
    if (response.ok) {
      // Show receipt
      printReceipt(result);
      onComplete(result);
    } else {
      alert('Error completing sale');
    }
  };

  return (
    <div>
      <select value={paymentType} onChange={(e) => setPaymentType(e.target.value)}>
        <option value="CASH">Cash</option>
        <option value="CARD">Card</option>
        <option value="MOBILE">Mobile Money</option>
        <option value="CREDIT">Credit</option>
      </select>
      
      <input 
        type="number" 
        placeholder="Amount Paid"
        value={amountPaid}
        onChange={(e) => setAmountPaid(e.target.value)}
      />
      
      <button onClick={completeSale}>Complete Sale</button>
    </div>
  );
};
```

---

## 🐛 Error Handling Template

```javascript
const apiCall = async (url, options = {}) => {
  try {
    const response = await fetch(url, {
      ...options,
      headers: {
        'Authorization': `Token ${getToken()}`,
        'Content-Type': 'application/json',
        ...options.headers
      }
    });

    if (!response.ok) {
      const error = await response.json();
      
      // Handle specific errors
      if (response.status === 401) {
        // Redirect to login
        window.location.href = '/login';
        return;
      }
      
      if (response.status === 400) {
        // Validation error - show field errors
        Object.keys(error).forEach(field => {
          showFieldError(field, error[field][0]);
        });
        return;
      }
      
      throw new Error(JSON.stringify(error));
    }

    return await response.json();
  } catch (error) {
    console.error('API Error:', error);
    showToast('An error occurred. Please try again.', 'error');
    throw error;
  }
};
```

---

## 📝 Required Data from Backend

To start building, you'll need these IDs from your backend:

```bash
# 1. Get your storefront ID
GET /inventory/api/storefronts/

# 2. Get product categories
GET /inventory/api/categories/

# 3. Test products exist
GET /inventory/api/products/?page_size=5
```

---

## 🎨 Recommended UI Components

1. **SearchBar** - With autocomplete and barcode scan
2. **ProductCard** - Show name, price, stock level, image
3. **CartItem** - Editable quantity, remove button
4. **CustomerSelect** - Searchable dropdown
5. **PaymentModal** - Payment method and amount
6. **Receipt** - Printable receipt template

---

## 🚦 Backend Status

| Feature | Status | Endpoint |
|---------|--------|----------|
| Product Search | ✅ Ready | `GET /inventory/api/products/` |
| Barcode Scan | ✅ Ready | `GET /inventory/api/products/by-barcode/{code}` |
| Stock Check | ✅ Ready | `GET /inventory/api/stock-products/` |
| Create Cart | ✅ Ready | `POST /sales/api/sales/` |
| Add to Cart | ✅ Ready | `POST /sales/api/sales/{id}/add_item/` |
| Update Item | ✅ Ready | `PATCH /sales/api/sale-items/{id}/` |
| Remove Item | ✅ Ready | `DELETE /sales/api/sale-items/{id}/` |
| Complete Sale | ✅ Ready | `POST /sales/api/sales/{id}/complete/` |
| Customer Search | ✅ Ready | `GET /sales/api/customers/` |
| Create Customer | ✅ Ready | `POST /sales/api/customers/` |
| Credit Check | ✅ Ready | `GET /sales/api/customers/{id}/credit_status/` |
| Sales History | ✅ Ready | `GET /sales/api/sales/` |

---

## 💡 Tips for Development

### 1. Use React Query or SWR for caching
```javascript
import { useQuery } from 'react-query';

const useProducts = (search) => {
  return useQuery(['products', search], () =>
    fetch(`/inventory/api/products/?search=${search}`)
      .then(r => r.json())
  );
};
```

### 2. Debounce search inputs
```javascript
import { debounce } from 'lodash';

const debouncedSearch = debounce((value) => {
  searchProducts(value);
}, 300);
```

### 3. Handle loading states
```javascript
const [loading, setLoading] = useState(false);

// Show spinner during API calls
{loading && <Spinner />}
```

### 4. Keyboard shortcuts for POS
```javascript
// Enter to checkout
// F9 for new sale
// ESC to cancel
useEffect(() => {
  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      completeSale();
    }
  };
  window.addEventListener('keydown', handleKeyPress);
  return () => window.removeEventListener('keydown', handleKeyPress);
}, []);
```

---

## ❓ Need Help?

### Questions to Clarify:

1. **Barcode Scanner Type:**
   - USB barcode scanner (acts as keyboard)? ✅ Supported
   - Camera-based scanning? Need to add QR code library

2. **Payment Integration:**
   - Stripe? I can add webhook endpoints
   - Mobile Money (MTN, Airtel)? Need API credentials

3. **Offline Support:**
   - Should POS work offline? Need to implement service worker

4. **Multi-terminal:**
   - Multiple POS terminals? Stock reservations handle this

5. **Receipt Printing:**
   - Thermal printer? Use browser print API
   - Email receipt? I can add email endpoint

---

## 🎯 Your Action Items

### To Start Building:

1. ✅ **Backend is ready** - All endpoints working
2. 📝 **Get test credentials** - Ask for login details
3. 🔑 **Test authentication** - Login and get token
4. 🛒 **Test one complete flow** - Create cart → Add item → Complete
5. 💻 **Build ProductSearch component** - Start here
6. 🛒 **Build Cart component** - Then this
7. 💳 **Build Checkout** - Finally this

---

## 📚 Full Documentation

See `frontend-sales-integration-guide.md` for:
- Complete API reference
- All data structures
- Error handling
- Performance optimization
- Complete workflow examples

---

## 🚀 Ready to Build!

The backend is **fully functional** and **production-ready** for Phase 1:
- ✅ All CRUD operations
- ✅ Stock reservations (prevent overselling)
- ✅ Multi-tenant isolation
- ✅ Audit logging
- ✅ Credit management
- ✅ Performance optimized (pagination, select_related, indexes)

**Start building your frontend now!** 🎉
