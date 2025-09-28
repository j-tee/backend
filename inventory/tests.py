import uuid
from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone

from django.contrib.auth import get_user_model

from .models import (
	Warehouse, StoreFront, BusinessWarehouse, BusinessStoreFront,
	StoreFrontEmployee, WarehouseEmployee, Category, Product, Stock
)
from accounts.models import Business, BusinessMembership

User = get_user_model()


class StockModelTest(TestCase):
	def setUp(self):
		self.category = Category.objects.create(name='Electronics')
		self.product = Product.objects.create(
			name='Metallo Cable',
			sku='MET-001',
			category=self.category,
			retail_price=Decimal('10.00'),
			wholesale_price=Decimal('8.00'),
			cost=Decimal('5.00')
		)
		self.warehouse = Warehouse.objects.create(name='Expiry Warehouse', location='Zone A')

	def test_expiry_date_persists(self):
		stock_item = Stock.objects.create(
			warehouse=self.warehouse,
			product=self.product,
			quantity=100,
			expiry_date=date(2025, 10, 30),
			supplier='Cable Imports Ltd.',
			reference_code='STK-EXP-001',
			arrival_date=timezone.now().date()
		)
		self.assertEqual(stock_item.expiry_date.isoformat(), '2025-10-30')

	def test_allows_multiple_expiries_for_same_batch_product(self):
		Stock.objects.create(
			warehouse=self.warehouse,
			product=self.product,
			quantity=50,
			expiry_date=date(2025, 10, 30),
			supplier='Cable Imports Ltd.',
			reference_code='STK-EXP-001',
			arrival_date=timezone.now().date()
		)
		Stock.objects.create(
			warehouse=self.warehouse,
			product=self.product,
			quantity=40,
			expiry_date=date(2025, 11, 20),
			supplier='Cable Imports Ltd.',
			reference_code='STK-EXP-002',
			arrival_date=timezone.now().date()
		)
		self.assertEqual(
			Stock.objects.filter(warehouse=self.warehouse, product=self.product).count(),
			2
		)

	def test_landed_cost_computation(self):
		stock_item = Stock.objects.create(
			warehouse=self.warehouse,
			product=self.product,
			quantity=80,
			unit_cost=Decimal('12.50'),
			unit_tax_rate=Decimal('10.00'),
			unit_additional_cost=Decimal('1.50'),
			supplier='Cable Imports Ltd.',
			reference_code='STK-COST-001',
			arrival_date=timezone.now().date()
		)
		stock_item.refresh_from_db()
		self.assertEqual(stock_item.unit_tax_amount, Decimal('1.25'))
		self.assertEqual(stock_item.landed_unit_cost, Decimal('15.25'))
		self.assertEqual(stock_item.total_tax_amount, Decimal('100.00'))
		self.assertEqual(stock_item.total_landed_cost, Decimal('1220.00'))

class BusinessTestMixin:
	"""Utility mixin to create businesses for tests."""

	def create_business(self, owner=None, **overrides):
		suffix = uuid.uuid4().hex[:6]
		if owner is None:
			owner = User.objects.create_user(
				email=f'owner-{suffix}@example.com',
				password='testpass123',
				name=f'Owner {suffix}'
			)
		business_defaults = {
			'name': overrides.get('name', f'Test Business {suffix}'),
			'tin': overrides.get('tin', f'TIN{suffix.upper()}'),
			'email': overrides.get('email', f'biz{suffix}@example.com'),
			'address': overrides.get('address', '123 Business Rd'),
			'website': overrides.get('website', 'https://example.com'),
			'phone_numbers': overrides.get('phone_numbers', ['+1234567890']),
			'social_handles': overrides.get('social_handles', {'instagram': '@testbiz'}),
		}
		business = Business.objects.create(owner=owner, **business_defaults)
		return owner, business


class WarehouseModelTest(BusinessTestMixin, TestCase):
	def setUp(self):
		_, self.business = self.create_business(name='Warehouse Biz', tin='TIN-WARE-001')

	def test_warehouse_creation(self):
		warehouse = Warehouse.objects.create(
			name='Main Warehouse',
			location='Industrial Park'
		)
		BusinessWarehouse.objects.create(business=self.business, warehouse=warehouse)

		self.assertEqual(warehouse.name, 'Main Warehouse')
		self.assertEqual(warehouse.location, 'Industrial Park')
		self.assertEqual(warehouse.business_link.business, self.business)


