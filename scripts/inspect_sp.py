# Quick inspection helper for a given StockProduct id
from django.db.models import Sum
from inventory.models import StockProduct
from inventory.stock_adjustments import StockAdjustment

SP_ID = '0646446d-59b2-4c99-baec-d3376fcb6e9b'  # source from recent transfer

sp = StockProduct.objects.select_related('product', 'warehouse', 'stock').get(id=SP_ID)
print('STOCK_PRODUCT', sp.id)
print('  product_id:', sp.product_id)
print('  warehouse_id:', sp.warehouse_id)
print('  intake (quantity):', sp.quantity)
print('  calculated_quantity:', sp.calculated_quantity)

all_adj = StockAdjustment.objects.filter(stock_product=sp).order_by('created_at')
print('\nAll adjustments for this stock product (chronological):')
for a in all_adj:
    print(' ', a.id, a.adjustment_type, a.quantity, a.status, a.created_at, a.reference_number)

comp_sum = all_adj.filter(status='COMPLETED').aggregate(total=Sum('quantity'))['total'] or 0
print('\nSum of completed adjustments on this stock product:', comp_sum)

# Product-level completed adjustments (for context)
prod_adj_sum = StockAdjustment.objects.filter(stock_product__product_id=sp.product_id, status='COMPLETED').aggregate(total=Sum('quantity'))['total'] or 0
print('Product-level completed adjustment sum:', prod_adj_sum)

# List completed adjustments only
print('\nCompleted adjustments:')
for a in all_adj.filter(status='COMPLETED'):
    print(' ', a.id, a.adjustment_type, a.quantity, a.completed_at, a.reference_number)

print('\nDone')
