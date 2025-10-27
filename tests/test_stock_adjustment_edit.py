"""
Test Stock Adjustment Edit Functionality
"""
import sys
sys.path.insert(0, '/home/teejay/Documents/Projects/pos/backend')

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from accounts.models import Business, BusinessMembership
from inventory.models import Category, Product, Supplier, Warehouse, Stock, StockProduct, BusinessWarehouse
from inventory.stock_adjustments import StockAdjustment

User = get_user_model()


class StockAdjustmentEditTest(TestCase):
    def setUp(self):
        # Create owner
        self.owner = User.objects.create_user(
            email='owner@test.com',
            password='testpass123',
            name='Owner'
        )
        self.owner.account_type = User.ACCOUNT_OWNER
        self.owner.is_active = True
        self.owner.save()
        
        # Create business (automatically creates owner membership)
        self.business = Business.objects.create(
            owner=self.owner,
            name='Test Business',
            tin='TIN123',
            email='biz@test.com',
            address='123 Test St'
        )
        
        # Create category and product
        self.category = Category.objects.create(name='Electronics')
        self.product = Product.objects.create(
            business=self.business,
            name='Test Product',
            sku='TEST-001',
            category=self.category
        )
        
        # Create warehouse
        self.warehouse = Warehouse.objects.create(name='Main Warehouse', location='Location A')
        BusinessWarehouse.objects.create(business=self.business, warehouse=self.warehouse)
        
        # Create stock
        self.stock = Stock.objects.create(business=self.business, description='Test stock')
        self.supplier = Supplier.objects.create(
            business=self.business,
            name='Test Supplier',
            email='supplier@test.com'
        )

        # Create stock product
        self.stock_product = StockProduct.objects.create(
            stock=self.stock,
            product=self.product,
            supplier=self.supplier,
            quantity=100,
            unit_cost=Decimal('10.00'),
            retail_price=Decimal('15.00')
        )

        # Create API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.owner)
    
    def test_can_view_adjustment_detail(self):
        """Test that we can retrieve an adjustment by ID"""
        adjustment = StockAdjustment.objects.create(
            business=self.business,
            stock_product=self.stock_product,
            adjustment_type='DAMAGE',
            quantity=-5,
            unit_cost=Decimal('10.00'),
            total_cost=Decimal('50.00'),
            reason='Test damage',
            created_by=self.owner,
            status='PENDING',
            requires_approval=True
        )
        
        response = self.client.get(f'/inventory/api/stock-adjustments/{adjustment.id}/')
        
        print(f"\n=== VIEW ADJUSTMENT DETAIL ===")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(adjustment.id))
        self.assertEqual(response.data['adjustment_type'], 'DAMAGE')
        self.assertEqual(response.data['quantity'], -5)
    
    def test_can_edit_pending_adjustment(self):
        """Test that we can edit a PENDING adjustment"""
        adjustment = StockAdjustment.objects.create(
            business=self.business,
            stock_product=self.stock_product,
            adjustment_type='DAMAGE',
            quantity=-5,
            unit_cost=Decimal('10.00'),
            total_cost=Decimal('50.00'),
            reason='Original reason',
            created_by=self.owner,
            status='PENDING',
            requires_approval=True
        )
        
        # Update the adjustment
        update_data = {
            'stock_product': str(self.stock_product.id),
            'adjustment_type': 'THEFT',
            'quantity': -8,
            'reason': 'Updated reason - theft instead of damage',
            'unit_cost': '10.00'
        }
        
        response = self.client.put(
            f'/inventory/api/stock-adjustments/{adjustment.id}/',
            update_data,
            format='json'
        )
        
        print(f"\n=== EDIT PENDING ADJUSTMENT ===")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify changes
        adjustment.refresh_from_db()
        self.assertEqual(adjustment.adjustment_type, 'THEFT')
        self.assertEqual(adjustment.quantity, -8)
        self.assertEqual(adjustment.reason, 'Updated reason - theft instead of damage')
        self.assertEqual(adjustment.total_cost, Decimal('80.00'))  # 8 * 10
    
    def test_cannot_edit_approved_adjustment(self):
        """Test that we CANNOT edit an APPROVED adjustment"""
        adjustment = StockAdjustment.objects.create(
            business=self.business,
            stock_product=self.stock_product,
            adjustment_type='DAMAGE',
            quantity=-5,
            unit_cost=Decimal('10.00'),
            total_cost=Decimal('50.00'),
            reason='Approved adjustment',
            created_by=self.owner,
            status='APPROVED',
            requires_approval=True,
            approved_by=self.owner
        )
        
        update_data = {
            'stock_product': str(self.stock_product.id),
            'adjustment_type': 'THEFT',
            'quantity': -8,
            'reason': 'Try to update',
            'unit_cost': '10.00'
        }
        
        response = self.client.put(
            f'/inventory/api/stock-adjustments/{adjustment.id}/',
            update_data,
            format='json'
        )
        
        print(f"\n=== TRY TO EDIT APPROVED ADJUSTMENT ===")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Cannot edit adjustment', response.json()['error'])
    
    def test_cannot_edit_completed_adjustment(self):
        """Test that we CANNOT edit a COMPLETED adjustment"""
        adjustment = StockAdjustment.objects.create(
            business=self.business,
            stock_product=self.stock_product,
            adjustment_type='DAMAGE',
            quantity=-5,
            unit_cost=Decimal('10.00'),
            total_cost=Decimal('50.00'),
            reason='Completed adjustment',
            created_by=self.owner,
            status='COMPLETED',
            requires_approval=True,
            approved_by=self.owner
        )
        
        update_data = {
            'stock_product': str(self.stock_product.id),
            'adjustment_type': 'THEFT',
            'quantity': -8,
            'reason': 'Try to update',
            'unit_cost': '10.00'
        }
        
        response = self.client.put(
            f'/inventory/api/stock-adjustments/{adjustment.id}/',
            update_data,
            format='json'
        )
        
        print(f"\n=== TRY TO EDIT COMPLETED ADJUSTMENT ===")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Cannot edit adjustment', response.json()['error'])
    
    def test_partial_update_pending_adjustment(self):
        """Test that we can partially update a PENDING adjustment"""
        adjustment = StockAdjustment.objects.create(
            business=self.business,
            stock_product=self.stock_product,
            adjustment_type='DAMAGE',
            quantity=-5,
            unit_cost=Decimal('10.00'),
            total_cost=Decimal('50.00'),
            reason='Original reason',
            created_by=self.owner,
            status='PENDING',
            requires_approval=True
        )
        
        # Partial update - only change reason
        update_data = {
            'reason': 'Updated reason only'
        }
        
        response = self.client.patch(
            f'/inventory/api/stock-adjustments/{adjustment.id}/',
            update_data,
            format='json'
        )
        
        print(f"\n=== PARTIAL UPDATE PENDING ADJUSTMENT ===")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify only reason changed
        adjustment.refresh_from_db()
        self.assertEqual(adjustment.reason, 'Updated reason only')
        self.assertEqual(adjustment.adjustment_type, 'DAMAGE')  # Unchanged
        self.assertEqual(adjustment.quantity, -5)  # Unchanged


if __name__ == '__main__':
    import unittest
    
    # Run tests
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(StockAdjustmentEditTest)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
