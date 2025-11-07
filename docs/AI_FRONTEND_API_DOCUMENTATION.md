# AI Features API Documentation for Frontend Team

**Backend Implementation Complete** ✅  
**Date:** November 7, 2025  
**Django Backend Developer:** Senior Developer  
**For:** Frontend/React Development Team

---

## 📋 Overview

The AI features backend has been successfully integrated into your POS system. This document provides all the information needed to integrate these AI features into your React frontend application.

**Base URL:** `https://your-domain.com/ai/`

All endpoints require authentication via token in the header:
```
Authorization: Token YOUR_AUTH_TOKEN_HERE
```

---

## 🔐 Authentication

All AI endpoints use the same authentication as your existing POS endpoints:

```javascript
const headers = {
  'Authorization': `Token ${userToken}`,
  'Content-Type': 'application/json'
};
```

---

## 💰 AI Credit Management Endpoints

### 1. Get Credit Balance

**Endpoint:** `GET /ai/api/credits/balance/`

**Description:** Get the current AI credit balance for the authenticated user's business.

**Request:**
```javascript
fetch('https://your-domain.com/ai/api/credits/balance/', {
  method: 'GET',
  headers: {
    'Authorization': `Token ${userToken}`,
  }
})
```

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "business": "uuid",
  "balance": 45.50,
  "purchased_at": "2025-11-07T10:00:00Z",
  "updated_at": "2025-11-07T15:30:00Z",
  "expires_at": "2026-05-07T10:00:00Z",
  "is_active": true,
  "is_expired": false,
  "days_until_expiry": 180
}
```

**Response when no credits:** `200 OK`
```json
{
  "balance": 0.00,
  "message": "No active AI credits. Purchase credits to get started."
}
```

---

### 2. Purchase AI Credits

**Endpoint:** `POST /ai/api/credits/purchase/`

**Description:** Initialize Paystack payment for AI credit purchase. Returns a Paystack checkout URL to redirect the user to.

**⚠️ IMPORTANT:** This endpoint now uses **Paystack** for payment processing. You must redirect the user to the returned `authorization_url` to complete payment.

**Credit Packages:**
- **Starter:** GHS 30 = 30 credits (no bonus)
- **Value:** GHS 80 = 100 credits (20 credits bonus = 25% extra)
- **Premium:** GHS 180 = 250 credits (70 credits bonus = 39% extra)
- **Custom:** Pay any amount, get 1:1 credits

**Request:**
```javascript
const purchaseData = {
  package: "value",  // "starter" | "value" | "premium" | "custom"
  payment_method: "mobile_money"  // "mobile_money" | "card"
};

// For custom package
const customPurchaseData = {
  package: "custom",
  custom_amount: 50.00,  // Required for custom
  payment_method: "mobile_money"
};

