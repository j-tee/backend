#!/usr/bin/env python
"""
Demonstration of Proportional Profit Calculation Impact

This script shows the difference between the old and new approach
for calculating cash on hand and outstanding credit profit.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from decimal import Decimal

print("=" * 90)
print("PROPORTIONAL PROFIT CALCULATION - DEMONSTRATION")
print("=" * 90)
print()

# Simulated business scenario
scenarios = [
    {
        'name': 'Fully Unpaid Credit Sale (PENDING)',
        'total_amount': Decimal('1000'),
        'amount_paid': Decimal('0'),
        'amount_due': Decimal('1000'),
        'profit': Decimal('300'),
    },
    {
        'name': 'Partially Paid Credit Sale (PARTIAL) - 40% Paid',
        'total_amount': Decimal('1000'),
        'amount_paid': Decimal('400'),
        'amount_due': Decimal('600'),
        'profit': Decimal('300'),
    },
    {
        'name': 'Partially Paid Credit Sale (PARTIAL) - 75% Paid',
        'total_amount': Decimal('2000'),
        'amount_paid': Decimal('1500'),
        'amount_due': Decimal('500'),
        'profit': Decimal('600'),
    },
    {
        'name': 'Fully Paid Credit Sale (COMPLETED)',
        'total_amount': Decimal('1000'),
        'amount_paid': Decimal('1000'),
        'amount_due': Decimal('0'),
        'profit': Decimal('300'),
    },
]

total_old_outstanding = Decimal('0')
total_new_outstanding = Decimal('0')
total_old_cash_on_hand = Decimal('0')
total_new_cash_on_hand = Decimal('0')
total_profit = Decimal('0')

print("Analyzing each scenario:")
print()

for i, scenario in enumerate(scenarios, 1):
    name = scenario['name']
    total = scenario['total_amount']
    paid = scenario['amount_paid']
    due = scenario['amount_due']
    profit = scenario['profit']
    
    # Old approach: All profit is outstanding for PENDING/PARTIAL
    if due > 0:
        old_outstanding = profit
        old_realized = Decimal('0')
    else:
        old_outstanding = Decimal('0')
        old_realized = profit
    
    # New approach: Proportional allocation
    if total > 0:
        outstanding_ratio = due / total
        realized_ratio = paid / total
        new_outstanding = profit * outstanding_ratio
        new_realized = profit * realized_ratio
    else:
        new_outstanding = Decimal('0')
        new_realized = Decimal('0')
    
    # Only add to cash on hand if COMPLETED in old approach
    if due == 0:
        old_cash_contribution = profit
    else:
        old_cash_contribution = Decimal('0')
    
    # New approach always includes realized profit
    new_cash_contribution = new_realized
    
    total_old_outstanding += old_outstanding
    total_new_outstanding += new_outstanding
    total_old_cash_on_hand += old_cash_contribution
    total_new_cash_on_hand += new_cash_contribution
    total_profit += profit
    
    print(f"Scenario {i}: {name}")
    print(f"  Sale: ${total} | Paid: ${paid} ({float(paid/total*100):.1f}%) | Due: ${due}")
    print(f"  Total Profit: ${profit}")
    print()
    print(f"  OLD APPROACH (All or Nothing):")
    print(f"    Outstanding Profit: ${old_outstanding}")
    print(f"    Realized Profit: ${old_realized}")
    print(f"    Cash on Hand Contribution: ${old_cash_contribution}")
    print()
    print(f"  NEW APPROACH (Proportional):")
    print(f"    Outstanding Profit: ${new_outstanding:.2f}")
    print(f"    Realized Profit: ${new_realized:.2f}")
    print(f"    Cash on Hand Contribution: ${new_cash_contribution:.2f}")
    print()
    
    difference = new_cash_contribution - old_cash_contribution
    if difference > 0:
        print(f"  ✅ IMPROVEMENT: Cash on hand increased by ${difference:.2f}")
    elif difference < 0:
        print(f"  ⚠️  CHANGE: Cash on hand decreased by ${abs(difference):.2f}")
    else:
        print(f"  ➡️  NO CHANGE: Same result in both approaches")
    print()
    print("-" * 90)
    print()

# Summary comparison
print("=" * 90)
print("OVERALL BUSINESS IMPACT")
print("=" * 90)
print()
print(f"Total Profit from all sales: ${total_profit}")
print()
print("OLD APPROACH:")
print(f"  Outstanding Credit Profit: ${total_old_outstanding}")
print(f"  Cash on Hand (Profit): ${total_old_cash_on_hand}")
print()
print("NEW APPROACH:")
print(f"  Outstanding Credit Profit: ${total_new_outstanding:.2f}")
print(f"  Cash on Hand (Profit): ${total_new_cash_on_hand:.2f}")
print()

improvement = total_new_cash_on_hand - total_old_cash_on_hand
print("=" * 90)
print("KEY INSIGHT")
print("=" * 90)
print()
if improvement > 0:
    print(f"✅ Cash on hand increased by ${improvement:.2f}")
    print()
    print("The new proportional calculation recognizes that:")
    print(f"  • ${improvement:.2f} in profit was already realized from partial payments")
    print("  • This money is available for business operations")
    print("  • Outstanding credit only reflects the truly unpaid portion")
elif improvement < 0:
    print(f"⚠️  Cash on hand decreased by ${abs(improvement):.2f}")
    print()
    print("This represents a more conservative, accurate view.")
else:
    print("➡️  No change - all sales were either fully paid or fully unpaid")

print()
print("=" * 90)
print("BUSINESS VALUE")
print("=" * 90)
print()
print("✓ Accurate Financial Position:")
print("  Shows the actual profit you've collected, not just from completed sales")
print()
print("✓ Better Decision Making:")
print("  Make informed decisions based on true available profit")
print()
print("✓ Automatic Updates:")
print("  As customers pay, cash on hand automatically increases")
print()
print("✓ Alignment with Revenue Accounting:")
print("  Mirrors how cash_at_hand and accounts_receivable work")
print()
print("=" * 90)
print("✅ DEMONSTRATION COMPLETE")
print("=" * 90)
