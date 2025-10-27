from django.db.models import Sum
from inventory.models import StockProduct
from inventory.stock_adjustments import StockAdjustment

SP_ID = '0646446d-59b2-4c99-baec-d3376fcb6e9b'
sp = StockProduct.objects.select_related('product','warehouse').get(id=SP_ID)
base = int(sp.quantity or 0)
adj_sum = StockAdjustment.objects.filter(stock_product=sp, status='COMPLETED').aggregate(total=Sum('quantity'))['total'] or 0
expected = base + int(adj_sum)
print('StockProduct:', sp.id)
print('  intake (quantity):', base)
print('  current calculated_quantity:', sp.calculated_quantity)
print('  sum of completed adjustments for this stock_product:', adj_sum)
print('  expected calculated_quantity = intake + adjustments =', expected)

# show any other completed adjustments for the product excluding this stock_product
prod_sum = StockAdjustment.objects.filter(stock_product__product_id=sp.product_id, status='COMPLETED').exclude(stock_product=sp).aggregate(total=Sum('quantity'))['total'] or 0
print('Product-level completed adjustments excluding this SP:', prod_sum)

# Print any completed adjustments on this SP (ids)
print('\nCompleted adjustments on this SP:')
for a in StockAdjustment.objects.filter(stock_product=sp, status='COMPLETED'):
    print(' ', a.id, a.adjustment_type, a.quantity, a.reference_number, a.completed_at)
