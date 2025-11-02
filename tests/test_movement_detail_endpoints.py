"""
Integration tests for movement detail endpoints.

Verifies that Sale, StockAdjustment, and Transfer detail endpoints
return the items_detail field for frontend movement modals.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import Business, BusinessMembership
from inventory.models import Category, Product, Stock, StockProduct, Supplier, Warehouse
from inventory.stock_adjustments import StockAdjustment
from inventory.transfer_models import Transfer, TransferItem
from inventory.models import StoreFront, BusinessStoreFront
from sales.models import Customer, Sale, SaleItem


User = get_user_model()


class MovementDetailEndpointsTests(TestCase):
    """Test that all movement detail endpoints include items_detail field."""

    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(
            email='testuser@example.com',
            password='testpass123',
            name='Test User',
            account_type=User.ACCOUNT_OWNER
        )
        
        # Create Business (auto-creates membership via signal)
        self.business = Business.objects.create(
            name='Movement Test Business',
            owner=self.user,
            is_active=True
        )
        # Ensure membership is active (create if signal didn't or update if needed)
        BusinessMembership.objects.update_or_create(
            business=self.business,
            user=self.user,
            defaults={
                'role': BusinessMembership.OWNER,
                'is_admin': True,
                'is_active': True
            }
        )

        # Create test data
        self.category = Category.objects.create(name='Test Category')
        self.warehouse = Warehouse.objects.create(name='Test Warehouse', location='Test Location')
        self.stock = Stock.objects.create(business=self.business, description='Test stock')
        self.product = Product.objects.create(
            business=self.business,
            name='Test Product',
            sku='TST-001',
            category=self.category
        )
        self.supplier = Supplier.objects.create(business=self.business, name='Test Supplier')
        self.stock_product = StockProduct.objects.create(
            stock=self.stock,
            warehouse=self.warehouse,
            product=self.product,
            supplier=self.supplier,
            quantity=100,
            calculated_quantity=100,
            unit_cost=Decimal('10.00'),
            retail_price=Decimal('15.00')
        )

        # Create storefront for sales
        self.storefront = StoreFront.objects.create(
            user=self.user,
            name='Test Store',
            location='Test Location'
        )
        BusinessStoreFront.objects.create(
            business=self.business,
            storefront=self.storefront
        )

        # Get walk-in customer (auto-created by Business signal)
        self.customer = Customer.objects.get(
            business=self.business,
            phone='+233000000000'
        )

        # API client
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_sale_detail_includes_items_detail(self):
        """Verify GET /sales/api/sales/{id}/ includes items_detail and correct fields."""
        # Create sale with item
        sale = Sale.objects.create(
            business=self.business,
            storefront=self.storefront,
            user=self.user,
            customer=self.customer,
            status='COMPLETED',
            payment_type='CASH',
            total_amount=Decimal('150.00'),
            amount_paid=Decimal('150.00'),  # ✅ FIX: Set amount_paid to match total_amount
            amount_due=Decimal('0.00'),  # ✅ FIX: Set amount_due
            receipt_number='SALE-TEST-001'  # ✅ FIX: Provide receipt_number
        )

        SaleItem.objects.create(
            sale=sale,
            product=self.product,
            stock_product=self.stock_product,
            quantity=10,
            unit_price=Decimal('15.00'),
            total_price=Decimal('150.00')  # ✅ FIX: Use total_price instead of base_amount
        )

        # Fetch via API
        response = self.client.get(f'/sales/api/sales/{sale.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # ✅ CRITICAL: Verify sale_number is present
        self.assertIn('sale_number', response.data)
        self.assertIsNotNone(response.data['sale_number'])
        
        # ✅ CRITICAL: Verify storefront field (not warehouse) is present
        self.assertIn('storefront', response.data)
        self.assertEqual(response.data['storefront'], 'Test Store')
        
        # ✅ Verify items_detail is present
        self.assertIn('items_detail', response.data)
        self.assertIsInstance(response.data['items_detail'], list)
        self.assertGreater(len(response.data['items_detail']), 0)

        # Verify item structure
        item_detail = response.data['items_detail'][0]
        self.assertIn('product_name', item_detail)
        self.assertEqual(item_detail['product_name'], 'Test Product')

    def test_stock_adjustment_detail_includes_items_detail(self):
        """Verify GET /inventory/api/stock-adjustments/{id}/ includes items_detail and correct fields."""
        # Create stock adjustment
        adjustment = StockAdjustment.objects.create(
            business=self.business,
            stock_product=self.stock_product,
            adjustment_type='PHYSICAL_COUNT',
            quantity=10,
            quantity_before=self.stock_product.quantity,
            unit_cost=Decimal('10.00'),
            reason='Test adjustment',
            reference_number='ADJ-TEST-001',  # ✅ FIX: Provide reference_number
            created_by=self.user
        )

        # Fetch via API
        response = self.client.get(f'/inventory/api/stock-adjustments/{adjustment.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # ✅ CRITICAL: Verify adjustment_number is present
        self.assertIn('adjustment_number', response.data)
        self.assertIsNotNone(response.data['adjustment_number'])
        
        # ✅ CRITICAL: Verify warehouse_name is present
        self.assertIn('warehouse_name', response.data)
        self.assertEqual(response.data['warehouse_name'], 'Test Warehouse')
        
        # ✅ CRITICAL: Verify created_by_name is present
        self.assertIn('created_by_name', response.data)
        self.assertEqual(response.data['created_by_name'], 'Test User')
        
        # ✅ Verify items_detail is present
        self.assertIn('items_detail', response.data)
        self.assertIsInstance(response.data['items_detail'], list)
        self.assertGreater(len(response.data['items_detail']), 0)

        # Verify item structure
        item_detail = response.data['items_detail'][0]
        self.assertIn('product_name', item_detail)
        self.assertEqual(item_detail['product_name'], 'Test Product')
        self.assertIn('quantity_change', item_detail)
        self.assertEqual(item_detail['quantity_change'], 10)
        self.assertIn('direction', item_detail)
        self.assertEqual(item_detail['direction'], 'increase')

    def test_transfer_detail_includes_items_detail(self):
        """Verify GET /inventory/api/transfers/{id}/ includes items_detail and correct location fields."""
        # Create second warehouse for transfer
        warehouse2 = Warehouse.objects.create(name='Warehouse 2', location='Location 2')
        
        # Test Case 1: Warehouse → Warehouse transfer
        transfer = Transfer.objects.create(
            business=self.business,
            source_warehouse=self.warehouse,
            destination_warehouse=warehouse2,
            transfer_type=Transfer.TYPE_WAREHOUSE_TO_WAREHOUSE,
            status=Transfer.STATUS_PENDING,
            created_by=self.user
        )

        TransferItem.objects.create(
            transfer=transfer,
            product=self.product,
            quantity=5,
            unit_cost=Decimal('10.00')
        )

        # Fetch via API
        response = self.client.get(f'/inventory/api/transfers/{transfer.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # ✅ CRITICAL: Verify transfer_number is present
        self.assertIn('transfer_number', response.data)
        self.assertIsNotNone(response.data['transfer_number'])
        
        # ✅ CRITICAL: Verify warehouse-to-warehouse specific fields
        self.assertIn('from_warehouse', response.data)
        self.assertEqual(response.data['from_warehouse'], 'Test Warehouse')
        self.assertIn('to_warehouse', response.data)
        self.assertEqual(response.data['to_warehouse'], 'Warehouse 2')
        
        # ✅ CRITICAL: Verify created_by is present
        self.assertIn('created_by', response.data)
        self.assertEqual(response.data['created_by'], 'Test User')
        
        # ✅ Verify items_detail is present
        self.assertIn('items_detail', response.data)
        self.assertEqual(len(response.data['items_detail']), 1)
        
        item_detail = response.data['items_detail'][0]
        self.assertIn('transfer_item_id', item_detail)
        self.assertIn('product_name', item_detail)
        self.assertIn('quantity', item_detail)
        self.assertIn('source_warehouse_name', item_detail)
        self.assertIn('destination_warehouse_name', item_detail)
        self.assertEqual(item_detail['product_name'], 'Test Product')
        self.assertEqual(item_detail['quantity'], 5)
        self.assertEqual(item_detail['source_warehouse_name'], 'Test Warehouse')
        self.assertEqual(item_detail['destination_warehouse_name'], 'Warehouse 2')
        
    def test_transfer_warehouse_to_storefront(self):
        """Verify warehouse-to-storefront transfer has correct location fields."""
        # Test Case 2: Warehouse → Storefront transfer
        transfer = Transfer.objects.create(
            business=self.business,
            source_warehouse=self.warehouse,
            destination_storefront=self.storefront,
            transfer_type=Transfer.TYPE_WAREHOUSE_TO_STOREFRONT,
            status=Transfer.STATUS_PENDING,
            created_by=self.user
        )

        TransferItem.objects.create(
            transfer=transfer,
            product=self.product,
            quantity=3,
            unit_cost=Decimal('10.00')
        )

        # Fetch via API
        response = self.client.get(f'/inventory/api/transfers/{transfer.id}/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # ✅ CRITICAL: Verify warehouse-to-storefront specific fields
        self.assertIn('from_warehouse', response.data)
        self.assertEqual(response.data['from_warehouse'], 'Test Warehouse')
        self.assertIn('to_storefront', response.data)
        self.assertEqual(response.data['to_storefront'], 'Test Store')
        
        # ✅ Verify to_warehouse is NOT present for this type
        # (frontend uses presence/absence of fields to determine transfer type)
        if 'to_warehouse' in response.data:
            self.assertIsNone(response.data['to_warehouse'],
                            "to_warehouse should be null for warehouse-to-storefront transfers")
