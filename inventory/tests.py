import uuid
from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model

from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.authtoken.models import Token

from .models import (
	Warehouse, StoreFront, BusinessWarehouse, BusinessStoreFront,
	StoreFrontEmployee, WarehouseEmployee, Category, Product, Supplier, Stock, StockProduct,
	Inventory, StoreFrontInventory, Transfer, TransferRequest
)
from accounts.models import Business, BusinessMembership

User = get_user_model()


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


class StockProductProfitTest(BusinessTestMixin, TestCase):
	"""Test profit calculations for StockProduct with different scenarios"""

	def setUp(self):
		self.owner, self.business = self.create_business(name='Profit Test Biz', tin='TIN-PROFIT-001')
		self.category = Category.objects.create(name='Electronics')
		self.product = Product.objects.create(
			business=self.business,
			name='Test Laptop',
			sku='LAPTOP-001',
			category=self.category
		)
		self.warehouse = Warehouse.objects.create(name='Main Warehouse', location='Downtown')
		BusinessWarehouse.objects.create(business=self.business, warehouse=self.warehouse)
		self.stock = Stock.objects.create(warehouse=self.warehouse, description='Laptop stock')
		self.supplier = Supplier.objects.create(
			business=self.business,
			name='Tech Supplier Inc',
			email='contact@techsupplier.com'
		)

	def test_expected_profit_scenarios_basic(self):
		"""Test basic expected profit scenarios for retail and wholesale"""
		stock_product = StockProduct.objects.create(
			stock=self.stock,
			product=self.product,
			supplier=self.supplier,
			quantity=100,
			unit_cost=Decimal('800.00'),
			unit_tax_rate=Decimal('10.00'),  # 10% tax = $80
			unit_tax_amount=Decimal('80.00'),
			unit_additional_cost=Decimal('20.00'),  # Total landed cost = 800 + 80 + 20 = 900
			retail_price=Decimal('1200.00'),
			wholesale_price=Decimal('1000.00')
		)

		# Test retail-only scenario
		retail_scenario = stock_product.get_expected_profit_scenarios()['retail_only']
		self.assertEqual(retail_scenario['scenario'], 'retail_only')
		self.assertEqual(retail_scenario['retail_percentage'], Decimal('100.00'))
		self.assertEqual(retail_scenario['wholesale_percentage'], Decimal('0.00'))
		self.assertEqual(retail_scenario['avg_selling_price'], Decimal('1200.00'))
		self.assertEqual(retail_scenario['profit_per_unit'], Decimal('300.00'))  # 1200 - 900
		self.assertEqual(retail_scenario['profit_margin'], Decimal('25.00'))  # (300/1200)*100
		self.assertEqual(retail_scenario['total_profit'], Decimal('30000.00'))  # 300 * 100

		# Test wholesale-only scenario
		wholesale_scenario = stock_product.get_expected_profit_scenarios()['wholesale_only']
		self.assertEqual(wholesale_scenario['scenario'], 'wholesale_only')
		self.assertEqual(wholesale_scenario['retail_percentage'], Decimal('0.00'))
		self.assertEqual(wholesale_scenario['wholesale_percentage'], Decimal('100.00'))
		self.assertEqual(wholesale_scenario['avg_selling_price'], Decimal('1000.00'))
		self.assertEqual(wholesale_scenario['profit_per_unit'], Decimal('100.00'))  # 1000 - 900
		self.assertEqual(wholesale_scenario['profit_margin'], Decimal('10.00'))  # (100/1000)*100
		self.assertEqual(wholesale_scenario['total_profit'], Decimal('10000.00'))  # 100 * 100

	def test_expected_profit_scenarios_mixed(self):
		"""Test mixed retail/wholesale scenarios"""
		stock_product = StockProduct.objects.create(
			stock=self.stock,
			product=self.product,
			supplier=self.supplier,
			quantity=100,
			unit_cost=Decimal('800.00'),
			unit_tax_rate=Decimal('10.00'),
			unit_tax_amount=Decimal('80.00'),
			unit_additional_cost=Decimal('20.00'),
			retail_price=Decimal('1200.00'),
			wholesale_price=Decimal('1000.00')
		)

		scenarios = stock_product.get_expected_profit_scenarios()['mixed_scenarios']
		
		# Test 50/50 split
		fifty_fifty = next(s for s in scenarios if s['scenario'] == 'mixed_50_50')
		self.assertEqual(fifty_fifty['retail_percentage'], Decimal('50.00'))
		self.assertEqual(fifty_fifty['wholesale_percentage'], Decimal('50.00'))
		self.assertEqual(fifty_fifty['retail_units'], Decimal('50.00'))
		self.assertEqual(fifty_fifty['wholesale_units'], Decimal('50.00'))
		
		# Average selling price: (1200*50 + 1000*50) / 100 = 1100
		self.assertEqual(fifty_fifty['avg_selling_price'], Decimal('1100.00'))
		
		# Total profit: (300*50) + (100*50) = 15000 + 5000 = 20000
		self.assertEqual(fifty_fifty['total_profit'], Decimal('20000.00'))
		
		# Average margin: (20000 / 110000) * 100 = 18.18%
		self.assertEqual(fifty_fifty['profit_margin'], Decimal('18.18'))

	def test_get_expected_profit_for_scenario(self):
		"""Test custom scenario calculation"""
		stock_product = StockProduct.objects.create(
			stock=self.stock,
			product=self.product,
			supplier=self.supplier,
			quantity=100,
			unit_cost=Decimal('800.00'),
			unit_tax_rate=Decimal('10.00'),
			unit_tax_amount=Decimal('80.00'),
			unit_additional_cost=Decimal('20.00'),
			retail_price=Decimal('1200.00'),
			wholesale_price=Decimal('1000.00')
		)

		# Test 70% retail, 30% wholesale
		scenario = stock_product.get_expected_profit_for_scenario(
			retail_percentage=Decimal('70.00'), 
			wholesale_percentage=Decimal('30.00')
		)
		
		self.assertEqual(scenario['retail_percentage'], Decimal('70.00'))
		self.assertEqual(scenario['wholesale_percentage'], Decimal('30.00'))
		self.assertEqual(scenario['retail_units'], Decimal('70.00'))
		self.assertEqual(scenario['wholesale_units'], Decimal('30.00'))
		self.assertEqual(scenario['avg_selling_price'], Decimal('1140.00'))  # (1200*70 + 1000*30) / 100
		self.assertEqual(scenario['total_profit'], Decimal('24000.00'))  # (300*70) + (100*30)
		self.assertEqual(scenario['profit_margin'], Decimal('21.05'))  # (24000 / 114000) * 100

	def test_get_expected_profit_for_scenario_invalid_percentages(self):
		"""Test that invalid percentages raise ValueError"""
		stock_product = StockProduct.objects.create(
			stock=self.stock,
			product=self.product,
			supplier=self.supplier,
			quantity=10,
			unit_cost=Decimal('100.00'),
			retail_price=Decimal('150.00'),
			wholesale_price=Decimal('120.00')
		)

		with self.assertRaises(ValueError):
			stock_product.get_expected_profit_for_scenario(
				retail_percentage=Decimal('60.00'), 
				wholesale_percentage=Decimal('50.00')  # 60 + 50 != 100
			)

	def test_product_expected_profit_summary_scenarios(self):
		"""Test Product.get_expected_profit_summary with different scenarios"""
		# Create multiple stock products for the same product
		sp1 = StockProduct.objects.create(
			stock=self.stock,
			product=self.product,
			supplier=self.supplier,
			quantity=50,
			unit_cost=Decimal('800.00'),
			unit_tax_rate=Decimal('10.00'),
			unit_tax_amount=Decimal('80.00'),
			unit_additional_cost=Decimal('20.00'),
			retail_price=Decimal('1200.00'),
			wholesale_price=Decimal('1000.00')
		)
		
		sp2 = StockProduct.objects.create(
			stock=self.stock,
			product=self.product,
			supplier=self.supplier,
			quantity=30,
			unit_cost=Decimal('750.00'),
			unit_tax_rate=Decimal('10.00'),
			unit_tax_amount=Decimal('75.00'),
			unit_additional_cost=Decimal('15.00'),
			retail_price=Decimal('1100.00'),
			wholesale_price=Decimal('950.00')
		)

		# Test retail-only summary (default)
		summary = self.product.get_expected_profit_summary()
		self.assertEqual(summary['total_quantity'], 80)
		self.assertEqual(summary['scenario'], '100.00% retail, 0.00% wholesale')
		self.assertEqual(summary['stock_products_count'], 2)
		
		# Expected profit: sp1: 300*50 = 15000, sp2: (1100-840)*30 = 7800, total = 22800
		self.assertEqual(summary['total_expected_profit'], Decimal('22800.00'))

		# Test wholesale-only summary
		wholesale_summary = self.product.get_expected_profit_summary(
			retail_percentage=Decimal('0.00'), 
			wholesale_percentage=Decimal('100.00')
		)
		self.assertEqual(wholesale_summary['scenario'], '0.00% retail, 100.00% wholesale')
		# Expected profit: sp1: 100*50 = 5000, sp2: (950-840)*30 = 3300, total = 8300
		self.assertEqual(wholesale_summary['total_expected_profit'], Decimal('8300.00'))

		# Test mixed scenario
		mixed_summary = self.product.get_expected_profit_summary(
			retail_percentage=Decimal('70.00'), 
			wholesale_percentage=Decimal('30.00')
		)
		self.assertEqual(mixed_summary['scenario'], '70.00% retail, 30.00% wholesale')
		# This should calculate weighted profits across both stock products


