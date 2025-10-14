# Subscription API Implementation Guide

**Last Updated:** October 14, 2025  
**Version:** 1.0

---

## 🔑 Authentication

**All authenticated endpoints use Django Token Authentication:**

```http
Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b
```

**NOT** `Bearer` - use `Token`!

---

## 📡 API Endpoints

### 1. Login

**Endpoint:** `POST /accounts/api/auth/login/`

**Request:**
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response:**
```json
{
  "token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b",
  "user": {
    "id": "uuid",
    "name": "John Doe",
    "email": "user@example.com",
    "account_type": "BUSINESS_OWNER",
    "platform_role": "USER"
  },
  "employment": null
}
```

**Note:** Use `token` (not `access_token`). No `businesses` array in response - fetch separately.

---

### 2. Get User's Businesses

**Endpoint:** `GET /accounts/api/businesses/`

**Headers:**
```http
Authorization: Token {token}
```

**Response:**
```json
[
  {
    "id": "uuid",
    "name": "DataLogique Systems",
    "email": "info@datalogique.com",
    "phone": "+233241234567",
    "tin": "TIN123456",
    "location": "Accra, Ghana",
    "subscription_status": "ACTIVE",
    "is_active": true,
    "owner": {
      "id": "uuid",
      "name": "John Doe",
      "email": "john@example.com"
    },
    "created_at": "2025-10-01T00:00:00Z"
  }
]
```

**Note:** Returns all businesses where user is owner or member. `subscription_status` is on the Business model.

---

### 3. Get Subscription Plans

**Endpoint:** `GET /subscriptions/api/plans/`

**Auth:** Not required (public endpoint)

**Response:**
```json
[
  {
    "id": "uuid",
    "name": "Free Plan",
    "description": "Perfect for getting started",
    "price": "0.00",
    "currency": "GHS",
    "billing_cycle": "MONTHLY",
    "max_users": 1,
    "max_storefronts": 1,
    "max_products": 100,
    "features": {
      "multi_storefront": false,
      "advanced_reports": false,
      "api_access": false,
      "priority_support": false
    },
    "is_active": true,
    "is_popular": false,
    "sort_order": 1
  },
  {
    "id": "uuid",
    "name": "Premium Plan",
    "description": "For growing businesses",
    "price": "99.99",
    "currency": "GHS",
    "billing_cycle": "MONTHLY",
    "max_users": 10,
    "max_storefronts": 5,
    "max_products": 1000,
    "features": {
      "multi_storefront": true,
      "advanced_reports": true,
      "api_access": true,
      "priority_support": true
    },
    "is_active": true,
    "is_popular": true,
    "sort_order": 2
  }
]
```

---

### 3a. Create Subscription Plan (Platform Admin Only)

**Endpoint:** `POST /subscriptions/api/plans/`

**Auth:** Required (Platform Admin only)

**Headers:**
```http
Authorization: Token {token}
Content-Type: application/json
```

**Request:**
```json
{
  "name": "Custom Plan",
  "description": "A custom plan for specific needs",
  "price": "149.99",
  "currency": "GHS",
  "billing_cycle": "MONTHLY",
  "max_users": 15,
  "max_storefronts": 7,
  "max_products": 5000,
  "features": {
    "multi_storefront": true,
    "advanced_reports": true,
    "api_access": true,
    "priority_support": true,
    "custom_feature": true
  },
  "is_active": true,
  "is_popular": false,
  "sort_order": 3,
  "trial_period_days": 14
}
```

**Response:**
```json
{
  "id": "uuid",
  "name": "Custom Plan",
  "description": "A custom plan for specific needs",
  "price": "149.99",
  "currency": "GHS",
  "billing_cycle": "MONTHLY",
  "max_users": 15,
  "max_storefronts": 7,
  "max_products": 5000,
  "features": {
    "multi_storefront": true,
    "advanced_reports": true,
    "api_access": true,
    "priority_support": true,
    "custom_feature": true
  },
  "is_active": true,
  "is_popular": false,
  "sort_order": 3,
  "trial_period_days": 14
}
```

**Status Codes:**
- `201` - Plan created successfully
- `400` - Invalid data
- `401` - Not authenticated
- `403` - Not a platform admin

---

