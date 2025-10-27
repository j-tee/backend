"""
Management command to backfill missing reference_number for legacy 
TRANSFER_IN/TRANSFER_OUT StockAdjustment records.

This command should be run BEFORE Phase 4 deployment to ensure all legacy
transfers have reference numbers for proper tracking in MovementTracker.

Usage:
    python manage.py backfill_transfer_references
    python manage.py backfill_transfer_references --dry-run
    python manage.py backfill_transfer_references --business-id <uuid>
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from inventory.stock_adjustments import StockAdjustment
from collections import defaultdict


class Command(BaseCommand):
    help = 'Backfill missing reference_number for TRANSFER_IN/OUT adjustments'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--business-id',
            type=str,
            help='Only backfill for specific business (UUID)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        business_id = options.get('business_id')

        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('Backfill Transfer Reference Numbers'))
        self.stdout.write(self.style.SUCCESS('=' * 70))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 DRY RUN MODE - No changes will be saved'))
        
        # Build query
        filters = {
            'adjustment_type__in': ['TRANSFER_IN', 'TRANSFER_OUT'],
            'reference_number__isnull': True
        }
        
        if business_id:
            filters['business_id'] = business_id
            self.stdout.write(f'📍 Filtering by business: {business_id}')
        
        # Get adjustments needing backfill
        adjustments = StockAdjustment.objects.filter(**filters).select_related(
            'stock_product',
            'business'
        ).order_by('created_at')
        
        total_count = adjustments.count()
        
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS('✅ No adjustments need backfilling!'))
            return
        
        self.stdout.write(f'📊 Found {total_count} adjustments needing reference numbers')
        self.stdout.write('')
        
        # Group adjustments by potential pairs (same created_at, product, opposite types)
        paired_count = 0
        unpaired_count = 0
        error_count = 0
        
        # Track paired adjustments
        paired_refs = set()
        
        # First pass: Find paired transfers (TRANSFER_OUT + TRANSFER_IN at same time)
        self.stdout.write('🔗 Phase 1: Identifying paired transfers...')
        
        # Group by timestamp (to second) and product
        potential_pairs = defaultdict(list)
        for adj in adjustments:
            # Create key: timestamp to second + product + business
            key = (
                adj.created_at.replace(microsecond=0),
                adj.stock_product.product_id if adj.stock_product else None,
                adj.business_id
            )
            potential_pairs[key].append(adj)
        
        # Process pairs
        updates = []
        for key, adjs in potential_pairs.items():
            timestamp, product_id, business_id = key
            
            # Check if we have both TRANSFER_OUT and TRANSFER_IN
            outs = [a for a in adjs if a.adjustment_type == 'TRANSFER_OUT']
            ins = [a for a in adjs if a.adjustment_type == 'TRANSFER_IN']
            
            if outs and ins:
                # Found a pair! Generate shared reference
                reference = f"TRF-LEGACY-{timestamp.strftime('%Y%m%d%H%M%S')}"
                
                # Ensure uniqueness
                counter = 1
                base_ref = reference
                while reference in paired_refs or StockAdjustment.objects.filter(reference_number=reference).exists():
                    reference = f"{base_ref}-{counter}"
                    counter += 1
                
                paired_refs.add(reference)
                
                for adj in adjs:
                    updates.append((adj, reference, 'paired'))
                    paired_count += 1
        
        self.stdout.write(f'   ✓ Found {paired_count} paired transfers')
        self.stdout.write('')
        
        # Second pass: Handle unpaired transfers
        self.stdout.write('📝 Phase 2: Generating references for unpaired transfers...')
        
        for adj in adjustments:
            # Skip if already processed in pairing phase
            if any(update[0].id == adj.id for update in updates):
                continue
            
            # Generate unique reference with ID to ensure uniqueness
            timestamp = adj.created_at.strftime('%Y%m%d%H%M%S')
            adj_id_short = str(adj.id)[:8]
            reference = f"TRF-LEGACY-{timestamp}-{adj_id_short}"
            
            # Ensure uniqueness (should be guaranteed by ID, but double-check)
            counter = 1
            base_ref = reference
            while (reference in paired_refs or 
                   StockAdjustment.objects.filter(reference_number=reference).exists() or
                   any(u[1] == reference for u in updates)):
                reference = f"{base_ref}-{counter}"
                counter += 1
            
            updates.append((adj, reference, 'unpaired'))
            unpaired_count += 1
        
        self.stdout.write(f'   ✓ Generated {unpaired_count} unique references')
        self.stdout.write('')
        
        # Summary before update
        self.stdout.write(self.style.SUCCESS('📋 Summary:'))
        self.stdout.write(f'   • Paired transfers: {paired_count}')
        self.stdout.write(f'   • Unpaired transfers: {unpaired_count}')
        self.stdout.write(f'   • Total to update: {len(updates)}')
        self.stdout.write('')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 DRY RUN - Sample updates (first 10):'))
            for adj, ref, pair_type in updates[:10]:
                business_name = adj.business.name if adj.business else 'N/A'
                product_name = adj.stock_product.product.name if adj.stock_product else 'N/A'
                self.stdout.write(
                    f'   • {adj.adjustment_type:12} | {ref:35} | '
                    f'{pair_type:8} | {product_name[:30]:30} | {business_name[:20]}'
                )
            
            if len(updates) > 10:
                self.stdout.write(f'   ... and {len(updates) - 10} more')
            
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('ℹ️  Run without --dry-run to apply changes'))
            return
        
        # Apply updates in transaction
        self.stdout.write('💾 Phase 3: Applying updates...')
        
        try:
            with transaction.atomic():
                for adj, reference, pair_type in updates:
                    try:
                        adj.reference_number = reference
                        adj.save(update_fields=['reference_number'])
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f'   ✗ Error updating {adj.id}: {str(e)}')
                        )
                        error_count += 1
                        raise  # Rollback entire transaction on any error
                
                success_count = len(updates) - error_count
                
                self.stdout.write('')
                self.stdout.write(self.style.SUCCESS('✅ Backfill Complete!'))
                self.stdout.write('')
                self.stdout.write(f'   • Successfully updated: {success_count}')
                
                if error_count > 0:
                    self.stdout.write(self.style.ERROR(f'   • Errors: {error_count}'))
                    self.stdout.write(self.style.ERROR('   • Transaction rolled back - no changes saved'))
                else:
                    self.stdout.write(self.style.SUCCESS('   • All updates applied successfully'))
                
        except Exception as e:
            self.stdout.write('')
            self.stdout.write(self.style.ERROR('❌ Backfill Failed!'))
            self.stdout.write(self.style.ERROR(f'   Error: {str(e)}'))
            self.stdout.write(self.style.ERROR('   All changes have been rolled back'))
            raise
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 70))
