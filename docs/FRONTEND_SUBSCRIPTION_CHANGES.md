# 🚨 CRITICAL: Subscription Architecture Change - Frontend Integration Required

## Date: October 14, 2025
## Status: BREAKING CHANGES - Immediate Action Required

---

## 📋 Executive Summary

The subscription system has been **completely refactored** from a **USER-CENTRIC** to a **BUSINESS-CENTRIC** architecture. This is a **BREAKING CHANGE** that requires immediate frontend updates.

### Why This Change?
- ❌ **OLD:** Subscriptions were tied to users (prevented users from owning multiple businesses)
- ✅ **NEW:** Subscriptions are tied to businesses (users can manage unlimited businesses, each with separate subscriptions)

### Impact Level: 🔴 **HIGH - Breaking Changes**

---

## 🎯 What Changed

### Core Concept Shift

#### BEFORE (Wrong):
```
User → Subscription → Business (optional)
       ↓
   User has subscription status
   User can only have ONE business effectively
```

#### AFTER (Correct):
```
User → Business Membership → Business → Subscription
                                         ↓
                                 Business has subscription status
                                 User can have MULTIPLE businesses
```

---

## 🔧 API Changes Required

### 1. Creating a Subscription

#### OLD API Call ❌:
```javascript
POST /api/subscriptions/

{
  "plan_id": "uuid-of-plan",
  "user_id": "uuid-of-user",  // REMOVED
  "payment_method": "PAYSTACK"
}
```

#### NEW API Call ✅:
```javascript
POST /api/subscriptions/

{
  "plan_id": "uuid-of-plan",
  "business_id": "uuid-of-business",  // REQUIRED NOW
  "payment_method": "PAYSTACK"
}
```

**Frontend Changes Needed:**
```javascript
// OLD
const createSubscription = async (planId) => {
  return await api.post('/subscriptions/', {
    plan_id: planId,
    payment_method: 'PAYSTACK'
  });
};

// NEW - Must include business_id
const createSubscription = async (planId, businessId) => {
  return await api.post('/subscriptions/', {
    plan_id: planId,
    business_id: businessId,  // ADD THIS
    payment_method: 'PAYSTACK'
  });
};
```

---

### 2. Getting Active Subscription

#### OLD API Response ❌:
```javascript
GET /api/subscriptions/me/

Response:
{
  "id": "uuid",
  "user": "uuid",
  "user_name": "John Doe",
  "plan": {...},
  "status": "ACTIVE"
}
```

#### NEW API Response ✅:
```javascript
GET /api/subscriptions/me/?business_id=uuid

Response:
{
  "id": "uuid",
  "business": "uuid",
  "business_name": "My Shop",
  "created_by": "uuid",
  "created_by_name": "John Doe",
  "plan": {...},
  "status": "ACTIVE"
}
```

**Frontend Changes Needed:**
```javascript
// OLD
const getMySubscription = async () => {
  return await api.get('/subscriptions/me/');
};

// NEW - Must specify which business
const getBusinessSubscription = async (businessId) => {
  return await api.get(`/subscriptions/me/?business_id=${businessId}`);
};

// OR if you have a current business context
const getCurrentBusinessSubscription = async () => {
  const businessId = getCurrentBusinessId(); // From your app state
  return await api.get(`/subscriptions/me/?business_id=${businessId}`);
};
```

---

### 3. Subscription Status Location Changed

#### OLD ❌:
```javascript
// Subscription status was on User object
GET /api/users/me/

Response:
{
  "id": "uuid",
  "name": "John Doe",
  "email": "john@example.com",
  "subscription_status": "ACTIVE"  // REMOVED
}
```

#### NEW ✅:
```javascript
// Subscription status is now on Business object
GET /api/businesses/{business_id}/

Response:
{
  "id": "uuid",
  "name": "My Shop",
  "owner": "uuid",
  "subscription_status": "ACTIVE",  // MOVED HERE
  "subscription": {
    "id": "uuid",
    "plan": {...},
    "status": "ACTIVE",
    "end_date": "2025-11-14"
  }
}
```