### 3b. Update Subscription Plan (Platform Admin Only)

**Endpoint:** `PUT /subscriptions/api/plans/{plan_id}/` or `PATCH /subscriptions/api/plans/{plan_id}/`

**Auth:** Required (Platform Admin only)

**Headers:**
```http
Authorization: Token {token}
Content-Type: application/json
```

**Request (PATCH - partial update):**
```json
{
  "price": "129.99",
  "is_popular": true
}
```

**Response:**
```json
{
  "id": "uuid",
  "name": "Custom Plan",
  "price": "129.99",
  "is_popular": true,
  // ... other fields
}
```

---

### 3c. Delete Subscription Plan (Platform Admin Only)

**Endpoint:** `DELETE /subscriptions/api/plans/{plan_id}/`

**Auth:** Required (Platform Admin only)

**Headers:**
```http
Authorization: Token {token}
```

**Response:**
```
204 No Content
```

**Note:** Be careful deleting plans that have active subscriptions!

---

### 4. Get Current User's Active Subscriptions

**Endpoint:** `GET /subscriptions/api/subscriptions/me/`

**Headers:**
```http
Authorization: Token {token}
```

**Response:** ⚠️ **RETURNS ARRAY** (users can be members of multiple businesses)
```json
[
  {
    "id": "uuid",
    "business": {
      "id": "business-uuid",
      "name": "My First Business",
      "description": "..."
    },
    "plan": {
      "id": "uuid",
      "name": "Premium Plan",
      "price": "99.99",
      "currency": "GHS",
      "billing_cycle": "MONTHLY",
      "max_users": 10,
      "max_storefronts": 5,
      "max_products": 1000,
      "features": {
        "multi_storefront": true,
        "advanced_reports": true,
        "api_access": true,
        "priority_support": true
      }
    },
    "status": "ACTIVE",
    "start_date": "2025-10-01",
    "end_date": "2025-10-31",
    "auto_renew": true,
    "is_trial": false,
    "trial_ends_at": null,
    "amount": "99.99",
    "currency": "GHS",
    "created_at": "2025-10-01T00:00:00Z"
  }
]
```

**Empty Response (no subscriptions):**
```json
[]
```

**Status Codes:**
- `200` - Success (always returns 200, even if array is empty)
- `401` - Unauthorized

**Important Notes:**
- ✅ Returns **array** of subscriptions (users can be members of multiple businesses)
- ✅ Returns **empty array `[]`** if user has no active subscriptions (not 404 error)
- ✅ Only returns subscriptions with status: ACTIVE, TRIAL, or PAST_DUE
- ✅ Each business has its own subscription
- **Frontend must handle array**: Use `subscriptions[0]` for single business or loop through all

---

### 5. Initialize Payment

**Endpoint:** `POST /subscriptions/api/subscriptions/{subscription_id}/initialize_payment/`

**Headers:**
```http
Authorization: Token {token}
Content-Type: application/json
```

**Request:**
```json
{
  "gateway": "PAYSTACK",
  "callback_url": "https://yourfrontend.com/payment/callback"
}
```

**For Stripe (includes success/cancel URLs):**
```json
{
  "gateway": "STRIPE",
  "callback_url": "https://yourfrontend.com/payment/callback",
  "success_url": "https://yourfrontend.com/payment/success",
  "cancel_url": "https://yourfrontend.com/payment/cancelled"
}
```

**Response (Paystack):**
```json
{
  "status": "success",
  "message": "Payment initialized",
  "data": {
    "authorization_url": "https://checkout.paystack.com/xyz",
    "access_code": "xyz123",
    "reference": "PAY-12345"
  }
}
```

**Response (Stripe):**
```json
{
  "status": "success",
  "message": "Checkout session created",
  "data": {
    "checkout_url": "https://checkout.stripe.com/xyz",
    "session_id": "cs_test_xyz123"
  }
}
```

**Usage:**
1. Call this endpoint to get payment URL
2. Redirect user to `authorization_url` (Paystack) or `checkout_url` (Stripe)
3. User completes payment on gateway
4. Gateway redirects back to your `callback_url` with reference/session_id
5. Call verify payment endpoint

---

### 6. Verify Payment

**Endpoint:** `POST /subscriptions/api/subscriptions/{subscription_id}/verify_payment/`

