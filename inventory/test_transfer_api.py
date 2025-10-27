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
from inventory.models import Product, Warehouse, Category, StoreFront, StockProduct
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
            business=self.business,
            location='Location 3',
            user=self.user
        )
        
        self.category = Category.objects.create(
            name='Test Category',
            business=self.business
        )
        self.product = Product.objects.create(
            name='Test Product',
            sku='TEST-001',
            business=self.business,
            category=self.category,
            cost=Decimal('10.00'),
            retail_price=Decimal('15.00')
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
            name='Test Category',
            business=self.business
        )
        self.product = Product.objects.create(
            name='Test Product',
            sku='TEST-001',
            business=self.business,
            category=self.category,
            cost=Decimal('10.00'),
            retail_price=Decimal('15.00')
        )
        
        # Create stock in warehouse1
        self.stock = StockProduct.objects.create(
            warehouse=self.warehouse1,
            product=self.product,
            business=self.business,
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
    
    def test_list_warehouse_transfers(self):
        """Test listing warehouse transfers"""
        # Create a transfer
        transfer = Transfer.objects.create(
            business=self.business,
            source_warehouse=self.warehouse1,
            destination_warehouse=self.warehouse2,
            created_by=self.user
        )
        TransferItem.objects.create(
            transfer=transfer,
            product=self.product,
            quantity=10,
            unit_cost=Decimal('10.00')
        )
        
        url = reverse('warehouse-transfers-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_get_warehouse_transfer_detail(self):
        """Test getting transfer details"""
        transfer = Transfer.objects.create(
            business=self.business,
            source_warehouse=self.warehouse1,
            destination_warehouse=self.warehouse2,
            created_by=self.user
        )
        TransferItem.objects.create(
            transfer=transfer,
            product=self.product,
            quantity=10,
            unit_cost=Decimal('10.00')
        )
        
        url = reverse('warehouse-transfers-detail', args=[transfer.id])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(transfer.id))
        self.assertEqual(len(response.data['items']), 1)
    
    def test_complete_warehouse_transfer(self):
        """Test completing a warehouse transfer"""
        transfer = Transfer.objects.create(
            business=self.business,
            source_warehouse=self.warehouse1,
            destination_warehouse=self.warehouse2,
            created_by=self.user
        )
        TransferItem.objects.create(
            transfer=transfer,
            product=self.product,
            quantity=10,
            unit_cost=Decimal('10.00')
        )
        
        url = reverse('warehouse-transfers-complete', args=[transfer.id])
        response = self.client.post(url, {'notes': 'Completed successfully'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        transfer.refresh_from_db()
        self.assertEqual(transfer.status, 'completed')
        self.assertIsNotNone(transfer.completed_at)
        self.assertEqual(transfer.completed_by, self.user)
        
        # Check stock was moved
        source_stock = StockProduct.objects.get(
            warehouse=self.warehouse1,
            product=self.product
        )
        dest_stock = StockProduct.objects.get(
            warehouse=self.warehouse2,
            product=self.product
        )
        self.assertEqual(source_stock.quantity, 90)
        self.assertEqual(dest_stock.quantity, 10)
    
    def test_cancel_warehouse_transfer(self):
        """Test cancelling a warehouse transfer"""
        transfer = Transfer.objects.create(
            business=self.business,
            source_warehouse=self.warehouse1,
            destination_warehouse=self.warehouse2,
            created_by=self.user
        )
        TransferItem.objects.create(
            transfer=transfer,
            product=self.product,
            quantity=10,
            unit_cost=Decimal('10.00')
        )
        
        url = reverse('warehouse-transfers-cancel', args=[transfer.id])
        response = self.client.post(url, {'reason': 'Changed plans'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        transfer.refresh_from_db()
        self.assertEqual(transfer.status, 'cancelled')
        self.assertIn('Changed plans', transfer.notes)
    
    def test_cannot_complete_cancelled_transfer(self):
        """Test that cancelled transfers cannot be completed"""
        transfer = Transfer.objects.create(
            business=self.business,
            source_warehouse=self.warehouse1,
            destination_warehouse=self.warehouse2,
            created_by=self.user,
            status='cancelled'
        )
        
        url = reverse('warehouse-transfers-complete', args=[transfer.id])
        response = self.client.post(url, {})
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_cannot_cancel_completed_transfer(self):
        """Test that completed transfers cannot be cancelled"""
        transfer = Transfer.objects.create(
            business=self.business,
            source_warehouse=self.warehouse1,
            destination_warehouse=self.warehouse2,
            created_by=self.user,
            status='completed'
        )
        
        url = reverse('warehouse-transfers-cancel', args=[transfer.id])
        response = self.client.post(url, {'reason': 'Test'})
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_filter_by_status(self):
        """Test filtering transfers by status"""
        # Create transfers with different statuses
        Transfer.objects.create(
            business=self.business,
            source_warehouse=self.warehouse1,
            destination_warehouse=self.warehouse2,
            created_by=self.user,
            status='pending'
        )
        Transfer.objects.create(
            business=self.business,
            source_warehouse=self.warehouse1,
            destination_warehouse=self.warehouse2,
            created_by=self.user,
            status='completed'
        )
        
        url = reverse('warehouse-transfers-list')
        response = self.client.get(url, {'status': 'pending'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['status'], 'pending')


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
            business=self.business,
            location='Location 2',
            user=self.user
        )
        
        self.category = Category.objects.create(
            name='Test Category',
            business=self.business
        )
        self.product = Product.objects.create(
            name='Test Product',
            sku='TEST-001',
            business=self.business,
            category=self.category,
            cost=Decimal('10.00'),
            retail_price=Decimal('15.00')
        )
        
        # Create stock in warehouse
        self.stock = StockProduct.objects.create(
            warehouse=self.warehouse,
            product=self.product,
            business=self.business,
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
    
    def test_complete_storefront_transfer(self):
        """Test completing a storefront transfer"""
        transfer = Transfer.objects.create(
            business=self.business,
            source_warehouse=self.warehouse,
            destination_storefront=self.storefront,
            created_by=self.user
        )
        TransferItem.objects.create(
            transfer=transfer,
            product=self.product,
            quantity=10,
            unit_cost=Decimal('10.00')
        )
        
        url = reverse('storefront-transfers-complete', args=[transfer.id])
        response = self.client.post(url, {})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        transfer.refresh_from_db()
        self.assertEqual(transfer.status, 'completed')


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
            name='Category',
            business=self.business1
        )
        self.product = Product.objects.create(
            name='Product',
            sku='PROD-001',
            business=self.business1,
            category=self.category,
            cost=Decimal('10.00')
        )
        
        self.client = APIClient()
    
    def test_user_can_only_see_own_business_transfers(self):
        """Test that users can only see transfers from their own business"""
        # Create transfer for business1
        transfer1 = Transfer.objects.create(
            business=self.business1,
            source_warehouse=self.warehouse1,
            destination_warehouse=self.warehouse2,
            created_by=self.user1
        )
        
        # User 2 should not see user 1's transfers
        self.client.force_authenticate(user=self.user2)
        url = reverse('warehouse-transfers-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 0)
    
    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated users cannot access transfers"""
        url = reverse('warehouse-transfers-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