class ProfitProjectionAPITest(BusinessTestMixin, APITestCase):
	"""Test profit projection API endpoints"""

	def setUp(self):
		self.owner, self.business = self.create_business(name='Profit API Test Biz', tin='TIN-PROFIT-API-001')
		self.category = Category.objects.create(name='Electronics')
		self.product = Product.objects.create(
			business=self.business,
			name='Test Laptop',
			sku='LAPTOP-API-001',
			category=self.category
		)
		self.warehouse = Warehouse.objects.create(name='API Warehouse', location='API City')
		BusinessWarehouse.objects.create(business=self.business, warehouse=self.warehouse)
		self.stock = Stock.objects.create(warehouse=self.warehouse, description='API stock batch')
		self.supplier = Supplier.objects.create(
			business=self.business,
			name='API Supplier Inc',
			email='api@supplier.com'
		)

		# Create stock product
		self.stock_product = StockProduct.objects.create(
			stock=self.stock,
			product=self.product,
			supplier=self.supplier,
			quantity=100,
			unit_cost=Decimal('800.00'),
			unit_tax_rate=Decimal('10.00'),
			unit_tax_amount=Decimal('80.00'),
			unit_additional_cost=Decimal('20.00'),
			retail_price=Decimal('1200.00'),
			wholesale_price=Decimal('1000.00')
		)

		# Create user and token
		self.user = User.objects.create_user(
			email='api-test@example.com',
			password='testpass123',
			name='API Test User'
		)
		self.user.account_type = User.ACCOUNT_OWNER
		self.user.email_verified = True
		self.user.is_active = True
		self.user.save()

		BusinessMembership.objects.create(
			business=self.business,
			user=self.user,
			role=BusinessMembership.OWNER,
			is_admin=True
		)

		self.token = Token.objects.create(user=self.user)
		self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)

	def test_get_available_scenarios(self):
		"""Test getting list of available profit scenarios"""
		url = '/inventory/api/profit-projections/scenarios/'
		response = self.client.get(url)
		
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		scenarios = response.data['scenarios']
		
		# Should have 11 predefined scenarios
		self.assertEqual(len(scenarios), 11)
		
		# Check some specific scenarios
		retail_only = next(s for s in scenarios if s['id'] == 'retail_only')
		self.assertEqual(retail_only['name'], 'Retail Only')
		self.assertEqual(retail_only['retail_percentage'], 100.00)
		self.assertEqual(retail_only['wholesale_percentage'], 0.00)

		mixed_70_30 = next(s for s in scenarios if s['id'] == 'mixed_70_30')
		self.assertEqual(mixed_70_30['name'], '70% Retail, 30% Wholesale')
		self.assertEqual(mixed_70_30['retail_percentage'], 70.00)
		self.assertEqual(mixed_70_30['wholesale_percentage'], 30.00)

	def test_stock_product_projection(self):
		"""Test profit projection for individual stock product"""
		url = '/inventory/api/profit-projections/stock-product/'
		data = {
			'stock_product_id': str(self.stock_product.id),
			'retail_percentage': 70.00,
			'wholesale_percentage': 30.00
		}
		
		response = self.client.post(url, data, format='json')
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		
		result = response.data
		self.assertEqual(result['stock_product_id'], str(self.stock_product.id))
		self.assertEqual(result['product_name'], 'Test Laptop')
		self.assertEqual(result['quantity'], 100)
		
		# Check requested scenario
		requested = result['requested_scenario']
		self.assertEqual(requested['retail_percentage'], Decimal('70.00'))
		self.assertEqual(requested['wholesale_percentage'], Decimal('30.00'))
		self.assertEqual(requested['retail_units'], Decimal('70.00'))
		self.assertEqual(requested['wholesale_units'], Decimal('30.00'))
		self.assertEqual(requested['avg_selling_price'], Decimal('1140.000'))  # (1200*70 + 1000*30) / 100
		self.assertEqual(requested['total_profit'], Decimal('24000.000'))  # (300*70) + (100*30)
		
		# Check retail-only scenario is included
		retail_only = result['retail_only']
		self.assertEqual(retail_only['scenario'], 'retail_only')
		self.assertEqual(retail_only['total_profit'], Decimal('30000.00'))
		
		# Check mixed scenarios are included
		mixed_scenarios = result['mixed_scenarios']
		self.assertTrue(len(mixed_scenarios) > 0)
		mixed_50_50 = next(s for s in mixed_scenarios if s['scenario'] == 'mixed_50_50')
		self.assertEqual(mixed_50_50['retail_percentage'], Decimal('50.00'))

	def test_stock_product_projection_invalid_stock_product(self):
		"""Test profit projection with invalid stock product ID"""
		url = '/inventory/api/profit-projections/stock-product/'
		data = {
			'stock_product_id': '00000000-0000-0000-0000-000000000000',  # Non-existent UUID
			'retail_percentage': 50.00,
			'wholesale_percentage': 50.00
		}
		
		response = self.client.post(url, data, format='json')
		self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
		self.assertIn('error', response.data)

	def test_stock_product_projection_invalid_percentages(self):
		"""Test profit projection with invalid percentages"""
		url = '/inventory/api/profit-projections/stock-product/'
		data = {
			'stock_product_id': str(self.stock_product.id),
			'retail_percentage': 60.00,
			'wholesale_percentage': 50.00  # 60 + 50 != 100
		}
		
		response = self.client.post(url, data, format='json')
		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

	def test_product_projection(self):
		"""Test profit projection for product (across all stock products)"""
		url = '/inventory/api/profit-projections/product/'
		data = {
			'product_id': str(self.product.id),
			'retail_percentage': 80.00,
			'wholesale_percentage': 20.00
		}
		
		response = self.client.post(url, data, format='json')
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		
		result = response.data
		self.assertEqual(result['product_id'], str(self.product.id))
		self.assertEqual(result['product_name'], 'Test Laptop')
		self.assertEqual(result['total_quantity'], 100)
		self.assertEqual(result['stock_products_count'], 1)
		
		# Check requested scenario
		requested = result['requested_scenario']
		self.assertEqual(requested['scenario'], '80.00% retail, 20.00% wholesale')
		
		# Check comparison scenarios
		retail_only = result['retail_only']
		self.assertEqual(retail_only['scenario'], '100.00% retail, 0.00% wholesale')
		
		wholesale_only = result['wholesale_only']
		self.assertEqual(wholesale_only['scenario'], '0.00% retail, 100.00% wholesale')

	def test_bulk_projection(self):
		"""Test bulk profit projection for multiple stock products"""
		url = '/inventory/api/profit-projections/bulk/'
		data = {
			'projections': [
				{
					'stock_product_id': str(self.stock_product.id),
					'retail_percentage': 100.00,
					'wholesale_percentage': 0.00
				},
				{
					'stock_product_id': str(self.stock_product.id),
					'retail_percentage': 0.00,
					'wholesale_percentage': 100.00
				}
			]
		}
		
		response = self.client.post(url, data, format='json')
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		
		result = response.data
		projections = result['projections']
		self.assertEqual(len(projections), 2)
		
		# Check first projection (retail only)
		projection1 = projections[0]
		self.assertEqual(projection1['requested_scenario']['retail_percentage'], Decimal('100.00'))
		self.assertEqual(projection1['requested_scenario']['total_profit'], Decimal('30000.00'))
		
		# Check second projection (wholesale only)
		projection2 = projections[1]
		self.assertEqual(projection2['requested_scenario']['wholesale_percentage'], Decimal('100.00'))
		self.assertEqual(projection2['requested_scenario']['total_profit'], Decimal('10000.00'))

	def test_bulk_projection_invalid_data(self):
		"""Test bulk projection with invalid data"""
		url = '/inventory/api/profit-projections/bulk/'
		data = {
			'projections': []  # Empty list
		}
		
		response = self.client.post(url, data, format='json')
		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

	def test_unauthorized_access(self):
		"""Test that unauthorized users cannot access profit projections"""
		# Create another user not belonging to the business
		other_user = User.objects.create_user(
			email='other@example.com',
			password='testpass123',
			name='Other User'
		)
		other_token = Token.objects.create(user=other_user)
		self.client.credentials(HTTP_AUTHORIZATION='Token ' + other_token.key)
		
		url = '/inventory/api/profit-projections/stock-product/'
		data = {
			'stock_product_id': str(self.stock_product.id),
			'retail_percentage': 50.00,
			'wholesale_percentage': 50.00
		}
		
		response = self.client.post(url, data, format='json')
		self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class StockModelTest(BusinessTestMixin, TestCase):
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