**Headers:**
```http
Authorization: Token {token}
Content-Type: application/json
```

**Request (Paystack):**
```json
{
  "gateway": "PAYSTACK",
  "reference": "PAY-12345"
}
```

**Request (Stripe):**
```json
{
  "gateway": "STRIPE",
  "reference": "cs_test_xyz123"
}
```

**Response (Success):**
```json
{
  "success": true,
  "message": "Payment verified successfully",
  "payment": {
    "id": "uuid",
    "subscription": "subscription-uuid",
    "amount": "99.99",
    "currency": "GHS",
    "status": "SUCCESSFUL",
    "payment_method": "MOBILE_MONEY",
    "gateway": "PAYSTACK",
    "gateway_reference": "PAY-12345",
    "paid_at": "2025-10-14T12:00:00Z"
  }
}
```

**Response (Failed):**
```json
{
  "success": false,
  "message": "Payment verification failed"
}
```

**Status Codes:**
- `200` - Verification successful
- `400` - Verification failed or invalid reference
- `401` - Unauthorized
- `403` - User doesn't own this subscription

---

### 7. Cancel Subscription

**Endpoint:** `POST /subscriptions/api/subscriptions/{subscription_id}/cancel/`

**Headers:**
```http
Authorization: Token {token}
Content-Type: application/json
```

**Request:**
```json
{
  "immediately": false,
  "reason": "Switching to competitor"
}
```

**Parameters:**
- `immediately` (boolean, optional): `true` = cancel now, `false` = cancel at period end. Default: `false`
- `reason` (string, optional): Cancellation reason

**Response:**
```json
{
  "id": "uuid",
  "status": "CANCELLED",
  "end_date": "2025-10-31",
  "cancelled_at": "2025-10-14T12:00:00Z",
  "auto_renew": false,
  "plan": { ... }
}
```

---

### 8. Get Subscription Usage

**Endpoint:** `GET /subscriptions/api/subscriptions/{subscription_id}/usage/`

**Headers:**
```http
Authorization: Token {token}
```

**Response:**
```json
{
  "subscription_id": "uuid",
  "plan_name": "Premium Plan",
  "usage": {
    "users": {
      "used": 5,
      "limit": 10,
      "percentage": 50
    },
    "storefronts": {
      "used": 2,
      "limit": 5,
      "percentage": 40
    },
    "products": {
      "used": 150,
      "limit": 1000,
      "percentage": 15
    }
  }
}
```

---

### 9. Get Subscription Invoices

**Endpoint:** `GET /subscriptions/api/subscriptions/{subscription_id}/invoices/`

**Headers:**
```http
Authorization: Token {token}
```

**Response:**
```json
[
  {
    "id": "uuid",
    "invoice_number": "INV-2025-0001",
    "subscription": "subscription-uuid",
    "amount": "99.99",
    "currency": "GHS",
    "status": "PAID",
    "due_date": "2025-10-31",
    "paid_at": "2025-10-01T10:00:00Z",
    "created_at": "2025-10-01T00:00:00Z"
  }
]
```

---

### 10. Get Subscription Payment History

**Endpoint:** `GET /subscriptions/api/subscriptions/{subscription_id}/payments/`

**Headers:**
```http
Authorization: Token {token}
```

**Response:**
```json
[
  {
    "id": "uuid",
    "subscription": "subscription-uuid",
    "amount": "99.99",
    "currency": "GHS",
    "status": "SUCCESSFUL",
    "payment_method": "MOBILE_MONEY",
    "gateway": "PAYSTACK",
    "gateway_reference": "PAY-12345",
    "paid_at": "2025-10-01T10:00:00Z",
    "created_at": "2025-10-01T10:00:00Z"
  }
]
```

---

## 🔄 Implementation Flow

### 1. Login Flow

```javascript
// 1. Login
const loginResponse = await fetch('/accounts/api/auth/login/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email, password })
});
const { token, user } = await loginResponse.json();

// Store token
localStorage.setItem('token', token);

// 2. Fetch businesses
const businessesResponse = await fetch('/accounts/api/businesses/', {
  headers: { 'Authorization': `Token ${token}` }
});
const businesses = await businessesResponse.json();

// 3. Select business
if (businesses.length === 1) {
  localStorage.setItem('current_business', JSON.stringify(businesses[0]));
} else {
  // Show business selector
}
```

