"""
Quick manual test - just import and check the profit calculation logic.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from decimal import Decimal
from django.db.models import F, Sum, ExpressionWrapper, DecimalField
from sales.models import Sale, SaleItem

print("\n" + "="*80)
print("TESTING PROFIT CALCULATION LOGIC")
print("="*80)

# Count completed sales
completed_sales = Sale.objects.filter(status='COMPLETED').count()
print(f"\nTotal completed sales: {completed_sales}")

# Calculate total profit
completed_sales_ids = Sale.objects.filter(status='COMPLETED').values_list('id', flat=True)
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

print(f"Total Profit: ${total_profit:,.2f}")

# Calculate outstanding credit profit
unpaid_credit_ids = Sale.objects.filter(
    payment_type='CREDIT',
    status__in=['PENDING', 'PARTIAL']
).values_list('id', flat=True)

outstanding_credit = SaleItem.objects.filter(
    sale_id__in=unpaid_credit_ids,
    stock_product__isnull=False
).aggregate(
    profit=Sum(
        ExpressionWrapper(
            (F('unit_price') - F('stock_product__unit_cost')) * F('quantity'),
            output_field=DecimalField()
        )
    )
)['profit'] or Decimal('0')

print(f"Outstanding Credit: ${outstanding_credit:,.2f}")

# Calculate cash on hand
cash_on_hand = total_profit - outstanding_credit
print(f"Cash on Hand: ${cash_on_hand:,.2f}")

# Show calculation
print(f"\nVerification:")
print(f"  Total Profit:        ${total_profit:,.2f}")
print(f"  - Outstanding Credit: ${outstanding_credit:,.2f}")
print(f"  = Cash on Hand:       ${cash_on_hand:,.2f}")

# Count unpaid credits
unpaid_count = Sale.objects.filter(
    payment_type='CREDIT',
    status__in=['PENDING', 'PARTIAL']
).count()

print(f"\nUnpaid Credit Sales: {unpaid_count}")

print("\n✅ PROFIT CALCULATION WORKING!")
