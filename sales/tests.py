from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import Business
from inventory.models import Category, Product, Stock, StockProduct, StoreFront, Warehouse
from .models import Sale, SaleItem


User = get_user_model()


class SaleItemTaxCalculationTest(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			email='cashier@example.com',
			password='testpass123',
			name='Cashier One'
		)
		self.business = Business.objects.create(
			owner=self.user,
			name='Test Business',
			tin='123456789',
			email='business@example.com',
			address='123 Test Street'
		)
		self.storefront = StoreFront.objects.create(
			user=self.user,
			name='POS Store',
			location='Main Street'
		)
		self.category = Category.objects.create(name='Beverages')
		self.product = Product.objects.create(
			business=self.business,
			name='Bottled Water',
			sku='WATER-001',
			category=self.category
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

		total = self.sale.calculate_totals()
		self.assertEqual(total, Decimal('63.25'))
		self.sale.refresh_from_db()
		self.assertEqual(self.sale.sale_items.first().tax_amount, Decimal('8.25'))

	def test_sale_item_profit_margin_calculation(self):
		# Create warehouse and stock for cost tracking
		warehouse = Warehouse.objects.create(
			name='Test Warehouse',
			location='Test Location',
			manager=self.user
		)
		stock = Stock.objects.create(
			business=self.business,
			arrival_date='2025-10-01'
		)
		stock_product = StockProduct.objects.create(
			stock=stock,
			warehouse=warehouse,
			product=self.product,
			quantity=100,
			unit_cost=Decimal('10.00'),  # Cost per unit
			retail_price=Decimal('20.00')
		)

		# Create sale item with stock reference
		sale_item = SaleItem.objects.create(
			sale=self.sale,
			product=self.product,
			stock=stock,
			stock_product=stock_product,
			quantity=2,
			unit_price=Decimal('20.00'),
			total_price=Decimal('40.00')
		)

		# Test profit calculations
		self.assertEqual(sale_item.unit_cost, Decimal('10.00'))  # Cost from stock
		self.assertEqual(sale_item.profit_amount, Decimal('10.00'))  # 20.00 - 10.00
		self.assertEqual(sale_item.profit_margin, Decimal('50.00'))  # (10.00 / 20.00) * 100
		self.assertEqual(sale_item.total_profit_amount, Decimal('20.00'))  # 10.00 * 2

	def test_sale_item_profit_margin_fallback_to_product_cost(self):
		# Set up product with latest cost (no stock reference)
		warehouse = Warehouse.objects.create(
			name='Test Warehouse',
			location='Test Location',
			manager=self.user
		)
		stock = Stock.objects.create(
			business=self.business,
			arrival_date='2025-10-01'
		)
		StockProduct.objects.create(
			stock=stock,
			warehouse=warehouse,
			product=self.product,
			quantity=100,
			unit_cost=Decimal('8.00'),  # This will be the latest cost
			retail_price=Decimal('20.00')
		)

		# Create sale item without stock reference
		sale_item = SaleItem.objects.create(
			sale=self.sale,
			product=self.product,
			quantity=1,
			unit_price=Decimal('25.00'),
			total_price=Decimal('25.00')
		)

		# Test profit calculations using fallback cost
		self.assertEqual(sale_item.unit_cost, Decimal('8.00'))  # Latest cost from product
		self.assertEqual(sale_item.profit_amount, Decimal('17.00'))  # 25.00 - 8.00
		self.assertEqual(sale_item.profit_margin, Decimal('68.00'))  # (17.00 / 25.00) * 100