---

### 2. Display Subscription

```javascript
const token = localStorage.getItem('token');
const currentBusiness = JSON.parse(localStorage.getItem('current_business'));

// Get user's subscriptions (RETURNS ARRAY!)
const response = await fetch('/subscriptions/api/subscriptions/me/', {
  headers: { 'Authorization': `Token ${token}` }
});

if (response.ok) {
  const subscriptions = await response.json();  // ⚠️ ARRAY, not single object!
  
  if (subscriptions.length > 0) {
    // Option 1: Display first subscription
    const subscription = subscriptions[0];
    console.log(subscription.plan.name, subscription.status);
    
    // Option 2: Find subscription for current business
    const currentSubscription = subscriptions.find(
      sub => sub.business.id === currentBusiness.id
    );
    if (currentSubscription) {
      console.log('Current business subscription:', currentSubscription.plan.name);
    }
    
    // Option 3: Display all subscriptions (multi-business user)
    subscriptions.forEach(sub => {
      console.log(`${sub.business.name}: ${sub.plan.name} (${sub.status})`);
    });
  } else {
    // Empty array - no active subscriptions
    console.log('No active subscriptions');
  }
}
```

---

### 3. Subscribe to Plan

```javascript
// Note: Current backend doesn't have this endpoint yet
// You'll need to wait for backend implementation
```

---

### 4. Payment Flow (Paystack)

```javascript
const subscriptionId = 'subscription-uuid';
const token = localStorage.getItem('token');

// 1. Initialize payment
const initResponse = await fetch(
  `/subscriptions/api/subscriptions/${subscriptionId}/initialize_payment/`,
  {
    method: 'POST',
    headers: {
      'Authorization': `Token ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      gateway: 'PAYSTACK',
      callback_url: `${window.location.origin}/payment/callback`
    })
  }
);
const { data } = await initResponse.json();

// 2. Redirect to payment page
window.location.href = data.authorization_url;

// 3. User pays and is redirected back to /payment/callback?reference=PAY-12345

// 4. In your callback page, verify payment
const urlParams = new URLSearchParams(window.location.search);
const reference = urlParams.get('reference');

const verifyResponse = await fetch(
  `/subscriptions/api/subscriptions/${subscriptionId}/verify_payment/`,
  {
    method: 'POST',
    headers: {
      'Authorization': `Token ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      gateway: 'PAYSTACK',
      reference: reference
    })
  }
);
const result = await verifyResponse.json();

if (result.success) {
  // Payment successful - redirect to success page
} else {
  // Payment failed - show error
}
```

---

### 5. Payment Flow (Stripe)

```javascript
// 1. Initialize payment
const initResponse = await fetch(
  `/subscriptions/api/subscriptions/${subscriptionId}/initialize_payment/`,
  {
    method: 'POST',
    headers: {
      'Authorization': `Token ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      gateway: 'STRIPE',
      success_url: `${window.location.origin}/payment/success`,
      cancel_url: `${window.location.origin}/payment/cancelled`
    })
  }
);
const { data } = await initResponse.json();

// 2. Redirect to Stripe checkout
window.location.href = data.checkout_url;

// 3. Stripe redirects to success_url with ?session_id=cs_test_xyz

// 4. Verify payment
const urlParams = new URLSearchParams(window.location.search);
const sessionId = urlParams.get('session_id');

