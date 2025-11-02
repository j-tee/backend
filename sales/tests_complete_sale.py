from decimal import Decimal

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Business, BusinessMembership
from inventory.models import (
    Category,
    Product,
    StoreFront,
    BusinessStoreFront,
    Warehouse,
    Stock,
    StockProduct,
    StoreFrontInventory,
)
from sales.models import Sale, SaleItem, Customer, StockReservation
from tests.utils import ensure_active_subscription


User = get_user_model()


class CompleteSaleEndpointTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="cashier@example.com",
            password="TestPass123",
            name="Cashier"
        )
        self.business = Business.objects.create(
            owner=self.user,
            name="Test Biz",
            tin="TIN1234567",
            email="biz@example.com",
            address="123 Test Lane"
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
        self.user.business = self.business
        ensure_active_subscription(self.business)

        self.category = Category.objects.create(name="Beverages")
        self.customer = Customer.objects.create(
            business=self.business,
            name="Walk-in Customer",
            created_by=self.user
        )
        self.product = Product.objects.create(
            business=self.business,
            name="Water Bottle",
            sku="WATER-001",
            category=self.category
        )
        self.warehouse = Warehouse.objects.create(
            name="Main Warehouse",
            location="Warehouse District",
            manager=self.user
        )
        self.stock = Stock.objects.create(
            business=self.business,
            description="Initial stock"
        )
        self.stock_product = StockProduct.objects.create(
            stock=self.stock,
            warehouse=self.warehouse,
            product=self.product,
            quantity=50,
            unit_cost=Decimal("5.00"),
            retail_price=Decimal("10.00")
        )
        self.storefront = StoreFront.objects.create(
            user=self.user,
            name="Main Storefront",
            location="Downtown"
        )
        BusinessStoreFront.objects.create(business=self.business, storefront=self.storefront)
        StoreFrontInventory.objects.create(
            storefront=self.storefront,
            product=self.product,
            quantity=50,
        )

        self.sale = Sale.objects.create(
            business=self.business,
            storefront=self.storefront,
            user=self.user,
            customer=self.customer,
            status="DRAFT",
            payment_type="CASH",
            cart_session_id="session-123"
        )
        SaleItem.objects.create(
            sale=self.sale,
            product=self.product,
            stock=self.stock,
            stock_product=self.stock_product,
            quantity=Decimal("2"),
            unit_price=Decimal("10.00")
        )
        self.sale.calculate_totals()
        self.sale.save()

        self.client.force_authenticate(user=self.user)

    def test_complete_sale_marks_sale_completed_and_records_payment(self):
        url = reverse("sale-complete", kwargs={"pk": self.sale.id})
        payload = {
            "payment_type": "CASH",
            "payments": [
                {
                    "sale": str(self.sale.id),
                    "customer": str(self.customer.id),
                    "payment_method": "CASH",
                    "amount_paid": "20.00"
                }
            ]
        }

        StockReservation.create_reservation(
            stock_product=self.stock_product,
            quantity=Decimal("2"),
            cart_session_id=str(self.sale.id)
        )

        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.sale.refresh_from_db()
        self.assertEqual(self.sale.status, "COMPLETED")
        self.assertEqual(self.sale.amount_due, Decimal("0.00"))
        self.assertEqual(self.sale.amount_paid, Decimal("20.00"))
        self.assertIsNotNone(self.sale.completed_at)
        self.assertEqual(self.sale.payments.count(), 1)
        self.assertIsNone(self.sale.cart_session_id)
        self.assertFalse(
            StockReservation.objects.filter(cart_session_id=str(self.sale.id)).exists()
        )

        storefront_inventory = StoreFrontInventory.objects.get(
            storefront=self.storefront,
            product=self.product,
        )
        self.assertEqual(storefront_inventory.quantity, 48)