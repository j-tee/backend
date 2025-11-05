from decimal import Decimal
import csv
import io
import uuid
from typing import Optional

from django.contrib.auth import get_user_model
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
from reports.utils.response import ReportError
from reports.utils.profit_calculator import ProfitCalculator
from sales.models import Customer, Sale, SaleItem, AccountsReceivable, Payment


User = get_user_model()


class StorefrontSalesReportBaseCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="reports-user@example.com",
            password="strongpass123",
            name="Reports Owner",
        )
        self.business = Business.objects.create(
            owner=self.user,
            name="Storefront Reports Biz",
            tin="TIN-987654",
            email="reports-biz@example.com",
            address="456 Analytics Ave",
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

        self.primary_storefront = StoreFront.objects.create(
            user=self.user,
            name="Primary Store",
            location="Accra",
        )
        self.secondary_storefront = StoreFront.objects.create(
            user=self.user,
            name="Secondary Store",
            location="Kumasi",
        )
        BusinessStoreFront.objects.create(
            business=self.business,
            storefront=self.primary_storefront,
        )
        BusinessStoreFront.objects.create(
            business=self.business,
            storefront=self.secondary_storefront,
        )

        self.category = Category.objects.create(name="Point of Sale")
        self.product_alpha = Product.objects.create(
            business=self.business,
            name="POS Bundle",
            sku="POS-ALPHA",
            category=self.category,
        )
        self.product_beta = Product.objects.create(
            business=self.business,
            name="Barcode Suite",
            sku="POS-BETA",
            category=self.category,
        )

        self.warehouse = Warehouse.objects.create(
            name="Analytics Warehouse",
            location="Tema",
            manager=self.user,
        )

        today = timezone.now().date()
        self.stock_for_product = {}
        for product, unit_cost, retail_price in [
            (self.product_alpha, Decimal("50.00"), Decimal("120.00")),
            (self.product_beta, Decimal("60.00"), Decimal("150.00")),
        ]:
            stock = Stock.objects.create(
                business=self.business,
                arrival_date=today,
            )
            stock_product = StockProduct.objects.create(
                stock=stock,
                warehouse=self.warehouse,
                product=product,
                quantity=100,
                unit_cost=unit_cost,
                retail_price=retail_price,
            )
            self.stock_for_product[product.id] = (stock, stock_product)

        self.client.force_authenticate(self.user)
        self.today = today

    def _create_completed_sale(
        self,
        *,
        storefront: StoreFront,
        product: Product,
        quantity: Decimal,
        unit_price: Decimal,
        customer: Optional[Customer] = None,
        sale_type: str = "RETAIL",
        payment_type: str = "CASH",
    ) -> Sale:
        sale = Sale.objects.create(
            business=self.business,
            storefront=storefront,
            user=self.user,
            customer=customer,
            payment_type=payment_type,
            status="COMPLETED",
            type=sale_type,
        )
        stock, stock_product = self.stock_for_product[product.id]
        SaleItem.objects.create(
            sale=sale,
            product=product,
            stock=stock,
            stock_product=stock_product,
            quantity=quantity,
            unit_price=unit_price,
            tax_rate=Decimal("0.00"),
        )
        sale.calculate_totals()
        sale.amount_paid = sale.total_amount
        sale.amount_due = Decimal("0.00")
        sale.receipt_number = f"RCPT-{sale.id}"
        sale.completed_at = timezone.now()
        sale.save()
        return sale

    def _create_credit_sale_with_ar(
        self,
        *,
        storefront: StoreFront,
        product: Product,
        quantity: Decimal,
        unit_price: Decimal,
        customer: Customer,
        sale_type: str = "RETAIL",
    ) -> AccountsReceivable:
        sale = Sale.objects.create(
            business=self.business,
            storefront=storefront,
            user=self.user,
            customer=customer,
            payment_type="CREDIT",
            status="COMPLETED",
            type=sale_type,
            is_credit_sale=True,
        )
        stock, stock_product = self.stock_for_product[product.id]
        SaleItem.objects.create(
            sale=sale,
            product=product,
            stock=stock,
            stock_product=stock_product,
            quantity=quantity,
            unit_price=unit_price,
            tax_rate=Decimal("0.00"),
        )
        sale.calculate_totals()
        sale.amount_paid = Decimal("0.00")
        sale.amount_due = sale.total_amount
        sale.receipt_number = f"CREDIT-{sale.id}"
        sale.completed_at = timezone.now()
        sale.save()

        ar = AccountsReceivable.objects.create(
            sale=sale,
            customer=customer,
            original_amount=sale.total_amount,
            amount_paid=Decimal("0.00"),
            amount_outstanding=sale.total_amount,
            status="PENDING",
            created_by=self.user,
        )
        return ar

    def _base_params(self):
        date_str = self.today.isoformat()
        return {'start_date': date_str, 'end_date': date_str}

    def _record_payment(
        self,
        sale: Sale,
        customer: Customer,
        amount: Decimal,
        *,
        payment_method: str = 'CASH'
    ) -> Payment:
        payment = Payment.objects.create(
            sale=sale,
            customer=customer,
            amount_paid=amount,
            payment_method=payment_method,
            status='SUCCESSFUL',
            processed_by=self.user,
        )
        sale.amount_paid = amount
        remaining = sale.total_amount - amount
        sale.amount_due = remaining if remaining > Decimal('0.00') else Decimal('0.00')
        sale.status = Sale.STATUS_PARTIAL if sale.amount_due > 0 else Sale.STATUS_COMPLETED
        if sale.customer_id != customer.id:
            sale.customer = customer
        sale.save(update_fields=['amount_paid', 'amount_due', 'status', 'customer'])
        return payment


class ProductPerformanceStorefrontFilterTests(StorefrontSalesReportBaseCase):
    def test_product_performance_scopes_results_by_storefront(self):
        primary_sale = self._create_completed_sale(
            storefront=self.primary_storefront,
            product=self.product_alpha,
            quantity=Decimal("2"),
            unit_price=Decimal("120.00"),
        )
        secondary_sale = self._create_completed_sale(
            storefront=self.secondary_storefront,
            product=self.product_beta,
            quantity=Decimal("1"),
            unit_price=Decimal("200.00"),
        )

        url = reverse('product-performance-report')
        params = self._base_params()

        response_all = self.client.get(url, params)
        self.assertEqual(response_all.status_code, 200)
        total_all = response_all.data['data']['summary']['total_revenue']
        expected_all = float(primary_sale.total_amount + secondary_sale.total_amount)
        self.assertAlmostEqual(total_all, expected_all, places=2)

        filtered_params = dict(params)
        filtered_params['storefront_id'] = str(self.primary_storefront.id)
        response_filtered = self.client.get(url, filtered_params)
        self.assertEqual(response_filtered.status_code, 200)

        filtered_total = response_filtered.data['data']['summary']['total_revenue']
        self.assertAlmostEqual(filtered_total, float(primary_sale.total_amount), places=2)

        metadata_filters = response_filtered.data['data']['metadata']['filters_applied']
        self.assertEqual(metadata_filters['storefront_ids'], [str(self.primary_storefront.id)])
        self.assertIn(self.primary_storefront.name, metadata_filters['storefront_names'])

    def test_product_performance_csv_export_respects_storefront_scope(self):
        focused_sale = self._create_completed_sale(
            storefront=self.primary_storefront,
            product=self.product_alpha,
            quantity=Decimal("3"),
            unit_price=Decimal("100.00"),
        )
        self._create_completed_sale(
            storefront=self.secondary_storefront,
            product=self.product_beta,
            quantity=Decimal("1"),
            unit_price=Decimal("180.00"),
        )

        url = reverse('product-performance-report')
        params = self._base_params()
        params['storefront_ids'] = str(self.primary_storefront.id)
        params['export_format'] = 'csv'

        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')

        rows = list(csv.reader(io.StringIO(response.content.decode('utf-8'))))
        scope_row = next(row for row in rows if row and row[0] == 'Storefront Scope')
        self.assertIn(self.primary_storefront.name, scope_row[1])

        total_row = next(row for row in rows if row and row[0] == 'Total Revenue')
        expected_total = f"${float(focused_sale.total_amount):,.2f}"
        self.assertEqual(total_row[1], expected_total)

    def test_product_performance_invalid_storefront_rejected(self):
        url = reverse('product-performance-report')
        params = self._base_params()
        params['storefront_id'] = str(uuid.uuid4())

        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error']['code'], ReportError.INVALID_FILTER)


class CustomerAnalyticsStorefrontFilterTests(StorefrontSalesReportBaseCase):
    def setUp(self):
        super().setUp()
        self.customer_primary = Customer.objects.create(
            business=self.business,
            name="Alice Customer",
            email="alice@example.com",
            credit_limit=Decimal("1000.00"),
            credit_terms_days=30,
            created_by=self.user,
        )
        self.customer_secondary = Customer.objects.create(
            business=self.business,
            name="Bob Customer",
            email="bob@example.com",
            credit_limit=Decimal("500.00"),
            credit_terms_days=30,
            created_by=self.user,
        )

    def test_customer_analytics_respects_storefront_filters(self):
        primary_sales = [
            self._create_completed_sale(
                storefront=self.primary_storefront,
                product=self.product_alpha,
                quantity=Decimal("1"),
                unit_price=Decimal("150.00"),
                customer=self.customer_primary,
            ),
            self._create_completed_sale(
                storefront=self.primary_storefront,
                product=self.product_beta,
                quantity=Decimal("2"),
                unit_price=Decimal("90.00"),
                customer=self.customer_primary,
            ),
        ]
        self._create_completed_sale(
            storefront=self.secondary_storefront,
            product=self.product_beta,
            quantity=Decimal("1"),
            unit_price=Decimal("220.00"),
            customer=self.customer_secondary,
        )

        url = reverse('customer-analytics-report')
        params = self._base_params()

        response_all = self.client.get(url, params)
        self.assertEqual(response_all.status_code, 200)
        self.assertEqual(response_all.data['data']['summary']['total_customers'], 2)

        filtered_params = dict(params)
        filtered_params['storefront_ids'] = str(self.primary_storefront.id)
        response_filtered = self.client.get(url, filtered_params)
        self.assertEqual(response_filtered.status_code, 200)

        summary_filtered = response_filtered.data['data']['summary']
        expected_revenue = float(sum(sale.total_amount for sale in primary_sales))
        self.assertEqual(summary_filtered['total_customers'], 1)
        self.assertAlmostEqual(summary_filtered['total_revenue'], expected_revenue, places=2)

        results = response_filtered.data['data']['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['customer_name'], self.customer_primary.name)

        metadata_filters = response_filtered.data['data']['metadata']['filters_applied']
        self.assertEqual(metadata_filters['storefront_ids'], [str(self.primary_storefront.id)])
        self.assertIn(self.primary_storefront.name, metadata_filters['storefront_names'])

    def test_customer_analytics_csv_export_includes_storefront_scope(self):
        focused_sale = self._create_completed_sale(
            storefront=self.primary_storefront,
            product=self.product_alpha,
            quantity=Decimal("2"),
            unit_price=Decimal("160.00"),
            customer=self.customer_primary,
        )
        self._create_completed_sale(
            storefront=self.secondary_storefront,
            product=self.product_beta,
            quantity=Decimal("1"),
            unit_price=Decimal("210.00"),
            customer=self.customer_secondary,
        )

        url = reverse('customer-analytics-report')
        params = self._base_params()
        params['storefront_id'] = str(self.primary_storefront.id)
        params['export_format'] = 'csv'

        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')

        rows = list(csv.reader(io.StringIO(response.content.decode('utf-8'))))
        scope_row = next(row for row in rows if row and row[0] == 'Storefront Scope')
        self.assertIn(self.primary_storefront.name, scope_row[1])

        total_customers_row = next(row for row in rows if row and row[0] == 'Total Customers')
        self.assertEqual(total_customers_row[1], '1')

        total_revenue_row = next(row for row in rows if row and row[0] == 'Total Revenue')
        expected_revenue = f"${float(focused_sale.total_amount):,.2f}"
        self.assertEqual(total_revenue_row[1], expected_revenue)

    def test_customer_analytics_invalid_storefront_returns_not_found(self):
        self._create_completed_sale(
            storefront=self.primary_storefront,
            product=self.product_alpha,
            quantity=Decimal("1"),
            unit_price=Decimal("150.00"),
            customer=self.customer_primary,
        )

        url = reverse('customer-analytics-report')
        params = self._base_params()
        params['storefront_id'] = str(uuid.uuid4())

        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error']['code'], ReportError.INVALID_FILTER)
        self.assertIn('storefront_ids', response.data['error']['details'])


class RevenueTrendsStorefrontFilterTests(StorefrontSalesReportBaseCase):
    def test_revenue_trends_scopes_results_by_storefront(self):
        primary_sale = self._create_completed_sale(
            storefront=self.primary_storefront,
            product=self.product_alpha,
            quantity=Decimal("2"),
            unit_price=Decimal("110.00"),
        )
        self._create_completed_sale(
            storefront=self.secondary_storefront,
            product=self.product_beta,
            quantity=Decimal("1"),
            unit_price=Decimal("250.00"),
        )

        url = reverse('revenue-trends-report')
        params = self._base_params()
        params['storefront_id'] = str(self.primary_storefront.id)

        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200)

        summary = response.data['data']['summary']
        self.assertAlmostEqual(summary['total_revenue'], float(primary_sale.total_amount), places=2)
        self.assertEqual(summary['total_orders'], 1)

        metadata_filters = response.data['data']['metadata']['filters_applied']
        self.assertEqual(metadata_filters['storefront_ids'], [str(self.primary_storefront.id)])
        self.assertIn(self.primary_storefront.name, metadata_filters['storefront_names'])

        trends = response.data['data']['results']['trends']
        self.assertTrue(trends)
        self.assertTrue(
            any(abs(point['revenue'] - float(primary_sale.total_amount)) < 0.01 for point in trends)
        )

    def test_revenue_trends_csv_export_respects_storefront_scope(self):
        primary_sale = self._create_completed_sale(
            storefront=self.primary_storefront,
            product=self.product_alpha,
            quantity=Decimal("1"),
            unit_price=Decimal("180.00"),
            payment_type="CARD",
        )
        self._create_completed_sale(
            storefront=self.secondary_storefront,
            product=self.product_beta,
            quantity=Decimal("1"),
            unit_price=Decimal("220.00"),
            payment_type="CASH",
        )

        url = reverse('revenue-trends-report')
        params = self._base_params()
        params['storefront_ids'] = str(self.primary_storefront.id)
        params['export_format'] = 'csv'

        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')

        rows = list(csv.reader(io.StringIO(response.content.decode('utf-8'))))
        scope_row = next(row for row in rows if row and row[0] == 'Storefront Scope')
        self.assertIn(self.primary_storefront.name, scope_row[1])

        total_row = next(row for row in rows if row and row[0] == 'Total Revenue')
        expected_total = f"${float(primary_sale.total_amount):,.2f}"
        self.assertEqual(total_row[1], expected_total)

    def test_revenue_trends_invalid_storefront_returns_not_found(self):
        self._create_completed_sale(
            storefront=self.primary_storefront,
            product=self.product_alpha,
            quantity=Decimal("1"),
            unit_price=Decimal("120.00"),
        )

        url = reverse('revenue-trends-report')
        params = self._base_params()
        params['storefront_id'] = str(uuid.uuid4())

        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error']['code'], ReportError.INVALID_FILTER)


class RevenueProfitStorefrontFilterTests(StorefrontSalesReportBaseCase):
    def test_revenue_profit_scopes_summary_by_storefront(self):
        primary_sales = [
            self._create_completed_sale(
                storefront=self.primary_storefront,
                product=self.product_alpha,
                quantity=Decimal("2"),
                unit_price=Decimal("130.00"),
                sale_type="RETAIL",
            ),
            self._create_completed_sale(
                storefront=self.primary_storefront,
                product=self.product_beta,
                quantity=Decimal("1"),
                unit_price=Decimal("200.00"),
                sale_type="WHOLESALE",
            ),
        ]
        self._create_completed_sale(
            storefront=self.secondary_storefront,
            product=self.product_beta,
            quantity=Decimal("1"),
            unit_price=Decimal("240.00"),
        )

        url = reverse('revenue-profit-report')
        params = self._base_params()
        params['storefront_id'] = str(self.primary_storefront.id)

        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200)

        summary = response.data['data']['summary']
        expected_revenue = float(sum(sale.total_amount for sale in primary_sales))
        self.assertAlmostEqual(summary['total_revenue'], expected_revenue, places=2)

        primary_ids = [sale.id for sale in primary_sales]
        expected_profit = float(
            ProfitCalculator.calculate_total_profit(
                Sale.objects.filter(id__in=primary_ids)
            )
        )
        self.assertAlmostEqual(summary['gross_profit'], expected_profit, places=2)

        metadata_filters = response.data['data']['metadata']['filters_applied']
        self.assertEqual(metadata_filters['storefront_ids'], [str(self.primary_storefront.id)])
        self.assertIn(self.primary_storefront.name, metadata_filters['storefront_names'])

        results = response.data['data']['results']
        self.assertTrue(results)
        self.assertTrue(any(abs(point['revenue'] - expected_revenue) < 0.01 for point in results))

    def test_revenue_profit_csv_export_includes_storefront_scope(self):
        primary_sale = self._create_completed_sale(
            storefront=self.primary_storefront,
            product=self.product_alpha,
            quantity=Decimal("1"),
            unit_price=Decimal("190.00"),
        )
        self._create_completed_sale(
            storefront=self.secondary_storefront,
            product=self.product_beta,
            quantity=Decimal("1"),
            unit_price=Decimal("210.00"),
        )

        url = reverse('revenue-profit-report')
        params = self._base_params()
        params['storefront_ids'] = str(self.primary_storefront.id)
        params['export_format'] = 'csv'

        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')

        rows = list(csv.reader(io.StringIO(response.content.decode('utf-8'))))
        scope_row = next(row for row in rows if row and row[0] == 'Storefront Scope')
        self.assertIn(self.primary_storefront.name, scope_row[1])

        total_row = next(row for row in rows if row and row[0] == 'Total Revenue')
        expected_total = f"${float(primary_sale.total_amount):,.2f}"
        self.assertEqual(total_row[1], expected_total)

    def test_revenue_profit_invalid_storefront_returns_not_found(self):
        self._create_completed_sale(
            storefront=self.primary_storefront,
            product=self.product_alpha,
            quantity=Decimal("1"),
            unit_price=Decimal("140.00"),
        )

        url = reverse('revenue-profit-report')
        params = self._base_params()
        params['storefront_id'] = str(uuid.uuid4())

        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error']['code'], ReportError.INVALID_FILTER)


