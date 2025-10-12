"""
Test: Stock Product Search in Stock Adjustment Creation
Verifies the bug fix for products not appearing in Create Stock Adjustment modal
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from accounts.models import Business, BusinessMembership
from inventory.models import Product, Warehouse, Stock, StockProduct, Supplier
from inventory.stock_adjustments import StockAdjustment
from decimal import Decimal

User = get_user_model()


class StockAdjustmentSearchBugFixTest(TestCase):
    """
    Test case for verifying the stock product search bug fix.
    
    Bug: Products visible in Stock Products page were not appearing
    in Create Stock Adjustment modal search.
    
    Root Cause: Serializer queryset not filtered by user's business.
    
    Fix: Added get_fields() method to filter stock_product queryset
    by authenticated user's business.
    """
    
    def setUp(self):
        """Set up test data"""
        # Create two businesses
        self.business1 = Business.objects.create(
            name="DataLogique Systems",
            owner_email="owner1@test.com"
        )
        self.business2 = Business.objects.create(
            name="Competitor Corp",
            owner_email="owner2@test.com"
        )
        
        # Create users
        self.user1 = User.objects.create_user(
            email="mike@datalogique.com",
            name="Mike Tetteh",
            password="testpass123"
        )
        self.user2 = User.objects.create_user(
            email="john@competitor.com",
            name="John Doe",
            password="testpass123"
        )
        
        # Create memberships
        self.membership1 = BusinessMembership.objects.create(
            business=self.business1,
            user=self.user1,
            role='OWNER',
            is_active=True
        )
        self.membership2 = BusinessMembership.objects.create(
            business=self.business2,
            user=self.user2,
            role='OWNER',
            is_active=True
        )
        
        # Create warehouses
        self.warehouse1 = Warehouse.objects.create(
            name="Rawlings Park Warehouse",
            address="123 Main St"
        )
        self.warehouse2 = Warehouse.objects.create(
            name="Competitor Warehouse",
            address="456 Oak Ave"
        )
        
        # Link warehouses to businesses
        from inventory.models import BusinessWarehouse
        BusinessWarehouse.objects.create(
            business=self.business1,
            warehouse=self.warehouse1
        )
        BusinessWarehouse.objects.create(
            business=self.business2,
            warehouse=self.warehouse2
        )
        
        # Create products
        self.product1 = Product.objects.create(
            business=self.business1,
            name="10mm Armoured Cable 50m",
            sku="ELEC-0007",
            description="Electrical cable"
        )
        self.product2 = Product.objects.create(
            business=self.business2,
            name="10mm Steel Rod",
            sku="STEEL-001",
            description="Construction steel"
        )
        
        # Create suppliers
        self.supplier1 = Supplier.objects.create(
            business=self.business1,
            name="Cable Supplier Ltd"
        )
        self.supplier2 = Supplier.objects.create(
            business=self.business2,
            name="Steel Supplier Inc"
        )
        
        # Create stocks
        self.stock1 = Stock.objects.create(
            warehouse=self.warehouse1,
            arrival_date="2025-01-01"
        )
        self.stock2 = Stock.objects.create(
            warehouse=self.warehouse2,
            arrival_date="2025-01-01"
        )
        
        # Create stock products
        self.stock_product1 = StockProduct.objects.create(
            stock=self.stock1,
            product=self.product1,
            supplier=self.supplier1,
            quantity=26,
            unit_cost=Decimal('12.00'),
            retail_price=Decimal('60.00')
        )
        self.stock_product2 = StockProduct.objects.create(
            stock=self.stock2,
            product=self.product2,
            supplier=self.supplier2,
            quantity=50,
            unit_cost=Decimal('8.00'),
            retail_price=Decimal('40.00')
        )
        
        # Create API client
        self.client = APIClient()
    
    def test_stock_product_search_filters_by_business(self):
        """
        Test that stock product search only returns products from user's business.
        
        This is the core fix - previously all products were visible.
        """
        # Authenticate as user1 (DataLogique Systems)
        self.client.force_authenticate(user=self.user1)
        
        # Search for "10mm" - should find ONLY business1's product
        response = self.client.get('/inventory/api/stock-products/?search=10mm')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Should have exactly 1 result (not 2)
        self.assertEqual(data['count'], 1, 
            "Should only find products from user's business")
        
        # Verify it's the correct product
        result = data['results'][0]
        self.assertEqual(result['product']['sku'], 'ELEC-0007')
        self.assertEqual(result['product']['name'], '10mm Armoured Cable 50m')
        
        # Verify it's NOT the competitor's product
        self.assertNotEqual(result['product']['sku'], 'STEEL-001')
    
    def test_other_business_products_not_visible(self):
        """
        Test that user2 cannot see user1's products and vice versa.
        
        Security test - ensures business isolation.
        """
        # Authenticate as user2 (Competitor Corp)
        self.client.force_authenticate(user=self.user2)
        
        # Search for "ELEC-0007" (DataLogique's product)
        response = self.client.get('/inventory/api/stock-products/?search=ELEC-0007')
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Should have 0 results
        self.assertEqual(data['count'], 0,
            "Should not see other business's products")
    
    def test_create_adjustment_with_searched_product(self):
        """
        Test the complete user flow: search → find product → create adjustment.
        
        This was the broken flow that the bug fix addresses.
        """
        # Authenticate as user1
        self.client.force_authenticate(user=self.user1)
        
        # Step 1: Search for product
        search_response = self.client.get('/inventory/api/stock-products/?search=10mm')
        self.assertEqual(search_response.status_code, 200)
        
        search_data = search_response.json()
        self.assertEqual(search_data['count'], 1)
        
        # Step 2: Get stock product ID from search result
        stock_product_id = search_data['results'][0]['id']
        
        # Step 3: Create adjustment using the found product
        adjustment_data = {
            'stock_product': stock_product_id,
            'adjustment_type': 'DAMAGE',
            'quantity': -5,
            'reason': 'Water damage during storage'
        }
        
        create_response = self.client.post(
            '/inventory/api/stock-adjustments/',
            adjustment_data,
            format='json'
        )
        
        # Should succeed
        self.assertEqual(create_response.status_code, 201,
            f"Failed to create adjustment: {create_response.json()}")
        
        # Verify adjustment details
        adjustment = create_response.json()
        self.assertEqual(
            adjustment['stock_product_details']['product_name'],
            '10mm Armoured Cable 50m'
        )
        self.assertEqual(adjustment['quantity'], -5)
        self.assertEqual(adjustment['adjustment_type'], 'DAMAGE')
    
    def test_cannot_create_adjustment_with_other_business_product(self):
        """
        Test that user cannot create adjustment for another business's product.
        
        Security test - validates business isolation at creation level.
        """
        # Authenticate as user1 (DataLogique)
        self.client.force_authenticate(user=self.user1)
        
        # Try to create adjustment using user2's product
        adjustment_data = {
            'stock_product': str(self.stock_product2.id),  # Competitor's product
            'adjustment_type': 'DAMAGE',
            'quantity': -5,
            'reason': 'Attempted cross-business adjustment'
        }
        
        response = self.client.post(
            '/inventory/api/stock-adjustments/',
            adjustment_data,
            format='json'
        )
        
        # Should fail with validation error
        self.assertEqual(response.status_code, 400)
        self.assertIn('stock_product', response.json() or {})
    
    def test_serializer_queryset_filtered_by_business(self):
        """
        Test the serializer's get_fields() method directly.
        
        Unit test for the actual fix implementation.
        """
        from inventory.adjustment_serializers import StockAdjustmentCreateSerializer
        from rest_framework.test import APIRequestFactory
        from rest_framework.request import Request
        
        factory = APIRequestFactory()
        request = factory.get('/')
        request.user = self.user1
        drf_request = Request(request)
        
        # Create serializer with request context
        serializer = StockAdjustmentCreateSerializer(
            context={'request': drf_request}
        )
        
        # Get the stock_product field queryset
        stock_product_field = serializer.fields['stock_product']
        queryset = stock_product_field.queryset
        
        # Should only contain business1's products
        self.assertEqual(queryset.count(), 1,
            "Serializer queryset should be filtered by business")
        
        # Verify it's the correct product
        self.assertEqual(queryset.first().id, self.stock_product1.id)
        
        # Verify competitor's product is NOT in queryset
        self.assertNotIn(
            self.stock_product2.id,
            [sp.id for sp in queryset],
            "Other business's products should not be in queryset"
        )
    
    def test_unauthenticated_request_returns_empty_queryset(self):
        """
        Test that unauthenticated requests get empty queryset.
        
        Security test - prevents data leakage.
        """
        from inventory.adjustment_serializers import StockAdjustmentCreateSerializer
        from rest_framework.test import APIRequestFactory
        from rest_framework.request import Request
        
        factory = APIRequestFactory()
        request = factory.get('/')
        # No user authentication
        drf_request = Request(request)
        
        serializer = StockAdjustmentCreateSerializer(
            context={'request': drf_request}
        )
        
        # Should have empty queryset
        queryset = serializer.fields['stock_product'].queryset
        self.assertEqual(queryset.count(), 0,
            "Unauthenticated requests should get empty queryset")


if __name__ == '__main__':
    import django
    django.setup()
    
    from django.test.runner import DiscoverRunner
    runner = DiscoverRunner(verbosity=2)
    failures = runner.run_tests(['__main__'])
    
    if failures == 0:
        print("\n✅ All tests passed! Bug fix verified.")
    else:
        print(f"\n❌ {failures} test(s) failed!")
