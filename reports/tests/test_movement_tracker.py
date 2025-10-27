"""
Unit tests for MovementTracker service.

Tests the MovementTracker's ability to aggregate movements from multiple sources
(legacy StockAdjustment, new Transfer, and Sales) and provide unified reporting.
"""

from decimal import Decimal
from datetime import datetime, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import Business
from inventory.models import Warehouse, Product, Stock, StockProduct, Category
from inventory.stock_adjustments import StockAdjustment
from reports.services import MovementTracker


User = get_user_model()


class MovementTrackerTestCase(TestCase):
    """Test cases for MovementTracker service."""
    
    def setUp(self):
        """Set up test data."""
        # Create user
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.user.full_name = 'Test User'
        self.user.save()
        
        # Create business
        self.business = Business.objects.create(
            name='Test Business',
            owner=self.user
        )
        
        # Create category (no business field - shared across businesses)
        self.category = Category.objects.create(
            name='Electronics-Test'
        )
        
        # Create warehouses (no business field - linked via BusinessWarehouse)
        self.warehouse_a = Warehouse.objects.create(
            name='Warehouse A',
            location='Location A'
        )
        
        self.warehouse_b = Warehouse.objects.create(
            name='Warehouse B',
            location='Location B'
        )
        
        # Create product
        self.product = Product.objects.create(
            name='Test Product',
            sku='TEST-001',
            category=self.category,
            business=self.business
        )
        
        # Create stock
        self.stock_a = Stock.objects.create(
            arrival_date=timezone.now().date(),
            business=self.business
        )
        
        # Create stock products
        self.stock_product_a = StockProduct.objects.create(
            stock=self.stock_a,
            warehouse=self.warehouse_a,
            product=self.product,
            quantity=100,
            unit_cost=Decimal('10.00')
        )
        
        self.stock_b = Stock.objects.create(
            arrival_date=timezone.now().date(),
            business=self.business
        )
        
        self.stock_product_b = StockProduct.objects.create(
            stock=self.stock_b,
            warehouse=self.warehouse_b,
            product=self.product,
            quantity=0,
            unit_cost=Decimal('10.00')
        )
    
    def test_get_movements_with_legacy_adjustments(self):
        """Test getting movements from legacy StockAdjustment records."""
        # Create a transfer using StockAdjustment (old system)
        reference = 'TRF-TEST-001'
        
        # TRANSFER_OUT from warehouse A
        adj_out = StockAdjustment.objects.create(
            stock_product=self.stock_product_a,
            adjustment_type='TRANSFER_OUT',
            quantity=-10,
            unit_cost=Decimal('10.00'),
            reference_number=reference,
            reason='Test transfer',
            created_by=self.user,
            business=self.business,
            status='COMPLETED'
        )
        
        # TRANSFER_IN to warehouse B
        adj_in = StockAdjustment.objects.create(
            stock_product=self.stock_product_b,
            adjustment_type='TRANSFER_IN',
            quantity=10,
            unit_cost=Decimal('10.00'),
            reference_number=reference,
            reason='Test transfer',
            created_by=self.user,
            business=self.business,
            status='COMPLETED'
        )
        
        # Get movements
        movements = MovementTracker.get_movements(
            business_id=str(self.business.id)
        )
        
        # Should have 2 movements (OUT and IN)
        self.assertEqual(len(movements), 2)
        
        # Check transfer movements
        transfer_movements = [m for m in movements if m['type'] == 'transfer']
        self.assertEqual(len(transfer_movements), 2)
        
        # Verify movement details
        out_movement = next(m for m in transfer_movements if m['direction'] == 'out')
        self.assertEqual(out_movement['quantity'], 10)
        self.assertEqual(out_movement['source_type'], 'legacy_adjustment')
        self.assertEqual(out_movement['reference_number'], reference)
        self.assertEqual(out_movement['product_name'], 'Test Product')
        
        in_movement = next(m for m in transfer_movements if m['direction'] == 'in')
        self.assertEqual(in_movement['quantity'], 10)
        self.assertEqual(in_movement['reference_number'], reference)
    
    def test_get_movements_with_shrinkage(self):
        """Test getting shrinkage movements."""
        # Create shrinkage adjustments
        StockAdjustment.objects.create(
            stock_product=self.stock_product_a,
            adjustment_type='THEFT',
            quantity=-5,
            unit_cost=Decimal('10.00'),
            reason='Stolen items',
            created_by=self.user,
            business=self.business,
            status='COMPLETED'
        )
        
        StockAdjustment.objects.create(
            stock_product=self.stock_product_a,
            adjustment_type='DAMAGE',
            quantity=-3,
            unit_cost=Decimal('10.00'),
            reason='Damaged in storage',
            created_by=self.user,
            business=self.business,
            status='COMPLETED'
        )
        
        # Get movements
        movements = MovementTracker.get_movements(
            business_id=str(self.business.id),
            movement_types=['shrinkage']
        )
        
        # Should have 2 shrinkage movements
        self.assertEqual(len(movements), 2)
        
        # Verify all are shrinkage type
        for movement in movements:
            self.assertEqual(movement['type'], 'shrinkage')
            self.assertEqual(movement['source_type'], 'legacy_adjustment')
    
    def test_get_movements_with_date_filter(self):
        """Test filtering movements by date range."""
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        
        # Create adjustment today
        StockAdjustment.objects.create(
            stock_product=self.stock_product_a,
            adjustment_type='TRANSFER_OUT',
            quantity=-10,
            unit_cost=Decimal('10.00'),
            created_by=self.user,
            business=self.business,
            status='COMPLETED'
        )
        
        # Get movements for today
        movements = MovementTracker.get_movements(
            business_id=str(self.business.id),
            start_date=today,
            end_date=today
        )
        
        # Should have 1 movement
        self.assertEqual(len(movements), 1)
        
        # Get movements for yesterday (should be empty)
        movements = MovementTracker.get_movements(
            business_id=str(self.business.id),
            start_date=yesterday,
            end_date=yesterday
        )
        
        self.assertEqual(len(movements), 0)
    
    def test_get_movements_with_warehouse_filter(self):
        """Test filtering movements by warehouse."""
        # Create transfers for both warehouses
        StockAdjustment.objects.create(
            stock_product=self.stock_product_a,
            adjustment_type='TRANSFER_OUT',
            quantity=-10,
            unit_cost=Decimal('10.00'),
            created_by=self.user,
            business=self.business
        )
        
        StockAdjustment.objects.create(
            stock_product=self.stock_product_b,
            adjustment_type='TRANSFER_IN',
            quantity=10,
            unit_cost=Decimal('10.00'),
            created_by=self.user,
            business=self.business
        )
        
        # Get movements for warehouse A only
        movements = MovementTracker.get_movements(
            business_id=str(self.business.id),
            warehouse_id=str(self.warehouse_a.id)
        )
        
        # Should have 1 movement (from warehouse A)
        self.assertEqual(len(movements), 1)
        self.assertEqual(movements[0]['source_location'], 'Warehouse A')
    
    def test_get_summary(self):
        """Test getting movement summary statistics."""
        # Create various movements
        # Transfer OUT
        StockAdjustment.objects.create(
            stock_product=self.stock_product_a,
            adjustment_type='TRANSFER_OUT',
            quantity=-10,
            unit_cost=Decimal('10.00'),
            created_by=self.user,
            business=self.business,
            status='COMPLETED'
        )
        
        # Transfer IN
        StockAdjustment.objects.create(
            stock_product=self.stock_product_b,
            adjustment_type='TRANSFER_IN',
            quantity=10,
            unit_cost=Decimal('10.00'),
            created_by=self.user,
            business=self.business,
            status='COMPLETED'
        )
        
        # Shrinkage
        StockAdjustment.objects.create(
            stock_product=self.stock_product_a,
            adjustment_type='THEFT',
            quantity=-5,
            unit_cost=Decimal('10.00'),
            created_by=self.user,
            business=self.business,
            status='COMPLETED'
        )
        
        # Get summary
        summary = MovementTracker.get_summary(
            business_id=str(self.business.id)
        )
        
        # Verify summary
        self.assertEqual(summary['total_movements'], 3)
        self.assertEqual(summary['transfers_count'], 2)  # OUT and IN
        self.assertEqual(summary['shrinkage_count'], 1)
        self.assertEqual(summary['total_quantity_transferred'], 20)  # 10 out + 10 in
        self.assertEqual(summary['total_shrinkage_quantity'], 5)
        self.assertEqual(summary['total_value_transferred'], Decimal('200.00'))
        self.assertEqual(summary['total_shrinkage_value'], Decimal('50.00'))
    
    def test_movement_sorting(self):
        """Test that movements are sorted by date (most recent first)."""
        # Create movements at different times
        now = timezone.now()
        
        # Older movement
        adj1 = StockAdjustment.objects.create(
            stock_product=self.stock_product_a,
            adjustment_type='TRANSFER_OUT',
            quantity=-10,
            unit_cost=Decimal('10.00'),
            created_by=self.user,
            business=self.business
        )
        adj1.created_at = now - timedelta(hours=2)
        adj1.save()
        
        # Newer movement
        adj2 = StockAdjustment.objects.create(
            stock_product=self.stock_product_a,
            adjustment_type='THEFT',
            quantity=-5,
            unit_cost=Decimal('10.00'),
            created_by=self.user,
            business=self.business
        )
        adj2.created_at = now - timedelta(hours=1)
        adj2.save()
        
        # Get movements
        movements = MovementTracker.get_movements(
            business_id=str(self.business.id)
        )
        
        # Should be sorted newest first
        self.assertEqual(len(movements), 2)
        self.assertGreater(movements[0]['date'], movements[1]['date'])
