# POS SaaS Backend - Comprehensive API Documentation

## Overview

This comprehensive documentation covers the complete Point of Sale (POS) SaaS backend application, consolidating all API specifications, business logic, and integration guidelines into a single reference. The system provides multi-tenant retail management with inventory tracking, sales processing, financial management, and subscription billing.

### Application Architecture

The POS SaaS backend is built with Django REST Framework and supports:
- **Multi-tenant business operations** with complete data isolation
- **Role-based access control** (Owner, Admin, Manager, Staff)
- **Real-time inventory management** with cost tracking
- **Complete sales processing** with multiple payment methods
- **Financial bookkeeping** with double-entry accounting
- **Subscription management** with automated billing

### Technology Stack
- **Backend**: Django 4.x + Django REST Framework
- **Database**: PostgreSQL with UUID primary keys
- **Authentication**: Token-based with business scoping
- **Caching**: Redis (planned)
- **Background Tasks**: Celery
- **Real-time**: Django Channels (planned)

---

## API Fundamentals

### Base URL
```
Development: http://localhost:8000
Production: https://api.yourdomain.com
```

### Authentication
All API requests require token authentication:
```http
Authorization: Token <your-auth-token>
Content-Type: application/json
```

### Common Response Patterns

#### Success Response
```json
{
  "count": 25,
  "next": "http://api.example.com/endpoint/?page=2",
  "previous": null,
  "results": [...]
}
```

#### Error Response
```json
{
  "field_name": ["Error message"],
  "detail": "General error message"
}
```

### Pagination
All list endpoints support pagination:
```http
GET /api/endpoint/?page=1&page_size=25
```
- Default page size: 25 items
- Maximum page size: 100 items
- Page size is configurable via `page_size` parameter

### Filtering & Ordering
```http
GET /api/endpoint/?search=term&field=value&ordering=-created_at
```

---

## 1. Authentication & User Management

### 1.1 User Registration

#### Owner Registration
```http
POST /accounts/api/auth/register/
Content-Type: application/json

{
  "name": "Jane Doe",
  "email": "jane@example.com",
  "password": "securepassword123",
  "account_type": "OWNER"
}
```

**Response (201):**
```json
{
  "message": "Account created. Check your email for the verification link.",
  "user_id": "uuid-string",
  "account_type": "OWNER"
}
```

#### Employee Registration
Employees must be invited before registration:
```http
POST /accounts/api/auth/register/
Content-Type: application/json

{
  "name": "John Employee",
  "email": "john@invited.com",
  "password": "securepassword123",
  "account_type": "EMPLOYEE"
}
```

### 1.2 Email Verification
```http
POST /accounts/api/auth/verify-email/
Content-Type: application/json

{
  "token": "verification-token-from-email"
}
```

**Response (200):**
```json
{
  "message": "Email verified successfully. You can now log in.",
  "user_id": "uuid",
  "account_type": "OWNER"
}
```

### 1.3 Business Registration (Owners Only)
```http
POST /accounts/api/auth/register-business/
Authorization: Token <auth-token>
Content-Type: application/json

{
  "name": "Jane's Retail Store",
  "tin": "TIN-001122",
  "email": "contact@janesretail.com",
  "address": "123 Main Street, City, Country",
  "phone_numbers": ["+1234567890"],
  "website": "https://janesretail.com",
  "social_handles": {
    "instagram": "@janesretail",
    "facebook": "janesretail"
  }
}
```

### 1.4 Authentication

#### Login
```http
POST /accounts/api/auth/login/
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "password"
}
```

**Response (200):**
```json
{
  "token": "auth-token-string",
  "user": {
    "id": "uuid",
    "name": "User Name",
    "email": "user@example.com",
    "account_type": "OWNER",
    "email_verified": true,
    "is_active": true,
    "subscription_status": "Active",
    "created_at": "2025-01-01T00:00:00Z"
  }
}
```

#### Logout
```http
POST /accounts/api/auth/logout/
Authorization: Token <auth-token>
```

#### Password Change
```http
POST /accounts/api/auth/change-password/
Authorization: Token <auth-token>
Content-Type: application/json

{
  "old_password": "currentpassword",
  "new_password": "newsecurepassword"
}
```

### 1.5 User Management

#### List Users
```http
GET /accounts/api/users/?search=jane&page=1
Authorization: Token <auth-token>
```

