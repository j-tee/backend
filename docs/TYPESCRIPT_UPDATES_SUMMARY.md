# TypeScript Interface Updates - Subscription System

**Date**: October 14, 2025  
**File**: `TYPESCRIPT_INTERFACES_UPDATED.ts`  
**Purpose**: Updated TypeScript interfaces matching current backend implementation

## Key Changes from Original Interfaces

### 1. Billing Cycle Type
```typescript
// BEFORE:
export type BillingCycle = 'MONTHLY' | 'QUARTERLY' | 'ANNUALLY'

// AFTER:
export type BillingCycle = 'MONTHLY' | 'QUARTERLY' | 'YEARLY'
```
**Reason**: Backend uses 'YEARLY', not 'ANNUALLY'

### 2. Payment Gateway Types
```typescript
// BEFORE:
export type PaymentGateway = 'PAYSTACK' | 'STRIPE'

// AFTER:
export type PaymentGateway = 'PAYSTACK' | 'STRIPE' | 'MOMO' | 'BANK_TRANSFER'
export type PaymentMethodType = 'MOMO' | 'PAYSTACK' | 'STRIPE' | 'BANK_TRANSFER'
```
**Reason**: Backend supports Mobile Money and Bank Transfer

### 3. Plan Interface - Major Updates
```typescript
// ADDED FIELDS:
billing_cycle_display: string       // Human-readable: "Monthly", "Quarterly", "Yearly"
max_users: number | null            // Was: max_employees
max_transactions_per_month: number | null  // Transaction limits
features_display: string[]          // Formatted features array
sort_order: number                  // Custom plan ordering
trial_period_days: number          // Trial configuration
active_subscriptions_count: number  // Usage statistics

// CHANGED:
features: string[] | Record<string, boolean>  // More flexible (can be array or object)
```

### 4. Subscription Interface - Critical Changes

#### Removed User Fields (Breaking Change!)
```typescript
// REMOVED (these don't exist on backend):
created_by: UUID
created_by_name: string

// Subscription belongs to BUSINESS, not USER!
```

#### Changed Field Names
```typescript
// BEFORE:
business: UUID
plan: UUID
trial_end: string | null
days_until_renewal: number
usage: UsageStats

// AFTER:
business_id: UUID              // Clearer naming
business?: BusinessInfo        // Full object in /me/ response
plan: Plan                     // Full plan object (not just UUID)
trial_end_date: string | null  // Consistent naming
days_until_expiry: number      // More accurate name
usage_limits?: UsageStats      // Clearer purpose
```

#### Added Critical Fields
```typescript
// Business relationship:
business_name: string
business?: BusinessInfo  // Full object from /me/ endpoint

// Plan relationship:
plan: Plan              // Full plan object with all details
plan_id?: UUID          // For write operations only

// Payment info:
payment_status: PaymentStatus
payment_method: string
amount: string
currency?: string

// Dates:
start_date: string
end_date: string
next_billing_date: string | null

// Trial:
is_trial: boolean

// Computed:
is_expired: boolean
latest_payment?: {...}  // Latest successful payment
```

### 5. Payment Status Values
```typescript
// BEFORE:
status: PaymentStatus  // Generic

// AFTER:
status: 'SUCCESSFUL' | 'PENDING' | 'FAILED' | 'CANCELLED' | 'REFUNDED'
```
**Reason**: More specific status values from backend

### 6. Payment Fields Updated
```typescript
// CHANGED:
subscription_plan_name?: string      // Added for display
subscription_business_name?: string  // Added for display
transaction_id: string | null        // Was: transaction_reference
gateway_reference: string | null     // Added
billing_period_start: string         // Added
billing_period_end: string          // Added
```

### 7. Invoice Fields Updated
```typescript
// ADDED:
subscription_plan_name?: string
subscription_business_name?: string
tax_amount: string
total_amount: string
is_overdue: boolean
days_overdue: number

// CHANGED:
billing_period_start: string  // Was: period_start
billing_period_end: string    // Was: period_end
notes: string | null          // Can be null
```

### 8. Alert Fields Updated
```typescript
// ADDED:
subscription_business_name?: string
subscription_plan_name?: string
email_sent: boolean
sms_sent: boolean
in_app_shown: boolean
action_taken: boolean
action_taken_at: string | null
metadata: Record<string, unknown>
```

