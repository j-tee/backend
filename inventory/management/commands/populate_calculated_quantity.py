from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum

from inventory.models import StockProduct
from inventory.stock_adjustments import StockAdjustment

class Command(BaseCommand):
    help = 'Populate or recalculate StockProduct.calculated_quantity from intake quantity and completed adjustments. Dry-run by default; use --apply to write.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Apply calculated values to the DB')
        parser.add_argument('--limit', type=int, default=0, help='Limit number of StockProduct rows to process (0 = all)')

    def handle(self, *args, **options):
        do_apply = options['apply']
        limit = options['limit']

        qs = StockProduct.objects.all().order_by('id')
        if limit > 0:
            qs = qs[:limit]

        count = qs.count()
        self.stdout.write(f'Found {count} StockProduct rows to inspect')

        processed = 0
        for sp in qs:
            # base intake
            base = int(sp.quantity or 0)
            # sum completed adjustments quantities for this stock product
            adj_sum = StockAdjustment.objects.filter(stock_product=sp, status='COMPLETED').aggregate(total=Sum('quantity'))['total'] or 0
            # calculated = intake + sum(adjustments)
            calc = base + int(adj_sum)

            self.stdout.write('---')
            self.stdout.write(f'StockProduct {sp.id} product={sp.product_id} intake={base} adjustments_sum={adj_sum} proposed_calculated={calc} current_calculated={getattr(sp, "calculated_quantity", None)}')

            if do_apply:
                try:
                    with transaction.atomic():
                        sp.calculated_quantity = calc
                        sp.save(update_fields=['calculated_quantity'])
                        processed += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Failed to update {sp.id}: {e}'))

        if do_apply:
            self.stdout.write(self.style.SUCCESS(f'Applied calculated_quantity to {processed} StockProduct rows'))
        else:
            self.stdout.write(self.style.SUCCESS('DRY-RUN complete. Rerun with --apply to update DB'))
