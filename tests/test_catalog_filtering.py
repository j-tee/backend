"""
Tests for server-side catalog filtering and pagination.

Tests both single storefront and multi-storefront catalog endpoints
with various filter combinations and pagination scenarios.
"""

from decimal import Decimal
from uuid import uuid4

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from accounts.models import Business, BusinessMembership
from inventory.models import (
    Category, StoreFront, Product, StockProduct, Stock,
    StoreFrontInventory, BusinessStoreFront, StoreFrontEmployee,
    Warehouse, BusinessWarehouse
)

User = get_user_model()


class CatalogFilteringTestCase(TestCase):
    """Test suite for catalog filtering and pagination."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create test user and business
        self.user = User.objects.create_user(
            email='owner@test.com',
            password='testpass123',
            name='Test Owner',
            account_type='OWNER'
        )
        
        self.business = Business.objects.create(
            name='Test Business',
            owner=self.user
        )
        
        # Get or create business membership (Business.save() auto-creates one)
        BusinessMembership.objects.get_or_create(
            business=self.business,
            user=self.user,
            defaults={
                'role': BusinessMembership.OWNER,
                'is_active': True
            }
        )
        
        # Create categories
        self.category_food = Category.objects.create(name='Food')
        self.category_beverages = Category.objects.create(name='Beverages')
        self.category_electronics = Category.objects.create(name='Electronics')
        
        # Create warehouse
        self.warehouse = Warehouse.objects.create(
            name='Main Warehouse'
        )
        BusinessWarehouse.objects.create(
            business=self.business,
            warehouse=self.warehouse
        )
        
        # Create storefronts
        self.storefront1 = StoreFront.objects.create(
            name='Store 1',
            user=self.user
        )
        BusinessStoreFront.objects.create(
            business=self.business,
            storefront=self.storefront1
        )
        
        self.storefront2 = StoreFront.objects.create(
            name='Store 2',
            user=self.user
        )
        BusinessStoreFront.objects.create(
            business=self.business,
            storefront=self.storefront2
        )
        
        # Create stock batch
        self.stock = Stock.objects.create(
            business=self.business,
            description='Test Stock Batch',
            arrival_date='2025-10-01'
        )
        
        # Create products with varying prices and categories
        self.products = []
        product_configs = [
            # (name, sku, barcode, category, retail_price)
            ('Sugar 1kg', 'SUG-001', '1234567890', self.category_food, '15.00'),
            ('Rice 5kg', 'RICE-001', '1234567891', self.category_food, '45.00'),
            ('Cooking Oil 1L', 'OIL-001', '1234567892', self.category_food, '25.00'),
            ('Coca Cola 500ml', 'COKE-001', '1234567893', self.category_beverages, '5.00'),
            ('Water 1.5L', 'WATER-001', '1234567894', self.category_beverages, '3.00'),
            ('Laptop HP', 'LAPTOP-001', '1234567895', self.category_electronics, '2500.00'),
            ('Mouse Wireless', 'MOUSE-001', '1234567896', self.category_electronics, '35.00'),
        ]
        
        for name, sku, barcode, category, price in product_configs:
            product = Product.objects.create(
                name=name,
                sku=sku,
                barcode=barcode,
                category=category,
                business=self.business,
                unit='pcs'
            )
            
            # Create stock product with pricing
            stock_product = StockProduct.objects.create(
                product=product,
                stock=self.stock,
                warehouse=self.warehouse,
                quantity=100,
                unit_cost=Decimal(price) * Decimal('0.7'),  # 30% markup
                retail_price=Decimal(price),
                wholesale_price=Decimal(price) * Decimal('0.9'),  # 10% discount
            )
            
            self.products.append({
                'product': product,
                'stock_product': stock_product,
                'price': Decimal(price)
            })
        
        # Add inventory to storefronts
        # Store 1: All products
        for item in self.products:
            StoreFrontInventory.objects.create(
                storefront=self.storefront1,
                product=item['product'],
                quantity=50
            )
        
        # Store 2: Only first 4 products
        for item in self.products[:4]:
            StoreFrontInventory.objects.create(
                storefront=self.storefront2,
                product=item['product'],
                quantity=30
            )
        
        # Authenticate client
        self.client.force_authenticate(user=self.user)
    
    def test_single_storefront_catalog_search_by_name(self):
        """Test searching by product name."""
        url = f'/inventory/api/storefronts/{self.storefront1.id}/sale-catalog/'
        response = self.client.get(url, {'search': 'sugar'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('products', response.data)
        self.assertEqual(len(response.data['products']), 1)
        self.assertEqual(response.data['products'][0]['product_name'], 'Sugar 1kg')
    
    def test_single_storefront_catalog_search_by_sku(self):
        """Test searching by SKU."""
        url = f'/inventory/api/storefronts/{self.storefront1.id}/sale-catalog/'
        response = self.client.get(url, {'search': 'RICE-001'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['products']), 1)
        self.assertEqual(response.data['products'][0]['sku'], 'RICE-001')
    
    def test_single_storefront_catalog_filter_by_category(self):
        """Test filtering by category."""
        url = f'/inventory/api/storefronts/{self.storefront1.id}/sale-catalog/'
        response = self.client.get(url, {'category': str(self.category_food.id)})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['products']), 3)  # Sugar, Rice, Oil
        for product in response.data['products']:
            self.assertEqual(product['category_name'], 'Food')
    
    def test_single_storefront_catalog_filter_by_price_range(self):
        """Test filtering by price range."""
        url = f'/inventory/api/storefronts/{self.storefront1.id}/sale-catalog/'
        response = self.client.get(url, {'min_price': '10', 'max_price': '50'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should get: Sugar (15), Rice (45), Oil (25), Mouse (35)
        self.assertEqual(len(response.data['products']), 4)
        for product in response.data['products']:
            price = Decimal(str(product['retail_price']))
            self.assertGreaterEqual(price, Decimal('10'))
            self.assertLessEqual(price, Decimal('50'))
    
    def test_single_storefront_catalog_combined_filters(self):
        """Test combining multiple filters."""
        url = f'/inventory/api/storefronts/{self.storefront1.id}/sale-catalog/'
        response = self.client.get(url, {
            'search': 'rice',
            'category': str(self.category_food.id),
            'max_price': '50'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['products']), 1)
        self.assertEqual(response.data['products'][0]['product_name'], 'Rice 5kg')
    
    def test_single_storefront_catalog_pagination(self):
        """Test pagination."""
        url = f'/inventory/api/storefronts/{self.storefront1.id}/sale-catalog/'
        response = self.client.get(url, {'page': 1, 'page_size': 3})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['page_size'], 3)
        self.assertEqual(len(response.data['products']), 3)
        self.assertIsNotNone(response.data['next'])
        self.assertEqual(response.data['current_page'], 1)
        self.assertEqual(response.data['count'], 7)  # Total products
    
    def test_single_storefront_catalog_pagination_page_2(self):
        """Test pagination page 2."""
        url = f'/inventory/api/storefronts/{self.storefront1.id}/sale-catalog/'
        response = self.client.get(url, {'page': 2, 'page_size': 3})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['products']), 3)
        self.assertEqual(response.data['current_page'], 2)
        self.assertIsNotNone(response.data['previous'])
    
    def test_single_storefront_catalog_in_stock_only(self):
        """Test in_stock_only parameter."""
        # Create a product with zero inventory
        out_of_stock = Product.objects.create(
            name='Out of Stock Product',
            sku='OOS-001',
            business=self.business,
            category=self.category_food
        )
        StockProduct.objects.create(
            product=out_of_stock,
            stock=self.stock,
            warehouse=self.warehouse,
            quantity=0,
            retail_price=Decimal('10.00')
        )
        StoreFrontInventory.objects.create(
            storefront=self.storefront1,
            product=out_of_stock,
            quantity=0
        )
        
        url = f'/inventory/api/storefronts/{self.storefront1.id}/sale-catalog/'
        
        # Default: in_stock_only=true
        response = self.client.get(url)
        product_names = [p['product_name'] for p in response.data['products']]
        self.assertNotIn('Out of Stock Product', product_names)
        
        # Explicit: in_stock_only=false
        response = self.client.get(url, {'in_stock_only': 'false'})
        product_names = [p['product_name'] for p in response.data['products']]
        self.assertIn('Out of Stock Product', product_names)
    
    def test_single_storefront_catalog_backward_compatibility_include_zero(self):
        """Test backward compatibility with include_zero parameter."""
        # Create a product with zero inventory
        out_of_stock = Product.objects.create(
            name='Zero Stock Product',
            sku='ZERO-001',
            business=self.business,
            category=self.category_food
        )
        StockProduct.objects.create(
            product=out_of_stock,
            stock=self.stock,
            warehouse=self.warehouse,
            quantity=0,
            retail_price=Decimal('10.00')
        )
        StoreFrontInventory.objects.create(
            storefront=self.storefront1,
            product=out_of_stock,
            quantity=0
        )
        
        url = f'/inventory/api/storefronts/{self.storefront1.id}/sale-catalog/'
        
        # include_zero=true should show zero-stock products
        response = self.client.get(url, {'include_zero': 'true'})
        product_names = [p['product_name'] for p in response.data['products']]
        self.assertIn('Zero Stock Product', product_names)
    
    def test_multi_storefront_catalog_search(self):
        """Test multi-storefront catalog search."""
        url = '/inventory/api/storefronts/multi-storefront-catalog/'
        response = self.client.get(url, {'search': 'coca'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['products']), 1)
        self.assertEqual(response.data['products'][0]['product_name'], 'Coca Cola 500ml')
        # Should have 2 locations (both storefronts)
        self.assertEqual(len(response.data['products'][0]['locations']), 2)
    
    def test_multi_storefront_catalog_filter_by_category(self):
        """Test multi-storefront catalog category filter."""
        url = '/inventory/api/storefronts/multi-storefront-catalog/'
        response = self.client.get(url, {'category': str(self.category_beverages.id)})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['products']), 2)  # Coke, Water
        for product in response.data['products']:
            self.assertEqual(product['category_name'], 'Beverages')
    
    def test_multi_storefront_catalog_filter_by_storefront(self):
        """Test filtering to specific storefronts."""
        url = '/inventory/api/storefronts/multi-storefront-catalog/'
        response = self.client.get(url, {'storefront': str(self.storefront2.id)})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Store 2 only has 4 products
        self.assertEqual(len(response.data['products']), 4)
        
        # Each product should only have Store 2 location
        for product in response.data['products']:
            self.assertEqual(len(product['locations']), 1)
            self.assertEqual(product['locations'][0]['storefront_id'], str(self.storefront2.id))
    
    def test_multi_storefront_catalog_filter_multiple_storefronts(self):
        """Test filtering to multiple specific storefronts."""
        url = '/inventory/api/storefronts/multi-storefront-catalog/'
        response = self.client.get(url, {
            'storefront': [str(self.storefront1.id), str(self.storefront2.id)]
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data['products']), 0)
    
    def test_multi_storefront_catalog_price_range(self):
        """Test multi-storefront catalog price filtering."""
        url = '/inventory/api/storefronts/multi-storefront-catalog/'
        response = self.client.get(url, {'min_price': '20', 'max_price': '100'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for product in response.data['products']:
            price = Decimal(str(product['retail_price']))
            self.assertGreaterEqual(price, Decimal('20'))
            self.assertLessEqual(price, Decimal('100'))
    
    def test_multi_storefront_catalog_total_available(self):
        """Test total_available aggregation across storefronts."""
        url = '/inventory/api/storefronts/multi-storefront-catalog/'
        response = self.client.get(url, {'search': 'sugar'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['products']), 1)
        
        product = response.data['products'][0]
        # Sugar is in both stores: 50 + 30 = 80
        self.assertEqual(product['total_available'], 80)
        self.assertEqual(len(product['locations']), 2)
    
    def test_multi_storefront_catalog_pagination(self):
        """Test multi-storefront catalog pagination."""
        url = '/inventory/api/storefronts/multi-storefront-catalog/'
        response = self.client.get(url, {'page': 1, 'page_size': 3})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['page_size'], 3)
        self.assertEqual(len(response.data['products']), 3)
        self.assertEqual(response.data['current_page'], 1)
        self.assertGreater(response.data['total_pages'], 1)
    
    def test_multi_storefront_catalog_combined_filters(self):
        """Test combining multiple filters on multi-storefront catalog."""
        url = '/inventory/api/storefronts/multi-storefront-catalog/'
        response = self.client.get(url, {
            'category': str(self.category_food.id),
            'max_price': '30',
            'search': 'oil'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['products']), 1)
        self.assertEqual(response.data['products'][0]['product_name'], 'Cooking Oil 1L')
    
    def test_catalog_response_structure(self):
        """Test that response has all required fields."""
        url = f'/inventory/api/storefronts/{self.storefront1.id}/sale-catalog/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check pagination fields
        self.assertIn('count', response.data)
        self.assertIn('next', response.data)
        self.assertIn('previous', response.data)
        self.assertIn('page_size', response.data)
        self.assertIn('total_pages', response.data)
        self.assertIn('current_page', response.data)
        self.assertIn('products', response.data)
        
        # Check product fields
        if response.data['products']:
            product = response.data['products'][0]
            required_fields = [
                'product_id', 'product_name', 'sku', 'barcode',
                'category_name', 'unit', 'available_quantity',
                'retail_price', 'stock_product_ids'
            ]
            for field in required_fields:
                self.assertIn(field, product)
    
    def test_multi_storefront_response_structure(self):
        """Test multi-storefront response structure."""
        url = '/inventory/api/storefronts/multi-storefront-catalog/'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check top-level fields
        self.assertIn('storefronts', response.data)
        self.assertIn('products', response.data)
        self.assertIn('count', response.data)
        
        # Check product fields
        if response.data['products']:
            product = response.data['products'][0]
            required_fields = [
                'product_id', 'product_name', 'sku', 'barcode',
                'category_name', 'total_available', 'locations',
                'retail_price', 'stock_product_ids'
            ]
            for field in required_fields:
                self.assertIn(field, product)
            
            # Check location structure
            if product['locations']:
                location = product['locations'][0]
                self.assertIn('storefront_id', location)
                self.assertIn('storefront_name', location)
                self.assertIn('available_quantity', location)
    
    def test_max_page_size_limit(self):
        """Test that page_size is capped at max_page_size."""
        url = f'/inventory/api/storefronts/{self.storefront1.id}/sale-catalog/'
        response = self.client.get(url, {'page_size': 500})  # Request more than max
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(response.data['page_size'], 200)  # Should be capped at 200
    
    def test_invalid_category_uuid(self):
        """Test that invalid category UUID is gracefully handled."""
        url = f'/inventory/api/storefronts/{self.storefront1.id}/sale-catalog/'
        response = self.client.get(url, {'category': 'invalid-uuid'})
        
        # Should still work, just ignore the invalid filter
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_invalid_price_values(self):
        """Test that invalid price values are gracefully handled."""
        url = f'/inventory/api/storefronts/{self.storefront1.id}/sale-catalog/'
        response = self.client.get(url, {'min_price': 'invalid', 'max_price': 'abc'})
        
        # Should still work, just ignore the invalid filters
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_empty_search_query(self):
        """Test that empty search query returns all products."""
        url = f'/inventory/api/storefronts/{self.storefront1.id}/sale-catalog/'
        response = self.client.get(url, {'search': ''})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['products']), 7)  # All products
    
    def test_no_results(self):
        """Test search with no matching results."""
        url = f'/inventory/api/storefronts/{self.storefront1.id}/sale-catalog/'
        response = self.client.get(url, {'search': 'nonexistent-product-xyz'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['products']), 0)
        self.assertEqual(response.data['count'], 0)
    
    def test_case_insensitive_search(self):
        """Test that search is case-insensitive."""
        url = f'/inventory/api/storefronts/{self.storefront1.id}/sale-catalog/'
        
        # Test uppercase
        response = self.client.get(url, {'search': 'SUGAR'})
        self.assertEqual(len(response.data['products']), 1)
        
        # Test lowercase
        response = self.client.get(url, {'search': 'sugar'})
        self.assertEqual(len(response.data['products']), 1)
        
        # Test mixed case
        response = self.client.get(url, {'search': 'SuGaR'})
        self.assertEqual(len(response.data['products']), 1)
