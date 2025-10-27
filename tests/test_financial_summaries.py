"""
Test Financial Summaries - Cash at Hand vs Accounts Receivable
Tests the enhanced financial analytics following proper accounting principles
"""
import sys
import os
import django

# Setup Django
sys.path.insert(0, '/home/teejay/Documents/Projects/pos/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from decimal import Decimal
from django.db.models import Sum, Q, Count
from sales.models import Sale, Payment

def run_financial_tests():
    """Run financial summary tests"""
    
    print("\n" + "="*90)
    print("FINANCIAL SUMMARIES - CASH AT HAND VS ACCOUNTS RECEIVABLE")
    print("="*90)
    print("\n📚 Accounting Principles:")
    print("  - Cash at Hand: Actual money received (liquid assets)")
    print("  - Accounts Receivable: Money owed from credit sales (current assets)")
    print("  - Total Revenue: Both cash and credit sales (accrual accounting)")
    print("="*90)
    
    # Get all completed sales
    completed_sales = Sale.objects.filter(status__in=['COMPLETED', 'PARTIAL', 'PENDING'])
    
    print(f"\n📊 Overall Sales Analysis")
    print("-"*90)
    
    # Total sales (accrual basis - all completed sales)
    total_revenue = Sale.objects.filter(status='COMPLETED').aggregate(
        total=Sum('total_amount')
    )['total'] or Decimal('0')
    
    # Cash at hand (actual money received)
    cash_at_hand = completed_sales.aggregate(
        total=Sum('amount_paid')
    )['total'] or Decimal('0')
    
    # Accounts receivable (money owed on credit sales)
    accounts_receivable = Sale.objects.filter(
        payment_type='CREDIT',
        status__in=['PENDING', 'PARTIAL']
    ).aggregate(
        total=Sum('amount_due')
    )['total'] or Decimal('0')
    
    print(f"\n💰 Financial Position:")
    print(f"  Total Revenue (Accrual):        ${total_revenue:,.2f}")
    print(f"  Cash at Hand (Received):        ${cash_at_hand:,.2f}")
    print(f"  Accounts Receivable (Owed):     ${accounts_receivable:,.2f}")
    print(f"  Total Assets (Cash + AR):       ${cash_at_hand + accounts_receivable:,.2f}")
    
    if cash_at_hand + accounts_receivable > 0:
        cash_pct = (cash_at_hand / (cash_at_hand + accounts_receivable)) * 100
        ar_pct = (accounts_receivable / (cash_at_hand + accounts_receivable)) * 100
        print(f"\n📈 Asset Composition:")
        print(f"  Cash Percentage:                {cash_pct:.2f}%")
        print(f"  Receivables Percentage:         {ar_pct:.2f}%")
    
    # Payment method breakdown
    print(f"\n💳 Payment Method Analysis")
    print("-"*90)
    
    payment_methods = ['CASH', 'CARD', 'MOBILE', 'CREDIT']
    for method in payment_methods:
        total = Sale.objects.filter(
            payment_type=method,
            status='COMPLETED'
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
        
        count = Sale.objects.filter(
            payment_type=method,
            status='COMPLETED'
        ).count()
        
        print(f"  {method:<10} Sales: ${total:>12,.2f}  ({count:>4} transactions)")
    
    # Credit sales detailed analysis
    print(f"\n📋 Credit Sales Detailed Analysis")
    print("-"*90)
    
    # All credit sales (both paid and unpaid)
    all_credit_sales = Sale.objects.filter(payment_type='CREDIT')
    
    # Unpaid credit sales
    unpaid_credit = all_credit_sales.filter(
        status='PENDING',
        amount_paid=Decimal('0.00')
    )
    unpaid_amount = unpaid_credit.aggregate(total=Sum('amount_due'))['total'] or Decimal('0')
    unpaid_count = unpaid_credit.count()
    
    # Partially paid credit sales
    partial_credit = all_credit_sales.filter(
        status='PARTIAL'
    )
    partial_amount = partial_credit.aggregate(total=Sum('amount_due'))['total'] or Decimal('0')
    partial_count = partial_credit.count()
    
    # Fully paid credit sales
    paid_credit = all_credit_sales.filter(
        status='COMPLETED'
    )
    paid_amount = paid_credit.aggregate(total=Sum('amount_paid'))['total'] or Decimal('0')
    paid_count = paid_credit.count()
    
    total_credit_sales = all_credit_sales.filter(status='COMPLETED').aggregate(
        total=Sum('total_amount')
    )['total'] or Decimal('0')
    
    print(f"\n  Total Credit Sales (Completed):  ${total_credit_sales:,.2f}")
    print(f"\n  Status Breakdown:")
    print(f"    Unpaid (PENDING):              ${unpaid_amount:>12,.2f}  ({unpaid_count:>3} sales)")
    print(f"    Partially Paid:                ${partial_amount:>12,.2f}  ({partial_count:>3} sales)")
    print(f"    Fully Paid (COMPLETED):        ${paid_amount:>12,.2f}  ({paid_count:>3} sales)")
    
    if total_credit_sales > 0:
        collection_rate = (paid_amount / total_credit_sales) * 100
        print(f"\n  Collection Rate:                 {collection_rate:.2f}%")
    
    # Sample unpaid credit sales
    if unpaid_credit.exists():
        print(f"\n  📝 Sample Unpaid Credit Sales:")
        for idx, sale in enumerate(unpaid_credit[:5], 1):
            print(f"    {idx}. Receipt: {sale.receipt_number or 'N/A':<25} "
                  f"Amount: ${sale.total_amount:>10,.2f}  "
                  f"Due: ${sale.amount_due:>10,.2f}  "
                  f"Customer: {sale.customer.name if sale.customer else 'N/A'}")
    
    # Cash flow analysis
    print(f"\n💵 Cash Flow Analysis")
    print("-"*90)
    
    # Cash sales (immediate cash)
    immediate_cash = Sale.objects.filter(
        payment_type__in=['CASH', 'CARD', 'MOBILE'],
        status='COMPLETED'
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
    
    # Credit sales that were paid (eventually became cash)
    credit_payments = Payment.objects.filter(
        sale__payment_type='CREDIT',
        status='SUCCESSFUL'
    ).aggregate(total=Sum('amount_paid'))['total'] or Decimal('0')
    
    print(f"\n  Immediate Cash (Cash/Card/Mobile):  ${immediate_cash:,.2f}")
    print(f"  Credit Payments Collected:          ${credit_payments:,.2f}")
    print(f"  Total Cash Received:                ${cash_at_hand:,.2f}")
    print(f"  Still Owed (Receivables):           ${accounts_receivable:,.2f}")
    
    # Business health metrics
    print(f"\n📊 Business Health Metrics")
    print("-"*90)
    
    total_sales_count = Sale.objects.filter(status='COMPLETED').count()
    credit_sales_count = all_credit_sales.filter(status='COMPLETED').count()
    
    if total_sales_count > 0:
        credit_percentage = (credit_sales_count / total_sales_count) * 100
        print(f"\n  Total Completed Sales:           {total_sales_count:>5} transactions")
        print(f"  Credit Sales:                    {credit_sales_count:>5} transactions ({credit_percentage:.1f}%)")
        print(f"  Cash Sales:                      {total_sales_count - credit_sales_count:>5} transactions ({100-credit_percentage:.1f}%)")
    
    if accounts_receivable > 0:
        receivables_to_revenue = (accounts_receivable / total_revenue) * 100 if total_revenue > 0 else 0
        print(f"\n  Receivables as % of Revenue:     {receivables_to_revenue:.2f}%")
        
        if receivables_to_revenue > 30:
            print(f"    ⚠️  WARNING: High receivables ratio (>30%)")
            print(f"        Recommendation: Focus on collecting outstanding payments")
        elif receivables_to_revenue > 15:
            print(f"    ⚡ MODERATE: Keep monitoring receivables")
        else:
            print(f"    ✅ HEALTHY: Low receivables ratio")
    
    # Summary for API response
    print(f"\n" + "="*90)
    print("API RESPONSE FORMAT (Simplified)")
    print("="*90)
    
    print(f"""
{{
  "summary": {{
    "total_sales": {total_revenue},
    "net_sales": {total_revenue},
    "cash_at_hand": {cash_at_hand},
    "accounts_receivable": {accounts_receivable},
    
    "financial_position": {{
      "cash_at_hand": {cash_at_hand},
      "accounts_receivable": {accounts_receivable},
      "total_assets": {cash_at_hand + accounts_receivable},
      "cash_percentage": {round(float((cash_at_hand / (cash_at_hand + accounts_receivable) * 100) if (cash_at_hand + accounts_receivable) > 0 else 0), 2)},
      "receivables_percentage": {round(float((accounts_receivable / (cash_at_hand + accounts_receivable) * 100) if (cash_at_hand + accounts_receivable) > 0 else 0), 2)}
    }},
    
    "credit_health": {{
      "total_credit_sales": {total_credit_sales},
      "unpaid_amount": {unpaid_amount},
      "partially_paid_amount": {partial_amount},
      "fully_paid_amount": {paid_amount},
      "collection_rate": {round(float((paid_amount / total_credit_sales * 100) if total_credit_sales else 0), 2)}
    }}
  }}
}}
""")
    
    print("="*90)
    print("✅ FINANCIAL SUMMARY TEST COMPLETE")
    print("="*90)
    print("\n📋 Key Insights:")
    print(f"  1. Total Revenue (Accrual Basis): ${total_revenue:,.2f}")
    print(f"  2. Cash Actually Received: ${cash_at_hand:,.2f}")
    print(f"  3. Money Still Owed: ${accounts_receivable:,.2f}")
    print(f"  4. This properly separates cash vs credit accounting!")
    print("\n💡 Tip: Use 'cash_at_hand' for cash flow analysis")
    print("         Use 'total_sales' for revenue/profit analysis")
    print("         Use 'accounts_receivable' for collection management")
    print("="*90 + "\n")

if __name__ == '__main__':
    run_financial_tests()