class StoreFrontModelTest(BusinessTestMixin, TestCase):
	def setUp(self):
		self.owner = User.objects.create_user(
			email='store-owner@example.com',
			password='testpass123',
			name='Store Owner'
		)
		_, self.business = self.create_business(owner=self.owner, name='Store Biz', tin='TIN-STORE-001')

	def test_storefront_association(self):
		storefront = StoreFront.objects.create(
			user=self.owner,
			name='Downtown Store',
			location='Downtown Avenue'
		)
		BusinessStoreFront.objects.create(business=self.business, storefront=storefront)

		self.assertEqual(storefront.name, 'Downtown Store')
		self.assertEqual(storefront.business_link.business, self.business)


class BusinessWarehouseModelTest(BusinessTestMixin, TestCase):
	def test_unique_business_warehouse_link(self):
		_, business = self.create_business(name='Unique Biz', tin='TIN-UNIQUE-001')
		warehouse = Warehouse.objects.create(name='North Warehouse', location='North Side')
		BusinessWarehouse.objects.create(business=business, warehouse=warehouse)

		with self.assertRaises(Exception):
			BusinessWarehouse.objects.create(business=business, warehouse=warehouse)


class BusinessStoreFrontModelTest(BusinessTestMixin, TestCase):
	def test_unique_business_storefront_link(self):
		owner, business = self.create_business(name='Retail Biz', tin='TIN-RETAIL-001')
		storefront = StoreFront.objects.create(user=owner, name='Mall Store', location='City Mall')
		BusinessStoreFront.objects.create(business=business, storefront=storefront)

		with self.assertRaises(Exception):
			BusinessStoreFront.objects.create(business=business, storefront=storefront)


class StoreFrontEmployeeModelTest(BusinessTestMixin, TestCase):
	def setUp(self):
		self.owner, self.business = self.create_business(name='Staff Biz', tin='TIN-STAF-001')
		self.storefront = StoreFront.objects.create(user=self.owner, name='Staff Store', location='Central Plaza')
		BusinessStoreFront.objects.create(business=self.business, storefront=self.storefront)
		self.employee = User.objects.create_user(
			email='employee@example.com',
			password='pass12345',
			name='Store Employee'
		)
		BusinessMembership.objects.create(
			business=self.business,
			user=self.employee,
			role=BusinessMembership.STAFF,
			is_admin=False
		)

	def test_storefront_employee_assignment(self):
		assignment = StoreFrontEmployee.objects.create(
			business=self.business,
			storefront=self.storefront,
			user=self.employee,
			role=BusinessMembership.MANAGER
		)

		self.assertEqual(assignment.business, self.business)
		self.assertEqual(assignment.storefront, self.storefront)
		self.assertEqual(assignment.user, self.employee)
		self.assertEqual(assignment.role, BusinessMembership.MANAGER)

	def test_invalid_storefront_assignment_without_membership(self):
		outsider = User.objects.create_user(
			email='outsider@example.com',
			password='pass12345',
			name='Outsider'
		)

		with self.assertRaises(ValidationError):
			StoreFrontEmployee.objects.create(
				business=self.business,
				storefront=self.storefront,
				user=outsider
			)


class WarehouseEmployeeModelTest(BusinessTestMixin, TestCase):
	def setUp(self):
		self.owner, self.business = self.create_business(name='Warehouse Staff Biz', tin='TIN-WSTAFF-001')
		self.warehouse = Warehouse.objects.create(name='Central Warehouse', location='Industrial Hub')
		BusinessWarehouse.objects.create(business=self.business, warehouse=self.warehouse)
		self.employee = User.objects.create_user(
			email='warehouse-employee@example.com',
			password='pass12345',
			name='Warehouse Employee'
		)
		BusinessMembership.objects.create(
			business=self.business,
			user=self.employee,
			role=BusinessMembership.STAFF,
			is_admin=False
		)

	def test_warehouse_employee_assignment(self):
		assignment = WarehouseEmployee.objects.create(
			business=self.business,
			warehouse=self.warehouse,
			user=self.employee,
			role=BusinessMembership.STAFF
		)

		self.assertEqual(assignment.business, self.business)
		self.assertEqual(assignment.warehouse, self.warehouse)
		self.assertEqual(assignment.user, self.employee)

	def test_invalid_warehouse_assignment_without_link(self):
		other_business = self.create_business(name='Other Biz', tin='TIN-OTHER-001')[1]
		with self.assertRaises(ValidationError):
			WarehouseEmployee.objects.create(
				business=other_business,
				warehouse=self.warehouse,
				user=self.employee
			)
