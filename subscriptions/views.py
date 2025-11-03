"""
Subscription Views
API endpoints for subscription management
"""
from rest_framework import viewsets, status, permissions, serializers
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.conf import settings
from datetime import timedelta, datetime
from decimal import Decimal

from .models import (
    SubscriptionPlan,
    Subscription,
    SubscriptionPayment,
    PaymentGatewayConfig,
    WebhookEvent,
    UsageTracking,
    Invoice,
    Alert,
    SubscriptionPricingTier,
    TaxConfiguration,
    ServiceCharge,
)
from .serializers import (
    SubscriptionPlanSerializer,
    SubscriptionListSerializer,
    SubscriptionDetailSerializer,
    SubscriptionCreateSerializer,
    SubscriptionPaymentSerializer,
    PaymentGatewayConfigSerializer,
    WebhookEventSerializer,
    UsageTrackingSerializer,
    InvoiceSerializer,
    AlertSerializer,
    SubscriptionStatsSerializer,
    SubscriptionPricingTierSerializer,
    TaxConfigurationSerializer,
    ServiceChargeSerializer,
    EnhancedSubscriptionPaymentSerializer,
)
from .payment_gateways import get_payment_gateway, PaymentGatewayError

import logging
logger = logging.getLogger(__name__)


class IsPlatformAdmin(permissions.BasePermission):
    """Permission for platform admins only"""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.is_staff


class IsBusinessOwner(permissions.BasePermission):
    """Permission for business owners"""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # User can only access subscriptions for businesses they're members of
        if hasattr(obj, 'business'):
            # Check if user is a member of this business
            return obj.business.memberships.filter(user=request.user).exists()
        elif hasattr(obj, 'subscription'):
            # For related objects (payments, alerts, etc.)
            return obj.subscription.business.memberships.filter(user=request.user).exists()
        return False


