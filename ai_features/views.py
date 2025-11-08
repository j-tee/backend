"""
AI Features Views
REST API endpoints for all AI-powered features.
"""

import time
import json
from decimal import Decimal
from typing import Dict, Any
from django.db.models import Sum, Count, Q, Avg
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.core.cache import cache
from django.utils import timezone

from .models import BusinessAICredits, AITransaction, AICreditPurchase
from .services import (
    AIBillingService, 
    InsufficientCreditsException, 
    QueryIntelligenceService, 
    get_openai_service, 
    OpenAIServiceError,
    PaystackService, 
    PaystackException,
    generate_payment_reference
)
from .serializers import (
    BusinessAICreditsSerializer,
    AITransactionSerializer,
    AICreditPurchaseSerializer,
    CreditPurchaseRequestSerializer,
    NaturalLanguageQuerySerializer,
    ProductDescriptionRequestSerializer,
    CreditAssessmentRequestSerializer,
    CollectionMessageRequestSerializer,
    InventoryForecastRequestSerializer,
    AIUsageStatsSerializer,
)
from sales.models import Customer, Sale, SaleItem
from inventory.models import Product


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_business_from_user(user):
    """
    Get business from user. Returns business or None.
    """
    return user.primary_business


def require_business(user):
    """
    Get business from user or raise error response.
    Returns (business, None) on success or (None, error_response) on failure.
    """
    business = get_business_from_user(user)
    if not business:
        error_response = Response(
            {
                'error': 'No business associated with your account',
                'message': 'Please contact support to link your account to a business.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )
        return None, error_response
    return business, None


# ============================================================================
# AI CREDIT MANAGEMENT ENDPOINTS
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_credit_balance(request):
    """
    Get current AI credit balance for authenticated user's business
    
    GET /ai/api/credits/balance/
    
    Response:
    {
        "balance": 45.50,
        "expires_at": "2026-05-07T10:00:00Z",
        "is_active": true,
        "days_until_expiry": 180
    }
    """
    business, error_response = require_business(request.user)
    if error_response:
        return error_response
    
    business_id = str(business.id)
    
    try:
        balance = AIBillingService.get_credit_balance(business_id)
        
        # Get credit details
        credits = BusinessAICredits.objects.filter(
            business_id=business_id,
            is_active=True
        ).first()
        
        if credits:
            serializer = BusinessAICreditsSerializer(credits)
            return Response(serializer.data)
        else:
            return Response({
                'balance': 0.00,
                'message': 'No active AI credits. Purchase credits to get started.'
            })
    
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def purchase_credits(request):
    """
    Purchase AI credits with tax calculation and Paystack payment
    
    POST /ai/api/credits/purchase/
    
    Request:
    {
        "package": "starter" | "value" | "premium" | "custom",
        "custom_amount": 50.00,  // Required if package="custom"
        "payment_method": "mobile_money" | "card",
        "callback_url": "https://frontend.com/payment/callback"  // Optional: Frontend callback URL
    }
    
    Packages:
    - starter: GHS 30 = 30 credits
    - value: GHS 80 = 100 credits (25% bonus)
    - premium: GHS 180 = 250 credits (39% bonus)
    
    Response:
    {
        "authorization_url": "https://checkout.paystack.com/...",
        "access_code": "xxx",
        "reference": "AI-CREDIT-xxx",
        "invoice": {
            "base_amount": 80.00,
            "taxes": [
                {"name": "VAT", "rate": 15.0, "amount": 12.00},
                {"name": "NHIL", "rate": 2.5, "amount": 2.00}
            ],
            "total_tax": 14.00,
            "total_amount": 94.00
        },
        "credits_to_add": 100.0
    }
    
    Note: If callback_url is not provided, defaults to {FRONTEND_URL}/payment/callback
    """
    from subscriptions.models import TaxConfiguration
    from datetime import date
    
    serializer = CreditPurchaseRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    business, error_response = require_business(request.user)
    if error_response:
        return error_response
    
    business_id = str(business.id)
    package = serializer.validated_data['package']
    payment_method = serializer.validated_data.get('payment_method', 'mobile_money')
    callback_url = serializer.validated_data.get('callback_url')
    
    # Define credit packages
    packages = {
        'starter': {'amount': Decimal('30.00'), 'credits': Decimal('30.00'), 'bonus': Decimal('0.00')},
        'value': {'amount': Decimal('80.00'), 'credits': Decimal('80.00'), 'bonus': Decimal('20.00')},
        'premium': {'amount': Decimal('180.00'), 'credits': Decimal('180.00'), 'bonus': Decimal('70.00')},
    }
    
    if package == 'custom':
        custom_amount = serializer.validated_data.get('custom_amount')
        if not custom_amount:
            return Response(
                {'error': 'custom_amount required for custom package'},
                status=status.HTTP_400_BAD_REQUEST
            )
        base_amount = custom_amount
        credits_purchased = custom_amount  # 1:1 ratio
        bonus_credits = Decimal('0.00')
    else:
        package_data = packages.get(package)
        if not package_data:
            return Response(
                {'error': 'Invalid package'},
                status=status.HTTP_400_BAD_REQUEST
            )
        base_amount = package_data['amount']
        credits_purchased = package_data['credits']
        bonus_credits = package_data['bonus']
    
    try:
        # Validate user email
        user_email = request.user.email
        if not user_email or '@' not in user_email or user_email == 'AnonymousUser':
            return Response(
                {
                    'error': 'invalid_email',
                    'message': 'A valid email address is required for payment processing. Please update your profile.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Calculate taxes
        today = date.today()
        active_taxes = TaxConfiguration.objects.filter(
            is_active=True,
            applies_to_subscriptions=True,  # Reuse subscription tax config
            effective_from__lte=today
        ).filter(
            Q(effective_until__isnull=True) | Q(effective_until__gte=today)
        ).order_by('calculation_order')
        
        tax_breakdown = []
        cumulative_amount = base_amount
        total_tax = Decimal('0.00')
        
        for tax in active_taxes:
            if tax.applies_to == 'SUBTOTAL':
                tax_base = base_amount
            else:  # CUMULATIVE
                tax_base = cumulative_amount
            
            tax_amount = (tax_base * tax.rate / Decimal('100')).quantize(Decimal('0.01'))
            cumulative_amount += tax_amount
            total_tax += tax_amount
            
            tax_breakdown.append({
                'tax_id': str(tax.id),
                'name': tax.name,
                'code': tax.code,
                'rate': float(tax.rate),
                'amount': float(tax_amount),
                'applies_to': tax.applies_to
            })
        
        total_amount = base_amount + total_tax
        
        # Generate unique payment reference
        payment_reference = generate_payment_reference()
        
        # Use provided callback_url or default to subscription callback (for consistency)
        from django.conf import settings
        if callback_url:
            paystack_callback_url = callback_url
        else:
            # Default to same callback as subscriptions for consistency
            # Frontend can detect payment type from reference prefix (AI-CREDIT-xxx vs SUB-xxx)
            paystack_callback_url = f'{settings.FRONTEND_URL}/app/subscription/payment/callback'
        
        # Initialize Paystack transaction
        paystack_response = PaystackService.initialize_transaction(
            email=request.user.email,
            amount=total_amount,  # Include taxes
            reference=payment_reference,
            metadata={
                'business_id': business_id,
                'user_id': str(request.user.id),
                'package': package,
                'base_amount': str(base_amount),
                'total_tax': str(total_tax),
                'credits_purchased': str(credits_purchased),
                'bonus_credits': str(bonus_credits),
                'purchase_type': 'ai_credits'
            },
            callback_url=paystack_callback_url
        )
        
        # Create pending purchase record with tax information
        AICreditPurchase.objects.create(
            business_id=business_id,
            user_id=str(request.user.id),
            amount_paid=total_amount,  # Total including taxes
            credits_purchased=credits_purchased,
            bonus_credits=bonus_credits,
            payment_reference=payment_reference,
            payment_method=payment_method,
            payment_status='pending',  # Will be updated after payment
            gateway_response={
                'base_amount': str(base_amount),
                'tax_breakdown': tax_breakdown,
                'total_tax': str(total_tax),
                'total_amount': str(total_amount)
            }
        )
        
        # Return Paystack authorization URL with invoice details
        return Response({
            'authorization_url': paystack_response['authorization_url'],
            'access_code': paystack_response['access_code'],
            'reference': payment_reference,
            'invoice': {
                'base_amount': float(base_amount),
                'taxes': tax_breakdown,
                'total_tax': float(total_tax),
                'total_amount': float(total_amount)
            },
            'credits_to_add': float(credits_purchased + bonus_credits),
            'package': package
        }, status=status.HTTP_200_OK)
    
    except PaystackException as e:
        return Response(
            {'error': 'payment_initialization_failed', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def verify_payment(request):
    """
    Verify Paystack payment and credit the account
    
    GET /ai/api/credits/verify/?reference=AI-CREDIT-xxx
    POST /ai/api/credits/verify/ with {"reference": "AI-CREDIT-xxx"}
    
    This endpoint is called:
    1. By frontend to verify payment (with authentication)
    2. As a manual verification endpoint
    
    Note: Paystack should redirect to FRONTEND callback page, not this backend API.
    """
    # Support both GET and POST, and both query params and body
    if request.method == 'GET':
        reference = request.GET.get('reference') or request.GET.get('trxref')
    else:
        reference = request.data.get('reference') or request.data.get('trxref')
    
    if not reference:
        return Response(
            {'error': 'reference parameter required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Verify payment with Paystack
        payment_data = PaystackService.verify_transaction(reference)
        
        # Check if payment was successful
        if payment_data['status'] != 'success':
            return Response({
                'status': 'failed',
                'message': 'Payment was not successful',
                'reference': reference
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get purchase record
        try:
            purchase = AICreditPurchase.objects.get(payment_reference=reference)
        except AICreditPurchase.DoesNotExist:
            return Response(
                {'error': 'Purchase record not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if already processed
        if purchase.payment_status == 'completed':
            # Already credited, just return success
            balance = AIBillingService.get_credit_balance(str(purchase.business_id))
            return Response({
                'status': 'success',
                'message': 'Payment already processed',
                'reference': reference,
                'credits_added': float(purchase.credits_purchased + purchase.bonus_credits),
                'current_balance': float(balance)
            })
        
        # Convert pesewas to GHS
        amount_paid_ghs = Decimal(str(payment_data['amount'])) / Decimal('100')
        
        # Add credits to business balance (don't create new purchase record, it already exists)
        from datetime import timedelta
        total_credits = purchase.credits_purchased + purchase.bonus_credits
        expires_at = timezone.now() + timedelta(days=180)
        
        # Get or create credit balance record
        from ai_features.models import BusinessAICredits
        credits, created = BusinessAICredits.objects.get_or_create(
            business_id=purchase.business_id,
            is_active=True,
            defaults={
                'balance': Decimal('0.00'),
                'expires_at': expires_at
            }
        )
        
        # Add new credits
        credits.balance += total_credits
        credits.expires_at = max(credits.expires_at, expires_at)  # Extend expiry if needed
        credits.save()
        
        # Clear cache
        from django.core.cache import cache
        cache_key = f"ai_credits_balance_{purchase.business_id}"
        cache.delete(cache_key)
        
        # Update purchase status
        purchase.payment_status = 'completed'
        purchase.completed_at = timezone.now()
        purchase.save()
        
        return Response({
            'status': 'success',
            'message': 'Payment verified and credits added successfully',
            'reference': reference,
            'credits_added': float(total_credits),
            'new_balance': float(credits.balance)
        })
    
    except PaystackException as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'PaystackException in verify_payment: {e}', exc_info=True)
        return Response(
            {'error': 'verification_failed', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    except Exception as e:
        import logging
        import traceback
        logger = logging.getLogger(__name__)
        logger.error(f'Exception in verify_payment: {e}', exc_info=True)
        logger.error(f'Traceback: {traceback.format_exc()}')
        return Response(
            {'error': str(e), 'type': type(e).__name__},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def paystack_webhook(request):
    """
    Handle Paystack webhook notifications
    
    POST /ai/api/webhooks/paystack/
    
    Paystack sends notifications for:
    - charge.success
    - charge.failed
    - transfer.success
    - etc.
    """
    # Verify webhook signature
    signature = request.headers.get('X-Paystack-Signature', '')
    
    if not PaystackService.verify_webhook_signature(request.body, signature):
        return Response(
            {'error': 'Invalid signature'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Parse webhook data
    data = request.data
    event = data.get('event')
    
    if event == 'charge.success':
        # Payment successful
        payment_data = data.get('data', {})
        reference = payment_data.get('reference')
        
        if not reference:
            return Response({'status': 'ignored'})
        
        try:
            # Get purchase record
            purchase = AICreditPurchase.objects.get(payment_reference=reference)
            
            # Check if already processed
            if purchase.payment_status == 'completed':
                return Response({'status': 'already_processed'})
            
            # Convert pesewas to GHS
            amount_paid_ghs = Decimal(str(payment_data['amount'])) / Decimal('100')
            
            # Credit the account
            AIBillingService.purchase_credits(
                business_id=str(purchase.business_id),
                amount_paid=amount_paid_ghs,
                credits_purchased=purchase.credits_purchased,
                payment_reference=reference,
                payment_method=purchase.payment_method,
                user_id=str(purchase.user_id),
                bonus_credits=purchase.bonus_credits
            )
            
            # Update purchase status
            purchase.payment_status = 'completed'
            purchase.completed_at = timezone.now()
            purchase.save()
            
            return Response({'status': 'success'})
        
        except AICreditPurchase.DoesNotExist:
            # Not an AI credit purchase, ignore
            return Response({'status': 'ignored'})
        
        except Exception as e:
            # Log error but return 200 to Paystack
            print(f"Webhook processing error: {str(e)}")
            return Response({'status': 'error', 'message': str(e)})
    
    # For other events, just acknowledge
    return Response({'status': 'received'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_usage_stats(request):
    """
    Get AI usage statistics for business
    
    GET /ai/api/usage/stats/?days=30
    
    Response:
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
            {"feature": "natural_language_query", "count": 80, "credits_used": 40.00},
            {"feature": "product_description", "count": 50, "credits_used": 5.00}
        ]
    }
    """
    business, error_response = require_business(request.user)
    if error_response:
        return error_response
    
    business_id = str(business.id)
    days = int(request.query_params.get('days', 30))
    
    try:
        stats = AIBillingService.get_usage_stats(business_id, days)
        serializer = AIUsageStatsSerializer(data=stats)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)
    
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_transactions(request):
    """Get AI transaction history"""
    business, error_response = require_business(request.user)
    if error_response:
        return error_response
    
    business_id = str(business.id)
    
    limit = int(request.query_params.get('limit', 50))
    feature = request.query_params.get('feature')
    
    transactions = AITransaction.objects.filter(business_id=business_id)
    
    if feature:
        transactions = transactions.filter(feature=feature)
    
    transactions = transactions.order_by('-timestamp')[:limit]
    serializer = AITransactionSerializer(transactions, many=True)
    
    return Response({
        'count': transactions.count(),
        'results': serializer.data
    })


# ============================================================================
# NATURAL LANGUAGE QUERY ENDPOINT
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def natural_language_query(request):
    """
    Process natural language business query
    
    POST /ai/api/query/
    
    Request:
    {
        "query": "How many Samsung TVs were sold between January and March?",
        "storefront_id": "uuid"  // Optional
    }
    
    Response:
    {
        "answer": "Based on your sales data, 127 Samsung TVs were sold between January and March 2025...",
        "query_type": "product",
        "data": {
            "products": [...]
        },
        "follow_up_questions": [...],
        "visualization_hints": {...},
        "credits_used": 0.50,
        "processing_time_ms": 1250
    }
    
    Cost: 0.5 credits
    """
    serializer = NaturalLanguageQuerySerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    business, error_response = require_business(request.user)
    if error_response:
        return error_response
    
    business_id = str(business.id)
    query = serializer.validated_data['query']
    storefront_id = serializer.validated_data.get('storefront_id')
    
    # Check credits
    credit_check = AIBillingService.check_credits(business_id, 'natural_language_query')
    if not credit_check['has_sufficient_credits']:
        return Response({
            'error': 'insufficient_credits',
            'message': 'You need 0.5 credits for this query. Purchase more to continue.',
            'current_balance': credit_check['current_balance'],
            'required_credits': credit_check['required_credits']
        }, status=status.HTTP_402_PAYMENT_REQUIRED)
    
    start_time = time.time()
    
    try:
        # Process query
        query_service = QueryIntelligenceService(
            business_id=business_id,
            storefront_id=str(storefront_id) if storefront_id else None
        )
        
        result = query_service.process_query(query)
        
        processing_time_ms = int((time.time() - start_time) * 1000)
        
        # Charge credits (estimate cost)
        actual_cost = Decimal('0.008')  # Estimated OpenAI cost
        
        billing_result = AIBillingService.charge_credits(
            business_id=business_id,
            feature='natural_language_query',
            actual_openai_cost=actual_cost,
            tokens_used=500,  # Estimate
            user_id=str(request.user.id),
            request_data={'query': query},
            response_summary=result['answer'][:200],
            processing_time_ms=processing_time_ms
        )
        
        # Add billing info to response
        result['credits_used'] = billing_result['credits_charged']
        result['new_balance'] = billing_result['new_balance']
        result['processing_time_ms'] = processing_time_ms
        
        return Response(result)
    
    except InsufficientCreditsException as e:
        return Response(
            {'error': 'insufficient_credits', 'message': str(e)},
            status=status.HTTP_402_PAYMENT_REQUIRED
        )
    except OpenAIServiceError as e:
        AIBillingService.log_failed_transaction(
            business_id=business_id,
            feature='natural_language_query',
            error_message=str(e),
            user_id=str(request.user.id),
            request_data={'query': query}
        )
        return Response(
            {
                'error': 'ai_provider_unavailable',
                'message': 'Our AI partner temporarily rejected the request. Please try again shortly.',
                'detail': str(e)
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    except Exception as e:
        AIBillingService.log_failed_transaction(
            business_id=business_id,
            feature='natural_language_query',
            error_message=str(e),
            user_id=str(request.user.id),
            request_data={'query': query}
        )
        return Response(
            {'error': 'processing_failed', 'message': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================================================
# PRODUCT DESCRIPTION GENERATOR
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_product_description(request):
    """
    Generate AI-powered product description
    
    POST /ai/api/products/generate-description/
    
    Request:
    {
        "product_id": "uuid",
        "tone": "professional" | "casual" | "technical" | "marketing",
        "language": "en" | "tw",
        "include_seo": true
    }
    
    Response:
    {
        "description": "Experience cinema-quality entertainment...",
        "short_description": "Samsung 55\" QLED TV with stunning picture...",
        "seo_keywords": ["samsung tv", "qled", "55 inch tv"],
        "meta_description": "Shop Samsung 55\" QLED TV...",
        "credits_used": 0.10
    }
    
    Cost: 0.1 credits
    """
    serializer = ProductDescriptionRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    business, error_response = require_business(request.user)
    if error_response:
        return error_response
    
    business_id = str(business.id)
    product_id = serializer.validated_data['product_id']
    tone = serializer.validated_data['tone']
    language = serializer.validated_data['language']
    include_seo = serializer.validated_data['include_seo']
    
    # Check credits
    credit_check = AIBillingService.check_credits(business_id, 'product_description')
    if not credit_check['has_sufficient_credits']:
        return Response({
            'error': 'insufficient_credits',
            'message': f'You need {credit_check["required_credits"]} credits. Current balance: {credit_check["current_balance"]}',
            'current_balance': credit_check['current_balance'],
            'required_credits': credit_check['required_credits']
        }, status=status.HTTP_402_PAYMENT_REQUIRED)
    
    try:
        # Get product
        product = Product.objects.get(id=product_id, business_id=business_id)
        
        # Check cache
        cache_key = f"product_desc_{product_id}_{tone}_{language}"
        cached = cache.get(cache_key)
        if cached:
            return Response(json.loads(cached))
        
        # Generate description
        openai_service = get_openai_service()
        
        system_prompt = f"""You are an expert product description writer.
Write a compelling product description in {language} language with a {tone} tone.
Return JSON with these fields:
{{
  "description": "Full product description (2-3 paragraphs)",
  "short_description": "One-line summary (max 100 chars)",
  "seo_keywords": ["keyword1", "keyword2", ...],
  "meta_description": "SEO meta description (max 160 chars)"
}}"""
        
        prompt = f"""Product: {product.name}
SKU: {product.sku}
Category: {product.category.name if product.category else 'General'}
Price: GHS {product.price}

Generate a {tone} product description."""
        
        result = openai_service.generate_json(
            prompt=prompt,
            system_prompt=system_prompt,
            feature='product_description',
            temperature=0.8
        )
        
        # Charge credits
        billing_result = AIBillingService.charge_credits(
            business_id=business_id,
            feature='product_description',
            actual_openai_cost=Decimal(str(result['cost_ghs'])),
            tokens_used=result['tokens']['total'],
            user_id=str(request.user.id),
            request_data={'product_id': str(product_id), 'tone': tone},
            response_summary=result['data'].get('short_description', '')[:200],
            processing_time_ms=result['processing_time_ms']
        )
        
        response_data = {
            **result['data'],
            'credits_used': billing_result['credits_charged'],
            'new_balance': billing_result['new_balance']
        }
        
        # Cache for 30 days
        cache.set(cache_key, json.dumps(response_data), 86400 * 30)
        
        return Response(response_data)
    
    except Product.DoesNotExist:
        return Response(
            {'error': 'Product not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        AIBillingService.log_failed_transaction(
            business_id=business_id,
            feature='product_description',
            error_message=str(e),
            user_id=str(request.user.id)
        )
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================================================
# SMART COLLECTIONS - COLLECTION MESSAGE GENERATOR
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_collection_message(request):
    """
    Generate personalized collection message for customer
    
    POST /ai/api/collections/message/
    
    Request:
    {
        "customer_id": "uuid",
        "message_type": "first_reminder" | "second_reminder" | "final_notice" | "payment_plan_offer",
        "tone": "professional_friendly" | "firm" | "formal_legal",
        "language": "en" | "tw",
        "include_payment_plan": false
    }
    
    Response:
    {
        "subject": "Friendly Reminder: Invoice #INV-2024-1234",
        "body": "Dear Mr. Mensah...",
        "sms_version": "Dear Mr. Mensah, gentle reminder...",
        "whatsapp_version": "Hello Mr. Mensah 👋...",
        "credits_used": 0.50
    }
    
    Cost: 0.5 credits
    """
    serializer = CollectionMessageRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    business, error_response = require_business(request.user)
    if error_response:
        return error_response
    
    business_id = str(business.id)
    customer_id = serializer.validated_data['customer_id']
    message_type = serializer.validated_data['message_type']
    tone = serializer.validated_data['tone']
    
    # Check credits
    credit_check = AIBillingService.check_credits(business_id, 'collection_message')
    if not credit_check['has_sufficient_credits']:
        return Response({
            'error': 'insufficient_credits',
            'message': f'You need {credit_check["required_credits"]} credits.',
            'current_balance': credit_check['current_balance']
        }, status=status.HTTP_402_PAYMENT_REQUIRED)
    
    try:
        # Get customer and outstanding sales
        customer = Customer.objects.get(id=customer_id, business_id=business_id)
        
        overdue_sales = Sale.objects.filter(
            customer=customer,
            status='CREDIT',
            is_paid=False,
            due_date__lt=timezone.now().date()
        ).order_by('due_date')
        
        # Build context
        total_overdue = sum(sale.amount_due for sale in overdue_sales)
        
        openai_service = get_openai_service()
        
        system_prompt = f"""You are a professional debt collection assistant for businesses in Ghana.
Generate a {tone} collection message for {message_type}.
Be culturally appropriate, respectful, and maintain business relationships.
Return JSON with: subject, body, sms_version, whatsapp_version"""
        
        prompt = f"""Customer: {customer.name}
Outstanding Balance: GHS {customer.outstanding_balance}
Overdue Amount: GHS {total_overdue}
Number of overdue invoices: {overdue_sales.count()}
Oldest overdue: {overdue_sales.first().due_date if overdue_sales.exists() else 'N/A'}

Generate {message_type} with {tone} tone."""
        
        result = openai_service.generate_json(
            prompt=prompt,
            system_prompt=system_prompt,
            feature='collection_message',
            temperature=0.7
        )
        
        # Charge credits
        billing_result = AIBillingService.charge_credits(
            business_id=business_id,
            feature='collection_message',
            actual_openai_cost=Decimal(str(result['cost_ghs'])),
            tokens_used=result['tokens']['total'],
            user_id=str(request.user.id),
            request_data={'customer_id': str(customer_id), 'message_type': message_type},
            processing_time_ms=result['processing_time_ms']
        )
        
        response_data = {
            **result['data'],
            'credits_used': billing_result['credits_charged'],
            'new_balance': billing_result['new_balance']
        }
        
        return Response(response_data)
    
    except Customer.DoesNotExist:
        return Response(
            {'error': 'Customer not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        AIBillingService.log_failed_transaction(
            business_id=business_id,
            feature='collection_message',
            error_message=str(e),
            user_id=str(request.user.id)
        )
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================================================
# SMART COLLECTIONS - CREDIT RISK ASSESSMENT
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assess_credit_risk(request):
    """
    AI-powered credit risk assessment for customer
    
    POST /ai/api/credit/assess/
    
    Request:
    {
        "customer_id": "uuid",
        "requested_credit_limit": 5000.00,
        "assessment_type": "new_credit" | "increase" | "renewal"
    }
    
    Response:
    {
        "customer": {...},
        "risk_score": 72,
        "risk_level": "MEDIUM",
        "recommendation": {
            "action": "APPROVE_PARTIAL",
            "suggested_limit": 3000.00,
            "confidence": 0.78
        },
        "analysis": {...},
        "credits_used": 3.00
    }
    
    Cost: 3.0 credits
    """
    serializer = CreditAssessmentRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    business, error_response = require_business(request.user)
    if error_response:
        return error_response
    
    business_id = str(business.id)
    customer_id = serializer.validated_data['customer_id']
    requested_limit = serializer.validated_data['requested_credit_limit']
    assessment_type = serializer.validated_data['assessment_type']
    
    # Check credits
    credit_check = AIBillingService.check_credits(business_id, 'credit_assessment')
    if not credit_check['has_sufficient_credits']:
        return Response({
            'error': 'insufficient_credits',
            'message': f'You need {credit_check["required_credits"]} credits.',
            'current_balance': credit_check['current_balance']
        }, status=status.HTTP_402_PAYMENT_REQUIRED)
    
    try:
        # Get customer with payment history
        customer = Customer.objects.get(id=customer_id, business_id=business_id)
        
        # Get payment statistics
        completed_sales = Sale.objects.filter(
            customer=customer,
            status__in=['COMPLETED', 'CREDIT'],
            is_paid=True
        )
        
        credit_sales = Sale.objects.filter(
            customer=customer,
            status='CREDIT'
        )
        
        total_purchases = completed_sales.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        avg_purchase = completed_sales.aggregate(Avg('total_amount'))['total_amount__avg'] or 0
        purchase_count = completed_sales.count()
        overdue_count = credit_sales.filter(is_paid=False, due_date__lt=timezone.now().date()).count()
        
        openai_service = get_openai_service()
        
        system_prompt = """You are a credit risk analyst for retail/wholesale businesses in Ghana.
Analyze customer data and provide credit risk assessment.
Return JSON with: risk_score (0-100), risk_level (LOW/MEDIUM/HIGH/CRITICAL),
recommendation (action, suggested_limit, confidence), analysis (positive_factors, risk_factors)"""
        
        prompt = f"""Assessment Type: {assessment_type}
Customer: {customer.name}
Current Credit Limit: GHS {customer.credit_limit}
Requested Limit: GHS {requested_limit}
Current Outstanding: GHS {customer.outstanding_balance}

Payment History:
- Total Purchases: GHS {total_purchases}
- Average Purchase: GHS {avg_purchase}
- Purchase Count: {purchase_count}
- Overdue Payments: {overdue_count}
- Customer Type: {customer.customer_type}
- Days Since First Purchase: {(timezone.now().date() - customer.created_at.date()).days if hasattr(customer, 'created_at') else 'Unknown'}

Provide detailed credit risk assessment."""
        
        result = openai_service.generate_json(
            prompt=prompt,
            system_prompt=system_prompt,
            feature='credit_assessment',
            temperature=0.3
        )
        
        # Charge credits
        billing_result = AIBillingService.charge_credits(
            business_id=business_id,
            feature='credit_assessment',
            actual_openai_cost=Decimal(str(result['cost_ghs'])),
            tokens_used=result['tokens']['total'],
            user_id=str(request.user.id),
            request_data={'customer_id': str(customer_id)},
            processing_time_ms=result['processing_time_ms']
        )
        
        response_data = {
            'customer': {
                'id': str(customer.id),
                'name': customer.name,
                'current_limit': float(customer.credit_limit),
                'requested_limit': float(requested_limit)
            },
            **result['data'],
            'credits_used': billing_result['credits_charged'],
            'new_balance': billing_result['new_balance']
        }
        
        return Response(response_data)
    
    except Customer.DoesNotExist:
        return Response(
            {'error': 'Customer not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        AIBillingService.log_failed_transaction(
            business_id=business_id,
            feature='credit_assessment',
            error_message=str(e),
            user_id=str(request.user.id)
        )
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================================================
# FEATURE AVAILABILITY CHECK
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_feature_availability(request):
    """
    Check if user has enough credits for a specific feature
    
    GET /ai/api/check-availability/?feature=natural_language_query
    
    Response:
    {
        "available": true,
        "feature": "natural_language_query",
        "cost": 0.50,
        "current_balance": 45.50
    }
    """
    feature = request.query_params.get('feature')
    
    if not feature:
        return Response(
            {'error': 'feature parameter required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    business, error_response = require_business(request.user)
    if error_response:
        return error_response
    
    business_id = str(business.id)
    
    credit_check = AIBillingService.check_credits(business_id, feature)
    
    return Response({
        'available': credit_check['has_sufficient_credits'],
        'feature': feature,
        'cost': credit_check['required_credits'],
        'current_balance': credit_check['current_balance'],
        'shortage': credit_check['shortage']
    })
