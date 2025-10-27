"""
Subscription Views
API endpoints for subscription management
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q, Count, Sum, Avg
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
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
    Alert
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
    SubscriptionStatsSerializer
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
        """Initialize payment for subscription"""
        subscription = self.get_object()
        
        # Check if user is a member of the business with this subscription
        if not subscription.business.memberships.filter(user=request.user).exists() and not request.user.is_staff:
            return Response(
                {'detail': 'You do not have permission to pay for this subscription'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        gateway_type = request.data.get('gateway', 'PAYSTACK')
        callback_url = request.data.get('callback_url', request.build_absolute_uri('/'))
        
        try:
            gateway = get_payment_gateway(gateway_type)
            
            if gateway_type == 'PAYSTACK':
                result = gateway.initialize_payment(subscription, callback_url)
            elif gateway_type == 'STRIPE':
                success_url = request.data.get('success_url', callback_url)
                cancel_url = request.data.get('cancel_url', callback_url)
                result = gateway.create_checkout_session(subscription, success_url, cancel_url)
            else:
                return Response(
                    {'detail': 'Unsupported payment gateway'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            return Response(result)
        except PaymentGatewayError as e:
            logger.error(f"Payment initialization error: {str(e)}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def verify_payment(self, request, pk=None):
        """Verify payment for subscription"""
        subscription = self.get_object()
        
        gateway_type = request.data.get('gateway', 'PAYSTACK')
        reference = request.data.get('reference')
        
        if not reference:
            return Response(
                {'detail': 'Payment reference is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            gateway = get_payment_gateway(gateway_type)
            
            if gateway_type == 'PAYSTACK':
                verification = gateway.verify_payment(reference)
                if verification['success']:
                    payment = gateway.create_subscription_payment(subscription, verification)
                    return Response({
                        'success': True,
                        'message': 'Payment verified successfully',
                        'payment': SubscriptionPaymentSerializer(payment).data
                    })
            elif gateway_type == 'STRIPE':
                session_id = reference
                session_data = gateway.retrieve_session(session_id)
                if session_data['payment_status'] == 'paid':
                    payment = gateway.create_subscription_payment(subscription, session_data)
                    return Response({
                        'success': True,
                        'message': 'Payment verified successfully',
                        'payment': SubscriptionPaymentSerializer(payment).data
                    })
            
            return Response(
                {'success': False, 'message': 'Payment verification failed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except PaymentGatewayError as e:
            logger.error(f"Payment verification error: {str(e)}")
            return Response(
                {'detail': str(e)},
                status=status.HTTP_400_BAD_REQUEST
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