class ARAgingStorefrontFilterTests(StorefrontSalesReportBaseCase):
    def setUp(self):
        super().setUp()
        self.customer_primary = Customer.objects.create(
            business=self.business,
            name="Credit Alice",
            email="credit.alice@example.com",
            credit_limit=Decimal("1000.00"),
            created_by=self.user,
        )
        self.customer_secondary = Customer.objects.create(
            business=self.business,
            name="Credit Bob",
            email="credit.bob@example.com",
            credit_limit=Decimal("500.00"),
            created_by=self.user,
        )

    def test_ar_aging_scopes_results_by_storefront(self):
        ar_primary = self._create_credit_sale_with_ar(
            storefront=self.primary_storefront,
            product=self.product_alpha,
            quantity=Decimal("1"),
            unit_price=Decimal("250.00"),
            customer=self.customer_primary,
            sale_type="RETAIL",
        )
        self._create_credit_sale_with_ar(
            storefront=self.secondary_storefront,
            product=self.product_beta,
            quantity=Decimal("1"),
            unit_price=Decimal("300.00"),
            customer=self.customer_secondary,
            sale_type="WHOLESALE",
        )

        url = reverse('ar-aging-report')
        params = {'storefront_id': str(self.primary_storefront.id)}

        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200)

        summary = response.data['data']['summary']
        self.assertAlmostEqual(summary['total_ar_outstanding'], float(ar_primary.amount_outstanding), places=2)
        self.assertEqual(summary['total_customers_with_balance'], 1)

        metadata_filters = response.data['data']['metadata']['filters_applied']
        self.assertEqual(metadata_filters['storefront_ids'], [str(self.primary_storefront.id)])
        self.assertIn(self.primary_storefront.name, metadata_filters['storefront_names'])

        results = response.data['data']['results']
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['customer_name'], self.customer_primary.name)

    def test_ar_aging_csv_export_includes_storefront_scope(self):
        ar_primary = self._create_credit_sale_with_ar(
            storefront=self.primary_storefront,
            product=self.product_alpha,
            quantity=Decimal("1"),
            unit_price=Decimal("180.00"),
            customer=self.customer_primary,
            sale_type="RETAIL",
        )
        self._create_credit_sale_with_ar(
            storefront=self.secondary_storefront,
            product=self.product_beta,
            quantity=Decimal("1"),
            unit_price=Decimal("210.00"),
            customer=self.customer_secondary,
            sale_type="WHOLESALE",
        )

        url = reverse('ar-aging-report')
        params = {
            'storefront_ids': str(self.primary_storefront.id),
            'export_format': 'csv',
        }

        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')

        rows = list(csv.reader(io.StringIO(response.content.decode('utf-8'))))
        scope_row = next(row for row in rows if row and row[0] == 'Storefront Scope')
        self.assertIn(self.primary_storefront.name, scope_row[1])

        total_row = next(row for row in rows if row and row[0] == 'Total AR Outstanding')
        expected_total = f"${float(ar_primary.amount_outstanding):,.2f}"
        self.assertEqual(total_row[1], expected_total)

    def test_ar_aging_invalid_storefront_returns_not_found(self):
        url = reverse('ar-aging-report')
        params = {
            'storefront_id': str(uuid.uuid4()),
        }

        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error']['code'], ReportError.INVALID_FILTER)


