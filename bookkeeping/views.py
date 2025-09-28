from rest_framework import viewsets, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import AccountType, Account, JournalEntry, LedgerEntry, TrialBalance, FinancialPeriod, Budget


class AccountTypeViewSet(viewsets.ModelViewSet):
    queryset = AccountType.objects.all()
    permission_classes = [permissions.IsAuthenticated]


class AccountViewSet(viewsets.ModelViewSet):
    queryset = Account.objects.all()
    permission_classes = [permissions.IsAuthenticated]


class JournalEntryViewSet(viewsets.ModelViewSet):
    queryset = JournalEntry.objects.all()
    permission_classes = [permissions.IsAuthenticated]


class LedgerEntryViewSet(viewsets.ModelViewSet):
    queryset = LedgerEntry.objects.all()
    permission_classes = [permissions.IsAuthenticated]


class TrialBalanceViewSet(viewsets.ModelViewSet):
    queryset = TrialBalance.objects.all()
    permission_classes = [permissions.IsAuthenticated]


class FinancialPeriodViewSet(viewsets.ModelViewSet):
    queryset = FinancialPeriod.objects.all()
    permission_classes = [permissions.IsAuthenticated]


class BudgetViewSet(viewsets.ModelViewSet):
    queryset = Budget.objects.all()
    permission_classes = [permissions.IsAuthenticated]


class FinancialReportView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        return Response([])
