# AI Integration Strategy - Backend Requirements & Implementation Guide

**Document Status:** Ready for Backend Team Review  
**Date:** November 7, 2025  
**Prepared By:** Frontend Team (AI Consultant Analysis)  
**For:** Backend Development Team  
**Priority:** Medium - Optional Strategic Feature Enhancement

---

## 📋 Executive Summary

**IMPORTANT:** AI features are **OPTIONAL ADD-ONS** to your existing POS system. Your current storefront-based subscription pricing remains unchanged. Users get full POS functionality without AI.

This document outlines the complete AI integration strategy for the POS system, including:
- AI feature requirements and endpoints needed
- AI Agent architecture considerations  
- Cost analysis and profitability models
- Pricing strategy recommendations (prepaid add-on model)
- Technical implementation requirements
- Ghana market considerations

**Key Decision:** AI features are implemented as **optional prepaid credits** - users buy only when needed, no forced subscription changes.

**See Also:** `/docs/AI_OPTIONAL_ADD_ON_STRATEGY.md` for detailed beginner-friendly guide on maintaining your current pricing model.

---

## 🎯 Business Context

### Market Reality: Ghana Tech Adoption Challenges
- **Tight margins**: Retail/wholesale businesses operate on 10-20% profit margins
- **Cash flow sensitive**: Cannot afford expensive tech with unclear ROI
- **Price sensitivity**: GHS 199/month subscription is already a significant commitment
- **"Show me the money" mentality**: Need immediate, tangible value
- **Pay-as-you-go preference**: Ghanaians prefer prepaid models (airtime, electricity, etc.)

### Business Goals
1. **Differentiate** from competitors with AI capabilities
2. **Increase** subscription value and pricing power
3. **Improve** customer retention through high-value features
4. **Generate** additional revenue streams
5. **Maintain** profitability (50%+ margins on AI features)

---

## 💰 Cost Analysis & Profitability

### OpenAI Pricing (November 2025)

| Model | Input (per 1K tokens) | Output (per 1K tokens) | Use Case |
|-------|---------------------|----------------------|----------|
| **GPT-4 Turbo** | $0.01 | $0.03 | Complex reasoning, agents |
| **GPT-4** | $0.03 | $0.06 | High-quality analysis |
| **GPT-3.5 Turbo** | $0.0005 | $0.0015 | Simple tasks, high volume |
| **GPT-4o-mini** | $0.00015 | $0.0006 | Ultra-cheap, good quality |

### Cost Per Feature (Optimized Implementation)

| Feature | OpenAI Cost | Charge User | Your Profit | Margin |
|---------|-------------|-------------|-------------|---------|
| Product Description | GHS 0.005 | GHS 0.10 | GHS 0.095 | 95% |
| Report Summary | GHS 0.015 | GHS 0.20 | GHS 0.185 | 92% |
| Customer Insight Query | GHS 0.008 | GHS 0.50 | GHS 0.492 | 98% |
| Collection Message | GHS 0.005 | GHS 0.50 | GHS 0.495 | 99% |
| Credit Risk Assessment | GHS 0.640 | GHS 3.00 | GHS 2.36 | 79% |
| Collections Analysis | GHS 3.200 | GHS 5.00 | GHS 1.80 | 36% |
| Inventory Forecast | GHS 2.000 | GHS 4.00 | GHS 2.00 | 50% |

**Key Insight:** Basic AI features are HIGHLY profitable (90%+ margins). Advanced features still maintain 50%+ margins when properly priced.

### Monthly Cost Estimates Per Business

**Scenario 1: Moderate AI User (Professional Plan)**
```
Monthly Usage:
- 50 product descriptions: GHS 0.25
- 30 report summaries: GHS 0.45
- 100 insight queries: GHS 0.80
- 50 collection messages: GHS 0.25
- 25 credit assessments: GHS 16.00
- 5 collection analyses: GHS 16.00
─────────────────────────────────
Total AI cost: ~GHS 34/month

Charge user: GHS 100 credits = GHS 100
Your profit: GHS 66/month (66% margin) ✅
```

**Scenario 2: Heavy AI User (Enterprise Plan)**
```
Monthly Usage:
- Unlimited basic features: GHS 5
- 100 credit assessments: GHS 64
- 20 collection analyses: GHS 64
─────────────────────────────────
Total AI cost: ~GHS 133/month

Charge user: Unlimited (GHS 449/month plan)
Your profit: GHS 316/month (70% margin) ✅
```

**Critical:** With optimized implementation (caching, batch processing, cheaper models), costs can be reduced by 70-80%.

---

## 🏗️ Recommended Architecture: AI Features vs. AI Agents

### What Are AI Agents?

**AI Features** (Recommended for Phase 1):
- User requests → AI responds
- Stateless (each request independent)
- Single-purpose per API call
- Example: User clicks "Generate message" → Returns message

**AI Agents** (Phase 2 - Future):
- Autonomous, proactive operation
- Stateful (remembers context, learns)
- Multi-step workflows
- Example: Agent monitors overdue customers daily, sends reminders automatically, follows up based on responses

### Why Start with Features, Not Agents?