#### Current User Profile
```http
GET /accounts/api/users/me/
Authorization: Token <auth-token>
```

#### Update User
```http
PATCH /accounts/api/users/{id}/
Authorization: Token <auth-token>
Content-Type: application/json

{
  "name": "Updated Name",
  "email": "newemail@example.com"
}
```

### 1.6 Role Management

#### List Roles
```http
GET /accounts/api/roles/
Authorization: Token <auth-token>
```

#### Business Memberships
```http
GET /accounts/api/business-memberships/
POST /accounts/api/business-memberships/
Authorization: Token <auth-token>
```

---

## 2. Inventory Management

### 2.1 Core Concepts

#### Product Catalog
Products contain catalog metadata. Pricing is managed at the stock level.

#### Stock Architecture
- **Stock Batches**: Group items from the same delivery/purchase
- **Stock Products**: Individual items with supplier-specific costs
- **Cost Calculation**: Automatic tax and landed cost computation

### 2.2 Categories
```http
GET /inventory/api/categories/
POST /inventory/api/categories/
Authorization: Token <auth-token>
```

### 2.3 Products

#### List Products
```http
GET /inventory/api/products/?page=1&page_size=25&category=<uuid>&is_active=true&search=laptop&ordering=name
Authorization: Token <auth-token>
```

#### Create Product
```http
POST /inventory/api/products/
Authorization: Token <auth-token>
Content-Type: application/json

{
  "name": "Wireless Mouse",
  "sku": "WM-001",
  "category": "category-uuid",
  "unit": "piece",
  "description": "Ergonomic wireless mouse",
  "is_active": true
}
```

#### Update Product
```http
PATCH /inventory/api/products/{id}/
Authorization: Token <auth-token>
Content-Type: application/json

{
  "description": "Updated description",
  "is_active": false
}
```

### 2.4 Stock Batches

#### List Stock Batches
```http
GET /inventory/api/stock/?warehouse=<uuid>&search=electronics&ordering=-arrival_date&page_size=20
Authorization: Token <auth-token>
```

#### Create Stock Batch
```http
POST /inventory/api/stock/
Authorization: Token <auth-token>
Content-Type: application/json

{
  "warehouse": "warehouse-uuid",
  "arrival_date": "2025-10-01",
  "description": "October Electronics Shipment"
}
```

### 2.5 Stock Products

#### List Stock Products
```http
GET /inventory/api/stock-products/?product=<uuid>&stock=<uuid>&supplier=<uuid>&has_quantity=true&search=mouse&ordering=-created_at&page_size=50
Authorization: Token <auth-token>
```

#### Create Stock Product
```http
POST /inventory/api/stock-products/
Authorization: Token <auth-token>
Content-Type: application/json

{
  "stock": "stock-batch-uuid",
  "product": "product-uuid",
  "supplier": "supplier-uuid",
  "quantity": 50,
  "unit_cost": "15.00",
  "unit_tax_rate": "10.00",
  "unit_additional_cost": "2.00",
  "retail_price": "25.00",
  "wholesale_price": "20.00",
  "expiry_date": "2026-10-01",
  "description": "Black wireless mouse"
}
```

**Cost Calculation Logic:**
- `unit_tax_amount = unit_cost × unit_tax_rate ÷ 100` (auto-calculated)
- `landed_unit_cost = unit_cost + unit_tax_amount + unit_additional_cost`
- Total costs: `total_* = unit_* × quantity`

#### Update Stock Product
```http
PATCH /inventory/api/stock-products/{id}/
Authorization: Token <auth-token>
Content-Type: application/json

{
  "quantity": 45,
  "unit_cost": "16.00"
}
```

### 2.6 Suppliers

#### List Suppliers
```http
GET /inventory/api/suppliers/?search=tech&ordering=name&page_size=25
Authorization: Token <auth-token>
```

#### Create Supplier
```http
POST /inventory/api/suppliers/
Authorization: Token <auth-token>
Content-Type: application/json

{
  "name": "Tech Supplies Inc",
  "contact_person": "John Smith",
  "email": "john@techsupplies.com",
  "phone_number": "+1-555-0123",
  "address": "123 Tech Street, Silicon Valley, CA",
  "notes": "Reliable electronics supplier"
}
```

### 2.7 Warehouses

#### List Warehouses
```http
GET /inventory/api/warehouses/
Authorization: Token <auth-token>
```

