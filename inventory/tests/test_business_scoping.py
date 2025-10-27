from django.test import TestCase
from accounts.models import Business, BusinessMembership
from django.contrib.auth import get_user_model
from inventory.models import Stock, StockProduct, Product, Warehouse


User = get_user_model()


class BusinessScopingTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create(username='owner')
        self.business = Business.objects.create(owner=self.owner, name='TestBiz', email='test@example.com')
        self.membership = BusinessMembership.objects.create(user=self.owner, business=self.business, is_active=True, role=BusinessMembership.OWNER)

        # Create stock batch for business
        self.stock = Stock.objects.create(business=self.business)
        self.warehouse = Warehouse.objects.create(name='W1', location='loc')
        self.product = Product.objects.create(business=self.business, name='P1', sku='P1')

        self.sp = StockProduct.objects.create(stock=self.stock, warehouse=self.warehouse, product=self.product, quantity=10)

    def test_stock_has_business_and_scoped(self):
        self.assertIsNotNone(self.stock.business)
        qs = Stock.objects.filter(business_id=self.business.id)
        self.assertIn(self.stock, list(qs))

    def test_stockproduct_scoping_by_stock_business(self):
        qs = StockProduct.objects.filter(stock__business_id=self.business.id)
        self.assertIn(self.sp, list(qs))