| Aspect | AI Features | AI Agents |
|--------|-------------|-----------|
| **Development Time** | 2-4 weeks | 8-12 weeks |
| **Cost** | GHS 30-50/month/business | GHS 150-300/month/business |
| **Complexity** | Low | High |
| **User Trust** | High (user controls) | Lower (automation anxiety) |
| **Support Burden** | Low | High |
| **Market Readiness** | Ready now | Need education |
| **Profitability** | High (70%+ margins) | Challenging (30-40% margins) |

**Recommendation:** Start with AI features (user-initiated). Add autonomous agents in Phase 2 after proving value and gathering usage data.

---

## 🎯 Priority Features to Implement

### Priority 1: Smart Collections Assistant ⭐⭐⭐ (HIGHEST ROI)

**Why This Matters Most:**
- Cash flow is king in retail/wholesale
- Collections are emotionally difficult for business owners
- Saves 10+ hours/week per business
- Reduces bad debt by 30-40%
- **ROI: GHS 6,000/month savings vs. GHS 50/month cost = 120x ROI!**

#### Required Backend Endpoints:

##### 1.1 Credit Risk Assessment
```
POST /ai/api/credit/risk-assessment/
```

**Request:**
```json
{
  "customer_id": "uuid",
  "requested_credit_limit": 5000,
  "assessment_type": "new_credit" | "increase" | "renewal"
}
```

**Response:**
```json
{
  "customer": {
    "name": "ABC Wholesale",
    "current_limit": 0,
    "requested_limit": 5000
  },
  "risk_score": 72,
  "risk_level": "MEDIUM",
  "recommendation": {
    "action": "APPROVE_PARTIAL" | "APPROVE_FULL" | "DENY" | "REQUIRE_MORE_INFO",
    "suggested_limit": 3000,
    "suggested_terms_days": 30,
    "confidence": 0.78
  },
  "analysis": {
    "positive_factors": [
      "Perfect payment history over 6 months",
      "Purchase frequency is consistent (weekly)",
      "Average order value stable at GHS 1,200"
    ],
    "risk_factors": [
      "Only 6 months of history (prefer 12+ months)",
      "Requested limit is 3x average monthly purchases"
    ],
    "comparable_customers": {
      "similar_approved_limit_avg": 3500,
      "default_rate_for_similar_profile": "8%"
    }
  },
  "conditions": [
    "Start with GHS 3,000 limit",
    "Review after 3 months of good payment",
    "Require monthly statements"
  ],
  "explanation": "Based on ABC Wholesale's solid 6-month track record..."
}
```

**AI Implementation Notes:**
- Use GPT-4 Turbo for complex analysis
- Input context: Customer payment history, purchase patterns, similar customer data
- Estimated cost: $0.04 per assessment (~GHS 0.64)
- Cache results for 5 minutes
- **Data Required:** Customer payment history, purchase frequency, average order value, outstanding balance history

##### 1.2 Collection Priority Analysis
```
GET /ai/api/credit/collection-priority/
```

**Query Parameters:**
```
?overdue_only=true&min_amount=500&storefront_id=uuid (optional)
```

**Response:**
```json
{
  "summary": {
    "total_overdue_customers": 45,
    "total_overdue_amount": "125,400.00",
    "prioritized_count": 15,
    "prioritized_amount": "98,200.00",
    "potential_recovery_30_days": "75,000.00"
  },
  "priority_list": [
    {
      "rank": 1,
      "urgency": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW",
      "customer": {
        "id": "uuid",
        "name": "XYZ Electronics",
        "outstanding_balance": "25,000.00",
        "days_overdue": 45,
        "credit_limit": "30,000.00"
      },
      "ai_insights": {
        "collection_likelihood": "HIGH" | "MEDIUM" | "LOW",
        "recommended_approach": "FIRM_BUT_PROFESSIONAL" | "FRIENDLY" | "ESCALATE_TO_FORMAL",
        "contact_today": true,
        "reasoning": "Customer has excellent payment history but suddenly stopped paying 45 days ago...",
        "talking_points": [
          "Reference their previously excellent payment record",
          "Express concern about the unusual delay",
          "Offer a payment plan if needed"
        ],
        "suggested_payment_plan": {
          "down_payment": 10000,
          "installments": 3,
          "installment_amount": 5000,
          "frequency": "weekly"
        }
      },
      "customer_profile": {
        "total_lifetime_purchases": "450,000.00",
        "average_payment_days": 15,
        "previous_overdue_count": 1,
        "last_purchase_date": "2025-10-15",
        "purchase_frequency": "DECLINING"
      },
      "next_steps": [
        "Call customer today before 4pm",
        "Reference invoice INV-2024-1234",
        "Propose payment plan if cash flow is issue"
      ]
    }
  ],
  "strategic_insights": {
    "best_collection_days": ["Monday", "Tuesday"],
    "best_contact_times": ["9-11am", "2-4pm"],
    "average_recovery_time": "14 days",
    "success_rate_with_payment_plans": "78%"
  }
}
```

**AI Implementation Notes:**
- **OPTIMIZATION CRITICAL:** Batch analyze all customers in ONE API call (not 45 separate calls)
- Use GPT-4o-mini for cost efficiency
- Estimated cost: $0.20 per analysis batch (~GHS 3.20)
- Cache results for 1 hour
- **Data Required:** All overdue customers with payment history, purchase patterns, communication history

##### 1.3 Collection Message Generator
```
POST /ai/api/credit/communication/
```

