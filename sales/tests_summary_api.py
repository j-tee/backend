from decimal import Decimal

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.models import Business
from inventory.models import (
    BusinessStoreFront,
    Category,
    Product,
    Stock,
    StockProduct,
    StoreFront,
    Warehouse,
)
from sales.models import Customer, Sale, SaleItem
from django.contrib.auth import get_user_model


User = get_user_model()


class SalesSummaryAPITestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@example.com",
            password="testpass123",
            name="Business Owner",
        )
        self.business = Business.objects.create(
            owner=self.user,
            name="Test Business",
            tin="TIN-123456",
            email="biz@example.com",
            address="123 Test Street",
        )
        self.storefront = StoreFront.objects.create(
            user=self.user,
            name="Main Store",
            location="Accra",
        )
        BusinessStoreFront.objects.create(
            business=self.business,
            storefront=self.storefront,
        )

        self.category = Category.objects.create(name="Electronics")
        self.product_cash = Product.objects.create(
            business=self.business,
            name="POS Terminal",
            sku="POS-001",
            category=self.category,
        )
        self.product_credit = Product.objects.create(
            business=self.business,
            name="Barcode Scanner",
            sku="POS-002",
            category=self.category,
        )

        self.warehouse = Warehouse.objects.create(
            name="Central Warehouse",
            location="Tema",
            manager=self.user,
        )
        self.stock_cash = Stock.objects.create(
            business=self.business,
            arrival_date=timezone.now().date(),
        )
        self.stock_credit = Stock.objects.create(
            business=self.business,
            arrival_date=timezone.now().date(),
        )
        self.stock_product_cash = StockProduct.objects.create(
            stock=self.stock_cash,
            warehouse=self.warehouse,
            product=self.product_cash,
            quantity=100,
            unit_cost=Decimal("60.00"),
            retail_price=Decimal("100.00"),
        )
        self.stock_product_credit = StockProduct.objects.create(
            stock=self.stock_credit,
            warehouse=self.warehouse,
            product=self.product_credit,
            quantity=100,
            unit_cost=Decimal("30.00"),
            retail_price=Decimal("50.00"),
        )

        self.customer_credit = Customer.objects.create(
            business=self.business,
            name="Credit Customer",
            created_by=self.user,
            credit_limit=Decimal("1000.00"),
            credit_terms_days=30,
        )

        self.client.force_authenticate(self.user)

    def _create_completed_cash_sale(self):
        sale = Sale.objects.create(
            business=self.business,
            storefront=self.storefront,
            user=self.user,
            payment_type="CASH",
            status="COMPLETED",
            type="RETAIL",
        )

        SaleItem.objects.create(
            sale=sale,
            product=self.product_cash,
            stock=self.stock_cash,
            stock_product=self.stock_product_cash,
            quantity=Decimal("2"),
            unit_price=Decimal("100.00"),
            tax_rate=Decimal("10.00"),
        )

        sale.calculate_totals()
        sale.amount_paid = sale.total_amount
        sale.amount_due = Decimal("0.00")
        sale.receipt_number = "RCPT-CASH-001"
        sale.completed_at = timezone.now()
        sale.save()
        return sale

    def _create_partial_credit_sale(self):
        sale = Sale.objects.create(
            business=self.business,
            storefront=self.storefront,
            user=self.user,
            customer=self.customer_credit,
            payment_type="CREDIT",
            status="PARTIAL",
            type="RETAIL",
        )

        SaleItem.objects.create(
            sale=sale,
            product=self.product_credit,
            stock=self.stock_credit,
            stock_product=self.stock_product_credit,
            quantity=Decimal("3"),
            unit_price=Decimal("50.00"),
            tax_rate=Decimal("0.00"),
        )

        sale.calculate_totals()
        sale.amount_paid = Decimal("75.00")
        sale.amount_due = sale.total_amount - sale.amount_paid
        sale.receipt_number = "RCPT-CREDIT-001"
        sale.completed_at = timezone.now()
        sale.save()
        return sale