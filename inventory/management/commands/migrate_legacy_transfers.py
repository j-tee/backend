"""
Django management command to migrate legacy TRANSFER_IN/TRANSFER_OUT 
StockAdjustment records to the new Transfer model.

This is a one-time migration to consolidate the dual transfer systems.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from inventory.stock_adjustments import StockAdjustment
from inventory.transfer_models import Transfer, TransferItem
from accounts.models import User
from decimal import Decimal
import uuid


class Command(BaseCommand):
    help = 'Migrate legacy TRANSFER_IN/TRANSFER_OUT adjustments to Transfer model'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without making changes',
        )
        parser.add_argument(
            '--delete-legacy',
            action='store_true',
            help='Delete legacy records after successful migration (only with --apply)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        delete_legacy = options['delete_legacy']

        # Find all legacy transfer records
        legacy_transfers = StockAdjustment.objects.filter(
            adjustment_type__in=['TRANSFER_IN', 'TRANSFER_OUT']
        ).select_related('stock_product__warehouse', 'stock_product__product', 'created_by')

        total_count = legacy_transfers.count()
        
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS('No legacy transfers found - migration already complete!'))
            return

        self.stdout.write(f'Found {total_count} legacy transfer records')

        # Group by reference_number to process pairs
        by_reference = {}
        for adj in legacy_transfers:
            ref = adj.reference_number or str(adj.id)
            if ref not in by_reference:
                by_reference[ref] = []
            by_reference[ref].append(adj)

        self.stdout.write(f'Grouped into {len(by_reference)} transfer pairs/singles')

        if dry_run:
            self.stdout.write(self.style.WARNING('\n=== DRY RUN MODE - NO CHANGES WILL BE MADE ===\n'))

        migrated_count = 0
        skipped_count = 0
        errors = []

        for ref, adjustments in by_reference.items():
            # Find TRANSFER_OUT and TRANSFER_IN
            out_adj = next((a for a in adjustments if a.adjustment_type == 'TRANSFER_OUT'), None)
            in_adj = next((a for a in adjustments if a.adjustment_type == 'TRANSFER_IN'), None)

            if not out_adj or not in_adj:
                msg = f'Reference {ref}: Missing paired transfer (found {[a.adjustment_type for a in adjustments]})'
                self.stdout.write(self.style.WARNING(msg))
                errors.append(msg)
                skipped_count += len(adjustments)
                continue

            # Extract transfer details
            from_warehouse = out_adj.stock_product.warehouse
            to_warehouse = in_adj.stock_product.warehouse
            product = out_adj.stock_product.product
            business = out_adj.business
            quantity = abs(int(out_adj.quantity))  # OUT is negative, make positive
            unit_cost = out_adj.unit_cost
            created_by = out_adj.created_by
            created_at = out_adj.created_at
            completed_at = out_adj.completed_at
            status = out_adj.status  # Should be 'COMPLETED'
            
            # Determine transfer type
            transfer_type = 'W2W'  # Warehouse to Warehouse
            destination_storefront = None

            self.stdout.write(f'\nProcessing transfer: {ref}')
            self.stdout.write(f'  FROM: {from_warehouse.name} -> TO: {to_warehouse.name}')
            self.stdout.write(f'  Product: {product.name}')
            self.stdout.write(f'  Quantity: {quantity}')
            self.stdout.write(f'  Status: {status}')
            self.stdout.write(f'  Created: {created_at}')

            if not dry_run:
                try:
                    with transaction.atomic():
                        # Create Transfer record
                        transfer = Transfer.objects.create(
                            business=business,
                            transfer_type=transfer_type,
                            source_warehouse=from_warehouse,
                            destination_warehouse=to_warehouse,
                            destination_storefront=destination_storefront,
                            status=status.lower() if status else 'completed',  # Convert COMPLETED to completed
                            created_by=created_by,
                            notes=f'Migrated from legacy transfer {ref}. Original reason: {out_adj.reason}',
                            # Preserve original timestamps
                            created_at=created_at,
                        )

                        # Note: reference_number is auto-generated, but we store legacy ref in notes
                        # The legacy reference {ref} is already in the notes field above

                        # Set completed_at if the legacy transfer was completed
                        if completed_at:
                            transfer.completed_at = completed_at
                            transfer.save(update_fields=['completed_at'])

                        # Create TransferItem
                        TransferItem.objects.create(
                            transfer=transfer,
                            product=product,
                            quantity=quantity,
                            unit_cost=unit_cost,
                        )

                        self.stdout.write(self.style.SUCCESS(f'  ✓ Created Transfer {transfer.id}'))
                        migrated_count += 2  # Count both IN and OUT adjustments

                        # Optionally delete legacy records
                        if delete_legacy:
                            out_adj.delete()
                            in_adj.delete()
                            self.stdout.write(self.style.SUCCESS(f'  ✓ Deleted legacy adjustments'))

                except Exception as e:
                    error_msg = f'Failed to migrate {ref}: {str(e)}'
                    self.stdout.write(self.style.ERROR(f'  ✗ {error_msg}'))
                    errors.append(error_msg)
            else:
                self.stdout.write(self.style.SUCCESS('  [DRY RUN] Would create Transfer record'))
                migrated_count += 2

        # Summary
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS(f'Migration Summary:'))
        self.stdout.write(f'  Total legacy records: {total_count}')
        self.stdout.write(f'  Successfully migrated: {migrated_count}')
        self.stdout.write(f'  Skipped: {skipped_count}')
        self.stdout.write(f'  Errors: {len(errors)}')

        if errors:
            self.stdout.write(self.style.ERROR('\nErrors encountered:'))
            for error in errors:
                self.stdout.write(f'  - {error}')

        if dry_run:
            self.stdout.write(self.style.WARNING('\n!!! THIS WAS A DRY RUN - NO CHANGES WERE MADE !!!'))
            self.stdout.write('Run without --dry-run to apply changes')
        else:
            self.stdout.write(self.style.SUCCESS('\n✓ Migration completed!'))
            if not delete_legacy:
                self.stdout.write(self.style.WARNING('\nNote: Legacy records were NOT deleted (use --delete-legacy to remove them)'))