class SubscriptionPlanViewSet(viewsets.ModelViewSet):
    """
    Viewset for viewing and managing subscription plans
    - List and detail views are public (anyone can view active plans)
    - Create, update, delete are platform admin only
    """
    queryset = SubscriptionPlan.objects.filter(is_active=True).order_by('sort_order', 'price')
    serializer_class = SubscriptionPlanSerializer
    
    def get_permissions(self):
        """
        Public can view plans
        Only platform admins can create/update/delete
        """
        if self.action in ['list', 'retrieve', 'popular', 'features']:
            permission_classes = [AllowAny]
        else:
            permission_classes = [IsPlatformAdmin]
        return [permission() for permission in permission_classes]
    
    def get_queryset(self):
        """Filter active plans, unless user is admin"""
        queryset = super().get_queryset()
        
        if self.request.user.is_authenticated and self.request.user.is_staff:
            return SubscriptionPlan.objects.all().order_by('sort_order', 'price')
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def popular(self, request):
        """Get most popular plans"""
        plans = self.get_queryset().filter(is_popular=True)
        serializer = self.get_serializer(plans, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def features(self, request, pk=None):
        """Get detailed features for a plan"""
        plan = self.get_object()
        return Response({
            'plan_name': plan.name,
            'features': plan.features,
            'max_users': plan.max_users,
            'max_storefronts': plan.max_storefronts,
            'max_products': plan.max_products,
            'billing_cycle': plan.get_billing_cycle_display(),
            'price': str(plan.price),
            'currency': plan.currency
        })


class SubscriptionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing subscriptions
    Business owners can manage their own subscriptions
    Platform admins can manage all subscriptions
    """
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return subscriptions based on user role"""
        user = self.request.user
        
        if user.is_staff:
            # Platform admins see all subscriptions
            return Subscription.objects.all().select_related('plan', 'business')
        else:
            # Regular users see subscriptions for businesses they're members of
            # Get all business IDs where user is a member
            user_business_ids = user.business_memberships.values_list('business_id', flat=True)
            return Subscription.objects.filter(
                business_id__in=user_business_ids
            ).select_related('plan', 'business')
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return SubscriptionListSerializer
        elif self.action == 'create':
            return SubscriptionCreateSerializer
        else:
            return SubscriptionDetailSerializer
    
    def create(self, request, *args, **kwargs):
        """Override create to provide better error messages"""
        serializer = self.get_serializer(data=request.data)
        
        try:
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(
                serializer.data, 
                status=status.HTTP_201_CREATED, 
                headers=headers
            )
        except serializers.ValidationError as e:
            # Format validation errors nicely for frontend
            error_detail = e.detail
            
            # Check if it's the duplicate subscription error with extra info
            if isinstance(error_detail, dict) and 'business_id' in error_detail:
                business_error = error_detail['business_id']
                
                # If it's our structured error response
                if isinstance(business_error, dict):
                    return Response({
                        'error': 'Subscription Already Exists',
                        'message': business_error.get('detail', str(business_error)),
                        'existing_subscription_id': business_error.get('existing_subscription_id'),
                        'plan_name': business_error.get('plan_name'),
                        'user_friendly_message': business_error.get('detail', 'You already have an active subscription.')
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            # Handle other validation errors
            # Extract the first error message for a clean user-facing message
            if isinstance(error_detail, dict):
                first_field = next(iter(error_detail.keys()))
                first_error = error_detail[first_field]
                
                if isinstance(first_error, list):
                    user_message = str(first_error[0])
                elif isinstance(first_error, dict):
                    user_message = first_error.get('detail', str(first_error))
                else:
                    user_message = str(first_error)
            else:
                user_message = str(error_detail)
            
            return Response({
                'error': 'Validation Error',
                'message': user_message,
                'details': error_detail,
                'user_friendly_message': user_message
            }, status=status.HTTP_400_BAD_REQUEST)
        
        except Exception as e:
            logger.error(f"Subscription creation error: {str(e)}", exc_info=True)
            return Response({
                'error': 'Subscription Creation Failed',
                'message': str(e),
                'user_friendly_message': 'An error occurred while creating your subscription. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def perform_create(self, serializer):
        """Create subscription for current user"""
        serializer.save()
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user's active subscriptions for their businesses"""
        # Get all business IDs where user is a member
        user_business_ids = request.user.business_memberships.values_list('business_id', flat=True)
        
        subscriptions = Subscription.objects.filter(
            business_id__in=user_business_ids,
            status__in=['ACTIVE', 'TRIAL', 'PAST_DUE']
        ).select_related('plan', 'business')
        
        # Always return 200 with array (empty array if no subscriptions)
        serializer = SubscriptionDetailSerializer(subscriptions, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def initialize_payment(self, request, pk=None):
        """
        Initialize payment for subscription with full pricing calculation.
        
        Request body:
        {
            "gateway": "PAYSTACK",
            "callback_url": "https://..."
        }
        
        Returns payment details including authorization URL for Paystack/Stripe checkout.
        """
        from datetime import date
        
        subscription = self.get_object()
        
        # Check if user is a member of the business with this subscription
        if not subscription.business.memberships.filter(user=request.user).exists() and not request.user.is_staff:
            return Response(
                {'error': 'Permission denied', 'detail': 'You do not have permission to pay for this subscription'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if already paid
        if subscription.payment_status == 'PAID' and subscription.status == 'ACTIVE':
            return Response(
                {'error': 'Payment already completed', 'detail': 'This subscription is already active and paid'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        gateway_type = request.data.get('gateway', 'PAYSTACK').upper()
        callback_url = request.data.get('callback_url', f"{settings.FRONTEND_URL}/app/subscription/payment/callback")
        
        try:
            # 1. Count business storefronts
            from accounts.models import Business
            
            # Count storefronts linked to this business via business_storefronts table
            storefront_count = subscription.business.business_storefronts.filter(is_active=True).count()
            
            # 2. Find applicable pricing tier
            tier = SubscriptionPricingTier.objects.filter(
                is_active=True,
                min_storefronts__lte=storefront_count
            ).filter(
                Q(max_storefronts__gte=storefront_count) | Q(max_storefronts__isnull=True)
            ).first()
            
            if not tier:
                return Response(
                    {'error': f'No pricing tier found for {storefront_count} storefronts'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # 3. Calculate base price
            base_price = tier.calculate_price(storefront_count)
            
            # 4. Calculate taxes
            taxes = []
            total_tax = Decimal('0.00')
            tax_breakdown = {}
            
            active_taxes = TaxConfiguration.objects.filter(
                is_active=True,
                applies_to_subscriptions=True,
                effective_from__lte=date.today()
            ).filter(
                Q(effective_until__gte=date.today()) | Q(effective_until__isnull=True)
            ).order_by('calculation_order')
            
            for tax in active_taxes:
                tax_amount = tax.calculate_amount(base_price)
                taxes.append({
                    'code': tax.code,
                    'name': tax.name,
                    'rate': float(tax.rate),
                    'amount': str(tax_amount)
                })
                tax_breakdown[tax.code] = {
                    'name': tax.name,
                    'rate': float(tax.rate),
                    'amount': str(tax_amount)
                }
                total_tax += tax_amount
            
            # 5. Calculate service charges
            charges = []
            total_charges = Decimal('0.00')
            charges_breakdown = {}
            
            active_charges = ServiceCharge.objects.filter(
                is_active=True
            ).filter(
                Q(payment_gateway='ALL') | Q(payment_gateway=gateway_type)
            )
            
            for charge in active_charges:
                charge_base = base_price if charge.applies_to == 'SUBTOTAL' else (base_price + total_tax)
                charge_amount = charge.calculate_amount(charge_base)
                charges.append({
                    'code': charge.code,
                    'name': charge.name,
                    'type': charge.charge_type,
                    'rate': float(charge.amount) if charge.charge_type == 'PERCENTAGE' else None,
                    'amount': str(charge_amount)
                })
                charges_breakdown[charge.code] = {
                    'name': charge.name,
                    'type': charge.charge_type,
                    'rate': float(charge.amount) if charge.charge_type == 'PERCENTAGE' else None,
                    'amount': str(charge_amount)
                }
                total_charges += charge_amount
            
            # 6. Calculate total
            total_amount = base_price + total_tax + total_charges
            
            # 7. Create SubscriptionPayment record
            reference = f"SUB-{subscription.id}-{timezone.now().timestamp()}"[:100]
            
            payment = SubscriptionPayment.objects.create(
                subscription=subscription,
                amount=total_amount,
                currency=tier.currency,
                payment_method=gateway_type,
                status='PENDING',
                transaction_reference=reference,
                billing_period_start=subscription.start_date or timezone.now().date(),
                billing_period_end=subscription.end_date or (timezone.now().date() + timezone.timedelta(days=30)),
                base_amount=base_price,
                storefront_count=storefront_count,
                pricing_tier_snapshot={
                    'tier_id': str(tier.id),
                    'tier_description': str(tier),
                    'min_storefronts': tier.min_storefronts,
                    'max_storefronts': tier.max_storefronts,
                    'base_price': str(tier.base_price),
                    'price_per_additional': str(tier.price_per_additional_storefront)
                },
                tax_breakdown=tax_breakdown,
                total_tax_amount=total_tax,
                service_charges_breakdown=charges_breakdown,
                total_service_charges=total_charges
            )
            
            # 8. Initialize payment with gateway
            gateway = get_payment_gateway(gateway_type)
            
            if gateway_type == 'PAYSTACK':
                # Get user email
                email = request.user.email
                
                paystack_result = gateway.initialize_transaction(
                    email=email,
                    amount=total_amount,
                    currency=tier.currency,
                    reference=reference,
                    callback_url=callback_url,
                    metadata={
                        'app_name': 'pos',
                        'subscription_id': str(subscription.id),
                        'business_id': str(subscription.business.id),
                        'business_name': subscription.business.name,
                        'payment_id': str(payment.id),
                        'storefront_count': storefront_count
                    }
                )
                
                if paystack_result.get('status'):
                    # Store gateway response
                    payment.gateway_response = paystack_result
                    payment.save()
                    
                    return Response({
                        'payment_id': str(payment.id),
                        'authorization_url': paystack_result['data']['authorization_url'],
                        'reference': reference,
                        'amount': str(total_amount),
                        'currency': tier.currency
                    }, status=status.HTTP_200_OK)
                else:
                    payment.status = 'FAILED'
                    payment.failure_reason = paystack_result.get('message', 'Payment initialization failed')
                    payment.save()
                    raise PaymentGatewayError(paystack_result.get('message', 'Payment initialization failed'))
            
            elif gateway_type == 'STRIPE':
                success_url = request.data.get('success_url', callback_url)
                cancel_url = request.data.get('cancel_url', callback_url)
                result = gateway.create_checkout_session(subscription, success_url, cancel_url)
                
                if result.get('success'):
                    payment.gateway_reference = result['session_id']
                    payment.gateway_response = {'session': result['session'].to_dict() if hasattr(result['session'], 'to_dict') else str(result['session'])}
                    payment.save()
                    
                    return Response({
                        'payment_id': str(payment.id),
                        'authorization_url': result['checkout_url'],
                        'reference': result['session_id'],
                        'amount': str(total_amount),
                        'currency': tier.currency
                    }, status=status.HTTP_200_OK)
                else:
                    raise PaymentGatewayError('Stripe checkout session creation failed')
            
            else:
                payment.delete()  # Clean up payment record
                return Response(
                    {'error': 'Unsupported payment gateway', 'detail': f'Gateway {gateway_type} is not supported'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
        except PaymentGatewayError as e:
            logger.error(f"Payment initialization error: {str(e)}")
            return Response(
                {'error': 'Payment initialization failed', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logger.error(f"Unexpected error in initialize_payment: {str(e)}")
            return Response(
                {'error': 'Internal server error', 'detail': 'An unexpected error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def verify_payment(self, request, pk=None):
        """
        Verify payment for subscription.
        
        Request body:
        {
            "gateway": "PAYSTACK",
            "reference": "SUB-..."
        }
        
        Returns verification result with payment and subscription details.
        """
        subscription = self.get_object()
        
        gateway_type = request.data.get('gateway', 'PAYSTACK').upper()
        reference = request.data.get('reference')
        
        if not reference:
            return Response(
                {'error': 'Reference is required', 'detail': 'Payment reference must be provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # 1. Find payment record
            payment = SubscriptionPayment.objects.filter(
                transaction_reference=reference,
                subscription=subscription
            ).first()
            
            if not payment:
                return Response(
                    {'error': 'Payment not found', 'detail': f'No payment found with reference {reference}'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # 2. Verify with gateway
            gateway = get_payment_gateway(gateway_type)
            
            if gateway_type == 'PAYSTACK':
                verification_result = gateway.verify_transaction(reference)
                
                if verification_result.get('status') and verification_result.get('data'):
                    data = verification_result['data']
                    
                    # Check if payment was successful
                    if data['status'] == 'success':
                        # Update payment record
                        payment.status = 'SUCCESSFUL'
                        payment.payment_date = timezone.now()
                        payment.transaction_id = str(data.get('id'))
                        payment.gateway_reference = data.get('reference')
                        payment.gateway_response = data
                        payment.save()
                        
                        # Update subscription
                        subscription.payment_status = 'PAID'
                        subscription.status = 'ACTIVE'
                        subscription.payment_method = 'PAYSTACK'
                        if not subscription.start_date:
                            subscription.start_date = timezone.now().date()
                        if not subscription.end_date:
                            subscription.end_date = subscription.start_date + timezone.timedelta(days=30)
                        subscription.save()
                        
                        # Update business
                        subscription.business.subscription_status = 'ACTIVE'
                        subscription.business.save()
                        
                        return Response({
                            'success': True,
                            'message': 'Payment verified successfully',
                            'payment': {
                                'id': str(payment.id),
                                'amount': str(payment.amount),
                                'status': payment.status,
                                'payment_date': payment.payment_date.isoformat() if payment.payment_date else None
                            },
                            'subscription': {
                                'id': str(subscription.id),
                                'status': subscription.status,
                                'payment_status': subscription.payment_status,
                                'start_date': subscription.start_date.isoformat() if subscription.start_date else None,
                                'end_date': subscription.end_date.isoformat() if subscription.end_date else None
                            }
                        }, status=status.HTTP_200_OK)
                    else:
                        # Payment failed
                        payment.status = 'FAILED'
                        payment.failure_reason = data.get('gateway_response', 'Transaction was not successful')
                        payment.gateway_response = data
                        payment.save()
                        
                        return Response({
                            'success': False,
                            'message': 'Payment verification failed',
                            'reason': data.get('gateway_response', 'Transaction was not successful')
                        }, status=status.HTTP_200_OK)
                else:
                    return Response({
                        'success': False,
                        'message': 'Payment verification failed',
                        'reason': verification_result.get('message', 'Verification request failed')
                    }, status=status.HTTP_200_OK)
            
            elif gateway_type == 'STRIPE':
                session_id = reference
                session_data = gateway.retrieve_session(session_id)
                
                if session_data.get('payment_status') == 'paid':
                    # Update payment record
                    payment.status = 'SUCCESSFUL'
                    payment.payment_date = timezone.now()
                    payment.transaction_id = session_data['session'].payment_intent if session_data.get('session') else None
                    payment.gateway_reference = session_id
                    payment.gateway_response = {'session': session_data['session'].to_dict() if hasattr(session_data.get('session'), 'to_dict') else str(session_data.get('session'))}
                    payment.save()
                    
                    # Update subscription
                    subscription.payment_status = 'PAID'
                    subscription.status = 'ACTIVE'
                    subscription.payment_method = 'STRIPE'
                    if not subscription.start_date:
                        subscription.start_date = timezone.now().date()
                    if not subscription.end_date:
                        subscription.end_date = subscription.start_date + timezone.timedelta(days=30)
                    subscription.save()
                    
                    # Update business
                    subscription.business.subscription_status = 'ACTIVE'
                    subscription.business.save()
                    
                    return Response({
                        'success': True,
                        'message': 'Payment verified successfully',
                        'payment': {
                            'id': str(payment.id),
                            'amount': str(payment.amount),
                            'status': payment.status,
                            'payment_date': payment.payment_date.isoformat() if payment.payment_date else None
                        },
                        'subscription': {
                            'id': str(subscription.id),
                            'status': subscription.status,
                            'payment_status': subscription.payment_status,
                            'start_date': subscription.start_date.isoformat() if subscription.start_date else None,
                            'end_date': subscription.end_date.isoformat() if subscription.end_date else None
                        }
                    }, status=status.HTTP_200_OK)
                else:
                    return Response({
                        'success': False,
                        'message': 'Payment verification failed',
                        'reason': 'Payment not completed'
                    }, status=status.HTTP_200_OK)
            
            else:
                return Response(
                    {'error': 'Unsupported payment gateway', 'detail': f'Gateway {gateway_type} is not supported'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
        except PaymentGatewayError as e:
            logger.error(f"Payment verification error: {str(e)}")
            return Response(
                {'error': 'Payment verification failed', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logger.error(f"Unexpected error in verify_payment: {str(e)}")
            return Response(
                {'error': 'Internal server error', 'detail': 'An unexpected error occurred'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel subscription"""
        subscription = self.get_object()
        
        # Check if user is a member of the business with this subscription
        if not subscription.business.memberships.filter(user=request.user).exists() and not request.user.is_staff:
            return Response(
                {'detail': 'You do not have permission to cancel this subscription'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        immediately = request.data.get('immediately', False)
        reason = request.data.get('reason', '')
        
        subscription.cancel(user=request.user, immediately=immediately)
        
        # Create alert
        Alert.objects.create(
            subscription=subscription,
            alert_type='SUBSCRIPTION_CANCELLED',
            priority='HIGH',
            title='Subscription Cancelled',
            message=f'Your subscription has been cancelled. {"It will remain active until " + str(subscription.end_date) if not immediately else "Access has been revoked immediately."}',
            metadata={'reason': reason, 'cancelled_by': str(request.user.id)}
        )
        
        serializer = SubscriptionDetailSerializer(subscription)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def renew(self, request, pk=None):
        """Renew subscription"""
        subscription = self.get_object()
        
        if not subscription.can_renew():
            return Response(
                {'detail': 'Subscription cannot be renewed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        payment_method = request.data.get('payment_method')
        subscription.renew(payment_method=payment_method)
        
        serializer = SubscriptionDetailSerializer(subscription)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[IsPlatformAdmin])
    def suspend(self, request, pk=None):
        """Suspend subscription (admin only)"""
        subscription = self.get_object()
        reason = request.data.get('reason', '')
        
        subscription.suspend(reason=reason)
        
        # Create alert
        Alert.objects.create(
            subscription=subscription,
            alert_type='SUBSCRIPTION_SUSPENDED',
            priority='CRITICAL',
            title='Subscription Suspended',
            message=f'Your subscription has been suspended. Reason: {reason}',
            metadata={'suspended_by': str(request.user.id)}
        )
        
        serializer = SubscriptionDetailSerializer(subscription)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[IsPlatformAdmin])
    def activate(self, request, pk=None):
        """Activate subscription (admin only)"""
        subscription = self.get_object()
        subscription.activate()
        
        # Create alert
        Alert.objects.create(
            subscription=subscription,
            alert_type='SUBSCRIPTION_ACTIVATED',
            priority='HIGH',
            title='Subscription Activated',
            message='Your subscription has been activated',
            metadata={'activated_by': str(request.user.id)}
        )
        
        serializer = SubscriptionDetailSerializer(subscription)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def usage(self, request, pk=None):
        """Get subscription usage statistics"""
        subscription = self.get_object()
        usage_limits = subscription.check_usage_limits()
        
        return Response({
            'subscription_id': str(subscription.id),
            'plan_name': subscription.plan.name,
            'usage': usage_limits
        })
    
    @action(detail=True, methods=['get'])
    def invoices(self, request, pk=None):
        """Get invoices for subscription"""
        subscription = self.get_object()
        invoices = subscription.invoices.all()
        serializer = InvoiceSerializer(invoices, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def payments(self, request, pk=None):
        """Get payment history for subscription"""
        subscription = self.get_object()
        payments = subscription.payments.all()
        serializer = SubscriptionPaymentSerializer(payments, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def alerts(self, request, pk=None):
        """Get alerts for subscription"""
        subscription = self.get_object()
        alerts = subscription.alerts.filter(is_dismissed=False).order_by('-priority', '-created_at')
        serializer = AlertSerializer(alerts, many=True)
        return Response(serializer.data)


class AlertViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing and managing alerts"""
    serializer_class = AlertSerializer
    permission_classes = [IsAuthenticated, IsBusinessOwner]
    
    def get_queryset(self):
        """Return alerts for user's subscriptions"""
        user = self.request.user
        
        if user.is_staff:
            return Alert.objects.all()
        else:
            # Get alerts for subscriptions of businesses user is a member of
            user_business_ids = user.business_memberships.values_list('business_id', flat=True)
            return Alert.objects.filter(subscription__business_id__in=user_business_ids)
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """Mark alert as read"""
        alert = self.get_object()
        alert.mark_as_read()
        serializer = self.get_serializer(alert)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def dismiss(self, request, pk=None):
        """Dismiss alert"""
        alert = self.get_object()
        alert.dismiss()
        serializer = self.get_serializer(alert)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def unread(self, request):
        """Get unread alerts"""
        alerts = self.get_queryset().filter(is_read=False, is_dismissed=False)
        serializer = self.get_serializer(alerts, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def critical(self, request):
        """Get critical alerts"""
        alerts = self.get_queryset().filter(
            priority='CRITICAL',
            is_dismissed=False
        )
        serializer = self.get_serializer(alerts, many=True)
        return Response(serializer.data)


class SubscriptionStatsViewSet(viewsets.ViewSet):
    """ViewSet for subscription statistics (Platform Admin only)"""
    permission_classes = [IsPlatformAdmin]
    
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Get overview of subscription statistics"""
        today = timezone.now().date()
        
        # Total subscriptions
        total_subs = Subscription.objects.count()
        active_subs = Subscription.objects.filter(status__in=['ACTIVE', 'TRIAL']).count()
        trial_subs = Subscription.objects.filter(status='TRIAL').count()
        expired_subs = Subscription.objects.filter(status='EXPIRED').count()
        cancelled_subs = Subscription.objects.filter(status='CANCELLED').count()
        
        # Revenue calculations
        total_revenue = SubscriptionPayment.objects.filter(
            status='SUCCESSFUL'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Monthly recurring revenue (active subscriptions)
        mrr = Subscription.objects.filter(
            status='ACTIVE',
            plan__billing_cycle='MONTHLY'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Average subscription value
        avg_value = Subscription.objects.filter(
            status__in=['ACTIVE', 'TRIAL']
        ).aggregate(avg=Avg('amount'))['avg'] or Decimal('0.00')
        
        # Churn rate (last 30 days)
        thirty_days_ago = today - timedelta(days=30)
        cancelled_last_month = Subscription.objects.filter(
            cancelled_at__gte=thirty_days_ago
        ).count()
        active_last_month = Subscription.objects.filter(
            created_at__lte=thirty_days_ago,
            status='ACTIVE'
        ).count()
        churn_rate = (cancelled_last_month / active_last_month * 100) if active_last_month > 0 else 0
        
        stats = {
            'total_subscriptions': total_subs,
            'active_subscriptions': active_subs,
            'trial_subscriptions': trial_subs,
            'expired_subscriptions': expired_subs,
            'cancelled_subscriptions': cancelled_subs,
            'total_revenue': total_revenue,
            'monthly_recurring_revenue': mrr,
            'average_subscription_value': avg_value,
            'churn_rate': round(churn_rate, 2)
        }
        
        serializer = SubscriptionStatsSerializer(stats)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def revenue_by_plan(self, request):
        """Get revenue breakdown by plan"""
        revenue_by_plan = Subscription.objects.filter(
            status__in=['ACTIVE', 'TRIAL']
        ).values('plan__name').annotate(
            total_revenue=Sum('amount'),
            subscription_count=Count('id')
        ).order_by('-total_revenue')
        
        return Response(revenue_by_plan)
    
    @action(detail=False, methods=['get'])
    def expiring_soon(self, request):
        """Get subscriptions expiring in next 7 days"""
        today = timezone.now().date()
        seven_days = today + timedelta(days=7)
        
        expiring = Subscription.objects.filter(
            end_date__range=[today, seven_days],
            status__in=['ACTIVE', 'TRIAL'],
            auto_renew=False
        ).select_related('user', 'plan', 'business')
        
        serializer = SubscriptionListSerializer(expiring, many=True)
        return Response(serializer.data)


@method_decorator(csrf_exempt, name='dispatch')
class PaymentWebhookView(APIView):
    """Handle payment gateway webhooks"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Process webhook from payment gateways"""
        gateway_type = request.data.get('gateway', 'PAYSTACK')
        
        try:
            if gateway_type == 'PAYSTACK':
                signature = request.META.get('HTTP_X_PAYSTACK_SIGNATURE', '')
                gateway = get_payment_gateway('PAYSTACK')
                success = gateway.process_webhook(request.data, signature)
            elif gateway_type == 'STRIPE':
                signature = request.META.get('HTTP_STRIPE_SIGNATURE', '')
                gateway = get_payment_gateway('STRIPE')
                success = gateway.process_webhook(request.body, signature)
            else:
                return Response(
                    {'status': 'error', 'message': 'Unknown gateway'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if success:
                return Response({'status': 'success'})
            else:
                return Response(
                    {'status': 'error', 'message': 'Webhook processing failed'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            logger.error(f"Webhook error: {str(e)}")
            return Response(
                {'status': 'error', 'message': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@csrf_exempt
@api_view(['POST'])
@permission_classes([])  # No auth for webhooks
def paystack_webhook(request):
    """
    Handle Paystack webhook events with app_name routing.
    
    This is called directly by Paystack when payment status changes.
    Validates signature and processes events for POS app only.
    """
    import hmac
    import hashlib
    from datetime import timedelta
    
    # Validate signature
    paystack_signature = request.META.get('HTTP_X_PAYSTACK_SIGNATURE')
    
    if not paystack_signature:
        logger.warning('Missing Paystack webhook signature')
        return Response(status=status.HTTP_400_BAD_REQUEST)
    
    # Compute signature
    computed_signature = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode('utf-8'),
        request.body,
        hashlib.sha512
    ).hexdigest()
    
    if computed_signature != paystack_signature:
        logger.warning('Invalid Paystack webhook signature')
        return Response(status=status.HTTP_400_BAD_REQUEST)
    
    # Parse event
    event_data = request.data
    event_type = event_data.get('event')
    
    # Check app_name to ensure this is for POS
    metadata = event_data.get('data', {}).get('metadata', {})
    app_name = metadata.get('app_name')
    
    if app_name != settings.PAYSTACK_APP_NAME:
        # This event is for another app (school system, etc.)
        logger.info(f'Webhook for app {app_name}, skipping (expected: {settings.PAYSTACK_APP_NAME})')
        return Response(status=status.HTTP_200_OK)
    
    # Process charge.success event
    if event_type == 'charge.success':
        reference = event_data['data']['reference']
        
        try:
            payment = SubscriptionPayment.objects.get(
                transaction_reference=reference
            )
            
            # Update payment
            payment.status = 'SUCCESSFUL'
            payment.payment_date = timezone.now()
            payment.gateway_response = event_data['data']
            payment.save()
            
            # Update subscription
            subscription = payment.subscription
            subscription.status = 'ACTIVE'
            subscription.payment_status = 'PAID'
            subscription.end_date = timezone.now().date() + timedelta(days=30)
            subscription.save()
            
            logger.info(f'Webhook processed successfully: {reference}')
            
        except SubscriptionPayment.DoesNotExist:
            logger.error(f'Payment not found for reference: {reference}')
        except Exception as e:
            logger.error(f'Error processing webhook: {str(e)}')
    
    return Response(status=status.HTTP_200_OK)


class SubscriptionPaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing payment history"""
    queryset = SubscriptionPayment.objects.all()
    serializer_class = SubscriptionPaymentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return payments for user's subscriptions"""
        user = self.request.user
        
        if user.is_staff:
            return SubscriptionPayment.objects.all()
        else:
            # Get payments for subscriptions of businesses user is a member of
            user_business_ids = user.business_memberships.values_list('business_id', flat=True)
            return SubscriptionPayment.objects.filter(subscription__business_id__in=user_business_ids)


class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing invoices"""
    queryset = Invoice.objects.all()
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Return invoices for user's subscriptions"""
        user = self.request.user
        
        if user.is_staff:
            return Invoice.objects.all()
        else:
            # Get invoices for subscriptions of businesses user is a member of
            user_business_ids = user.business_memberships.values_list('business_id', flat=True)
            return Invoice.objects.filter(subscription__business_id__in=user_business_ids)
    
    @action(detail=True, methods=['post'])
    def mark_paid(self, request, pk=None):
        """Mark invoice as paid (admin only)"""
        if not request.user.is_staff:
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        invoice = self.get_object()
        invoice.mark_as_paid()
        serializer = self.get_serializer(invoice)
        return Response(serializer.data)


# New ViewSets for Flexible Pricing System

class SubscriptionPricingTierViewSet(viewsets.ModelViewSet):
    """
    API endpoints for managing subscription pricing tiers.
    
    Permissions:
    - List/Retrieve: Any authenticated user
    - Create/Update/Delete: Platform admins only (SUPER_ADMIN, ADMIN)
    """
    queryset = SubscriptionPricingTier.objects.all()
    serializer_class = SubscriptionPricingTierSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        return queryset
    
    def get_permissions(self):
        # Only platform admins can create/update/delete
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            from .permissions import IsPlatformAdmin
            return [IsPlatformAdmin()]
        return super().get_permissions()
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a pricing tier"""
        from .permissions import IsPlatformAdmin
        if not IsPlatformAdmin().has_permission(request, self):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        tier = self.get_object()
        tier.is_active = True
        tier.save()
        return Response(
            SubscriptionPricingTierSerializer(tier).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        """Deactivate a pricing tier"""
        from .permissions import IsPlatformAdmin
        if not IsPlatformAdmin().has_permission(request, self):
            return Response(
                {'detail': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        tier = self.get_object()
        tier.is_active = False
        tier.save()
        return Response(
            SubscriptionPricingTierSerializer(tier).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=False, methods=['get'])
    def calculate(self, request):
        """
        Calculate pricing for a given number of storefronts.
        
        Query params:
        - storefronts: Number of storefronts (required)
        - include_taxes: Include tax calculation (default: true)
        - include_charges: Include service charges (default: true)
        - gateway: Payment gateway for gateway-specific charges (optional)
        
        Returns detailed pricing breakdown.
        """
        from datetime import date
        
        try:
            storefront_count = int(request.query_params.get('storefronts', 0))
            if storefront_count < 1:
                return Response(
                    {'error': 'Storefronts must be at least 1'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid storefronts parameter'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Find applicable pricing tier
        tier = SubscriptionPricingTier.objects.filter(
            is_active=True,
            min_storefronts__lte=storefront_count
        ).filter(
            Q(max_storefronts__gte=storefront_count) | Q(max_storefronts__isnull=True)
        ).first()
        
        if not tier:
            return Response(
                {'error': f'No pricing tier found for {storefront_count} storefronts'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Calculate base price
        base_price = tier.calculate_price(storefront_count)
        additional_storefronts = max(0, storefront_count - tier.min_storefronts)
        additional_cost = additional_storefronts * tier.price_per_additional_storefront
        
        # Tax calculation
        include_taxes = request.query_params.get('include_taxes', 'true').lower() == 'true'
        taxes = {}
        total_tax = Decimal('0.00')
        
        if include_taxes:
            active_taxes = TaxConfiguration.objects.filter(
                is_active=True,
                applies_to_subscriptions=True,
                effective_from__lte=date.today()
            ).filter(
                Q(effective_until__gte=date.today()) | Q(effective_until__isnull=True)
            ).order_by('calculation_order')
            
            current_base = base_price
            for tax in active_taxes:
                tax_amount = tax.calculate_amount(
                    current_base if tax.applies_to == 'SUBTOTAL' else (base_price + total_tax)
                )
                taxes[tax.code] = {
                    'name': tax.name,
                    'rate': float(tax.rate),
                    'amount': str(tax_amount)
                }
                total_tax += tax_amount
        
        # Service charges calculation
        include_charges = request.query_params.get('include_charges', 'true').lower() == 'true'
        service_charges = {}
        total_charges = Decimal('0.00')
        
        if include_charges:
            gateway = request.query_params.get('gateway', 'ALL')
            active_charges = ServiceCharge.objects.filter(
                is_active=True
            ).filter(
                Q(payment_gateway='ALL') | Q(payment_gateway=gateway.upper())
            )
            
            for charge in active_charges:
                charge_base = base_price if charge.applies_to == 'SUBTOTAL' else (base_price + total_tax)
                charge_amount = charge.calculate_amount(charge_base)
                service_charges[charge.code] = {
                    'name': charge.name,
                    'type': charge.charge_type,
                    'rate': float(charge.amount) if charge.charge_type == 'PERCENTAGE' else None,
                    'amount': str(charge_amount)
                }
                total_charges += charge_amount
        
        # Total calculation
        total_amount = base_price + total_tax + total_charges
        
        # Build breakdown text
        breakdown = [
            f"Pricing Tier: {tier}",
            f"Base Price ({tier.min_storefronts} storefronts): {tier.currency} {tier.base_price}",
        ]
        
        if additional_storefronts > 0:
            breakdown.append(
                f"Additional {additional_storefronts} storefronts @ {tier.currency} {tier.price_per_additional_storefront}: {tier.currency} {additional_cost}"
            )
        
        breakdown.append(f"Subtotal: {tier.currency} {base_price}")
        
        for code, tax_info in taxes.items():
            breakdown.append(f"{tax_info['name']} ({tax_info['rate']}%): {tier.currency} {tax_info['amount']}")
        
        for code, charge_info in service_charges.items():
            if charge_info['type'] == 'PERCENTAGE':
                breakdown.append(f"{charge_info['name']} ({charge_info['rate']}%): {tier.currency} {charge_info['amount']}")
            else:
                breakdown.append(f"{charge_info['name']}: {tier.currency} {charge_info['amount']}")
        
        breakdown.append(f"Total: {tier.currency} {total_amount}")
        
        return Response({
            'storefronts': storefront_count,
            'tier': SubscriptionPricingTierSerializer(tier).data,
            'base_price': str(base_price),
            'additional_storefronts': additional_storefronts,
            'additional_cost': str(additional_cost),
            'subtotal': str(base_price),
            'taxes': taxes,
            'total_tax': str(total_tax),
            'service_charges': service_charges,
            'total_service_charges': str(total_charges),
            'total_amount': str(total_amount),
            'currency': tier.currency,
            'breakdown': breakdown
        })


class TaxConfigurationViewSet(viewsets.ModelViewSet):
    """
    API endpoints for managing tax configurations.
    
    Permissions:
    - List/Retrieve: Any authenticated user
    - Create/Update/Delete: Platform admins only
    """
    queryset = TaxConfiguration.objects.all()
    serializer_class = TaxConfigurationSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        # Filter by country
        country = self.request.query_params.get('country')
        if country:
            queryset = queryset.filter(country=country.upper())
        
        return queryset
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            from .permissions import IsPlatformAdmin
            return [IsPlatformAdmin()]
        return super().get_permissions()
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get all currently active taxes"""
        from datetime import date
        
        active_taxes = TaxConfiguration.objects.filter(
            is_active=True,
            effective_from__lte=date.today()
        ).filter(
            Q(effective_until__gte=date.today()) | Q(effective_until__isnull=True)
        )
        
        serializer = self.get_serializer(active_taxes, many=True)
        return Response(serializer.data)


class ServiceChargeViewSet(viewsets.ModelViewSet):
    """API endpoints for managing service charges"""
    queryset = ServiceCharge.objects.all()
    serializer_class = ServiceChargeSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        gateway = self.request.query_params.get('gateway')
        if gateway:
            queryset = queryset.filter(
                Q(payment_gateway='ALL') | Q(payment_gateway=gateway.upper())
            )
        
        return queryset
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            from .permissions import IsPlatformAdmin
            return [IsPlatformAdmin()]
        return super().get_permissions()
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class PaymentStatsViewSet(viewsets.ViewSet):
    """Analytics endpoints for payment data"""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """
        Get overall payment statistics.
        
        Returns:
        - Total payments processed
        - Success/failure counts and rates
        - Revenue metrics
        - Failure reason analysis
        """
        from .permissions import IsPlatformAdmin
        
        # Only platform admins can see all payments
        if IsPlatformAdmin().has_permission(request, self):
            payments = SubscriptionPayment.objects.all()
        else:
            # Regular users see only their business payments
            payments = SubscriptionPayment.objects.filter(
                subscription__business__memberships__user=request.user
            )
        
        # Apply date filters
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        if date_from:
            payments = payments.filter(created_at__gte=date_from)
        if date_to:
            payments = payments.filter(created_at__lte=date_to)
        
        # Calculate stats
        total_count = payments.count()
        successful = payments.filter(status='SUCCESSFUL').count()
        failed = payments.filter(status='FAILED').count()
        pending = payments.filter(status='PENDING').count()
        
        success_rate = (successful / total_count * 100) if total_count > 0 else 0
        
        # Revenue
        total_revenue = payments.filter(status='SUCCESSFUL').aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        total_tax = payments.filter(status='SUCCESSFUL').aggregate(
            total=Sum('total_tax_amount')
        )['total'] or Decimal('0.00')
        
        # Failure reasons
        failure_reasons = {}
        failed_payments = payments.filter(status='FAILED')
        for payment in failed_payments:
            reason = payment.failure_reason or 'Unknown'
            failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
        
        return Response({
            'payments': {
                'total_processed': total_count,
                'successful': successful,
                'failed': failed,
                'pending': pending,
                'success_rate': round(success_rate, 2)
            },
            'revenue': {
                'total_revenue': str(total_revenue),
                'total_tax_collected': str(total_tax),
                'average_payment': str(total_revenue / successful) if successful > 0 else '0.00'
            },
            'failure_analysis': failure_reasons
        })


# Pricing Calculation Endpoint (Backend-First Architecture)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def calculate_subscription_pricing(request):
    """
    Calculate complete pricing breakdown for subscription.
    
    Frontend just calls this endpoint and displays the result.
    NO calculation logic on frontend.
    
    Query params:
    - storefronts: Number of storefronts (required)
    - gateway: Payment gateway (PAYSTACK, STRIPE, etc.) - optional
    
    Returns complete pricing with ALL taxes, fees, breakdowns
    """
    from datetime import date
    
    try:
        storefront_count = int(request.query_params.get('storefronts', 1))
        if storefront_count < 1:
            return Response(
                {'error': 'Storefronts must be at least 1'},
                status=status.HTTP_400_BAD_REQUEST
            )
    except (ValueError, TypeError):
        return Response(
            {'error': 'Invalid storefronts parameter'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    gateway = request.query_params.get('gateway', 'PAYSTACK')
    
    # 1. Find applicable pricing tier
    tier = SubscriptionPricingTier.objects.filter(
        is_active=True,
        min_storefronts__lte=storefront_count
    ).filter(
        Q(max_storefronts__gte=storefront_count) | Q(max_storefronts__isnull=True)
    ).first()
    
    if not tier:
        return Response(
            {'error': f'No pricing tier found for {storefront_count} storefronts'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # 2. Calculate base price
    base_price = tier.calculate_price(storefront_count)
    additional_storefronts = max(0, storefront_count - tier.min_storefronts)
    
    # 3. Calculate taxes (Ghana VAT, NHIL, GETFund, COVID levy)
    taxes = []
    total_tax = Decimal('0.00')
    
    active_taxes = TaxConfiguration.objects.filter(
        is_active=True,
        applies_to_subscriptions=True,
        effective_from__lte=date.today()
    ).filter(
        Q(effective_until__gte=date.today()) | Q(effective_until__isnull=True)
    ).order_by('calculation_order')
    
    for tax in active_taxes:
        tax_amount = tax.calculate_amount(base_price)
        taxes.append({
            'code': tax.code,
            'name': tax.name,
            'rate': float(tax.rate),
            'amount': str(tax_amount)
        })
        total_tax += tax_amount
    
    # 4. Calculate service charges (Paystack fees, etc.)
    charges = []
    total_charges = Decimal('0.00')
    
    active_charges = ServiceCharge.objects.filter(
        is_active=True
    ).filter(
        Q(payment_gateway='ALL') | Q(payment_gateway=gateway.upper())
    )
    
    for charge in active_charges:
        charge_base = base_price if charge.applies_to == 'SUBTOTAL' else (base_price + total_tax)
        charge_amount = charge.calculate_amount(charge_base)
        charges.append({
            'code': charge.code,
            'name': charge.name,
            'type': charge.charge_type,
            'rate': float(charge.amount) if charge.charge_type == 'PERCENTAGE' else None,
            'amount': str(charge_amount)
        })
        total_charges += charge_amount
    
    # 5. Calculate total
    total_amount = base_price + total_tax + total_charges
    
    # 6. Return complete breakdown
    return Response({
        'storefronts': storefront_count,
        'currency': tier.currency,
        'base_price': str(base_price),
        'taxes': taxes,
        'total_tax': str(total_tax),
        'service_charges': charges,
        'total_service_charges': str(total_charges),
        'total_amount': str(total_amount),
        'breakdown': {
            'tier_id': str(tier.id),
            'tier_description': str(tier),
            'base_storefronts': tier.min_storefronts,
            'additional_storefronts': additional_storefronts,
            'price_per_additional': str(tier.price_per_additional_storefront)
        }
    })


class PaymentStatsViewSet(viewsets.ViewSet):
    """Analytics endpoints for payment data"""
    permission_classes = [IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """
        Get overall payment statistics.
        
        Returns:
        - Total payments processed
        - Success/failure counts and rates
        - Revenue metrics
        - Failure reason analysis
        """
        from .permissions import IsPlatformAdmin
        
        # Only platform admins can see all payments
        if IsPlatformAdmin().has_permission(request, self):
            payments = SubscriptionPayment.objects.all()
        else:
            # Regular users see only their business payments
            payments = SubscriptionPayment.objects.filter(
                subscription__business__memberships__user=request.user
            )
        
        # Apply date filters
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        if date_from:
            payments = payments.filter(created_at__gte=date_from)
        if date_to:
            payments = payments.filter(created_at__lte=date_to)
        
        # Calculate stats
        total_count = payments.count()
        successful = payments.filter(status='SUCCESSFUL').count()
        failed = payments.filter(status='FAILED').count()
        pending = payments.filter(status='PENDING').count()
        
        success_rate = (successful / total_count * 100) if total_count > 0 else 0
        
        # Revenue
        total_revenue = payments.filter(status='SUCCESSFUL').aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        total_tax = payments.filter(status='SUCCESSFUL').aggregate(
            total=Sum('total_tax_amount')
        )['total'] or Decimal('0.00')
        
        # Failure reasons
        failure_reasons = {}
        failed_payments = payments.filter(status='FAILED')
        for payment in failed_payments:
            reason = payment.failure_reason or 'Unknown'
            failure_reasons[reason] = failure_reasons.get(reason, 0) + 1
        
        return Response({
            'payments': {
                'total_processed': total_count,
                'successful': successful,
                'failed': failed,
                'pending': pending,
                'success_rate': round(success_rate, 2)
            },
            'revenue': {
                'total_revenue': str(total_revenue),
                'total_tax_collected': str(total_tax),
                'average_payment': str(total_revenue / successful) if successful > 0 else '0.00'
            },
            'failure_analysis': failure_reasons
        })
    
    @action(detail=False, methods=['get'])
    def revenue_chart(self, request):
        """
        Get revenue data for charts.
        
        Query params:
        - period: DAILY, WEEKLY, MONTHLY (default: MONTHLY)
        - date_from: Start date
        - date_to: End date
        """
        from django.db.models.functions import TruncMonth, TruncWeek, TruncDay
        
        period = request.query_params.get('period', 'MONTHLY')
        
        payments = SubscriptionPayment.objects.filter(status='SUCCESSFUL')
        
        # Apply date filters
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        if date_from:
            payments = payments.filter(payment_date__gte=date_from)
        if date_to:
            payments = payments.filter(payment_date__lte=date_to)
        
        # Group by period
        if period == 'DAILY':
            trunc_func = TruncDay
        elif period == 'WEEKLY':
            trunc_func = TruncWeek
        else:  # MONTHLY
            trunc_func = TruncMonth
        
        revenue_data = payments.annotate(
            period=trunc_func('payment_date')
        ).values('period').annotate(
            revenue=Sum('amount'),
            tax=Sum('total_tax_amount'),
            count=Count('id')
        ).order_by('period')
        
        labels = []
        revenue_values = []
        tax_values = []
        
        for item in revenue_data:
            labels.append(item['period'].strftime('%Y-%m-%d') if item['period'] else 'N/A')
            revenue_values.append(float(item['revenue']) if item['revenue'] else 0)
            tax_values.append(float(item['tax']) if item['tax'] else 0)
        
        return Response({
            'labels': labels,
            'datasets': [
                {
                    'label': 'Revenue',
                    'data': revenue_values
                },
                {
                    'label': 'Taxes',
                    'data': tax_values
                }
            ]
        })


# ============================================================================
# Subscription Status Endpoint (for frontend integration)
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def subscription_status(request):
    """
    Get comprehensive subscription status for the current user's business.
    
    This endpoint provides all information needed by the frontend to:
    - Display subscription status
    - Show/hide features based on subscription
    - Display renewal prompts
    - Enforce storefront limits
    
    Returns:
        JSON object with subscription status, tier info, features available,
        and storefront limits.
    """
    from .utils import SubscriptionChecker
    
    # Get user's business
    business = getattr(request.user, 'business', None)
    
    if not business:
        return Response({
            'error': 'User is not associated with a business',
            'has_business': False
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Get comprehensive subscription status
    subscription_status_data = SubscriptionChecker.get_subscription_status(business)
    
    return Response(subscription_status_data, status=status.HTTP_200_OK)
