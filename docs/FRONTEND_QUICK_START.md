# Frontend Quick Start - Subscription Changes

## 🎯 TL;DR - What Changed

**Before:** User has subscription  
**After:** Business has subscription (users can have multiple businesses)

---

## ⚡ Quick Fixes Needed

### 1. Subscription Creation
```diff
// OLD
- const sub = await api.post('/subscriptions/', { plan_id: planId });

// NEW
+ const sub = await api.post('/subscriptions/', { 
+   plan_id: planId,
+   business_id: currentBusinessId  // REQUIRED
+ });
```

### 2. Get Subscription
```diff
// OLD
- const sub = await api.get('/subscriptions/me/');

// NEW
+ const sub = await api.get(`/subscriptions/me/?business_id=${businessId}`);
```

### 3. Subscription Status
```diff
// OLD
- const isActive = user.subscription_status === 'ACTIVE';

// NEW
+ const isActive = business.subscription_status === 'ACTIVE';
```

### 4. User Object Changed
```diff
// OLD User Response
{
  "id": "uuid",
  "name": "John",
- "subscription_status": "ACTIVE"  // REMOVED
}

// NEW Business Response
{
  "id": "uuid",
  "name": "My Shop",
+ "subscription_status": "ACTIVE"  // MOVED HERE
}
```

---

## 🔧 State Management Update

```javascript
// Add to your global state
const appState = {
  user: { id: "...", name: "..." },
  
  // NEW: Add these
  currentBusiness: null,
  businesses: []
};

// Load on app init
const loadUserBusinesses = async () => {
  const { data } = await api.get('/api/businesses/my-businesses/');
  setBusinesses(data.results);
  setCurrentBusiness(data.results[0]); // Set first as default
};
```

---

## 🎨 New UI Component Needed

### Business Selector
```jsx
const BusinessSelector = () => {
  const { businesses, currentBusiness, setCurrentBusiness } = useAppContext();

  return (
    <select 
      value={currentBusiness?.id}
      onChange={(e) => switchBusiness(e.target.value)}
    >
      {businesses.map(b => (
        <option key={b.id} value={b.id}>
          {b.name} ({b.subscription_status})
        </option>
      ))}
    </select>
  );
};
```

---

## 📋 Checklist

- [ ] Update subscription creation to include `business_id`
- [ ] Change subscription status check from `user` to `business`
- [ ] Add business selector component
- [ ] Load user's businesses on login
- [ ] Store current business in state
- [ ] Pass business context to all API calls
- [ ] Update permission checks to use business subscription
- [ ] Test with user having multiple businesses

---

## 🚨 Breaking Changes

1. **`business_id` required** for subscription creation
2. **User object no longer has** `subscription_status`
3. **Business object now has** `subscription_status`
4. **Must track current business** in app state

---

## 📖 Full Documentation

See `FRONTEND_SUBSCRIPTION_CHANGES.md` for complete details.

---

**Need Help?** Check the backend API docs or contact the backend team.
