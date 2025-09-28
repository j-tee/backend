import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from decimal import Decimal


User = get_user_model()


class AccountType(models.Model):
    """Chart of accounts types"""
    ACCOUNT_CATEGORIES = [
        ('ASSET', 'Asset'),
        ('LIABILITY', 'Liability'),
        ('EQUITY', 'Equity'),
        ('REVENUE', 'Revenue'),
        ('EXPENSE', 'Expense'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    category = models.CharField(max_length=20, choices=ACCOUNT_CATEGORIES)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'account_types'
        ordering = ['code', 'name']
    
    def __str__(self):
        return f"{self.code} - {self.name}"


class Account(models.Model):
    """Chart of accounts for bookkeeping"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    account_type = models.ForeignKey(AccountType, on_delete=models.PROTECT, related_name='accounts')
    code = models.CharField(max_length=20, unique=True)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'accounts'
        ordering = ['code', 'name']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['account_type', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    @property
    def account_category(self):
        return self.account_type.category


class JournalEntry(models.Model):
    """Journal entries for double-entry bookkeeping"""
    ENTRY_TYPE_CHOICES = [
        ('SALE', 'Sale'),
        ('PURCHASE', 'Purchase'),
        ('PAYMENT', 'Payment'),
        ('RECEIPT', 'Receipt'),
        ('TRANSFER', 'Transfer'),
        ('ADJUSTMENT', 'Adjustment'),
        ('OPENING_BALANCE', 'Opening Balance'),
        ('CLOSING', 'Closing Entry'),
    ]
    
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('POSTED', 'Posted'),
        ('REVERSED', 'Reversed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entry_number = models.CharField(max_length=50, unique=True)
    entry_type = models.CharField(max_length=20, choices=ENTRY_TYPE_CHOICES)
    description = models.TextField()
    reference_id = models.UUIDField(null=True, blank=True)  # Sale ID, Purchase ID, etc.
    reference_number = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    total_debit = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    total_credit = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='journal_entries')
    posted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='posted_entries')
    posted_at = models.DateTimeField(null=True, blank=True)
    entry_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'journal_entries'
        ordering = ['-entry_date', '-created_at']
        indexes = [
            models.Index(fields=['entry_number']),
            models.Index(fields=['entry_type', 'status']),
            models.Index(fields=['entry_date', 'status']),
            models.Index(fields=['reference_id']),
        ]
    
    def __str__(self):
        return f"{self.entry_number} - {self.description}"
    
    def is_balanced(self):
        """Check if journal entry is balanced (debits = credits)"""
        return self.total_debit == self.total_credit
    
    def calculate_totals(self):
        """Calculate total debits and credits"""
        entries = self.ledger_entries.all()
        self.total_debit = sum(entry.debit_amount for entry in entries)
        self.total_credit = sum(entry.credit_amount for entry in entries)
        return self.is_balanced()


class LedgerEntry(models.Model):
    """Individual ledger entries (journal entry lines)"""
    ENTRY_TYPE_CHOICES = [
        ('DEBIT', 'Debit'),
        ('CREDIT', 'Credit'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name='ledger_entries')
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='ledger_entries')
    entry_type = models.CharField(max_length=10, choices=ENTRY_TYPE_CHOICES)
    debit_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    credit_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    description = models.TextField(blank=True, null=True)
    
    class Meta:
        db_table = 'ledger_entries'
        indexes = [
            models.Index(fields=['journal_entry', 'account']),
            models.Index(fields=['account', 'entry_type']),
        ]
    
    def __str__(self):
        amount = self.debit_amount if self.entry_type == 'DEBIT' else self.credit_amount
        return f"{self.account.name} - {self.entry_type} - {amount}"
    
    def clean(self):
        """Ensure only one of debit or credit has a value"""
        from django.core.exceptions import ValidationError
        if self.debit_amount > 0 and self.credit_amount > 0:
            raise ValidationError("An entry cannot have both debit and credit amounts.")
        if self.debit_amount == 0 and self.credit_amount == 0:
            raise ValidationError("An entry must have either a debit or credit amount.")


class TrialBalance(models.Model):
    """Trial balance snapshots"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    period_start = models.DateField()
    period_end = models.DateField()
    total_debits = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    total_credits = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    is_balanced = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='trial_balances')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'trial_balances'
        ordering = ['-period_end']
        unique_together = ['period_start', 'period_end']
    
    def __str__(self):
        return f"Trial Balance {self.period_start} to {self.period_end}"


class TrialBalanceEntry(models.Model):
    """Individual account balances in trial balance"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    trial_balance = models.ForeignKey(TrialBalance, on_delete=models.CASCADE, related_name='entries')
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='trial_balance_entries')
    debit_balance = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    credit_balance = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    class Meta:
        db_table = 'trial_balance_entries'
        unique_together = ['trial_balance', 'account']
    
    def __str__(self):
        return f"{self.account.name} - DB: {self.debit_balance}, CR: {self.credit_balance}"


class FinancialPeriod(models.Model):
    """Financial periods for reporting"""
    PERIOD_TYPE_CHOICES = [
        ('MONTHLY', 'Monthly'),
        ('QUARTERLY', 'Quarterly'),
        ('YEARLY', 'Yearly'),
    ]
    
    STATUS_CHOICES = [
        ('OPEN', 'Open'),
        ('CLOSED', 'Closed'),
        ('LOCKED', 'Locked'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    period_type = models.CharField(max_length=20, choices=PERIOD_TYPE_CHOICES)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    closed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='closed_periods')
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'financial_periods'
        ordering = ['-start_date']
        unique_together = ['start_date', 'end_date']
    
    def __str__(self):
        return f"{self.name} ({self.start_date} to {self.end_date})"


class Budget(models.Model):
    """Budget planning"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    financial_period = models.ForeignKey(FinancialPeriod, on_delete=models.CASCADE, related_name='budgets')
    total_budget = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    actual_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    variance = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='budgets')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'budgets'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.financial_period.name}"
    
    def calculate_variance(self):
        """Calculate budget variance"""
        self.variance = self.actual_amount - self.total_budget
        return self.variance


class BudgetLine(models.Model):
    """Individual budget line items"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    budget = models.ForeignKey(Budget, on_delete=models.CASCADE, related_name='budget_lines')
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='budget_lines')
    budgeted_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    actual_amount = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    variance = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        db_table = 'budget_lines'
        unique_together = ['budget', 'account']
    
    def __str__(self):
        return f"{self.budget.name} - {self.account.name}"
    
    def calculate_variance(self):
        """Calculate line item variance"""
        self.variance = self.actual_amount - self.budgeted_amount
        return self.variance