**Request:**
```json
{
  "customer_id": "uuid",
  "message_type": "first_reminder" | "second_reminder" | "final_notice" | "payment_plan_offer",
  "tone": "professional_friendly" | "firm" | "formal_legal",
  "language": "en" | "tw",
  "include_payment_plan": true
}
```

**Response:**
```json
{
  "message": {
    "subject": "Friendly Reminder: Invoice #INV-2024-1234 - Payment Due",
    "body": "Dear Mr. Mensah,\n\nI hope this message finds you well...",
    "sms_version": "Dear Mr. Mensah, gentle reminder that invoice INV-2024-1234...",
    "whatsapp_version": "Hello Mr. Mensah 👋\n\nJust a friendly reminder...",
    "follow_up_schedule": {
      "next_reminder": "2025-11-13",
      "escalation_date": "2025-11-20",
      "final_notice_date": "2025-11-27"
    }
  },
  "cultural_notes": [
    "Tone maintains respect and relationship focus (important in Ghanaian business culture)",
    "Offers face-saving payment plan option",
    "Assumes good faith and temporary difficulty"
  ]
}
```

**AI Implementation Notes:**
- Use GPT-4o-mini for cost efficiency
- Estimated cost: $0.0003 per message (~GHS 0.005)
- No caching (each message should be fresh)
- **Data Required:** Customer details, outstanding invoices, payment history summary

##### 1.4 Portfolio Health Dashboard
```
GET /ai/api/credit/dashboard/
```

**Response:**
```json
{
  "portfolio_health": {
    "overall_score": 68,
    "status": "MODERATE_RISK" | "EXCELLENT" | "GOOD" | "HIGH_RISK" | "CRITICAL",
    "trend": "DETERIORATING" | "IMPROVING" | "STABLE"
  },
  "ai_executive_summary": "Your credit portfolio shows concerning trends this month. Outstanding receivables increased 22%...",
  "key_metrics": {
    "total_credit_extended": "450,000.00",
    "total_outstanding": "280,000.00",
    "overdue_amount": "125,000.00",
    "overdue_percentage": 44.6,
    "average_collection_days": 42,
    "default_risk_amount": "45,000.00"
  },
  "ai_insights": {
    "biggest_risks": [
      {
        "risk": "Three large customers at high default risk",
        "amount": "45,000.00",
        "action": "Immediate collection focus required"
      }
    ],
    "opportunities": [
      {
        "opportunity": "15 excellent-credit customers ready for limit increases",
        "potential_revenue": "25,000.00/month",
        "action": "Approve increases to capture more business"
      }
    ],
    "trends": {
      "payment_days_trend": "INCREASING",
      "utilization_trend": "INCREASING",
      "default_rate_trend": "STABLE",
      "explanation": "Customers are taking longer to pay (35→42 days)..."
    }
  },
  "recommendations": [
    "Focus collections on 15 priority customers (GHS 98,000 recoverable)",
    "Block 3 high-risk customers from new credit",
    "Approve 8 low-risk customers for limit increases"
  ]
}
```

**AI Implementation Notes:**
- Use GPT-4 Turbo for comprehensive analysis
- Estimated cost: $0.50 per dashboard (~GHS 8)
- Cache results for 6 hours (expensive operation)
- **Data Required:** All credit customers, payment trends, outstanding balances, collection history

##### 1.5 Payment Prediction
```
GET /ai/api/credit/payment-prediction/{customer_id}/
```

**Response:**
```json
{
  "customer": {
    "name": "GHI Supermarket",
    "outstanding_invoices": 3,
    "total_due": "15,600.00"
  },
  "predictions": [
    {
      "invoice_id": "INV-2024-5678",
      "amount": "5,200.00",
      "due_date": "2025-11-01",
      "predicted_payment_date": "2025-11-08",
      "confidence": 0.82,
      "prediction_reasoning": "Customer typically pays 7-10 days after due date...",
      "recommended_action": "Send friendly reminder on Nov 6th"
    }
  ],
  "payment_pattern_analysis": {
    "average_payment_day_after_due": 8,
    "payment_consistency": "HIGH",
    "preferred_payment_days": ["Wednesday", "Friday"],
    "monthly_cash_flow_cycle": "Pays after 5th of month (likely salary day)",
    "seasonality": "Slower in December, faster in March-April"
  }
}
```

**AI Implementation Notes:**
- Use GPT-4o-mini
- Estimated cost: $0.01 per prediction (~GHS 0.16)
- Cache results for 24 hours
- **Data Required:** Customer payment history with dates, invoice amounts, payment patterns

---

### Priority 2: Customer Insights Assistant ⭐⭐

Natural language query interface for business insights.

#### Required Backend Endpoint:

```
POST /ai/api/insights/query/
```

**Request:**
```json
{
  "query": "Which customers are at risk of churning?",
  "context": "rfm_segmentation" | "sales_analysis" | "inventory" | "financial"
}
```

**Response:**
```json
{
  "answer": "Based on your RFM analysis, 12 customers are showing churn risk signals...",
  "data_sources": [
    "Customer segmentation report",
    "Purchase frequency analysis",
    "Last 90 days transaction data"
  ],
  "confidence": 0.85,
  "suggestions": [
    "Show me details about these at-risk customers",
    "What products do they usually buy?",
    "How can I re-engage them?"
  ],
  "visualizations": [
    {
      "type": "table",
      "title": "At-Risk Customers",
      "data": [...]
    }
  ]
}
```