class CollectionRatesStorefrontFilterTests(StorefrontSalesReportBaseCase):
    def setUp(self):
        super().setUp()
        self.customer_primary = Customer.objects.create(
            business=self.business,
            name="Collection Alice",
            email="collection.alice@example.com",
            credit_limit=Decimal("1500.00"),
            created_by=self.user,
        )
        self.customer_secondary = Customer.objects.create(
            business=self.business,
            name="Collection Bob",
            email="collection.bob@example.com",
            credit_limit=Decimal("800.00"),
            created_by=self.user,
        )

    def test_collection_rates_scopes_summary_by_storefront(self):
        primary_ar = self._create_credit_sale_with_ar(
            storefront=self.primary_storefront,
            product=self.product_alpha,
            quantity=Decimal("1"),
            unit_price=Decimal("220.00"),
            customer=self.customer_primary,
            sale_type="RETAIL",
        )
        secondary_ar = self._create_credit_sale_with_ar(
            storefront=self.secondary_storefront,
            product=self.product_beta,
            quantity=Decimal("1"),
            unit_price=Decimal("260.00"),
            customer=self.customer_secondary,
            sale_type="WHOLESALE",
        )

        self._record_payment(primary_ar.sale, self.customer_primary, Decimal("120.00"))

        url = reverse('collection-rates-report')
        params = self._base_params()
        params['storefront_id'] = str(self.primary_storefront.id)

        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200)

        summary = response.data['data']['summary']
        self.assertEqual(summary['total_credit_sales_amount'], str(primary_ar.sale.total_amount))
        self.assertEqual(summary['total_collected_amount'], "120.00")
        outstanding = primary_ar.sale.total_amount - Decimal("120.00")
        self.assertEqual(summary['outstanding_amount'], str(outstanding))
        self.assertAlmostEqual(summary['overall_collection_rate'], round(float(Decimal("120.00") / primary_ar.sale.total_amount * 100), 2))
        self.assertEqual(summary['retail']['credit_sales_count'], 1)
        self.assertEqual(summary['wholesale']['credit_sales_count'], 0)

        metadata_filters = response.data['data']['metadata']['filters_applied']
        self.assertEqual(metadata_filters['storefront_ids'], [str(self.primary_storefront.id)])
        self.assertIn(self.primary_storefront.name, metadata_filters['storefront_names'])

        self.assertTrue(response.data['data']['results'])

        params_all = self._base_params()
        response_all = self.client.get(url, params_all)
        self.assertEqual(response_all.status_code, 200)
        summary_all = response_all.data['data']['summary']
        combined_total = primary_ar.sale.total_amount + secondary_ar.sale.total_amount
        self.assertEqual(summary_all['total_credit_sales_amount'], str(combined_total))

    def test_collection_rates_csv_export_respects_storefront_scope(self):
        focused_ar = self._create_credit_sale_with_ar(
            storefront=self.primary_storefront,
            product=self.product_alpha,
            quantity=Decimal("1"),
            unit_price=Decimal("210.00"),
            customer=self.customer_primary,
            sale_type="RETAIL",
        )
        self._record_payment(focused_ar.sale, self.customer_primary, Decimal("80.00"))
        self._create_credit_sale_with_ar(
            storefront=self.secondary_storefront,
            product=self.product_beta,
            quantity=Decimal("1"),
            unit_price=Decimal("240.00"),
            customer=self.customer_secondary,
            sale_type="WHOLESALE",
        )

        url = reverse('collection-rates-report')
        params = self._base_params()
        params['storefront_ids'] = str(self.primary_storefront.id)
        params['export_format'] = 'csv'

        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')

        rows = list(csv.reader(io.StringIO(response.content.decode('utf-8'))))
        scope_row = next(row for row in rows if row and row[0] == 'Storefront Scope')
        self.assertIn(self.primary_storefront.name, scope_row[1])

        total_row = next(row for row in rows if row and row[0] == 'Total Credit Sales Amount')
        expected_total = f"${float(focused_ar.sale.total_amount):,.2f}"
        self.assertEqual(total_row[1], expected_total)

        collected_row = next(row for row in rows if row and row[0] == 'Total Collected Amount')
        self.assertEqual(collected_row[1], "$80.00")

    def test_collection_rates_invalid_storefront_returns_not_found(self):
        url = reverse('collection-rates-report')
        params = self._base_params()
        params['storefront_id'] = str(uuid.uuid4())

        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error']['code'], ReportError.INVALID_FILTER)


