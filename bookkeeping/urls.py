from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    AccountTypeViewSet, AccountViewSet, JournalEntryViewSet,
    LedgerEntryViewSet, TrialBalanceViewSet, FinancialPeriodViewSet,
    BudgetViewSet, FinancialReportView
)

router = DefaultRouter()
router.register(r'account-types', AccountTypeViewSet)
router.register(r'accounts', AccountViewSet)
router.register(r'journal-entries', JournalEntryViewSet)
router.register(r'ledger-entries', LedgerEntryViewSet)
router.register(r'trial-balances', TrialBalanceViewSet)
router.register(r'financial-periods', FinancialPeriodViewSet)
router.register(r'budgets', BudgetViewSet)

urlpatterns = [
    path('api/', include(router.urls)),
    path('api/reports/financial/', FinancialReportView.as_view(), name='financial-report'),
]