from __future__ import annotations

import uuid
from decimal import Decimal
from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

from accounts.models import Business
from inventory.models import StoreFront, BusinessStoreFront
from sales.models import Customer, Sale, AccountsReceivable, ARPayment


class CreditUtilizationReportTests(TestCase):
    """Validate the credit utilization analytics endpoint."""

    def setUp(self):
        cache.clear()

        self.user = get_user_model().objects.create_user(
            email='owner@example.com',
            password='pass1234',
            name='Report Owner'
        )

        self.client = APIClient()
        self.client.force_authenticate(self.user)

        self.business = Business.objects.create(
            owner=self.user,
            name='Utilization Biz',
            tin=str(uuid.uuid4()),
            email='biz@example.com',
            address='123 Finance Street',
            phone_numbers=['+233000000'],
        )

        self.storefront = StoreFront.objects.create(
            user=self.user,
            name='Main Store',
            location='Accra HQ'
        )
        BusinessStoreFront.objects.create(
            business=self.business,
            storefront=self.storefront
        )

        self.today = timezone.now().date()

        self.customer_high = Customer.objects.create(
            business=self.business,
            name='Ama Serwaa',
            email='ama.serwaa@example.com',
            phone='+233111111',
            customer_type='RETAIL',
            credit_limit=Decimal('5000.00'),
            outstanding_balance=Decimal('4800.00'),
            credit_terms_days=30,
            created_by=self.user
        )
        self.customer_low = Customer.objects.create(
            business=self.business,
            name='Kwame Mensah',
            email='kwame.m@example.com',
            phone='+233222222',
            customer_type='RETAIL',
            credit_limit=Decimal('6000.00'),
            outstanding_balance=Decimal('1200.00'),
            credit_terms_days=45,
            created_by=self.user
        )

        self._seed_high_risk_credit_profile()
        self._seed_low_risk_credit_profile()

        self.url = reverse('customer-credit-utilization-report')

    def _create_credit_sale(self, customer: Customer, amount: Decimal, receipt_suffix: str, created_at) -> Sale:
        sale = Sale.objects.create(
            business=self.business,
            storefront=self.storefront,
            user=self.user,
            customer=customer,
            payment_type=Sale.PAYMENT_TYPE_CREDIT,
            status=Sale.STATUS_PENDING,
            type=Sale.TYPE_RETAIL if customer.customer_type == 'RETAIL' else Sale.TYPE_WHOLESALE,
            is_credit_sale=True,
            subtotal=amount,
            total_amount=amount,
            amount_due=amount,
            amount_paid=Decimal('0.00'),
            receipt_number=f'RCPT-{receipt_suffix}-{uuid.uuid4().hex[:6]}'
        )

        Sale.objects.filter(id=sale.id).update(
            created_at=created_at,
            updated_at=created_at,
            completed_at=created_at
        )
        sale.refresh_from_db()
        return sale

    def _seed_high_risk_credit_profile(self):
        sale_date = timezone.now() - timedelta(days=80)
        due_date = (sale_date.date() + timedelta(days=self.customer_high.credit_terms_days))

        sale = self._create_credit_sale(
            customer=self.customer_high,
            amount=Decimal('5000.00'),
            receipt_suffix='HIGH',
            created_at=sale_date
        )

        AccountsReceivable.objects.create(
            sale=sale,
            customer=self.customer_high,
            original_amount=Decimal('5000.00'),
            amount_paid=Decimal('200.00'),
            amount_outstanding=Decimal('4800.00'),
            due_date=due_date
        )

        self.customer_high.refresh_from_db()
        self.customer_high.outstanding_balance = Decimal('4800.00')
        self.customer_high.save(update_fields=['outstanding_balance'])

    def _seed_low_risk_credit_profile(self):
        sale_date = timezone.now() - timedelta(days=15)
        due_date = (sale_date.date() + timedelta(days=self.customer_low.credit_terms_days))

        sale = self._create_credit_sale(
            customer=self.customer_low,
            amount=Decimal('2000.00'),
            receipt_suffix='LOW',
            created_at=sale_date
        )

        ar = AccountsReceivable.objects.create(
            sale=sale,
            customer=self.customer_low,
            original_amount=Decimal('2000.00'),
            amount_paid=Decimal('0.00'),
            amount_outstanding=Decimal('2000.00'),
            due_date=due_date
        )

        payment_date = sale_date + timedelta(days=10)
        ARPayment.objects.create(
            accounts_receivable=ar,
            amount=Decimal('800.00'),
            payment_method='CASH',
            payment_date=payment_date,
            received_by=self.user
        )

        ar.refresh_from_db()
        self.customer_low.refresh_from_db()
        self.low_last_payment_date = payment_date.date()

    def test_credit_utilization_summary_and_customers(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        self.assertTrue(payload['success'])

        summary = payload['data']['summary']
        self.assertEqual(summary['total_customers_with_credit'], 2)
        self.assertEqual(summary['over_80_percent'], 1)
        self.assertEqual(summary['credit_risk_high'], 1)
        self.assertAlmostEqual(summary['total_credit_extended'], 11000.00, places=2)
        self.assertAlmostEqual(summary['total_credit_used'], 6000.00, places=2)
        self.assertAlmostEqual(summary['average_utilization'], 58.0, places=1)

        risk_distribution = payload['data']['risk_distribution']
        self.assertEqual(risk_distribution['high'], 1)
        self.assertEqual(risk_distribution['medium'], 0)
        self.assertEqual(risk_distribution['low'], 1)

        customers = payload['data']['customers']
        self.assertEqual(len(customers), 2)

        meta = payload['meta']
        pagination = meta['pagination']
        self.assertEqual(pagination['page'], 1)
        self.assertEqual(pagination['page_size'], 50)
        self.assertEqual(pagination['total_count'], 2)
        self.assertEqual(pagination['total_pages'], 1)
        self.assertFalse(pagination['has_next'])
        self.assertFalse(pagination['has_previous'])

        first = customers[0]
        self.assertEqual(first['customer_id'], str(self.customer_high.id))
        self.assertEqual(first['risk_level'], 'high')
        self.assertEqual(first['recommended_action'], 'reduce_limit')
        self.assertGreaterEqual(first['utilization_percentage'], 90.0)

        second = customers[1]
        self.assertEqual(second['customer_id'], str(self.customer_low.id))
        self.assertEqual(second['risk_level'], 'low')
        self.assertEqual(second['recommended_action'], 'increase_limit')
        self.assertEqual(second['last_payment_date'], self.low_last_payment_date.isoformat())

    def test_sort_by_risk_orders_high_first(self):
        response = self.client.get(self.url, {'sort_by': 'risk'})
        self.assertEqual(response.status_code, 200)
        customers = response.json()['data']['customers']
        self.assertEqual(customers[0]['risk_level'], 'high')
        self.assertEqual(customers[-1]['risk_level'], 'low')

    def test_threshold_override_counts_expected_customers(self):
        response = self.client.get(self.url, {'utilization_threshold': 10})
        self.assertEqual(response.status_code, 200)
        summary = response.json()['data']['summary']
        self.assertEqual(summary['over_80_percent'], 2)

    def test_segment_filter_returns_no_data_for_wholesale(self):
        response = self.client.get(self.url, {'segment': 'wholesale'})
        self.assertEqual(response.status_code, 200)
        payload = response.json()['data']
        self.assertEqual(payload['summary']['total_customers_with_credit'], 0)
        self.assertEqual(payload['summary']['total_credit_extended'], 0)
        self.assertEqual(payload['customers'], [])
        self.assertEqual(payload['risk_distribution'], {'low': 0, 'medium': 0, 'high': 0})

    def test_pagination_honors_page_and_page_size(self):
        response = self.client.get(self.url, {'page': 2, 'page_size': 1})
        self.assertEqual(response.status_code, 200)

        payload = response.json()
        customers = payload['data']['customers']
        self.assertEqual(len(customers), 1)
        self.assertEqual(customers[0]['customer_id'], str(self.customer_low.id))

        pagination = payload['meta']['pagination']
        self.assertEqual(pagination['page'], 2)
        self.assertEqual(pagination['page_size'], 1)
        self.assertEqual(pagination['total_count'], 2)
        self.assertEqual(pagination['total_pages'], 2)
        self.assertFalse(pagination['has_next'])
        self.assertTrue(pagination['has_previous'])
