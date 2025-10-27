from django.core.management.base import BaseCommand
from django.utils import timezone

from sales.models import StockReservation


class Command(BaseCommand):
    """Release all expired stock reservations."""

    help = (
        "Release ACTIVE stock reservations whose expiry timestamp has passed. "
        "Run this command from cron or a scheduled job if Celery beat is not available."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only report how many reservations would be released without updating anything.",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Print the reservations that are being released.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        verbose: bool = options["verbose"]

        expired_qs = (
            StockReservation.objects.filter(status="ACTIVE", expires_at__lt=timezone.now())
            .select_related("stock_product__product")
            .order_by("expires_at")
        )
        expired = list(expired_qs)
        count = len(expired)

        if count == 0:
            self.stdout.write(self.style.SUCCESS("No expired reservations found."))
            return

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"{count} expired reservations would be released (dry-run).")
            )
        else:
            released = StockReservation.release_expired()
            self.stdout.write(self.style.SUCCESS(f"Released {released} expired reservations."))

        if verbose:
            for reservation in expired:
                product_name = (
                    reservation.stock_product.product.name
                    if reservation.stock_product and reservation.stock_product.product
                    else "<unknown>"
                )
                self.stdout.write(
                    f"- Reservation {reservation.id} | product={product_name} | "
                    f"quantity={reservation.quantity} | expires_at={reservation.expires_at.isoformat()}"
                )

        if dry_run:
            self.stdout.write("Run without --dry-run to release them.")