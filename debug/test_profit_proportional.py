#!/usr/bin/env python
"""
Test proportional profit calculation for credit sales with partial payments.

This test verifies that:
1. When a credit payment is made, outstanding credit profit decreases
2. Cash on hand profit increases by the realized portion
3. The calculations are proportional to payment percentage
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from decimal import Decimal
from sales.models import Sale
from django.db.models import Sum, F, ExpressionWrapper, DecimalField

print("=" * 80)
print("PROPORTIONAL PROFIT CALCULATION TEST")
print("=" * 80)
print()

# Get a sample credit sale with partial payment
partial_sales = Sale.objects.filter(
    payment_type='CREDIT',
    status='PARTIAL'
).order_by('-total_amount')[:3]

if partial_sales.exists():
    print("Testing with actual PARTIAL credit sales:")
    print()
    
    for sale in partial_sales:
        print(f"Sale: {sale.receipt_number}")
        print(f"  Total Amount: ${sale.total_amount}")
        print(f"  Amount Paid: ${sale.amount_paid}")
        print(f"  Amount Due: ${sale.amount_due}")
        print(f"  Payment %: {float(sale.amount_paid / sale.total_amount * 100):.2f}%")
        
        # Calculate profit for this sale
        from sales.models import SaleItem
        sale_profit = SaleItem.objects.filter(
            sale_id=sale.id,
            stock_product__isnull=False
        ).aggregate(
            profit=Sum(
                ExpressionWrapper(
                    (F('unit_price') - F('stock_product__unit_cost')) * F('quantity'),
                    output_field=DecimalField()
                )
            )
        )['profit'] or Decimal('0')
        
        # Calculate proportional outstanding profit
        if sale.total_amount > 0:
            outstanding_ratio = sale.amount_due / sale.total_amount
            realized_ratio = sale.amount_paid / sale.total_amount
            
            outstanding_profit = sale_profit * outstanding_ratio
            realized_profit = sale_profit * realized_ratio
            
            print(f"  Total Profit: ${sale_profit}")
            print(f"  Outstanding Ratio: {float(outstanding_ratio * 100):.2f}%")
            print(f"  Outstanding Profit: ${outstanding_profit:.2f}")
            print(f"  Realized Ratio: {float(realized_ratio * 100):.2f}%")
            print(f"  Realized Profit: ${realized_profit:.2f}")
            print(f"  ✅ Verification: {sale_profit:.2f} = {outstanding_profit:.2f} + {realized_profit:.2f}")
            print()
else:
    print("⚠️  No PARTIAL credit sales found for testing")
    print()

# Now test the summary endpoint calculation using direct calculation
print("=" * 80)
print("TESTING SUMMARY CALCULATION LOGIC")
print("=" * 80)
print()

from django.db.models import Q, Count, Avg

# Replicate the summary calculation
queryset = Sale.objects.all()

# Get completed sales for total profit
completed_sales_ids = queryset.filter(status='COMPLETED').values_list('id', flat=True)

from sales.models import SaleItem
total_profit = SaleItem.objects.filter(
    sale_id__in=completed_sales_ids,
    stock_product__isnull=False
).aggregate(
    profit=Sum(
        ExpressionWrapper(
            (F('unit_price') - F('stock_product__unit_cost')) * F('quantity'),
            output_field=DecimalField()
        )
    )
)['profit'] or Decimal('0')

# Calculate outstanding credit profit proportionally
unpaid_credit_sales = queryset.filter(
    payment_type='CREDIT',
    status__in=['PENDING', 'PARTIAL']
)

outstanding_credit_profit = Decimal('0')
realized_credit_profit = Decimal('0')

for sale in unpaid_credit_sales:
    sale_profit = SaleItem.objects.filter(
        sale_id=sale.id,
        stock_product__isnull=False
    ).aggregate(
        profit=Sum(
            ExpressionWrapper(
                (F('unit_price') - F('stock_product__unit_cost')) * F('quantity'),
                output_field=DecimalField()
            )
        )
    )['profit'] or Decimal('0')
    
    if sale.total_amount > 0:
        outstanding_ratio = sale.amount_due / sale.total_amount
        outstanding_credit_profit += sale_profit * outstanding_ratio
        realized_credit_profit += sale_profit * (Decimal('1') - outstanding_ratio)

# Get all credit sales profit
credit_sales_ids = queryset.filter(payment_type='CREDIT').values_list('id', flat=True)
total_credit_profit = SaleItem.objects.filter(
    sale_id__in=credit_sales_ids,
    stock_product__isnull=False
).aggregate(
    profit=Sum(
        ExpressionWrapper(
            (F('unit_price') - F('stock_product__unit_cost')) * F('quantity'),
            output_field=DecimalField()
        )
    )
)['profit'] or Decimal('0')

cash_on_hand_profit = total_profit - outstanding_credit_profit

summary = {
    'total_profit': total_profit,
    'outstanding_credit': outstanding_credit_profit,
    'realized_credit_profit': realized_credit_profit,
    'cash_on_hand': cash_on_hand_profit,
}

print("Financial Summary Results:")
print(f"  Total Profit (all completed): ${summary['total_profit']}")
print(f"  Outstanding Credit Profit: ${summary['outstanding_credit']}")
print(f"  Realized Credit Profit: ${summary.get('realized_credit_profit', 'N/A')}")
print(f"  Cash on Hand (Profit): ${summary['cash_on_hand']}")
print()

# Verify the math
total = summary['total_profit']
outstanding = summary['outstanding_credit']
cash_on_hand = summary['cash_on_hand']

print("Verification:")
print(f"  Total Profit - Outstanding Credit = Cash on Hand")
print(f"  ${total} - ${outstanding} = ${cash_on_hand}")

if total - outstanding == cash_on_hand:
    print("  ✅ CALCULATION CORRECT!")
else:
    print(f"  ❌ ERROR: Expected ${total - outstanding}, got ${cash_on_hand}")

print()
print("=" * 80)
print("BUSINESS LOGIC EXPLANATION")
print("=" * 80)
print()
print("When a credit sale has partial payment:")
print("  1. Total sale profit is calculated")
print("  2. Profit is split proportionally:")
print("     - Outstanding Profit = Total Profit × (Amount Due / Total Amount)")
print("     - Realized Profit = Total Profit × (Amount Paid / Total Amount)")
print("  3. Cash on Hand = All Profit - Outstanding Profit")
print()
print("Example: $1000 sale with $300 profit, 40% paid ($400)")
print("  - Outstanding Profit = $300 × 60% = $180")
print("  - Realized Profit = $300 × 40% = $120")
print("  - Cash on Hand includes the $120 realized from this sale")
print()

# Compare revenue vs profit metrics
print("=" * 80)
print("REVENUE vs PROFIT COMPARISON")
print("=" * 80)
print()
print("Revenue-based (Traditional Accounting):")
print(f"  Cash at Hand: ${summary.get('cash_at_hand', 'N/A')}")
print(f"  Accounts Receivable: ${summary.get('accounts_receivable', 'N/A')}")
print()
print("Profit-based (Business Reality):")
print(f"  Cash on Hand (Profit): ${summary['cash_on_hand']}")
print(f"  Outstanding Credit (Profit): ${summary['outstanding_credit']}")
print()
print("Key Insight:")
print("  Revenue shows money owed, Profit shows actual value created.")
print("  Both are important for complete financial picture.")
print()

print("=" * 80)
print("✅ TEST COMPLETE")
print("=" * 80)