class OwnerStorefrontWarehouseAPITest(BusinessTestMixin, APITestCase):
	def setUp(self):
		self.owner = User.objects.create_user(
			email='api-owner@example.com',
			password='testpass123',
			name='API Owner'
		)
		self.owner.account_type = User.ACCOUNT_OWNER
		self.owner.email_verified = True
		self.owner.is_active = True
		self.owner.save(update_fields=['account_type', 'email_verified', 'is_active'])

		_, self.business = self.create_business(owner=self.owner, name='API Biz', tin='TIN-API-001')
		self.token = Token.objects.create(user=self.owner)
		self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
		self.workspace_url = '/inventory/api/owner/workspace/'

	def test_owner_can_create_storefront_and_warehouse(self):
		response = self.client.get(self.workspace_url)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['storefronts'], [])
		self.assertEqual(response.data['warehouses'], [])

		storefront_payload = {
			'name': 'Flagship Store',
			'location': 'Main Street'
		}
		store_response = self.client.post('/inventory/api/storefronts/', storefront_payload, format='json')
		self.assertEqual(store_response.status_code, status.HTTP_201_CREATED)
		self.assertTrue(
			BusinessStoreFront.objects.filter(business=self.business, storefront__name='Flagship Store').exists()
		)

		warehouse_payload = {
			'name': 'Primary Warehouse',
			'location': 'Industrial Estate'
		}
		warehouse_response = self.client.post('/inventory/api/warehouses/', warehouse_payload, format='json')
		self.assertEqual(warehouse_response.status_code, status.HTTP_201_CREATED)
		self.assertTrue(
			BusinessWarehouse.objects.filter(business=self.business, warehouse__name='Primary Warehouse').exists()
		)

		workspace_response = self.client.get(self.workspace_url)
		self.assertEqual(workspace_response.status_code, status.HTTP_200_OK)
		self.assertEqual(len(workspace_response.data['storefronts']), 1)
		self.assertEqual(len(workspace_response.data['warehouses']), 1)
		self.assertEqual(workspace_response.data['business']['storefront_count'], 1)
		self.assertEqual(workspace_response.data['business']['warehouse_count'], 1)



