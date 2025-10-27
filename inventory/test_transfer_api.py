"""
Transfer API Tests (Phase 4)

Test suite for new Transfer API endpoints.
Tests serializers, viewsets, and complete/cancel actions.
"""

import uuid
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from accounts.models import Business, BusinessMembership
from inventory.models import Product, Warehouse, Category, StoreFront, StockProduct, Stock
from inventory.transfer_models import Transfer, TransferItem
from inventory.transfer_serializers import (
    WarehouseTransferSerializer,
    StorefrontTransferSerializer,
    TransferCompleteSerializer,
    TransferCancelSerializer,
)

User = get_user_model()


class BusinessTestMixin:
    """Mixin for creating test businesses"""
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


class TransferSerializerTest(BusinessTestMixin, TestCase):
    """Test Transfer serializers"""
    
    def setUp(self):
        """Set up test data"""
        self.user, self.business = self.create_business()
        
        self.warehouse1 = Warehouse.objects.create(
            name='Warehouse 1',
            location='Location 1'
        )
        self.warehouse2 = Warehouse.objects.create(
            name='Warehouse 2',
            location='Location 2'
        )
        self.storefront = StoreFront.objects.create(
            name='Storefront 1',
            location='Location 3',
            user=self.user
        )
        
        self.category = Category.objects.create(
            name='Test Category'
        )
        self.product = Product.objects.create(
            name='Test Product',
            sku='TEST-001',
            business=self.business,
            category=self.category
        )
    
    def test_warehouse_transfer_serializer_validation(self):
        """Test WarehouseTransferSerializer validation"""
        data = {
            'source_warehouse': self.warehouse1.id,
            'destination_warehouse': self.warehouse2.id,
            'notes': 'Test transfer',
            'items': [
                {
                    'product': self.product.id,
                    'quantity': 10,
                    'unit_cost': '10.00'
                }
            ]
        }
        
        serializer = WarehouseTransferSerializer(data=data, context={'request': None})
        self.assertTrue(serializer.is_valid(), serializer.errors)
    
    def test_warehouse_transfer_prevents_self_transfer(self):
        """Test that warehouse cannot transfer to itself"""
        data = {
            'source_warehouse': self.warehouse1.id,
            'destination_warehouse': self.warehouse1.id,
            'items': [
                {
                    'product': self.product.id,
                    'quantity': 10,
                    'unit_cost': '10.00'
                }
            ]
        }
        
        serializer = WarehouseTransferSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('Source and destination warehouse cannot be the same', 
                     str(serializer.errors))
    
    def test_storefront_transfer_serializer_validation(self):
        """Test StorefrontTransferSerializer validation"""
        data = {
            'source_warehouse': self.warehouse1.id,
            'destination_storefront': self.storefront.id,
            'notes': 'Test storefront transfer',
            'items': [
                {
                    'product': self.product.id,
                    'quantity': 5,
                    'unit_cost': '10.00'
                }
            ]
        }
        
        serializer = StorefrontTransferSerializer(data=data, context={'request': None})
        self.assertTrue(serializer.is_valid(), serializer.errors)
    
    def test_transfer_requires_items(self):
        """Test that transfer must have at least one item"""
        data = {
            'source_warehouse': self.warehouse1.id,
            'destination_warehouse': self.warehouse2.id,
            'items': []
        }
        
        serializer = WarehouseTransferSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('items', serializer.errors)
    
    def test_transfer_prevents_duplicate_products(self):
        """Test that duplicate products are not allowed"""
        data = {
            'source_warehouse': self.warehouse1.id,
            'destination_warehouse': self.warehouse2.id,
            'items': [
                {
                    'product': self.product.id,
                    'quantity': 10,
                    'unit_cost': '10.00'
                },
                {
                    'product': self.product.id,
                    'quantity': 5,
                    'unit_cost': '10.00'
                }
            ]
        }
        
        serializer = WarehouseTransferSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('Duplicate products are not allowed', str(serializer.errors))
    
    def test_transfer_validates_positive_quantity(self):
        """Test that quantity must be positive"""
        data = {
            'source_warehouse': self.warehouse1.id,
            'destination_warehouse': self.warehouse2.id,
            'items': [
                {
                    'product': self.product.id,
                    'quantity': -5,
                    'unit_cost': '10.00'
                }
            ]
        }
        
        serializer = WarehouseTransferSerializer(data=data)
        self.assertFalse(serializer.is_valid())