#### Create Warehouse
```http
POST /inventory/api/warehouses/
Authorization: Token <auth-token>
Content-Type: application/json

{
  "name": "Main Warehouse",
  "location": "Industrial District",
  "manager": "user-uuid" // optional
}
```

#### Warehouse-Employee Assignments
```http
GET /inventory/api/warehouse-employees/
POST /inventory/api/warehouse-employees/
Authorization: Token <auth-token>
```

### 2.8 Storefronts

#### List Storefronts
```http
GET /inventory/api/storefronts/
Authorization: Token <auth-token>
```

#### Create Storefront
```http
POST /inventory/api/storefronts/
Authorization: Token <auth-token>
Content-Type: application/json

{
  "name": "Downtown Store",
  "location": "123 Main Street",
  "manager": "user-uuid" // optional
}
```

#### Storefront-Employee Assignments
```http
GET /inventory/api/storefront-employees/
POST /inventory/api/storefront-employees/
Authorization: Token <auth-token>
```

### 2.9 Business Workspace
```http
GET /inventory/api/owner/workspace/
Authorization: Token <auth-token>
```

**Response:**
```json
{
  "business": {
    "id": "business-uuid",
    "name": "Jane's Retail",
    "storefront_count": 2,
    "warehouse_count": 1
  },
  "storefronts": [...],
  "warehouses": [...]
}
```

### 2.10 Inventory Operations

#### Current Inventory Levels
```http
GET /inventory/api/inventory/
Authorization: Token <auth-token>
```

#### Stock Transfers
```http
GET /inventory/api/transfers/
POST /inventory/api/transfers/
Authorization: Token <auth-token>
Content-Type: application/json

{
  "product": "product-uuid",
  "stock": "stock-uuid",
  "from_warehouse": "warehouse-uuid",
  "to_storefront": "storefront-uuid",
  "quantity": 10,
  "note": "Restocking downtown store"
}
```

#### Stock Alerts
```http
GET /inventory/api/stock-alerts/
Authorization: Token <auth-token>
```

---

## 3. Sales & Transactions

### 3.1 Customer Management

#### List Customers
```http
GET /sales/api/customers/?search=john&page=1
Authorization: Token <auth-token>
```

#### Create Customer
```http
POST /sales/api/customers/
Authorization: Token <auth-token>
Content-Type: application/json

{
  "name": "John Doe",
  "email": "john@example.com",
  "phone": "+1234567890",
  "address": "123 Customer Street",
  "credit_limit": "1000.00"
}
```

#### Update Customer
```http
PATCH /sales/api/customers/{id}/
Authorization: Token <auth-token>
Content-Type: application/json

{
  "credit_limit": "1500.00"
}
```

### 3.2 Sales Processing

#### Create Sale
```http
POST /sales/api/sales/
Authorization: Token <auth-token>
Content-Type: application/json

{
  "storefront": "storefront-uuid",
  "customer": "customer-uuid", // optional
  "user": "cashier-uuid", // auto-populated
  "payment_type": "CASH",
  "type": "RETAIL",
  "discount_amount": "5.00",
  "items": [
    {
      "product": "product-uuid",
      "stock": "stock-uuid",
      "quantity": 2,
      "unit_price": "25.00",
      "discount_amount": "1.00"
    }
  ]
}
```

**Sale Statuses:**
- `COMPLETED`: Successful transaction
- `PENDING`: Awaiting payment/approval
- `REFUNDED`: Fully refunded
- `PARTIAL`: Partially refunded
- `CANCELLED`: Cancelled transaction

#### List Sales
```http
GET /sales/api/sales/?customer=<uuid>&status=COMPLETED&date_from=2025-01-01&ordering=-created_at
Authorization: Token <auth-token>
```

### 3.3 Payment Processing

#### Process Payment
```http
POST /sales/api/payments/
Authorization: Token <auth-token>
Content-Type: application/json

{
  "sale": "sale-uuid",
  "customer": "customer-uuid", // optional, for credit payments
  "amount_paid": "45.00",
  "payment_method": "CASH"
}
```

**Payment Methods:**
- `CASH`: Cash payment
- `CARD`: Credit/debit card
- `MOBILE`: Mobile money
- `CREDIT`: Customer credit
- `BANK_TRANSFER`: Bank transfer
- `MOMO`: Mobile money (MTN/Airtel)
- `PAYSTACK`: Paystack payment
- `STRIPE`: Stripe payment

