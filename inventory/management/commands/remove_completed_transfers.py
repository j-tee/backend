from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from inventory.stock_adjustments import StockAdjustment
from inventory.models import StockProduct, Stock


class Command(BaseCommand):
    help = 'Remove completed paired warehouse transfers (TRANSFER_OUT/TRANSFER_IN). Dry-run by default; use --apply to execute.'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Apply changes. Without this flag the command runs in dry-run mode')
        parser.add_argument('--restore-source', action='store_true', default=True, help='Restore source StockProduct.quantity by the transferred amount when removing transfers')
        parser.add_argument('--limit', type=int, default=0, help='Limit number of transfers processed (0 = no limit)')
        parser.add_argument('--force', action='store_true', help='Process unpaired transfer adjustments (best-effort). Use with caution.')

    def handle(self, *args, **options):
        do_apply = options['apply']
        restore_source = options['restore_source']
        limit = options['limit']

        # Find reference_numbers that have completed transfer adjustments
        qs = StockAdjustment.objects.filter(adjustment_type__in=['TRANSFER_OUT', 'TRANSFER_IN'], status='COMPLETED')
        refs = (
            qs.values('reference_number')
            .annotate(cnt=Count('id'))
            .filter(reference_number__isnull=False)
            .order_by('reference_number')
        )

        if limit > 0:
            refs = refs[:limit]

        refs = list(refs)
        if not refs:
            self.stdout.write(self.style.SUCCESS('No completed transfer reference groups found.'))
            return

        self.stdout.write(f'Found {len(refs)} completed transfer reference(s) to inspect')

        to_process = []
        for r in refs:
            ref = r['reference_number']
            adjustments = list(qs.filter(reference_number=ref).order_by('created_at'))
            # Find out/in pair
            out_adj = next((a for a in adjustments if a.adjustment_type == 'TRANSFER_OUT'), None)
            in_adj = next((a for a in adjustments if a.adjustment_type == 'TRANSFER_IN'), None)
            if out_adj and in_adj:
                qty = abs(out_adj.quantity)
                # basic sanity check: in_adj.quantity should equal qty
                if in_adj.quantity != qty:
                    self.stdout.write(self.style.WARNING(f'Reference {ref} has mismatched quantities (out={out_adj.quantity}, in={in_adj.quantity}) — skipping'))
                    continue

                source_sp = out_adj.stock_product
                dest_sp = in_adj.stock_product

                to_process.append({
                    'reference': ref,
                    'paired': True,
                    'out_adj': out_adj,
                    'in_adj': in_adj,
                    'qty': qty,
                    'source_sp': source_sp,
                    'dest_sp': dest_sp,
                })
            else:
                # unpaired case
                if not options.get('force'):
                    self.stdout.write(self.style.WARNING(f'Reference {ref} does not have both TRANSFER_OUT and TRANSFER_IN — skipping'))
                    continue

                # Best-effort handling when forced
                if out_adj and not in_adj:
                    qty = abs(out_adj.quantity)
                    source_sp = out_adj.stock_product
                    to_process.append({
                        'reference': ref,
                        'paired': False,
                        'side': 'out-only',
                        'out_adj': out_adj,
                        'in_adj': None,
                        'qty': qty,
                        'source_sp': source_sp,
                        'dest_sp': None,
                    })
                elif in_adj and not out_adj:
                    qty = in_adj.quantity
                    dest_sp = in_adj.stock_product
                    to_process.append({
                        'reference': ref,
                        'paired': False,
                        'side': 'in-only',
                        'out_adj': None,
                        'in_adj': in_adj,
                        'qty': qty,
                        'source_sp': None,
                        'dest_sp': dest_sp,
                    })

        if not to_process:
            self.stdout.write(self.style.SUCCESS('No valid paired completed transfers found to process.'))
            return

        # Dry-run: show planned actions
        for item in to_process:
            self.stdout.write('---')
            self.stdout.write(f"Reference: {item['reference']}")
            src = item.get('source_sp')
            dst = item.get('dest_sp')
            if src is None:
                self.stdout.write(f"  Source StockProduct: MISSING")
            else:
                # safe attribute access
                try:
                    self.stdout.write(f"  Source StockProduct: {src.id} (product={src.product_id}) current_quantity={src.quantity}")
                except Exception:
                    self.stdout.write(f"  Source StockProduct: {repr(src)} (could not read fields)")

            if dst is None:
                self.stdout.write(f"  Dest   StockProduct: MISSING")
            else:
                try:
                    self.stdout.write(f"  Dest   StockProduct: {dst.id} (product={dst.product_id}) quantity={dst.quantity}")
                except Exception:
                    self.stdout.write(f"  Dest   StockProduct: {repr(dst)} (could not read fields)")

            self.stdout.write(f"  Transfer quantity: {item['qty']}")
            self.stdout.write(f"  Actions planned: {'restore source quantity, ' if restore_source else ''}delete adjustments, delete destination stockproduct; delete dest stock if it becomes empty")

        if not do_apply:
            self.stdout.write(self.style.SUCCESS(f'DRY-RUN complete. {len(to_process)} transfer(s) would be processed. Rerun with --apply to execute.'))
            return

        # Apply changes
        processed = 0
        for item in to_process:
            ref = item['reference']
            out_adj = item['out_adj']
            in_adj = item['in_adj']
            qty = item['qty']
            source_sp = item['source_sp']
            dest_sp = item['dest_sp']

            try:
                with transaction.atomic():
                    # Refresh conditionally
                    if source_sp is not None:
                        try:
                            source_sp.refresh_from_db()
                        except Exception:
                            # If refresh fails, proceed cautiously
                            pass

                    if dest_sp is not None:
                        try:
                            dest_sp.refresh_from_db()
                        except Exception:
                            pass

                    if restore_source and source_sp is not None:
                        # restore source quantity
                        source_sp.quantity = (source_sp.quantity or 0) + qty
                        source_sp.save(update_fields=['quantity'])

                    # Delete the adjustments if they exist
                    if out_adj is not None:
                        out_adj.delete()
                    if in_adj is not None:
                        in_adj.delete()

                    # Delete destination stockproduct if present
                    dest_stock = None
                    if dest_sp is not None:
                        dest_stock = getattr(dest_sp, 'stock', None)
                        try:
                            dest_sp.delete()
                        except Exception:
                            # swallow individual delete errors and continue
                            pass

                    # If stock exists and has no more items, delete it
                    if dest_stock and dest_stock.items.count() == 0:
                        try:
                            dest_stock.delete()
                        except Exception:
                            pass

                processed += 1
                self.stdout.write(self.style.SUCCESS(f'Processed and removed transfer {ref}'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Failed to process transfer {ref}: {str(e)}'))

        self.stdout.write(self.style.SUCCESS(f'Applied changes: processed {processed} transfers'))
