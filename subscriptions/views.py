from rest_framework import viewsets, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import (
    SubscriptionPlan, Subscription, SubscriptionPayment, PaymentGatewayConfig,
    WebhookEvent, UsageTracking, Invoice
)


class SubscriptionPlanViewSet(viewsets.ModelViewSet):
    queryset = SubscriptionPlan.objects.all()
    permission_classes = [permissions.IsAuthenticated]


class SubscriptionViewSet(viewsets.ModelViewSet):
    queryset = Subscription.objects.all()
    permission_classes = [permissions.IsAuthenticated]


class SubscriptionPaymentViewSet(viewsets.ModelViewSet):
    queryset = SubscriptionPayment.objects.all()
    permission_classes = [permissions.IsAuthenticated]


class PaymentGatewayConfigViewSet(viewsets.ModelViewSet):
    queryset = PaymentGatewayConfig.objects.all()
    permission_classes = [permissions.IsAuthenticated]


class WebhookEventViewSet(viewsets.ModelViewSet):
    queryset = WebhookEvent.objects.all()
    permission_classes = [permissions.IsAuthenticated]


class UsageTrackingViewSet(viewsets.ModelViewSet):
    queryset = UsageTracking.objects.all()
    permission_classes = [permissions.IsAuthenticated]


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.all()
    permission_classes = [permissions.IsAuthenticated]


class PaymentWebhookView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        return Response({'status': 'received'})


class SubscriptionReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        return Response([])
