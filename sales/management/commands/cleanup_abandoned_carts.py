"""
Management command to clean up abandoned DRAFT sales (carts)

Usage:
    python manage.py cleanup_abandoned_carts
    python manage.py cleanup_abandoned_carts --age-hours=2 --dry-run
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from sales.models import Sale, StockReservation


class Command(BaseCommand):
    help = 'Clean up abandoned DRAFT sales and release their stock reservations'

    def add_arguments(self, parser):
        parser.add_argument(
            '--age-hours',
            type=int,
            default=24,
            help='Minimum age in hours for a DRAFT sale to be considered abandoned (default: 24)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )

    def handle(self, *args, **options):
        age_hours = options['age_hours']
        dry_run = options['dry_run']
        
        cutoff_time = timezone.now() - timedelta(hours=age_hours)
        
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("ABANDONED CART CLEANUP"))
        self.stdout.write("=" * 80)
        self.stdout.write(f"\nLooking for DRAFT sales older than {age_hours} hours...")
        self.stdout.write(f"Cutoff time: {cutoff_time}")
        
        if dry_run:
            self.stdout.write(self.style.WARNING("\n⚠️  DRY RUN MODE - No changes will be made\n"))
        
        # Find abandoned DRAFT sales
        abandoned_sales = Sale.objects.filter(
            status='DRAFT',
            updated_at__lt=cutoff_time
        ).select_related('storefront', 'customer')
        
        total_count = abandoned_sales.count()
        
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS("\n✅ No abandoned carts found!"))
            return
        
        self.stdout.write(f"\nFound {total_count} abandoned carts:\n")
        self.stdout.write("-" * 80)
        
        total_reserved = 0
        total_value = 0
        
        for sale in abandoned_sales:
            # Get reservations
            reservations = StockReservation.objects.filter(
                cart_session_id=str(sale.id),
                status='ACTIVE'
            )
            
            reserved_count = reservations.count()
            reserved_qty = sum(r.quantity for r in reservations)
            
            total_reserved += reserved_qty
            total_value += float(sale.total_amount)
            
            self.stdout.write(f"\nSale ID: {sale.id}")
            self.stdout.write(f"  Storefront: {sale.storefront.name if sale.storefront else 'N/A'}")
            self.stdout.write(f"  Customer: {sale.customer.name if sale.customer else 'Walk-in'}")
            self.stdout.write(f"  Created: {sale.created_at}")
            self.stdout.write(f"  Last Updated: {sale.updated_at}")
            self.stdout.write(f"  Age: {(timezone.now() - sale.updated_at).total_seconds() / 3600:.1f} hours")
            self.stdout.write(f"  Items: {sale.sale_items.count()}")
            self.stdout.write(f"  Total Amount: ${sale.total_amount}")
            self.stdout.write(f"  Active Reservations: {reserved_count} ({reserved_qty} units)")
            
            # Show items
            for item in sale.sale_items.all():
                self.stdout.write(f"    - {item.product.name} x {item.quantity}")
        
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(f"SUMMARY:")
        self.stdout.write(f"  Total Abandoned Carts: {total_count}")
        self.stdout.write(f"  Total Reserved Units: {total_reserved}")
        self.stdout.write(f"  Total Cart Value: ${total_value:.2f}")
        self.stdout.write("=" * 80)
        
        if not dry_run:
            self.stdout.write(self.style.WARNING("\n⚠️  Proceeding with cleanup..."))
            
            deleted_sales = 0
            released_reservations = 0
            
            with transaction.atomic():
                for sale in abandoned_sales:
                    # Release reservations
                    reservations = StockReservation.objects.filter(
                        cart_session_id=str(sale.id),
                        status='ACTIVE'
                    )
                    
                    count = reservations.count()
                    reservations.update(status='EXPIRED')
                    released_reservations += count
                    
                    # Delete the sale
                    sale.delete()
                    deleted_sales += 1
            
            self.stdout.write(self.style.SUCCESS(f"\n✅ Cleanup complete!"))
            self.stdout.write(f"  Deleted {deleted_sales} abandoned carts")
            self.stdout.write(f"  Released {released_reservations} stock reservations")
            self.stdout.write(f"  Freed up {total_reserved} units for sale\n")
        else:
            self.stdout.write(self.style.WARNING(f"\n📋 Dry run complete - no changes made"))
            self.stdout.write(f"   Run without --dry-run to actually clean up these carts\n")
