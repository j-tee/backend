from decimal import Decimal

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Business, BusinessMembership
from inventory.models import (
    BusinessStoreFront,
    Category,
    Product,
    Stock,
    StockProduct,
    StoreFront,
    Warehouse,
)
from sales.models import Sale, SaleItem, StockReservation
from django.contrib.auth import get_user_model
from tests.utils import ensure_active_subscription


User = get_user_model()


class SaleAbandonEndpointTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@example.com",
            password="testpass123",
            name="Business Owner",
        )
        self.business = Business.objects.create(
            owner=self.user,
            name="Reservation Business",
            tin="TIN-246810",
            email="reservation@example.com",
            address="123 Reservation Ave",
        )

        # Ensure business membership exists and is active for permission checks
        BusinessMembership.objects.update_or_create(
            business=self.business,
            user=self.user,
            defaults={
                "role": BusinessMembership.OWNER,
                "is_admin": True,
                "is_active": True,
            },
        )
        # Attach primary business attribute expected by subscription permission
        self.user.business = self.business
        ensure_active_subscription(self.business)

        self.storefront = StoreFront.objects.create(
            user=self.user,
            name="Reservation Store",
            location="Accra",
        )
        BusinessStoreFront.objects.create(
            business=self.business,
            storefront=self.storefront,
        )

        self.category = Category.objects.create(name="Networking")
        self.product = Product.objects.create(
            business=self.business,
            name="WiFi Router",
            sku="ROUTER-RESV-001",
            category=self.category,
        )

        self.warehouse = Warehouse.objects.create(
            name="Reservation Warehouse",
            location="Tema",
            manager=self.user,
        )
        stock = Stock.objects.create(
            business=self.business,
            arrival_date=timezone.now().date(),
        )
        self.stock_product = StockProduct.objects.create(
            stock=stock,
            warehouse=self.warehouse,
            product=self.product,
            quantity=10,
            unit_cost=Decimal("45.00"),
            retail_price=Decimal("65.00"),
        )

        self.sale = Sale.objects.create(
            business=self.business,
            storefront=self.storefront,
            user=self.user,
            status="DRAFT",
            type="RETAIL",
            payment_type="CASH",
        )

        SaleItem.objects.create(
            sale=self.sale,
            product=self.product,
            stock_product=self.stock_product,
            quantity=Decimal("3"),
            unit_price=Decimal("65.00"),
        )

        self.reservation = StockReservation.create_reservation(
            stock_product=self.stock_product,
            quantity=Decimal("3"),
            cart_session_id=str(self.sale.id),
            expiry_minutes=30,
        )

        self.client.force_authenticate(self.user)

    def test_abandon_releases_reservations_and_cancels_sale(self):
        url = reverse("sale-abandon", kwargs={"pk": self.sale.pk})

        response = self.client.post(url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        sale = Sale.objects.get(pk=self.sale.pk)
        self.assertEqual(sale.status, "CANCELLED")

        reservation = StockReservation.objects.get(pk=self.reservation.pk)
        self.assertEqual(reservation.status, "RELEASED")
        self.assertIsNotNone(reservation.released_at)

        released_section = response.data["released"]
        self.assertEqual(released_section["count"], 1)
        self.assertEqual(Decimal(released_section["total_quantity"]), Decimal("3"))
        self.assertEqual(len(released_section["reservations"]), 1)

    def test_abandon_on_completed_sale_is_idempotent(self):
        self.sale.status = "COMPLETED"
        self.sale.save(update_fields=["status"])

        url = reverse("sale-abandon", kwargs={"pk": self.sale.pk})
        response = self.client.post(url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["current_status"], "COMPLETED")
        self.assertTrue(response.data["already_finalized"])
        self.assertFalse(response.data["status_changed"])
        released_section = response.data["released"]
        self.assertEqual(released_section["count"], 1)
        self.assertEqual(Decimal(released_section["total_quantity"]), Decimal("3"))
        self.assertEqual(len(released_section["reservations"]), released_section["count"])
        reservation = StockReservation.objects.get(pk=self.reservation.pk)
        self.assertEqual(reservation.status, "RELEASED")

        sale = Sale.objects.get(pk=self.sale.pk)
        self.assertEqual(sale.status, "COMPLETED")
