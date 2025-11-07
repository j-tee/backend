# AI Credits Database Schema - Simple Explanation

**Date**: November 7, 2025  
**Purpose**: Explain how the AI credits system works in simple terms

---

## The Big Picture 🎯

Think of the AI credits system like a **prepaid mobile phone plan**:
- You **buy credits** (like buying airtime)
- You **use credits** when making AI requests (like making phone calls)
- You can **check your balance** anytime
- Credits **expire** after 6 months (like unused data bundles)

---

## The 4 Main Tables

### 1. 💰 **BusinessAICredits** - Your Credit Balance (like your phone balance)

**Purpose**: Stores the CURRENT credit balance for each business

```
Think of it as: Your bank account balance
```

**What it stores:**
- `business` → Which business owns these credits
- `balance` → How many credits they have right now (e.g., 50.00)
- `expires_at` → When the credits will expire (6 months from purchase)
- `is_active` → Are these credits still valid? (true/false)
- `purchased_at` → When these credits were first created
- `updated_at` → Last time the balance changed

**Example:**
```
Business: DataLogique Systems
Balance: 80.00 credits
Expires: May 6, 2026
Active: Yes
```

**Key Point**: Each business has ONE active record that tracks their CURRENT balance. When they buy more credits, this balance INCREASES. When they use AI features, this balance DECREASES.

---

### 2. 🛒 **AICreditPurchase** - Purchase History (like your receipts)

**Purpose**: Records EVERY TIME someone buys credits (the transaction history)

```
Think of it as: Your purchase receipts/invoices
```

**What it stores:**
- `business` → Who bought the credits
- `user` → Which user in the business made the purchase
- `amount_paid` → How much money they paid (e.g., GHS 30.00)
- `credits_purchased` → Base credits bought (e.g., 30 credits)
- `bonus_credits` → Extra credits given (e.g., 20 bonus)
- `payment_reference` → Unique payment ID (e.g., "AI-CREDIT-123456")
- `payment_status` → pending, completed, failed, or refunded
- `payment_method` → mobile_money, card, admin_grant, etc.

**Example:**
```
Purchase #1:
  Business: DataLogique Systems
  Paid: GHS 30.00
  Got: 30 credits (no bonus)
  Reference: AI-CREDIT-1762540463876-713300bc
  Status: Completed
  Date: Nov 7, 2025
```

**Key Point**: This table keeps a HISTORY of all purchases. Even after credits are used up, the purchase record remains (like keeping old receipts).

---

### 3. 📊 **AITransaction** - Usage Log (like your call history)

**Purpose**: Records EVERY TIME someone uses AI credits (the usage history)

```
Think of it as: Your phone call history showing each call made
```

**What it stores:**
- `business` → Who used the credits
- `user` → Which user made the AI request
- `feature` → What AI feature was used (e.g., "Product Description Generator")
- `credits_used` → How many credits were deducted (e.g., 2.50)
- `cost_to_us` → What OpenAI charged us (for analytics)
- `tokens_used` → How many AI tokens were used
- `timestamp` → When the request was made
- `success` → Did it work? (true/false)
- `processing_time_ms` → How long it took

**Example:**
```
Transaction #1:
  Business: DataLogique Systems
  Feature: Product Description Generator
  Credits Used: 2.50
  Success: Yes
  Date: Nov 7, 2025 10:30 AM
```

**Key Point**: Every time you use an AI feature, a record is created here showing what you used and when. This helps with analytics and billing transparency.

---

### 4. 🔔 **AIUsageAlert** - Low Balance Warnings (like low battery alerts)

**Purpose**: Tracks alerts sent when credits are running low

```
Think of it as: Low balance SMS notifications
```

**What it stores:**
- `business` → Which business got the alert
- `alert_type` → low_balance, depleted, or expired
- `current_balance` → Balance when alert was sent
- `threshold` → Balance level that triggered alert
- `sent_at` → When the alert was sent
- `acknowledged` → Did they see it? (true/false)

**Example:**
```
Alert #1:
  Business: DataLogique Systems
  Type: Low Balance
  Balance: 5.00 credits
  Threshold: 10.00 credits
  Sent: Nov 7, 2025
```

**Key Point**: Prevents businesses from running out of credits unexpectedly by warning them in advance.

---

## How It All Works Together 🔄

### Scenario 1: Buying Credits

```
1. User clicks "Buy 30 Credits" (Starter Package)
2. Pays GHS 30.00 via Paystack
3. System creates:
   
   ✅ AICreditPurchase record:
      - amount_paid: 30.00
      - credits_purchased: 30.00
      - payment_status: completed
   
   ✅ Updates BusinessAICredits:
      - balance: 50.00 → 80.00 (adds 30)
      - expires_at: May 6, 2026 (6 months from now)

Result: Business now has 80 credits!
```

---

### Scenario 2: Using Credits

```
1. User generates a product description (costs 2.50 credits)
2. System creates:
   
   ✅ AITransaction record:
      - feature: product_description
      - credits_used: 2.50
      - success: true
   
   ✅ Updates BusinessAICredits:
      - balance: 80.00 → 77.50 (deducts 2.50)

Result: Business now has 77.50 credits!
```

---

### Scenario 3: Low Balance Alert

```
1. Business uses credits: 77.50 → 8.00
2. Balance drops below 10.00 threshold
3. System creates:
   
   ✅ AIUsageAlert record:
      - alert_type: low_balance
      - current_balance: 8.00
      - threshold: 10.00
   
   ✅ Sends notification to business owner

Result: Business gets warning to buy more credits!
```

---

## Visual Relationship Diagram 📊