fetch('https://your-domain.com/ai/api/credits/purchase/', {
  method: 'POST',
  headers: {
    'Authorization': `Token ${userToken}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify(purchaseData)
})
```

**Response:** `200 OK` (Paystack Integration)
```json
{
  "authorization_url": "https://checkout.paystack.com/xxxxxxx",
  "access_code": "xxxxxxx",
  "reference": "AI-CREDIT-1699357200-abc123",
  "amount": 80.00,
  "credits_to_add": 100.0
}
```

**What Frontend Should Do:**
1. Receive the `authorization_url`
2. Redirect user to this URL: `window.location.href = data.authorization_url`
3. User completes payment on Paystack
4. Paystack redirects back to your callback URL
5. Verify payment with `/ai/api/credits/verify/?reference=xxx`

---

### 3. Verify Payment

**Endpoint:** `GET /ai/api/credits/verify/?reference=AI-CREDIT-xxx`

**Description:** Verify Paystack payment and credit the account. This endpoint is called after user completes payment on Paystack.

**When to Use:**
- After Paystack redirects back to your app
- To check payment status manually
- In your payment callback page

**Request:**
```javascript
const urlParams = new URLSearchParams(window.location.search);
const reference = urlParams.get('reference');

fetch(`https://your-domain.com/ai/api/credits/verify/?reference=${reference}`, {
  method: 'GET',
  headers: {
    'Authorization': `Token ${userToken}`,
  }
})
```

**Response - Success:** `200 OK`
```json
{
  "status": "success",
  "message": "Payment verified and credits added successfully",
  "reference": "AI-CREDIT-1699357200-abc123",
  "credits_added": 100.0,
  "new_balance": 145.5
}
```

**Response - Already Processed:** `200 OK`
```json
{
  "status": "success",
  "message": "Payment already processed",
  "reference": "AI-CREDIT-1699357200-abc123",
  "credits_added": 100.0,
  "current_balance": 145.5
}
```

**Response - Payment Failed:** `400 Bad Request`
```json
{
  "status": "failed",
  "message": "Payment was not successful",
  "reference": "AI-CREDIT-1699357200-abc123"
}
```

**Response - Invalid Reference:** `404 Not Found`
```json
{
  "error": "Purchase record not found"
}
```

---

### 4. Get Usage Statistics

**Endpoint:** `GET /ai/api/usage/stats/?days=30`

**Description:** Get AI usage statistics for the business.

**Query Parameters:**
- `days` (optional, default=30): Number of days to look back

**Request:**
```javascript
fetch('https://your-domain.com/ai/api/usage/stats/?days=30', {
  method: 'GET',
  headers: {
    'Authorization': `Token ${userToken}`,
  }
})
```

**Response:** `200 OK`
```json
{
  "period_days": 30,
  "current_balance": 45.50,
  "total_requests": 150,
  "successful_requests": 148,
  "failed_requests": 2,
  "total_credits_used": 75.20,
  "total_cost_ghs": 25.40,
  "avg_processing_time_ms": 850,
  "feature_breakdown": [
    {
      "feature": "natural_language_query",
      "count": 80,
      "credits_used": 40.00
    },
    {
      "feature": "product_description",
      "count": 50,
      "credits_used": 5.00
    },
    {
      "feature": "collection_message",
      "count": 18,
      "credits_used": 9.00
    }
  ]
}
```

---

### 5. Get Transaction History

**Endpoint:** `GET /ai/api/transactions/?limit=50&feature=natural_language_query`

**Description:** Get AI transaction history with optional filtering.

**Query Parameters:**
- `limit` (optional, default=50): Max number of records
- `feature` (optional): Filter by specific feature

**Request:**
```javascript
fetch('https://your-domain.com/ai/api/transactions/?limit=20', {
  method: 'GET',
  headers: {
    'Authorization': `Token ${userToken}`,
  }
})
```

**Response:** `200 OK`
```json
{
  "count": 150,
  "results": [
    {
      "id": "uuid",
      "business": "uuid",
      "user": "uuid",
      "feature": "natural_language_query",
      "feature_display": "Natural Language Query",
      "credits_used": 0.50,
      "cost_to_us": 0.008,
      "tokens_used": 523,
      "timestamp": "2025-11-07T15:45:00Z",
      "success": true,
      "error_message": "",
      "processing_time_ms": 1250
    }
  ]
}
```

---

### 6. Check Feature Availability

**Endpoint:** `GET /ai/api/check-availability/?feature=natural_language_query`

**Description:** Check if user has enough credits for a specific feature before making the request.

**Query Parameters:**
- `feature` (required): Feature name to check

**Feature Names:**
- `natural_language_query` (0.5 credits)
- `product_description` (0.1 credits)
- `collection_message` (0.5 credits)
- `credit_assessment` (3.0 credits)
- `collection_priority` (5.0 credits)
- `portfolio_dashboard` (5.0 credits)
- `payment_prediction` (1.0 credits)
- `inventory_forecast` (4.0 credits)
- `report_narrative` (0.2 credits)

**Request:**
```javascript
fetch('https://your-domain.com/ai/api/check-availability/?feature=natural_language_query', {
  method: 'GET',
  headers: {
    'Authorization': `Token ${userToken}`,
  }
})
```

**Response:** `200 OK`
```json
{
  "available": true,
  "feature": "natural_language_query",
  "cost": 0.50,
  "current_balance": 45.50,
  "shortage": 0.0
}
```

**When insufficient credits:**
```json
{
  "available": false,
  "feature": "credit_assessment",
  "cost": 3.00,
  "current_balance": 2.50,
  "shortage": 0.50
}
```

---

## 🤖 Natural Language Query Endpoint

### Process Natural Language Query

**Endpoint:** `POST /ai/api/query/`

**Description:** Ask questions about your business data in plain English. **This is what answers questions like "How many Samsung TVs were sold between January and March?"**

**Cost:** 0.5 credits per query

**Request:**
```javascript
const queryData = {
  query: "How many Samsung TVs were sold between January and March?",
  storefront_id: "uuid"  // Optional: Filter to specific storefront
};

fetch('https://your-domain.com/ai/api/query/', {
  method: 'POST',
  headers: {
    'Authorization': `Token ${userToken}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify(queryData)
})
```

**Example Queries:**
- "How many Samsung TVs were sold between January and March?"
- "What were my total sales this month?"
- "Which product is my top seller?"
- "Show me customers who haven't bought in 90 days"
- "What products are out of stock?"
- "What's my profit this month?"

**Response:** `200 OK`
```json
{
  "answer": "Based on your sales data, 127 Samsung TVs were sold between January and March 2025, generating GHS 152,400 in revenue. This represents 23% of your total electronics sales for that period.\n\nKey insights:\n• January: 45 units (GHS 54,000)\n• February: 42 units (GHS 50,400)\n• March: 40 units (GHS 48,000)\n• Average price per unit: GHS 1,200\n• Sales trend: Declining slightly month-over-month",
  
  "query_type": "product",
  
  "data": {
    "products": [
      {
        "product__id": "uuid",
        "product__name": "Samsung 55\" QLED TV",
        "product__sku": "SAM-TV-55-001",
        "total_quantity": 127,
        "total_revenue": 152400.00,
        "transaction_count": 115
      }
    ],
    "total_products": 1
  },
  
  "follow_up_questions": [
    "Which products have the highest profit margins?",
    "Show me slow-moving products",
    "What products need restocking?"
  ],
  
  "visualization_hints": {
    "type": "bar_chart",
    "x_axis": "product_name",
    "y_axis": "total_quantity",
    "title": "Product Sales Comparison"
  },
  
  "credits_used": 0.50,
  "new_balance": 45.00,
  "processing_time_ms": 1250
}
```

**Error - Insufficient Credits:** `402 Payment Required`
```json
{
  "error": "insufficient_credits",
  "message": "You need 0.5 credits for this query. Purchase more to continue.",
  "current_balance": 0.20,
  "required_credits": 0.50
}
```

**Error - Processing Failed:** `500 Internal Server Error`
```json
{
  "error": "processing_failed",
  "message": "Error details here"
}
```

---

## 📝 Product Description Generator

### Generate Product Description

**Endpoint:** `POST /ai/api/products/generate-description/`

**Description:** Generate AI-powered product descriptions for e-commerce/catalog.

**Cost:** 0.1 credits per generation

**Request:**
```javascript
const descriptionData = {
  product_id: "uuid",
  tone: "professional",  // "professional" | "casual" | "technical" | "marketing"
  language: "en",  // "en" | "tw"
  include_seo: true
};

fetch('https://your-domain.com/ai/api/products/generate-description/', {
  method: 'POST',
  headers: {
    'Authorization': `Token ${userToken}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify(descriptionData)
})
```

**Response:** `200 OK`
```json
{
  "description": "Experience cinema-quality entertainment with this Samsung 55\" QLED TV. Featuring Quantum Dot technology, this television delivers stunning picture quality with over a billion shades of vibrant, accurate color. The 4K resolution ensures every detail is crystal clear, while the intelligent processor optimizes content in real-time.\n\nDesigned for modern living spaces, the sleek, minimalist design complements any room décor. Smart TV capabilities provide easy access to your favorite streaming services, and built-in voice control makes finding content effortless. Whether you're watching movies, sports, or gaming, this QLED TV transforms your entertainment experience.",
  
  "short_description": "Samsung 55\" QLED TV with stunning 4K picture quality and smart features",
  
  "seo_keywords": [
    "samsung tv",
    "qled television",
    "55 inch tv",
    "4k television",
    "smart tv",
    "quantum dot tv",
    "samsung qled"
  ],
  
  "meta_description": "Shop Samsung 55\" QLED TV - Crystal clear 4K picture, Quantum Dot technology, smart features. Experience cinema-quality entertainment at home.",
  
  "credits_used": 0.10,
  "new_balance": 44.90
}
```

**Error - Product Not Found:** `404 Not Found`
```json
{
  "error": "Product not found"
}
```

---

## 💼 Smart Collections Endpoints

### 1. Generate Collection Message

**Endpoint:** `POST /ai/api/collections/message/`

**Description:** Generate personalized, culturally-appropriate collection messages for customers with outstanding balances.

**Cost:** 0.5 credits per message

**Request:**
```javascript
const messageData = {
  customer_id: "uuid",
  message_type: "first_reminder",  // "first_reminder" | "second_reminder" | "final_notice" | "payment_plan_offer"
  tone: "professional_friendly",  // "professional_friendly" | "firm" | "formal_legal"
  language: "en",  // "en" | "tw"
  include_payment_plan: false
};

fetch('https://your-domain.com/ai/api/collections/message/', {
  method: 'POST',
  headers: {
    'Authorization': `Token ${userToken}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify(messageData)
})
```

**Response:** `200 OK`
```json
{
  "subject": "Friendly Reminder: Outstanding Balance - Invoice #INV-2024-1234",
  
  "body": "Dear Mr. Mensah,\n\nI hope this message finds you well and business is thriving.\n\nThis is a gentle reminder regarding your outstanding balance of GHS 15,000.00. We value our business relationship and want to ensure everything is going smoothly on your end.\n\nOutstanding invoices:\n• Invoice #INV-2024-1234 - GHS 10,000.00 (Due: Oct 15, 2024)\n• Invoice #INV-2024-1256 - GHS 5,000.00 (Due: Oct 30, 2024)\n\nIf you've already made payment, please disregard this message. If you're experiencing any challenges, I'd be happy to discuss a payment plan that works for you.\n\nPlease feel free to contact us to discuss this matter.\n\nBest regards,\n[Your Business Name]",
  
  "sms_version": "Dear Mr. Mensah, gentle reminder that invoice INV-2024-1234 (GHS 15,000) is overdue. Please contact us to arrange payment or discuss a plan. Thank you.",
  
  "whatsapp_version": "Hello Mr. Mensah 👋\n\nJust a friendly reminder about your outstanding balance of GHS 15,000.00 📋\n\nWe value our partnership and want to help if there are any issues. Can we arrange payment or would a payment plan work better?\n\nLet's chat! 📞",
  
  "credits_used": 0.50,
  "new_balance": 44.40
}
```

**Error - Customer Not Found:** `404 Not Found`
```json
{
  "error": "Customer not found"
}
```

---

### 2. Credit Risk Assessment

**Endpoint:** `POST /ai/api/credit/assess/`

**Description:** AI-powered credit risk assessment for approving or adjusting customer credit limits.

**Cost:** 3.0 credits per assessment

**Request:**
```javascript
const assessmentData = {
  customer_id: "uuid",
  requested_credit_limit: 5000.00,
  assessment_type: "new_credit"  // "new_credit" | "increase" | "renewal"
};

fetch('https://your-domain.com/ai/api/credit/assess/', {
  method: 'POST',
  headers: {
    'Authorization': `Token ${userToken}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify(assessmentData)
})
```

**Response:** `200 OK`
```json
{
  "customer": {
    "id": "uuid",
    "name": "ABC Wholesale",
    "current_limit": 0.00,
    "requested_limit": 5000.00
  },
  
  "risk_score": 72,
  "risk_level": "MEDIUM",
  
  "recommendation": {
    "action": "APPROVE_PARTIAL",
    "suggested_limit": 3000.00,
    "suggested_terms_days": 30,
    "confidence": 0.78
  },
  
  "analysis": {
    "positive_factors": [
      "Perfect payment history over 6 months",
      "Purchase frequency is consistent (weekly)",
      "Average order value stable at GHS 1,200",
      "No overdue payments in history"
    ],
    "risk_factors": [
      "Only 6 months of history (prefer 12+ months)",
      "Requested limit is 3x average monthly purchases",
      "No previous credit history"
    ],
    "comparable_customers": {
      "similar_approved_limit_avg": 3500.00,
      "default_rate_for_similar_profile": "8%"
    }
  },
  
  "conditions": [
    "Start with GHS 3,000 limit",
    "Review after 3 months of good payment",
    "Require monthly statements",
    "Personal guarantee recommended"
  ],
  
  "explanation": "Based on ABC Wholesale's solid 6-month track record of consistent purchases and perfect payment history, they demonstrate good credit discipline. However, the limited history and high requested limit relative to their purchase patterns suggest starting with a conservative GHS 3,000 limit. This allows them to prove their ability to manage larger credit while minimizing your risk. After 3 months of on-time payments, consider increasing to their requested amount.",
  
  "credits_used": 3.00,
  "new_balance": 41.40
}
```

**Possible Actions:**
- `APPROVE_FULL`: Approve full requested amount
- `APPROVE_PARTIAL`: Approve reduced amount
- `DENY`: Deny credit request
- `REQUIRE_MORE_INFO`: Need additional information

**Possible Risk Levels:**
- `LOW`: Safe to approve
- `MEDIUM`: Approve with caution
- `HIGH`: High risk, careful consideration needed
- `CRITICAL`: Very high risk, likely deny

---

## 🎨 React Component Examples

### Natural Language Query Component

```jsx
import React, { useState } from 'react';

const AIQueryBox = () => {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [balance, setBalance] = useState(null);

  const handleQuery = async () => {
    setLoading(true);
    
    try {
      const response = await fetch('https://your-domain.com/ai/api/query/', {
        method: 'POST',
        headers: {
          'Authorization': `Token ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query })
      });
      
      if (response.status === 402) {
        const error = await response.json();
        alert(`Insufficient credits: ${error.message}`);
        return;
      }
      
      const data = await response.json();
      setResult(data);
      setBalance(data.new_balance);
    } catch (error) {
      console.error('Query failed:', error);
      alert('Query failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="ai-query-box">
      <div className="query-header">
        <h3>🤖 Ask About Your Business</h3>
        {balance !== null && (
          <span className="credit-balance">
            Credits: {balance.toFixed(2)}
          </span>
        )}
      </div>
      
      <div className="query-input-section">
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask a question... (e.g., 'How many Samsung TVs were sold in January?')"
          rows={3}
        />
        
        <button 
          onClick={handleQuery} 
          disabled={loading || !query.trim()}
        >
          {loading ? 'Thinking...' : 'Ask (0.5 credits)'}
        </button>
      </div>
      
      {result && (
        <div className="query-result">
          <div className="answer">
            <h4>✅ Answer</h4>
            <p style={{ whiteSpace: 'pre-wrap' }}>{result.answer}</p>
          </div>
          
          {result.follow_up_questions && (
            <div className="follow-up-questions">
              <h5>❓ You might also want to ask:</h5>
              <div className="follow-up-buttons">
                {result.follow_up_questions.map((q, i) => (
                  <button 
                    key={i}
                    onClick={() => setQuery(q)}
                    className="follow-up-btn"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}
          
          <div className="query-meta">
            <small>
              Processed in {result.processing_time_ms}ms | 
              Credits used: {result.credits_used}
            </small>
          </div>
        </div>
      )}
    </div>
  );
};

export default AIQueryBox;
```

### Credit Balance Widget

```jsx
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const AICreditsWidget = () => {
  const [credits, setCredits] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    fetchBalance();
  }, []);

  const fetchBalance = async () => {
    try {
      const response = await fetch('https://your-domain.com/ai/api/credits/balance/', {
        headers: {
          'Authorization': `Token ${localStorage.getItem('token')}`,
        }
      });
      
      const data = await response.json();
      setCredits(data);
    } catch (error) {
      console.error('Failed to fetch balance:', error);
    } finally {
      setLoading(false);
    }
  };

  const handlePurchase = async (packageType) => {
    try {
      const response = await fetch('https://your-domain.com/ai/api/credits/purchase/', {
        method: 'POST',
        headers: {
          'Authorization': `Token ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          package: packageType,
          payment_method: 'mobile_money'
        })
      });
      
      const data = await response.json();
      
      if (response.ok) {
        // Redirect to Paystack checkout
        window.location.href = data.authorization_url;
      } else {
        alert(`Error: ${data.error || 'Purchase failed'}`);
      }
    } catch (error) {
      console.error('Purchase failed:', error);
      alert('Failed to initialize payment. Please try again.');
    }
  };

  if (loading) return <div>Loading credits...</div>;

  return (
    <div className="ai-credits-widget">
      <div className="balance-display">
        <h4>AI Credits</h4>
        <div className="balance-amount">
          {credits?.balance?.toFixed(2) || '0.00'}
        </div>
        {credits?.days_until_expiry && (
          <small>Expires in {credits.days_until_expiry} days</small>
        )}
      </div>
      
      {credits?.balance < 10 && (
        <div className="low-balance-warning">
          ⚠️ Low balance! Purchase more credits to continue using AI features.
        </div>
      )}
      
      <div className="purchase-options">
        <button onClick={() => handlePurchase('starter')}>
          Buy Starter Pack<br/>
          <small>GHS 30 = 30 credits</small>
        </button>
        
        <button onClick={() => handlePurchase('value')} className="recommended">
          Buy Value Pack<br/>
          <small>GHS 80 = 100 credits (+25% bonus!)</small>
        </button>
        
        <button onClick={() => handlePurchase('premium')}>
          Buy Premium Pack<br/>
          <small>GHS 180 = 250 credits (+39% bonus!)</small>
        </button>
      </div>
    </div>
  );
};

export default AICreditsWidget;
```

### Payment Callback Page

Create this page to handle Paystack redirects:

```jsx
// pages/PaymentCallback.jsx
import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';

const PaymentCallback = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState('verifying');
  const [message, setMessage] = useState('Verifying your payment...');
  const [creditsAdded, setCreditsAdded] = useState(0);

  useEffect(() => {
    const reference = searchParams.get('reference');
    
    if (!reference) {
      setStatus('error');
      setMessage('No payment reference found');
      return;
    }

    verifyPayment(reference);
  }, [searchParams]);

  const verifyPayment = async (reference) => {
    try {
      const response = await fetch(
        `https://your-domain.com/ai/api/credits/verify/?reference=${reference}`,
        {
          headers: {
            'Authorization': `Token ${localStorage.getItem('token')}`,
          }
        }
      );

      const data = await response.json();

      if (data.status === 'success') {
        setStatus('success');
        setMessage(data.message);
        setCreditsAdded(data.credits_added);
        
        // Redirect to dashboard after 3 seconds
        setTimeout(() => {
          navigate('/dashboard');
        }, 3000);
      } else {
        setStatus('error');
        setMessage(data.message || 'Payment verification failed');
      }
    } catch (error) {
      console.error('Verification error:', error);
      setStatus('error');
      setMessage('Failed to verify payment. Please contact support if payment was deducted.');
    }
  };

  return (
    <div className="payment-callback-container">
      {status === 'verifying' && (
        <div className="verifying">
          <div className="spinner"></div>
          <h2>Verifying Payment...</h2>
          <p>Please wait while we confirm your payment with Paystack.</p>
        </div>
      )}

      {status === 'success' && (
        <div className="success">
          <div className="checkmark">✓</div>
          <h2>Payment Successful!</h2>
          <p className="credits-info">
            {creditsAdded} credits have been added to your account
          </p>
          <p className="redirect-info">Redirecting to dashboard...</p>
        </div>
      )}

      {status === 'error' && (
        <div className="error">
          <div className="error-icon">✗</div>
          <h2>Payment Verification Failed</h2>
          <p>{message}</p>
          <div className="error-actions">
            <button onClick={() => navigate('/credits')}>
              Try Again
            </button>
            <button onClick={() => navigate('/support')}>
              Contact Support
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default PaymentCallback;
```

### Add Route in App

```jsx
// App.jsx
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import PaymentCallback from './pages/PaymentCallback';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* ... other routes ... */}
        <Route path="/payment/callback" element={<PaymentCallback />} />
      </Routes>
    </BrowserRouter>
  );
}
```

**⚠️ Important:** Configure this callback URL in your backend's Paystack integration settings.

---

## 📊 Feature Cost Reference

Quick reference for frontend developers to show users:

| Feature | Credits | GHS Cost | Use Case |
|---------|---------|----------|----------|
| Natural Language Query | 0.5 | GHS 0.50 | Ask questions about business data |
| Product Description | 0.1 | GHS 0.10 | Generate product descriptions |
| Collection Message | 0.5 | GHS 0.50 | Create payment reminder messages |
| Credit Risk Assessment | 3.0 | GHS 3.00 | Analyze customer creditworthiness |
| Collection Priority | 5.0 | GHS 5.00 | Prioritize collection efforts |
| Payment Prediction | 1.0 | GHS 1.00 | Predict when customer will pay |
| Inventory Forecast | 4.0 | GHS 4.00 | Forecast inventory needs |
| Report Narrative | 0.2 | GHS 0.20 | Generate report summaries |

---

## 🚨 Error Handling

All endpoints follow consistent error patterns:

**402 Payment Required** - Insufficient credits
```json
{
  "error": "insufficient_credits",
  "message": "You need X credits. Current balance: Y",
  "current_balance": 2.50,
  "required_credits": 3.00
}
```

**400 Bad Request** - Invalid parameters
```json
{
  "field_name": ["Error message"],
  "another_field": ["Another error"]
}
```

**404 Not Found** - Resource doesn't exist
```json
{
  "error": "Product not found"
}
```

**500 Internal Server Error** - Processing failed
```json
{
  "error": "processing_failed",
  "message": "Detailed error message"
}
```

**Example Error Handling:**
```javascript
try {
  const response = await fetch(endpoint, options);
  
  if (response.status === 402) {
    // Insufficient credits - prompt user to purchase
    const error = await response.json();
    showPurchaseModal(error);
    return;
  }
  
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.message || 'Request failed');
  }
  
  const data = await response.json();
  return data;
} catch (error) {
  console.error('API Error:', error);
  showErrorNotification(error.message);
}
```

---

## 🔧 Installation & Setup (Backend)

For backend deployment, ensure these steps are completed:

1. **Install Dependencies:**
```bash
pip install openai==1.54.0 tiktoken==0.7.0 python-dateutil==2.9.0
```

2. **Set Environment Variables:**

**For Development** - Add to `.env.development`:
```env
OPENAI_API_KEY=sk-proj-your-key-here
PAYSTACK_SECRET_KEY=sk_test_your_test_key_here
PAYSTACK_PUBLIC_KEY=pk_test_your_test_key_here
AI_FEATURES_ENABLED=True
```

**For Production** - Add to `.env.production`:
```env
OPENAI_API_KEY=sk-proj-your-key-here
PAYSTACK_SECRET_KEY=sk_live_your_live_key_here
PAYSTACK_PUBLIC_KEY=pk_live_your_live_key_here
AI_FEATURES_ENABLED=True
```

3. **Run Migrations:**
```bash
python manage.py migrate ai_features
```

4. **Create Initial Credits (optional):**
You can grant initial free credits via Django admin or create a management command.

---

## 📞 Support & Questions

**For Frontend Team:**
- All endpoints are live and tested
- Check `check-availability` endpoint before making expensive calls
- Cache product descriptions (they don't change often)
- Show credit balance prominently in UI
- Implement "low credit" warnings at 10 credits

**Need Help?**
- Backend issues: Contact backend team
- API questions: Refer to this document
- New features: Submit feature request

---

## ✅ Testing Checklist

Before deploying frontend:

- [ ] Can fetch credit balance
- [ ] Can purchase credits (test with small amount)
- [ ] Natural language query works
- [ ] Error handling for insufficient credits
- [ ] Product description generation works
- [ ] Collection message generation works  
- [ ] Credit assessment endpoint works
- [ ] Usage stats display correctly
- [ ] Low credit warnings shown
- [ ] Transaction history loads

---

**🎉 You're all set!** The backend is production-ready. Happy coding! 🚀

**Last Updated:** November 7, 2025  
**Backend Version:** 1.0.0  
**Django Version:** 5.2.6