**AI Implementation Notes:**
- Use GPT-4o-mini for cost efficiency
- Estimated cost: $0.0005 per query (~GHS 0.008)
- Cache similar queries for 30 minutes
- **Data Required:** Access to reports data, customer data, sales data (query-dependent)

---

### Priority 3: Product Description Generator ⭐⭐

Generate compelling product descriptions for e-commerce/catalog.

#### Required Backend Endpoint:

```
POST /ai/api/products/generate-description/
```

**Request:**
```json
{
  "product_name": "Samsung 55\" QLED TV",
  "category": "Electronics",
  "attributes": {
    "brand": "Samsung",
    "size": "55 inches",
    "type": "QLED"
  },
  "tone": "professional" | "casual" | "technical" | "marketing",
  "language": "en" | "tw"
}
```

**Response:**
```json
{
  "description": "Experience cinema-quality entertainment with this Samsung 55\" QLED TV...",
  "short_description": "Samsung 55\" QLED TV with stunning picture quality",
  "seo_keywords": ["samsung tv", "qled", "55 inch tv", "4k television"],
  "meta_description": "Shop Samsung 55\" QLED TV - Crystal clear picture, smart features...",
  "suggestions": {
    "upsell_opportunities": ["Premium HDMI Cable", "TV Wall Mount"],
    "complementary_products": ["Sound Bar", "Streaming Device"]
  }
}
```

**AI Implementation Notes:**
- Use GPT-4o-mini (very cheap)
- Estimated cost: $0.0003 per description (~GHS 0.005)
- Cache permanently (descriptions rarely change)
- No special data requirements (just product attributes)

---

### Priority 4: AI Report Narratives ⭐

Transform data tables into readable business stories.

#### Required Backend Enhancement:

Add AI narrative to **existing report endpoints**:
- `GET /reports/api/sales/summary`
- `GET /reports/api/financial/revenue-profit`
- `GET /reports/api/customer/segmentation`
- `GET /reports/api/financial/ar-aging`
- etc.

**Enhanced Response (add ai_narrative field):**
```json
{
  "summary": { /* existing data */ },
  "results": [ /* existing data */ ],
  
  "ai_narrative": {
    "summary": "Your business generated GHS 150,000 in revenue this month, a 15% increase...",
    "key_insights": [
      "Electronics category showed strongest growth at 25%",
      "Weekend sales outperformed weekdays by 40%",
      "Credit sales increased, monitor receivables closely"
    ],
    "recommendations": [
      "Consider expanding electronics inventory",
      "Implement weekend promotions to maximize foot traffic",
      "Review credit policies to maintain healthy cash flow"
    ],
    "risk_factors": [
      "Outstanding receivables up 20% - may need collection efforts"
    ],
    "trends": [
      {
        "metric": "Revenue",
        "direction": "up",
        "change_percentage": 15,
        "interpretation": "Strong growth driven by electronics category"
      }
    ]
  }
}
```