### 3.4 Refunds & Returns

#### Create Refund
```http
POST /sales/api/refunds/
Authorization: Token <auth-token>
Content-Type: application/json

{
  "sale": "sale-uuid",
  "refund_type": "PARTIAL",
  "amount": "25.00",
  "reason": "Customer returned damaged item",
  "requested_by": "user-uuid",
  "items": [
    {
      "sale_item": "sale-item-uuid",
      "quantity": 1,
      "amount": "25.00"
    }
  ]
}
```

**Refund Types:**
- `FULL`: Complete refund
- `PARTIAL`: Partial refund
- `EXCHANGE`: Exchange for different items

### 3.5 Credit Management

#### Credit Transactions
```http
GET /sales/api/credit-transactions/?customer=<uuid>&transaction_type=CREDIT_SALE
Authorization: Token <auth-token>
```

**Transaction Types:**
- `CREDIT_SALE`: Sale on credit
- `PAYMENT`: Credit payment
- `ADJUSTMENT`: Manual adjustment
- `REFUND`: Credit refund

---

## 4. Reporting & Analytics

### 4.1 Inventory Reports

#### Inventory Valuation Export
```http
GET /reports/inventory/valuation/?format=excel&warehouse_id=<uuid>&product_id=<uuid>
Authorization: Token <auth-token>
```

**Supported Formats:** `excel`, `pdf`, `docx`

**Response:** File download with appropriate content type

#### Inventory Summary (Placeholder)
```http
GET /inventory/api/reports/inventory-summary/
Authorization: Token <auth-token>
```
*Currently returns empty array - UI ready for future implementation*

### 4.2 Sales Reports (Placeholder)
```http
GET /sales/api/reports/sales/
Authorization: Token <auth-token>
```
*Currently returns empty array - UI ready for future implementation*

### 4.3 Customer Credit Reports (Placeholder)
```http
GET /sales/api/reports/customer-credit/
Authorization: Token <auth-token>
```
*Currently returns empty array - UI ready for future implementation*

### 4.4 Financial Reports (Placeholder)
```http
GET /bookkeeping/api/reports/financial/
Authorization: Token <auth-token>
```
*Currently returns empty array - UI ready for future implementation*

---

## 5. Bookkeeping & Accounting

### 5.1 Chart of Accounts

#### Account Types
```http
GET /bookkeeping/api/account-types/
Authorization: Token <auth-token>
```

#### Accounts
```http
GET /bookkeeping/api/accounts/
POST /bookkeeping/api/accounts/
Authorization: Token <auth-token>
Content-Type: application/json

{
  "name": "Sales Revenue",
  "account_type": "account-type-uuid",
  "code": "4000",
  "description": "Revenue from product sales"
}
```

### 5.2 Journal Entries

#### Create Journal Entry
```http
POST /bookkeeping/api/journal-entries/
Authorization: Token <auth-token>
Content-Type: application/json

{
  "date": "2025-10-01",
  "description": "Daily sales entry",
  "lines": [
    {
      "account": "revenue-account-uuid",
      "debit": "1000.00",
      "credit": "0.00"
    },
    {
      "account": "cash-account-uuid",
      "debit": "0.00",
      "credit": "1000.00"
    }
  ]
}
```

#### List Journal Entries
```http
GET /bookkeeping/api/journal-entries/?date_from=2025-01-01&date_to=2025-12-31
Authorization: Token <auth-token>
```

### 5.3 Financial Periods & Budgets
```http
GET /bookkeeping/api/financial-periods/
GET /bookkeeping/api/budgets/
POST /bookkeeping/api/budgets/
Authorization: Token <auth-token>
```

### 5.4 Trial Balances
```http
GET /bookkeeping/api/trial-balances/
Authorization: Token <auth-token>
```

---

## 6. Subscription & Billing

### 6.1 Subscription Plans
```http
GET /subscriptions/api/plans/
Authorization: Token <auth-token>
```

### 6.2 Subscription Management

#### Create Subscription
```http
POST /subscriptions/api/subscriptions/
Authorization: Token <auth-token>
Content-Type: application/json

{
  "plan": "plan-uuid",
  "auto_renew": true
}
```

#### List Subscriptions
```http
GET /subscriptions/api/subscriptions/
Authorization: Token <auth-token>
```