class WarehouseTransferViewSetTest(BusinessTestMixin, APITestCase):
    """Test WarehouseTransferViewSet endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.user, self.business = self.create_business()
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        self.warehouse1 = Warehouse.objects.create(
            name='Warehouse 1',
            location='Location 1'
        )
        self.warehouse2 = Warehouse.objects.create(
            name='Warehouse 2',
            location='Location 2'
        )
        
        self.category = Category.objects.create(
            name='Test Category'
        )
        self.product = Product.objects.create(
            name='Test Product',
            sku='TEST-001',
            business=self.business,
            category=self.category
        )
        
        # Create stock in warehouse1
        stock_batch = Stock.objects.create(
            business=self.business,
            description='Test stock batch'
        )
        self.stock = StockProduct.objects.create(
            stock=stock_batch,
            warehouse=self.warehouse1,
            product=self.product,
            quantity=100
        )
    
    def test_create_warehouse_transfer(self):
        """Test creating a warehouse transfer"""
        url = reverse('warehouse-transfers-list')
        data = {
            'source_warehouse': str(self.warehouse1.id),
            'destination_warehouse': str(self.warehouse2.id),
            'notes': 'Test transfer',
            'items': [
                {
                    'product': str(self.product.id),
                    'quantity': 10,
                    'unit_cost': '10.00'
                }
            ]
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Transfer.objects.count(), 1)
        
        transfer = Transfer.objects.first()
        self.assertEqual(transfer.status, 'pending')
        self.assertEqual(transfer.items.count(), 1)
        self.assertIsNotNone(transfer.reference_number)


class StorefrontTransferViewSetTest(BusinessTestMixin, APITestCase):
    """Test StorefrontTransferViewSet endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.user, self.business = self.create_business()
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
        
        self.warehouse = Warehouse.objects.create(
            name='Warehouse 1',
            location='Location 1'
        )
        self.storefront = StoreFront.objects.create(
            name='Storefront 1',
            location='Location 2',
            user=self.user
        )
        
        self.category = Category.objects.create(
            name='Test Category'
        )
        self.product = Product.objects.create(
            name='Test Product',
            sku='TEST-001',
            business=self.business,
            category=self.category
        )
        
        # Create stock in warehouse
        stock_batch = Stock.objects.create(
            business=self.business,
            description='Test stock batch'
        )
        self.stock = StockProduct.objects.create(
            stock=stock_batch,
            warehouse=self.warehouse,
            product=self.product,
            quantity=100
        )
    
    def test_create_storefront_transfer(self):
        """Test creating a storefront transfer"""
        url = reverse('storefront-transfers-list')
        data = {
            'source_warehouse': str(self.warehouse.id),
            'destination_storefront': str(self.storefront.id),
            'notes': 'Test storefront transfer',
            'items': [
                {
                    'product': str(self.product.id),
                    'quantity': 10,
                    'unit_cost': '10.00'
                }
            ]
        }
        
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        transfer = Transfer.objects.first()
        self.assertEqual(transfer.destination_storefront, self.storefront)
        self.assertIsNone(transfer.destination_warehouse)


class TransferPermissionsTest(BusinessTestMixin, APITestCase):
    """Test Transfer API permissions"""
    
    def setUp(self):
        """Set up test data"""
        self.user1, self.business1 = self.create_business()
        self.user2, self.business2 = self.create_business()
        
        self.warehouse1 = Warehouse.objects.create(
            name='Warehouse 1',
            location='Location 1'
        )
        self.warehouse2 = Warehouse.objects.create(
            name='Warehouse 2',
            location='Location 2'
        )
        
        self.category = Category.objects.create(
            name='Category'
        )
        self.product = Product.objects.create(
            name='Product',
            sku='PROD-001',
            business=self.business1,
            category=self.category
        )
        
        self.client = APIClient()
