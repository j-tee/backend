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
    StoreFrontInventory,
    Warehouse,
)
from sales.models import Sale
from django.contrib.auth import get_user_model


User = get_user_model()


class AddSaleItemErrorPayloadTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@example.com",
            password="testpass123",
            name="Business Owner",
        )
        self.business = Business.objects.create(
            owner=self.user,
            name="Stock Limited Business",
            tin="TIN-987654",
            email="limited@example.com",
            address="456 Example Street",
        )
        
        # Create business membership for permission access
        BusinessMembership.objects.create(
            business=self.business,
            user=self.user,
            role=BusinessMembership.OWNER,
            is_admin=True,
            is_active=True
        )
        
        self.storefront = StoreFront.objects.create(
            user=self.user,
            name="City Store",
            location="Accra",
        )
        BusinessStoreFront.objects.create(
            business=self.business,
            storefront=self.storefront,
        )

        self.category = Category.objects.create(name="Networking")
        self.product = Product.objects.create(
            business=self.business,
            name="Wireless Router",
            sku="ROUTER-001",
            category=self.category,
        )

        self.warehouse = Warehouse.objects.create(
            name="Primary Warehouse",
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
            quantity=1,
            unit_cost=Decimal("45.00"),
            retail_price=Decimal("65.00"),
        )

        self.sale = Sale.objects.create(
            business=self.business,
            storefront=self.storefront,
            user=self.user,
            status="DRAFT",
            type="RETAIL",
        )

        self.client.force_authenticate(self.user)

    def test_storefront_inventory_allows_add_when_stock_product_low(self):
        StoreFrontInventory.objects.update_or_create(
            storefront=self.storefront,
            product=self.product,
            defaults={"quantity": 25},
        )

        url = reverse("sale-add-item", kwargs={"pk": self.sale.pk})
        payload = {
            "product": str(self.product.id),
            "stock_product": str(self.stock_product.id),
            "quantity": "6",
            "unit_price": "65.00",
        }

        response = self.client.post(url, payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.sale.refresh_from_db()
        self.assertEqual(self.sale.sale_items.count(), 1)
        sale_item = self.sale.sale_items.first()
        self.assertEqual(sale_item.quantity, Decimal("6"))