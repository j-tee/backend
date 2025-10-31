from collections import defaultdict
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Sum

from inventory.models import Product, StockProduct
from inventory.stock_adjustments import StockAdjustment
from sales.models import RefundItem, SaleItem


class Command(BaseCommand):
    """Recalculate StockProduct.calculated_quantity from intake, sales, refunds, and adjustments."""

    help = (
        "Rebuild StockProduct.calculated_quantity so it matches intake quantity minus committed sales "
        "plus processed refunds and stock adjustments."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--product",
            dest="product_id",
            help="Limit to a specific product UUID.",
        )
        parser.add_argument(
            "--sku",
            dest="sku",
            help="Limit to a specific product SKU.",
        )
        parser.add_argument(
            "--warehouse",
            dest="warehouse_id",
            help="Limit to a specific warehouse UUID.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show the expected changes without writing to the database.",
        )

    def handle(self, *args, **options):
        product_id = options.get("product_id")
        sku = options.get("sku")
        warehouse_id = options.get("warehouse_id")
        dry_run = options.get("dry_run")

        stock_products = StockProduct.objects.all()

        if sku:
            try:
                product = Product.objects.get(sku=sku)
            except Product.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"No product found with SKU {sku}"))
                return
            stock_products = stock_products.filter(product=product)

        if product_id:
            stock_products = stock_products.filter(product_id=product_id)

        if warehouse_id:
            stock_products = stock_products.filter(warehouse_id=warehouse_id)

        stock_ids = list(stock_products.values_list("id", flat=True))
        if not stock_ids:
            self.stdout.write(self.style.WARNING("No StockProduct rows match the provided filters."))
            return

        # Pre-compute aggregates to avoid per-row queries.
        adjustment_map = defaultdict(int)
        for row in (
            StockAdjustment.objects.filter(stock_product_id__in=stock_ids, status="COMPLETED")
            .values("stock_product")
            .annotate(total=Sum("quantity"))
        ):
            adjustment_map[row["stock_product"]] = int(row["total"] or 0)

        sale_map = defaultdict(int)
        for row in (
            SaleItem.objects.filter(stock_product_id__in=stock_ids, sale__completed_at__isnull=False)
            .values("stock_product")
            .annotate(total=Sum("quantity"))
        ):
            total = row["total"] or Decimal("0")
            sale_map[row["stock_product"]] = int(total)

        refund_map = defaultdict(int)
        for row in (
            RefundItem.objects.filter(
                sale_item__stock_product_id__in=stock_ids,
                refund__status__in=["PROCESSED"],
            )
            .values("sale_item__stock_product")
            .annotate(total=Sum("quantity"))
        ):
            refund_map[row["sale_item__stock_product"]] = int(row["total"] or 0)

        # Group stock products by product for redistribution so totals align even if
        # historical sales referenced a single StockProduct record.
        products_by_id = defaultdict(list)
        for stock_product in (
            StockProduct.objects.filter(id__in=stock_ids)
            .select_related("product", "warehouse", "stock")
            .order_by("product_id", "stock__arrival_date", "created_at")
        ):
            products_by_id[stock_product.product_id].append(stock_product)

        updated = 0
        differences = 0

        for product_id, product_stock in products_by_id.items():
            total_capacity = 0
            total_sales = 0
            total_refunds = 0

            capacity_map = {}
            for sp in product_stock:
                base_intake = int(sp.quantity or 0)
                adj_total = adjustment_map[sp.id]
                capacity = base_intake + adj_total
                if capacity < 0:
                    capacity = 0
                capacity_map[sp.id] = capacity
                total_capacity += capacity
                total_sales += sale_map[sp.id]
                total_refunds += refund_map[sp.id]

            expected_total = total_capacity - total_sales + total_refunds
            if expected_total < 0:
                expected_total = 0
            if expected_total > total_capacity:
                expected_total = total_capacity

            to_reduce = total_capacity - expected_total
            remaining_reduce = to_reduce

            # Reduce oldest stock first (FIFO) so newer stock retains remaining quantity.
            for sp in product_stock:
                capacity = capacity_map[sp.id]
                reduction = min(capacity, remaining_reduce)
                new_calc = capacity - reduction
                remaining_reduce -= reduction

                if new_calc != (sp.calculated_quantity or 0):
                    differences += 1
                    if dry_run:
                        self.stdout.write(
                            f"{sp.product.name} @ {sp.warehouse.name}: "
                            f"current={sp.calculated_quantity}, expected={new_calc}"
                        )
                        continue

                    sp.calculated_quantity = new_calc
                    sp.save(update_fields=["calculated_quantity", "updated_at"])
                    updated += 1

            if remaining_reduce > 0:
                self.stderr.write(
                    self.style.WARNING(
                        f"Product {product_id} still has {remaining_reduce} units unallocated after redistribution."
                    )
                )

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f"Dry run complete. {differences} stock products would change.")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Rebuild complete. Updated {updated} stock products (differences found: {differences})."
                )
            )
