from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal

from inventory.models import Stock, StockProduct


class Command(BaseCommand):
    help = 'Fix destination StockProduct records created by the auto-transfer flow by copying missing metadata from existing batches'

    def add_arguments(self, parser):
        parser.add_argument(
            '--description',
            default='Auto-created stock batch for transfer',
            help='Stock.description substring to match for auto-created batches (case-insensitive)'
        )
        parser.add_argument('--apply', action='store_true', help='Apply changes. Without this flag the command runs in dry-run mode')

    def handle(self, *args, **options):
        description = options['description']
        do_apply = options['apply']

        # Use case-insensitive containment so we match both original and annotated descriptions
        stocks = Stock.objects.filter(description__icontains=description).order_by('created_at')
        total_stocks = stocks.count()
        if total_stocks == 0:
            self.stdout.write(self.style.SUCCESS('No auto-created stock batches found.'))
            return

        self.stdout.write(f'Found {total_stocks} stock batch(es) with description "{description}"')

        updated = 0
        inspected = 0

        for stock in stocks:
            items = list(stock.items.all())
            if not items:
                self.stdout.write(self.style.WARNING(f'Stock {stock.id} has no StockProduct items, skipping'))
                continue

            for sp in items:
                inspected += 1
                # Only consider records that look incomplete (no retail_price or wholesale_price or unit_tax fields missing)
                needs_fix = False
                missing_fields = []
                # Treat zero or None as missing for prices
                if not sp.retail_price or Decimal(str(sp.retail_price)) == Decimal('0'):
                    needs_fix = True
                    missing_fields.append('retail_price')
                if not sp.wholesale_price or Decimal(str(sp.wholesale_price)) == Decimal('0'):
                    needs_fix = True
                    missing_fields.append('wholesale_price')
                if sp.supplier is None:
                    needs_fix = True
                    missing_fields.append('supplier')

                if not needs_fix:
                    self.stdout.write(self.style.NOTICE(f'StockProduct {sp.id} looks complete — skipping'))
                    continue

                # Find candidate source stock product for the same product with non-zero quantity
                candidate = (
                    StockProduct.objects.filter(product=sp.product)
                    .exclude(id=sp.id)
                    .filter(quantity__gt=0)
                    .order_by('-quantity', '-created_at')
                    .first()
                )
                if not candidate:
                    # fallback to any other batch for the product
                    candidate = (
                        StockProduct.objects.filter(product=sp.product)
                        .exclude(id=sp.id)
                        .order_by('-created_at')
                        .first()
                    )

                if not candidate:
                    self.stdout.write(self.style.WARNING(f'No candidate source found to copy metadata for StockProduct {sp.id} (product {sp.product_id}).'))
                    continue

                self.stdout.write(f'Preparing to fix StockProduct {sp.id} (product {sp.product_id}) — missing: {missing_fields}. Candidate: {candidate.id}')

                if do_apply:
                    with transaction.atomic():
                        changed = False
                        stock_changed = False
                        # Copy a safe set of metadata if missing
                        if (not sp.retail_price or Decimal(str(sp.retail_price)) == Decimal('0')) and candidate.retail_price:
                            sp.retail_price = candidate.retail_price
                            changed = True
                        if (not sp.wholesale_price or Decimal(str(sp.wholesale_price)) == Decimal('0')) and candidate.wholesale_price:
                            sp.wholesale_price = candidate.wholesale_price
                            changed = True
                        if sp.supplier is None and candidate.supplier is not None:
                            sp.supplier = candidate.supplier
                            changed = True
                        if not sp.unit_tax_rate and candidate.unit_tax_rate:
                            sp.unit_tax_rate = candidate.unit_tax_rate
                            changed = True
                        if not sp.unit_tax_amount and candidate.unit_tax_amount:
                            sp.unit_tax_amount = candidate.unit_tax_amount
                            changed = True
                        if not sp.unit_additional_cost and candidate.unit_additional_cost:
                            sp.unit_additional_cost = candidate.unit_additional_cost
                            changed = True
                        if not sp.description and candidate.description:
                            sp.description = candidate.description
                            changed = True

                        # Save StockProduct if any changes
                        if changed:
                            sp.save()

                        # Now consider copying safe Stock-level fields from the candidate's associated Stock
                        candidate_stock = getattr(candidate, 'stock', None)
                        if candidate_stock:
                            try:
                                # arrival_date: only copy if destination stock arrival_date is missing
                                if (not getattr(stock, 'arrival_date', None)) and getattr(candidate_stock, 'arrival_date', None):
                                    stock.arrival_date = candidate_stock.arrival_date
                                    stock_changed = True

                                # stock.description: copy only if the current description is empty or appears to be the auto-created marker
                                current_desc = (stock.description or '').strip()
                                auto_marker = 'auto-created stock batch for transfer'
                                if ((not current_desc) or auto_marker in current_desc.lower()) and (candidate_stock.description):
                                    # set the candidate's description but keep an audit marker
                                    stock.description = candidate_stock.description + ' [fixed-transfer-metadata]'
                                    stock_changed = True

                                if stock_changed:
                                    stock.save(update_fields=[f for f in ['arrival_date', 'description'] if getattr(stock, f) is not None])
                            except Exception:
                                # never crash the whole job for a single stock copy failure
                                self.stdout.write(self.style.WARNING(f'Failed to copy stock-level fields for stock {stock.id}'))

                        if changed or stock_changed:
                            updated += 1
                            self.stdout.write(self.style.SUCCESS(f'Updated StockProduct {sp.id}'))
                        else:
                            self.stdout.write(self.style.NOTICE(f'No updatable fields for StockProduct {sp.id}'))
                else:
                    # Dry-run output — include proposed stock-level copies when applicable
                    # Determine proposed stock-level changes
                    stock_proposals = []
                    candidate_stock = getattr(candidate, 'stock', None)
                    if candidate_stock:
                        if (not getattr(stock, 'arrival_date', None)) and getattr(candidate_stock, 'arrival_date', None):
                            stock_proposals.append('arrival_date')
                        current_desc = (stock.description or '').strip()
                        auto_marker = 'auto-created stock batch for transfer'
                        if ((not current_desc) or auto_marker in current_desc.lower()) and (candidate_stock.description):
                            stock_proposals.append('stock.description')

                    self.stdout.write(f'Would copy from candidate {candidate.id} to {sp.id}: fields={missing_fields} stock_fields={stock_proposals}')

        self.stdout.write(self.style.SUCCESS(f'Inspected {inspected} StockProduct(s); updated {updated}'))