**Frontend Changes Needed:**
```javascript
// OLD
const hasActiveSubscription = (user) => {
  return user.subscription_status === 'ACTIVE';
};

// NEW
const hasActiveSubscription = (business) => {
  return business.subscription_status === 'ACTIVE' || 
         business.subscription_status === 'TRIAL';
};

// OR check the subscription directly
const hasActiveSubscription = (business) => {
  return business.subscription?.is_active || false;
};
```

---

### 4. Multiple Businesses Support

#### NEW Feature: User Can Access Multiple Businesses

```javascript
// Get all businesses user has access to
GET /api/businesses/my-businesses/

Response:
{
  "results": [
    {
      "id": "uuid-1",
      "name": "Shop A",
      "subscription_status": "ACTIVE",
      "role": "OWNER",
      "subscription": {
        "plan": "Premium",
        "status": "ACTIVE"
      }
    },
    {
      "id": "uuid-2", 
      "name": "Shop B",
      "subscription_status": "TRIAL",
      "role": "ADMIN",
      "subscription": {
        "plan": "Basic",
        "status": "TRIAL"
      }
    }
  ]
}
```

**Frontend Implementation:**
```javascript
// Business Selector Component
const BusinessSelector = () => {
  const [businesses, setBusinesses] = useState([]);
  const [currentBusiness, setCurrentBusiness] = useState(null);

  useEffect(() => {
    // Fetch all businesses user has access to
    api.get('/api/businesses/my-businesses/').then(response => {
      setBusinesses(response.data.results);
      // Set first business as default
      if (response.data.results.length > 0) {
        setCurrentBusiness(response.data.results[0]);
      }
    });
  }, []);

  return (
    <select onChange={(e) => setCurrentBusiness(e.target.value)}>
      {businesses.map(business => (
        <option key={business.id} value={business.id}>
          {business.name} - {business.subscription_status}
        </option>
      ))}
    </select>
  );
};
```

---

### 5. Permission Checks

#### OLD ❌:
```javascript
// Check user subscription
const canAccessFeature = (user) => {
  return user.subscription_status === 'ACTIVE';
};
```

#### NEW ✅:
```javascript
// Check business subscription
const canAccessFeature = (business) => {
  if (!business) return false;
  return ['ACTIVE', 'TRIAL'].includes(business.subscription_status);
};

// With limits checking
const canCreateUser = (business) => {
  if (!canAccessFeature(business)) return false;
  
  const limits = business.subscription?.plan;
  const currentUsers = business.users_count || 0;
  
  return limits.max_users === null || currentUsers < limits.max_users;
};
```

---

## 🔄 Migration Path for Frontend

### Phase 1: Update State Management

```javascript
// OLD Redux/Context State
{
  user: {
    id: "uuid",
    name: "John",
    subscription_status: "ACTIVE"  // REMOVE THIS
  }
}

// NEW Redux/Context State
{
  user: {
    id: "uuid",
    name: "John"
  },
  currentBusiness: {
    id: "uuid",
    name: "My Shop",
    subscription_status: "ACTIVE"  // ADD THIS
  },
  businesses: [
    { id: "uuid-1", name: "Shop A", subscription_status: "ACTIVE" },
    { id: "uuid-2", name: "Shop B", subscription_status: "TRIAL" }
  ]
}
```

### Phase 2: Update API Calls

1. **Add business context to all API calls:**
```javascript
// Add business_id to headers or query params
const api = axios.create({
  baseURL: '/api',
  headers: {
    'X-Business-ID': getCurrentBusinessId()  // Add this
  }
});
```

2. **Update subscription endpoints:**
```javascript
// All subscription operations now need business_id
subscriptionService.create(planId, businessId);
subscriptionService.getForBusiness(businessId);
subscriptionService.cancel(subscriptionId, businessId);
```

### Phase 3: Update UI Components

```javascript
// Subscription Status Badge Component
const SubscriptionBadge = ({ business }) => {
  const status = business?.subscription_status || 'INACTIVE';
  const color = {
    'ACTIVE': 'green',
    'TRIAL': 'blue',
    'EXPIRED': 'red',
    'INACTIVE': 'gray'
  }[status];

  return (
    <Badge color={color}>
      {status}
    </Badge>
  );
};

// Usage
<SubscriptionBadge business={currentBusiness} />
```

---

## 📊 Updated Workflows

### Workflow 1: New User Registration with Business

