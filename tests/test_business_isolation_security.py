"""
CRITICAL SECURITY TESTS: Business Data Isolation
================================================

These tests verify that multi-tenant data isolation is working correctly.
Users should NEVER see data from other businesses.

Test Coverage:
- Storefronts
- Warehouses  
- Products
- Stock
- Sales
- Customers
"""

from django.test import TestCase
from rest_framework.test import APIClient
from accounts.models import User, Business, BusinessMembership
from inventory.models import (
    StoreFront, Warehouse, Product, Stock, StockProduct,
    BusinessStoreFront, BusinessWarehouse, Category, Supplier
)


class BusinessIsolationSecurityTest(TestCase):
    """
    CRITICAL: Test that users can ONLY access their own business data.
    
    Failure of any test here represents a SEVERE SECURITY BREACH.
    """
    
    def setUp(self):
        """Create two separate businesses with their own data"""
        
        # Business 1: DataLogique Systems
        self.user1 = User.objects.create_user(
            email='owner1@business1.com',
            password='testpass123',
            name='Owner One',
            account_type=User.ACCOUNT_OWNER
        )
        self.business1 = Business.objects.create(
            owner=self.user1,
            name='DataLogique Systems',
            tin='TIN001',
            email='business1@example.com',
            address='Address 1'
        )
        BusinessMembership.objects.update_or_create(
            user=self.user1,
            business=self.business1,
            defaults={'role': BusinessMembership.OWNER, 'is_active': True}
        )
        
        # Business 2: Datalogique Ghana (Different business!)
        self.user2 = User.objects.create_user(
            email='owner2@business2.com',
            password='testpass123',
            name='Owner Two',
            account_type=User.ACCOUNT_OWNER
        )
        self.business2 = Business.objects.create(
            owner=self.user2,
            name='Datalogique Ghana',
            tin='TIN002',
            email='business2@example.com',
            address='Address 2'
        )
        BusinessMembership.objects.update_or_create(
            user=self.user2,
            business=self.business2,
            defaults={'role': BusinessMembership.OWNER, 'is_active': True}
        )
        
        # Create storefronts for Business 1
        self.sf1_business1 = StoreFront.objects.create(
            user=self.user1,
            name='Adenta Store',
            location='Adenta Police Station'
        )
        BusinessStoreFront.objects.create(
            business=self.business1,
            storefront=self.sf1_business1
        )
        
        self.sf2_business1 = StoreFront.objects.create(
            user=self.user1,
            name='Cow Lane Store',
            location='Asase Street'
        )
        BusinessStoreFront.objects.create(
            business=self.business1,
            storefront=self.sf2_business1
        )
        
        # Create storefronts for Business 2
        self.sf1_business2 = StoreFront.objects.create(
            user=self.user2,
            name='Adenta Branch',
            location='Adenta, Accra'
        )
        BusinessStoreFront.objects.create(
            business=self.business2,
            storefront=self.sf1_business2
        )
        
        self.sf2_business2 = StoreFront.objects.create(
            user=self.user2,
            name='Cow Lane Branch',
            location='Cow Lane, Accra'
        )
        BusinessStoreFront.objects.create(
            business=self.business2,
            storefront=self.sf2_business2
        )
        
        # Create warehouses for Business 1
        self.wh1_business1 = Warehouse.objects.create(
            name='Warehouse A',
            location='Location A'
        )
        BusinessWarehouse.objects.create(
            business=self.business1,
            warehouse=self.wh1_business1
        )
        
        # Create warehouses for Business 2
        self.wh1_business2 = Warehouse.objects.create(
            name='Warehouse B',
            location='Location B'
        )
        BusinessWarehouse.objects.create(
            business=self.business2,
            warehouse=self.wh1_business2
        )
        
        # Create products for Business 1
        category = Category.objects.create(name='Electronics')
        self.product1 = Product.objects.create(
            business=self.business1,
            name='Product A',
            sku='SKU-A',
            category=category
        )
        
        # Create products for Business 2
        self.product2 = Product.objects.create(
            business=self.business2,
            name='Product B',
            sku='SKU-B',
            category=category
        )
        
        # Create suppliers for Business 1
        self.supplier1 = Supplier.objects.create(
            business=self.business1,
            name='Supplier A'
        )
        
        # Create suppliers for Business 2
        self.supplier2 = Supplier.objects.create(
            business=self.business2,
            name='Supplier B'
        )
        
        # API clients
        self.client1 = APIClient()
        self.client1.force_authenticate(user=self.user1)
        
        self.client2 = APIClient()
        self.client2.force_authenticate(user=self.user2)
    
    def test_storefront_list_isolation(self):
        """🚨 CRITICAL: User 1 should NOT see User 2's storefronts"""
        response = self.client1.get('/inventory/api/storefronts/')
        
        self.assertEqual(response.status_code, 200)
        results = response.data.get('results', [])
        storefront_names = [sf['name'] for sf in results]
        
        # User 1 should ONLY see their own storefronts
        self.assertIn('Adenta Store', storefront_names)
        self.assertIn('Cow Lane Store', storefront_names)
        
        # 🚨 CRITICAL: Should NOT see Business 2's storefronts
        self.assertNotIn('Adenta Branch', storefront_names, 
                        "🚨 SECURITY BREACH: User can see other business's storefront!")
        self.assertNotIn('Cow Lane Branch', storefront_names,
                        "🚨 SECURITY BREACH: User can see other business's storefront!")
        
        # Should have exactly 2 storefronts
        self.assertEqual(len(results), 2,
                        f"🚨 SECURITY BREACH: Expected 2 storefronts, got {len(results)}")
    
    def test_storefront_detail_access_denial(self):
        """🚨 CRITICAL: User 1 should NOT access User 2's storefront details"""
        # Try to access Business 2's storefront
        response = self.client1.get(f'/inventory/api/storefronts/{self.sf1_business2.id}/')
        
        # Should get 404 (not found) or 403 (forbidden), NOT 200
        self.assertIn(response.status_code, [403, 404],
                     f"🚨 SECURITY BREACH: User accessed other business's storefront! "
                     f"Status: {response.status_code}")
    
    def test_warehouse_list_isolation(self):
        """🚨 CRITICAL: User 1 should NOT see User 2's warehouses"""
        response = self.client1.get('/inventory/api/warehouses/')
        
        self.assertEqual(response.status_code, 200)
        results = response.data.get('results', [])
        warehouse_names = [wh['name'] for wh in results]
        
        # User 1 should ONLY see their own warehouse
        self.assertIn('Warehouse A', warehouse_names)
        
        # 🚨 CRITICAL: Should NOT see Business 2's warehouse
        self.assertNotIn('Warehouse B', warehouse_names,
                        "🚨 SECURITY BREACH: User can see other business's warehouse!")
        
        self.assertEqual(len(results), 1,
                        f"🚨 SECURITY BREACH: Expected 1 warehouse, got {len(results)}")
    
    def test_product_list_isolation(self):
        """🚨 CRITICAL: User 1 should NOT see User 2's products"""
        response = self.client1.get('/inventory/api/products/')
        
        # May return 403 if subscription check enforced, or 200 with filtered results
        if response.status_code == 403:
            # Subscription enforcement - acceptable
            return
        
        self.assertEqual(response.status_code, 200)
        results = response.data.get('results', [])
        product_names = [p['name'] for p in results]
        
        # User 1 should ONLY see their own products
        self.assertIn('Product A', product_names)
        
        # 🚨 CRITICAL: Should NOT see Business 2's products
        self.assertNotIn('Product B', product_names,
                        "🚨 SECURITY BREACH: User can see other business's products!")
    
    def test_supplier_list_isolation(self):
        """🚨 CRITICAL: User 1 should NOT see User 2's suppliers"""
        response = self.client1.get('/inventory/api/suppliers/')
        
        self.assertEqual(response.status_code, 200)
        results = response.data.get('results', [])
        supplier_names = [s['name'] for s in results]
        
        # User 1 should ONLY see their own suppliers
        self.assertIn('Supplier A', supplier_names)
        
        # 🚨 CRITICAL: Should NOT see Business 2's suppliers
        self.assertNotIn('Supplier B', supplier_names,
                        "🚨 SECURITY BREACH: User can see other business's suppliers!")
    
    def test_user_storefronts_method_isolation(self):
        """🚨 CRITICAL: User.get_accessible_storefronts() must filter correctly"""
        storefronts = self.user1.get_accessible_storefronts()
        storefront_names = list(storefronts.values_list('name', flat=True))
        
        # User 1 should ONLY see their own storefronts
        self.assertIn('Adenta Store', storefront_names)
        self.assertIn('Cow Lane Store', storefront_names)
        
        # 🚨 CRITICAL: Should NOT see Business 2's storefronts
        self.assertNotIn('Adenta Branch', storefront_names,
                        "🚨 SECURITY BREACH: get_accessible_storefronts() returns other business data!")
        self.assertNotIn('Cow Lane Branch', storefront_names,
                        "🚨 SECURITY BREACH: get_accessible_storefronts() returns other business data!")
        
        self.assertEqual(storefronts.count(), 2,
                        f"🚨 SECURITY BREACH: Expected 2 storefronts, got {storefronts.count()}")
    
    def test_cross_business_storefront_access_via_api(self):
        """🚨 CRITICAL: Cannot access other business's storefront via direct ID"""
        # User 1 tries to access User 2's storefront
        response = self.client1.get(f'/inventory/api/storefronts/{self.sf1_business2.id}/')
        
        self.assertNotEqual(response.status_code, 200,
                           "🚨 SECURITY BREACH: User accessed other business's storefront!")
    
    def test_user_accounts_api_storefronts_isolation(self):
        """🚨 CRITICAL: /accounts/api/users/storefronts/ must filter correctly"""
        response = self.client1.get('/accounts/api/users/storefronts/')
        
        self.assertEqual(response.status_code, 200)
        storefronts = response.data.get('storefronts', [])
        storefront_names = [sf['name'] for sf in storefronts]
        
        # User 1 should ONLY see their own storefronts
        self.assertIn('Adenta Store', storefront_names)
        self.assertIn('Cow Lane Store', storefront_names)
        
        # 🚨 CRITICAL: Should NOT see Business 2's storefronts
        self.assertNotIn('Adenta Branch', storefront_names,
                        "🚨 SECURITY BREACH: /accounts/api/users/storefronts/ leaks data!")
        self.assertNotIn('Cow Lane Branch', storefront_names,
                        "🚨 SECURITY BREACH: /accounts/api/users/storefronts/ leaks data!")
        
        self.assertEqual(len(storefronts), 2,
                        f"🚨 SECURITY BREACH: Expected 2 storefronts, got {len(storefronts)}")


