import type { UUID } from './common'

export type BillingCycle = 'MONTHLY' | 'QUARTERLY' | 'YEARLY'  // Changed: ANNUALLY → YEARLY

export type SubscriptionStatus = 
  | 'TRIAL'
  | 'ACTIVE'
  | 'PAST_DUE'
  | 'INACTIVE'
  | 'CANCELLED'
  | 'SUSPENDED'
  | 'EXPIRED'

export type PaymentGateway = 'PAYSTACK' | 'STRIPE' | 'MOMO' | 'BANK_TRANSFER'  // Added: MOMO, BANK_TRANSFER

export type PaymentStatus = 'PAID' | 'PENDING' | 'FAILED' | 'OVERDUE' | 'CANCELLED'

export type PaymentMethodType = 'MOMO' | 'PAYSTACK' | 'STRIPE' | 'BANK_TRANSFER'  // Added: Matches backend PAYMENT_METHOD_CHOICES

export type InvoiceStatus = 'DRAFT' | 'SENT' | 'PAID' | 'OVERDUE' | 'CANCELLED'

export type AlertPriority = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'

export type AlertType =
  | 'PAYMENT_DUE'
  | 'PAYMENT_FAILED'
  | 'PAYMENT_SUCCESS'
  | 'TRIAL_ENDING'
  | 'SUBSCRIPTION_EXPIRING'
  | 'SUBSCRIPTION_EXPIRED'
  | 'USAGE_LIMIT_WARNING'
  | 'USAGE_LIMIT_REACHED'
  | 'SUBSCRIPTION_CANCELLED'
  | 'SUBSCRIPTION_SUSPENDED'
  | 'SUBSCRIPTION_ACTIVATED'

// Business info included in subscription responses
export interface BusinessInfo {
  id: UUID
  name: string
  description?: string
}

export interface Plan {
  id: UUID
  name: string
  description: string
  price: string
  currency: string
  billing_cycle: BillingCycle
  billing_cycle_display: string  // Added: Human-readable billing cycle
  
  // Limits
  max_users: number | null  // Changed: max_employees → max_users
  max_storefronts: number | null
  max_products: number | null
  max_transactions_per_month: number | null  // Added: Transaction limit
  
  // Features (can be list or object)
  features: string[] | Record<string, boolean>  // Changed: More flexible type
  features_display: string[]  // Added: Formatted features for display
  
  is_active: boolean
  is_popular: boolean
  sort_order: number  // Added: For custom ordering
  trial_period_days: number  // Added: Trial period configuration
  active_subscriptions_count: number  // Added: Count of active subscriptions
  
  created_at: string
  updated_at: string
}

export interface UsageStats {
  users?: {  // Changed: employees → users
    current: number
    limit: number | null
    exceeded: boolean
  }
  storefronts?: {
    current: number  // Changed: used → current
    limit: number | null
    exceeded: boolean
  }
  products?: {
    current: number  // Changed: used → current
    limit: number | null
    exceeded: boolean
  }
}

export interface Subscription {
  id: UUID
  
  // Business relationship (NOT user!)
  business_id: UUID  // Changed: business → business_id
  business_name: string
  business?: BusinessInfo  // Added: Full business object (from /me/ endpoint)
  
  // Plan relationship
  plan: Plan  // Changed: Full plan object (not just UUID)
  plan_id?: UUID  // Added: For write operations
  
  // Status and lifecycle
  status: SubscriptionStatus
  payment_status: PaymentStatus  // Added: Payment status
  payment_method: string  // Added: Payment method used
  
  // Billing periods
  start_date: string  // Added: Subscription start
  end_date: string  // Added: Subscription end
  current_period_start: string
  current_period_end: string
  next_billing_date: string | null  // Added: Next billing date
  
  // Trial info
  is_trial: boolean  // Added: Trial flag
  trial_end_date: string | null  // Changed: trial_end → trial_end_date
  
  // Renewal and cancellation
  auto_renew: boolean
  cancel_at_period_end: boolean
  cancelled_at: string | null
  cancelled_by: UUID | null  // Added: Who cancelled it
  
  // Amounts
  amount: string  // Added: Subscription amount
  currency?: string  // Added: Currency
  
  // Computed fields
  grace_period_days: number
  days_until_expiry: number  // Changed: days_until_renewal → days_until_expiry
  is_active: boolean
  is_expired: boolean  // Added: Expiry check
  
  // Usage tracking
  usage_limits?: UsageStats  // Changed: usage → usage_limits
  latest_payment?: {  // Added: Latest payment info
    id: string
    amount: string
    payment_date: string
    payment_method: string
  }
  
  // Metadata
  notes: string
  created_at: string
  updated_at: string
}

// For /me/ endpoint - returns array of subscriptions
export type MySubscriptionsResponse = Subscription[]  // ⚠️ IMPORTANT: Returns array!

export interface SubscriptionPayment {
  id: UUID
  subscription: UUID
  subscription_plan_name?: string  // Added: Plan name for display
  subscription_business_name?: string  // Added: Business name for display
  
  amount: string
  payment_method: PaymentMethodType  // Changed: Use PaymentMethodType
  status: 'SUCCESSFUL' | 'PENDING' | 'FAILED' | 'CANCELLED' | 'REFUNDED'  // Changed: More specific statuses
  
  transaction_id: string | null  // Changed: transaction_reference → transaction_id
  gateway_reference: string | null  // Added: Gateway-specific reference
  gateway_response: Record<string, unknown>
  
  payment_date: string | null
  
  billing_period_start: string  // Added: Billing period info
  billing_period_end: string  // Added: Billing period info
  