class BusinessScopedVisibilityAPITest(BusinessTestMixin, APITestCase):
	def setUp(self):
		self.owner1, self.business1 = self.create_business(
			name='DataLogique Systems',
			tin='TIN-DLS-001',
		)
		self.owner1.email_verified = True
		self.owner1.is_active = True
		self.owner1.save(update_fields=['email_verified', 'is_active'])

		self.owner2, self.business2 = self.create_business(
			name='Other Biz',
			tin='TIN-OTH-001',
		)
		self.owner2.email_verified = True
		self.owner2.is_active = True
		self.owner2.save(update_fields=['email_verified', 'is_active'])

		self.business = self.business1

		# Storefronts and warehouses for business 1
		self.storefront1 = StoreFront.objects.create(
			user=self.owner1,
			name='DataLogique Store',
			location='Accra',
			manager=self.owner1,
		)
		BusinessStoreFront.objects.create(business=self.business1, storefront=self.storefront1)

		self.warehouse1 = Warehouse.objects.create(
			name='DataLogique Warehouse',
			location='Tema',
			manager=self.owner1,
		)
		BusinessWarehouse.objects.create(business=self.business1, warehouse=self.warehouse1)

		# Storefronts and warehouses for business 2
		storefront2 = StoreFront.objects.create(
			user=self.owner2,
			name='Other Biz Store',
			location='Takoradi',
			manager=self.owner2,
		)
		BusinessStoreFront.objects.create(business=self.business2, storefront=storefront2)

		warehouse2 = Warehouse.objects.create(
			name='Other Biz Warehouse',
			location='Kumasi',
			manager=self.owner2,
		)
		BusinessWarehouse.objects.create(business=self.business2, warehouse=warehouse2)

		self.employee = User.objects.create_user(
			email='employee-visibility@example.com',
			password='employeeVisibility123',
			name='Visibility Tester',
			account_type=User.ACCOUNT_EMPLOYEE,
		)
		self.employee.email_verified = True
		self.employee.is_active = True
		self.employee.save(update_fields=['email_verified', 'is_active'])

		BusinessMembership.objects.create(
			business=self.business1,
			user=self.employee,
			role=BusinessMembership.STAFF,
			is_admin=False,
			is_active=True,
		)

		self.token = Token.objects.create(user=self.employee)
		self.owner_token = Token.objects.create(user=self.owner1)
		self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)

	def _get_results(self, response):
		data = response.data
		if isinstance(data, dict) and 'results' in data:
			return data['results']
		return data

	def test_business_storefronts_scoped_to_user(self):
		response = self.client.get('/inventory/api/business-storefronts/')
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		storefront_names = {item['storefront_name'] for item in response.data['results']}
		self.assertEqual(storefront_names, {'DataLogique Store'})

	def test_business_warehouses_scoped_to_user(self):
		response = self.client.get('/inventory/api/business-warehouses/')
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		warehouse_names = {item['warehouse_name'] for item in response.data['results']}
		self.assertEqual(warehouse_names, {'DataLogique Warehouse'})

	def test_employee_business_filter_respects_scope_for_unassigned_business(self):
		response = self.client.get(
			'/inventory/api/warehouses/',
			{'business': str(self.business2.id)}
		)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(self._get_results(response), [])

		storefront_response = self.client.get(
			'/inventory/api/storefronts/',
			{'business': str(self.business2.id)}
		)
		self.assertEqual(storefront_response.status_code, status.HTTP_200_OK)
		self.assertEqual(self._get_results(storefront_response), [])

	def test_employee_can_filter_locations_when_in_multiple_businesses(self):
		BusinessMembership.objects.create(
			business=self.business2,
			user=self.employee,
			role=BusinessMembership.STAFF,
			is_admin=False,
			is_active=True,
		)

		warehouse_response = self.client.get('/inventory/api/warehouses/')
		self.assertEqual(warehouse_response.status_code, status.HTTP_200_OK)
		warehouse_names = {item['name'] for item in self._get_results(warehouse_response)}
		self.assertEqual(warehouse_names, {'DataLogique Warehouse', 'Other Biz Warehouse'})

		warehouse_filtered = self.client.get(
			'/inventory/api/warehouses/',
			{'business': str(self.business1.id)}
		)
		self.assertEqual(warehouse_filtered.status_code, status.HTTP_200_OK)
		warehouse_filtered_names = {item['name'] for item in self._get_results(warehouse_filtered)}
		self.assertEqual(warehouse_filtered_names, {'DataLogique Warehouse'})

		warehouse_filtered_alias = self.client.get(
			'/inventory/api/warehouses/',
			{'business_id': str(self.business2.id)}
		)
		self.assertEqual(warehouse_filtered_alias.status_code, status.HTTP_200_OK)
		warehouse_filtered_alias_names = {item['name'] for item in self._get_results(warehouse_filtered_alias)}
		self.assertEqual(warehouse_filtered_alias_names, {'Other Biz Warehouse'})

		storefront_response = self.client.get('/inventory/api/storefronts/')
		self.assertEqual(storefront_response.status_code, status.HTTP_200_OK)
		storefront_names = {item['name'] for item in self._get_results(storefront_response)}
		self.assertEqual(storefront_names, {'DataLogique Store', 'Other Biz Store'})

		storefront_filtered = self.client.get(
			'/inventory/api/storefronts/',
			{'business': str(self.business1.id)}
		)
		self.assertEqual(storefront_filtered.status_code, status.HTTP_200_OK)
		storefront_filtered_names = {item['name'] for item in self._get_results(storefront_filtered)}
		self.assertEqual(storefront_filtered_names, {'DataLogique Store'})

		storefront_filtered_alias = self.client.get(
			'/inventory/api/storefronts/',
			{'business_id': str(self.business2.id)}
		)
		self.assertEqual(storefront_filtered_alias.status_code, status.HTTP_200_OK)
		storefront_filtered_alias_names = {item['name'] for item in self._get_results(storefront_filtered_alias)}
		self.assertEqual(storefront_filtered_alias_names, {'Other Biz Store'})

	def test_business_filter_requires_valid_uuid(self):
		response = self.client.get('/inventory/api/warehouses/', {'business': 'not-a-uuid'})
		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn('business', response.data)

		storefront_response = self.client.get('/inventory/api/storefronts/', {'business': 'not-a-uuid'})
		self.assertEqual(storefront_response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn('business', storefront_response.data)
	def test_owner_can_update_and_delete_storefront(self):
		self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.owner_token.key)
		store_response = self.client.post(
			'/inventory/api/storefronts/',
			{'name': 'Popup Store', 'location': 'Old Town'},
			format='json'
		)
		self.assertEqual(store_response.status_code, status.HTTP_201_CREATED)
		storefront_id = store_response.data['id']

		update_response = self.client.patch(
			f'/inventory/api/storefronts/{storefront_id}/',
			{'name': 'Renovated Store', 'location': 'New Town'},
			format='json'
		)
		self.assertEqual(update_response.status_code, status.HTTP_200_OK)
		self.assertEqual(update_response.data['name'], 'Renovated Store')
		self.assertEqual(update_response.data['location'], 'New Town')

		delete_response = self.client.delete(f'/inventory/api/storefronts/{storefront_id}/')
		self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
		self.assertFalse(StoreFront.objects.filter(id=storefront_id).exists())
		self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)

	def test_owner_can_update_and_delete_warehouse(self):
		self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.owner_token.key)
		warehouse_response = self.client.post(
			'/inventory/api/warehouses/',
			{'name': 'Secondary Warehouse', 'location': 'Zone 3'},
			format='json'
		)
		self.assertEqual(warehouse_response.status_code, status.HTTP_201_CREATED)
		warehouse_id = warehouse_response.data['id']

		update_response = self.client.patch(
			f'/inventory/api/warehouses/{warehouse_id}/',
			{'name': 'Updated Warehouse', 'location': 'Zone 5'},
			format='json'
		)
		self.assertEqual(update_response.status_code, status.HTTP_200_OK)
		self.assertEqual(update_response.data['name'], 'Updated Warehouse')
		self.assertEqual(update_response.data['location'], 'Zone 5')

		delete_response = self.client.delete(f'/inventory/api/warehouses/{warehouse_id}/')
		self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
		self.assertFalse(Warehouse.objects.filter(id=warehouse_id).exists())
		self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)

	def test_employee_cannot_create_storefront(self):
		employee = User.objects.create_user(
			email='emp@example.com',
			password='pass12345',
			name='Employee User',
			account_type=User.ACCOUNT_EMPLOYEE
		)
		employee.email_verified = True
		employee.is_active = True
		employee.save(update_fields=['email_verified', 'is_active'])

		BusinessMembership.objects.create(
			business=self.business1,
			user=employee,
			role=BusinessMembership.STAFF,
			is_admin=False
		)

		employee_token = Token.objects.create(user=employee)
		self.client.credentials(HTTP_AUTHORIZATION='Token ' + employee_token.key)

		response = self.client.post(
			'/inventory/api/storefronts/',
			{'name': 'Blocked Store', 'location': 'Hidden'},
			format='json'
		)
		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

		self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)


