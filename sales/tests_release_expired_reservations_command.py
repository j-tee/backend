from datetime import timedelta
from decimal import Decimal
from io import StringIO
import re

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from accounts.models import Business
from inventory.models import Category, Product, Stock, StockProduct, Warehouse
from sales.models import StockReservation


User = get_user_model()


class ReleaseExpiredReservationsCommandTest(TestCase):
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")

    def strip_ansi(self, value: str) -> str:
        return self.ansi_escape.sub("", value)

    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@example.com",
            password="testpass123",
            name="Owner"
        )
        self.business = Business.objects.create(
            owner=self.user,
            name="Test Business",
            tin="TIN123456",
            email="business@example.com",
            address="123 Test Street",
            phone_numbers=["+1000000000"],
            social_handles={}
        )
        self.category = Category.objects.create(name="Beverages")
        self.product = Product.objects.create(
            business=self.business,
            name="Mineral Water",
            sku="WATER-001",
            category=self.category
        )
        self.warehouse = Warehouse.objects.create(
            name="Main Warehouse",
            location="Downtown"
        )
        self.stock = Stock.objects.create(business=self.business)
        self.stock_product = StockProduct.objects.create(
            stock=self.stock,
            warehouse=self.warehouse,
            product=self.product,
            quantity=10,
            unit_cost=Decimal("5.00"),
            retail_price=Decimal("7.50")
        )

    def _create_reservation(self, quantity: Decimal, expires_delta: timedelta) -> StockReservation:
        reservation = StockReservation.create_reservation(
            stock_product=self.stock_product,
            quantity=quantity,
            cart_session_id="test-session"
        )
        reservation.expires_at = timezone.now() + expires_delta
        reservation.save(update_fields=["expires_at"])
        return reservation

    def test_command_releases_expired_reservations(self):
        expired = self._create_reservation(Decimal("2"), expires_delta=timedelta(minutes=-5))
        active = self._create_reservation(Decimal("1"), expires_delta=timedelta(minutes=5))

        out = StringIO()
        call_command("release_expired_reservations", stdout=out)
        output = self.strip_ansi(out.getvalue())

        expired.refresh_from_db()
        active.refresh_from_db()

        self.assertEqual(expired.status, "RELEASED")
        self.assertEqual(active.status, "ACTIVE")
        self.assertIn("Released 1 expired reservations.", output)

    def test_dry_run_does_not_release_reservations(self):
        expired = self._create_reservation(Decimal("3"), expires_delta=timedelta(minutes=-10))

        out = StringIO()
        call_command("release_expired_reservations", dry_run=True, stdout=out)
        output = self.strip_ansi(out.getvalue())

        expired.refresh_from_db()
        self.assertEqual(expired.status, "ACTIVE")
        self.assertIn("1 expired reservations would be released (dry-run).", output)
        self.assertIn("Run without --dry-run to release them.", output)