  notes: string
  created_at: string
  updated_at: string
}

export interface Invoice {
  id: UUID
  subscription: UUID
  subscription_plan_name?: string  // Added: Plan name for display
  subscription_business_name?: string  // Added: Business name for display
  
  invoice_number: string
  amount: string
  tax_amount: string  // Added: Tax amount
  total_amount: string  // Added: Total with tax
  
  status: InvoiceStatus
  
  billing_period_start: string  // Changed: period_start → billing_period_start
  billing_period_end: string  // Changed: period_end → billing_period_end
  issue_date: string
  due_date: string
  paid_date: string | null
  
  is_overdue: boolean  // Added: Computed field
  days_overdue: number  // Added: Computed field
  
  notes: string | null  // Changed: Can be null
  created_at: string
  updated_at: string
}

export interface SubscriptionAlert {
  id: UUID
  subscription: UUID
  subscription_business_name?: string  // Added: Business name for display
  subscription_plan_name?: string  // Added: Plan name for display
  
  alert_type: AlertType
  priority: AlertPriority
  
  title: string
  message: string
  
  // Notification channels
  email_sent: boolean  // Added: Email notification status
  sms_sent: boolean  // Added: SMS notification status
  in_app_shown: boolean  // Added: In-app notification status
  
  // User actions
  is_read: boolean
  is_dismissed: boolean
  action_taken: boolean  // Added: User took action
  action_taken_at: string | null  // Added: When action was taken
  
  read_at: string | null
  dismissed_at: string | null
  
  metadata: Record<string, unknown>  // Added: Additional alert data
  
  created_at: string
}

export interface PaymentInitiationResponse {
  status: string  // Added: Response status
  message: string  // Added: Response message
  data: {  // Changed: Wrapped in data object
    authorization_url?: string  // Paystack
    checkout_url?: string  // Stripe
    access_code?: string  // Paystack
    session_id?: string  // Stripe
    reference: string  // Common reference
  }
}

export interface PaymentVerificationResponse {
  success: boolean
  message: string
  payment?: SubscriptionPayment  // Changed: Optional, only present if successful
}

export interface SubscriptionStats {
  total_subscriptions: number
  active_subscriptions: number
  trial_subscriptions: number
  expired_subscriptions: number
  cancelled_subscriptions: number
  total_revenue: string
  monthly_recurring_revenue: string
  average_subscription_value: string
  churn_rate: number
}

export interface CreateSubscriptionRequest {
  plan_id: UUID
  business_id: UUID  // ⚠️ REQUIRED - subscription belongs to business, not user
  payment_method?: PaymentMethodType  // Changed: Optional, can be set later
  is_trial?: boolean
  trial_end_date?: string  // Added: Optional trial end date override
}

export interface CancelSubscriptionRequest {
  immediately?: boolean
  reason?: string
}

export interface InitializePaymentRequest {
  gateway: PaymentGateway
  callback_url?: string
  success_url?: string  // Stripe only
  cancel_url?: string  // Stripe only
}

export interface VerifyPaymentRequest {
  gateway: PaymentGateway
  reference: string  // Required: payment reference or session_id
}

// ============================================
// API Response Types
// ============================================

export interface PaginatedResponse<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

// Plans list response
export type PlansListResponse = PaginatedResponse<Plan>

// Subscriptions list response
export type SubscriptionsListResponse = PaginatedResponse<Subscription>

// Payments list response
export type PaymentsListResponse = PaginatedResponse<SubscriptionPayment>

// Invoices list response
export type InvoicesListResponse = PaginatedResponse<Invoice>

// Alerts list response
export type AlertsListResponse = PaginatedResponse<SubscriptionAlert>

// ============================================
// Usage Examples for Frontend
// ============================================

/*
IMPORTANT NOTES FOR FRONTEND DEVELOPERS:

1. GET /subscriptions/api/subscriptions/me/ returns ARRAY, not single object!
   
   ❌ WRONG:
   const { data: subscription } = await api.get('/subscriptions/api/subscriptions/me/')
   console.log(subscription.plan.name)  // Error: subscription is array!
   
   ✅ CORRECT:
   const { data: subscriptions } = await api.get('/subscriptions/api/subscriptions/me/')
   if (subscriptions.length > 0) {
     console.log(subscriptions[0].plan.name)  // Works!
   }

2. Creating subscription requires business_id (REQUIRED):
   
   ❌ WRONG:
   await api.post('/subscriptions/api/subscriptions/', {
     plan_id: selectedPlan.id
     // Missing business_id!
   })
   
   ✅ CORRECT:
   await api.post('/subscriptions/api/subscriptions/', {
     plan_id: selectedPlan.id,
     business_id: currentBusiness.id  // Required!
   })

3. Subscription belongs to BUSINESS, not USER:
   - Each business has one subscription
   - Users access subscriptions through business membership
   - Use subscription.business_id and subscription.business_name

4. Empty /me/ response is [] not 404:
   ✅ CORRECT:
   const { data: subscriptions } = await api.get('/subscriptions/api/subscriptions/me/')
   if (subscriptions.length === 0) {
     // No subscriptions - this is normal!
   }

5. Payment gateway types:
   - 'PAYSTACK' - For Ghana/Mobile Money
   - 'STRIPE' - For international cards
   - 'MOMO' - Mobile Money direct
   - 'BANK_TRANSFER' - Bank transfer

6. Billing cycles:
   - 'MONTHLY' - Monthly billing
   - 'QUARTERLY' - Every 3 months
   - 'YEARLY' - Annual billing (not 'ANNUALLY')
*/