### 6.3 Payment Processing

#### Process Payment
```http
POST /subscriptions/api/payments/
Authorization: Token <auth-token>
Content-Type: application/json

{
  "subscription": "subscription-uuid",
  "amount": "99.00",
  "payment_method": "CARD"
}
```

#### List Payments
```http
GET /subscriptions/api/payments/
Authorization: Token <auth-token>
```

### 6.4 Webhook Handling
```http
POST /subscriptions/api/webhooks/payment/
Content-Type: application/json

{
  "event_type": "payment.succeeded",
  "payment_id": "gateway-payment-id",
  "amount": "99.00",
  "subscription_id": "subscription-id"
}
```

### 6.5 Usage Tracking & Invoices
```http
GET /subscriptions/api/usage-tracking/
GET /subscriptions/api/invoices/
Authorization: Token <auth-token>
```

---

## 7. Business Logic & Validation Rules

### 7.1 Cost Calculations

#### Stock Product Costs
- **Tax Amount**: `unit_tax_amount = unit_cost × (unit_tax_rate ÷ 100)`
- **Landed Cost**: `unit_cost + unit_tax_amount + unit_additional_cost`
- **Total Costs**: `total_field = unit_field × quantity`

#### Sales Calculations
- **Item Total**: `(unit_price × quantity) - discount_amount`
- **Sale Total**: `Σ(item_totals) - sale_discount`
- **Tax Calculation**: `taxable_amount × tax_rate ÷ 100`

### 7.2 Business Scoping
- All data is automatically scoped to the authenticated user's business
- Users can only access resources within their business context
- Cross-business data access is prevented at the database level

### 7.3 Permission Levels

| Role | Permissions |
|------|-------------|
| **OWNER** | Full business control, billing access, user management |
| **ADMIN** | User management, business settings, full operational access |
| **MANAGER** | Operational oversight, reporting, inventory management |
| **STAFF** | Basic operational tasks (sales, inventory updates) |

### 7.4 Validation Rules

#### Products
- SKU must be unique within business
- Category must exist
- Unit must be valid (piece, kg, liter, etc.)

#### Stock
- Warehouse must belong to user's business
- Products must exist in catalog
- Quantities must be positive
- Costs must be valid decimal numbers

#### Sales
- Storefront must belong to user's business
- Products must have available inventory
- Payment amounts must match sale totals
- Credit limits cannot be exceeded

### 7.5 Subscription Gates
Critical business functions require active subscriptions:
- Sales creation and payment processing
- Sensitive financial reports
- Advanced analytics features

---

## 8. Error Handling & Status Codes

### HTTP Status Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| 200 | Success | GET, PUT, PATCH successful |
| 201 | Created | POST successful |
| 204 | No Content | DELETE successful |
| 400 | Bad Request | Validation errors, malformed data |
| 401 | Unauthorized | Missing/invalid token |
| 403 | Forbidden | Insufficient permissions, subscription required |
| 404 | Not Found | Resource doesn't exist |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error |

### Common Error Responses

#### Validation Errors
```json
{
  "field_name": ["This field is required."],
  "email": ["Enter a valid email address."]
}
```

#### Permission Denied
```json
{
  "detail": "You do not have permission to perform this action."
}
```

#### Business Scoping
```json
{
  "detail": "This resource belongs to a different business."
}
```

#### Subscription Required
```json
{
  "detail": "Active subscription required for this feature."
}
```

---

## 9. Frontend Integration Guidelines

### 9.1 API Client Setup

#### Axios Configuration
```javascript
import axios from 'axios';

const apiClient = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'http://localhost:8000',
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('authToken');
  if (token) {
    config.headers.Authorization = `Token ${token}`;
  }
  return config;
});

// Response interceptor
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('authToken');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export default apiClient;
```

### 9.2 State Management Patterns

#### Authentication Store
```javascript
const useAuth = () => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const login = async (email, password) => {
    const response = await apiClient.post('/accounts/api/auth/login/', {
      email,
      password
    });
    const { token, user } = response.data;
    localStorage.setItem('authToken', token);
    setUser(user);
    return user;
  };

  const logout = async () => {
    await apiClient.post('/accounts/api/auth/logout/');
    localStorage.removeItem('authToken');
    setUser(null);
  };

  return { user, login, logout, loading };
};
```