class BusinessMembershipPlatformRoleAPITest(BusinessTestMixin, APITestCase):
	def setUp(self):
		self.owner = User.objects.create_user(
			email='owner-platform@example.com',
			password='testpass123',
			name='Platform Owner'
		)
		self.owner.account_type = User.ACCOUNT_OWNER
		self.owner.email_verified = True
		self.owner.is_active = True
		self.owner.save(update_fields=['account_type', 'email_verified', 'is_active'])

		_, self.business = self.create_business(owner=self.owner, name='Platform Biz', tin='TIN-PLATFORM-001')

		self.employee = User.objects.create_user(
			email='platform-employee@example.com',
			password='employee123',
			name='Platform Employee'
		)
		self.employee.account_type = User.ACCOUNT_EMPLOYEE
		self.employee.email_verified = True
		self.employee.is_active = True
		self.employee.save(update_fields=['account_type', 'email_verified', 'is_active'])

		self.membership = BusinessMembership.objects.create(
			business=self.business,
			user=self.employee,
			role=BusinessMembership.STAFF,
			is_admin=False,
		)

		self.owner_token = Token.objects.create(user=self.owner)

		self.super_admin = User.objects.create_user(
			email='super-admin@example.com',
			password='superpass123',
			name='Super Admin'
		)
		self.super_admin.platform_role = User.PLATFORM_SUPER_ADMIN
		self.super_admin.email_verified = True
		self.super_admin.is_active = True
		self.super_admin.save(update_fields=['platform_role', 'email_verified', 'is_active'])
		self.super_token = Token.objects.create(user=self.super_admin)

		self.url = f'/inventory/api/memberships/{self.membership.id}/'

	def test_owner_cannot_assign_platform_role(self):
		self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.owner_token.key)
		response = self.client.patch(
			self.url,
			{'platform_role': User.PLATFORM_SAAS_STAFF},
			format='json'
		)
		self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
		self.membership.user.refresh_from_db()
		self.assertEqual(self.membership.user.platform_role, User.PLATFORM_NONE)

	def test_platform_super_admin_can_assign_platform_role(self):
		self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.super_token.key)
		response = self.client.patch(
			self.url,
			{'platform_role': User.PLATFORM_SAAS_ADMIN},
			format='json'
		)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.membership.user.refresh_from_db()
		self.assertEqual(self.membership.user.platform_role, User.PLATFORM_SAAS_ADMIN)
		self.assertIn('role_matrix', response.data)
		self.assertEqual(response.data['role_matrix']['platform']['role'], User.PLATFORM_SAAS_ADMIN)
		self.assertEqual(response.data['user']['platform_role'], User.PLATFORM_SAAS_ADMIN)

	def test_platform_super_admin_can_clear_platform_role(self):
		self.membership.user.platform_role = User.PLATFORM_SAAS_STAFF
		self.membership.user.save(update_fields=['platform_role', 'updated_at'])
		self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.super_token.key)
		response = self.client.patch(
			self.url,
			{'platform_role': User.PLATFORM_NONE},
			format='json'
		)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.membership.user.refresh_from_db()
		self.assertEqual(self.membership.user.platform_role, User.PLATFORM_NONE)


