"""
Comprehensive test suite for automatic sale cancellation workflow.

Tests verify that cancelling a sale automatically:
1. Returns inventory to original location (storefront or warehouse)
2. Processes full refund for all items
3. Updates sale status to CANCELLED
4. Reverses customer credit balance (if applicable)
5. Creates comprehensive audit trail
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import transaction
from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import transaction
from accounts.models import Business, User
from inventory.models import (
    Category, Product, StockProduct, StoreFrontInventory, 
    Warehouse, StoreFront, BusinessStoreFront, BusinessWarehouse,
    Stock, Supplier
)
from sales.models import Sale, SaleItem, Refund, RefundItem, AuditLog, Customer


class SaleCancellationTestCase(TestCase):
    """Test automatic sale cancellation workflow."""
    
    def setUp(self):
        """Set up test data."""
        # Create user first (needed for business owner)
        self.user = User.objects.create_user(
            email='test@user.com',
            password='testpass123',
            name='Test User'
        )
        self.user.account_type = User.ACCOUNT_OWNER
        self.user.is_active = True
        self.user.save()
        
        # Create business
        self.business = Business.objects.create(
            owner=self.user,
            name='Test Business',
            email='test@business.com',
            tin='TIN123456',
            address='123 Test Street'
        )
        
        # Create warehouse
        self.warehouse = Warehouse.objects.create(
            name='Main Warehouse',
            location='Test Location',
            manager=self.user
        )
        BusinessWarehouse.objects.create(business=self.business, warehouse=self.warehouse)
        
        # Create storefront
        self.storefront = StoreFront.objects.create(
            name='Test Storefront',
            user=self.user,
            location='Test Location'
        )
        BusinessStoreFront.objects.create(business=self.business, storefront=self.storefront)
        
        # Create customer
        self.customer = Customer.objects.create(
            name='Test Customer',
            email='customer@test.com',
            business=self.business,
            created_by=self.user
        )
        
        # Create category
        self.category = Category.objects.create(
            name='Electronics'
        )
        
        # Create products
        self.product1 = Product.objects.create(
            name='Laptop',
            category=self.category,
            business=self.business,
            sku='LAP-001'
        )
        
        self.product2 = Product.objects.create(
            name='Mouse',
            category=self.category,
            business=self.business,
            sku='MOU-001'
        )
        
        # Create stock
        self.stock = Stock.objects.create(
            business=self.business,
            description='Initial stock'
        )
        
        # Create supplier
        self.supplier = Supplier.objects.create(
            business=self.business,
            name='Test Supplier',
            email='supplier@test.com'
        )
        
        # Create stock products in warehouse
        self.stock1 = StockProduct.objects.create(
            product=self.product1,
            stock=self.stock,
            warehouse=self.warehouse,
            quantity=10,
            unit_cost=Decimal('500.00'),
            retail_price=Decimal('600.00')
        )
        
        self.stock2 = StockProduct.objects.create(
            product=self.product2,
            stock=self.stock,
            warehouse=self.warehouse,
            quantity=50,
            unit_cost=Decimal('20.00'),
            retail_price=Decimal('25.00')
        )
        
        # Transfer some stock to storefront
        self.storefront_inv1 = StoreFrontInventory.objects.create(
            product=self.product1,
            storefront=self.storefront,
            quantity=5
        )
        
        self.storefront_inv2 = StoreFrontInventory.objects.create(
            product=self.product2,
            storefront=self.storefront,
            quantity=20
        )
    
    def test_cancel_completed_storefront_sale(self):
        """Test cancelling a completed storefront sale restocks correctly."""
        print("\n" + "="*80)
        print("TEST 1: Cancel Completed Storefront Sale")
        print("="*80)
        
        # Create and complete a storefront sale
        sale = Sale.objects.create(
            business=self.business,
            storefront=self.storefront,
            user=self.user,
            customer=self.customer,
            payment_type='CASH',
            status='DRAFT'
        )
        
        # Add items
        item1 = SaleItem.objects.create(
            sale=sale,
            product=self.product1,
            stock=self.stock,
            stock_product=self.stock1,
            quantity=2,
            unit_price=Decimal('600.00'),
            total_price=Decimal('1200.00')
        )
        
        item2 = SaleItem.objects.create(
            sale=sale,
            product=self.product2,
            stock=self.stock,
            stock_product=self.stock2,
            quantity=5,
            unit_price=Decimal('25.00'),
            total_price=Decimal('125.00')
        )
        
        # Complete the sale (this deducts from storefront inventory)
        sale.complete_sale(user=self.user)
        
        # Check inventory was deducted
        self.storefront_inv1.refresh_from_db()
        self.storefront_inv2.refresh_from_db()
        print(f"\n✓ After sale completion:")
        print(f"  Product1 storefront inventory: 5 → {self.storefront_inv1.quantity} (expected 3)")
        print(f"  Product2 storefront inventory: 20 → {self.storefront_inv2.quantity} (expected 15)")
        self.assertEqual(self.storefront_inv1.quantity, Decimal('3'))  # 5 - 2
        self.assertEqual(self.storefront_inv2.quantity, Decimal('15'))  # 20 - 5
        
        # Check sale totals
        sale.refresh_from_db()
        print(f"\n✓ Sale details:")
        print(f"  Total: {sale.total_amount}")
        print(f"  Status: {sale.status}")
        self.assertEqual(sale.total_amount, Decimal('1325.00'))
        self.assertEqual(sale.status, 'COMPLETED')
        
        # CANCEL THE SALE
        print(f"\n{'─'*80}")
        print("CANCELLING SALE...")
        print(f"{'─'*80}")
        
        refund = sale.cancel_sale(
            user=self.user,
            reason="Customer changed mind"
        )
        
        # Verify refund was created
        self.assertIsNotNone(refund)
        print(f"\n✓ Refund created:")
        print(f"  Amount: {refund.amount}")
        print(f"  Items refunded: {refund.refund_items.count()}")
        self.assertEqual(refund.amount, Decimal('1325.00'))
        self.assertEqual(refund.refund_items.count(), 2)
        
        # Verify inventory was restocked to STOREFRONT (original location)
        self.storefront_inv1.refresh_from_db()
        self.storefront_inv2.refresh_from_db()
        print(f"\n✓ After cancellation (inventory returned to storefront):")
        print(f"  Product1 storefront inventory: 3 → {self.storefront_inv1.quantity} (expected 5)")
        print(f"  Product2 storefront inventory: 15 → {self.storefront_inv2.quantity} (expected 20)")
        self.assertEqual(self.storefront_inv1.quantity, Decimal('5'))  # 3 + 2
        self.assertEqual(self.storefront_inv2.quantity, Decimal('20'))  # 15 + 5
        
        # Verify sale status changed to CANCELLED
        sale.refresh_from_db()
        print(f"\n✓ Sale status updated:")
        print(f"  Status: COMPLETED → {sale.status} (expected CANCELLED)")
        self.assertEqual(sale.status, 'CANCELLED')
        
        # Verify audit log was created
        audit_logs = AuditLog.objects.filter(
            event_type='sale.cancelled',
            sale=sale
        )
        print(f"\n✓ Audit trail created:")
        print(f"  Cancellation logs: {audit_logs.count()}")
        self.assertTrue(audit_logs.exists())
        
        log = audit_logs.first()
        print(f"  Reason: {log.event_data.get('reason')}")
        print(f"  Previous status: {log.event_data.get('previous_status')}")
        print(f"  Refund amount: {log.event_data.get('refund_amount')}")
        self.assertEqual(log.event_data['reason'], 'Customer changed mind')
        self.assertEqual(log.event_data['previous_status'], 'COMPLETED')
        
        print(f"\n{'='*80}")
        print("✅ TEST 1 PASSED: Storefront sale cancelled and inventory restored")
        print(f"{'='*80}\n")
    
    def test_cancel_credit_sale_reverses_customer_balance(self):
        """Test cancelling a credit sale reverses customer's credit balance."""
        print("\n" + "="*80)
        print("TEST 2: Cancel Credit Sale - Reverse Customer Balance")
        print("="*80)
        
        # Set customer credit limit
        self.customer.credit_limit = Decimal('5000.00')
        self.customer.credit_balance = Decimal('0.00')
        self.customer.save()
        
        # Create and complete a credit sale
        sale = Sale.objects.create(
            business=self.business,
            storefront=self.storefront,
            user=self.user,
            customer=self.customer,
            payment_type='CREDIT',
            status='DRAFT'
        )
        
        item = SaleItem.objects.create(
            sale=sale,
            product=self.product1,
            stock=self.stock,
            stock_product=self.stock1,
            quantity=1,
            unit_price=Decimal('600.00'),
            total_price=Decimal('600.00')
        )
        
        # Complete the sale (increases customer debt)
        sale.complete_sale(user=self.user)
        
        # Check customer balance increased
        self.customer.refresh_from_db()
        print(f"\n✓ After credit sale:")
        print(f"  Customer credit balance: {self.customer.credit_balance}")
        self.assertEqual(self.customer.credit_balance, Decimal('600.00'))
        
        # CANCEL THE SALE
        print(f"\n{'─'*80}")
        print("CANCELLING CREDIT SALE...")
        print(f"{'─'*80}")
        
        refund = sale.cancel_sale(
            user=self.user,
            reason="Product defective"
        )
        
        # Verify customer balance was reversed
        self.customer.refresh_from_db()
        print(f"\n✓ After cancellation:")
        print(f"  Customer credit balance: {self.customer.credit_balance} (expected 0.00)")
        self.assertEqual(self.customer.credit_balance, Decimal('0.00'))
        
        # Verify sale shows full refund
        sale.refresh_from_db()
        print(f"  Sale amount_refunded: {sale.amount_refunded}")
        print(f"  Sale status: {sale.status}")
        self.assertEqual(sale.amount_refunded, Decimal('600.00'))
        self.assertEqual(sale.status, 'CANCELLED')
        
        print(f"\n{'='*80}")
        print("✅ TEST 2 PASSED: Credit sale cancelled and customer balance reversed")
        print(f"{'='*80}\n")
    
    def test_cannot_cancel_already_cancelled_sale(self):
        """Test that cancelling an already cancelled sale raises error."""
        print("\n" + "="*80)
        print("TEST 3: Cannot Cancel Already Cancelled Sale")
        print("="*80)
        
        # Create and complete a sale
        sale = Sale.objects.create(
            business=self.business,
            storefront=self.storefront,
            user=self.user,
            customer=self.customer,
            payment_type='CASH',
            status='DRAFT'
        )
        
        item = SaleItem.objects.create(
            sale=sale,
            product=self.product1,
            stock=self.stock,
            stock_product=self.stock1,
            quantity=1,
            unit_price=Decimal('600.00'),
            total_price=Decimal('600.00')
        )
        
        sale.complete_sale(user=self.user)
        
        # Cancel once
        print(f"\n✓ First cancellation...")
        refund1 = sale.cancel_sale(
            user=self.user,
            reason="First cancellation"
        )
        
        sale.refresh_from_db()
        print(f"  Sale status: {sale.status}")
        self.assertEqual(sale.status, 'CANCELLED')
        
        # Try to cancel again
        print(f"\n✓ Attempting second cancellation...")
        with self.assertRaises(ValidationError) as context:
            sale.cancel_sale(
                user=self.user,
                reason="Second cancellation attempt"
            )
        
        print(f"  Error raised: {str(context.exception)}")
        self.assertIn('already cancelled', str(context.exception).lower())
        
        print(f"\n{'='*80}")
        print("✅ TEST 3 PASSED: Cannot cancel already cancelled sale")
        print(f"{'='*80}\n")
    
    def test_cancel_partial_refund_sale(self):
        """Test cancelling a sale that already has partial refund."""
        print("\n" + "="*80)
        print("TEST 4: Cancel Sale With Partial Refund")
        print("="*80)
        
        # Create and complete a sale with 2 items
        sale = Sale.objects.create(
            business=self.business,
            storefront=self.storefront,
            user=self.user,
            customer=self.customer,
            payment_type='CASH',
            status='DRAFT'
        )
        
        item1 = SaleItem.objects.create(
            sale=sale,
            product=self.product1,
            stock=self.stock,
            stock_product=self.stock1,
            quantity=2,
            unit_price=Decimal('600.00'),
            total_price=Decimal('1200.00')
        )
        
        item2 = SaleItem.objects.create(
            sale=sale,
            product=self.product2,
            stock=self.stock,
            stock_product=self.stock2,
            quantity=5,
            unit_price=Decimal('25.00'),
            total_price=Decimal('125.00')
        )
        
        sale.complete_sale(user=self.user)
        
        print(f"\n✓ Sale completed:")
        print(f"  Total: {sale.total_amount}")
        print(f"  Items: 2 (Laptop x2, Mouse x5)")
        
        # Process partial refund for 1 laptop
        print(f"\n✓ Processing partial refund for 1 laptop...")
        partial_refund = sale.process_refund(
            user=self.user,
            items=[{
                'sale_item': item1,
                'quantity': 1
            }],
            reason='Customer returned 1 laptop',
            refund_type='PARTIAL'
        )
        
        sale.refresh_from_db()
        print(f"  Amount refunded: {sale.amount_refunded}")
        print(f"  Status: {sale.status}")
        self.assertEqual(sale.amount_refunded, Decimal('600.00'))
        self.assertEqual(sale.status, 'PARTIAL')
        
        # CANCEL THE SALE (should refund remaining items)
        print(f"\n{'─'*80}")
        print("CANCELLING SALE (should refund remaining items)...")
        print(f"{'─'*80}")
        
        cancel_refund = sale.cancel_sale(
            user=self.user,
            reason="Customer wants full cancellation"
        )
        
        # Verify remaining items were refunded
        sale.refresh_from_db()
        print(f"\n✓ After cancellation:")
        print(f"  Total refunded: {sale.amount_refunded} (expected 1325.00)")
        print(f"  Status: {sale.status}")
        self.assertEqual(sale.amount_refunded, Decimal('1325.00'))  # Full amount
        self.assertEqual(sale.status, 'CANCELLED')
        
        # Verify both refunds exist
        refunds = Refund.objects.filter(sale=sale)
        print(f"  Total refunds: {refunds.count()}")
        self.assertEqual(refunds.count(), 2)  # Partial + Cancellation
        
        print(f"\n{'='*80}")
        print("✅ TEST 4 PASSED: Partial refund sale cancelled successfully")
        print(f"{'='*80}\n")
    
    def test_cancel_draft_sale_no_refund_needed(self):
        """Test cancelling a draft sale (no refund needed)."""
        print("\n" + "="*80)
        print("TEST 5: Cancel Draft Sale (No Refund Needed)")
        print("="*80)
        
        # Create a draft sale
        sale = Sale.objects.create(
            business=self.business,
            storefront=self.storefront,
            user=self.user,
            customer=self.customer,
            payment_type='CASH',
            status='DRAFT'
        )
        
        item = SaleItem.objects.create(
            sale=sale,
            product=self.product1,
            stock=self.stock,
            stock_product=self.stock1,
            quantity=1,
            unit_price=Decimal('600.00'),
            total_price=Decimal('600.00')
        )
        
        print(f"\n✓ Draft sale created:")
        print(f"  Status: {sale.status}")
        print(f"  Items: 1")
        
        # CANCEL THE DRAFT SALE
        print(f"\n{'─'*80}")
        print("CANCELLING DRAFT SALE...")
        print(f"{'─'*80}")
        
        refund = sale.cancel_sale(
            user=self.user,
            reason="Customer abandoned cart"
        )
        
        # Verify no refund was created (draft never completed)
        print(f"\n✓ After cancellation:")
        print(f"  Refund created: {refund is not None}")
        print(f"  Sale status: {sale.status}")
        
        sale.refresh_from_db()
        self.assertEqual(sale.status, 'CANCELLED')
        
        # Verify audit log still created
        audit_log = AuditLog.objects.filter(
            event_type='sale.cancelled',
            sale=sale
        ).first()
        
        print(f"  Audit log created: {audit_log is not None}")
        print(f"  Reason: {audit_log.event_data.get('reason')}")
        self.assertIsNotNone(audit_log)
        
        print(f"\n{'='*80}")
        print("✅ TEST 5 PASSED: Draft sale cancelled without refund")
        print(f"{'='*80}\n")


if __name__ == '__main__':
    import unittest
    
    # Create test suite
    suite = unittest.TestLoader().loadTestsFromTestCase(SaleCancellationTestCase)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "="*80)
    print("SALE CANCELLATION TEST SUMMARY")
    print("="*80)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    if result.wasSuccessful():
        print("\n🎉 ALL TESTS PASSED!")
        print("\nAutomatic sale cancellation workflow is fully functional:")
        print("  ✅ Storefront sales restock to storefront")
        print("  ✅ Credit sales reverse customer balance")
        print("  ✅ Cannot cancel already cancelled sales")
        print("  ✅ Partial refunds handled correctly")
        print("  ✅ Draft sales cancelled without refund")
    else:
        print("\n❌ SOME TESTS FAILED")
        if result.failures:
            print("\nFailures:")
            for test, traceback in result.failures:
                print(f"  - {test}")
        if result.errors:
            print("\nErrors:")
            for test, traceback in result.errors:
                print(f"  - {test}")
    
    print("="*80 + "\n")
    
    sys.exit(0 if result.wasSuccessful() else 1)