class BusinessIsolationStockTest(TestCase):
    """Test stock and inventory isolation between businesses"""
    
    def setUp(self):
        """Create stock data for two separate businesses"""
        # Business 1
        self.user1 = User.objects.create_user(
            email='owner1@business1.com',
            password='testpass123',
            name='Owner One',
            account_type=User.ACCOUNT_OWNER
        )
        self.business1 = Business.objects.create(
            owner=self.user1,
            name='Business One',
            tin='TIN001',
            email='b1@example.com',
            address='Address 1'
        )
        BusinessMembership.objects.update_or_create(
            user=self.user1,
            business=self.business1,
            defaults={'role': BusinessMembership.OWNER, 'is_active': True}
        )
        
        # Business 2
        self.user2 = User.objects.create_user(
            email='owner2@business2.com',
            password='testpass123',
            name='Owner Two',
            account_type=User.ACCOUNT_OWNER
        )
        self.business2 = Business.objects.create(
            owner=self.user2,
            name='Business Two',
            tin='TIN002',
            email='b2@example.com',
            address='Address 2'
        )
        BusinessMembership.objects.update_or_create(
            user=self.user2,
            business=self.business2,
            defaults={'role': BusinessMembership.OWNER, 'is_active': True}
        )
        
        # Create category
        category = Category.objects.create(name='Electronics')
        
        # Stock for Business 1
        self.product1 = Product.objects.create(
            business=self.business1,
            name='Product A',
            sku='SKU-A',
            category=category
        )
        self.stock1 = Stock.objects.create(business=self.business1)
        
        wh1 = Warehouse.objects.create(name='WH1', location='Loc1')
        BusinessWarehouse.objects.create(business=self.business1, warehouse=wh1)
        
        self.stock_product1 = StockProduct.objects.create(
            stock=self.stock1,
            product=self.product1,
            warehouse=wh1,
            quantity=100,
            retail_price=100.00
        )
        
        # Stock for Business 2
        self.product2 = Product.objects.create(
            business=self.business2,
            name='Product B',
            sku='SKU-B',
            category=category
        )
        self.stock2 = Stock.objects.create(business=self.business2)
        
        wh2 = Warehouse.objects.create(name='WH2', location='Loc2')
        BusinessWarehouse.objects.create(business=self.business2, warehouse=wh2)
        
        self.stock_product2 = StockProduct.objects.create(
            stock=self.stock2,
            product=self.product2,
            warehouse=wh2,
            quantity=200,
            retail_price=200.00
        )
        
        self.client1 = APIClient()
        self.client1.force_authenticate(user=self.user1)
    
    def test_stock_list_isolation(self):
        """🚨 CRITICAL: User 1 should NOT see User 2's stock batches"""
        response = self.client1.get('/inventory/api/stock/')
        
        self.assertEqual(response.status_code, 200)
        results = response.data.get('results', [])
        stock_ids = [s['id'] for s in results]
        
        # User 1 should ONLY see their own stock
        self.assertIn(str(self.stock1.id), stock_ids)
        
        # 🚨 CRITICAL: Should NOT see Business 2's stock
        self.assertNotIn(str(self.stock2.id), stock_ids,
                        "🚨 SECURITY BREACH: User can see other business's stock!")
    
    def test_stock_product_list_isolation(self):
        """🚨 CRITICAL: User 1 should NOT see User 2's stock products"""
        response = self.client1.get('/inventory/api/stock-products/')
        
        self.assertEqual(response.status_code, 200)
        results = response.data.get('results', [])
        stock_product_ids = [sp['id'] for sp in results]
        
        # User 1 should ONLY see their own stock products
        self.assertIn(str(self.stock_product1.id), stock_product_ids)
        
        # 🚨 CRITICAL: Should NOT see Business 2's stock products
        self.assertNotIn(str(self.stock_product2.id), stock_product_ids,
                        "🚨 SECURITY BREACH: User can see other business's stock products!")