class TransferAvailabilityValidationTest(BusinessTestMixin, APITestCase):
	def setUp(self):
		self.owner, self.business = self.create_business()
		self.owner.account_type = User.ACCOUNT_OWNER
		self.owner.email_verified = True
		self.owner.is_active = True
		self.owner.save(update_fields=['account_type', 'email_verified', 'is_active'])

		BusinessMembership.objects.get_or_create(
			business=self.business,
			user=self.owner,
			defaults={'role': BusinessMembership.OWNER, 'is_admin': True}
		)

		self.category = Category.objects.create(name=f'Availability {uuid.uuid4().hex[:8]}')
		self.product = Product.objects.create(
			business=self.business,
			name='Availability Widget',
			sku=f'AVL-{uuid.uuid4().hex[:6]}',
			category=self.category
		)
		self.warehouse = Warehouse.objects.create(name='Source Warehouse', location='Test City')
		BusinessWarehouse.objects.create(business=self.business, warehouse=self.warehouse)

		self.storefront = StoreFront.objects.create(user=self.owner, name='Main Store', location='Downtown')
		BusinessStoreFront.objects.create(business=self.business, storefront=self.storefront)

		Inventory.objects.create(product=self.product, warehouse=self.warehouse, quantity=10)

		self.client.force_authenticate(self.owner)

	def test_stock_availability_endpoint_reports_on_hand_stock(self):
		response = self.client.get(
			'/inventory/api/stock/availability/',
			{'warehouse': str(self.warehouse.id), 'product': str(self.product.id), 'quantity': 5}
		)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['available_quantity'], 10)
		self.assertTrue(response.data['is_available'])
		self.assertEqual(response.data['requested_quantity'], 5)

	def test_transfer_creation_fails_when_stock_insufficient(self):
		payload = {
			'source_warehouse': str(self.warehouse.id),
			'destination_storefront': str(self.storefront.id),
			'notes': 'Request beyond available stock',
			'line_items': [
				{
					'product': str(self.product.id),
					'requested_quantity': 15
				}
			]
		}
		response = self.client.post('/inventory/api/transfers/', payload, format='json')
		self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn('line_items', response.data)
		line_errors = response.data['line_items']
		self.assertIn('0', line_errors)
		self.assertIn('Only', line_errors['0'])

	def test_transfer_creation_succeeds_when_stock_sufficient(self):
		payload = {
			'source_warehouse': str(self.warehouse.id),
			'destination_storefront': str(self.storefront.id),
			'notes': 'Within allocation',
			'line_items': [
				{
					'product': str(self.product.id),
					'requested_quantity': 4
				}
			]
		}
		response = self.client.post('/inventory/api/transfers/', payload, format='json')
		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(Transfer.objects.filter(business=self.business).count(), 1)
		self.assertEqual(response.data['line_items'][0]['requested_quantity'], 4)

		# Availability check should now reflect the remaining stock (still 10, reservation happens later in workflow)
		recheck = self.client.get(
			'/inventory/api/stock/availability/',
			{'warehouse': str(self.warehouse.id), 'product': str(self.product.id), 'quantity': 4}
		)
		self.assertEqual(recheck.status_code, status.HTTP_200_OK)
		self.assertTrue(recheck.data['is_available'])


