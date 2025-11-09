"""
AI Features Views
REST API endpoints for all AI-powered features.
"""

import time
import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, Optional, List
from django.db.models import Sum, Count, Q, Avg, F
from django.db.models.functions import TruncWeek
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.core.cache import cache
from django.utils import timezone
from subscriptions.permissions import RequiresActiveSubscription
from subscriptions.models import TaxConfiguration

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
    ReportNarrativeRequestSerializer,
    InventoryForecastRequestSerializer,
    AIUsageStatsSerializer,
)
from sales.models import Customer, Sale, SaleItem, AccountsReceivable
from inventory.models import Product, Warehouse, Category, StockProduct


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


def _build_ai_provider_error_message(error: Exception) -> str:
    """Return a concise, user-friendly message for AI provider failures."""
    error_text = str(error)

    if 'insufficient_quota' in error_text or '429' in error_text:
        return (
            "We temporarily ran out of AI capacity. No credits were deducted; please try again in a few minutes."
        )

    if '401' in error_text or 'Invalid authentication credentials' in error_text:
        return (
            "The AI provider rejected our request. No credits were deducted; please try again or contact support."
        )

    if 'timeout' in error_text.lower():
        return (
            "The AI service took too long to respond. No credits were deducted; please try again shortly."
        )

    if '500' in error_text or '502' in error_text or '503' in error_text:
        return (
            "The AI provider encountered an internal error. No credits were deducted; please try again later."
        )

    return "The AI service was unavailable. No credits were deducted; please try again later."


def _json_default(value: Any) -> Any:
    """JSON serializer for objects not serializable by default json code."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, '__str__'):
        return str(value)
    return value


def _prepare_json_for_prompt(payload: Any) -> str:
    """Serialize data into compact JSON suitable for LLM prompts."""
    return json.dumps(payload, default=_json_default, ensure_ascii=False, indent=2)


def _to_float(value: Optional[Any]) -> float:
    """Safely convert decimal-like values to float for JSON responses."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _respond_with_ai_provider_issue(
    *,
    business_id: str,
    feature: str,
    user_id: Optional[str],
    request_data: Optional[Dict[str, Any]],
    error: Exception,
    status_code: int = status.HTTP_503_SERVICE_UNAVAILABLE,
) -> Response:
    """Log and return a standardized response for upstream AI provider failures."""
    message = _build_ai_provider_error_message(error)
    AIBillingService.log_failed_transaction(
        business_id=business_id,
        feature=feature,
        error_message=str(error),
        user_id=user_id,
        request_data=request_data or {},
    )
    return Response(
        {'error': 'ai_provider_error', 'message': message},
        status=status_code
    )


def _respond_with_standard_ai_provider_error(
    *,
    business_id: str,
    feature: str,
    user_id: Optional[str],
    request_data: Optional[Dict[str, Any]],
    error: Exception,
) -> Response:
    """Wrapper for the common AI provider failure response."""
    return _respond_with_ai_provider_issue(
        business_id=business_id,
        feature=feature,
        user_id=user_id,
        request_data=request_data,
        error=error,
    )


