# Quick DB verification script. Run with: ./scripts/run_manage.sh shell -c "exec(open('scripts/verify_db.py').read())"
from django.db.models import Count
from inventory.models import StockProduct
from inventory.stock_adjustments import StockAdjustment
import pprint

print('=== StockProducts sample (most recently updated, up to 20) ===')
for sp in StockProduct.objects.all().order_by('-updated_at')[:20]:
    print(f'id={sp.id} product={sp.product_id} warehouse={sp.warehouse_id} intake={sp.quantity} calculated={getattr(sp, "calculated_quantity", None)} stock={sp.stock_id}')

print('\n=== Recent transfer references (up to 20) ===')
refs = (StockAdjustment.objects.filter(adjustment_type__in=['TRANSFER_IN','TRANSFER_OUT'])
        .values('reference_number')
        .annotate(cnt=Count('id'))
        .filter(reference_number__isnull=False)
        .order_by('-reference_number')[:20])

pprint.pprint(list(refs))

for r in refs:
    ref = r['reference_number']
    print('\n--- Reference:', ref)
    adjustments = StockAdjustment.objects.filter(reference_number=ref).select_related('stock_product__warehouse','stock_product__product').order_by('created_at')
    for a in adjustments:
        sp = a.stock_product
        print(f' adj_id={a.id} type={a.adjustment_type} status={a.status} qty={a.quantity} sp_id={getattr(sp, "id", None)} intake={getattr(sp, "quantity", None)} calc={getattr(sp, "calculated_quantity", None)}')

print('\n=== Done ===')
