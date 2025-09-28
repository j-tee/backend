import uuid

from django.test import TestCase
from django.core.exceptions import ValidationError

from django.contrib.auth import get_user_model

from .models import (
	Warehouse, StoreFront, BusinessWarehouse, BusinessStoreFront,
	StoreFrontEmployee, WarehouseEmployee
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