#### Paginated Data Hook
```javascript
const usePaginatedData = (endpoint, initialFilters = {}) => {
  const [data, setData] = useState([]);
  const [pagination, setPagination] = useState({});
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState(initialFilters);

  const fetchData = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value) params.append(key, value);
    });

    const response = await apiClient.get(`${endpoint}?${params}`);
    setData(response.data.results);
    setPagination({
      count: response.data.count,
      next: response.data.next,
      previous: response.data.previous
    });
    setLoading(false);
  }, [endpoint, filters]);

  useEffect(() => { fetchData(); }, [fetchData]);

  return {
    data,
    pagination,
    loading,
    updateFilters: (newFilters) => setFilters(prev => ({ ...prev, ...newFilters, page: 1 })),
    changePage: (page) => setFilters(prev => ({ ...prev, page })),
    refetch: fetchData
  };
};
```

### 9.3 Form Handling

#### Create/Update Operations
```javascript
const useFormSubmission = (endpoint, method = 'post') => {
  const [loading, setLoading] = useState(false);
  const [errors, setErrors] = useState({});

  const submit = async (data) => {
    setLoading(true);
    setErrors({});
    try {
      const response = await apiClient[method](endpoint, data);
      return response.data;
    } catch (error) {
      if (error.response?.status === 400) {
        setErrors(error.response.data);
      }
      throw error;
    } finally {
      setLoading(false);
    }
  };

  return { submit, loading, errors };
};
```

### 9.4 Error Handling

#### Global Error Handler
```javascript
const handleApiError = (error, showNotification) => {
  const status = error.response?.status;
  const data = error.response?.data;

  switch (status) {
    case 400:
      // Validation errors
      if (data && typeof data === 'object') {
        Object.keys(data).forEach(field => {
          const messages = Array.isArray(data[field]) ? data[field] : [data[field]];
          messages.forEach(message => {
            showNotification(`${field}: ${message}`, 'error');
          });
        });
      }
      break;

    case 403:
      if (data?.detail?.includes('subscription')) {
        showNotification('This feature requires an active subscription', 'warning');
        // Redirect to billing
      } else {
        showNotification('You do not have permission to perform this action', 'error');
      }
      break;

    case 404:
      showNotification('The requested resource was not found', 'error');
      break;

    default:
      showNotification('An unexpected error occurred', 'error');
  }
};
```

### 9.5 Real-time Considerations

The backend is architected to support WebSocket connections for real-time updates:
- Inventory level changes
- Sales transaction notifications
- Stock alert triggers
- Transfer status updates

*Implementation planned for future release*

---

## 10. Testing & Quality Assurance

### 10.1 Testing Strategy

#### Unit Tests
- Model methods and business logic
- Serializer validation
- Cost calculation algorithms
- Permission checks

#### Integration Tests
- API endpoint functionality
- Authentication flows
- Business workflow completion
- Cross-entity relationships

#### End-to-End Tests
- Complete user journeys
- Critical business workflows
- Performance validation
- Multi-tenant isolation

### 10.2 Test Data Setup

#### Create Test Business
```python
# Django shell or test setup
from accounts.models import User, Business
from inventory.models import Warehouse, StoreFront, Product, Stock, StockProduct

# Create test user and business
user = User.objects.create_user(
    email='test@example.com',
    password='testpass123',
    name='Test Owner',
    account_type='OWNER'
)

business = Business.objects.create(
    name='Test Business',
    owner=user,
    tin='TEST-001'
)

# Create warehouse and storefront
warehouse = Warehouse.objects.create(
    name='Test Warehouse',
    location='Test Location',
    business_link=business
)

storefront = StoreFront.objects.create(
    name='Test Store',
    location='Test Location',
    user=user,
    business_link=business
)

# Create product and stock
product = Product.objects.create(
    name='Test Product',
    sku='TEST-001',
    category=category,
    unit='piece'
)

stock_batch = Stock.objects.create(
    warehouse=warehouse,
    arrival_date='2025-01-01',
    description='Test stock'
)

stock_product = StockProduct.objects.create(
    stock=stock_batch,
    product=product,
    quantity=100,
    unit_cost='10.00'
)
```

### 10.3 API Testing Examples

#### Test Authentication
```bash
# Login
curl -X POST http://localhost:8000/accounts/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass123"}'

# Use token for authenticated requests
curl -H "Authorization: Token <token>" \
  http://localhost:8000/inventory/api/products/
```