const verifyResponse = await fetch(
  `/subscriptions/api/subscriptions/${subscriptionId}/verify_payment/`,
  {
    method: 'POST',
    headers: {
      'Authorization': `Token ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      gateway: 'STRIPE',
      reference: sessionId
    })
  }
);
```

---

## 📊 Business & Subscription Relationship

**Key Concept:** Subscription is tied to **BUSINESS**, not USER.

```
User
 └── belongs to → Business 1 (subscription_status: ACTIVE)
 └── belongs to → Business 2 (subscription_status: TRIAL)
```

Each business has:
- `subscription_status` field on Business model
- One Subscription record (OneToOne relationship)
- Own subscription limits (storefronts, users, etc.)

---

## ⚠️ Important Changes & Limitations

### ✅ FIXED: Multi-Business Support
The `/me/` endpoint now correctly returns **all subscriptions** for businesses where the user is a member.

**Returns:** Array of subscriptions (not single object)
```typescript
// Endpoint: GET /subscriptions/api/subscriptions/me/
type MeResponse = Subscription[]; // ARRAY!
```

### 1. No Business-Specific Subscription Endpoint
The endpoint `GET /subscriptions/api/subscription/business/{business_id}/` doesn't exist yet.

**Workaround:** 
- Use `/subscriptions/api/subscriptions/me/` to get all subscriptions
- Filter by `business.id` on the frontend
- Or use `/accounts/api/businesses/{id}/` to get business details (includes `subscription_status`)

### 2. Can't Subscribe Business to Plan via API
No endpoint to create subscription for a specific business yet.

**Status:** Backend needs to implement business subscription creation endpoint.

---

## 🎨 Subscription Status Values

- `ACTIVE` - Active subscription, full access
- `TRIAL` - Trial period, full access until trial ends
- `PAST_DUE` - Payment failed, grace period
- `EXPIRED` - Subscription ended, no access
- `CANCELLED` - User cancelled, may have access until period end
- `SUSPENDED` - Admin suspended, no access
- `INACTIVE` - No subscription

---

## 🔒 Permissions

### Who Can Access What:

**Business Owner:**
- View subscription details
- Initialize payments
- Cancel subscription
- View invoices and payments

**Business Manager:**
- View subscription details
- View invoices and payments
- Cannot cancel or modify subscription

**Business Employee:**
- No subscription access

**Platform Admin:**
- Full access to all subscriptions

---

## 📝 TypeScript Interfaces

```typescript
interface LoginResponse {
  token: string;
  user: {
    id: string;
    name: string;
    email: string;
    account_type: string;
    platform_role: string;
  };
  employment: any | null;
}

interface Business {
  id: string;
  name: string;
  email: string;
  phone: string;
  tin: string;
  location: string;
  subscription_status: 'ACTIVE' | 'TRIAL' | 'INACTIVE' | 'PAST_DUE' | 'EXPIRED' | 'CANCELLED';
  is_active: boolean;
  owner: {
    id: string;
    name: string;
    email: string;
  };
  created_at: string;
}

interface SubscriptionPlan {
  id: string;
  name: string;
  description: string;
  price: string;
  currency: string;
  billing_cycle: 'MONTHLY' | 'YEARLY';
  max_users: number;
  max_storefronts: number;
  max_products: number;
  features: {
    multi_storefront: boolean;
    advanced_reports: boolean;
    api_access: boolean;
    priority_support: boolean;
    [key: string]: boolean;
  };
  is_active: boolean;
  is_popular: boolean;
}

interface Subscription {
  id: string;
  business: {
    id: string;
    name: string;
    description: string;
  };
  plan: SubscriptionPlan;
  status: 'ACTIVE' | 'TRIAL' | 'PAST_DUE' | 'EXPIRED' | 'CANCELLED' | 'SUSPENDED' | 'INACTIVE';
  start_date: string;
  end_date: string;
  auto_renew: boolean;
  is_trial: boolean;
  trial_ends_at: string | null;
  amount: string;
  currency: string;
  created_at: string;
}

// ⚠️ IMPORTANT: /me/ endpoint returns ARRAY, not single object!
type MySubscriptionsResponse = Subscription[];  // Array of subscriptions

interface PaymentInitResponse {
  status: string;
  message: string;
  data: {
    authorization_url?: string;  // Paystack
    checkout_url?: string;        // Stripe
    access_code?: string;         // Paystack
    session_id?: string;          // Stripe
    reference: string;
  };
}

interface PaymentVerification {
  success: boolean;
  message: string;
  payment?: {
    id: string;
    subscription: string;
    amount: string;
    currency: string;
    status: 'SUCCESSFUL' | 'FAILED' | 'PENDING';
    payment_method: string;
    gateway: 'PAYSTACK' | 'STRIPE';
    gateway_reference: string;
    paid_at: string;
  };
}
```

---

## 🆘 Support

**Backend Developer:** alphalogiquetechnologies@gmail.com

---

**That's it!** Everything you need to implement subscription features is in this document.
