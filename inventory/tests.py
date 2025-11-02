import uuid
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.utils import timezone
from django.urls import reverse
from django.db.models import Sum
from django.contrib.auth import get_user_model

from accounts.models import Business, BusinessMembership
from inventory.stock_adjustments import StockAdjustment
from sales.models import Customer, Sale, SaleItem, StockReservation

from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.authtoken.models import Token

from .models import (
	Warehouse, StoreFront, BusinessWarehouse, BusinessStoreFront,
	StoreFrontEmployee, WarehouseEmployee, Category, Product, Supplier, Stock, StockProduct,
	StoreFrontInventory, TransferRequest
)

User = get_user_model()


class BusinessTestMixin:
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
		BusinessMembership.objects.get_or_create(
			business=business,
			user=owner,
			defaults={'role': BusinessMembership.OWNER, 'is_admin': True, 'is_active': True}
		)
		return owner, business


class StorefrontTransferWorkflowTest(BusinessTestMixin, APITestCase):
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
		# Create stock batch and stock product (replaces Inventory)
		self.supplier = Supplier.objects.create(business=self.business, name='Test Supplier', email='supplier@test.com')
		self.stock = Stock.objects.create(business=self.business, description='Test Stock Batch')
		self.stock_product = StockProduct.objects.create(
			stock=self.stock,
			warehouse=self.warehouse,
			product=self.product,
			supplier=self.supplier,
			quantity=20,
			unit_cost=Decimal('10.00'),
			retail_price=Decimal('15.00')
		)

		self.storefront = StoreFront.objects.create(user=self.owner, name='Transfer Storefront', location='Retail Park')
		BusinessStoreFront.objects.create(business=self.business, storefront=self.storefront)
		StoreFrontEmployee.objects.create(
			business=self.business,
			storefront=self.storefront,
			user=self.staff,
			role=BusinessMembership.STAFF,
			is_active=True
		)

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
		self.assertEqual(len(request_data['line_items']), 1)
		self.assertEqual(request_data['line_items'][0]['requested_quantity'], 5)

	def test_manager_can_fulfill_request_via_action(self):
		request_data = self._create_request(quantity=4)
		request_id = request_data['id']

		self.client.force_authenticate(self.owner)
		fulfill_response = self.client.post(
			f'/inventory/api/transfer-requests/{request_id}/fulfill/',
			format='json'
		)
		self.assertEqual(fulfill_response.status_code, status.HTTP_200_OK)
		self.assertEqual(fulfill_response.data['status'], TransferRequest.STATUS_FULFILLED)
		self.assertEqual(str(fulfill_response.data['fulfilled_by']), str(self.owner.id))
		self.assertIn('_inventory_adjustments', fulfill_response.data)
		self.assertEqual(fulfill_response.data['_inventory_adjustments'][0]['quantity_added'], 4)
		inventory_entry = StoreFrontInventory.objects.get(storefront=self.storefront, product=self.product)
		self.assertEqual(inventory_entry.quantity, 4)

	def test_manager_can_cancel_request(self):
		request_data = self._create_request(quantity=6)
		request_id = request_data['id']

		self.client.force_authenticate(self.owner)
		cancel_response = self.client.post(f'/inventory/api/transfer-requests/{request_id}/cancel/', format='json')
		self.assertEqual(cancel_response.status_code, status.HTTP_200_OK)
		self.assertEqual(cancel_response.data['status'], TransferRequest.STATUS_CANCELLED)

		fulfill_after_cancel = self.client.post(
			f'/inventory/api/transfer-requests/{request_id}/fulfill/',
			format='json'
		)
		self.assertEqual(fulfill_after_cancel.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn('status', fulfill_after_cancel.data)

	def test_fulfilled_request_reflected_in_workspace_summary(self):
		request_data = self._create_request(quantity=3)
		request_id = request_data['id']

		self.client.force_authenticate(self.owner)
		fulfill_response = self.client.post(
			f'/inventory/api/transfer-requests/{request_id}/fulfill/',
			format='json'
		)
		self.assertEqual(fulfill_response.status_code, status.HTTP_200_OK)

		manager_workspace = self.client.get('/inventory/api/employee/workspace/')
		self.assertEqual(manager_workspace.status_code, status.HTTP_200_OK)
		self.assertEqual(len(manager_workspace.data['businesses']), 1)
		manager_summary = manager_workspace.data['businesses'][0]
		self.assertEqual(manager_summary['transfer_requests']['by_status'][TransferRequest.STATUS_FULFILLED], 1)
		self.assertEqual(manager_summary['stock']['storefront_on_hand'], 3)

		self.client.force_authenticate(self.staff)
		staff_workspace = self.client.get('/inventory/api/employee/workspace/')
		self.assertEqual(staff_workspace.status_code, status.HTTP_200_OK)
		self.assertEqual(len(staff_workspace.data['businesses']), 1)
		staff_summary = staff_workspace.data['businesses'][0]
		self.assertEqual(staff_summary['transfer_requests']['by_status'][TransferRequest.STATUS_FULFILLED], 1)
		self.assertEqual(staff_summary['stock']['storefront_on_hand'], 3)
		self.assertEqual(staff_workspace.data['my_transfer_requests'][0]['status'], TransferRequest.STATUS_FULFILLED)

	def test_manager_can_update_request_status_with_force_reset(self):
		request_data = self._create_request(quantity=4)
		request_id = request_data['id']

		self.client.force_authenticate(self.owner)
		fulfill_response = self.client.post(
			f'/inventory/api/transfer-requests/{request_id}/update-status/',
			{'status': TransferRequest.STATUS_FULFILLED},
			format='json'
		)
		self.assertEqual(fulfill_response.status_code, status.HTTP_200_OK)
		self.assertEqual(fulfill_response.data['status'], TransferRequest.STATUS_FULFILLED)

		reset_response = self.client.post(
			f'/inventory/api/transfer-requests/{request_id}/update-status/',
			{'status': TransferRequest.STATUS_NEW},
			format='json'
		)
		self.assertEqual(reset_response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn('status', reset_response.data)

		force_reset_response = self.client.post(
			f'/inventory/api/transfer-requests/{request_id}/update-status/',
			{'status': TransferRequest.STATUS_NEW, 'force': True},
			format='json'
		)
		self.assertEqual(force_reset_response.status_code, status.HTTP_200_OK)
		self.assertEqual(force_reset_response.data['status'], TransferRequest.STATUS_NEW)

	def test_staff_cannot_update_request_status(self):
		"""Staff members cannot manually update request status."""
		request_data = self._create_request(quantity=3)
		request_id = request_data['id']

		self.client.force_authenticate(self.staff)
		update_response = self.client.post(
			f'/inventory/api/transfer-requests/{request_id}/update-status/',
			{'status': TransferRequest.STATUS_FULFILLED},
			format='json'
		)
		self.assertEqual(update_response.status_code, status.HTTP_403_FORBIDDEN)

	def test_invalid_status_update_rejected(self):
		"""Invalid status values are rejected."""
		request_data = self._create_request(quantity=4)
		request_id = request_data['id']

		self.client.force_authenticate(self.owner)
		invalid_response = self.client.post(
			f'/inventory/api/transfer-requests/{request_id}/update-status/',
			{'status': 'INVALID_STATUS'},
			format='json'
		)
		self.assertEqual(invalid_response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn('status', invalid_response.data)

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
		self.client.force_authenticate(user=None)
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

		# Create stock batch and stock product (replaces Inventory)
		self.supplier = Supplier.objects.create(business=self.business, name='Test Supplier', email='supplier@test.com')
		self.stock = Stock.objects.create(business=self.business, description='Test Stock Batch')
		StockProduct.objects.create(
			stock=self.stock,
			warehouse=self.warehouse,
			product=self.product,
			supplier=self.supplier,
			quantity=10,
			unit_cost=Decimal('10.00'),
			retail_price=Decimal('15.00')
		)

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

	def test_transfer_request_creation_records_line_items(self):
		payload = {
			'storefront': str(self.storefront.id),
			'priority': TransferRequest.PRIORITY_MEDIUM,
			'notes': 'Within allocation',
			'line_items': [
				{
					'product': str(self.product.id),
					'requested_quantity': 4
				}
			]
		}
		response = self.client.post('/inventory/api/transfer-requests/', payload, format='json')
		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		self.assertEqual(response.data['status'], TransferRequest.STATUS_NEW)
		self.assertEqual(len(response.data['line_items']), 1)
		self.assertEqual(response.data['line_items'][0]['product'], str(self.product.id))
		self.assertEqual(response.data['line_items'][0]['requested_quantity'], 4)

	def test_transfer_request_fulfillment_updates_storefront_inventory(self):
		payload = {
			'storefront': str(self.storefront.id),
			'priority': TransferRequest.PRIORITY_MEDIUM,
			'notes': 'Fulfill this request',
			'line_items': [
				{
					'product': str(self.product.id),
					'requested_quantity': 3
				}
			]
		}
		response = self.client.post('/inventory/api/transfer-requests/', payload, format='json')
		self.assertEqual(response.status_code, status.HTTP_201_CREATED)
		request_id = response.data['id']

		fulfill_response = self.client.post(f'/inventory/api/transfer-requests/{request_id}/fulfill/', format='json')
		self.assertEqual(fulfill_response.status_code, status.HTTP_200_OK)
		self.assertEqual(fulfill_response.data['status'], TransferRequest.STATUS_FULFILLED)
		adjustments = fulfill_response.data.get('_inventory_adjustments')
		self.assertIsNotNone(adjustments)
		self.assertEqual(adjustments[0]['quantity_added'], 3)

		storefront_inventory = StoreFrontInventory.objects.get(storefront=self.storefront, product=self.product)
		self.assertEqual(storefront_inventory.quantity, 3)


class StorefrontAvailabilityAfterSaleTest(BusinessTestMixin, APITestCase):
	def setUp(self):
		self.owner, self.business = self.create_business()
		self.owner.account_type = User.ACCOUNT_OWNER
		self.owner.is_active = True
		self.owner.save(update_fields=['account_type', 'is_active'])

		BusinessMembership.objects.get_or_create(
			business=self.business,
			user=self.owner,
			defaults={'role': BusinessMembership.OWNER, 'is_admin': True}
		)

		self.category = Category.objects.create(name='Availability Tracking')
		self.product = Product.objects.create(
			business=self.business,
			name='Realtime Widget',
			sku='RT-001',
			category=self.category
		)

		self.warehouse = Warehouse.objects.create(name='Realtime Warehouse', location='Central Depot')
		BusinessWarehouse.objects.create(business=self.business, warehouse=self.warehouse)

		self.stock = Stock.objects.create(business=self.business, description='Initial Batch')
		self.stock_product = StockProduct.objects.create(
			stock=self.stock,
			warehouse=self.warehouse,
			product=self.product,
			quantity=60,
			unit_cost=Decimal('5.00'),
			retail_price=Decimal('12.00')
		)

		self.storefront = StoreFront.objects.create(user=self.owner, name='Realtime Storefront', location='Downtown')
		BusinessStoreFront.objects.create(business=self.business, storefront=self.storefront)
		self.storefront_inventory = StoreFrontInventory.objects.create(
			storefront=self.storefront,
			product=self.product,
			quantity=50
		)

		self.customer = Customer.objects.create(
			business=self.business,
			name='Walk-in Customer',
			created_by=self.owner
		)

		self.sale = Sale.objects.create(
			business=self.business,
			storefront=self.storefront,
			user=self.owner,
			customer=self.customer,
			status='DRAFT',
			payment_type='CASH'
		)
		SaleItem.objects.create(
			sale=self.sale,
			product=self.product,
			stock=self.stock,
			stock_product=self.stock_product,
			quantity=Decimal('2'),
			unit_price=Decimal('12.00')
		)
		self.sale.calculate_totals()

		self.client.force_authenticate(self.owner)

	def test_storefront_availability_reflects_completed_sale(self):
		url = reverse('stock-availability', kwargs={
			'storefront_id': self.storefront.id,
			'product_id': self.product.id,
		})

		pre_sale_response = self.client.get(url)
		self.assertEqual(pre_sale_response.status_code, status.HTTP_200_OK)
		self.assertEqual(pre_sale_response.data['unreserved_quantity'], 50)
		self.assertEqual(pre_sale_response.data['reserved_quantity'], 0)

		self.sale.amount_paid = self.sale.total_amount
		self.sale.amount_due = Decimal('0.00')
class StorefrontSaleCatalogAPITest(BusinessTestMixin, APITestCase):
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

		self.category = Category.objects.create(name='Catalog Products')
		self.product_with_stock = Product.objects.create(
			business=self.business,
			name='Catalog Widget',
			sku='CAT-001',
			category=self.category
		)
		self.product_without_stock = Product.objects.create(
			business=self.business,
			name='Ghost Widget',
			sku='CAT-002',
			category=self.category
		)

		self.warehouse = Warehouse.objects.create(name='Catalog Warehouse', location='Industrial Estate')
		BusinessWarehouse.objects.create(business=self.business, warehouse=self.warehouse)
		self.stock = Stock.objects.create(business=self.business, description='Initial Catalog Batch')
		self.supplier = Supplier.objects.create(business=self.business, name='Catalog Supplier')

		self.storefront = StoreFront.objects.create(user=self.owner, name='Catalog Storefront', location='High Street')
		BusinessStoreFront.objects.create(business=self.business, storefront=self.storefront)

		self.stock_product_old = StockProduct.objects.create(
			stock=self.stock,
			warehouse=self.warehouse,
			product=self.product_with_stock,
			supplier=self.supplier,
			quantity=5,
			unit_cost=Decimal('8.00'),
			unit_tax_rate=Decimal('5.00'),
			retail_price=Decimal('10.00'),
			wholesale_price=Decimal('9.00')
		)
		self.stock_product_latest = StockProduct.objects.create(
			stock=self.stock,
			warehouse=self.warehouse,
			product=self.product_with_stock,
			supplier=self.supplier,
			quantity=7,
			unit_cost=Decimal('9.00'),
			unit_tax_rate=Decimal('5.00'),
			retail_price=Decimal('12.50'),
			wholesale_price=Decimal('10.50')
		)

		self.catalog_inventory = StoreFrontInventory.objects.create(
			storefront=self.storefront,
			product=self.product_with_stock,
			quantity=5
		)
		self.catalog_inventory.quantity += 7
		self.catalog_inventory.save(update_fields=['quantity', 'updated_at'])

		StoreFrontInventory.objects.create(
			storefront=self.storefront,
			product=self.product_without_stock,
			quantity=9
		)

		self.client.force_authenticate(self.owner)

	def test_sale_catalog_filters_products_without_stock_product(self):
		url = f'/inventory/api/storefronts/{self.storefront.id}/sale-catalog/'
		response = self.client.get(url)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertIn('products', response.data)
		products = response.data['products']
		self.assertEqual(len(products), 1)
		product_data = products[0]
		self.assertEqual(product_data['product_id'], str(self.product_with_stock.id))
		self.assertEqual(product_data['available_quantity'], 12)
		self.assertEqual(
			sorted(product_data['stock_product_ids']),
			sorted([str(self.stock_product_old.id), str(self.stock_product_latest.id)])
		)
		self.assertEqual(Decimal(product_data['retail_price']), Decimal('12.50'))
		self.assertEqual(Decimal(product_data['wholesale_price']), Decimal('10.50'))
		self.assertIsNotNone(product_data['last_stocked_at'])

	def test_sale_catalog_includes_zero_stock_when_requested(self):
		# Zero out storefront quantity but request include_zero to confirm optional behaviour
		self.catalog_inventory.quantity = 0
		self.catalog_inventory.save(update_fields=['quantity', 'updated_at'])
		url = f'/inventory/api/storefronts/{self.storefront.id}/sale-catalog/?include_zero=true'
		response = self.client.get(url)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		products = response.data['products']
		self.assertEqual(len(products), 1)
		self.assertEqual(products[0]['available_quantity'], 0)


class StockReconciliationAPITest(BusinessTestMixin, APITestCase):
	def setUp(self):
		self.owner, self.business = self.create_business()
		self.owner.account_type = User.ACCOUNT_OWNER
		self.owner.is_active = True
		self.owner.save(update_fields=['account_type', 'is_active'])

		BusinessMembership.objects.update_or_create(
			business=self.business,
			user=self.owner,
			defaults={'role': BusinessMembership.OWNER, 'is_admin': True, 'is_active': True}
		)
		self.owner.business = self.business

		self.category = Category.objects.create(name='Reconciliation Gadgets')
		self.product = Product.objects.create(
			business=self.business,
			name='Recon Widget',
			sku='RECON-001',
			category=self.category
		)

		self.warehouse = Warehouse.objects.create(name='Recon Warehouse', location='Recon City')
		BusinessWarehouse.objects.create(business=self.business, warehouse=self.warehouse)
		# Create supplier and stock batch for reconciliation test
		self.supplier = Supplier.objects.create(business=self.business, name='Test Supplier', email='supplier@test.com')
		self.stock = Stock.objects.create(business=self.business, description='Recon batch')
		self.stock_product = StockProduct.objects.create(
			stock=self.stock,
			warehouse=self.warehouse,
			product=self.product,
			supplier=self.supplier,
			quantity=20,  # StockProduct quantity is 20, representing warehouse stock
			unit_cost=Decimal('5.00'),
			retail_price=Decimal('10.00')
		)

		self.storefront = StoreFront.objects.create(user=self.owner, name='Recon Storefront', location='Mall')
		BusinessStoreFront.objects.create(business=self.business, storefront=self.storefront)
		StoreFrontInventory.objects.create(
			storefront=self.storefront,
			product=self.product,
			quantity=5
		)

		self.customer = Customer.objects.create(
			business=self.business,
			name='Recon Customer',
			created_by=self.owner
		)

		self.sale = Sale.objects.create(
			business=self.business,
			storefront=self.storefront,
			user=self.owner,
			customer=self.customer,
			status='COMPLETED',
			payment_type='CASH'
		)
		SaleItem.objects.create(
			sale=self.sale,
			product=self.product,
			stock=self.stock,
			stock_product=self.stock_product,
			quantity=Decimal('3'),
			unit_price=Decimal('12.00')
		)
		line_total = self.sale.sale_items.aggregate(total=Sum('total_price'))['total'] or Decimal('0.00')
		self.sale.amount_paid = line_total
		self.sale.calculate_totals()
		self.sale.completed_at = timezone.now()
		self.sale.save(update_fields=['subtotal', 'discount_amount', 'tax_amount', 'total_amount', 'amount_paid', 'amount_due', 'completed_at', 'updated_at'])

		StockAdjustment.objects.create(
			business=self.business,
			stock_product=self.stock_product,
			adjustment_type='DAMAGE',
			quantity=-2,
			unit_cost=Decimal('5.00'),
			total_cost=Decimal('10.00'),
			reason='Damage',
			status='COMPLETED',
			requires_approval=False,
			created_by=self.owner,
			approved_by=self.owner,
			approved_at=timezone.now(),
			completed_at=timezone.now()
		)
		StockAdjustment.objects.create(
			business=self.business,
			stock_product=self.stock_product,
			adjustment_type='CORRECTION_INCREASE',
			quantity=1,
			unit_cost=Decimal('5.00'),
			total_cost=Decimal('5.00'),
			reason='Correction',
			status='COMPLETED',
			requires_approval=False,
			created_by=self.owner,
			approved_by=self.owner,
			approved_at=timezone.now(),
			completed_at=timezone.now()
		)

		StockReservation.objects.create(
			stock_product=self.stock_product,
			quantity=Decimal('2'),
			cart_session_id=str(self.sale.id),
			status='ACTIVE',
			expires_at=timezone.now() + timedelta(minutes=30)
		)
		StockReservation.objects.create(
			stock_product=self.stock_product,
			quantity=Decimal('1'),
			cart_session_id='orphan-session',
			status='ACTIVE',
			expires_at=timezone.now() + timedelta(minutes=30)
		)

		self.client.force_authenticate(self.owner)

	def test_stock_reconciliation_returns_expected_metrics(self):
		url = reverse('product-stock-reconciliation', kwargs={'pk': self.product.id})
		response = self.client.get(url)
		self.assertEqual(response.status_code, status.HTTP_200_OK)

		payload = response.data

		self.assertEqual(payload['warehouse']['recorded_quantity'], 20)
		self.assertEqual(payload['storefront']['total_on_hand'], 5)
		self.assertEqual(payload['sales']['completed_units'], 3)
		self.assertEqual(payload['adjustments']['shrinkage_units'], 2)
		self.assertEqual(payload['adjustments']['correction_units'], 1)
		self.assertEqual(payload['reservations']['linked_units'], 2)
		self.assertEqual(payload['reservations']['orphaned_units'], 1)

		# Warehouse on hand = Recorded batch (20) - Storefront on hand (5) = 15
		formula = payload['formula']
		self.assertEqual(formula['warehouse_inventory_on_hand'], 15)
		# Baseline (corrected formula) = Warehouse (15) + Storefront (5) - Shrinkage (2) + Corrections (1) - Reservations (2) = 17
		# Note: sold units are not added separately because they are included in storefront transfers
		self.assertEqual(formula['calculated_baseline'], 17)
		self.assertEqual(formula['recorded_batch_quantity'], 20)
		# Delta: recorded (20) - calculated baseline (17) = 3
		self.assertEqual(formula['baseline_vs_recorded_delta'], 3)

	def test_warehouse_inventory_falls_back_to_recorded_quantity_when_no_entries(self):
		new_product = Product.objects.create(
			business=self.business,
			name='Fallback Widget',
			sku='FALL-001',
			category=self.category
		)
		new_stock = Stock.objects.create(business=self.business, description='Fallback stock')
		new_stock_product = StockProduct.objects.create(
			stock=new_stock,
			warehouse=self.warehouse,
			product=new_product,
			quantity=15,
			unit_cost=Decimal('4.00'),
			retail_price=Decimal('8.00')
		)

		url = reverse('product-stock-reconciliation', kwargs={'pk': new_product.id})
		response = self.client.get(url)
		self.assertEqual(response.status_code, status.HTTP_200_OK)

		payload = response.data
		self.assertEqual(payload['warehouse']['recorded_quantity'], 15)
		# No storefront transfers, so warehouse on hand = recorded quantity
		self.assertEqual(payload['warehouse']['inventory_on_hand'], 15)

		formula = payload['formula']
		self.assertEqual(formula['warehouse_inventory_on_hand'], 15)
		self.assertEqual(formula['recorded_batch_quantity'], 15)
		# Baseline = Warehouse (15) + Storefront (0) + Sold (0) - Shrinkage (0) + Corrections (0) - Reservations (0) = 15
		self.assertEqual(formula['calculated_baseline'], 15)
		self.assertEqual(formula['baseline_vs_recorded_delta'], 0)

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

		# Create stock batch and stock product (replaces Inventory)
		supplier = Supplier.objects.create(business=self.business, name='Test Supplier', email='supplier@test.com')
		stock = Stock.objects.create(business=self.business, description='Test Stock Batch')
		StockProduct.objects.create(
			stock=stock,
			warehouse=self.warehouse,
			product=self.product,
			supplier=supplier,
			quantity=20,
			unit_cost=Decimal('10.00'),
			retail_price=Decimal('15.00')
		)

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

		# warehouse_stock = Inventory.objects.get(warehouse=self.warehouse, product=self.product)
		# self.assertEqual(warehouse_stock.quantity, 17)

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
		self.assertEqual(manager_summary['transfers']['by_status'][TransferRequest.STATUS_COMPLETED], 1)
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
		self.assertEqual(staff_summary['transfers']['by_status'][TransferRequest.STATUS_COMPLETED], 1)
		self.assertEqual(len(staff_workspace.data['incoming_transfers']), 1)
		self.assertEqual(staff_workspace.data['incoming_transfers'][0]['status'], TransferRequest.STATUS_COMPLETED)
		self.assertEqual(staff_workspace.data['incoming_transfers'][0]['reference'], transfer_response.data['reference'])
		self.assertEqual(staff_workspace.data['my_transfer_requests'][0]['status'], TransferRequest.STATUS_FULFILLED)

	def test_manual_fulfillment_updates_storefront_inventory(self):
		request_data = self._create_request(quantity=5)
		request_id = request_data['id']

		self.client.force_authenticate(self.owner)
		response = self.client.post(
			f'/inventory/api/transfer-requests/{request_id}/update-status/',
			{'status': TransferRequest.STATUS_FULFILLED},
			format='json'
		)
		self.assertEqual(response.status_code, status.HTTP_200_OK)
		self.assertEqual(response.data['status'], TransferRequest.STATUS_FULFILLED)
		inventory_entry = StoreFrontInventory.objects.get(storefront=self.storefront, product=self.product)
		self.assertEqual(inventory_entry.quantity, 5)
		adjustments = response.data.get('_inventory_adjustments')
		self.assertIsNotNone(adjustments)
		self.assertEqual(adjustments[0]['quantity_added'], 5)

	def test_manager_can_cancel_request(self):
		request_data = self._create_request(quantity=6)
		request_id = request_data['id']

		self.client.force_authenticate(self.owner)
		cancel_response = self.client.post(f'/inventory/api/transfer-requests/{request_id}/cancel/', format='json')
		self.assertEqual(cancel_response.status_code, status.HTTP_200_OK)
		self.assertEqual(cancel_response.data['status'], TransferRequest.STATUS_CANCELLED)

	def test_manager_can_update_request_status(self):
		"""Test that managers can manually update stock request status."""
		request_data = self._create_request(quantity=5)
		request_id = request_data['id']

		# Verify initial status
		self.assertEqual(request_data['status'], TransferRequest.STATUS_NEW)

		# Manager updates status to ASSIGNED
		self.client.force_authenticate(self.owner)
		update_response = self.client.post(
			f'/inventory/api/transfer-requests/{request_id}/update-status/',
			{'status': TransferRequest.STATUS_ASSIGNED},
			format='json'
		)
		self.assertEqual(update_response.status_code, status.HTTP_200_OK)
		self.assertEqual(update_response.data['status'], TransferRequest.STATUS_ASSIGNED)
		self.assertIsNotNone(update_response.data['assigned_at'])
		self.assertIn('_status_change', update_response.data)
		self.assertEqual(update_response.data['_status_change']['old_status'], TransferRequest.STATUS_NEW)
		self.assertEqual(update_response.data['_status_change']['new_status'], TransferRequest.STATUS_ASSIGNED)

		# Manager manually fulfills the request
		fulfill_response = self.client.post(
			f'/inventory/api/transfer-requests/{request_id}/update-status/',
			{'status': TransferRequest.STATUS_FULFILLED},
			format='json'
		)
		self.assertEqual(fulfill_response.status_code, status.HTTP_200_OK)
		self.assertEqual(fulfill_response.data['status'], TransferRequest.STATUS_FULFILLED)
		self.assertIsNotNone(fulfill_response.data['fulfilled_at'])
		self.assertEqual(str(fulfill_response.data['fulfilled_by']), str(self.owner.id))

		# Try to change from FULFILLED without force flag (should fail)
		reset_response = self.client.post(
			f'/inventory/api/transfer-requests/{request_id}/update-status/',
			{'status': TransferRequest.STATUS_NEW},
			format='json'
		)
		self.assertEqual(reset_response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn('status', reset_response.data)
		error_message = reset_response.data['status'][0] if isinstance(reset_response.data['status'], list) else reset_response.data['status']
		self.assertIn('force', error_message.lower())

		# Reset with force flag
		force_reset_response = self.client.post(
			f'/inventory/api/transfer-requests/{request_id}/update-status/',
			{'status': TransferRequest.STATUS_NEW, 'force': True},
			format='json'
		)
		self.assertEqual(force_reset_response.status_code, status.HTTP_200_OK)
		self.assertEqual(force_reset_response.data['status'], TransferRequest.STATUS_NEW)

	def test_staff_cannot_update_request_status(self):
		"""Test that staff members cannot manually update status (manager-only)."""
		request_data = self._create_request(quantity=3)
		request_id = request_data['id']

		# Staff tries to update status (should be denied)
		self.client.force_authenticate(self.staff)
		update_response = self.client.post(
			f'/inventory/api/transfer-requests/{request_id}/update-status/',
			{'status': TransferRequest.STATUS_FULFILLED},
			format='json'
		)
		self.assertEqual(update_response.status_code, status.HTTP_403_FORBIDDEN)

	def test_invalid_status_update_rejected(self):
		"""Test that invalid status values are rejected."""
		request_data = self._create_request(quantity=4)
		request_id = request_data['id']

		self.client.force_authenticate(self.owner)
		invalid_response = self.client.post(
			f'/inventory/api/transfer-requests/{request_id}/update-status/',
			{'status': 'INVALID_STATUS'},
			format='json'
		)
		self.assertEqual(invalid_response.status_code, status.HTTP_400_BAD_REQUEST)
		self.assertIn('status', invalid_response.data)