#### Test CRUD Operations
```bash
# Create product
curl -X POST http://localhost:8000/inventory/api/products/ \
  -H "Authorization: Token <token>" \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Product","sku":"TEST-001","category":"category-uuid","unit":"piece"}'

# List with filtering
curl "http://localhost:8000/inventory/api/products/?search=test&page_size=10" \
  -H "Authorization: Token <token>"
```

---

## 11. Deployment & Operations

### 11.1 Environment Configuration

#### Required Environment Variables
```env
# Django Settings
DEBUG=False
SECRET_KEY=your-production-secret-key
DATABASE_URL=postgres://user:password@host:5432/dbname
REDIS_URL=redis://host:6379/0

# Email Configuration
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.yourprovider.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@domain.com
EMAIL_HOST_PASSWORD=your-email-password

# Payment Gateways
STRIPE_PUBLIC_KEY=pk_live_...
STRIPE_SECRET_KEY=sk_live_...
PAYSTACK_PUBLIC_KEY=pk_live_...
PAYSTACK_SECRET_KEY=sk_live_...

# File Storage (if using)
AWS_ACCESS_KEY_ID=your-aws-key
AWS_SECRET_ACCESS_KEY=your-aws-secret
AWS_STORAGE_BUCKET_NAME=your-bucket
```

### 11.2 Production Deployment Checklist

#### Security
- [ ] `DEBUG=False`
- [ ] `SECRET_KEY` is production-specific
- [ ] `SECURE_SSL_REDIRECT=True`
- [ ] `SECURE_HSTS_SECONDS=31536000`
- [ ] Database credentials are secure
- [ ] API rate limiting configured

#### Performance
- [ ] Database indexes optimized
- [ ] Static files served via CDN
- [ ] Redis caching enabled
- [ ] Database connection pooling configured

#### Monitoring
- [ ] Error logging configured (Sentry, etc.)
- [ ] Performance monitoring (New Relic, DataDog)
- [ ] Database query monitoring
- [ ] Uptime monitoring

#### Backup & Recovery
- [ ] Database backups scheduled
- [ ] File storage backups configured
- [ ] Recovery procedures documented
- [ ] Business continuity plan in place

### 11.3 Scaling Considerations

#### Horizontal Scaling
- **Application**: Multiple Django instances behind load balancer
- **Database**: PostgreSQL with read replicas
- **Cache**: Redis Cluster
- **Background Tasks**: Multiple Celery workers

#### Database Optimization
- Connection pooling
- Query optimization
- Index management
- Partitioning for large tables

---

## 12. API Versioning & Evolution

### Versioning Strategy
- API versioning via URL prefixes: `/api/v1/`
- Backward compatibility maintained for 2 major versions
- Deprecation warnings in response headers
- Migration guides provided for breaking changes

### Change Management
- New features added without breaking changes when possible
- Breaking changes announced 3 months in advance
- Comprehensive testing before deployment
- Rollback procedures documented

---

## 13. Support & Troubleshooting

### Common Issues

#### Authentication Problems
- **Token expired**: Re-login to get new token
- **Invalid token**: Check token format and expiration
- **Permission denied**: Verify user role and business membership

#### Data Issues
- **Business scoping**: Ensure user belongs to correct business
- **Foreign key errors**: Verify referenced entities exist
- **Validation errors**: Check field requirements and formats

#### Performance Issues
- **Slow queries**: Check database indexes
- **Large responses**: Use pagination and filtering
- **Rate limiting**: Implement request throttling

### Getting Help
1. Check this documentation
2. Review API error messages
3. Check application logs
4. Contact development team

---

## 14. Future Enhancements

### Planned Features
- **Real-time WebSocket support** for live updates
- **Advanced analytics dashboard** with charts and KPIs
- **Mobile app API** optimization
- **Multi-currency support** for international businesses
- **Advanced inventory forecasting** with AI/ML
- **Integration APIs** for third-party services
- **Advanced reporting** with custom date ranges and filters

### API Roadmap
- GraphQL API for flexible queries
- Bulk operations for data import/export
- Webhook support for external integrations
- API rate limiting with tiered access
- Advanced search with full-text indexing

---

*This comprehensive documentation reflects the current state of the POS SaaS backend as of October 2025. For the latest updates and changes, refer to the project changelog and release notes.*