class CashFlowStorefrontFilterTests(StorefrontSalesReportBaseCase):
    def setUp(self):
        super().setUp()
        self.cash_customer = Customer.objects.create(
            business=self.business,
            name="Cash Flow Alice",
            email="cash.alice@example.com",
            credit_limit=Decimal("0.00"),
            created_by=self.user,
        )
        self.secondary_customer = Customer.objects.create(
            business=self.business,
            name="Cash Flow Bob",
            email="cash.bob@example.com",
            credit_limit=Decimal("0.00"),
            created_by=self.user,
        )

    def test_cash_flow_scopes_summary_by_storefront(self):
        primary_sale = self._create_completed_sale(
            storefront=self.primary_storefront,
            product=self.product_alpha,
            quantity=Decimal("1"),
            unit_price=Decimal("150.00"),
            customer=self.cash_customer,
            sale_type="RETAIL",
            payment_type="CASH",
        )
        secondary_sale = self._create_completed_sale(
            storefront=self.secondary_storefront,
            product=self.product_beta,
            quantity=Decimal("1"),
            unit_price=Decimal("210.00"),
            customer=self.secondary_customer,
            sale_type="WHOLESALE",
            payment_type="CARD",
        )

        self._record_payment(primary_sale, self.cash_customer, primary_sale.total_amount, payment_method='CASH')
        self._record_payment(secondary_sale, self.secondary_customer, secondary_sale.total_amount, payment_method='CARD')

        url = reverse('cash-flow-report')
        params = self._base_params()
        params['storefront_id'] = str(self.primary_storefront.id)

        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200)

        summary = response.data['data']['summary']
        self.assertEqual(summary['total_inflows'], str(primary_sale.total_amount))
        self.assertEqual(summary['net_cash_flow'], str(primary_sale.total_amount))
        self.assertEqual(summary['retail']['transaction_count'], 1)
        self.assertEqual(summary['wholesale']['transaction_count'], 0)

        metadata_filters = response.data['data']['metadata']['filters_applied']
        self.assertEqual(metadata_filters['storefront_ids'], [str(self.primary_storefront.id)])
        self.assertIn(self.primary_storefront.name, metadata_filters['storefront_names'])

        results = response.data['data']['results']
        self.assertTrue(results)
        self.assertTrue(any(row['inflows'] == str(primary_sale.total_amount) for row in results))

        params_all = self._base_params()
        response_all = self.client.get(url, params_all)
        self.assertEqual(response_all.status_code, 200)
        summary_all = response_all.data['data']['summary']
        combined_total = primary_sale.total_amount + secondary_sale.total_amount
        self.assertEqual(summary_all['total_inflows'], str(combined_total))

    def test_cash_flow_csv_export_respects_storefront_scope(self):
        sale = self._create_completed_sale(
            storefront=self.primary_storefront,
            product=self.product_alpha,
            quantity=Decimal("1"),
            unit_price=Decimal("175.00"),
            customer=self.cash_customer,
            sale_type="RETAIL",
            payment_type="CASH",
        )
        self._record_payment(sale, self.cash_customer, sale.total_amount, payment_method='CASH')

        url = reverse('cash-flow-report')
        params = self._base_params()
        params['storefront_ids'] = str(self.primary_storefront.id)
        params['payment_method'] = 'cash'
        params['export_format'] = 'csv'

        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')

        rows = list(csv.reader(io.StringIO(response.content.decode('utf-8'))))
        scope_row = next(row for row in rows if row and row[0] == 'Storefront Scope')
        self.assertIn(self.primary_storefront.name, scope_row[1])

        total_row = next(row for row in rows if row and row[0] == 'Total Inflows')
        expected_total = f"${float(sale.total_amount):,.2f}"
        self.assertEqual(total_row[1], expected_total)

        payment_method_row = next(row for row in rows if row and row[0] == 'Payment Method')
        self.assertEqual(payment_method_row[1], 'CASH')

    def test_cash_flow_invalid_storefront_returns_not_found(self):
        url = reverse('cash-flow-report')
        params = self._base_params()
        params['storefront_id'] = str(uuid.uuid4())

        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error']['code'], ReportError.INVALID_FILTER)


