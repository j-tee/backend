# Subscription Architecture - Visual Guide

## 🔑 Key Terminology

**IMPORTANT: Understand the difference between Business and Storefront**

- **Business** = A company/organization (e.g., "DataLogique Systems", "Tech Solutions Ltd")
  - Has ONE subscription
  - Subscription covers ALL storefronts under that business
  - Can have multiple storefronts/shops/branches

- **Storefront/Shop** = A physical location/branch under a business (e.g., "Accra Branch", "Kumasi Branch")
  - Multiple storefronts belong to ONE business
  - All covered by the business's single subscription
  - No separate subscription per storefront

**Example:**
```
DataLogique Systems (BUSINESS - has 1 subscription)
    ├── Accra Branch (Storefront)
    ├── Kumasi Branch (Storefront)
    ├── Tamale Branch (Storefront)
    └── Cape Coast Branch (Storefront)
    
    All 4 storefronts covered by ONE subscription!
```

**What changed:** User can now own MULTIPLE BUSINESSES (not multiple storefronts - that was always allowed)

---

## Before (User-Centric) ❌

```
┌─────────────────────────────────────────────────────────┐
│                     USER ACCOUNT                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Name: John Doe                                  │  │
│  │  Email: john@example.com                         │  │
│  │  Subscription Status: ACTIVE  ←── Stored here!   │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │           SUBSCRIPTION                           │  │
│  │  Plan: Premium                                   │  │
│  │  Status: ACTIVE                                  │  │
│  │  User: john@example.com  ←── Linked to user     │  │
│  │  Business: (optional)                            │  │
│  └──────────────────────────────────────────────────┘  │
│                      ↓                                  │
│  ┌──────────────────────────────────────────────────┐  │
│  │           BUSINESS (Optional)                    │  │
│  │  Name: My Shop                                   │  │
│  │  Owner: john@example.com                         │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘

PROBLEM: 
- User can effectively only have ONE business
- To manage second business, need NEW email account
- Subscription tied to user, not business
```

---

## After (Business-Centric) ✅

```
┌─────────────────────────────────────────────────────────┐
│                   USER ACCOUNT                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Name: John Doe                                  │  │
│  │  Email: john@example.com                         │  │
│  │  (No subscription_status field)                  │  │
│  └──────────────────────────────────────────────────┘  │
│                      │                                  │
│         ┌────────────┴────────────┐                     │
│         ↓                         ↓                     │
│  ┌─────────────────┐      ┌─────────────────┐          │
│  │  MEMBERSHIP #1  │      │  MEMBERSHIP #2  │          │
│  │  Role: OWNER    │      │  Role: OWNER    │          │
│  └────────┬────────┘      └────────┬────────┘          │
│           ↓                        ↓                    │
│  ┌────────────────────┐   ┌────────────────────┐       │
│  │  BUSINESS A        │   │  BUSINESS B        │       │
│  │  "DataLogique      │   │  "Tech Solutions   │       │
│  │   Systems"         │   │   Ltd"             │       │
│  │  Status: ACTIVE    │   │  Status: TRIAL     │       │
│  └────────┬───────────┘   └────────┬───────────┘       │
│           ↓                        ↓                    │
│  ┌────────────────┐       ┌────────────────┐           │
│  │ SUBSCRIPTION A │       │ SUBSCRIPTION B │           │
│  │ Plan: Premium  │       │ Plan: Basic    │           │
│  │ Status: ACTIVE │       │ Status: TRIAL  │           │
│  │ Max Storefronts:│      │ Max Storefronts:│          │
│  │  10            │       │  3             │           │
│  └────────┬───────┘       └────────┬───────┘           │
│           │                        │                    │
│           ↓                        ↓                    │
│  ┌────────────────┐       ┌────────────────┐           │
│  │  Storefronts:  │       │  Storefronts:  │           │
│  │  - Accra       │       │  - Tema        │           │
│  │  - Kumasi      │       │  - Takoradi    │           │
│  │  - Tamale      │       │                │           │
│  └────────────────┘       └────────────────┘           │
└─────────────────────────────────────────────────────────┘

SOLUTION:
✓ One user can own multiple BUSINESSES (companies)
✓ Each BUSINESS has ONE subscription
✓ Each subscription covers ALL storefronts under that business
✓ Subscription status on business (not on storefronts)
✓ User can switch between businesses in UI
```