**AI Implementation Notes:**
- Use GPT-4o-mini
- Estimated cost: $0.0009 per narrative (~GHS 0.015)
- Cache for 6 hours (reports don't change frequently)
- **Data Required:** Report summary data, period comparison data, trends

---

### Priority 5: Inventory Forecasting ⭐

Predict inventory needs and prevent stockouts.

#### Required Backend Endpoint:

```
POST /ai/api/inventory/forecast/
```

**Request:**
```json
{
  "product_id": "uuid",
  "forecast_days": 30,
  "include_seasonality": true,
  "include_recommendations": true
}
```

**Response:**
```json
{
  "product": {
    "id": "uuid",
    "name": "Samsung TV 55\"",
    "current_stock": 15
  },
  "forecast": {
    "next_7_days": {
      "predicted_units": 8,
      "confidence": 0.85
    },
    "next_30_days": {
      "predicted_units": 32,
      "confidence": 0.78
    },
    "predicted_stockout_date": "2025-11-20"
  },
  "recommendations": {
    "action": "REORDER" | "MONITOR" | "REDUCE_STOCK" | "NO_ACTION",
    "suggested_quantity": 40,
    "urgency": "HIGH" | "MEDIUM" | "LOW" | "CRITICAL",
    "reasoning": "Based on current sales velocity and upcoming holiday season...",
    "optimal_reorder_point": 10,
    "economic_order_quantity": 35
  },
  "seasonal_insights": {
    "is_seasonal": true,
    "peak_months": ["November", "December"],
    "low_months": ["February", "March"],
    "seasonal_adjustment_factor": 1.4
  }
}
```

**AI Implementation Notes:**
- Use GPT-4 Turbo for complex forecasting
- Estimated cost: $0.25 per forecast (~GHS 4)
- Cache for 24 hours
- **Data Required:** Product sales history (90 days minimum), stock movement history, seasonal patterns

---

## 🎯 Recommended Pricing Strategy

After analysis of Ghana market dynamics and cost structures, we recommend:

### **Phase 1 Launch: Simple Hybrid Model**

```
┌─────────────────────────────────────────────────────┐
│ STANDARD PLAN - GHS 199/month                       │
├─────────────────────────────────────────────────────┤
│ ✅ Full POS features (inventory, sales, reports)   │
│ ✅ 10 FREE AI credits/month (to trial AI)          │
│ ❌ No premium AI features                           │
│                                                     │
│ 💰 Buy AI credits when needed:                     │
│    - Starter Pack: GHS 30 = 30 credits             │
│    - Value Pack: GHS 80 = 100 credits (20% bonus)  │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ AI-POWERED PLAN - GHS 299/month                     │
├─────────────────────────────────────────────────────┤
│ ✅ Everything in Standard                           │
│ ✅ 200 AI credits/month (included)                  │
│ ✅ Unused credits roll over (max 100)               │
│ ✅ Priority AI processing                           │
│ ✅ Discounted top-ups: GHS 30 = 40 credits         │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│ ENTERPRISE PLAN - GHS 449/month                     │
├─────────────────────────────────────────────────────┤
│ ✅ Everything in AI-Powered                         │
│ ✅ UNLIMITED AI usage                               │
│ ✅ Unlimited storefronts                            │
│ ✅ Dedicated support                                │
│ ✅ Custom integrations                              │
└─────────────────────────────────────────────────────┘
```

### Credit Cost Structure

| AI Feature | Credits | GHS Cost | Your Cost | Your Profit |
|-----------|---------|----------|-----------|-------------|
| Product Description | 0.1 | 0.10 | 0.005 | 0.095 (95%) |
| Report Summary | 0.2 | 0.20 | 0.015 | 0.185 (92%) |
| Customer Insight | 0.5 | 0.50 | 0.008 | 0.492 (98%) |
| Collection Message | 0.5 | 0.50 | 0.005 | 0.495 (99%) |
| Credit Assessment | 3.0 | 3.00 | 0.640 | 2.36 (79%) |
| Collection Analysis | 5.0 | 5.00 | 3.200 | 1.80 (36%) |
| Inventory Forecast | 4.0 | 4.00 | 2.000 | 2.00 (50%) |

**Profitability Analysis:**
```
Standard Plan (with 30 credit pack purchase):
- Revenue: GHS 199 + GHS 30 = GHS 229
- Your costs: GHS 100 (infrastructure) + GHS 10 (AI usage) = GHS 110
- Profit: GHS 119 (52% margin) ✅

AI-Powered Plan:
- Revenue: GHS 299
- Your costs: GHS 100 + GHS 60 (200 credits usage) = GHS 160
- Profit: GHS 139 (47% margin) ✅

Enterprise Plan:
- Revenue: GHS 449
- Your costs: GHS 120 + GHS 150 (heavy AI usage) = GHS 270
- Profit: GHS 179 (40% margin) ✅
```

---

## 🔧 Technical Implementation Requirements

### Backend Infrastructure Needed

#### 1. AI Credit Management System

```python
# Required Models

class BusinessAICredits(models.Model):
    """Track AI credit balance per business"""
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    purchased_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)

class AITransaction(models.Model):
    """Log every AI request for billing and analytics"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    feature = models.CharField(max_length=100)  # 'credit_assessment', 'collection_message', etc.
    credits_used = models.DecimalField(max_digits=6, decimal_places=2)
    cost_to_us = models.DecimalField(max_digits=6, decimal_places=4)  # Track actual OpenAI cost
    timestamp = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    request_data = models.JSONField()  # Store request params
    response_data = models.JSONField()  # Store response (for debugging)

class AICreditPurchase(models.Model):
    """Track credit purchases"""
    business = models.ForeignKey(Business, on_delete=models.CASCADE)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    credits_purchased = models.DecimalField(max_digits=10, decimal_places=2)
    payment_reference = models.CharField(max_length=255)
    payment_method = models.CharField(max_length=50)
    purchased_at = models.DateTimeField(auto_now_add=True)
```

#### 2. Credit Billing Service

```python
class AIBillingService:
    """Handle AI credit charging and validation"""
    
    FEATURE_COSTS = {
        'product_description': 0.1,
        'report_summary': 0.2,
        'customer_insight': 0.5,
        'collection_message': 0.5,
        'credit_assessment': 3.0,
        'collection_analysis': 5.0,
        'inventory_forecast': 4.0,
    }
    
    @staticmethod
    def check_credits(business_id: UUID, feature: str) -> bool:
        """Check if business has enough credits"""
        credits = BusinessAICredits.objects.filter(
            business_id=business_id,
            is_active=True,
            expires_at__gt=timezone.now()
        ).first()
        
        if not credits:
            raise InsufficientCreditsException("No active AI credits")
        
        cost = AIBillingService.FEATURE_COSTS[feature]
        return credits.balance >= cost
    
    @staticmethod
    def charge_credits(business_id: UUID, feature: str, actual_openai_cost: float):
        """Deduct credits after successful AI call"""
        credits = BusinessAICredits.objects.get(business_id=business_id)
        cost = AIBillingService.FEATURE_COSTS[feature]
        
        # Deduct credits
        credits.balance -= cost
        credits.save()
        
        # Log transaction
        AITransaction.objects.create(
            business_id=business_id,
            feature=feature,
            credits_used=cost,
            cost_to_us=actual_openai_cost,
            success=True
        )
        
        # Send alert if running low
        if credits.balance < 10:
            send_low_credit_alert(business_id, credits.balance)
        
        return credits.balance
```

#### 3. API Endpoint Pattern

All AI endpoints should follow this pattern:

```python
from rest_framework.decorators import api_view
from rest_framework.response import Response
from openai import OpenAI

@api_view(['POST'])
def ai_feature_endpoint(request):
    """Pattern for all AI endpoints"""
    business_id = request.user.business_id
    
    # 1. Validate AI credits
    feature_name = 'credit_assessment'
    if not AIBillingService.check_credits(business_id, feature_name):
        return Response({
            'error': 'insufficient_credits',
            'message': 'You need 3.0 credits. Buy more to continue.',
            'current_balance': get_credit_balance(business_id),
            'required_credits': AIBillingService.FEATURE_COSTS[feature_name]
        }, status=402)  # Payment Required
    
    # 2. Check cache first (if applicable)
    cache_key = f"ai_{feature_name}_{business_id}_{hash(request.data)}"
    cached = cache.get(cache_key)
    if cached:
        return Response(cached)
    
    # 3. Call OpenAI API
    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
        # Prepare context from your database
        context_data = prepare_context(business_id, request.data)
        
        # Call OpenAI
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # or gpt-4-turbo for complex tasks
            messages=[
                {"role": "system", "content": "You are an expert..."},
                {"role": "user", "content": format_prompt(context_data)}
            ],
            temperature=0.7
        )
        
        # Calculate actual cost
        actual_cost = calculate_openai_cost(response.usage)
        
        # Parse response
        result = parse_ai_response(response)
        
        # 4. Charge credits
        AIBillingService.charge_credits(business_id, feature_name, actual_cost)
        
        # 5. Cache result (if applicable)
        cache.set(cache_key, result, timeout=3600)  # 1 hour
        
        return Response(result)
        
    except Exception as e:
        # Log error but don't charge credits
        log_ai_error(business_id, feature_name, str(e))
        return Response({
            'error': 'ai_service_error',
            'message': 'AI service temporarily unavailable. Please try again.'
        }, status=503)
```

#### 4. Cost Optimization Strategies

**CRITICAL FOR PROFITABILITY:**

```python
# 1. Batch Processing
def analyze_all_overdue_customers(business_id):
    """Analyze all customers in ONE API call instead of 45 separate calls"""
    customers = get_overdue_customers(business_id)
    
    # Build single prompt with all customer data
    batch_prompt = f"""
    Analyze these {len(customers)} overdue customers and prioritize them:
    
    {format_all_customers(customers)}
    
    Return JSON array with priority ranking for each.
    """
    
    # ONE API call instead of 45
    response = openai_call(batch_prompt)
    return parse_batch_response(response)

# Cost savings: 80-90%


# 2. Use Cheaper Models Strategically
def generate_collection_message(customer_id):
    """Use cheapest model for simple tasks"""
    
    # DON'T use GPT-4 ($0.03/1K tokens) for simple tasks
    # DO use GPT-4o-mini ($0.0006/1K tokens) - 50x cheaper!
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",  # ← Critical for cost savings
        messages=[...]
    )

# Cost savings: 95%


# 3. Aggressive Caching
from django.core.cache import cache

@cache_result(ttl=86400)  # 24 hours
def assess_credit_risk(customer_id):
    """Cache expensive operations"""
    # Credit risk doesn't change minute-to-minute
    # Cache for 24 hours to avoid repeated calls
    return call_openai_api(customer_id)

# Cost savings: 90% (if checking 10x per day)


# 4. Rule-Based Pre-filtering
def analyze_customer_priority(customers):
    """Use free logic first, AI only for edge cases"""
    
    for customer in customers:
        # Simple rules (FREE):
        if customer.days_overdue < 7:
            customer.priority = "low"
        elif customer.days_overdue > 60:
            customer.priority = "critical"
        elif customer.payment_history == "excellent" and customer.days_overdue < 30:
            customer.priority = "medium"
        else:
            # Only 20% need AI analysis
            customer.priority = call_ai_for_complex_case(customer)

# Cost savings: 80%
```

#### 5. AI Service Configuration

```python
# settings.py

# OpenAI Configuration
OPENAI_API_KEY = config('OPENAI_API_KEY')
OPENAI_ORGANIZATION = config('OPENAI_ORGANIZATION', default='')

# AI Feature Flags
AI_FEATURES_ENABLED = config('AI_FEATURES_ENABLED', default=True, cast=bool)

# AI Model Selection
AI_MODELS = {
    'cheap': 'gpt-4o-mini',  # $0.00015 input, $0.0006 output
    'standard': 'gpt-3.5-turbo',  # $0.0005 input, $0.0015 output
    'advanced': 'gpt-4-turbo-preview',  # $0.01 input, $0.03 output
}

# Feature → Model Mapping (optimize costs)
AI_FEATURE_MODELS = {
    'product_description': AI_MODELS['cheap'],
    'report_summary': AI_MODELS['cheap'],
    'customer_insight': AI_MODELS['cheap'],
    'collection_message': AI_MODELS['cheap'],
    'credit_assessment': AI_MODELS['advanced'],  # Complex analysis needs GPT-4
    'collection_analysis': AI_MODELS['advanced'],
    'inventory_forecast': AI_MODELS['advanced'],
}

# Rate Limiting (prevent abuse)
AI_RATE_LIMITS = {
    'requests_per_minute': 10,
    'requests_per_hour': 100,
    'requests_per_day': 500,
}

# Caching Configuration
AI_CACHE_DURATIONS = {
    'product_description': 86400 * 30,  # 30 days (permanent)
    'report_summary': 3600 * 6,  # 6 hours
    'customer_insight': 1800,  # 30 minutes
    'collection_message': 0,  # No cache (always fresh)
    'credit_assessment': 300,  # 5 minutes
    'collection_analysis': 3600,  # 1 hour
    'inventory_forecast': 86400,  # 24 hours
}

# Cost Tracking & Alerts
AI_COST_ALERT_THRESHOLD = 100  # Alert if monthly cost exceeds GHS 100 per business
AI_BUDGET_CAPS = {
    'per_business_daily': 10.0,  # GHS 10/day max
    'per_business_monthly': 200.0,  # GHS 200/month max
    'platform_monthly': 10000.0,  # GHS 10,000 total platform budget
}
```

---

## 🔒 Security & Data Privacy

### Critical Considerations

1. **No PII in AI Prompts**
   ```python
   # ❌ BAD - Sending customer personal data to OpenAI
   prompt = f"Analyze customer {customer.name}, phone: {customer.phone}..."
   
   # ✅ GOOD - Anonymize customer data
   prompt = f"Analyze Customer ID {hash(customer.id)}, payment history: {...}"
   ```

2. **Data Encryption**
   - All API requests to OpenAI over HTTPS
   - Encrypt AI transaction logs at rest
   - Don't store full AI responses permanently (GDPR)

3. **Audit Logging**
   - Log every AI request (who, what, when, cost)
   - Track which user initiated each AI call
   - Retention: 90 days (then purge for privacy)

4. **User Consent**
   - Add checkbox: "I agree to AI-powered features processing my business data"
   - Allow opt-out at subscription level
   - Clearly disclose AI usage in terms of service

5. **OpenAI Data Processing Agreement**
   - Sign OpenAI's data processing addendum
   - Ensure compliance with OpenAI's usage policies
   - Configure zero data retention in OpenAI settings

---

## 📊 Data Requirements Summary

To implement AI features, backend needs to expose/prepare:

### For Credit AI:
- ✅ Customer payment history (dates, amounts, on-time vs late)
- ✅ Customer purchase patterns (frequency, average order value, trends)
- ✅ Outstanding balance history per customer
- ✅ Communication history (reminders sent, responses received)
- ✅ Credit limit and utilization data
- ✅ Similar customer cohort data (for comparison)
- ✅ Industry/category benchmarks (optional, for better analysis)

### For Insights AI:
- ✅ Access to existing report data (sales, customers, inventory)
- ✅ Aggregated metrics and trends
- ✅ Customer segmentation data (RFM)

### For Inventory AI:
- ✅ Product sales history (90+ days recommended)
- ✅ Stock level history
- ✅ Seasonal patterns (if available)
- ✅ Supplier lead times
- ✅ Reorder costs

### For Product AI:
- ✅ Product attributes (name, category, brand, specs)
- ✅ No historical data needed

---

## 🚀 Implementation Phases

### Phase 1: Foundation (Weeks 1-2)
**Backend Tasks:**
- [ ] Create AI credit management models
- [ ] Implement credit purchase endpoint (MOMO integration)
- [ ] Build credit billing service
- [ ] Set up OpenAI API configuration
- [ ] Create AI transaction logging
- [ ] Implement rate limiting
- [ ] Add AI usage tracking endpoint: `GET /ai/api/usage-stats/`

**Deliverable:** Credit system working, ready for AI endpoints

---

### Phase 2: Smart Collections (Weeks 3-5)
**Backend Tasks:**
- [ ] Implement credit risk assessment endpoint
- [ ] Implement collection priority analysis endpoint
- [ ] Implement message generator endpoint
- [ ] Implement portfolio dashboard endpoint
- [ ] Implement payment prediction endpoint
- [ ] Add data preparation utilities
- [ ] Optimize with caching and batching
- [ ] Write unit tests

**Deliverable:** All collections AI endpoints functional

---

### Phase 3: Additional Features (Weeks 6-7)
**Backend Tasks:**
- [ ] Implement customer insights endpoint
- [ ] Implement product description generator
- [ ] Add AI narratives to existing reports
- [ ] Implement inventory forecasting endpoint
- [ ] Performance optimization

**Deliverable:** All Priority 1-5 features complete

---

### Phase 4: Optimization & Launch (Week 8)
**Backend Tasks:**
- [ ] Load testing
- [ ] Cost optimization review
- [ ] Security audit
- [ ] API documentation
- [ ] Admin dashboard for monitoring AI usage
- [ ] Production deployment

**Deliverable:** Production-ready AI features

---

## 📈 Success Metrics to Track

### Technical Metrics
- ✅ AI API response time: < 3 seconds (95th percentile)
- ✅ Cache hit rate: > 40%
- ✅ Error rate: < 1%
- ✅ Average tokens per request: < 2,000
- ✅ Cost per business/month: < GHS 60 (for Professional plan)

### Business Metrics
- ✅ AI feature adoption: > 60% of paid users
- ✅ Credit purchase rate: > 30% of Standard plan users
- ✅ Upgrade rate: 20% Standard → AI-Powered plan
- ✅ Customer satisfaction (NPS): > 8 for AI features
- ✅ Profit margin: > 50% on AI features

### Financial Metrics
- ✅ AI revenue per user: > GHS 50/month
- ✅ AI cost per user: < GHS 40/month
- ✅ Payback period: < 3 months

---

## 🎯 Go-to-Market Strategy

### Marketing Messages (Ghana-Focused)

**❌ Don't Say:**
- "AI-powered features"
- "GPT-4 integration"
- "Machine learning algorithms"

**✅ Do Say:**
- "Get paid 25% faster with smart collections"
- "Reduce bad debt by 30%"
- "Know which customers to contact first"
- "Save 10 hours per week on collections"

### ROI Calculator (Include in Sales Materials)

```
Smart Collections ROI:
──────────────────────────
Your monthly credit sales: GHS 200,000
Current bad debt rate: 5% = GHS 10,000/year lost

With AI Collections:
Reduce bad debt to 2% = GHS 4,000/year lost
Savings: GHS 6,000/year

Cost: GHS 100 credits/month × 12 = GHS 1,200/year
NET SAVINGS: GHS 4,800/year

ROI: 400% 🎉
```

### Pricing Communication

**Standard Plan Page:**
```
GHS 199/month
✅ Full POS features
✅ 10 FREE AI credits (try before you buy!)

Want more AI power?
Buy credits: GHS 30 = 30 credits
OR
Upgrade to AI-Powered Plan: GHS 299/month
```

**AI-Powered Plan Page:**
```
GHS 299/month
✅ Everything in Standard
✅ 200 AI credits included every month
✅ Roll over unused credits
✅ Faster collections, smarter decisions

Perfect for businesses with:
• High credit sales
• 50+ customers
• Collection challenges
```

---

## ⚠️ Risk Mitigation

### Technical Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| OpenAI API downtime | HIGH | Implement graceful fallback, cache frequently used queries |
| High unexpected costs | HIGH | Budget caps per business, cost alerts, aggressive caching |
| Slow response times | MEDIUM | Async processing for non-critical features, optimize prompts |
| Token limit exceeded | LOW | Chunk large contexts, summarize before sending |

### Business Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Low adoption | MEDIUM | Free 10 credits, user education, prominent UI |
| Credit system too complex | MEDIUM | Simple UI, clear pricing, automatic alerts |
| Users exhaust credits fast | LOW | Set reasonable credit costs, offer bulk packs |
| Competition copies features | LOW | Continuous innovation, superior implementation |

---

## 📞 Questions for Backend Team

Before implementation begins, please clarify:

1. **Data Access:**
   - Which existing models/endpoints provide customer payment history?
   - How do we calculate "days overdue" - is this already computed?
   - Is there existing customer segmentation data we can leverage?

2. **Infrastructure:**
   - Current caching solution (Redis? Memcached?)?
   - Background job system for expensive AI operations (Celery? RQ?)?
   - Preferred OpenAI SDK version?

3. **Security:**
   - Current API authentication mechanism (will AI endpoints use same)?
   - GDPR compliance requirements?
   - Data retention policies?

4. **Integration:**
   - MOMO payment integration for credit purchases (existing or new)?
   - Notification system for low credit alerts (email? SMS? in-app)?
   - Admin dashboard framework (Django admin? Custom React?)?

5. **Deployment:**
   - Preferred deployment timeline?
   - Beta testing group?
   - Feature flag system available?

---

## 📚 Additional Resources

### OpenAI Documentation
- [API Reference](https://platform.openai.com/docs/api-reference)
- [Best Practices Guide](https://platform.openai.com/docs/guides/production-best-practices)
- [Token Counting](https://platform.openai.com/tokenizer)
- [Safety Guidelines](https://platform.openai.com/docs/guides/safety-best-practices)

### Cost Calculators
- [OpenAI Pricing](https://openai.com/pricing)
- [Token Calculator](https://platform.openai.com/tokenizer)

### Implementation Examples
- Sample prompts for each feature type
- Reference implementations available upon request

---

## ✅ Next Steps

1. **Backend Team Review** (1 week)
   - Review this document
   - Ask clarifying questions
   - Validate technical feasibility
   - Estimate development timeline

2. **Joint Planning Session** (1 day)
   - Frontend + Backend alignment
   - Finalize API contracts
   - Agree on phasing
   - Set sprint goals

3. **Implementation Kickoff** (Week 1)
   - Backend: Credit system + first endpoint
   - Frontend: Credit UI + first integration
   - Parallel development

4. **Weekly Syncs**
   - Progress updates
   - Blocker resolution
   - Cost monitoring
   - Performance optimization

---

## 📝 Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | Nov 7, 2025 | Frontend Team | Initial comprehensive documentation |

---

## 🤝 Sign-off Required

- [ ] Backend Team Lead - Technical feasibility confirmed
- [ ] Product Owner - Business requirements approved
- [ ] CTO - Architecture and cost model approved
- [ ] Finance - Pricing strategy approved

---

**END OF DOCUMENT**

Questions? Contact frontend team or schedule joint planning session.