class TransferRequestWorkflowAPITest(BusinessTestMixin, APITestCase):
	def setUp(self):
		self.owner, self.business = self.create_business()
		self.owner.account_type = User.ACCOUNT_OWNER
		self.owner.email_verified = True
		self.owner.is_active = True
		self.owner.save(update_fields=['account_type', 'email_verified', 'is_active'])

		BusinessMembership.objects.get_or_create(
			business=self.business,
			user=self.owner,
			defaults={'role': BusinessMembership.OWNER, 'is_admin': True}
		)

		self.staff = User.objects.create_user(
			email='staff-request@example.com',
			password='testpass123',
			name='Store Staff'
		)
		self.staff.account_type = User.ACCOUNT_EMPLOYEE
		self.staff.email_verified = True
		self.staff.is_active = True
		self.staff.save(update_fields=['account_type', 'email_verified', 'is_active'])

		BusinessMembership.objects.create(
			business=self.business,
			user=self.staff,
			role=BusinessMembership.STAFF,
			is_admin=False,
			is_active=True
		)

		self.category = Category.objects.create(name='Transfers Category')
		self.product = Product.objects.create(
			business=self.business,
			name='Transfer Gadget',
			sku='TRF-GDG-001',
			category=self.category
		)

		self.warehouse = Warehouse.objects.create(name='Transfer Warehouse', location='Warehouse District')
		BusinessWarehouse.objects.create(business=self.business, warehouse=self.warehouse)

		self.storefront = StoreFront.objects.create(user=self.owner, name='Transfer Storefront', location='Retail Park')
		BusinessStoreFront.objects.create(business=self.business, storefront=self.storefront)
		StoreFrontEmployee.objects.create(
			business=self.business,
			storefront=self.storefront,
			user=self.staff,
			role=BusinessMembership.STAFF,
			is_active=True
		)

		Inventory.objects.create(product=self.product, warehouse=self.warehouse, quantity=20)

		self.client.force_authenticate(self.staff)

	def _create_request(self, quantity=3):
		payload = {
			'storefront': str(self.storefront.id),
			'priority': TransferRequest.PRIORITY_HIGH,
			'notes': 'Need quick restock',
			'line_items': [
				{
					'product': str(self.product.id),
					'requested_quantity': quantity
				}
			]
		}
		response = self.client.post('/inventory/api/transfer-requests/', payload, format='json')
		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		return response.data

	def test_staff_can_create_transfer_request(self):
		request_data = self._create_request(quantity=5)
		self.assertEqual(request_data['status'], TransferRequest.STATUS_NEW)
		self.assertIsNone(request_data['linked_transfer'])
		self.assertEqual(len(request_data['line_items']), 1)
		self.assertEqual(request_data['line_items'][0]['requested_quantity'], 5)

	def test_transfer_creation_links_request_and_clones_line_items(self):
		request_data = self._create_request(quantity=4)
		request_id = request_data['id']

		self.client.force_authenticate(self.owner)
		transfer_payload = {
			'source_warehouse': str(self.warehouse.id),
			'destination_storefront': str(self.storefront.id),
			'request_id': request_id
		}
		transfer_response = self.client.post('/inventory/api/transfers/', transfer_payload, format='json')
		self.assertEqual(transfer_response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(transfer_response.data['request_id'], request_id)
		self.assertEqual(len(transfer_response.data['line_items']), 1)
		self.assertEqual(transfer_response.data['line_items'][0]['requested_quantity'], 4)

		transfer_request = TransferRequest.objects.get(id=request_id)
		self.assertEqual(transfer_request.status, TransferRequest.STATUS_ASSIGNED)
		self.assertEqual(str(transfer_request.linked_transfer_id), transfer_response.data['id'])
		self.assertEqual(transfer_request.linked_transfer_reference, transfer_response.data['reference'])

	def test_confirm_receipt_marks_transfer_and_request(self):
		request_data = self._create_request(quantity=2)
		request_id = request_data['id']

		self.client.force_authenticate(self.owner)
		transfer_payload = {
			'source_warehouse': str(self.warehouse.id),
			'destination_storefront': str(self.storefront.id),
			'request_id': request_id
		}
		transfer_response = self.client.post('/inventory/api/transfers/', transfer_payload, format='json')
		self.assertEqual(transfer_response.status_code, status.HTTP_201_CREATED)
		transfer_id = transfer_response.data['id']

		submit_response = self.client.post(f'/inventory/api/transfers/{transfer_id}/submit/')
		self.assertEqual(submit_response.status_code, status.HTTP_200_OK)
		approve_response = self.client.post(f'/inventory/api/transfers/{transfer_id}/approve/')
		self.assertEqual(approve_response.status_code, status.HTTP_200_OK)
		dispatch_response = self.client.post(f'/inventory/api/transfers/{transfer_id}/dispatch/')
		self.assertEqual(dispatch_response.status_code, status.HTTP_200_OK)

		self.client.force_authenticate(self.staff)
		confirm_response = self.client.post(
			f'/inventory/api/transfers/{transfer_id}/confirm-receipt/',
			{'notes': 'Everything arrived intact'},
			format='json'
		)
		self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)
		self.assertEqual(str(confirm_response.data['received_by']), str(self.staff.id))
		self.assertIsNotNone(confirm_response.data['received_at'])

		transfer_request = TransferRequest.objects.get(id=request_id)
		self.assertEqual(transfer_request.status, TransferRequest.STATUS_FULFILLED)
		self.assertEqual(transfer_request.fulfilled_by_id, self.staff.id)

	def test_manager_approval_updates_stock_and_employee_workspace(self):
		request_data = self._create_request(quantity=3)
		request_id = request_data['id']

		self.client.force_authenticate(self.owner)
		transfer_payload = {
			'source_warehouse': str(self.warehouse.id),
			'destination_storefront': str(self.storefront.id),
			'request_id': request_id
		}
		transfer_response = self.client.post('/inventory/api/transfers/', transfer_payload, format='json')
		self.assertEqual(transfer_response.status_code, status.HTTP_201_CREATED)
		transfer_id = transfer_response.data['id']

		submit_response = self.client.post(f'/inventory/api/transfers/{transfer_id}/submit/')
		self.assertEqual(submit_response.status_code, status.HTTP_200_OK)

		approve_response = self.client.post(f'/inventory/api/transfers/{transfer_id}/approve/')
		self.assertEqual(approve_response.status_code, status.HTTP_200_OK)

		dispatch_response = self.client.post(f'/inventory/api/transfers/{transfer_id}/dispatch/')
		self.assertEqual(dispatch_response.status_code, status.HTTP_200_OK)

		warehouse_stock = Inventory.objects.get(warehouse=self.warehouse, product=self.product)
		self.assertEqual(warehouse_stock.quantity, 17)

		complete_response = self.client.post(f'/inventory/api/transfers/{transfer_id}/complete/')
		self.assertEqual(complete_response.status_code, status.HTTP_200_OK)

		storefront_stock = StoreFrontInventory.objects.get(storefront=self.storefront, product=self.product)
		self.assertEqual(storefront_stock.quantity, 3)

		self.client.force_authenticate(self.staff)
		confirm_response = self.client.post(
			f'/inventory/api/transfers/{transfer_id}/confirm-receipt/',
			{'notes': 'Received as expected'},
			format='json'
		)
		self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)

		transfer_request = TransferRequest.objects.get(id=request_id)
		self.assertEqual(transfer_request.status, TransferRequest.STATUS_FULFILLED)
		self.assertEqual(transfer_request.fulfilled_by_id, self.staff.id)

		self.client.force_authenticate(self.owner)
		manager_workspace = self.client.get('/inventory/api/employee/workspace/')
		self.assertEqual(manager_workspace.status_code, status.HTTP_200_OK)
		self.assertEqual(len(manager_workspace.data['businesses']), 1)
		manager_summary = manager_workspace.data['businesses'][0]
		self.assertEqual(manager_summary['transfer_requests']['by_status'][TransferRequest.STATUS_FULFILLED], 1)
		self.assertEqual(manager_summary['transfers']['by_status'][Transfer.STATUS_COMPLETED], 1)
		self.assertEqual(manager_summary['stock']['warehouse_on_hand'], 17)
		self.assertEqual(manager_summary['stock']['storefront_on_hand'], 3)
		self.assertEqual(manager_workspace.data['pending_approvals'], [])

		self.client.force_authenticate(self.staff)
		staff_workspace = self.client.get('/inventory/api/employee/workspace/')
		self.assertEqual(staff_workspace.status_code, status.HTTP_200_OK)
		self.assertEqual(len(staff_workspace.data['businesses']), 1)
		staff_summary = staff_workspace.data['businesses'][0]
		self.assertEqual(staff_summary['transfer_requests']['by_status'][TransferRequest.STATUS_FULFILLED], 1)
		self.assertEqual(staff_summary['stock']['storefront_on_hand'], 3)
		self.assertEqual(staff_summary['transfers']['by_status'][Transfer.STATUS_COMPLETED], 1)
		self.assertEqual(len(staff_workspace.data['incoming_transfers']), 1)
		self.assertEqual(staff_workspace.data['incoming_transfers'][0]['status'], Transfer.STATUS_COMPLETED)
		self.assertEqual(staff_workspace.data['incoming_transfers'][0]['reference'], transfer_response.data['reference'])
		self.assertEqual(staff_workspace.data['my_transfer_requests'][0]['status'], TransferRequest.STATUS_FULFILLED)

	def test_manager_can_cancel_request(self):
		request_data = self._create_request(quantity=6)
		request_id = request_data['id']

		self.client.force_authenticate(self.owner)
		cancel_response = self.client.post(f'/inventory/api/transfer-requests/{request_id}/cancel/', format='json')
		self.assertEqual(cancel_response.status_code, status.HTTP_200_OK)
		self.assertEqual(cancel_response.data['status'], TransferRequest.STATUS_CANCELLED)

		transfer_request = TransferRequest.objects.get(id=request_id)
		self.assertEqual(transfer_request.status, TransferRequest.STATUS_CANCELLED)
		self.assertIsNone(transfer_request.linked_transfer_id)

