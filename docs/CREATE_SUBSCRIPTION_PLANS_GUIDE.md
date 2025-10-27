# Creating Subscription Plans - Quick Guide

**Date:** October 14, 2025

---

## 🎯 Three Ways to Create Subscription Plans

### Method 1: Management Command (Easiest)

Creates 5 default plans (Free, Starter, Professional, Business, Enterprise):

```bash
python manage.py create_subscription_plans
```

**To reset and recreate:**
```bash
python manage.py create_subscription_plans --reset
```

**This creates:**
- ✅ Free Plan (0 GHS) - 1 storefront, 100 products
- ✅ Starter Plan (49.99 GHS) - 2 storefronts, 500 products
- ✅ Professional Plan (99.99 GHS) - 5 storefronts, 2000 products ⭐ Popular
- ✅ Business Plan (199.99 GHS) - 10 storefronts, 10000 products
- ✅ Enterprise Plan (499.99 GHS) - Unlimited everything

---

### Method 2: Django Admin (Visual Interface)

1. Log in as platform admin/superuser
2. Go to: `/admin/subscriptions/subscriptionplan/`
3. Click "Add Subscription Plan"
4. Fill in the form:
   - **Basic Information:** Name, description, price, currency, billing cycle
   - **Limits:** Max users, max storefronts, max products
   - **Features:** JSON object with feature flags
   - **Display Options:** Active status, popular flag, sort order

**Example Features JSON:**
```json
{
  "multi_storefront": true,
  "advanced_reports": true,
  "api_access": true,
  "priority_support": false,
  "inventory_management": true,
  "basic_reports": true,
  "sales_tracking": true,
  "customer_management": true,
  "email_support": true
}
```

5. Click "Save"

---

### Method 3: API Endpoint (For Platform Admin)

**Endpoint:** `POST /subscriptions/api/plans/`

**Requirements:**
- Must be authenticated as platform admin
- User must have `is_staff=True`

**Request:**
```bash
curl -X POST http://localhost:8000/subscriptions/api/plans/ \
  -H "Authorization: Token YOUR_PLATFORM_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
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
      "priority_support": true
    },
    "is_active": true,
    "is_popular": false,
    "sort_order": 3,
    "trial_period_days": 14
  }'
```

**JavaScript/TypeScript:**
```javascript
const response = await fetch('/subscriptions/api/plans/', {
  method: 'POST',
  headers: {
    'Authorization': `Token ${platformAdminToken}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    name: 'Custom Plan',
    description: 'A custom plan for specific needs',
    price: '149.99',
    currency: 'GHS',
    billing_cycle: 'MONTHLY',
    max_users: 15,
    max_storefronts: 7,
    max_products: 5000,
    features: {
      multi_storefront: true,
      advanced_reports: true,
      api_access: true,
      priority_support: true
    },
    is_active: true,
    is_popular: false,
    sort_order: 3,
    trial_period_days: 14
  })
});

const plan = await response.json();
console.log('Plan created:', plan);
```

---

## 📋 Plan Fields Reference

### Required Fields:
- **name** (string) - Plan name (e.g., "Professional Plan")
- **price** (decimal) - Monthly price (e.g., "99.99")
- **currency** (string) - Currency code (e.g., "GHS", "USD")
- **billing_cycle** (string) - "MONTHLY" or "YEARLY"
- **max_users** (integer) - Maximum users allowed
- **max_storefronts** (integer) - Maximum storefronts allowed
- **max_products** (integer) - Maximum products allowed

### Optional Fields:
- **description** (string) - Plan description
- **features** (JSON object) - Feature flags
- **is_active** (boolean) - Default: true
- **is_popular** (boolean) - Default: false
- **sort_order** (integer) - Display order (lower = first)
- **trial_period_days** (integer) - Trial period in days (0 = no trial)

---

## 🔒 Permissions

### Who Can Create Plans:

**Platform Admin/Superuser:**
- ✅ Create plans via admin interface
- ✅ Create plans via API
- ✅ Run management commands
- ✅ View all plans (active & inactive)

**Business Owner:**
- ❌ Cannot create plans
- ✅ Can view active plans (public endpoint)

**Employee:**
- ❌ Cannot create plans
- ✅ Can view active plans (public endpoint)

---

## 🧪 Testing

### 1. Create Default Plans
```bash
python manage.py create_subscription_plans
```

### 2. View Plans (Public - No Auth)
```bash
curl http://localhost:8000/subscriptions/api/plans/
```

### 3. View All Plans (Admin Only)
```bash
curl http://localhost:8000/subscriptions/api/plans/ \
  -H "Authorization: Token PLATFORM_ADMIN_TOKEN"
```

### 4. Create Custom Plan (Admin Only)
```bash
curl -X POST http://localhost:8000/subscriptions/api/plans/ \
  -H "Authorization: Token PLATFORM_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Plan","price":"29.99","currency":"GHS","billing_cycle":"MONTHLY","max_users":5,"max_storefronts":2,"max_products":500,"features":{}}'
```

### 5. Update Plan (Admin Only)
```bash
curl -X PATCH http://localhost:8000/subscriptions/api/plans/{plan_id}/ \
  -H "Authorization: Token PLATFORM_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"price":"39.99"}'
```

### 6. Delete Plan (Admin Only)
```bash
curl -X DELETE http://localhost:8000/subscriptions/api/plans/{plan_id}/ \
  -H "Authorization: Token PLATFORM_ADMIN_TOKEN"
```

---

## ✅ Quick Start (Recommended)

**For first-time setup:**

1. **Create platform admin account:**
   ```bash
   python manage.py create_platform_owner
   ```

2. **Create default plans:**
   ```bash
   python manage.py create_subscription_plans
   ```

3. **Verify plans created:**
   - View at: http://localhost:8000/subscriptions/api/plans/
   - Or admin: http://localhost:8000/admin/subscriptions/subscriptionplan/

4. **Done!** Users can now see and subscribe to plans.

---

## 💡 Tips

1. **Sort Order:** Lower numbers appear first (1, 2, 3...)
2. **Popular Flag:** Only set 1-2 plans as popular
3. **Features:** Use consistent key names across all plans
4. **Pricing:** Consider your target market (GHS for Ghana, USD for international)
5. **Limits:** Set realistic limits (999999 = "unlimited")
6. **Trial Period:** 14 days is industry standard

---

## 🐛 Troubleshooting

**"Permission denied" when creating plan via API:**
- Make sure user is platform admin (`is_staff=True`)
- Use correct token in Authorization header

**"Plans already exist" from management command:**
- Use `--reset` flag to delete and recreate
- Or create plans with different names

**Plans not showing in API:**
- Check `is_active=True`
- Public users only see active plans
- Admins see all plans

---

**Need help?** Contact: alphalogiquetechnologies@gmail.com