```javascript
// Step 1: User registers
const user = await registerUser({
  name: "John Doe",
  email: "john@example.com",
  password: "secure123"
});

// Step 2: Create business
const business = await createBusiness({
  name: "My Shop",
  email: "shop@example.com",
  tin: "12345678",
  address: "123 Main St"
});

// Step 3: Subscribe the BUSINESS (not the user)
const subscription = await createSubscription({
  plan_id: selectedPlanId,
  business_id: business.id,  // IMPORTANT: business, not user
  payment_method: "PAYSTACK"
});

// Step 4: Initialize payment
const payment = await initializePayment({
  subscription_id: subscription.id,
  gateway: "PAYSTACK",
  callback_url: "https://myapp.com/payment/callback"
});

// Step 5: Redirect to payment
window.location.href = payment.authorization_url;
```

### Workflow 2: User with Multiple Businesses

```javascript
// User has 2 businesses
const UserDashboard = () => {
  const [businesses, setBusinesses] = useState([]);
  const [selectedBusiness, setSelectedBusiness] = useState(null);

  useEffect(() => {
    loadBusinesses();
  }, []);

  const loadBusinesses = async () => {
    const response = await api.get('/api/businesses/my-businesses/');
    setBusinesses(response.data.results);
    setSelectedBusiness(response.data.results[0]);
  };

  const switchBusiness = (businessId) => {
    const business = businesses.find(b => b.id === businessId);
    setSelectedBusiness(business);
    // Reload data for new business context
    loadBusinessData(businessId);
  };

  return (
    <div>
      <BusinessSelector 
        businesses={businesses}
        current={selectedBusiness}
        onChange={switchBusiness}
      />
      
      <SubscriptionStatus business={selectedBusiness} />
      
      {/* All other components now use selectedBusiness context */}
      <Dashboard business={selectedBusiness} />
    </div>
  );
};
```

### Workflow 3: Subscription Upgrade

```javascript
const upgradeSubscription = async (businessId, newPlanId) => {
  // Get current subscription
  const subscription = await api.get(
    `/api/subscriptions/me/?business_id=${businessId}`
  );

  // Cancel current subscription
  await api.post(`/api/subscriptions/${subscription.id}/cancel/`, {
    immediately: false  // Cancel at period end
  });

  // Create new subscription with new plan
  const newSubscription = await api.post('/api/subscriptions/', {
    plan_id: newPlanId,
    business_id: businessId  // Same business, different plan
  });

  // Initialize payment
  return await initializePayment(newSubscription.id);
};
```

---

## 🎨 UI/UX Recommendations

### 1. Business Selector (New Component Needed)

Add a business selector in your app header/navigation:

```jsx
<Header>
  <Logo />
  <BusinessDropdown>
    {businesses.map(business => (
      <BusinessOption 
        key={business.id}
        business={business}
        isActive={business.id === currentBusiness.id}
      >
        <BusinessName>{business.name}</BusinessName>
        <SubscriptionBadge status={business.subscription_status} />
      </BusinessOption>
    ))}
    <AddBusinessButton />
  </BusinessDropdown>
  <UserMenu />
</Header>
```

### 2. Subscription Warning Banner

Show warnings when business subscription is expiring:

```jsx
const SubscriptionWarning = ({ business }) => {
  const daysUntilExpiry = calculateDaysUntilExpiry(business.subscription);

  if (business.subscription_status === 'EXPIRED') {
    return (
      <Alert severity="error">
        Your subscription has expired. 
        <Link to="/subscribe">Renew now</Link> to continue using the platform.
      </Alert>
    );
  }

  if (daysUntilExpiry <= 7) {
    return (
      <Alert severity="warning">
        Your subscription expires in {daysUntilExpiry} days.
        <Link to="/subscribe">Renew now</Link>
      </Alert>
    );
  }

  return null;
};
```

### 3. Subscription Limits Display

Show current usage vs limits:

```jsx
const SubscriptionLimits = ({ business }) => {
  const { subscription } = business;
  const limits = subscription?.plan;

  return (
    <Card>
      <h3>Subscription Limits</h3>
      <LimitItem>
        <Label>Users</Label>
        <Progress 
          current={business.users_count} 
          max={limits.max_users} 
        />
        <Text>{business.users_count} / {limits.max_users || '∞'}</Text>
      </LimitItem>
      <LimitItem>
        <Label>Storefronts</Label>
        <Progress 
          current={business.storefronts_count} 
          max={limits.max_storefronts} 
        />
        <Text>{business.storefronts_count} / {limits.max_storefronts || '∞'}</Text>
      </LimitItem>
    </Card>
  );
};
```

