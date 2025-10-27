import uuid
from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from inventory.models import StockProduct
from inventory.stock_adjustments import StockAdjustment


class Command(BaseCommand):
    help = (
        "Reapply stock adjustments that were marked as completed without invoking the "
        "model's completion workflow. By default, the command runs in dry-run mode and "
        "prints the actions it would take. Use --apply to persist the changes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--stock-product",
            dest="stock_product",
            help="Limit the replay to a specific stock product UUID.",
        )
        parser.add_argument(
            "--adjustment",
            dest="adjustment",
            help="Limit the replay to a specific stock adjustment UUID.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            dest="apply",
            help="Persist the stock quantity updates. Without this flag a dry-run is performed.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            dest="force",
            help=(
                "Apply adjustments even when the safety heuristics cannot confirm they were skipped. "
                "Use with caution."
            ),
        )

    def handle(self, *args, **options):
        apply_changes = options.get("apply", False)
        force = options.get("force", False)
        stock_product_filter = options.get("stock_product")
        adjustment_filter = options.get("adjustment")

        queryset = StockAdjustment.objects.filter(
            status="COMPLETED",
            completed_at__isnull=False,
            stock_product__isnull=False,
        )

        if stock_product_filter:
            try:
                uuid.UUID(str(stock_product_filter))
            except ValueError as exc:  # pragma: no cover - defensive guard
                raise CommandError("--stock-product must be a valid UUID") from exc
            queryset = queryset.filter(stock_product_id=stock_product_filter)

        if adjustment_filter:
            try:
                uuid.UUID(str(adjustment_filter))
            except ValueError as exc:  # pragma: no cover - defensive guard
                raise CommandError("--adjustment must be a valid UUID") from exc
            queryset = queryset.filter(id=adjustment_filter)

        adjustments = list(
            queryset.select_related(
                "stock_product",
                "stock_product__product",
                "stock_product__warehouse",
                "stock_product__stock",
            ).order_by("stock_product_id", "completed_at", "created_at")
        )

        if not adjustments:
            self.stdout.write("No completed stock adjustments matched the provided filters.")
            return

        grouped = defaultdict(list)
        for adjustment in adjustments:
            grouped[adjustment.stock_product_id].append(adjustment)

        applied_products = 0
        total_adjustments = 0

        for stock_product_id, product_adjustments in grouped.items():
            stock_product = product_adjustments[0].stock_product
            if stock_product is None:
                self.stdout.write(self.style.WARNING(
                    f"Skipping adjustments linked to missing stock product {stock_product_id}."
                ))
                continue

            product_adjustments = self._sort_adjustments(product_adjustments)
            batches, leftovers = self._build_batches(product_adjustments, stock_product.quantity)

            if not batches and not force:
                self.stdout.write(
                    self.style.WARNING(
                        f"No unapplied adjustments detected for stock product {stock_product.id} "
                        f"({stock_product.product.name})."
                    )
                )
                continue

            if leftovers and not force:
                self.stdout.write(
                    self.style.WARNING(
                        f"Partial replay for stock product {stock_product.id} was skipped because "
                        f"{len(leftovers)} adjustments could not be matched to the current quantity. "
                        f"Re-run with --force to override."
                    )
                )
                continue

            if leftovers and force:
                forced_batches = self._build_forced_batches(leftovers, batches, stock_product.quantity)
                batches.extend(forced_batches)

            total_delta = sum(batch["delta"] for batch in batches)
            if total_delta == 0:
                self.stdout.write(
                    self.style.WARNING(
                        f"Stock product {stock_product.id} ({stock_product.product.name}) already reflects the "
                        "combined adjustments."
                    )
                )
                continue

            projected_quantity = stock_product.quantity + total_delta
            if projected_quantity < 0:
                raise CommandError(
                    f"Applying adjustments would make stock product {stock_product.id} negative "
                    f"({projected_quantity}). Aborting."
                )

            summary_prefix = (
                f"Stock product {stock_product.id} ({stock_product.product.name}) in "
                f"{stock_product.warehouse.name if stock_product.warehouse else 'warehouse unknown'}"
            )
            batch_count = sum(len(batch["adjustments"]) for batch in batches)

            if apply_changes:
                with transaction.atomic():
                    for batch in batches:
                        self._apply_batch(batch)
                stock_product.refresh_from_db()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"{summary_prefix}: quantity updated from {projected_quantity - total_delta} "
                        f"to {projected_quantity} using {batch_count} adjustment(s)."
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"[DRY-RUN] {summary_prefix}: would update quantity from "
                        f"{stock_product.quantity} to {projected_quantity} using {batch_count} adjustment(s)."
                    )
                )

            applied_products += 1
            total_adjustments += batch_count

        if applied_products == 0:
            self.stdout.write("No stock quantities required reconciliation.")
            return

        summary = (
            f"Processed {applied_products} stock product(s); "
            f"{total_adjustments} adjustment(s) {'applied' if apply_changes else 'inspected'}"
        )
        if apply_changes:
            self.stdout.write(self.style.SUCCESS(summary))
        else:
            self.stdout.write(self.style.WARNING(summary))

    def _sort_adjustments(self, adjustments):
        def sort_key(adjustment):
            return (
                adjustment.completed_at or adjustment.approved_at or adjustment.created_at or timezone.now(),
                adjustment.id,
            )

        return sorted(adjustments, key=sort_key)

    def _build_batches(self, adjustments, starting_quantity):
        remaining = list(adjustments)
        batches = []
        current_quantity = starting_quantity

        while remaining:
            matching = [adj for adj in remaining if adj.quantity_before == current_quantity]
            if not matching:
                break

            matching = self._sort_adjustments(matching)
            delta = sum(adj.quantity for adj in matching)
            batches.append(
                {
                    "before": current_quantity,
                    "delta": delta,
                    "adjustments": matching,
                    "forced": False,
                }
            )
            current_quantity += delta
            remaining = [adj for adj in remaining if adj not in matching]

        leftovers = self._sort_adjustments(remaining) if remaining else []
        return batches, leftovers

    def _build_forced_batches(self, leftovers, existing_batches, starting_quantity):
        batches = []
        if existing_batches:
            working_quantity = existing_batches[-1]["before"] + existing_batches[-1]["delta"]
        else:
            working_quantity = starting_quantity

        for adjustment in leftovers:
            batches.append(
                {
                    "before": working_quantity,
                    "delta": adjustment.quantity,
                    "adjustments": [adjustment],
                    "forced": True,
                }
            )
            working_quantity += adjustment.quantity
        return batches

    def _apply_batch(self, batch):
        adjustments = batch["adjustments"]
        if not adjustments:
            return 0

        stock_product = adjustments[0].stock_product
        locked_product = StockProduct.objects.select_for_update().get(pk=stock_product.pk)

        delta = sum(adj.quantity for adj in adjustments)
        new_quantity = locked_product.quantity + delta
        if new_quantity < 0:
            raise CommandError(
                f"Applying adjustments would make stock product {locked_product.id} negative "
                f"({new_quantity})."
            )

        locked_product.quantity = new_quantity
        locked_product.save(update_fields=["quantity", "updated_at"])

        to_update = [adj for adj in adjustments if adj.status != "COMPLETED"]
        if to_update:
            StockAdjustment.objects.filter(pk__in=[adj.pk for adj in to_update]).update(status="COMPLETED")

        return delta
