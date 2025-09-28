from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from inventory.models import Category, Product, StoreFront
from .models import Sale, SaleItem


User = get_user_model()


class SaleItemTaxCalculationTest(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			email='cashier@example.com',
			password='testpass123',
			name='Cashier One'
		)
		self.storefront = StoreFront.objects.create(
			user=self.user,
			name='POS Store',
			location='Main Street'
		)
		self.category = Category.objects.create(name='Beverages')
		self.product = Product.objects.create(
			name='Bottled Water',
			sku='WATER-001',
			category=self.category,
			retail_price=Decimal('25.00'),
			wholesale_price=Decimal('20.00'),
			cost=Decimal('10.00')
		)
		self.sale = Sale.objects.create(
			storefront=self.storefront,
			user=self.user,
			total_amount=Decimal('0.00'),
			payment_type='CASH',
			status='COMPLETED',
			type='RETAIL',
			amount_due=Decimal('0.00'),
			discount_amount=Decimal('0.00'),
			tax_amount=Decimal('0.00'),
			receipt_number='RCP-12345'
		)

	def test_sale_item_tax_and_total_calculation(self):
		sale_item = SaleItem.objects.create(
			sale=self.sale,
			product=self.product,
			quantity=3,
			unit_price=Decimal('20.00'),
			discount_amount=Decimal('5.00'),
			tax_rate=Decimal('15.00'),
			total_price=Decimal('0.00')
		)
		sale_item.refresh_from_db()
		self.assertEqual(sale_item.unit_price, Decimal('20.00'))
		self.assertEqual(sale_item.base_amount, Decimal('55.00'))
		self.assertEqual(sale_item.tax_amount, Decimal('8.25'))
		self.assertEqual(sale_item.total_price, Decimal('63.25'))

		total = self.sale.calculate_total()
		self.assertEqual(total, Decimal('63.25'))
		self.assertEqual(self.sale.tax_amount, Decimal('8.25'))
