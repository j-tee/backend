"""
Management command to fix corrupted storefront inventory caused by transaction rollback bug.

This script recalculates the correct storefront inventory quantities based on
FULFILLED transfer requests only, removing the overcapacity caused by failed
validation attempts that still incremented inventory.

Usage:
    python manage.py fix_storefront_inventory --product-id <uuid>
    python manage.py fix_storefront_inventory --all
    python manage.py fix_storefront_inventory --dry-run
"""

from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.db import transaction
from inventory.models import (
    Product, StoreFrontInventory, TransferRequest, 
    TransferRequestLineItem, StockProduct
)


class Command(BaseCommand):
    help = 'Fix corrupted storefront inventory from transaction rollback bug'

    def add_arguments(self, parser):
        parser.add_argument(
            '--product-id',
            type=str,
            help='UUID of specific product to fix'
        )
        parser.add_argument(
            '--product-name',
            type=str,
            help='Name of product to fix (supports partial match)'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Fix all products with storefront inventory'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without actually changing it'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed information'
        )

    def handle(self, *args, **options):
        product_id = options.get('product_id')
        product_name = options.get('product_name')
        fix_all = options.get('all')
        dry_run = options.get('dry_run')
        verbose = options.get('verbose')

        if dry_run:
            self.stdout.write(self.style.WARNING('*** DRY RUN MODE - No changes will be made ***\n'))

        # Determine which products to fix
        products = []
        if product_id:
            try:
                product = Product.objects.get(id=product_id)
                products = [product]
                self.stdout.write(f'Fixing product by ID: {product.name}\n')
            except Product.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Product with ID {product_id} not found'))
                return
        elif product_name:
            products = list(Product.objects.filter(name__icontains=product_name))
            if not products:
                self.stdout.write(self.style.ERROR(f'No products found matching "{product_name}"'))
                return
            self.stdout.write(f'Found {len(products)} product(s) matching "{product_name}":\n')
            for p in products:
                self.stdout.write(f'  - {p.name} ({p.id})\n')
        elif fix_all:
            # Get all products that have storefront inventory
            products = list(Product.objects.filter(
                storefront_inventory_entries__isnull=False
            ).distinct())
            self.stdout.write(f'Fixing all {len(products)} products with storefront inventory\n')
        else:
            self.stdout.write(self.style.ERROR(
                'Please specify --product-id, --product-name, or --all'
            ))
            return

        # Process each product
        total_fixed = 0
        total_unchanged = 0
        total_errors = 0

        for product in products:
            try:
                result = self.fix_product_inventory(product, dry_run, verbose)
                if result['changed']:
                    total_fixed += 1
                else:
                    total_unchanged += 1
            except Exception as e:
                total_errors += 1
                self.stdout.write(self.style.ERROR(
                    f'Error fixing {product.name}: {str(e)}'
                ))

        # Summary
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS(f'\nSummary:'))
        self.stdout.write(f'  Products fixed: {total_fixed}')
        self.stdout.write(f'  Products unchanged: {total_unchanged}')
        if total_errors:
            self.stdout.write(self.style.ERROR(f'  Errors: {total_errors}'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n*** DRY RUN - No actual changes were made ***'))

    def fix_product_inventory(self, product, dry_run=False, verbose=False):
        """Fix inventory for a single product."""
        
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(f'\nProduct: {product.name} (SKU: {product.sku})')
        self.stdout.write(f'ID: {product.id}\n')

        # Get current storefront inventory
        sf_inventories = StoreFrontInventory.objects.filter(product=product)
        
        if not sf_inventories.exists():
            self.stdout.write(self.style.WARNING('  No storefront inventory records found'))
            return {'changed': False}

        # Get warehouse stock intake
        warehouse_stock = StockProduct.objects.filter(
            product=product
        ).aggregate(total=Sum('quantity'))['total'] or 0

        self.stdout.write(f'\nWarehouse stock intake: {warehouse_stock} units')

        # Calculate expected inventory from FULFILLED transfers
        fulfilled_transfers = TransferRequestLineItem.objects.filter(
            product=product,
            request__status=TransferRequest.STATUS_FULFILLED
        ).aggregate(total=Sum('requested_quantity'))['total'] or 0

        self.stdout.write(f'Fulfilled transfer requests: {fulfilled_transfers} units')

        # Get all transfer request line items for analysis
        all_line_items = TransferRequestLineItem.objects.filter(
            product=product
        ).select_related('request')

        status_breakdown = {}
        for item in all_line_items:
            status = item.request.status
            if status not in status_breakdown:
                status_breakdown[status] = {'count': 0, 'quantity': 0}
            status_breakdown[status]['count'] += 1
            status_breakdown[status]['quantity'] += item.requested_quantity

        if verbose:
            self.stdout.write('\nTransfer request breakdown by status:')
            for status, data in status_breakdown.items():
                self.stdout.write(f'  {status}: {data["count"]} requests, {data["quantity"]} units')

        # Process each storefront
        changed = False
        for sf_inv in sf_inventories:
            current_qty = sf_inv.quantity
            
            # Calculate correct quantity for this storefront
            correct_qty = TransferRequestLineItem.objects.filter(
                product=product,
                request__storefront=sf_inv.storefront,
                request__status=TransferRequest.STATUS_FULFILLED
            ).aggregate(total=Sum('requested_quantity'))['total'] or 0

            self.stdout.write(f'\nStorefront: {sf_inv.storefront.name}')
            self.stdout.write(f'  Current quantity: {current_qty}')
            self.stdout.write(f'  Correct quantity: {correct_qty}')
            
            if current_qty != correct_qty:
                difference = current_qty - correct_qty
                self.stdout.write(self.style.WARNING(
                    f'  Discrepancy: {difference} units (overcapacity)' if difference > 0 
                    else f'  Discrepancy: {abs(difference)} units (undercapacity)'
                ))
                
                if not dry_run:
                    with transaction.atomic():
                        sf_inv.quantity = correct_qty
                        sf_inv.save(update_fields=['quantity', 'updated_at'])
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Fixed: Set to {correct_qty} units'))
                else:
                    self.stdout.write(f'  → Would change to: {correct_qty} units')
                
                changed = True
            else:
                self.stdout.write(self.style.SUCCESS('  ✓ Already correct'))

        # Validation check
        if fulfilled_transfers > warehouse_stock:
            self.stdout.write(self.style.ERROR(
                f'\n⚠ WARNING: Fulfilled transfers ({fulfilled_transfers}) exceed '
                f'warehouse stock ({warehouse_stock})!'
            ))
            self.stdout.write('  This indicates data integrity issues beyond the transaction bug.')

        return {'changed': changed}
