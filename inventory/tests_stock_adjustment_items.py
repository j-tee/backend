from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import Business
from inventory.models import Category, Product, Stock, StockProduct, Supplier, Warehouse
from inventory.stock_adjustments import StockAdjustment


class StockAdjustmentItemsPayloadTests(TestCase):
    """Ensure StockAdjustment.items returns a frontend-friendly payload."""

    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            email='owner-items@example.com',
            password='testpass123',
            name='Owner Items'
        )

        self.business = Business.objects.create(
            owner=self.owner,
            name='Items Payload Business',
            tin='TIN-ITEMS-0001',
            email='items-business@example.com',
            address='123 Items Street',
            phone_numbers=['+233555000001'],
            social_handles={}
        )

        self.category = Category.objects.create(name='Items Category')
        self.warehouse = Warehouse.objects.create(name='Items Warehouse', location='Items Location')
        self.stock = Stock.objects.create(business=self.business, description='Initial stock batch')
        self.product = Product.objects.create(
            business=self.business,
            name='Items Product',
            sku='ITEMS-001',
            category=self.category
        )
        self.supplier = Supplier.objects.create(business=self.business, name='Items Supplier')
        self.stock_product = StockProduct.objects.create(
            stock=self.stock,
            warehouse=self.warehouse,
            product=self.product,
            supplier=self.supplier,
            quantity=50,
            calculated_quantity=50,
            unit_cost=Decimal('12.50'),
            retail_price=Decimal('20.00')
        )

    def test_items_payload_returns_expected_shape(self):
        adjustment = StockAdjustment.objects.create(
            business=self.business,
            stock_product=self.stock_product,
            adjustment_type='CORRECTION_INCREASE',
            quantity=5,
            unit_cost=Decimal('12.50'),
            reason='Inventory recount increase',
            created_by=self.owner,
            status='COMPLETED'
        )

        payload = adjustment.get_items_detail()
        self.assertEqual(len(payload), 1)
        item = payload[0]
        self.assertEqual(item['stock_product_id'], str(self.stock_product.id))
        self.assertEqual(item['product_id'], str(self.product.id))
        self.assertEqual(item['product_name'], self.product.name)
        self.assertEqual(item['warehouse_name'], self.warehouse.name)
        self.assertEqual(item['quantity_before'], self.stock_product.quantity)
        self.assertEqual(item['quantity_change'], 5)
        self.assertEqual(item['quantity_after'], self.stock_product.quantity + 5)
        self.assertEqual(item['unit_cost'], '12.50')
        self.assertEqual(item['total_cost'], '62.50')
        self.assertEqual(item['direction'], 'increase')
        self.assertEqual(item['adjustment_type'], 'CORRECTION_INCREASE')

    def test_items_payload_uses_stock_snapshot_fallback(self):
        adjustment = StockAdjustment.objects.create(
            business=self.business,
            stock_product=self.stock_product,
            adjustment_type='THEFT',
            quantity=-10,
            unit_cost=Decimal('12.50'),
            reason='Inventory loss',
            created_by=self.owner,
            status='COMPLETED'
        )

        self.stock_product.calculated_quantity = 40
        self.stock_product.save(update_fields=['calculated_quantity'])

        adjustment.quantity_before = None
        adjustment.save(update_fields=['quantity_before'])

        payload = adjustment.get_items_detail()
        self.assertEqual(len(payload), 1)
        item = payload[0]
        self.assertEqual(item['quantity_before'], 40)
        self.assertEqual(item['quantity_after'], 30)
        self.assertEqual(item['direction'], 'decrease')
        self.assertEqual(item['quantity_change'], -10)
        self.assertEqual(item['total_cost'], '125.00')
