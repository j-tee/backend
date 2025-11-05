from decimal import Decimal
import csv
import io
import uuid

from django.urls import reverse
from django.utils import timezone
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
from sales.models import Customer, Sale, SaleItem
from django.contrib.auth import get_user_model
from reports.utils.response import ReportError


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
        self.membership, created = BusinessMembership.objects.get_or_create(
            business=self.business,
            user=self.user,
            defaults={
                'role': BusinessMembership.OWNER,
                'is_admin': True,
                'is_active': True,
            },
        )
        if not created:
            update_fields = []
            if self.membership.role != BusinessMembership.OWNER:
                self.membership.role = BusinessMembership.OWNER
                update_fields.append('role')
            if not self.membership.is_admin:
                self.membership.is_admin = True
                update_fields.append('is_admin')
            if not self.membership.is_active:
                self.membership.is_active = True
                update_fields.append('is_active')
            if update_fields:
                self.membership.save(update_fields=update_fields)
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

    def _create_completed_cash_sale_for_storefront(
        self,
        storefront,
        *,
        quantity: Decimal = Decimal("1"),
        unit_price: Decimal = Decimal("100.00"),
    ):
        sale = Sale.objects.create(
            business=self.business,
            storefront=storefront,
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
            quantity=quantity,
            unit_price=unit_price,
            tax_rate=Decimal("0.00"),
        )

        sale.calculate_totals()
        sale.amount_paid = sale.total_amount
        sale.amount_due = Decimal("0.00")
        sale.receipt_number = f"RCPT-{str(storefront.id)[:8]}"
        sale.completed_at = timezone.now()
        sale.save()
        return sale

    def test_sales_summary_supports_storefront_filters(self):
        sale_primary = self._create_completed_cash_sale()

        secondary_storefront = StoreFront.objects.create(
            user=self.user,
            name="Annex Store",
            location="Kumasi",
        )
        BusinessStoreFront.objects.create(
            business=self.business,
            storefront=secondary_storefront,
        )

        sale_secondary = self._create_completed_cash_sale_for_storefront(
            secondary_storefront,
            quantity=Decimal("1"),
            unit_price=Decimal("150.00"),
        )

        today = timezone.now().date().isoformat()
        url = reverse('sales-summary-report')
        base_params = {'start_date': today, 'end_date': today}

        response_all = self.client.get(url, base_params)
        self.assertEqual(response_all.status_code, 200)
        total_all = response_all.data['data']['summary']['total_sales']
        expected_all = float(sale_primary.total_amount + sale_secondary.total_amount)
        self.assertAlmostEqual(total_all, expected_all, places=2)

        filter_params = dict(base_params)
        filter_params['storefront_ids'] = str(self.storefront.id)
        response_filtered = self.client.get(url, filter_params)
        self.assertEqual(response_filtered.status_code, 200)
        filtered_total = response_filtered.data['data']['summary']['total_sales']
        self.assertAlmostEqual(filtered_total, float(sale_primary.total_amount), places=2)

        filters_payload = response_filtered.data['data']['filters']
        self.assertEqual(filters_payload['storefront_ids'], [str(self.storefront.id)])
        self.assertIn(self.storefront.name, filters_payload['storefront_names'])

        metadata_filters = response_filtered.data['data']['metadata']['filters_applied']
        self.assertEqual(metadata_filters['storefront_ids'], [str(self.storefront.id)])

        single_params = dict(base_params)
        single_params['storefront_id'] = str(secondary_storefront.id)
        response_single = self.client.get(url, single_params)
        self.assertEqual(response_single.status_code, 200)
        single_total = response_single.data['data']['summary']['total_sales']
        self.assertAlmostEqual(single_total, float(sale_secondary.total_amount), places=2)

    def test_sales_summary_invalid_storefront_returns_not_found(self):
        self._create_completed_cash_sale()

        url = reverse('sales-summary-report')
        today = timezone.now().date().isoformat()
        params = {
            'start_date': today,
            'end_date': today,
            'storefront_id': str(uuid.uuid4()),
        }

        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error']['code'], ReportError.INVALID_FILTER)
        self.assertIn('storefront_ids', response.data['error']['details'])

    def test_sales_summary_blocks_storefronts_from_other_businesses(self):
        self._create_completed_cash_sale()

        outsider = User.objects.create_user(
            email="outsider@example.com",
            password="pass12345",
            name="Outsider",
        )
        other_business = Business.objects.create(
            owner=outsider,
            name="Other Biz",
            tin="TIN-000000",
            email="otherbiz@example.com",
            address="1 Elsewhere",
        )
        other_storefront = StoreFront.objects.create(
            user=outsider,
            name="Other Store",
            location="Tamale",
        )
        BusinessStoreFront.objects.create(
            business=other_business,
            storefront=other_storefront,
        )

        url = reverse('sales-summary-report')
        today = timezone.now().date().isoformat()
        params = {
            'start_date': today,
            'end_date': today,
            'storefront_id': str(other_storefront.id),
        }

        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error']['code'], ReportError.INVALID_FILTER)

    def test_sales_summary_csv_export_respects_storefront_filter(self):
        sale_primary = self._create_completed_cash_sale_for_storefront(
            self.storefront,
            quantity=Decimal("1"),
            unit_price=Decimal("200.00"),
        )

        secondary_storefront = StoreFront.objects.create(
            user=self.user,
            name="Annex Store",
            location="Kumasi",
        )
        BusinessStoreFront.objects.create(
            business=self.business,
            storefront=secondary_storefront,
        )
        self._create_completed_cash_sale_for_storefront(
            secondary_storefront,
            quantity=Decimal("1"),
            unit_price=Decimal("300.00"),
        )

        url = reverse('sales-summary-report')
        today = timezone.now().date().isoformat()
        params = {
            'start_date': today,
            'end_date': today,
            'storefront_id': str(self.storefront.id),
            'export_format': 'csv',
        }

        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')

        csv_content = response.content.decode('utf-8')
        rows = list(csv.reader(io.StringIO(csv_content)))

        storefront_row = next(row for row in rows if row and row[0] == 'Storefront Scope')
        self.assertIn(self.storefront.name, storefront_row[1])

        total_sales_row = next(row for row in rows if row and row[0] == 'Total Sales (Revenue)')
        expected_total = f"${float(sale_primary.total_amount):,.2f}"
        self.assertEqual(total_sales_row[1], expected_total)