---

## Data Flow Comparison

### Creating a Subscription

#### Before ❌:
```
User clicks "Subscribe"
  ↓
Frontend sends: { plan_id: "uuid" }
  ↓
Backend creates: Subscription → links to User
  ↓
User.subscription_status = 'ACTIVE'
```

#### After ✅:
```
User selects Business + clicks "Subscribe"
  ↓
Frontend sends: { plan_id: "uuid", business_id: "uuid" }
  ↓
Backend creates: Subscription → links to Business
  ↓
Business.subscription_status = 'ACTIVE'
```

---

## User Journey Comparison

### Before (Limited) ❌:

```
Step 1: Register → john@example.com
Step 2: Subscribe → Subscription created for john@example.com
Step 3: Create Business A → Linked to subscription
Step 4: Want Business B → ⚠️ Need new email: john2@example.com
```

### After (Flexible) ✅:

```
Step 1: Register → john@example.com
Step 2: Create Business A
Step 3: Subscribe Business A → Business A has subscription
Step 4: Create Business B
Step 5: Subscribe Business B → Business B has subscription
Step 6: Switch between businesses in UI
```

---

## Frontend State Structure

### Before ❌:
```javascript
{
  user: {
    id: "user-uuid",
    name: "John Doe",
    email: "john@example.com",
    subscription_status: "ACTIVE"  // ← Here
  },
  currentBusiness: {
    id: "business-uuid",
    name: "My Shop"
    // No subscription info
  }
}
```

### After ✅:
```javascript
{
  user: {
    id: "user-uuid",
    name: "John Doe",
    email: "john@example.com"
    // No subscription_status
  },
  currentBusiness: {
    id: "business-uuid",
    name: "DataLogique Systems",  // The BUSINESS (company)
    subscription_status: "ACTIVE",  // ← Moved here
    subscription: {
      plan: {...},
      end_date: "2025-11-14",
      max_storefronts: 10
    },
    storefronts: [  // Shops under this business
      { id: "sf1", name: "Accra Branch" },
      { id: "sf2", name: "Kumasi Branch" }
    ]
  },
  businesses: [  // ← List of all BUSINESSES user owns/manages
    {
      id: "business-1-uuid",
      name: "DataLogique Systems",  // First company
      subscription_status: "ACTIVE"
    },
    {
      id: "business-2-uuid",
      name: "Tech Solutions Ltd",  // Second company
      subscription_status: "TRIAL"
    }
  ]
}
```

---

## UI Component Hierarchy

### Before (Simple but Limited) ❌:
```
App
├── Header
│   ├── Logo
│   ├── User Menu (with subscription badge)
│   └── Navigation
├── Dashboard
│   └── Content (checks user.subscription_status)
└── Footer
```

### After (Flexible) ✅:
```
App
├── Header
│   ├── Logo
│   ├── Business Selector  ← NEW!
│   │   └── Dropdown
│   │       ├── DataLogique Systems (ACTIVE)
│   │       ├── Tech Solutions Ltd (TRIAL)
│   │       └── + Add New Business
│   ├── User Menu
│   └── Navigation
├── Dashboard
│   ├── Subscription Banner (for current business)
│   ├── Storefront List (all shops under current business)
│   └── Content (checks currentBusiness.subscription_status)
└── Footer
```

---

## Permission Check Flow

### Before ❌:
```
┌──────────┐
│ API Call │
└────┬─────┘
     ↓
┌──────────────────────┐
│ Check Permission     │
│ if user.subscription │
│   .status == ACTIVE  │
└────┬─────────────────┘
     ↓
┌──────────┐
│ Execute  │
└──────────┘
```

### After ✅:
```
┌──────────┐
│ API Call │
│ + business_id header │
└────┬─────┘
     ↓
┌──────────────────────┐
│ Get Business         │
│ from business_id     │
└────┬─────────────────┘
     ↓
┌──────────────────────┐
│ Check user is        │
│ member of business   │
└────┬─────────────────┘
     ↓
┌──────────────────────┐
│ Check business       │
│ .subscription_status │
└────┬─────────────────┘
     ↓
┌──────────────────────┐
│ Check limits         │
│ (users, storefronts) │
└────┬─────────────────┘
     ↓
┌──────────┐
│ Execute  │
└──────────┘
```