### 9. Payment Response Structures
```typescript
// BEFORE:
export interface PaymentInitiationResponse {
  success: boolean
  authorization_url?: string
  reference?: string
  session_id?: string
  checkout_url?: string
}

// AFTER:
export interface PaymentInitiationResponse {
  status: string
  message: string
  data: {
    authorization_url?: string  // Paystack
    checkout_url?: string       // Stripe
    access_code?: string        // Paystack
    session_id?: string         // Stripe
    reference: string           // Always present
  }
}
```

### 10. New Type: MySubscriptionsResponse
```typescript
// ⚠️ CRITICAL: /me/ endpoint returns ARRAY
export type MySubscriptionsResponse = Subscription[]
```

### 11. Usage Stats Structure
```typescript
// BEFORE:
export interface UsageStats {
  storefronts: {
    used: number
    limit: number
  }
  // ...
}

// AFTER:
export interface UsageStats {
  users?: {
    current: number  // was: used
    limit: number | null
    exceeded: boolean  // Added
  }
  storefronts?: {
    current: number
    limit: number | null
    exceeded: boolean
  }
  products?: {
    current: number
    limit: number | null
    exceeded: boolean
  }
}
```

## Breaking Changes Summary

### 1. /me/ Endpoint Returns Array
```typescript
// ❌ WRONG:
const { data: subscription } = await api.get('/me/')
console.log(subscription.plan.name)

// ✅ CORRECT:
const { data: subscriptions } = await api.get('/me/')
if (subscriptions.length > 0) {
  console.log(subscriptions[0].plan.name)
}
```

### 2. No User Fields in Subscription
```typescript
// ❌ REMOVED:
subscription.created_by
subscription.created_by_name

// ✅ USE INSTEAD:
subscription.business_id
subscription.business_name
subscription.business  // Full object in /me/ response
```

### 3. business_id Required for Creation
```typescript
// ❌ WRONG:
const request: CreateSubscriptionRequest = {
  plan_id: "uuid"
  // Missing business_id!
}

// ✅ CORRECT:
const request: CreateSubscriptionRequest = {
  plan_id: "uuid",
  business_id: currentBusiness.id  // REQUIRED
}
```

### 4. Billing Cycle Value Changed
```typescript
// ❌ WRONG:
if (plan.billing_cycle === 'ANNUALLY') { ... }

// ✅ CORRECT:
if (plan.billing_cycle === 'YEARLY') { ... }
```

## New Helper Types

```typescript
// Paginated responses
export type PlansListResponse = PaginatedResponse<Plan>
export type SubscriptionsListResponse = PaginatedResponse<Subscription>
export type PaymentsListResponse = PaginatedResponse<SubscriptionPayment>
export type InvoicesListResponse = PaginatedResponse<Invoice>
export type AlertsListResponse = PaginatedResponse<SubscriptionAlert>

// Business info in responses
export interface BusinessInfo {
  id: UUID
  name: string
  description?: string
}
```

## Usage Examples Included

The file includes comprehensive usage examples in comments:

1. ✅ How to handle /me/ endpoint array response
2. ✅ How to create subscriptions with business_id
3. ✅ Understanding business-centric architecture
4. ✅ Handling empty subscription states
5. ✅ Payment gateway selection
6. ✅ Billing cycle values

## Implementation Checklist

When integrating these interfaces:

- [ ] Replace old `BillingCycle` type everywhere
- [ ] Update /me/ endpoint calls to handle arrays
- [ ] Add `business_id` to subscription creation
- [ ] Remove references to `subscription.created_by`
- [ ] Update to use `subscription.business_id` and `subscription.business_name`
- [ ] Handle `plan` as full object (not just UUID)
- [ ] Update payment response handling (wrapped in `data` object)
- [ ] Use `billing_cycle_display` for user-facing text
- [ ] Handle empty subscriptions array (not 404)

## File Location

**Created**: `/home/teejay/Documents/Projects/pos/backend/TYPESCRIPT_INTERFACES_UPDATED.ts`

**To Use**: Copy this file to your frontend TypeScript project and adjust the import path for `UUID` type.

---

**Status**: ✅ Complete and ready for frontend integration  
**Compatibility**: Matches backend as of October 14, 2025  
**Breaking Changes**: Documented with migration examples
