# Natural Language Query System - Complete Implementation Guide

**Feature:** AI-powered natural language interface for business insights  
**Priority:** High - User-friendly data access  
**Complexity:** Medium  
**Timeline:** 1-2 weeks

---

## 🎯 What This Feature Does

Allows users to ask questions in plain English instead of navigating complex reports:

```
Instead of this:
User → Reports → Sales → Filter by January → Sort by quantity → Export

Users do this:
User → "Which product sold the most in January?" → Get answer instantly
```

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    USER INTERFACE                       │
│  ┌───────────────────────────────────────────────┐    │
│  │ "Which product is fastest selling in January?"│    │
│  └───────────────────────────────────────────────┘    │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              BACKEND API ENDPOINT                       │
│  POST /ai/api/insights/query/                          │
│                                                         │
│  1. Parse user query                                   │
│  2. Determine query type (sales/inventory/customer)    │
│  3. Extract parameters (date range, filters)           │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│           DATA RETRIEVAL SERVICE                        │
│                                                         │
│  Query your actual database:                           │
│  - Sales.objects.filter(...)                           │
│  - Customer.objects.annotate(...)                      │
│  - Product.objects.aggregate(...)                      │
│                                                         │
│  Returns: Raw data (JSON)                              │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              OPENAI API CALL                            │
│                                                         │
│  Prompt: "User asked: {question}                       │
│           Here's the data: {data}                      │
│           Provide natural language answer"             │
│                                                         │
│  OpenAI analyzes and generates human answer            │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│              RESPONSE FORMATTER                         │
│                                                         │
│  - Add visualizations (charts, tables)                 │
│  - Suggest follow-up questions                         │
│  - Cache result                                        │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────┐
│                 RETURN TO USER                          │
│  Natural language answer + data visualization          │
└─────────────────────────────────────────────────────────┘
```

---

## 📁 Step 1: Create Query Intelligence Service

Create `app/ai_services/query_intelligence.py`:

```python
"""
AI-powered natural language query service
Converts user questions into database queries and generates insights
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from django.db.models import Sum, Count, Avg, F, Q
from django.utils import timezone
from openai import OpenAI
import json
import re

from sales.models import Sale, SaleItem
from inventory.models import Product
from accounts.models import Customer
from reports.models import CustomerSegment


class QueryType:
    """Query type constants"""
    SALES = "sales"
    PRODUCT = "product"
    CUSTOMER = "customer"
    INVENTORY = "inventory"
    FINANCIAL = "financial"
    GENERAL = "general"


class QueryIntelligenceService:
    """
    Intelligent query processor that:
    1. Understands natural language questions
    2. Fetches relevant data from database
    3. Uses OpenAI to generate human-readable insights
    """
    
    def __init__(self, business_id: str):
        self.business_id = business_id
        self.openai_client = OpenAI()
    
    def process_query(self, user_question: str) -> Dict[str, Any]:
        """
        Main entry point: Process user's natural language question
        
        Args:
            user_question: Plain English question from user
            
        Returns:
            Dict with answer, data, visualizations, and suggestions
        """
        
        # Step 1: Classify the query type
        query_info = self._classify_query(user_question)
        
        # Step 2: Extract parameters (dates, filters, etc.)
        params = self._extract_parameters(user_question, query_info)
        
        # Step 3: Fetch relevant data from database
        data = self._fetch_data(query_info, params)
        
        # Step 4: Generate AI answer
        ai_response = self._generate_answer(user_question, data, query_info)
        
        # Step 5: Format response with visualizations
        response = self._format_response(ai_response, data, query_info)
        
        return response
    
    def _classify_query(self, question: str) -> Dict[str, Any]:
        """
        Use OpenAI to classify the query type and intent
        
        Example:
        "Which product sold the most?" → {type: "product", intent: "top_selling"}
        "Show me customers who haven't bought in 3 months" → {type: "customer", intent: "churn_risk"}
        """
        
        classification_prompt = f"""
        Classify this business query:
        "{question}"
        
        Determine:
        1. query_type: sales, product, customer, inventory, or financial
        2. intent: What specifically they want (e.g., "top_selling", "trend_analysis", "comparison")
        3. metric: What to measure (revenue, quantity, profit, count, etc.)
        4. aggregation: sum, average, count, max, min, etc.
        
        Return JSON only:
        {{
            "query_type": "...",
            "intent": "...",
            "metric": "...",
            "aggregation": "..."
        }}
        """
        
        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a query classification expert. Return only valid JSON."},
                {"role": "user", "content": classification_prompt}
            ],
            temperature=0.3
        )
        
        result = json.loads(response.choices[0].message.content)
        return result
    
    def _extract_parameters(self, question: str, query_info: Dict) -> Dict[str, Any]:
        """
        Extract parameters like date ranges, product names, thresholds, etc.
        """
        
        params = {}
        question_lower = question.lower()
        
        # Extract date ranges
        if "january" in question_lower:
            params['start_date'] = datetime(timezone.now().year, 1, 1)
            params['end_date'] = datetime(timezone.now().year, 1, 31)
        elif "last month" in question_lower or "previous month" in question_lower:
            today = timezone.now()
            first_of_this_month = today.replace(day=1)
            params['end_date'] = first_of_this_month - timedelta(days=1)
            params['start_date'] = params['end_date'].replace(day=1)
        elif "this month" in question_lower:
            today = timezone.now()
            params['start_date'] = today.replace(day=1)
            params['end_date'] = today
        elif "last 30 days" in question_lower or "past month" in question_lower:
            params['end_date'] = timezone.now()
            params['start_date'] = params['end_date'] - timedelta(days=30)
        elif "last week" in question_lower:
            params['end_date'] = timezone.now()
            params['start_date'] = params['end_date'] - timedelta(days=7)
        elif "this week" in question_lower:
            today = timezone.now()
            params['start_date'] = today - timedelta(days=today.weekday())
            params['end_date'] = today
        elif "today" in question_lower:
            params['start_date'] = timezone.now().replace(hour=0, minute=0, second=0)
            params['end_date'] = timezone.now()
        elif "yesterday" in question_lower:
            yesterday = timezone.now() - timedelta(days=1)
            params['start_date'] = yesterday.replace(hour=0, minute=0, second=0)
            params['end_date'] = yesterday.replace(hour=23, minute=59, second=59)
        else:
            # Default: last 30 days
            params['end_date'] = timezone.now()
            params['start_date'] = params['end_date'] - timedelta(days=30)
        
        # Extract numbers (thresholds, limits, etc.)
        numbers = re.findall(r'\d+', question)
        if numbers:
            params['limit'] = int(numbers[0])  # Top N products, etc.
        else:
            params['limit'] = 10  # Default limit
        
        # Extract product category if mentioned
        # (You'd expand this based on your actual categories)
        categories = ['electronics', 'food', 'clothing', 'furniture', 'beverages']
        for category in categories:
            if category in question_lower:
                params['category'] = category.title()
                break
        
        return params
    
    def _fetch_data(self, query_info: Dict, params: Dict) -> Dict[str, Any]:
        """
        Fetch actual data from database based on query classification
        """
        
        query_type = query_info.get('query_type')
        intent = query_info.get('intent')
        
        if query_type == QueryType.PRODUCT:
            return self._fetch_product_data(intent, params)
        elif query_type == QueryType.SALES:
            return self._fetch_sales_data(intent, params)
        elif query_type == QueryType.CUSTOMER:
            return self._fetch_customer_data(intent, params)
        elif query_type == QueryType.INVENTORY:
            return self._fetch_inventory_data(intent, params)
        elif query_type == QueryType.FINANCIAL:
            return self._fetch_financial_data(intent, params)
        else:
            return self._fetch_general_data(params)
    
    def _fetch_product_data(self, intent: str, params: Dict) -> Dict[str, Any]:
        """Fetch product-related data"""
        
        start_date = params.get('start_date')
        end_date = params.get('end_date')
        limit = params.get('limit', 10)
        
        # Get top-selling products
        top_products = (
            SaleItem.objects
            .filter(
                sale__business_id=self.business_id,
                sale__created_at__gte=start_date,
                sale__created_at__lte=end_date,
                sale__status='COMPLETED'
            )
            .values('product__name', 'product__id')
            .annotate(
                total_quantity=Sum('quantity'),
                total_revenue=Sum(F('quantity') * F('price')),
                number_of_sales=Count('sale__id', distinct=True),
                avg_price=Avg('price')
            )
            .order_by('-total_quantity')[:limit]
        )
        
        return {
            'top_products': list(top_products),
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'total_products_analyzed': Product.objects.filter(
                business_id=self.business_id
            ).count()
        }
    
    def _fetch_sales_data(self, intent: str, params: Dict) -> Dict[str, Any]:
        """Fetch sales-related data"""
        
        start_date = params.get('start_date')
        end_date = params.get('end_date')
        
        # Overall sales summary
        sales_summary = (
            Sale.objects
            .filter(
                business_id=self.business_id,
                created_at__gte=start_date,
                created_at__lte=end_date,
                status='COMPLETED'
            )
            .aggregate(
                total_sales=Count('id'),
                total_revenue=Sum('total_amount'),
                total_profit=Sum('profit'),
                avg_sale_amount=Avg('total_amount')
            )
        )
        
        # Daily breakdown
        daily_sales = (
            Sale.objects
            .filter(
                business_id=self.business_id,
                created_at__gte=start_date,
                created_at__lte=end_date,
                status='COMPLETED'
            )
            .extra({'date': "date(created_at)"})
            .values('date')
            .annotate(
                sales_count=Count('id'),
                revenue=Sum('total_amount')
            )
            .order_by('date')
        )
        
        return {
            'summary': sales_summary,
            'daily_breakdown': list(daily_sales),
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        }
    
    def _fetch_customer_data(self, intent: str, params: Dict) -> Dict[str, Any]:
        """Fetch customer-related data"""
        
        limit = params.get('limit', 20)
        
        # Top customers by revenue
        top_customers = (
            Customer.objects
            .filter(business_id=self.business_id)
            .annotate(
                total_purchases=Count('sales'),
                total_spent=Sum('sales__total_amount'),
                last_purchase_date=Max('sales__created_at')
            )
            .order_by('-total_spent')[:limit]
        )
        
        # At-risk customers (haven't purchased in 90+ days)
        ninety_days_ago = timezone.now() - timedelta(days=90)
        at_risk = (
            Customer.objects
            .filter(business_id=self.business_id)
            .annotate(
                last_purchase=Max('sales__created_at'),
                total_purchases=Count('sales')
            )
            .filter(
                last_purchase__lt=ninety_days_ago,
                total_purchases__gt=0
            )[:limit]
        )
        
        return {
            'top_customers': [
                {
                    'name': c.name,
                    'total_spent': float(c.total_spent or 0),
                    'total_purchases': c.total_purchases,
                    'last_purchase': c.last_purchase_date.isoformat() if c.last_purchase_date else None
                }
                for c in top_customers
            ],
            'at_risk_customers': [
                {
                    'name': c.name,
                    'last_purchase': c.last_purchase.isoformat() if c.last_purchase else None,
                    'total_purchases': c.total_purchases
                }
                for c in at_risk
            ],
            'total_customers': Customer.objects.filter(business_id=self.business_id).count()
        }
    
    def _fetch_inventory_data(self, intent: str, params: Dict) -> Dict[str, Any]:
        """Fetch inventory-related data"""
        
        # Low stock items
        low_stock = (
            Product.objects
            .filter(
                business_id=self.business_id,
                quantity__lte=F('reorder_level')
            )
            .values('name', 'quantity', 'reorder_level', 'unit_cost')
            .order_by('quantity')[:20]
        )
        
        # Out of stock
        out_of_stock = (
            Product.objects
            .filter(business_id=self.business_id, quantity=0)
            .count()
        )
        
        # Total inventory value
        total_value = (
            Product.objects
            .filter(business_id=self.business_id)
            .aggregate(
                total_value=Sum(F('quantity') * F('unit_cost')),
                total_products=Count('id')
            )
        )
        
        return {
            'low_stock_items': list(low_stock),
            'out_of_stock_count': out_of_stock,
            'inventory_summary': total_value
        }
    
    def _fetch_financial_data(self, intent: str, params: Dict) -> Dict[str, Any]:
        """Fetch financial data"""
        
        start_date = params.get('start_date')
        end_date = params.get('end_date')
        
        # Revenue and profit
        financial_summary = (
            Sale.objects
            .filter(
                business_id=self.business_id,
                created_at__gte=start_date,
                created_at__lte=end_date,
                status='COMPLETED'
            )
            .aggregate(
                total_revenue=Sum('total_amount'),
                total_profit=Sum('profit'),
                total_cost=Sum('total_cost')
            )
        )
        
        # Calculate profit margin
        if financial_summary['total_revenue']:
            financial_summary['profit_margin'] = (
                (financial_summary['total_profit'] / financial_summary['total_revenue']) * 100
            )
        else:
            financial_summary['profit_margin'] = 0
        
        return {
            'summary': financial_summary,
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        }
    
    def _fetch_general_data(self, params: Dict) -> Dict[str, Any]:
        """Fetch general business metrics"""
        
        start_date = params.get('start_date')
        end_date = params.get('end_date')
        
        return {
            'business_summary': {
                'total_products': Product.objects.filter(business_id=self.business_id).count(),
                'total_customers': Customer.objects.filter(business_id=self.business_id).count(),
                'total_sales': Sale.objects.filter(
                    business_id=self.business_id,
                    created_at__gte=start_date,
                    created_at__lte=end_date
                ).count()
            },
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            }
        }
    
    def _generate_answer(
        self, 
        question: str, 
        data: Dict, 
        query_info: Dict
    ) -> Dict[str, Any]:
        """
        Use OpenAI to generate natural language answer
        """
        
        prompt = f"""
        You are a business intelligence assistant helping a retail/wholesale business owner understand their data.
        
        User Question: "{question}"
        
        Here is the relevant data from their database:
        {json.dumps(data, indent=2, default=str)}
        
        Provide a clear, concise answer that:
        1. Directly answers their question
        2. Highlights key insights
        3. Provides context (percentages, comparisons)
        4. Suggests actionable next steps
        5. Uses Ghanaian business context where relevant
        
        Format your response as JSON:
        {{
            "answer": "Main answer in 2-3 sentences",
            "key_insights": ["insight 1", "insight 2", "insight 3"],
            "recommendations": ["action 1", "action 2"],
            "data_summary": "Brief summary of what the data shows"
        }}
        """
        
        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a business intelligence assistant. Return only valid JSON."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        
        return json.loads(response.choices[0].message.content)
    
    def _format_response(
        self,
        ai_response: Dict,
        data: Dict,
        query_info: Dict
    ) -> Dict[str, Any]:
        """
        Format final response with visualizations and follow-up suggestions
        """
        
        # Suggest follow-up questions
        follow_ups = self._generate_follow_up_questions(query_info, data)
        
        # Determine visualization type
        viz_type = self._recommend_visualization(query_info, data)
        
        return {
            'answer': ai_response.get('answer'),
            'key_insights': ai_response.get('key_insights', []),
            'recommendations': ai_response.get('recommendations', []),
            'data_summary': ai_response.get('data_summary'),
            'raw_data': data,
            'visualization': {
                'type': viz_type,
                'data': self._prepare_viz_data(data, viz_type)
            },
            'follow_up_questions': follow_ups,
            'query_info': query_info
        }
    
    def _generate_follow_up_questions(
        self, 
        query_info: Dict, 
        data: Dict
    ) -> List[str]:
        """Generate intelligent follow-up questions"""
        
        query_type = query_info.get('query_type')
        
        suggestions = {
            QueryType.PRODUCT: [
                "Which products have the highest profit margins?",
                "Show me products that are running low on stock",
                "What's the average sale price for top products?"
            ],
            QueryType.SALES: [
                "How does this compare to last month?",
                "Which day of the week has the highest sales?",
                "Show me hourly sales patterns"
            ],
            QueryType.CUSTOMER: [
                "Which customers haven't bought in 90 days?",
                "Show me my VIP customers",
                "What products do my top customers buy?"
            ],
            QueryType.INVENTORY: [
                "Which products need immediate reordering?",
                "Show me slow-moving inventory",
                "What's my total inventory value?"
            ]
        }
        
        return suggestions.get(query_type, [
            "Show me sales trends for this month",
            "Which products are most profitable?",
            "How many customers do I have?"
        ])
    
    def _recommend_visualization(self, query_info: Dict, data: Dict) -> str:
        """Recommend appropriate visualization type"""
        
        intent = query_info.get('intent', '')
        
        if 'trend' in intent or 'over_time' in intent:
            return 'line_chart'
        elif 'top_' in intent or 'ranking' in intent:
            return 'bar_chart'
        elif 'comparison' in intent:
            return 'comparison_table'
        elif 'distribution' in intent:
            return 'pie_chart'
        else:
            return 'table'
    
    def _prepare_viz_data(self, data: Dict, viz_type: str) -> Dict:
        """Prepare data for frontend visualization"""
        
        # This would format data specifically for your chosen charting library
        # (e.g., Chart.js, Recharts, etc.)
        
        if viz_type == 'table':
            # Extract first data array found
            for key, value in data.items():
                if isinstance(value, list) and len(value) > 0:
                    return {'rows': value}
        
        return data
```

---

## 📁 Step 2: Create API Endpoint

Create `app/ai_views/query_views.py`:

```python
"""
API endpoints for natural language queries
"""

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.core.cache import cache
from django.utils import timezone
import hashlib

from app.ai_services.query_intelligence import QueryIntelligenceService
from subscriptions.ai_billing import AIBillingService
from subscriptions.models import BusinessAICredits


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def natural_language_query(request):
    """
    Process natural language business query
    
    Request:
    {
        "query": "Which product sold the most in January?",
        "context": "sales" (optional - helps AI understand better)
    }
    
    Response:
    {
        "answer": "Your fastest-selling product in January was...",
        "key_insights": [...],
        "recommendations": [...],
        "visualization": {...},
        "follow_up_questions": [...]
    }
    """
    
    business = request.user.business
    user_query = request.data.get('query', '').strip()
    
    # Validate input
    if not user_query:
        return Response(
            {'error': 'Query cannot be empty'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if len(user_query) > 500:
        return Response(
            {'error': 'Query too long. Please keep it under 500 characters.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check AI credits
    feature_name = 'customer_insight'
    credit_check = AIBillingService.check_credits(business.id, feature_name)
    
    if not credit_check['has_credits']:
        return Response({
            'error': 'insufficient_credits',
            'message': f'You need {credit_check["required"]} credits. Buy more to continue.',
            'current_balance': credit_check['current_balance'],
            'required_credits': credit_check['required']
        }, status=status.HTTP_402_PAYMENT_REQUIRED)
    
    # Check cache first (30 minutes)
    cache_key = f"ai_query_{business.id}_{hashlib.md5(user_query.encode()).hexdigest()}"
    cached_result = cache.get(cache_key)
    
    if cached_result:
        return Response({
            **cached_result,
            'cached': True,
            'credits_charged': 0
        })
    
    # Process query
    try:
        start_time = timezone.now()
        
        service = QueryIntelligenceService(business.id)
        result = service.process_query(user_query)
        
        end_time = timezone.now()
        response_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        # Charge credits
        billing_result = AIBillingService.charge_credits(
            business_id=business.id,
            user_id=request.user.id,
            feature='customer_insight',
            actual_openai_cost_usd=0.008,  # Approximate for gpt-4o-mini
            input_tokens=200,
            output_tokens=150,
            response_time_ms=response_time_ms,
            request_data={'query': user_query},
            response_summary={'answer_length': len(result.get('answer', ''))}
        )
        
        # Cache result
        cache.set(cache_key, result, timeout=1800)  # 30 minutes
        
        # Add billing info to response
        result['credits_charged'] = billing_result['credits_charged']
        result['new_balance'] = billing_result['new_balance']
        result['low_credit_warning'] = billing_result['low_credit_warning']
        result['cached'] = False
        
        return Response(result)
    
    except Exception as e:
        # Log error but don't charge credits
        AIBillingService.log_failed_transaction(
            business_id=business.id,
            user_id=request.user.id,
            feature='customer_insight',
            error_message=str(e),
            request_data={'query': user_query}
        )
        
        return Response({
            'error': 'query_processing_failed',
            'message': 'Unable to process your query. Please try again or rephrase.',
            'details': str(e) if settings.DEBUG else None
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def query_suggestions(request):
    """
    Get example queries to help users get started
    """
    
    suggestions = {
        'sales': [
            "What were my total sales this month?",
            "Which day had the highest sales last week?",
            "How do sales this month compare to last month?",
            "Show me sales trends for the last 30 days"
        ],
        'products': [
            "Which product is my top seller?",
            "What products sold the most in January?",
            "Show me products with the highest profit margins",
            "Which products need restocking?"
        ],
        'customers': [
            "Who are my top 10 customers?",
            "Which customers haven't bought anything in 90 days?",
            "Show me customers at risk of churning",
            "How many new customers did I get this month?"
        ],
        'inventory': [
            "What's my current inventory value?",
            "Which products are out of stock?",
            "Show me slow-moving inventory items",
            "What products should I reorder today?"
        ],
        'financial': [
            "What's my profit margin this month?",
            "How much profit did I make last week?",
            "Show me my expenses breakdown",
            "What's my average transaction value?"
        ]
    }
    
    return Response({
        'categories': suggestions,
        'tips': [
            "Be specific about time periods (e.g., 'in January', 'last 30 days')",
            "Ask one question at a time for better results",
            "You can ask follow-up questions to dive deeper"
        ]
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def query_history(request):
    """
    Get user's recent query history
    """
    
    business = request.user.business
    limit = int(request.query_params.get('limit', 20))
    
    from subscriptions.models import AITransaction
    
    recent_queries = AITransaction.objects.filter(
        business=business,
        feature='customer_insight',
        success=True
    ).order_by('-timestamp')[:limit]
    
    history = [
        {
            'id': str(transaction.id),
            'query': transaction.request_data.get('query', ''),
            'timestamp': transaction.timestamp.isoformat(),
            'credits_used': float(transaction.credits_charged)
        }
        for transaction in recent_queries
    ]
    
    return Response({
        'history': history,
        'total_queries': recent_queries.count()
    })
```

---

## 📁 Step 3: Add URL Routes

Add to `app/urls.py`:

```python
from django.urls import path
from app.ai_views import query_views

urlpatterns = [
    # ... existing urls ...
    
    # Natural Language Query
    path('ai/query/', query_views.natural_language_query, name='natural_language_query'),
    path('ai/query/suggestions/', query_views.query_suggestions, name='query_suggestions'),
    path('ai/query/history/', query_views.query_history, name='query_history'),
]
```

---

## 🎨 Step 4: Frontend Integration Example

```javascript
// Example React component

import React, { useState } from 'react';
import axios from 'axios';

function AIQueryBox() {
  const [query, setQuery] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const response = await axios.post('/ai/query/', {
        query: query
      });
      
      setResult(response.data);
    } catch (error) {
      console.error('Query failed:', error);
      alert(error.response?.data?.message || 'Query failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="ai-query-box">
      <h2>Ask Your Business Data</h2>
      
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g., Which product sold the most in January?"
          className="query-input"
        />
        <button type="submit" disabled={loading}>
          {loading ? 'Analyzing...' : 'Ask'}
        </button>
      </form>

      {result && (
        <div className="result-card">
          <div className="answer">
            <h3>Answer:</h3>
            <p>{result.answer}</p>
          </div>

          {result.key_insights && (
            <div className="insights">
              <h4>Key Insights:</h4>
              <ul>
                {result.key_insights.map((insight, idx) => (
                  <li key={idx}>{insight}</li>
                ))}
              </ul>
            </div>
          )}

          {result.recommendations && (
            <div className="recommendations">
              <h4>Recommendations:</h4>
              <ul>
                {result.recommendations.map((rec, idx) => (
                  <li key={idx}>{rec}</li>
                ))}
              </ul>
            </div>
          )}

          {result.follow_up_questions && (
            <div className="follow-ups">
              <h4>You might also want to ask:</h4>
              {result.follow_up_questions.map((question, idx) => (
                <button
                  key={idx}
                  onClick={() => setQuery(question)}
                  className="follow-up-btn"
                >
                  {question}
                </button>
              ))}
            </div>
          )}

          <div className="credits-info">
            Credits used: {result.credits_charged} | 
            Balance: {result.new_balance}
          </div>
        </div>
      )}
    </div>
  );
}

export default AIQueryBox;
```

---

## 💰 Cost & Pricing

**Cost per query:**
- OpenAI: ~$0.0005 (GHS 0.008)
- Your charge: 0.5 credits = GHS 0.50
- **Profit: GHS 0.492 (98% margin!)**

**Typical usage:**
- Light user: 20 queries/month = 10 credits = GHS 10
- Power user: 100 queries/month = 50 credits = GHS 50

---

## 🚀 Deployment Steps

### Week 1: Core Implementation
```bash
# Day 1-2: Set up service
1. Create QueryIntelligenceService class
2. Implement query classification
3. Test with OpenAI

# Day 3-4: Database queries
1. Implement data fetching methods
2. Test query performance
3. Add database indexes if needed

# Day 5: API endpoint
1. Create API views
2. Add credit checking
3. Test end-to-end
```

### Week 2: Polish & Launch
```bash
# Day 1-2: Optimization
1. Add caching
2. Optimize prompts
3. Reduce token usage

# Day 3-4: Testing
1. Test various query types
2. Handle edge cases
3. Beta testing with 5 users

# Day 5: Launch
1. Deploy to production
2. Monitor costs
3. Gather feedback
```

---

## 📊 Example Queries & Expected Results

### Query 1: "Which product sold the most in January?"

**What happens:**
1. System detects: Product query, January date range
2. Fetches: Top products for January from database
3. AI generates: Natural language answer

**Response:**
```json
{
  "answer": "Your fastest-selling product in January was Samsung 55\" TV with 127 units sold, generating GHS 152,400 in revenue. This represents a 34% increase compared to December.",
  "key_insights": [
    "Electronics category dominated January sales",
    "Average sale price was GHS 1,200 per unit",
    "Weekend sales were 2x higher than weekday sales"
  ],
  "recommendations": [
    "Stock up on electronics for February",
    "Consider bundling TVs with accessories",
    "Promote on weekends for maximum sales"
  ]
}
```

### Query 2: "Show me customers who haven't bought in 3 months"

**What happens:**
1. System detects: Customer churn query
2. Fetches: Customers with last purchase > 90 days ago
3. AI generates: Actionable insights

**Response:**
```json
{
  "answer": "You have 23 customers who haven't purchased in the last 3 months. These customers previously spent an average of GHS 8,500/month. Reaching out could recover GHS 195,500 in potential revenue.",
  "key_insights": [
    "Most at-risk customers are from wholesale segment",
    "Average customer lifetime value: GHS 45,000",
    "Win-back rate is typically 35% with proactive outreach"
  ],
  "recommendations": [
    "Send personalized win-back offers",
    "Call top 5 customers personally",
    "Offer 10% discount for next purchase"
  ]
}
```

---

## ⚡ Performance Optimization Tips

### 1. Smart Caching
```python
# Cache similar queries
cache_key = f"query_{business_id}_{query_hash}"
cache.set(cache_key, result, timeout=1800)  # 30 min
```

### 2. Database Indexing
```python
# Add indexes for common queries
class Meta:
    indexes = [
        models.Index(fields=['business', 'created_at']),
        models.Index(fields=['product', '-quantity']),
    ]
```

### 3. Limit Data Sent to OpenAI
```python
# Don't send all data - send summary
summary = {
    'top_10_products': [...],  # Not all 1000 products
    'summary_stats': {...}
}
```

### 4. Use Cheaper Models
```python
# gpt-4o-mini is 50x cheaper than GPT-4
model="gpt-4o-mini"  # $0.0006/1K tokens
```

---

## 🎯 Success Metrics

Track these to measure feature adoption:

- **Usage rate:** % of users who try the feature
- **Query success rate:** % of queries that produce good answers
- **Repeat usage:** Users who query >5 times/month
- **Cost per query:** Should stay < GHS 0.01
- **User satisfaction:** Gather feedback ratings

---

## 🔧 Troubleshooting

### Issue: OpenAI returns gibberish
**Solution:** Improve your prompts, add more context

### Issue: Queries are slow (>5 seconds)
**Solution:** Optimize database queries, add caching

### Issue: Costs are too high
**Solution:** Use gpt-4o-mini, cache aggressively, limit data sent

### Issue: AI misunderstands queries
**Solution:** Add more examples in classification prompt

---

## 📚 Next Steps

After launching basic natural language query:

1. **Add voice input** (optional)
2. **Multi-turn conversations** ("Tell me more about that")
3. **Scheduled queries** ("Send me top products report every Monday")
4. **Export results** (PDF, Excel)
5. **Share insights** (with team members)

---

**Ready to implement?** Start with the QueryIntelligenceService class and test with a few simple queries!

**Questions?** This is a powerful feature that will delight your users. Let me know if you need clarification on any part!