---

## Subscription Lifecycle

### Before ❌:
```
User → Subscribe → Active → Renew → Active
                     ↓
                   Expire
                     ↓
                  User Locked Out
```

### After ✅:
```
Business A → Subscribe → Active → Renew → Active
                           ↓
                         Expire
                           ↓
              Business A Locked Out
              (User still has access via Business B)

Business B → Subscribe → Active → ...
```

---

## Example: User with 2 Businesses

```
╔═══════════════════════════════════════════════════════════════════╗
║  USER: john@example.com (Platform User)                          ║
╚═══════════════════════════════════════════════════════════════════╝
                          │
            ┌─────────────┴──────────────┐
            ↓                            ↓
┌────────────────────────┐    ┌────────────────────────┐
│  BUSINESS A            │    │  BUSINESS B            │
│  "DataLogique Systems" │    │  "Tech Solutions Ltd"  │
│  (The Company)         │    │  (Separate Company)    │
│                        │    │                        │
│  Status: ACTIVE ✓      │    │  Status: TRIAL ⏱       │
│                        │    │                        │
│  Subscription:         │    │  Subscription:         │
│  ├─ Plan: Premium      │    │  ├─ Plan: Basic        │
│  ├─ Price: $99/mo      │    │  ├─ Price: $29/mo      │
│  ├─ Max Users: 50      │    │  ├─ Max Users: 10      │
│  └─ Max Storefronts:10 │    │  └─ Max Storefronts: 3 │
│                        │    │                        │
│  Current Usage:        │    │  Current Usage:        │
│  ├─ Users: 35/50       │    │  ├─ Users: 5/10        │
│  └─ Storefronts: 4/10  │    │  └─ Storefronts: 2/3   │
│                        │    │                        │
│  Storefronts (Shops):  │    │  Storefronts (Shops):  │
│  ├─ Accra Branch       │    │  ├─ Tema Branch        │
│  ├─ Kumasi Branch      │    │  └─ Takoradi Branch    │
│  ├─ Tamale Branch      │    │                        │
│  └─ Cape Coast Branch  │    │                        │
└────────────────────────┘    └────────────────────────┘
```

**Key Points:**
- **Business A** and **Business B** are SEPARATE COMPANIES
- Each company has ONE subscription
- Subscription covers ALL storefronts under that company
- User owns/manages both companies with one login
- **In the UI:** Business dropdown shows: "DataLogique Systems (ACTIVE)" and "Tech Solutions Ltd (TRIAL)"
- User can switch between companies to manage different businesses
- Each business has its own storefronts, users, and subscription limits

---

## Migration Timeline

```
┌─────────────────────────────────────────────────────────┐
│ Phase 1: Backend (COMPLETED ✓)                         │
├─────────────────────────────────────────────────────────┤
│ ✓ Models updated                                        │
│ ✓ Migrations applied                                    │
│ ✓ Business now has subscription_status                  │
│ ✓ Subscription now requires business_id                 │
└─────────────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────┐
│ Phase 2: Frontend (IN PROGRESS ⏳)                      │
├─────────────────────────────────────────────────────────┤
│ ⏳ Update API calls to include business_id              │
│ ⏳ Add business selector component                      │
│ ⏳ Update state management                              │
│ ⏳ Move subscription checks to business                 │
└─────────────────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────────────────┐
│ Phase 3: Testing (NEXT)                                 │
├─────────────────────────────────────────────────────────┤
│ □ Test single business workflow                         │
│ □ Test multiple business workflow                       │
│ □ Test business switching                               │
│ □ Test subscription limits                              │
└─────────────────────────────────────────────────────────┘
```

---

## Quick Reference Card

| Aspect | Before | After |
|--------|--------|-------|
| **Subscription Owner** | User | Business |
| **Status Location** | `user.subscription_status` | `business.subscription_status` |
| **Create Subscription** | `{plan_id}` | `{plan_id, business_id}` |
| **Businesses per User** | Effectively 1 | Unlimited |
| **API Context** | User-based | Business-based |
| **State Structure** | `user` object | `currentBusiness` object |
| **UI Component** | User badge | Business selector |

---

**Visual summary complete!** Share this with your frontend team for a quick understanding.