```
┌─────────────────────────────────────────────────────────────────┐
│                         BUSINESS                                 │
│                    (e.g., DataLogique)                          │
└────────────────────┬─────────────────┬────────────────┬─────────┘
                     │                 │                │
                     │                 │                │
        ┌────────────▼──────┐  ┌──────▼─────────┐  ┌──▼──────────┐
        │ BusinessAICredits │  │ AICreditPurchase│  │AITransaction│
        │                   │  │                  │  │             │
        │ Balance: 80.00    │  │ History Record 1 │  │ Used 2.50   │
        │ Expires: May 2026 │  │ History Record 2 │  │ Used 1.75   │
        │ Active: Yes       │  │ History Record 3 │  │ Used 3.00   │
        └───────────────────┘  └──────────────────┘  └─────────────┘
                │
                │ (triggers when low)
                │
        ┌───────▼─────────┐
        │  AIUsageAlert   │
        │                 │
        │ Type: Low       │
        │ Balance: 8.00   │
        └─────────────────┘
```

---

## Key Differences Explained 🔑

### BusinessAICredits vs AICreditPurchase

| Aspect | BusinessAICredits | AICreditPurchase |
|--------|------------------|------------------|
| **What** | Current balance | Purchase history |
| **When** | Always up-to-date | Historical records |
| **How many** | ONE per business | MANY per business |
| **Example** | "You have 80 credits" | "You bought 30 credits on Nov 7" |
| **Like** | Bank balance | Bank statement |

---

## Real-World Example 🌍

Let's follow **DataLogique Systems** through a week:

### Monday - Starting Fresh
```
BusinessAICredits:
  Balance: 0 credits
  
AICreditPurchase:
  (empty - no purchases yet)
```

### Tuesday - First Purchase
```
BusinessAICredits:
  Balance: 50 credits  ← UPDATED
  Expires: May 6, 2026
  
AICreditPurchase:
  Record #1: Bought 50 credits (GHS 0.00 - Free Trial)  ← NEW
```

### Wednesday - Using AI Features
```
BusinessAICredits:
  Balance: 45.50 credits  ← DEDUCTED 4.50
  
AITransaction:
  Record #1: Product description (-2.50)  ← NEW
  Record #2: Customer insight (-2.00)     ← NEW
  
AICreditPurchase:
  Record #1: Bought 50 credits (unchanged)
```

### Thursday - Buying More
```
BusinessAICredits:
  Balance: 75.50 credits  ← ADDED 30
  
AICreditPurchase:
  Record #1: Bought 50 credits (Free Trial)
  Record #2: Bought 30 credits (GHS 30.00)  ← NEW
  
AITransaction:
  Record #1: Product description (-2.50)
  Record #2: Customer insight (-2.00)
```

### Friday - Heavy Usage
```
BusinessAICredits:
  Balance: 8.00 credits  ← DEDUCTED 67.50
  
AIUsageAlert:
  Alert #1: Low balance warning (8.00 < 10.00)  ← NEW
  
AITransaction:
  Record #1-20: Various AI features used
  
AICreditPurchase:
  Record #1: Bought 50 credits
  Record #2: Bought 30 credits
```

---

## Common Questions ❓

### Q1: Why do we have separate tables for balance and purchases?

**A:** 
- **BusinessAICredits** = What you have NOW (like checking your phone balance)
- **AICreditPurchase** = What you bought BEFORE (like your purchase history)

You need both because:
- You want to quickly check "How many credits do I have?" → Look at BusinessAICredits
- You want to see "When did I buy credits?" → Look at AICreditPurchase

### Q2: What happens when I buy more credits?

**A:**
1. New record created in **AICreditPurchase** (the receipt)
2. Balance increased in **BusinessAICredits** (your wallet)
3. Both tables are updated, but serve different purposes

### Q3: Why keep purchase history after credits are used?

**A:** For accounting, analytics, and customer support:
- "When did I last buy credits?"
- "How much did I spend this month?"
- "Show me all my invoices"

### Q4: Can a business have multiple BusinessAICredits records?

**A:** Technically yes, but typically NO in practice:
- ONE active record per business (is_active=True)
- Old expired records become inactive (is_active=False)
- Current balance is always in the active record

### Q5: What's the difference between credits_purchased and bonus_credits?

**A:**
- **credits_purchased**: What you paid for (e.g., 80 credits for GHS 80)
- **bonus_credits**: Free extra credits (e.g., 20 bonus = 25% extra)
- **Total**: 80 + 20 = 100 credits added to balance

---

## Summary 📝

Think of the system as a **prepaid service**:

1. **BusinessAICredits** = Your current wallet balance
2. **AICreditPurchase** = Your receipts/invoices
3. **AITransaction** = Your usage statements
4. **AIUsageAlert** = Your low balance notifications

**Simple Flow:**
1. Buy credits → Record in AICreditPurchase, add to BusinessAICredits balance
2. Use AI feature → Record in AITransaction, deduct from BusinessAICredits balance
3. Balance low → Create AIUsageAlert, notify business
4. Credits expire → BusinessAICredits becomes inactive

---

## Quick Reference Table 📋

| Table | Purpose | Updates | Records |
|-------|---------|---------|---------|
| **BusinessAICredits** | Current balance | Every purchase/use | 1 active per business |
| **AICreditPurchase** | Purchase history | On every purchase | Many per business |
| **AITransaction** | Usage history | On every AI request | Many per business |
| **AIUsageAlert** | Low balance warnings | When balance drops | Many per business |

---

**Need More Help?**
- See the models file: `ai_features/models.py`
- See the billing service: `ai_features/services/billing.py`
- Run: `python manage.py setup_ai_credits --list-businesses`