---

## 🧪 Testing Checklist

### Frontend Tests to Update:

- [ ] Update all subscription-related tests to use `business_id`
- [ ] Test user with single business
- [ ] Test user with multiple businesses
- [ ] Test business switching
- [ ] Test subscription creation with business context
- [ ] Test subscription status display on business
- [ ] Test permission checks using business subscription
- [ ] Test subscription limits enforcement
- [ ] Test payment flow with business_id
- [ ] Test subscription renewal for specific business
- [ ] Test expired subscription handling per business

---

## 📱 API Endpoint Quick Reference

### Updated Endpoints:

| Method | Endpoint | Body/Params | Notes |
|--------|----------|-------------|-------|
| `POST` | `/api/subscriptions/` | `{plan_id, business_id}` | **Changed:** Requires `business_id` now |
| `GET` | `/api/subscriptions/me/` | `?business_id=uuid` | **Changed:** Needs business context |
| `GET` | `/api/businesses/{id}/` | - | **New field:** `subscription_status` |
| `GET` | `/api/businesses/my-businesses/` | - | **New:** List all user's businesses |
| `POST` | `/api/subscriptions/{id}/initialize_payment/` | `{gateway, callback_url}` | Same (no change) |
| `POST` | `/api/subscriptions/{id}/verify_payment/` | `{reference}` | Same (no change) |
| `GET` | `/api/subscriptions/{id}/usage/` | - | Returns business usage limits |

---

## 🚀 Implementation Timeline

### Immediate (Day 1):
1. Update API service layer to include `business_id` in subscription calls
2. Add business selector component
3. Update state management to track current business

### Short-term (Week 1):
4. Update all subscription UI components
5. Add business context to all protected routes
6. Update permission checks
7. Test with multiple businesses

### Medium-term (Week 2):
8. Add subscription limits display
9. Implement business switching
10. Update all documentation
11. User acceptance testing

---

## ⚠️ Common Pitfalls to Avoid

### 1. Don't assume single business per user
```javascript
// BAD ❌
const business = user.business;  // User can have multiple!

// GOOD ✅
const business = currentBusiness || user.businesses[0];
```

### 2. Don't check user subscription status
```javascript
// BAD ❌
if (user.subscription_status === 'ACTIVE') { ... }

// GOOD ✅
if (currentBusiness.subscription_status === 'ACTIVE') { ... }
```

### 3. Don't forget business context in API calls
```javascript
// BAD ❌
api.post('/subscriptions/', { plan_id });

// GOOD ✅
api.post('/subscriptions/', { plan_id, business_id });
```

---

## 📞 Support & Questions

### Backend Endpoints Status:
- ✅ Models updated (business-centric)
- ✅ Migrations applied
- ⏳ Views/Serializers update in progress
- ⏳ Documentation update in progress

### For Questions:
- Backend developer: [Contact info]
- API documentation: `/api/docs/` (Swagger/OpenAPI)
- Architecture doc: `SUBSCRIPTION_ARCHITECTURE_FIX_COMPLETED.md`

---

## 📝 Summary of Action Items

### Must Do Immediately:
1. ✅ Add `business_id` parameter to subscription creation
2. ✅ Update subscription retrieval to use business context
3. ✅ Move subscription status checks from User to Business
4. ✅ Add business selector to UI
5. ✅ Update state management for multiple businesses

### Should Do Soon:
6. Add business switching functionality
7. Display subscription limits per business
8. Update all permission checks
9. Add subscription warnings per business
10. Test multi-business workflows

### Nice to Have:
11. Business-specific analytics
12. Per-business notification preferences
13. Business transfer functionality
14. Subscription comparison tool

---

**Last Updated:** October 14, 2025  
**Version:** 2.0 (Business-Centric Architecture)  
**Breaking Change:** Yes - Requires frontend updates  
**Backward Compatible:** No

**Questions? Check `SUBSCRIPTION_ARCHITECTURE_FIX_COMPLETED.md` for technical details.**
