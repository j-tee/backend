from django.test import TestCase
from accounts.models import Business
from django.contrib.auth import get_user_model
from inventory.models import Stock, StockProduct, Product, Warehouse
from inventory.stock_adjustments import StockAdjustment

User = get_user_model()


class TransferBehaviorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='u1')
        self.business = Business.objects.create(owner=self.user, name='B1', email='b1@example.com')
        self.stock_src = Stock.objects.create(business=self.business)
        self.stock_dst = Stock.objects.create(business=self.business)
        self.warehouse_src = Warehouse.objects.create(name='WS', location='s')
        self.warehouse_dst = Warehouse.objects.create(name='WD', location='d')
        self.product = Product.objects.create(business=self.business, name='Prod', sku='SKU')
        # Source product intake 45
        self.sp_src = StockProduct.objects.create(stock=self.stock_src, warehouse=self.warehouse_src, product=self.product, quantity=45, calculated_quantity=35)
        # Destination intake already equals transfer qty (5)
        self.sp_dst = StockProduct.objects.create(stock=self.stock_dst, warehouse=self.warehouse_dst, product=self.product, quantity=5, calculated_quantity=5)

    def test_transfer_in_double_count_prevention(self):
        # Create linked adjustments
        ref = 'TRF-TEST-1'
        out = StockAdjustment.objects.create(
            business=self.business,
            stock_product=self.sp_src,
            adjustment_type='TRANSFER_OUT',
            quantity=-5,
            unit_cost=self.sp_src.unit_cost,
            total_cost=0,
            reason='transfer out',
            reference_number=ref,
            status='APPROVED',
            created_by=self.user
        )
        inn = StockAdjustment.objects.create(
            business=self.business,
            stock_product=self.sp_dst,
            adjustment_type='TRANSFER_IN',
            quantity=5,
            unit_cost=self.sp_dst.unit_cost,
            total_cost=0,
            reason='transfer in',
            reference_number=ref,
            status='APPROVED',
            created_by=self.user
        )

        # Completing the out should decrease src calculated_quantity
        out.complete()
        self.sp_src.refresh_from_db()
        self.assertEqual(self.sp_src.calculated_quantity, 30)

        # Completing the in should NOT double-add because destination intake == incoming_qty
        inn.complete()
        self.sp_dst.refresh_from_db()
        # destination calculated_quantity remains 5 (no double addition)
        self.assertEqual(self.sp_dst.calculated_quantity, 5)
