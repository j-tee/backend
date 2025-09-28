from rest_framework import viewsets, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Customer, Sale, SaleItem, Payment, Refund, RefundItem, CreditTransaction


class CustomerViewSet(viewsets.ModelViewSet):
    queryset = Customer.objects.all()
    permission_classes = [permissions.IsAuthenticated]


class SaleViewSet(viewsets.ModelViewSet):
    queryset = Sale.objects.all()
    permission_classes = [permissions.IsAuthenticated]


class SaleItemViewSet(viewsets.ModelViewSet):
    queryset = SaleItem.objects.all()
    permission_classes = [permissions.IsAuthenticated]


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    permission_classes = [permissions.IsAuthenticated]


class RefundViewSet(viewsets.ModelViewSet):
    queryset = Refund.objects.all()
    permission_classes = [permissions.IsAuthenticated]


class RefundItemViewSet(viewsets.ModelViewSet):
    queryset = RefundItem.objects.all()
    permission_classes = [permissions.IsAuthenticated]


class CreditTransactionViewSet(viewsets.ModelViewSet):
    queryset = CreditTransaction.objects.all()
    permission_classes = [permissions.IsAuthenticated]


class SalesReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        return Response([])


class CustomerCreditReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        return Response([])
