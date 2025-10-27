# Check sales/reservations that reference a given StockProduct id
from django.db.models import Sum
SP_ID = '0646446d-59b2-4c99-baec-d3376fcb6e9b'
print('Inspecting', SP_ID)
try:
    from sales.models import SaleItem, Sale
    sale_qty = SaleItem.objects.filter(stock_product_id=SP_ID).aggregate(total=Sum('quantity'))['total'] or 0
    print('SaleItems referencing this stock_product: total quantity =', sale_qty)
    # Show last 10 sale items
    for si in SaleItem.objects.filter(stock_product_id=SP_ID).order_by('-created_at')[:10]:
        print(' ', si.id, si.quantity, si.sale_id, getattr(si, 'created_at', None))
except Exception as e:
    print('No sale items or error:', e)

# Check reservations (if model exists)
try:
    from inventory.models import Reservation
    res_sum = Reservation.objects.filter(stock_product_id=SP_ID, status='ACTIVE').aggregate(total=Sum('quantity'))['total'] or 0
    print('Active reservations total qty =', res_sum)
except Exception as e:
    print('No Reservation model or error:', e)

# Check storefront transfers adjustments (not stock_adjustments) - attempt to find any other models that may decrement calculated_quantity
print('Done')
