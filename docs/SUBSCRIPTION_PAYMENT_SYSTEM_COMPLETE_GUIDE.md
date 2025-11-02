# POS Subscription Payment System - Complete Guide

**Last Updated**: November 2, 2025  
**Version**: 1.0  
**Status**: Production Ready

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Installation & Setup](#installation--setup)
4. [Environment Configuration](#environment-configuration)
5. [Database Models](#database-models)
6. [API Endpoints](#api-endpoints)
7. [Payment Flow](#payment-flow)
8. [Paystack Integration](#paystack-integration)
9. [Testing Guide](#testing-guide)
10. [Deployment](#deployment)
11. [Troubleshooting](#troubleshooting)
12. [API Reference](#api-reference)

---

## Overview

The POS Subscription Payment System is a comprehensive, backend-first payment infrastructure that implements flexible subscription pricing for multi-storefront businesses. It integrates with Paystack payment gateway and supports Ghana's tax system.

### Key Features

- ✅ **Backend-First Architecture** - All calculations on server, frontend only displays
- ✅ **Flexible Pricing** - Tier-based pricing with dynamic storefront scaling
- ✅ **Ghana Tax Compliance** - VAT, NHIL, GETFund, COVID-19 levies
- ✅ **Paystack Integration** - Secure payment processing with webhook validation
- ✅ **Shared Account Support** - Multi-app routing via `app_name` metadata
- ✅ **Comprehensive Tracking** - Payment history, status transitions, failure reasons
- ✅ **Service Charges** - Payment gateway fees calculated automatically

### Technology Stack

- **Backend**: Django 5.2.6, Django REST Framework 3.14.0
- **Database**: PostgreSQL
- **Payment Gateway**: Paystack
- **Task Queue**: Celery + Redis
- **Authentication**: JWT (Django REST Framework)

---

## Architecture

### Backend-First Design Principles

1. **Single Source of Truth**: All pricing calculations happen on backend
2. **Security**: No sensitive logic exposed to client
3. **Consistency**: Same pricing logic across all endpoints
4. **Auditability**: Complete tracking of all calculations and transactions

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                        FRONTEND                              │
│  - Display pricing breakdown                                 │
│  - Collect user input (plan, storefront count)              │
│  - Redirect to Paystack payment page                        │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│                    DJANGO BACKEND                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Pricing Calculation API                             │   │
│  │  - Calculate base amount                             │   │
│  │  - Apply pricing tier logic                          │   │
│  │  - Calculate taxes (VAT, NHIL, GETFund, COVID-19)   │   │
│  │  - Calculate service charges                         │   │
│  │  - Return complete breakdown                         │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Payment Initialization                              │   │
│  │  - Create subscription record                        │   │
│  │  - Create payment record                             │   │
│  │  - Initialize Paystack transaction                   │   │
│  │  - Return authorization URL                          │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Webhook Handler                                     │   │
│  │  - Validate HMAC-SHA512 signature                    │   │
│  │  - Filter by app_name routing                        │   │
│  │  - Verify payment with Paystack                      │   │
│  │  - Activate subscription                             │   │
│  │  - Record status history                             │   │
│  └──────────────────────────────────────────────────────┘   │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│                    PAYSTACK GATEWAY                          │
│  - Process payment                                           │
│  - Send webhook notification                                 │
│  - Return payment status                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Installation & Setup

### Prerequisites

- Python 3.8+
- PostgreSQL 12+
- Redis (for Celery)
- Git
- Virtual environment tool

### Step 1: Clone and Setup Environment

```bash
# Navigate to backend directory
cd /home/teejay/Documents/Projects/pos/backend

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables

```bash
# Copy environment template
cp .env.template .env.development

# Edit with your configuration
nano .env.development
```

**Required Variables**:
```bash
# Paystack Keys (REQUIRED)
PAYSTACK_SECRET_KEY=sk_test_16b164b455153a23804423ec0198476b3c4ca206
PAYSTACK_PUBLIC_KEY=pk_test_5309f5af38555dbf7ef47287822ef2c6d3019b9d
PAYSTACK_APP_NAME=pos

# Frontend URL
FRONTEND_URL=http://localhost:5173

# Database
DB_NAME=pos_db
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432

# Django
SECRET_KEY=your-django-secret-key
DEBUG=true
ALLOWED_HOSTS=localhost,127.0.0.1
```

### Step 3: Database Migration

```bash
# Activate virtual environment
source venv/bin/activate

# Create migrations
python manage.py makemigrations subscriptions

# Apply migrations
python manage.py migrate

# Setup default pricing data
python manage.py setup_default_pricing
```

**Expected Output**:
```
Setting up default pricing tiers...
  ✓ Created tier: 1-1 storefronts: GHS 100.00
  ✓ Created tier: 2-2 storefronts: GHS 150.00
  ✓ Created tier: 3-3 storefronts: GHS 180.00
  ✓ Created tier: 4-4 storefronts: GHS 200.00
  ✓ Created tier: 5+ storefronts: GHS 200.00 + 50.00/extra

Setting up Ghana tax configurations...
  ✓ Created tax: VAT (15.00%) - GH
  ✓ Created tax: NHIL (2.50%) - GH
  ✓ Created tax: GETFund Levy (2.50%) - GH
  ✓ Created tax: COVID-19 Health Recovery Levy (1.00%) - GH
```

### Step 4: Create Superuser (Optional)

```bash
source venv/bin/activate
python manage.py createsuperuser
```

### Step 5: Start Development Server

```bash
source venv/bin/activate
python manage.py runserver
```

Server will be available at: `http://localhost:8000`

---

## Environment Configuration

### Environment Files Structure

The project uses `python-decouple` for environment management:

- **`.env.development`** - Development environment (test keys)
- **`.env.production`** - Production environment (live keys)
- **`.env.template`** - Template with all variables

### Loading Environment Files

Django automatically loads `.env.development` by default. To use a different file:

```bash
export DJANGO_ENV_FILE=.env.production
python manage.py runserver
```

### Paystack Configuration

#### Development (Test Keys)

```bash
# In .env.development
PAYSTACK_SECRET_KEY=sk_test_16b164b455153a23804423ec0198476b3c4ca206
PAYSTACK_PUBLIC_KEY=pk_test_5309f5af38555dbf7ef47287822ef2c6d3019b9d
PAYSTACK_APP_NAME=pos
```

#### Production (Live Keys)

```bash
# In .env.production
PAYSTACK_SECRET_KEY=sk_live_your_actual_live_secret_key
PAYSTACK_PUBLIC_KEY=pk_live_your_actual_live_public_key
PAYSTACK_APP_NAME=pos
```

⚠️ **IMPORTANT**: 
- Never commit `.env.production` with live keys to version control
- Get live keys from: https://dashboard.paystack.com/settings/developer
- Restrict file permissions: `chmod 600 .env.production`

### Shared Paystack Account

Since the Paystack account is shared across multiple applications, the `PAYSTACK_APP_NAME` is **critical**:

- All transactions include `app_name: 'pos'` in metadata
- Webhook handler filters events by this value
- Prevents processing events from other apps on the same account

### Verifying Configuration

```bash
source venv/bin/activate
python manage.py shell
```

```python
from django.conf import settings

# Verify keys are loaded
print(f"Secret Key: {settings.PAYSTACK_SECRET_KEY[:10]}...")
print(f"Public Key: {settings.PAYSTACK_PUBLIC_KEY[:10]}...")
print(f"App Name: {settings.PAYSTACK_APP_NAME}")
```

---

## Database Models

### SubscriptionPricingTier

Dynamic pricing tiers based on storefront count.

**Fields**:
- `name` - Tier name (e.g., "Starter", "Professional")
- `min_storefronts` - Minimum storefronts (default: 1)
- `max_storefronts` - Maximum storefronts (null for unlimited)
- `base_price` - Base price for tier (Decimal)
- `price_per_additional_storefront` - Cost per extra storefront (Decimal)
- `currency` - Currency code (default: "GHS")
- `is_active` - Whether tier is active (Boolean)

**Example**:
```python
# 1-3 storefronts: GHS 100 flat
tier = SubscriptionPricingTier.objects.create(
    name="Starter",
    min_storefronts=1,
    max_storefronts=3,
    base_price=Decimal('100.00'),
    price_per_additional_storefront=Decimal('0.00')
)

# 4+ storefronts: GHS 200 + GHS 50 per extra
tier = SubscriptionPricingTier.objects.create(
    name="Enterprise",
    min_storefronts=4,
    max_storefronts=None,  # Unlimited
    base_price=Decimal('200.00'),
    price_per_additional_storefront=Decimal('50.00')
)
```

### TaxConfiguration

Ghana tax configuration with effective date tracking.

**Fields**:
- `name` - Tax name (e.g., "VAT", "NHIL")
- `tax_type` - Type: VAT, NHIL, GETFUND, COVID19, OTHER
- `rate` - Tax rate percentage (Decimal)
- `country` - Country code (default: "GH")
- `effective_from` - Start date
- `effective_until` - End date (null if still active)
- `is_active` - Whether tax is currently active

**Ghana Taxes**:
```python
taxes = [
    {'name': 'VAT', 'rate': Decimal('15.00')},
    {'name': 'NHIL', 'rate': Decimal('2.50')},
    {'name': 'GETFund Levy', 'rate': Decimal('2.50')},
    {'name': 'COVID-19 Levy', 'rate': Decimal('1.00')},
]
```

### ServiceCharge

Payment gateway fees and service charges.

**Fields**:
- `name` - Charge name (e.g., "Paystack Fee")
- `charge_type` - Type: PERCENTAGE or FIXED
- `rate` - Rate/amount (Decimal)
- `payment_gateway` - Gateway: PAYSTACK, STRIPE, OTHER
- `currency` - Currency code
- `is_active` - Whether charge is active

**Example**:
```python
# Paystack charges 1.95% per transaction
charge = ServiceCharge.objects.create(
    name="Paystack Transaction Fee",
    charge_type='PERCENTAGE',
    rate=Decimal('1.95'),
    payment_gateway='PAYSTACK'
)
```

### SubscriptionPayment (Enhanced)

Complete payment tracking with detailed breakdown.

**New Fields**:
- `base_amount` - Subscription base price
- `storefront_count` - Number of storefronts
- `tax_breakdown` - JSON array of applied taxes
- `total_tax_amount` - Sum of all taxes
- `service_charges_breakdown` - JSON array of charges
- `total_service_charges` - Sum of all service charges
- `currency` - Currency code (default: "GHS")
- `transaction_reference` - Paystack transaction reference
- `pricing_tier_snapshot` - JSON snapshot of pricing tier
- `status_history` - JSON array of status changes
- `failure_reason` - Payment failure description
- `gateway_error_code` - Payment gateway error code
- `gateway_error_message` - Payment gateway error message
- `attempt_number` - Payment attempt count
- `previous_attempt` - Link to previous payment attempt

**Example Status History**:
```json
[
    {
        "status": "pending",
        "timestamp": "2025-11-02T10:00:00Z",
        "note": "Payment initialized"
    },
    {
        "status": "completed",
        "timestamp": "2025-11-02T10:05:00Z",
        "note": "Payment verified successfully"
    }
]
```

---

## API Endpoints

### Base URL

```
http://localhost:8000/api/subscriptions/
```

### Authentication

All endpoints require JWT authentication (except webhooks):

```bash
Authorization: Bearer <your_access_token>
```

### 1. Pricing Calculation

**Endpoint**: `POST /api/subscriptions/pricing/calculate/`

**Purpose**: Calculate exact pricing breakdown before payment initialization.

**Request**:
```json
{
    "plan_id": 1,
    "storefront_count": 5,
    "duration_months": 1
}
```

**Response** (Success):
```json
{
    "success": true,
    "data": {
        "plan": {
            "id": 1,
            "name": "Professional",
            "interval": "monthly"
        },
        "storefront_count": 5,
        "duration_months": 1,
        "pricing_breakdown": {
            "base_amount": "200.00",
            "additional_storefronts": 1,
            "additional_storefront_cost": "50.00",
            "subtotal": "250.00",
            "taxes": [
                {
                    "name": "VAT",
                    "rate": "15.00",
                    "amount": "37.50"
                },
                {
                    "name": "NHIL",
                    "rate": "2.50",
                    "amount": "6.25"
                },
                {
                    "name": "GETFund Levy",
                    "rate": "2.50",
                    "amount": "6.25"
                },
                {
                    "name": "COVID-19 Health Recovery Levy",
                    "rate": "1.00",
                    "amount": "2.50"
                }
            ],
            "total_tax": "52.50",
            "service_charges": [
                {
                    "name": "Paystack Transaction Fee",
                    "type": "percentage",
                    "rate": "1.95",
                    "amount": "5.90"
                }
            ],
            "total_service_charges": "5.90",
            "grand_total": "308.40"
        },
        "payment_gateway": "paystack",
        "currency": "GHS"
    }
}
```

**Response** (Error):
```json
{
    "success": false,
    "error": "Subscription plan not found"
}
```

**cURL Example**:
```bash
curl -X POST http://localhost:8000/api/subscriptions/pricing/calculate/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "plan_id": 1,
    "storefront_count": 5,
    "duration_months": 1
  }'
```

### 2. Pricing Tiers Management

**List Tiers**: `GET /api/subscriptions/pricing-tiers/`
```json
[
    {
        "id": 1,
        "name": "Starter",
        "min_storefronts": 1,
        "max_storefronts": 1,
        "base_price": "100.00",
        "price_per_additional_storefront": "0.00",
        "currency": "GHS",
        "is_active": true
    }
]
```

**Create Tier** (Admin only): `POST /api/subscriptions/pricing-tiers/`
```json
{
    "name": "Custom Tier",
    "min_storefronts": 10,
    "max_storefronts": 20,
    "base_price": "500.00",
    "price_per_additional_storefront": "30.00",
    "currency": "GHS"
}
```

**Calculate for Tier**: `GET /api/subscriptions/pricing-tiers/{id}/calculate/?storefronts=5`

### 3. Tax Configuration

**List Active Taxes**: `GET /api/subscriptions/tax-config/active/`
```json
[
    {
        "id": 1,
        "name": "VAT",
        "tax_type": "VAT",
        "rate": "15.00",
        "country": "GH",
        "is_active": true,
        "is_effective_now": true
    }
]
```

**Create Tax** (Admin only): `POST /api/subscriptions/tax-config/`

### 4. Service Charges

**List Charges**: `GET /api/subscriptions/service-charges/`

**Filter by Gateway**: `GET /api/subscriptions/service-charges/?payment_gateway=PAYSTACK`

### 5. Payment Statistics

**Overview**: `GET /api/subscriptions/payment-stats/overview/`
```json
{
    "total_revenue": "15000.00",
    "payment_count": {
        "total": 50,
        "completed": 45,
        "pending": 3,
        "failed": 2
    },
    "revenue_by_gateway": {
        "paystack": "15000.00"
    },
    "average_payment_amount": "300.00",
    "success_rate": 90.0
}
```

**Revenue Chart**: `GET /api/subscriptions/payment-stats/revenue-chart/?period=month`

### 6. Webhook Handler

**Endpoint**: `POST /api/subscriptions/webhooks/paystack/`

**Purpose**: Handle Paystack payment notifications.

**Headers**:
```
Content-Type: application/json
X-Paystack-Signature: <hmac-sha512-signature>
```

**Request** (sent by Paystack):
```json
{
    "event": "charge.success",
    "data": {
        "reference": "txn_1234567890",
        "amount": 30840,
        "status": "success",
        "metadata": {
            "app_name": "pos",
            "subscription_id": 123,
            "payment_id": 456,
            "plan_id": 1,
            "storefront_count": 5
        }
    }
}
```

**Response**:
```json
{
    "status": "success",
    "message": "Webhook processed successfully"
}
```

**Security**:
- HMAC-SHA512 signature validation using Paystack secret key
- App name filtering (only processes events with `app_name: 'pos'`)
- Transaction verification with Paystack API

---

## Payment Flow

### Complete End-to-End Flow

```
┌─────────────────────────────────────────────────────────────┐
│ STEP 1: User Selects Plan and Storefront Count              │
│ Frontend: User chooses plan and enters storefront count     │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 2: Calculate Pricing                                    │
│ POST /api/subscriptions/pricing/calculate/                   │
│ Backend calculates complete breakdown with taxes & charges   │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 3: Display Pricing to User                             │
│ Frontend shows complete breakdown (base, taxes, total)       │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 4: User Confirms Payment                                │
│ User clicks "Pay Now" button                                 │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 5: Initialize Payment                                   │
│ Backend:                                                      │
│ - Creates Subscription (status='pending_payment')            │
│ - Creates SubscriptionPayment (status='pending')             │
│ - Calls Paystack initialize_transaction()                    │
│ - Returns authorization_url to frontend                      │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 6: Redirect to Paystack                                │
│ window.location.href = authorization_url                     │
│ User completes payment on Paystack page                      │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 7: Paystack Webhook Notification                       │
│ POST /api/subscriptions/webhooks/paystack/                   │
│ Backend:                                                      │
│ - Validates HMAC signature                                    │
│ - Checks app_name == 'pos'                                   │
│ - Verifies payment with Paystack API                         │
│ - Updates subscription status → 'active'                     │
│ - Updates payment status → 'completed'                       │
│ - Records status history                                      │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 8: Paystack Redirects User                             │
│ Redirect to: {FRONTEND_URL}/subscription/success            │
│ Query params: ?reference=txn_xxx                             │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 9: Frontend Verifies Payment                           │
│ GET /api/subscriptions/payments/{payment_id}/                │
│ Confirms payment status is 'completed'                       │
└────────────────┬────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│ STEP 10: Display Success Message                            │
│ Frontend shows subscription details and receipt              │
└─────────────────────────────────────────────────────────────┘
```

### Backend Payment Initialization Code

```python
from subscriptions.payment_gateways import PaystackGateway
from subscriptions.models import Subscription, SubscriptionPayment
from django.conf import settings

def create_subscription_with_payment(user, plan, storefront_count):
    """
    Initialize payment for new subscription
    """
    # 1. Calculate pricing
    pricing = calculate_pricing(plan, storefront_count)
    
    # 2. Create subscription
    subscription = Subscription.objects.create(
        user=user,
        plan=plan,
        storefront_count=storefront_count,
        status='pending_payment'
    )
    
    # 3. Create payment record
    payment = SubscriptionPayment.objects.create(
        subscription=subscription,
        user=user,
        amount=pricing['grand_total'],
        base_amount=pricing['base_amount'],
        storefront_count=storefront_count,
        tax_breakdown=pricing['taxes'],
        total_tax_amount=pricing['total_tax'],
        service_charges_breakdown=pricing['service_charges'],
        total_service_charges=pricing['total_service_charges'],
        status='pending',
        gateway='paystack',
        currency='GHS'
    )
    
    # 4. Initialize Paystack transaction
    gateway = PaystackGateway()
    result = gateway.initialize_transaction(
        email=user.email,
        amount=payment.amount,
        metadata={
            'subscription_id': subscription.id,
            'payment_id': payment.id,
            'plan_id': plan.id,
            'storefront_count': storefront_count,
            'app_name': 'pos'  # CRITICAL for shared account
        }
    )
    
    # 5. Update payment with transaction reference
    payment.transaction_reference = result['reference']
    payment.save()
    
    return {
        'subscription': subscription,
        'payment': payment,
        'authorization_url': result['authorization_url']
    }
```

### Frontend Integration Example

```javascript
// Step 1: Calculate pricing
async function calculatePricing(planId, storefrontCount) {
    const response = await fetch('/api/subscriptions/pricing/calculate/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${accessToken}`
        },
        body: JSON.stringify({
            plan_id: planId,
            storefront_count: storefrontCount,
            duration_months: 1
        })
    });
    
    return await response.json();
}

// Step 2: Display pricing to user
function displayPricing(data) {
    const breakdown = data.pricing_breakdown;
    
    document.getElementById('base-amount').textContent = 
        `${breakdown.base_amount} ${data.currency}`;
    
    document.getElementById('taxes').textContent = 
        `${breakdown.total_tax} ${data.currency}`;
    
    document.getElementById('total').textContent = 
        `${breakdown.grand_total} ${data.currency}`;
}

// Step 3: Initialize payment
async function initializePayment(planId, storefrontCount) {
    const response = await fetch('/api/subscriptions/subscriptions/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${accessToken}`
        },
        body: JSON.stringify({
            plan: planId,
            storefront_count: storefrontCount
        })
    });
    
    const result = await response.json();
    
    if (result.authorization_url) {
        // Redirect to Paystack
        window.location.href = result.authorization_url;
    }
}

// Step 4: Handle payment callback
function handlePaymentCallback() {
    const urlParams = new URLSearchParams(window.location.search);
    const reference = urlParams.get('reference');
    
    if (reference) {
        // Verify payment status
        verifyPayment(reference);
    }
}
```

---

## Paystack Integration

### Configuration

#### Test Environment

```bash
# .env.development
PAYSTACK_SECRET_KEY=sk_test_16b164b455153a23804423ec0198476b3c4ca206
PAYSTACK_PUBLIC_KEY=pk_test_5309f5af38555dbf7ef47287822ef2c6d3019b9d
PAYSTACK_APP_NAME=pos
```

#### Production Environment

```bash
# .env.production
PAYSTACK_SECRET_KEY=sk_live_your_live_secret_key
PAYSTACK_PUBLIC_KEY=pk_live_your_live_public_key
PAYSTACK_APP_NAME=pos
```

### PaystackGateway Class

**Location**: `subscriptions/payment_gateways.py`

**Methods**:

#### initialize_transaction()

```python
gateway = PaystackGateway()
result = gateway.initialize_transaction(
    email='user@example.com',
    amount=Decimal('308.40'),
    metadata={
        'app_name': 'pos',  # REQUIRED
        'subscription_id': 123,
        'payment_id': 456
    }
)

# Returns:
{
    'authorization_url': 'https://checkout.paystack.com/xxx',
    'access_code': 'xxx',
    'reference': 'txn_xxx'
}
```

#### verify_transaction()

```python
gateway = PaystackGateway()
result = gateway.verify_transaction(reference='txn_xxx')

# Returns:
{
    'status': 'success',
    'amount': 30840,  # In kobo (GHS 308.40)
    'metadata': {...}
}
```

### Webhook Configuration

#### Paystack Dashboard Setup

1. Login to: https://dashboard.paystack.com
2. Navigate to: **Settings → Webhooks**
3. Add Webhook URL: `https://your-domain.com/api/subscriptions/webhooks/paystack/`
4. Select Events:
   - ✓ `charge.success`
   - ✓ `charge.failed` (optional)

#### Webhook Security

The webhook handler implements three layers of security:

**1. Signature Validation**:
```python
import hmac
import hashlib

def verify_signature(request_body, signature):
    secret = settings.PAYSTACK_SECRET_KEY.encode('utf-8')
    hash_value = hmac.new(secret, request_body, hashlib.sha512).hexdigest()
    return hash_value == signature
```

**2. App Name Routing**:
```python
app_name = metadata.get('app_name')
if app_name != settings.PAYSTACK_APP_NAME:
    return JsonResponse({'status': 'ignored'})
```

**3. Payment Verification**:
```python
gateway = PaystackGateway()
verification = gateway.verify_transaction(reference)
if verification['status'] != 'success':
    return JsonResponse({'status': 'failed'})
```

#### Testing Webhooks Locally

Use **ngrok** for local webhook testing:

```bash
# Install ngrok
npm install -g ngrok

# Start ngrok tunnel
ngrok http 8000

# Copy HTTPS URL (e.g., https://abc123.ngrok.io)
# Add to Paystack: https://abc123.ngrok.io/api/subscriptions/webhooks/paystack/
```

### Test Cards

Use these cards for testing payments:

#### Successful Payment
```
Card Number: 4084084084084081
CVV: 408
Expiry: Any future date
PIN: 0000
OTP: 123456
```

#### Failed Payment (Insufficient Funds)
```
Card Number: 5060666666666666666
CVV: 123
Expiry: Any future date
```

More test cards: https://paystack.com/docs/payments/test-payments

---

## Testing Guide

### Unit Tests

Run all subscription tests:

```bash
source venv/bin/activate
python manage.py test subscriptions
```

Run specific test file:

```bash
python manage.py test subscriptions.tests.test_pricing
python manage.py test subscriptions.tests.test_api
```

### API Testing with cURL

#### 1. Test Pricing Calculation

```bash
curl -X POST http://localhost:8000/api/subscriptions/pricing/calculate/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "plan_id": 1,
    "storefront_count": 5,
    "duration_months": 1
  }'
```

#### 2. Test Pricing Tiers

```bash
# List all tiers
curl http://localhost:8000/api/subscriptions/pricing-tiers/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# Get specific tier
curl http://localhost:8000/api/subscriptions/pricing-tiers/1/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### 3. Test Tax Configuration

```bash
# Get active taxes
curl http://localhost:8000/api/subscriptions/tax-config/active/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### 4. Test Payment Stats

```bash
# Get overview
curl http://localhost:8000/api/subscriptions/payment-stats/overview/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# Get revenue chart
curl "http://localhost:8000/api/subscriptions/payment-stats/revenue-chart/?period=month" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Testing Paystack Integration

#### Test in Django Shell

```bash
source venv/bin/activate
python manage.py shell
```

```python
from subscriptions.payment_gateways import PaystackGateway
from accounts.models import User

# Get a user
user = User.objects.first()

# Initialize payment
gateway = PaystackGateway()
result = gateway.initialize_transaction(
    email=user.email,
    amount=100.00,
    metadata={
        'app_name': 'pos',
        'test': True
    }
)

print(result['authorization_url'])
# Visit this URL and use test card
```

#### Test Webhook Handler

```bash
# Create test payload
cat > webhook_test.json << EOF
{
  "event": "charge.success",
  "data": {
    "reference": "test_txn_123",
    "amount": 30840,
    "status": "success",
    "metadata": {
      "app_name": "pos",
      "subscription_id": 1
    }
  }
}
EOF

# Generate signature
python -c "
import hmac
import hashlib

secret = 'sk_test_16b164b455153a23804423ec0198476b3c4ca206'
with open('webhook_test.json', 'rb') as f:
    payload = f.read()
    
signature = hmac.new(
    secret.encode('utf-8'),
    payload,
    hashlib.sha512
).hexdigest()

print(signature)
"

# Test webhook
curl -X POST http://localhost:8000/api/subscriptions/webhooks/paystack/ \
  -H "Content-Type: application/json" \
  -H "X-Paystack-Signature: <SIGNATURE_FROM_ABOVE>" \
  -d @webhook_test.json
```

### Manual Testing Checklist

- [ ] Calculate pricing for 1 storefront
- [ ] Calculate pricing for 5 storefronts
- [ ] Calculate pricing for 10 storefronts
- [ ] Verify tax calculations are correct
- [ ] Verify service charges are applied
- [ ] Initialize Paystack transaction
- [ ] Complete payment with test card
- [ ] Verify webhook is received
- [ ] Verify subscription is activated
- [ ] Check payment status in admin
- [ ] Verify status history is recorded

---

## Deployment

### Pre-Deployment Checklist

#### Database
- [ ] Run migrations: `python manage.py migrate`
- [ ] Setup default pricing: `python manage.py setup_default_pricing`
- [ ] Create superuser: `python manage.py createsuperuser`
- [ ] Backup database

#### Environment
- [ ] Copy `.env.production.example` to `.env.production`
- [ ] Set Paystack **LIVE** keys
- [ ] Update `FRONTEND_URL` to production domain
- [ ] Set `DEBUG=false`
- [ ] Update `ALLOWED_HOSTS`
- [ ] Set secure `SECRET_KEY`
- [ ] Configure production database credentials

#### Security
- [ ] Restrict `.env.production` permissions: `chmod 600 .env.production`
- [ ] Enable HTTPS/SSL
- [ ] Configure CORS settings
- [ ] Set up firewall rules

### Production Setup

#### 1. Environment Variables

```bash
# .env.production
DJANGO_ENV_FILE=.env.production

# Paystack LIVE Keys
PAYSTACK_SECRET_KEY=sk_live_your_actual_live_key
PAYSTACK_PUBLIC_KEY=pk_live_your_actual_live_key
PAYSTACK_APP_NAME=pos

# Production Settings
DEBUG=false
ALLOWED_HOSTS=posbackend.alphalogiquetechnologies.com
FRONTEND_URL=https://pos.alphalogiquetechnologies.com

# Security
SECURE_SSL_REDIRECT=true
SESSION_COOKIE_SECURE=true
CSRF_COOKIE_SECURE=true
```

#### 2. Configure Paystack Webhook

1. Login to Paystack: https://dashboard.paystack.com
2. Switch to **Live** mode
3. Navigate to: Settings → Webhooks
4. Add webhook URL: `https://posbackend.alphalogiquetechnologies.com/api/subscriptions/webhooks/paystack/`
5. Select events: `charge.success`

#### 3. Collect Static Files

```bash
source venv/bin/activate
python manage.py collectstatic --noinput
```

#### 4. Start Services

```bash
# Using Gunicorn
gunicorn app.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 4 \
  --timeout 120

# Using systemd (recommended)
sudo systemctl start gunicorn
sudo systemctl enable gunicorn
```

### Post-Deployment Verification

#### 1. Verify Configuration

```bash
source venv/bin/activate
python manage.py shell
```

```python
from django.conf import settings

# Verify live keys are loaded
print(f"Secret Key: {settings.PAYSTACK_SECRET_KEY[:8]}... (live)")
print(f"Public Key: {settings.PAYSTACK_PUBLIC_KEY[:8]}... (live)")
print(f"Debug: {settings.DEBUG}")  # Should be False
```

#### 2. Test Endpoints

```bash
# Test pricing calculation
curl https://posbackend.alphalogiquetechnologies.com/api/subscriptions/pricing/calculate/ \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"plan_id": 1, "storefront_count": 3, "duration_months": 1}'
```

#### 3. Test Live Payment

- Use a real card with small amount
- Verify webhook is received
- Check subscription is activated
- Verify email notifications

#### 4. Monitor Logs

```bash
# Django logs
tail -f /path/to/logs/django.log

# Gunicorn logs
tail -f /path/to/logs/gunicorn.log

# Nginx logs
tail -f /var/log/nginx/pos_backend.access.log
tail -f /var/log/nginx/pos_backend.error.log
```

### Monitoring & Alerts

#### Key Metrics to Monitor

1. **Payment Success Rate**: Track successful vs failed payments
2. **Webhook Response Time**: Monitor webhook processing speed
3. **API Response Times**: Track pricing calculation latency
4. **Error Rates**: Monitor 4xx and 5xx errors
5. **Database Performance**: Query execution times

#### Set Up Alerts

- Payment failures > 5%
- Webhook processing > 5 seconds
- API errors > 1% of requests
- Database connection errors

---

## Troubleshooting

### Common Issues

#### 1. "PAYSTACK_SECRET_KEY not found"

**Cause**: Environment variable not set

**Solution**:
```bash
# Check environment file
cat .env.development | grep PAYSTACK

# Ensure variable is set
PAYSTACK_SECRET_KEY=sk_test_...

# Restart Django
source venv/bin/activate
python manage.py runserver
```

#### 2. "Subscription plan not found"

**Cause**: Default pricing not setup

**Solution**:
```bash
source venv/bin/activate
python manage.py setup_default_pricing
```

#### 3. Webhook Signature Validation Failing

**Cause**: Wrong secret key or request body modified

**Solution**:
1. Verify `PAYSTACK_SECRET_KEY` matches Paystack dashboard
2. Ensure using correct environment (test vs live)
3. Check webhook payload is raw JSON (not parsed)
4. View Paystack webhook logs for signature details

#### 4. Pricing Calculation Returns 0

**Cause**: No pricing tier found for storefront count

**Solution**:
```bash
# Check pricing tiers
source venv/bin/activate
python manage.py shell
```

```python
from subscriptions.models import SubscriptionPricingTier

# List all tiers
for tier in SubscriptionPricingTier.objects.filter(is_active=True):
    print(f"{tier.name}: {tier.min_storefronts}-{tier.max_storefronts}")
```

#### 5. Payment Not Working in Production

**Checklist**:
- [ ] Using live keys (`sk_live_...`, `pk_live_...`)
- [ ] Webhook URL configured in Paystack dashboard
- [ ] Webhook URL is accessible via HTTPS
- [ ] `PAYSTACK_APP_NAME` matches metadata
- [ ] Frontend has correct public key
- [ ] SSL certificate is valid

#### 6. Webhook Not Receiving Events

**Debugging**:

1. Check Paystack dashboard webhook logs
2. Verify webhook URL is accessible:
   ```bash
   curl -X POST https://your-domain.com/api/subscriptions/webhooks/paystack/ \
     -H "Content-Type: application/json" \
     -d '{"test": true}'
   ```
3. Check firewall/security groups
4. Verify HTTPS is enabled
5. Check Django logs for webhook requests

#### 7. Database Migration Errors

**Solution**:
```bash
# Reset migrations (development only)
python manage.py migrate subscriptions zero
python manage.py migrate subscriptions

# Create fresh migrations
rm subscriptions/migrations/0002_*.py
python manage.py makemigrations subscriptions
python manage.py migrate
```

### Debug Mode

Enable detailed error messages:

```python
# In Django shell
import logging
logging.basicConfig(level=logging.DEBUG)

# Test payment initialization
from subscriptions.payment_gateways import PaystackGateway
gateway = PaystackGateway()
# ... test operations
```

### Getting Help

1. **Check Logs**: `tail -f logs/django.log`
2. **Django Shell**: Test components interactively
3. **Paystack Dashboard**: View transaction history and webhook logs
4. **Paystack Support**: support@paystack.com
5. **Paystack Docs**: https://paystack.com/docs

---

## API Reference

### Quick Reference Table

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/subscriptions/pricing/calculate/` | POST | Yes | Calculate pricing breakdown |
| `/api/subscriptions/pricing-tiers/` | GET | Yes | List pricing tiers |
| `/api/subscriptions/pricing-tiers/` | POST | Admin | Create pricing tier |
| `/api/subscriptions/pricing-tiers/{id}/` | GET | Yes | Get tier details |
| `/api/subscriptions/pricing-tiers/{id}/calculate/` | GET | Yes | Calculate pricing for tier |
| `/api/subscriptions/tax-config/` | GET | Yes | List tax configurations |
| `/api/subscriptions/tax-config/active/` | GET | Yes | Get active taxes |
| `/api/subscriptions/service-charges/` | GET | Yes | List service charges |
| `/api/subscriptions/payment-stats/overview/` | GET | Admin | Payment statistics |
| `/api/subscriptions/payment-stats/revenue-chart/` | GET | Admin | Revenue chart data |
| `/api/subscriptions/webhooks/paystack/` | POST | No | Paystack webhook handler |

### Response Status Codes

- `200 OK` - Request successful
- `201 Created` - Resource created successfully
- `400 Bad Request` - Invalid request data
- `401 Unauthorized` - Authentication required
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource not found
- `500 Internal Server Error` - Server error

### Error Response Format

```json
{
    "success": false,
    "error": "Error message description",
    "details": {
        "field_name": ["Field-specific error"]
    }
}
```

---

## Appendix

### Ghana Tax Rates (2025)

| Tax | Rate | Description |
|-----|------|-------------|
| VAT | 15.00% | Value Added Tax |
| NHIL | 2.50% | National Health Insurance Levy |
| GETFund | 2.50% | Ghana Education Trust Fund |
| COVID-19 Levy | 1.00% | COVID-19 Health Recovery Levy |
| **Total** | **21.00%** | Combined tax rate |

### Default Pricing Tiers

| Tier | Storefronts | Base Price | Extra Storefront |
|------|-------------|------------|------------------|
| Starter | 1 | GHS 100.00 | N/A |
| Growth | 2 | GHS 150.00 | N/A |
| Professional | 3 | GHS 180.00 | N/A |
| Business | 4 | GHS 200.00 | N/A |
| Enterprise | 5+ | GHS 200.00 | GHS 50.00/each |

### Service Charges

| Gateway | Type | Rate | Description |
|---------|------|------|-------------|
| Paystack | Percentage | 1.95% | Transaction fee |

### File Structure

```
subscriptions/
├── models.py                      # Database models
├── serializers.py                 # DRF serializers
├── views.py                       # API views and endpoints
├── urls.py                        # URL routing
├── permissions.py                 # Custom permissions
├── payment_gateways.py           # Paystack integration
├── admin.py                       # Django admin config
├── management/
│   └── commands/
│       └── setup_default_pricing.py  # Setup command
├── tests/
│   ├── test_pricing.py           # Unit tests
│   └── test_api.py               # API tests
└── migrations/
    └── 0002_subscription_payment_...  # Latest migration
```

### Environment Variables Reference

```bash
# Required
PAYSTACK_SECRET_KEY=sk_test_... or sk_live_...
PAYSTACK_PUBLIC_KEY=pk_test_... or pk_live_...
PAYSTACK_APP_NAME=pos

# Django
SECRET_KEY=your-secret-key
DEBUG=true or false
ALLOWED_HOSTS=localhost,127.0.0.1,...

# Database
DB_NAME=pos_db
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432

# Frontend
FRONTEND_URL=http://localhost:5173
CORS_ALLOWED_ORIGINS=http://localhost:5173,...

# Optional
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
CELERY_BROKER_URL=redis://localhost:6379/0
```

### Support Resources

- **Paystack Dashboard**: https://dashboard.paystack.com
- **Paystack Documentation**: https://paystack.com/docs
- **Paystack Support**: support@paystack.com
- **Django Documentation**: https://docs.djangoproject.com
- **DRF Documentation**: https://www.django-rest-framework.org

---

**Document Version**: 1.0  
**Last Updated**: November 2, 2025  
**Maintained By**: POS Development Team  
**Status**: Production Ready ✅