class TopCustomersStorefrontFilterTests(StorefrontSalesReportBaseCase):
    def setUp(self):
        super().setUp()
        self.customer_primary = Customer.objects.create(
            business=self.business,
            name="Top Alice",
            email="top.alice@example.com",
            credit_limit=Decimal("500.00"),
            created_by=self.user,
        )
        self.customer_secondary = Customer.objects.create(
            business=self.business,
            name="Top Bob",
            email="top.bob@example.com",
            credit_limit=Decimal("500.00"),
            created_by=self.user,
        )

    def test_top_customers_scopes_results_by_storefront(self):
        primary_sale = self._create_completed_sale(
            storefront=self.primary_storefront,
            product=self.product_alpha,
            quantity=Decimal("2"),
            unit_price=Decimal("120.00"),
            customer=self.customer_primary,
        )
        secondary_sale = self._create_completed_sale(
            storefront=self.secondary_storefront,
            product=self.product_beta,
            quantity=Decimal("1"),
            unit_price=Decimal("180.00"),
            customer=self.customer_secondary,
        )

        url = reverse('customer-top-customers')
        params = self._base_params()

        response_all = self.client.get(url, params)
        self.assertEqual(response_all.status_code, 200)
        self.assertEqual(len(response_all.data['data']['customers']), 2)

        filtered_params = dict(params)
        filtered_params['storefront_id'] = str(self.primary_storefront.id)
        response_filtered = self.client.get(url, filtered_params)
        self.assertEqual(response_filtered.status_code, 200)

        customers = response_filtered.data['data']['customers']
        self.assertEqual(len(customers), 1)
        self.assertEqual(customers[0]['customer_name'], self.customer_primary.name)
        filters_metadata = response_filtered.data['data']['metadata']['filters_applied']
        self.assertEqual(filters_metadata['storefront_ids'], [str(self.primary_storefront.id)])
        self.assertIn(self.primary_storefront.name, filters_metadata['storefront_names'])

        summary = response_filtered.data['data']['summary']
        self.assertAlmostEqual(summary['top_10_revenue'], float(primary_sale.total_amount), places=2)

        summary_all = response_all.data['data']['summary']
        expected_revenue = float(primary_sale.total_amount + secondary_sale.total_amount)
        self.assertAlmostEqual(summary_all['top_10_revenue'], expected_revenue, places=2)

    def test_top_customers_csv_export_includes_storefront_scope(self):
        focused_sale = self._create_completed_sale(
            storefront=self.primary_storefront,
            product=self.product_alpha,
            quantity=Decimal("1"),
            unit_price=Decimal("150.00"),
            customer=self.customer_primary,
        )
        self._create_completed_sale(
            storefront=self.secondary_storefront,
            product=self.product_beta,
            quantity=Decimal("1"),
            unit_price=Decimal("200.00"),
            customer=self.customer_secondary,
        )

        url = reverse('customer-top-customers')
        params = self._base_params()
        params['storefront_ids'] = str(self.primary_storefront.id)
        params['export_format'] = 'csv'

        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')

        rows = list(csv.reader(io.StringIO(response.content.decode('utf-8'))))
        scope_row = next(row for row in rows if row and row[0] == 'Storefront Scope')
        self.assertIn(self.primary_storefront.name, scope_row[1])

        header_index = next(
            idx
            for idx, row in enumerate(rows)
            if row and row[0] == 'Customer Name'
        )
        data_row = rows[header_index + 1]
        expected_total = f"{float(focused_sale.total_amount):.2f}"
        self.assertEqual(data_row[3], expected_total)

    def test_top_customers_invalid_storefront_returns_not_found(self):
        url = reverse('customer-top-customers')
        params = self._base_params()
        params['storefront_id'] = str(uuid.uuid4())

        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.data['success'])
        self.assertEqual(response.data['error']['code'], ReportError.INVALID_FILTER)