# ============================================================================
# AI CREDIT MANAGEMENT
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_credit_balance(request):
    """Return the active AI credit balance for the authenticated business."""
    business, error_response = require_business(request.user)
    if error_response:
        return error_response

    business_id = str(business.id)

    try:
        credits = (
            BusinessAICredits.objects
            .filter(business_id=business_id, is_active=True)
            .order_by('-updated_at')
            .first()
        )

        if credits:
            serializer = BusinessAICreditsSerializer(credits)
            return Response(serializer.data)

        balance = AIBillingService.get_credit_balance(business_id)
        return Response({
            'balance': _to_float(balance),
            'message': 'No active AI credits. Purchase credits to get started.'
        })

    except Exception as exc:
        return Response(
            {'error': str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================================================
# CREDIT RISK ASSESSMENT
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated, RequiresActiveSubscription])
def assess_credit_risk(request):
    """Assess credit risk for a customer using business context and AI analysis."""
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

    credit_check = AIBillingService.check_credits(business_id, 'credit_assessment')
    if not credit_check['has_sufficient_credits']:
        return Response({
            'error': 'insufficient_credits',
            'message': f'You need {credit_check["required_credits"]} credits.',
            'current_balance': credit_check['current_balance']
        }, status=status.HTTP_402_PAYMENT_REQUIRED)

    try:
        customer = Customer.objects.get(id=customer_id, business_id=business_id)
    except Customer.DoesNotExist:
        return Response({
            'error': 'customer_not_found',
            'message': 'Customer does not exist or does not belong to your business'
        }, status=status.HTTP_404_NOT_FOUND)

    today = timezone.now().date()
    ninety_days_ago = today - timedelta(days=90)

    ar_qs = AccountsReceivable.objects.filter(customer=customer)
    current_balance = ar_qs.aggregate(
        total=Sum('amount_outstanding', filter=Q(amount_outstanding__gt=0))
    )['total'] or Decimal('0.00')

    outstanding_ratio = 0.0
    if customer.credit_limit and customer.credit_limit > 0:
        outstanding_ratio = float((current_balance / customer.credit_limit) * 100)

    total_ar_records = ar_qs.count()
    on_time_payments = 0
    recent_late_payments = 0
    for record in ar_qs:
        if record.due_date:
            if record.amount_outstanding <= 0 and record.updated_at.date() <= record.due_date:
                on_time_payments += 1
            if record.amount_outstanding > 0 and record.due_date < today and record.due_date >= ninety_days_ago:
                recent_late_payments += 1

    on_time_rate = (on_time_payments / total_ar_records * 100) if total_ar_records else 0.0

    sales_qs = Sale.objects.filter(customer=customer)
    first_sale = sales_qs.order_by('created_at').first()
    months_active = 0.0
    if first_sale:
        months_active = round((today - first_sale.created_at.date()).days / 30.0, 1)

    avg_order_value = sales_qs.aggregate(avg=Avg('total_amount'))['avg'] or Decimal('0.00')
    total_orders = sales_qs.count()

    comparable_customers = Customer.objects.filter(business_id=business_id).exclude(id=customer_id)
    avg_similar_limit = comparable_customers.aggregate(avg=Avg('credit_limit'))['avg'] or Decimal('0.00')

    comparable_ar = AccountsReceivable.objects.filter(customer__business_id=business_id).exclude(customer=customer)
    comparable_total = comparable_ar.count()
    comparable_defaults = comparable_ar.filter(status__in=['WRITTEN_OFF', 'IN_COLLECTION']).count()
    default_rate = (comparable_defaults / comparable_total * 100) if comparable_total else 0.0

    requested_increase_pct = 0.0
    if customer.credit_limit and customer.credit_limit > 0:
        requested_increase_pct = float(((requested_limit - customer.credit_limit) / customer.credit_limit) * 100)

    customer_profile = {
        'name': customer.name,
        'current_credit_limit': _to_float(customer.credit_limit),
        'current_balance': _to_float(current_balance),
        'utilization_pct': round(outstanding_ratio, 2),
        'months_active': months_active,
        'on_time_payment_rate': round(on_time_rate, 2),
        'total_transactions': total_ar_records,
        'avg_order_value': _to_float(avg_order_value),
        'total_orders': total_orders,
        'recent_late_payments': recent_late_payments,
        'customer_type': customer.customer_type,
        'requested_limit': _to_float(requested_limit),
        'requested_increase_pct': round(requested_increase_pct, 2),
    }

    benchmark = {
        'similar_customers_avg_limit': _to_float(avg_similar_limit),
        'default_rate_for_similar_profile': f"{default_rate:.1f}%",
    }

    context_payload = {
        'assessment_type': assessment_type,
        'customer': customer_profile,
        'benchmark': benchmark,
        'current_date': today.isoformat(),
    }

    system_prompt = f"""You are a credit risk assessment AI. Analyze customer credit applications and provide data-driven recommendations.

Assessment Type: {assessment_type}
Current Credit Limit: GHS {customer_profile['current_credit_limit']:.2f}
Requested Credit Limit: GHS {customer_profile['requested_limit']:.2f}

Provide the assessment as JSON with the following structure:
{{
  "risk_score": 0-100,
  "risk_level": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
  "recommendation": {{
    "action": "APPROVE_FULL" | "APPROVE_PARTIAL" | "DENY" | "REQUIRE_MORE_INFO",
    "suggested_limit": number,
    "suggested_terms_days": 15 | 30 | 45 | 60,
    "confidence": 0.0-1.0
  }},
  "analysis": {{
    "positive_factors": ["factor1", "factor2"],
    "risk_factors": ["risk1", "risk2"],
    "comparable_customers": {{
      "similar_approved_limit_avg": number,
      "default_rate_for_similar_profile": "X.X%"
    }}
  }},
  "conditions": ["condition1", "condition2"],
  "explanation": "Detailed explanation paragraph"
}}"""

    user_prompt = (
        "Assess credit risk for the customer using this data:\n"
        f"{_prepare_json_for_prompt(context_payload)}"
    )

    try:
        openai_service = get_openai_service()
        result = openai_service.generate_json(
            prompt=user_prompt,
            system_prompt=system_prompt,
            feature='credit_assessment',
            temperature=0.3
        )
    except OpenAIServiceError as e:
        return _respond_with_standard_ai_provider_error(
            business_id=business_id,
            feature='credit_assessment',
            user_id=str(request.user.id),
            request_data={
                'customer_id': str(customer_id),
                'assessment_type': assessment_type,
                'requested_credit_limit': _to_float(requested_limit),
            },
            error=e,
        )

    try:
        result_data = result.get('data', {}) if isinstance(result, dict) else {}

        risk_score_raw = result_data.get('risk_score', 0)
        try:
            risk_score = int(round(float(risk_score_raw)))
        except (TypeError, ValueError):
            risk_score = 0

        risk_level = result_data.get('risk_level', 'MEDIUM')

        recommendation = result_data.get('recommendation', {})
        if not isinstance(recommendation, dict):
            recommendation = {}

        analysis = result_data.get('analysis', {})
        if not isinstance(analysis, dict):
            analysis = {}

        conditions = result_data.get('conditions', [])
        if not isinstance(conditions, list):
            conditions = [str(conditions)] if conditions else []

        explanation = result_data.get('explanation', '')

        try:
            billing_result = AIBillingService.charge_credits(
                business_id=business_id,
                feature='credit_assessment',
                actual_openai_cost=Decimal(str(result.get('cost_ghs', 0))),
                tokens_used=int(result.get('tokens', {}).get('total', 0)),
                user_id=str(request.user.id),
                request_data={
                    'customer_id': str(customer_id),
                    'assessment_type': assessment_type,
                    'requested_credit_limit': _to_float(requested_limit),
                },
                response_summary=str(explanation)[:200],
                processing_time_ms=int(result.get('processing_time_ms', 0))
            )
        except InsufficientCreditsException as exc:
            return Response(
                {'error': 'insufficient_credits', 'message': str(exc)},
                status=status.HTTP_402_PAYMENT_REQUIRED
            )

        response_payload = {
            'customer': {
                'id': str(customer.id),
                'name': customer.name,
                'current_limit': _to_float(customer.credit_limit),
                'requested_limit': _to_float(requested_limit),
            },
            'risk_score': risk_score,
            'risk_level': risk_level,
            'recommendation': recommendation,
            'analysis': analysis,
            'conditions': conditions,
            'explanation': explanation,
            'credits_used': billing_result['credits_charged'],
            'new_balance': billing_result['new_balance'],
        }

        return Response(response_payload)

    except Exception as exc:  # pragma: no cover - guard against malformed AI output
        AIBillingService.log_failed_transaction(
            business_id=business_id,
            feature='credit_assessment',
            error_message=str(exc),
            user_id=str(request.user.id),
            request_data={
                'customer_id': str(customer_id),
                'assessment_type': assessment_type,
                'requested_credit_limit': _to_float(requested_limit),
            }
        )
        return Response(
            {'error': 'processing_failed', 'message': str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================================================
# REPORT NARRATIVE GENERATOR
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated, RequiresActiveSubscription])
def generate_report_narrative(request):
    """Generate executive summaries and insights for business reports."""
    serializer = ReportNarrativeRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    business, error_response = require_business(request.user)
    if error_response:
        return error_response

    business_id = str(business.id)
    report_type = serializer.validated_data['report_type']
    report_data = serializer.validated_data['report_data']

    credit_check = AIBillingService.check_credits(business_id, 'report_narrative')
    if not credit_check['has_sufficient_credits']:
        return Response({
            'error': 'insufficient_credits',
            'message': f'You need {credit_check["required_credits"]} credits.',
            'current_balance': credit_check['current_balance']
        }, status=status.HTTP_402_PAYMENT_REQUIRED)

    instructions_map = {
        'sales_summary': {
            'focus': 'revenue growth, transaction patterns, customer segments',
            'concerns': 'declining sales, low transaction value, revenue concentration risks',
        },
        'stock_levels': {
            'focus': 'inventory coverage, stockouts, overstock exposure',
            'concerns': 'critical stockouts, dead stock, negative trends in availability',
        },
        'revenue_profit': {
            'focus': 'profitability, margin erosion, cost drivers',
            'concerns': 'shrinking margins, high costs, unprofitable products or channels',
        },
        'ar_aging': {
            'focus': 'collection efficiency, overdue exposure, customer credit risk',
            'concerns': 'aging receivables, high DSO, high-risk customer segments',
        },
        'inventory_movement': {
            'focus': 'stock velocity, transfer performance, shrinkage trends',
            'concerns': 'slow movers, shrinkage, operational bottlenecks',
        },
        'general': {
            'focus': 'key highlights, material shifts, actionable takeaways',
            'concerns': 'data anomalies, negative performance, urgent risks',
        },
    }
    instructions = instructions_map.get(report_type, instructions_map['general'])

    system_prompt = (
        "You are a business intelligence analyst. Generate natural language narratives from business report data.\n\n"
        f"Report Type: {report_type}\n"
        f"Focus Areas: {instructions['focus']}\n"
        f"Watch For: {instructions['concerns']}\n\n"
        f"Report Data:\n{_prepare_json_for_prompt(report_data)}\n\n"
        "Return JSON with keys executive_summary, key_insights, trends, recommendations, alerts.\n"
        "Guidelines:\n"
        "- Use clear, concise language suitable for business leaders.\n"
        "- Reference exact metrics and time periods when available.\n"
        "- Highlight root causes and recommended actions.\n"
        "- Keep alerts limited to genuinely urgent issues."
    )

    user_prompt = "Analyze the report data and generate narrative insights."

    try:
        openai_service = get_openai_service()
        result = openai_service.generate_json(
            prompt=user_prompt,
            system_prompt=system_prompt,
            feature='report_narrative',
            temperature=0.5
        )
    except OpenAIServiceError as e:
        return _respond_with_standard_ai_provider_error(
            business_id=business_id,
            feature='report_narrative',
            user_id=str(request.user.id),
            request_data={'report_type': report_type},
            error=e,
        )

    try:
        result_data = result.get('data', {}) if isinstance(result, dict) else {}

        executive_summary = result_data.get('executive_summary', '')

        key_insights = result_data.get('key_insights', [])
        if not isinstance(key_insights, list):
            key_insights = [str(key_insights)] if key_insights else []

        trends = result_data.get('trends', [])
        if not isinstance(trends, list):
            trends = [str(trends)] if trends else []

        recommendations = result_data.get('recommendations', [])
        if not isinstance(recommendations, list):
            recommendations = [str(recommendations)] if recommendations else []

        alerts = result_data.get('alerts', [])
        if not isinstance(alerts, list):
            alerts = [str(alerts)] if alerts else []

        try:
            billing_result = AIBillingService.charge_credits(
                business_id=business_id,
                feature='report_narrative',
                actual_openai_cost=Decimal(str(result.get('cost_ghs', 0))),
                tokens_used=int(result.get('tokens', {}).get('total', 0) if isinstance(result.get('tokens', {}), dict) else 0),
                user_id=str(request.user.id),
                request_data={'report_type': report_type},
                response_summary=str(executive_summary)[:200],
                processing_time_ms=int(result.get('processing_time_ms', 0))
            )
        except InsufficientCreditsException as exc:
            return Response(
                {'error': 'insufficient_credits', 'message': str(exc)},
                status=status.HTTP_402_PAYMENT_REQUIRED
            )

        response_payload = {
            'report_type': report_type,
            'executive_summary': executive_summary,
            'key_insights': key_insights,
            'trends': trends,
            'recommendations': recommendations,
            'alerts': alerts,
            'credits_used': billing_result['credits_charged'],
            'new_balance': billing_result['new_balance'],
        }

        return Response(response_payload)

    except Exception as exc:  # pragma: no cover - guard against malformed AI output
        AIBillingService.log_failed_transaction(
            business_id=business_id,
            feature='report_narrative',
            error_message=str(exc),
            user_id=str(request.user.id),
            request_data={'report_type': report_type}
        )
        return Response(
            {'error': 'processing_failed', 'message': str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================================================
# INVENTORY FORECASTING
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated, RequiresActiveSubscription])
def generate_inventory_forecast(request):
    """Forecast inventory risks and reorder recommendations."""
    serializer = InventoryForecastRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    business, error_response = require_business(request.user)
    if error_response:
        return error_response

    business_id = str(business.id)
    warehouse_id = serializer.validated_data.get('warehouse_id')
    category_id = serializer.validated_data.get('category_id')
    forecast_days = serializer.validated_data.get('forecast_days', 30)

    credit_check = AIBillingService.check_credits(business_id, 'inventory_forecast')
    if not credit_check['has_sufficient_credits']:
        return Response({
            'error': 'insufficient_credits',
            'message': f'You need {credit_check["required_credits"]} credits.',
            'current_balance': credit_check['current_balance']
        }, status=status.HTTP_402_PAYMENT_REQUIRED)

    warehouse = None
    if warehouse_id:
        try:
            warehouse = Warehouse.objects.get(id=warehouse_id)
        except Warehouse.DoesNotExist:
            return Response(
                {'error': 'warehouse_not_found', 'message': 'Warehouse does not exist.'},
                status=status.HTTP_404_NOT_FOUND
            )

    category = None
    if category_id:
        try:
            category = Category.objects.get(id=category_id)
        except Category.DoesNotExist:
            return Response(
                {'error': 'category_not_found', 'message': 'Category does not exist.'},
                status=status.HTTP_404_NOT_FOUND
            )

    products_qs = Product.objects.filter(business_id=business_id, is_active=True)
    if category:
        products_qs = products_qs.filter(category=category)
    if warehouse:
        products_qs = products_qs.filter(stock_items__warehouse=warehouse)

    products_qs = products_qs.distinct().order_by('name')

    analysis_start = timezone.now() - timedelta(days=90)
    forecasts_context: List[Dict[str, Any]] = []

    for product in products_qs[:100]:
        stock_items = product.stock_items
        if warehouse:
            stock_items = stock_items.filter(warehouse=warehouse)

        stock_totals = stock_items.aggregate(total=Sum('calculated_quantity'))['total'] or 0
        current_stock = float(stock_totals) if stock_totals is not None else 0.0

        reorder_point = getattr(product, 'reorder_point', None)
        if reorder_point is None:
            reorder_point = getattr(product, 'minimum_stock', None)
        if reorder_point is None:
            reorder_point = 10

        sales_qs = SaleItem.objects.filter(product=product, sale__created_at__gte=analysis_start)
        if warehouse:
            sales_qs = sales_qs.filter(stock_product__warehouse=warehouse)

        weekly_sales = list(
            sales_qs.annotate(week=TruncWeek('sale__created_at'))
            .values('week')
            .annotate(units_sold=Sum('quantity'))
            .order_by('week')
        )

        if not weekly_sales:
            continue

        total_weeks = max(1, int((timezone.now() - analysis_start).days / 7))
        total_units = sum(float(item['units_sold']) for item in weekly_sales)
        weekly_velocity = round(total_units / total_weeks, 2)

        if len(weekly_sales) >= 4:
            midpoint = len(weekly_sales) // 2
            first_avg = sum(float(item['units_sold']) for item in weekly_sales[:midpoint]) / max(midpoint, 1)
            second_avg = sum(float(item['units_sold']) for item in weekly_sales[midpoint:]) / max(len(weekly_sales) - midpoint, 1)
            if second_avg > first_avg * 1.2:
                trend = 'increasing'
            elif second_avg < first_avg * 0.8:
                trend = 'decreasing'
            else:
                trend = 'stable'
        else:
            trend = 'stable'

        sales_history = [
            {
                'week_start': item['week'].date().isoformat() if item['week'] else None,
                'units_sold': round(float(item['units_sold']), 2),
            }
            for item in weekly_sales
        ]

        unit_cost = 0.0
        try:
            unit_cost = _to_float(product.get_latest_cost(warehouse=warehouse))
        except TypeError:
            unit_cost = _to_float(product.get_latest_cost())

        forecasts_context.append({
            'product_id': str(product.id),
            'product_name': product.name,
            'sku': product.sku,
            'current_stock': round(current_stock, 2),
            'reorder_point': float(reorder_point),
            'weekly_velocity': weekly_velocity,
            'trend': trend,
            'sales_history': sales_history,
            'unit_cost': unit_cost,
        })

        if len(forecasts_context) >= 50:
            break

    if not forecasts_context:
        return Response(
            {
                'error': 'insufficient_data',
                'message': 'Not enough inventory and sales data to generate a forecast.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    forecast_input = {
        'forecast_days': forecast_days,
        'products': forecasts_context,
    }

    system_prompt = (
        "You are an inventory forecasting AI. Analyze sales patterns and predict stockouts.\n\n"
        "For each product, calculate predicted_stockout_date, days_until_stockout, recommended_reorder_quantity, "
        "recommended_reorder_date, confidence_score (0-1), seasonality_factor, and risk_level (critical/high/medium/low).\n"
        "Assume supplier lead time is 7 days and safety stock equals one week of demand.\n"
        "Return JSON with a 'forecasts' array containing the calculated fields for each product."
    )

    user_prompt = (
        f"Forecast inventory for {forecast_days} days using the following data:\n"
        f"{_prepare_json_for_prompt(forecast_input)}"
    )

    try:
        openai_service = get_openai_service()
        result = openai_service.generate_json(
            prompt=user_prompt,
            system_prompt=system_prompt,
            feature='inventory_forecast',
            temperature=0.3
        )
    except OpenAIServiceError as e:
        return _respond_with_standard_ai_provider_error(
            business_id=business_id,
            feature='inventory_forecast',
            user_id=str(request.user.id),
            request_data={
                'warehouse_id': str(warehouse_id) if warehouse_id else None,
                'category_id': str(category_id) if category_id else None,
                'forecast_days': forecast_days,
            },
            error=e,
        )

    try:
        result_data = result.get('data', {}) if isinstance(result, dict) else {}
        ai_forecasts = result_data.get('forecasts', [])
        if not isinstance(ai_forecasts, list):
            ai_forecasts = []

        context_map = {item['product_id']: item for item in forecasts_context}
        final_forecasts: List[Dict[str, Any]] = []
        total_reorder_value = Decimal('0.00')

        def _as_float(value: Any) -> float:
            try:
                return float(value)
            except (TypeError, ValueError):
                return 0.0

        def _as_int(value: Any) -> int:
            try:
                return int(round(float(value)))
            except (TypeError, ValueError):
                return 0

        for entry in ai_forecasts:
            product_id = entry.get('product_id')
            if not product_id or product_id not in context_map:
                continue

            context_item = context_map[product_id]

            recommended_qty = _as_float(entry.get('recommended_reorder_quantity', 0))
            days_until_stockout = _as_int(entry.get('days_until_stockout', 0))
            confidence_score = round(_as_float(entry.get('confidence_score', 0.0)), 2)
            seasonality_factor = round(_as_float(entry.get('seasonality_factor', 1.0)), 2)
            risk_level = (entry.get('risk_level') or 'low').lower()

            unit_cost_decimal = Decimal(str(context_item.get('unit_cost', 0.0)))
            total_reorder_value += unit_cost_decimal * Decimal(str(recommended_qty))

            final_forecasts.append({
                'product_id': product_id,
                'product_name': context_item['product_name'],
                'sku': context_item['sku'],
                'current_stock': context_item['current_stock'],
                'reorder_point': context_item['reorder_point'],
                'predicted_stockout_date': entry.get('predicted_stockout_date'),
                'days_until_stockout': days_until_stockout,
                'recommended_reorder_quantity': round(recommended_qty, 2),
                'recommended_reorder_date': entry.get('recommended_reorder_date'),
                'confidence_score': confidence_score,
                'weekly_sales_velocity': context_item['weekly_velocity'],
                'trend': context_item['trend'],
                'seasonality_factor': seasonality_factor,
                'risk_level': risk_level,
            })

        summary = {
            'critical_items': len([f for f in final_forecasts if f['risk_level'] == 'critical']),
            'high_risk_items': len([f for f in final_forecasts if f['risk_level'] == 'high']),
            'medium_risk_items': len([f for f in final_forecasts if f['risk_level'] == 'medium']),
            'low_risk_items': len([f for f in final_forecasts if f['risk_level'] == 'low']),
            'total_recommended_reorder_value': float(total_reorder_value.quantize(Decimal('0.01')))
        }

        products_at_risk = len([f for f in final_forecasts if f['risk_level'] in ('critical', 'high')])

        try:
            billing_result = AIBillingService.charge_credits(
                business_id=business_id,
                feature='inventory_forecast',
                actual_openai_cost=Decimal(str(result.get('cost_ghs', 0))),
                tokens_used=int(result.get('tokens', {}).get('total', 0) if isinstance(result.get('tokens', {}), dict) else 0),
                user_id=str(request.user.id),
                request_data={
                    'warehouse_id': str(warehouse_id) if warehouse_id else None,
                    'category_id': str(category_id) if category_id else None,
                    'forecast_days': forecast_days,
                },
                response_summary=f"Forecasted {len(final_forecasts)} products",
                processing_time_ms=int(result.get('processing_time_ms', 0))
            )
        except InsufficientCreditsException as exc:
            return Response(
                {'error': 'insufficient_credits', 'message': str(exc)},
                status=status.HTTP_402_PAYMENT_REQUIRED
            )

        response_payload = {
            'forecast_period_days': forecast_days,
            'total_products_analyzed': len(forecasts_context),
            'products_at_risk': products_at_risk,
            'forecasts': final_forecasts,
            'summary': summary,
            'credits_used': billing_result['credits_charged'],
            'new_balance': billing_result['new_balance'],
        }

        return Response(response_payload)

    except Exception as exc:  # pragma: no cover - guard against malformed AI output
        AIBillingService.log_failed_transaction(
            business_id=business_id,
            feature='inventory_forecast',
            error_message=str(exc),
            user_id=str(request.user.id),
            request_data={
                'warehouse_id': str(warehouse_id) if warehouse_id else None,
                'category_id': str(category_id) if category_id else None,
                'forecast_days': forecast_days,
            }
        )
        return Response(
            {'error': 'processing_failed', 'message': str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================================================
# CREDIT PURCHASE FLOW
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def purchase_credits(request):
    """Initialize an AI credit purchase request via Paystack."""
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

    packages = {
        'starter': {'amount': Decimal('30.00'), 'credits': Decimal('30.00'), 'bonus': Decimal('0.00')},
        'value': {'amount': Decimal('80.00'), 'credits': Decimal('80.00'), 'bonus': Decimal('20.00')},
        'premium': {'amount': Decimal('180.00'), 'credits': Decimal('180.00'), 'bonus': Decimal('70.00')},
    }

    if package == 'custom':
        custom_amount = serializer.validated_data.get('custom_amount')
        if custom_amount is None:
            return Response(
                {
                    'error': 'custom_amount_required',
                    'message': 'Provide custom_amount when selecting the custom package.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        base_amount = custom_amount.quantize(Decimal('0.01'))
        credits_purchased = base_amount
        bonus_credits = Decimal('0.00')
    else:
        package_data = packages.get(package)
        if not package_data:
            return Response(
                {'error': 'invalid_package', 'message': 'Unsupported package selected.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        base_amount = package_data['amount']
        credits_purchased = package_data['credits']
        bonus_credits = package_data['bonus']

    if not request.user.email:
        return Response(
            {
                'error': 'missing_email',
                'message': 'A valid email address is required for payment processing. Please update your profile.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        today = date.today()
        active_taxes = TaxConfiguration.objects.filter(
            is_active=True,
            applies_to_subscriptions=True,
            effective_from__lte=today
        ).filter(
            Q(effective_until__isnull=True) | Q(effective_until__gte=today)
        ).order_by('calculation_order')

        tax_breakdown: List[Dict[str, Any]] = []
        cumulative_amount = base_amount
        total_tax = Decimal('0.00')

        for tax in active_taxes:
            tax_base = base_amount if tax.applies_to == 'SUBTOTAL' else cumulative_amount
            tax_amount = (tax_base * tax.rate / Decimal('100')).quantize(Decimal('0.01'))
            cumulative_amount += tax_amount
            total_tax += tax_amount

            tax_breakdown.append({
                'tax_id': str(tax.id),
                'name': tax.name,
                'code': tax.code,
                'rate': float(tax.rate),
                'amount': float(tax_amount),
                'applies_to': tax.applies_to,
            })

        total_amount = base_amount + total_tax
        payment_reference = generate_payment_reference()

        from django.conf import settings
        paystack_callback_url = callback_url or f'{settings.FRONTEND_URL}/app/subscription/payment/callback'

        paystack_response = PaystackService.initialize_transaction(
            email=request.user.email,
            amount=total_amount,
            reference=payment_reference,
            metadata={
                'business_id': business_id,
                'user_id': str(request.user.id),
                'package': package,
                'base_amount': str(base_amount),
                'total_tax': str(total_tax),
                'credits_purchased': str(credits_purchased),
                'bonus_credits': str(bonus_credits),
                'purchase_type': 'ai_credits',
            },
            callback_url=paystack_callback_url
        )

        AICreditPurchase.objects.create(
            business_id=business_id,
            user_id=str(request.user.id),
            amount_paid=total_amount,
            credits_purchased=credits_purchased,
            bonus_credits=bonus_credits,
            payment_reference=payment_reference,
            payment_method=payment_method,
            payment_status='pending',
            gateway_response={
                'base_amount': str(base_amount),
                'tax_breakdown': tax_breakdown,
                'total_tax': str(total_tax),
                'total_amount': str(total_amount),
            }
        )

        return Response({
            'authorization_url': paystack_response['authorization_url'],
            'access_code': paystack_response['access_code'],
            'reference': payment_reference,
            'invoice': {
                'base_amount': float(base_amount),
                'taxes': tax_breakdown,
                'total_tax': float(total_tax),
                'total_amount': float(total_amount),
            },
            'credits_to_add': float(credits_purchased + bonus_credits),
            'package': package,
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
        return _respond_with_ai_provider_issue(
            business_id=business_id,
            feature='natural_language_query',
            user_id=str(request.user.id),
            request_data={'query': query},
            error=e,
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
@permission_classes([IsAuthenticated, RequiresActiveSubscription])
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
        product = Product.objects.select_related('category').get(id=product_id, business_id=business_id)
    except Product.DoesNotExist:
        return Response({
            'error': 'product_not_found',
            'message': 'Product does not exist or does not belong to your business'
        }, status=status.HTTP_404_NOT_FOUND)

    cache_key = f"product_desc_{product_id}_{tone}_{language}_{int(include_seo)}"
    cached = cache.get(cache_key)
    if cached:
        return Response(json.loads(cached))

    tone_instructions = {
        'professional': 'Write in a professional, business-appropriate tone.',
        'casual': 'Write in a friendly, conversational tone with light personality.',
        'technical': 'Write with technical precision, highlighting specifications and performance details.',
        'marketing': 'Write persuasively with emotional appeal and benefits-focused messaging.',
    }

    language_instructions = {
        'en': 'Write in English with clear, customer-friendly language.',
        'tw': 'Write in Twi (Ghanaian language) using respectful and culturally appropriate expressions.',
    }

    seo_instruction = (
        'Include SEO keywords and an SEO meta description that help the product rank for relevant searches.'
        if include_seo else
        'Set seo_keywords to an empty array and meta_description to an empty string because SEO metadata is disabled for this request.'
    )

    latest_stock: Optional[StockProduct] = product.stock_items.order_by('-created_at').first()
    retail_price = _to_float(getattr(latest_stock, 'retail_price', None)) if latest_stock else 0.0
    wholesale_price = _to_float(getattr(latest_stock, 'wholesale_price', None)) if latest_stock else 0.0

    product_info = {
        'name': product.name,
        'category': product.category.name if getattr(product, 'category', None) else 'Uncategorized',
        'unit': getattr(product, 'unit', 'unit'),
        'sku': product.sku,
        'existing_description': (product.description or '').strip(),
        'retail_price': retail_price if retail_price else None,
        'wholesale_price': wholesale_price if wholesale_price else None,
    }

    price_line = 'N/A'
    if product_info['retail_price']:
        price_line = f"GHS {product_info['retail_price']:.2f} retail"
    elif product_info['wholesale_price']:
        price_line = f"GHS {product_info['wholesale_price']:.2f} wholesale"

    system_prompt = (
        "You are a professional product copywriter. Generate compelling product descriptions for e-commerce.\n\n"
        f"{tone_instructions[tone]}\n"
        f"{language_instructions[language]}\n"
        f"{seo_instruction}\n\n"
        "Format your response as JSON with these fields:\n"
        "- description: Full product description (2-3 paragraphs, 150-200 words)\n"
        "- short_description: One-sentence summary (max 80 characters)\n"
        "- seo_keywords: Array of 5-8 relevant keywords\n"
        "- meta_description: SEO meta description (150-160 characters)"
    )

    keywords_hint = 'N/A'

    user_prompt = (
        f"Business Name: {business.name}\n"
        f"Product Name: {product_info['name']}\n"
        f"Category: {product_info['category']}\n"
        f"Unit: {product_info['unit']}\n"
        f"SKU: {product_info['sku']}\n"
        f"Price: {price_line}\n"
        f"Existing Description: {product_info['existing_description'] or 'None'}\n"
        f"Tone: {tone}\n"
        f"Language: {language}\n"
        "\nGenerate a product description. Include these keywords if relevant: "
        f"{keywords_hint}"
    )

    try:
        openai_service = get_openai_service()
        result = openai_service.generate_json(
            prompt=user_prompt,
            system_prompt=system_prompt,
            feature='product_description',
            temperature=0.7
        )
    except OpenAIServiceError as e:
        return _respond_with_standard_ai_provider_error(
            business_id=business_id,
            feature='product_description',
            user_id=str(request.user.id),
            request_data={
                'product_id': str(product_id),
                'tone': tone,
                'language': language,
                'include_seo': include_seo,
            },
            error=e,
        )

    try:
        result_data = result.get('data', {}) if isinstance(result, dict) else {}

        description = result_data.get('description', '')
        short_description = result_data.get('short_description', '')
        meta_description = result_data.get('meta_description', '')
        seo_keywords: List[str] = result_data.get('seo_keywords', [])

        if not isinstance(seo_keywords, list):
            seo_keywords = [str(seo_keywords)] if seo_keywords else []

        if not include_seo:
            seo_keywords = []
            meta_description = ''

        try:
            billing_result = AIBillingService.charge_credits(
                business_id=business_id,
                feature='product_description',
                actual_openai_cost=Decimal(str(result.get('cost_ghs', 0))),
                tokens_used=int(result.get('tokens', {}).get('total', 0)),
                user_id=str(request.user.id),
                request_data={
                    'product_id': str(product_id),
                    'tone': tone,
                    'language': language,
                    'include_seo': include_seo,
                },
                response_summary=description[:200],
                processing_time_ms=int(result.get('processing_time_ms', 0))
            )
        except InsufficientCreditsException as exc:
            return Response(
                {'error': 'insufficient_credits', 'message': str(exc)},
                status=status.HTTP_402_PAYMENT_REQUIRED
            )

        response_payload = {
            'description': description,
            'short_description': short_description,
            'seo_keywords': seo_keywords,
            'meta_description': meta_description,
            'credits_used': billing_result['credits_charged'],
            'new_balance': billing_result['new_balance'],
        }

        cache.set(cache_key, json.dumps(response_payload, default=_json_default), 86400 * 30)

        return Response(response_payload)

    except Exception as exc:  # pragma: no cover - safeguard for unexpected data issues
        AIBillingService.log_failed_transaction(
            business_id=business_id,
            feature='product_description',
            error_message=str(exc),
            user_id=str(request.user.id),
            request_data={
                'product_id': str(product_id),
                'tone': tone,
                'language': language,
                'include_seo': include_seo,
            }
        )
        return Response(
            {'error': 'processing_failed', 'message': str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



# ============================================================================
# SMART COLLECTIONS - COLLECTION MESSAGE GENERATOR
# ============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated, RequiresActiveSubscription])
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
    language = serializer.validated_data['language']
    include_payment_plan = serializer.validated_data['include_payment_plan']
    
    # Check credits
    credit_check = AIBillingService.check_credits(business_id, 'collection_message')
    if not credit_check['has_sufficient_credits']:
        return Response({
            'error': 'insufficient_credits',
            'message': f'You need {credit_check["required_credits"]} credits.',
            'current_balance': credit_check['current_balance']
        }, status=status.HTTP_402_PAYMENT_REQUIRED)
    
    try:
        customer = Customer.objects.select_related('business').get(id=customer_id, business_id=business_id)
    except Customer.DoesNotExist:
        return Response({
            'error': 'customer_not_found',
            'message': 'Customer does not exist or does not belong to your business'
        }, status=status.HTTP_404_NOT_FOUND)

    ar_qs = AccountsReceivable.objects.filter(customer=customer)
    outstanding_balance = ar_qs.aggregate(
        total=Sum('amount_outstanding', filter=Q(amount_outstanding__gt=0))
    )['total'] or Decimal('0.00')

    overdue_qs = ar_qs.filter(amount_outstanding__gt=0, due_date__isnull=False, due_date__lt=timezone.now().date())
    oldest_overdue = overdue_qs.order_by('due_date').first()
    days_past_due = 0
    if oldest_overdue and oldest_overdue.due_date:
        days_past_due = max(0, (timezone.now().date() - oldest_overdue.due_date).days)

    customer_info = {
        'name': customer.name,
        'outstanding_balance': _to_float(outstanding_balance),
        'days_past_due': days_past_due,
        'credit_limit': _to_float(customer.credit_limit),
        'email': customer.email or '',
        'phone': customer.phone or '',
        'total_open_invoices': ar_qs.count(),
        'has_payment_plan': include_payment_plan,
    }

    MESSAGE_TYPE_CONTEXT = {
        'first_reminder': {
            'urgency': 'low',
            'description': 'Friendly first reminder, gentle and understanding.'
        },
        'second_reminder': {
            'urgency': 'medium',
            'description': 'Follow-up reminder, more direct but still polite.'
        },
        'final_notice': {
            'urgency': 'high',
            'description': 'Final warning before escalated action. Firm and clear.'
        },
        'payment_plan_offer': {
            'urgency': 'medium',
            'description': 'Offer assistance via payment plan, empathetic and supportive.'
        }
    }

    TONE_INSTRUCTIONS = {
        'professional_friendly': 'Be professional yet warm and understanding.',
        'firm': 'Be direct and assertive while remaining professional.',
        'formal_legal': 'Use formal business language with legal undertones and clear consequences.',
    }

    LANGUAGE_INSTRUCTIONS = {
        'en': 'Write in English and ensure the tone matches the brand voice.',
        'tw': 'Write in Twi (Ghanaian language) using respectful and culturally appropriate phrasing.',
    }

    payment_plan_instruction = 'Mention available payment plan options and how to engage.' if include_payment_plan else 'Do not mention payment plans in any of the outputs.'

    context_payload = {
        'business_name': business.name,
        'message_type': message_type,
        'tone': tone,
        'language': language,
        'customer': customer_info,
        'message_context': MESSAGE_TYPE_CONTEXT[message_type],
    }

    system_prompt = (
        "You are a professional debt collection communication specialist. Generate collection messages that are effective yet maintain customer relationships.\n\n"
        f"Message Type: {message_type} - {MESSAGE_TYPE_CONTEXT[message_type]['description']}\n"
        f"Urgency Level: {MESSAGE_TYPE_CONTEXT[message_type]['urgency']}\n"
        f"Tone Guidance: {TONE_INSTRUCTIONS[tone]}\n"
        f"Language: {LANGUAGE_INSTRUCTIONS[language]}\n"
        f"Payment Plan Guidance: {payment_plan_instruction}\n\n"
        "Generate 3 versions:\n"
        "1. EMAIL: Full professional email with subject line\n"
        "2. SMS: Short version (max 160 characters)\n"
        "3. WHATSAPP: Medium length, slightly casual with emojis where appropriate\n\n"
        "Format the response as JSON with keys subject, body, sms_version, whatsapp_version."
    )

    user_prompt = (
        "Generate a collection message using the following context:\n"
        f"{_prepare_json_for_prompt(context_payload)}"
    )

    try:
        openai_service = get_openai_service()
        result = openai_service.generate_json(
            prompt=user_prompt,
            system_prompt=system_prompt,
            feature='collection_message',
            temperature=0.6
        )
    except OpenAIServiceError as e:
        return _respond_with_standard_ai_provider_error(
            business_id=business_id,
            feature='collection_message',
            user_id=str(request.user.id),
            request_data={
                'customer_id': str(customer_id),
                'message_type': message_type,
                'tone': tone,
                'language': language,
                'include_payment_plan': include_payment_plan,
            },
            error=e,
        )

    try:
        result_data = result.get('data', {}) if isinstance(result, dict) else {}

        subject = str(result_data.get('subject', '')).strip()
        body = str(result_data.get('body', '')).strip()
        sms_version = str(result_data.get('sms_version', '')).strip()
        whatsapp_version = str(result_data.get('whatsapp_version', '')).strip()

        if len(sms_version) > 160:
            sms_version = sms_version[:157] + '...'

        try:
            billing_result = AIBillingService.charge_credits(
                business_id=business_id,
                feature='collection_message',
                actual_openai_cost=Decimal(str(result.get('cost_ghs', 0))),
                tokens_used=int(result.get('tokens', {}).get('total', 0)),
                user_id=str(request.user.id),
                request_data={
                    'customer_id': str(customer_id),
                    'message_type': message_type,
                    'tone': tone,
                    'language': language,
                    'include_payment_plan': include_payment_plan,
                },
                response_summary=body[:200],
                processing_time_ms=int(result.get('processing_time_ms', 0))
            )
        except InsufficientCreditsException as exc:
            return Response(
                {'error': 'insufficient_credits', 'message': str(exc)},
                status=status.HTTP_402_PAYMENT_REQUIRED
            )

        response_payload = {
            'subject': subject,
            'body': body,
            'sms_version': sms_version,
            'whatsapp_version': whatsapp_version,
            'credits_used': billing_result['credits_charged'],
            'new_balance': billing_result['new_balance'],
        }

        return Response(response_payload)

    except Exception as exc:  # pragma: no cover - safeguard for malformed AI output
        AIBillingService.log_failed_transaction(
            business_id=business_id,
            feature='collection_message',
            error_message=str(exc),
            user_id=str(request.user.id),
            request_data={
                'customer_id': str(customer_id),
                'message_type': message_type,
                'tone': tone,
                'language': language,
                'include_payment_plan': include_payment_plan,
            }
        )
        return Response(
            {'error': 'processing_failed', 'message': str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



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
