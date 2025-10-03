import uuid
from typing import Optional

from django.db import models, transaction
from django.db.models import Sum
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal

from accounts.models import Business, BusinessMembership


User = get_user_model()


class Category(models.Model):
    """Product categories"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'categories'
        verbose_name_plural = 'categories'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Supplier(models.Model):
    """Suppliers providing stock for products."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='suppliers')
    name = models.CharField(max_length=255)
    contact_person = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'suppliers'
        ordering = ['name']
        unique_together = ['business', 'name']  # Prevent duplicate supplier names per business

    def __str__(self):
        return f"{self.name} ({self.business.name})"


class Warehouse(models.Model):
    """Warehouses for storing inventory"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    location = models.TextField()
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_warehouses')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'warehouses'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class StoreFront(models.Model):
    """Store fronts for retail sales"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='store_fronts')
    name = models.CharField(max_length=255)
    location = models.TextField()
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_stores')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'storefronts'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} (Owner: {self.user.name})"


class Product(models.Model):
    """Products in the inventory"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    unit = models.CharField(max_length=50, default='pcs')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'products'
        ordering = ['name']
        unique_together = ['business', 'sku']  # Prevent duplicate SKUs per business
        indexes = [
            models.Index(fields=['business', 'sku']),
            models.Index(fields=['business', 'category', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.sku}) - {self.business.name}"
    
    def get_latest_cost(self, warehouse=None, supplier=None):
        """Get the latest unit cost for this product from stock"""
        stock_products = self.stock_items.all()
        if warehouse:
            stock_products = stock_products.filter(stock__warehouse=warehouse)
        if supplier:
            stock_products = stock_products.filter(supplier=supplier)
        
        latest_stock = stock_products.order_by('-created_at').first()
        return latest_stock.unit_cost if latest_stock else Decimal('0.00')

    def get_expected_profit_summary(self, warehouse=None, supplier=None, 
                                   retail_percentage: Decimal = Decimal('100.00'), 
                                   wholesale_percentage: Decimal = Decimal('0.00')):
        """
        Get expected profit summary across all stock products for this product.
        
        Args:
            warehouse: Filter by specific warehouse
            supplier: Filter by specific supplier  
            retail_percentage: Percentage of units expected to be sold at retail price
            wholesale_percentage: Percentage of units expected to be sold at wholesale price
            
        Returns:
            Dictionary with profit summary for the specified scenario
        """
        stock_products = self.stock_items.all()
        if warehouse:
            stock_products = stock_products.filter(stock__warehouse=warehouse)
        if supplier:
            stock_products = stock_products.filter(supplier=supplier)
        
        total_quantity = sum(sp.quantity for sp in stock_products)
        
        if total_quantity == 0:
            return {
                'total_quantity': Decimal('0'),
                'total_expected_profit': Decimal('0.00'),
                'average_expected_margin': Decimal('0.00'),
                'stock_products_count': 0,
                'scenario': f'{retail_percentage}% retail, {wholesale_percentage}% wholesale',
            }
        
        # Calculate profit for each stock product using the specified scenario
        total_expected_profit = Decimal('0.00')
        weighted_margin_sum = Decimal('0.00')
        
        for sp in stock_products:
            scenario_profit = sp.get_expected_profit_for_scenario(retail_percentage, wholesale_percentage)
            total_expected_profit += scenario_profit['total_profit']
            # Weight margin by revenue for accurate average
            revenue = scenario_profit['avg_selling_price'] * sp.quantity
            if revenue > 0:
                weighted_margin_sum += scenario_profit['profit_margin'] * revenue
        
        # Calculate weighted average margin
        total_revenue = sum(
            sp.get_expected_profit_for_scenario(retail_percentage, wholesale_percentage)['avg_selling_price'] * sp.quantity 
            for sp in stock_products
        )
        avg_expected_margin = (weighted_margin_sum / total_revenue * Decimal('100')).quantize(Decimal('0.01')) if total_revenue > 0 else Decimal('0.00')
        
        return {
            'total_quantity': total_quantity,
            'total_expected_profit': total_expected_profit,
            'average_expected_margin': avg_expected_margin,
            'stock_products_count': stock_products.count(),
            'scenario': f'{retail_percentage}% retail, {wholesale_percentage}% wholesale',
            'retail_percentage': retail_percentage,
            'wholesale_percentage': wholesale_percentage,
        }


class Stock(models.Model):
    """Stock batches for organizing inventory."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='stocks')
    arrival_date = models.DateField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'stock'
        ordering = ['-arrival_date', 'created_at']
        indexes = [
            models.Index(fields=['warehouse', 'arrival_date']),
        ]

    def __str__(self):
        arrival = self.arrival_date.isoformat() if self.arrival_date else 'unscheduled'
        return f"{self.warehouse.name} stock ({arrival})"


class StockProduct(models.Model):
    """Stock items with supplier-specific data."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_items')
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name='stock_items')
    expiry_date = models.DateField(blank=True, null=True)
    quantity = models.PositiveIntegerField()
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))], default=Decimal('0.00'))
    unit_tax_rate = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))], default=Decimal('0.00'), null=True, blank=True)
    unit_tax_amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))], default=Decimal('0.00'), null=True, blank=True)
    unit_additional_cost = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))], default=Decimal('0.00'), null=True, blank=True)
    retail_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))], default=Decimal('0.00'))
    wholesale_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))], default=Decimal('0.00'))
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'stock_products'
        ordering = ['product__name', 'stock__warehouse__name']
        indexes = [
            models.Index(fields=['stock', 'product']),
            models.Index(fields=['product', 'expiry_date']),
            models.Index(fields=['supplier']),
            models.Index(fields=['stock', 'product', 'unit_cost']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['stock', 'product', 'supplier', 'expiry_date', 'unit_cost'],
                name='stock_unique_product_supplier_expiry_cost'
            ),
        ]

    def __str__(self):
        arrival = self.stock.arrival_date.isoformat() if self.stock.arrival_date else 'unscheduled'
        supplier_info = f" by {self.supplier.name}" if self.supplier else ""
        return f"{self.product.name} @ {self.stock.warehouse.name} ({arrival}){supplier_info}"

    def save(self, *args, **kwargs):
        # Calculate tax_amount from tax_rate only if tax_amount is not already set
        if self.unit_cost and self.unit_tax_rate is not None and (self.unit_tax_amount is None or self.unit_tax_amount == Decimal('0.00')):
            tax_value = (self.unit_cost * self.unit_tax_rate) / Decimal('100.00')
            self.unit_tax_amount = tax_value.quantize(Decimal('0.01'))
        super().save(*args, **kwargs)

    @property
    def warehouse(self):
        """Get warehouse from the stock batch."""
        return self.stock.warehouse

    @property
    def effective_supplier(self):
        return self.supplier

    @property
    def landed_unit_cost(self) -> Decimal:
        """Total cost per unit including all taxes and additional costs"""
        return (self.unit_cost or Decimal('0.00')) + (self.unit_tax_amount or Decimal('0.00')) + (self.unit_additional_cost or Decimal('0.00'))

    @property
    def total_base_cost(self) -> Decimal:
        """Total base cost for all units (without taxes and additional costs)"""
        return (self.unit_cost or Decimal('0.00')) * self.quantity

    @property
    def total_tax_amount(self) -> Decimal:
        """Total tax amount for all units"""
        return (self.unit_tax_amount or Decimal('0.00')) * self.quantity

    @property
    def total_additional_cost(self) -> Decimal:
        """Total additional costs for all units"""
        return (self.unit_additional_cost or Decimal('0.00')) * self.quantity

    @property
    def total_landed_cost(self) -> Decimal:
        """Total landed cost including all taxes and additional costs"""
        return self.landed_unit_cost * self.quantity

    @property
    def expected_profit_amount(self) -> Decimal:
        """Expected profit per unit if sold at retail price (retail_price - landed_unit_cost)"""
        if not self.retail_price or self.retail_price <= Decimal('0.00'):
            return Decimal('0.00')
        return self.retail_price - self.landed_unit_cost

    @property
    def expected_profit_margin(self) -> Decimal:
        """Expected profit margin percentage if sold at retail price"""
        if not self.retail_price or self.retail_price <= Decimal('0.00'):
            return Decimal('0.00')
        return ((self.retail_price - self.landed_unit_cost) / self.retail_price * Decimal('100')).quantize(Decimal('0.01'))

    @property
    def expected_total_profit(self) -> Decimal:
        """Expected total profit if all units sold at retail price"""
        return self.expected_profit_amount * self.quantity

    def get_available_quantity(self) -> Decimal:
        """
        Get available quantity considering active reservations
        
        Returns:
            Decimal: Quantity available for new reservations/sales
        """
        from django.db.models import Sum
        
        # Get total reserved quantity
        reserved = self.reservations.filter(
            status='ACTIVE'
        ).aggregate(
            total=Sum('quantity')
        )['total'] or Decimal('0.00')
        
        available = Decimal(str(self.quantity)) - reserved
        return max(Decimal('0.00'), available)
    
    def get_expected_profit_scenarios(self) -> dict:
        """
        Calculate expected profit projections for different sales scenarios.
        
        Returns scenarios for:
        - retail_only: All units sold at retail price
        - wholesale_only: All units sold at wholesale price  
        - mixed_scenarios: Various retail/wholesale combinations
        """
        scenarios = {}
        
        # Retail-only scenario
        scenarios['retail_only'] = {
            'scenario': 'retail_only',
            'description': 'All units sold at retail price',
            'retail_percentage': Decimal('100.00'),
            'wholesale_percentage': Decimal('0.00'),
            'avg_selling_price': self.retail_price,
            'profit_per_unit': self.expected_profit_amount,
            'profit_margin': self.expected_profit_margin,
            'total_profit': self.expected_total_profit,
        }
        
        # Wholesale-only scenario
        wholesale_profit_per_unit = Decimal('0.00')
        wholesale_margin = Decimal('0.00')
        if self.wholesale_price and self.wholesale_price > Decimal('0.00'):
            wholesale_profit_per_unit = self.wholesale_price - self.landed_unit_cost
            wholesale_margin = ((self.wholesale_price - self.landed_unit_cost) / self.wholesale_price * Decimal('100')).quantize(Decimal('0.01'))
        
        scenarios['wholesale_only'] = {
            'scenario': 'wholesale_only',
            'description': 'All units sold at wholesale price',
            'retail_percentage': Decimal('0.00'),
            'wholesale_percentage': Decimal('100.00'),
            'avg_selling_price': self.wholesale_price,
            'profit_per_unit': wholesale_profit_per_unit,
            'profit_margin': wholesale_margin,
            'total_profit': wholesale_profit_per_unit * self.quantity,
        }
        
        # Mixed scenarios - common combinations
        mixed_scenarios = []
        common_splits = [
            (Decimal('90.00'), Decimal('10.00'), '90% retail, 10% wholesale'),
            (Decimal('80.00'), Decimal('20.00'), '80% retail, 20% wholesale'),
            (Decimal('70.00'), Decimal('30.00'), '70% retail, 30% wholesale'),
            (Decimal('60.00'), Decimal('40.00'), '60% retail, 40% wholesale'),
            (Decimal('50.00'), Decimal('50.00'), '50% retail, 50% wholesale'),
            (Decimal('40.00'), Decimal('60.00'), '40% retail, 60% wholesale'),
            (Decimal('30.00'), Decimal('70.00'), '30% retail, 70% wholesale'),
            (Decimal('20.00'), Decimal('80.00'), '20% retail, 80% wholesale'),
            (Decimal('10.00'), Decimal('90.00'), '10% retail, 90% wholesale'),
        ]
        
        for retail_pct, wholesale_pct, description in common_splits:
            retail_units = (retail_pct / Decimal('100.00')) * self.quantity
            wholesale_units = (wholesale_pct / Decimal('100.00')) * self.quantity
            
            retail_profit = self.expected_profit_amount * retail_units
            wholesale_profit = wholesale_profit_per_unit * wholesale_units
            total_profit = retail_profit + wholesale_profit
            
            # Weighted average selling price
            total_revenue = (self.retail_price * retail_units) + (self.wholesale_price * wholesale_units)
            avg_price = total_revenue / self.quantity if self.quantity > 0 else Decimal('0.00')
            
            # Weighted average margin
            avg_margin = (total_profit / total_revenue * Decimal('100')).quantize(Decimal('0.01')) if total_revenue > 0 else Decimal('0.00')
            
            mixed_scenarios.append({
                'scenario': f'mixed_{int(retail_pct)}_{int(wholesale_pct)}',
                'description': description,
                'retail_percentage': retail_pct,
                'wholesale_percentage': wholesale_pct,
                'retail_units': retail_units,
                'wholesale_units': wholesale_units,
                'avg_selling_price': avg_price,
                'profit_per_unit': total_profit / self.quantity if self.quantity > 0 else Decimal('0.00'),
                'profit_margin': avg_margin,
                'total_profit': total_profit,
            })
        
        scenarios['mixed_scenarios'] = mixed_scenarios
        
        return scenarios

    def get_expected_profit_for_scenario(self, retail_percentage: Decimal = Decimal('100.00'), 
                                       wholesale_percentage: Decimal = Decimal('0.00')) -> dict:
        """
        Calculate expected profit for a specific retail/wholesale percentage split.
        
        Args:
            retail_percentage: Percentage of units sold at retail price (0-100)
            wholesale_percentage: Percentage of units sold at wholesale price (0-100)
            
        Returns:
            Dictionary with profit calculations for the specified scenario
        """
        if retail_percentage + wholesale_percentage != Decimal('100.00'):
            raise ValueError("Retail and wholesale percentages must sum to 100%")
            
        retail_pct = retail_percentage / Decimal('100.00')
        wholesale_pct = wholesale_percentage / Decimal('100.00')
        
        retail_units = retail_pct * self.quantity
        wholesale_units = wholesale_pct * self.quantity
        
        retail_profit = self.expected_profit_amount * retail_units
        wholesale_profit_per_unit = Decimal('0.00')
        if self.wholesale_price and self.wholesale_price > Decimal('0.00'):
            wholesale_profit_per_unit = self.wholesale_price - self.landed_unit_cost
        wholesale_profit = wholesale_profit_per_unit * wholesale_units
        
        total_profit = retail_profit + wholesale_profit
        total_revenue = (self.retail_price * retail_units) + (self.wholesale_price * wholesale_units)
        
        avg_selling_price = total_revenue / self.quantity if self.quantity > 0 else Decimal('0.00')
        avg_margin = (total_profit / total_revenue * Decimal('100')).quantize(Decimal('0.01')) if total_revenue > 0 else Decimal('0.00')
        
        return {
            'retail_percentage': retail_percentage,
            'wholesale_percentage': wholesale_percentage,
            'retail_units': retail_units,
            'wholesale_units': wholesale_units,
            'avg_selling_price': avg_selling_price,
            'profit_per_unit': total_profit / self.quantity if self.quantity > 0 else Decimal('0.00'),
            'profit_margin': avg_margin,
            'total_profit': total_profit,
            'retail_profit': retail_profit,
            'wholesale_profit': wholesale_profit,
        }

    @property
    def cost_breakdown(self) -> dict:
        """Detailed cost breakdown for analysis"""
        return {
            'unit_cost': self.unit_cost,
            'unit_tax_rate': self.unit_tax_rate,
            'unit_tax_amount': self.unit_tax_amount,
            'unit_additional_cost': self.unit_additional_cost,
            'landed_unit_cost': self.landed_unit_cost,
            'retail_price': self.retail_price,
            'wholesale_price': self.wholesale_price,
            'quantity': self.quantity,
            'total_base_cost': self.total_base_cost,
            'total_tax_amount': self.total_tax_amount,
            'total_additional_cost': self.total_additional_cost,
            'total_landed_cost': self.total_landed_cost,
            'expected_profit_amount': self.expected_profit_amount,
            'expected_profit_margin': self.expected_profit_margin,
            'expected_total_profit': self.expected_total_profit,
            'profit_scenarios': self.get_expected_profit_scenarios(),
        }


class Inventory(models.Model):
    """Current inventory levels (denormalized for performance)"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='inventory')
    stock = models.ForeignKey(StockProduct, on_delete=models.SET_NULL, null=True, blank=True, related_name='inventory_entries')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='inventory')
    quantity = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'inventory'
        unique_together = ['product', 'warehouse', 'stock']
        indexes = [
            models.Index(fields=['product', 'warehouse']),
            models.Index(fields=['warehouse', 'quantity']),
            models.Index(fields=['stock', 'warehouse']),
        ]

    def __str__(self):
        if self.stock and self.stock.stock:
            arrival = self.stock.stock.arrival_date.isoformat() if self.stock.stock.arrival_date else 'unscheduled'
        else:
            arrival = 'unscheduled'
        return f"{self.product.name} - {self.warehouse.name} ({arrival}) Qty: {self.quantity}"


class StoreFrontInventory(models.Model):
    """Inventory levels tracked at the storefront level."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    storefront = models.ForeignKey(StoreFront, on_delete=models.CASCADE, related_name='inventory_entries')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='storefront_inventory_entries')
    quantity = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'storefront_inventory'
        unique_together = ['storefront', 'product']
        indexes = [
            models.Index(fields=['storefront', 'product']),
            models.Index(fields=['product']),
        ]

    def __str__(self):
        return f"{self.product.name} - {self.storefront.name} Qty: {self.quantity}"


def _generate_transfer_reference() -> str:
    date_fragment = timezone.now().strftime('%Y%m%d')
    random_part = uuid.uuid4().hex[:6].upper()
    return f"TRF-{date_fragment}-{random_part}"


class Transfer(models.Model):
    """Transfers from warehouse to storefront with lifecycle management."""

    STATUS_DRAFT = 'DRAFT'
    STATUS_REQUESTED = 'REQUESTED'
    STATUS_APPROVED = 'APPROVED'
    STATUS_IN_TRANSIT = 'IN_TRANSIT'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_REJECTED = 'REJECTED'
    STATUS_CANCELLED = 'CANCELLED'

    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_REQUESTED, 'Requested'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_IN_TRANSIT, 'In transit'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='transfers')
    reference = models.CharField(max_length=32, unique=True, default=_generate_transfer_reference)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    source_warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='outbound_transfer_orders')
    destination_storefront = models.ForeignKey(StoreFront, on_delete=models.CASCADE, related_name='inbound_transfer_orders')
    notes = models.TextField(blank=True, null=True)
    request = models.OneToOneField('inventory.TransferRequest', on_delete=models.SET_NULL, null=True, blank=True, related_name='transfer')
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='requested_transfers')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_transfers')
    fulfilled_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='fulfilled_transfers')
    received_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='received_transfers')
    submitted_at = models.DateTimeField(blank=True, null=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    dispatched_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    received_at = models.DateTimeField(blank=True, null=True)
    rejected_at = models.DateTimeField(blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'transfers'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['business', 'status']),
            models.Index(fields=['source_warehouse', 'status']),
            models.Index(fields=['destination_storefront', 'status']),
            models.Index(fields=['reference']),
        ]

    def __str__(self):
        return f"{self.reference} ({self.get_status_display()})"

    # ---- validation helpers ---------------------------------------------

    def touch_business(self):
        if self.business_id:
            return
        if self.request_id and getattr(self, 'request', None):
            self.business = self.request.business
            return
        link = getattr(self.source_warehouse, 'business_link', None)
        if link:
            self.business = link.business

    def clean(self):
        self.touch_business()
        if not self.business_id:
            raise ValidationError('Transfers must belong to a business.')

        warehouse_business = getattr(self.source_warehouse, 'business_link', None)
        storefront_business = getattr(self.destination_storefront, 'business_link', None)

        if not warehouse_business or warehouse_business.business_id != self.business_id:
            raise ValidationError({'source_warehouse': 'Source warehouse must belong to the transfer business.'})
        if not storefront_business or storefront_business.business_id != self.business_id:
            raise ValidationError({'destination_storefront': 'Destination storefront must belong to the transfer business.'})

        if self.request_id:
            request = getattr(self, 'request', None)
            if not request:
                raise ValidationError({'request_id': 'Linked request was not found.'})
            if request.business_id != self.business_id:
                raise ValidationError({'request_id': 'Request must belong to the transfer business.'})
            if request.storefront_id != self.destination_storefront_id:
                raise ValidationError({'request_id': 'Request storefront must match the transfer destination storefront.'})

    def save(self, *args, **kwargs):
        self.touch_business()
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def is_editable(self) -> bool:
        return self.status in {self.STATUS_DRAFT, self.STATUS_REJECTED}

    @staticmethod
    def available_quantity(warehouse: Warehouse, product: Product, exclude_transfer: Optional['Transfer'] = None) -> int:
        """Calculate available quantity for a product at a warehouse, accounting for reserved transfers."""
        on_hand = Inventory.objects.filter(warehouse=warehouse, product=product).aggregate(total=Sum('quantity'))['total'] or 0

        reserved_qs = TransferLineItem.objects.filter(
            transfer__source_warehouse=warehouse,
            product=product,
            transfer__status__in=[Transfer.STATUS_REQUESTED, Transfer.STATUS_APPROVED],
        )
        if exclude_transfer:
            reserved_qs = reserved_qs.exclude(transfer=exclude_transfer)

        reserved = 0
        for line in reserved_qs.select_related('transfer'):
            reserved += line.transfer._required_quantity_for_line(line)

        available = int(on_hand) - reserved
        return available if available > 0 else 0

    # ---- stock helpers ---------------------------------------------------

    def _required_quantity_for_line(self, line: 'TransferLineItem') -> int:
        if line.fulfilled_quantity is not None:
            return line.fulfilled_quantity
        if line.approved_quantity is not None:
            return line.approved_quantity
        return line.requested_quantity

    def _deduct_warehouse_quantities(self):
        for line in self.line_items.select_related('product'):
            required = self._required_quantity_for_line(line)
            if required <= 0:
                continue
            self._adjust_warehouse_inventory(line.product, required)

    def _return_warehouse_quantities(self):
        for line in self.line_items.select_related('product'):
            required = self._required_quantity_for_line(line)
            if required <= 0:
                continue
            self._adjust_warehouse_inventory(line.product, -required)

    def _adjust_warehouse_inventory(self, product: 'Product', delta: int):
        with transaction.atomic():
            entries = list(
                Inventory.objects.select_for_update().filter(
                    warehouse=self.source_warehouse,
                    product=product,
                ).order_by('-updated_at', 'id')
            )
            total = sum(entry.quantity for entry in entries)

            if delta > 0 and total < delta:
                raise ValidationError({'line_items': f'Insufficient stock for {product.name} at {self.source_warehouse.name}.'})

            if delta > 0:
                remaining = delta
                for entry in entries:
                    if remaining == 0:
                        break
                    take = min(entry.quantity, remaining)
                    entry.quantity -= take
                    remaining -= take
                    entry.save(update_fields=['quantity', 'updated_at'])
                if remaining > 0:
                    raise ValidationError({'line_items': f'Insufficient stock for {product.name} at {self.source_warehouse.name}.'})
            elif delta < 0:
                remaining = abs(delta)
                if entries:
                    entry = entries[0]
                    entry.quantity += remaining
                    entry.save(update_fields=['quantity', 'updated_at'])
                else:
                    Inventory.objects.create(
                        product=product,
                        warehouse=self.source_warehouse,
                        quantity=remaining,
                    )

    def _increment_storefront_quantities(self):
        with transaction.atomic():
            for line in self.line_items.select_related('product'):
                qty = self._required_quantity_for_line(line)
                if qty <= 0:
                    continue
                entry, created = StoreFrontInventory.objects.select_for_update().get_or_create(
                    storefront=self.destination_storefront,
                    product=line.product,
                    defaults={'quantity': 0},
                )
                entry.quantity += qty
                entry.save(update_fields=['quantity', 'updated_at'])

    # ---- audit + lifecycle ----------------------------------------------

    def add_audit(self, action: str, actor: User | None, remarks: str | None = None):
        TransferAuditEntry.objects.create(
            transfer=self,
            action=action,
            actor=actor,
            remarks=remarks,
        )

    def ensure_state(self, *allowed: str):
        if self.status not in allowed:
            allowed_str = ', '.join(allowed)
            raise ValidationError({'status': f'Invalid transition from {self.status}. Expected: {allowed_str}.'})

    def submit(self, actor: User | None):
        self.ensure_state(self.STATUS_DRAFT, self.STATUS_REJECTED)
        if not self.line_items.exists():
            raise ValidationError({'line_items': 'At least one line item is required before submission.'})
        self.status = self.STATUS_REQUESTED
        self.submitted_at = timezone.now()
        self.add_audit(TransferAuditEntry.ACTION_SUBMITTED, actor)
        self.save(update_fields=['status', 'submitted_at', 'updated_at'])

    def approve(self, actor: User | None):
        self.ensure_state(self.STATUS_REQUESTED)
        self.status = self.STATUS_APPROVED
        self.approved_by = actor
        self.approved_at = timezone.now()
        self.add_audit(TransferAuditEntry.ACTION_APPROVED, actor)
        self.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])

    def reject(self, actor: User | None, reason: str | None = None):
        self.ensure_state(self.STATUS_REQUESTED)
        self.status = self.STATUS_REJECTED
        self.rejected_at = timezone.now()
        self.add_audit(TransferAuditEntry.ACTION_REJECTED, actor, reason)
        request = getattr(self, 'request', None)
        if request:
            request.clear_assignment()
            self.request = None
        self.save(update_fields=['status', 'rejected_at', 'updated_at', 'request'])

    def cancel(self, actor: User | None, reason: str | None = None):
        self.ensure_state(self.STATUS_REQUESTED, self.STATUS_APPROVED, self.STATUS_IN_TRANSIT)
        if self.status == self.STATUS_IN_TRANSIT:
            self._return_warehouse_quantities()
        self.status = self.STATUS_CANCELLED
        self.cancelled_at = timezone.now()
        self.add_audit(TransferAuditEntry.ACTION_CANCELLED, actor, reason)
        request = getattr(self, 'request', None)
        if request:
            request.clear_assignment()
            self.request = None
        self.save(update_fields=['status', 'cancelled_at', 'updated_at', 'request'])

    def dispatch(self, actor: User | None):
        self.ensure_state(self.STATUS_APPROVED)
        self._deduct_warehouse_quantities()
        self.status = self.STATUS_IN_TRANSIT
        self.fulfilled_by = actor
        self.dispatched_at = timezone.now()
        self.add_audit(TransferAuditEntry.ACTION_DISPATCHED, actor)
        self.save(update_fields=['status', 'fulfilled_by', 'dispatched_at', 'updated_at'])

    def complete(self, actor: User | None):
        self.ensure_state(self.STATUS_IN_TRANSIT)
        self._increment_storefront_quantities()
        self.status = self.STATUS_COMPLETED
        self.completed_at = timezone.now()
        self.add_audit(TransferAuditEntry.ACTION_COMPLETED, actor)
        self.save(update_fields=['status', 'completed_at', 'updated_at'])

    def confirm_receipt(self, actor: User | None, notes: str | None = None):
        self.ensure_state(self.STATUS_IN_TRANSIT, self.STATUS_COMPLETED)
        if self.received_at is not None:
            raise ValidationError({'detail': 'Receipt already confirmed for this transfer.'})
        self.received_by = actor
        self.received_at = timezone.now()
        self.add_audit(TransferAuditEntry.ACTION_RECEIPT_CONFIRMED, actor, notes)
        self.save(update_fields=['received_by', 'received_at', 'updated_at'])
        request = getattr(self, 'request', None)
        if request:
            request.mark_fulfilled(actor)


class TransferLineItem(models.Model):
    """Individual product movements within a transfer."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transfer = models.ForeignKey(Transfer, on_delete=models.CASCADE, related_name='line_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='transfer_line_items')
    requested_quantity = models.PositiveIntegerField()
    approved_quantity = models.PositiveIntegerField(null=True, blank=True)
    fulfilled_quantity = models.PositiveIntegerField(null=True, blank=True)
    unit_of_measure = models.CharField(max_length=50, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'transfer_line_items'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['transfer']),
            models.Index(fields=['product']),
        ]

    def __str__(self):
        return f"{self.product.name} x{self.requested_quantity}"

    def clean(self):
        if self.requested_quantity <= 0:
            raise ValidationError({'requested_quantity': 'Requested quantity must be greater than zero.'})
        if self.approved_quantity is not None and self.approved_quantity < 0:
            raise ValidationError({'approved_quantity': 'Approved quantity cannot be negative.'})
        if self.fulfilled_quantity is not None and self.fulfilled_quantity < 0:
            raise ValidationError({'fulfilled_quantity': 'Fulfilled quantity cannot be negative.'})

        transfer_business_id = self.transfer.business_id if self.transfer_id else None
        if transfer_business_id and self.product.business_id != transfer_business_id:
            raise ValidationError({'product': 'Product must belong to the transfer business.'})


class TransferRequest(models.Model):
    """Storefront-originated stock requests that can be linked to transfers."""

    PRIORITY_LOW = 'LOW'
    PRIORITY_MEDIUM = 'MEDIUM'
    PRIORITY_HIGH = 'HIGH'
    PRIORITY_CHOICES = [
        (PRIORITY_LOW, 'Low'),
        (PRIORITY_MEDIUM, 'Medium'),
        (PRIORITY_HIGH, 'High'),
    ]

    STATUS_NEW = 'NEW'
    STATUS_ASSIGNED = 'ASSIGNED'
    STATUS_FULFILLED = 'FULFILLED'
    STATUS_CANCELLED = 'CANCELLED'
    STATUS_CHOICES = [
        (STATUS_NEW, 'New'),
        (STATUS_ASSIGNED, 'Assigned'),
        (STATUS_FULFILLED, 'Fulfilled'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='transfer_requests')
    storefront = models.ForeignKey(StoreFront, on_delete=models.CASCADE, related_name='transfer_requests')
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='transfer_requests')
    priority = models.CharField(max_length=16, choices=PRIORITY_CHOICES, default=PRIORITY_MEDIUM)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_NEW)
    notes = models.TextField(blank=True, null=True)
    linked_transfer_reference = models.CharField(max_length=32, blank=True, null=True)
    assigned_at = models.DateTimeField(blank=True, null=True)
    fulfilled_at = models.DateTimeField(blank=True, null=True)
    fulfilled_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='fulfilled_transfer_requests')
    cancelled_at = models.DateTimeField(blank=True, null=True)
    cancelled_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='cancelled_transfer_requests')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'transfer_requests'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['business', 'status']),
            models.Index(fields=['storefront', 'status']),
        ]

    def __str__(self):
        return f"Request {self.id} ({self.get_status_display()})"

    def clean(self):
        link = getattr(self.storefront, 'business_link', None)
        if not link:
            raise ValidationError({'storefront': 'Storefront must be linked to a business.'})
        if self.business_id and link.business_id != self.business_id:
            raise ValidationError({'storefront': 'Storefront must belong to the specified business.'})
        self.business = link.business

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def _current_transfer(self) -> Transfer | None:
        try:
            return self.transfer
        except Transfer.DoesNotExist:
            return None

    @property
    def linked_transfer_id(self) -> uuid.UUID | None:
        transfer = self._current_transfer()
        return transfer.id if transfer else None

    def mark_assigned(self, transfer: Transfer):
        if self.status not in {self.STATUS_NEW, self.STATUS_ASSIGNED}:
            raise ValidationError({'status': 'Request is already fulfilled or cancelled.'})
        existing = self._current_transfer()
        if existing and existing != transfer:
            raise ValidationError({'linked_transfer': 'Request is already linked to another transfer.'})
        self.status = self.STATUS_ASSIGNED
        self.assigned_at = timezone.now()
        self.linked_transfer_reference = transfer.reference
        self.save(update_fields=['status', 'assigned_at', 'linked_transfer_reference', 'updated_at'])

    def clear_assignment(self):
        updated_fields = []
        if self.status not in {self.STATUS_CANCELLED, self.STATUS_FULFILLED}:
            if self.status != self.STATUS_NEW:
                self.status = self.STATUS_NEW
                updated_fields.append('status')
            if self.linked_transfer_reference:
                self.linked_transfer_reference = None
                updated_fields.append('linked_transfer_reference')
        if self.assigned_at is not None:
            self.assigned_at = None
            updated_fields.append('assigned_at')
        if updated_fields:
            updated_fields.append('updated_at')
            self.save(update_fields=updated_fields)

    def mark_cancelled(self, actor: User | None):
        if self.status == self.STATUS_CANCELLED:
            return
        if self.status == self.STATUS_FULFILLED:
            raise ValidationError({'status': 'Fulfilled requests cannot be cancelled.'})
        self.status = self.STATUS_CANCELLED
        self.cancelled_at = timezone.now()
        self.cancelled_by = actor
        self.linked_transfer_reference = None
        self.assigned_at = None
        self.save(update_fields=['status', 'cancelled_at', 'cancelled_by', 'linked_transfer_reference', 'assigned_at', 'updated_at'])
        transfer = self._current_transfer()
        if transfer:
            transfer.request = None
            transfer.save(update_fields=['request', 'updated_at'])

    def mark_fulfilled(self, actor: User | None):
        if self.status == self.STATUS_FULFILLED:
            return
        if self.status != self.STATUS_ASSIGNED:
            raise ValidationError({'status': 'Only assigned requests can be fulfilled.'})
        transfer = self._current_transfer()
        if not transfer:
            raise ValidationError({'linked_transfer': 'Request is not linked to a transfer.'})
        if transfer.status != Transfer.STATUS_COMPLETED and transfer.status != Transfer.STATUS_IN_TRANSIT:
            raise ValidationError({'linked_transfer': 'Linked transfer must be in transit or completed before fulfilling the request.'})
        self.status = self.STATUS_FULFILLED
        self.fulfilled_at = timezone.now()
        self.fulfilled_by = actor
        self.save(update_fields=['status', 'fulfilled_at', 'fulfilled_by', 'updated_at'])


class TransferRequestLineItem(models.Model):
    """Line items requested by storefront staff before transfer creation."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(TransferRequest, on_delete=models.CASCADE, related_name='line_items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='transfer_request_line_items')
    requested_quantity = models.PositiveIntegerField()
    unit_of_measure = models.CharField(max_length=50, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'transfer_request_line_items'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['request']),
            models.Index(fields=['product']),
        ]

    def __str__(self):
        return f"{self.product.name} x{self.requested_quantity}"

    def clean(self):
        if self.requested_quantity <= 0:
            raise ValidationError({'requested_quantity': 'Requested quantity must be greater than zero.'})
        request_business_id = self.request.business_id if self.request_id else None
        if request_business_id and self.product.business_id != request_business_id:
            raise ValidationError({'product': 'Product must belong to the same business as the request.'})


class TransferAuditEntry(models.Model):
    """Audit trail for transfer lifecycle changes."""

    ACTION_CREATED = 'CREATED'
    ACTION_SUBMITTED = 'SUBMITTED'
    ACTION_APPROVED = 'APPROVED'
    ACTION_REJECTED = 'REJECTED'
    ACTION_CANCELLED = 'CANCELLED'
    ACTION_DISPATCHED = 'DISPATCHED'
    ACTION_COMPLETED = 'COMPLETED'
    ACTION_UPDATED = 'UPDATED'
    ACTION_RECEIPT_CONFIRMED = 'RECEIPT_CONFIRMED'

    ACTION_CHOICES = [
        (ACTION_CREATED, 'Created'),
        (ACTION_SUBMITTED, 'Submitted'),
        (ACTION_APPROVED, 'Approved'),
        (ACTION_REJECTED, 'Rejected'),
        (ACTION_CANCELLED, 'Cancelled'),
        (ACTION_DISPATCHED, 'Dispatched'),
        (ACTION_COMPLETED, 'Completed'),
        (ACTION_UPDATED, 'Updated'),
        (ACTION_RECEIPT_CONFIRMED, 'Receipt confirmed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transfer = models.ForeignKey(Transfer, on_delete=models.CASCADE, related_name='audit_entries')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='transfer_audit_entries')
    remarks = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'transfer_audit_entries'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['transfer']),
            models.Index(fields=['action']),
        ]

    def __str__(self):
        return f"{self.transfer.reference} - {self.action}"


class StockAlert(models.Model):
    """Stock alerts for low inventory"""
    ALERT_TYPE_CHOICES = [
        ('LOW_STOCK', 'Low Stock'),
        ('OUT_OF_STOCK', 'Out of Stock'),
        ('EXPIRY_WARNING', 'Expiry Warning'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_alerts')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='stock_alerts')
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPE_CHOICES)
    current_quantity = models.IntegerField()
    threshold_quantity = models.IntegerField()
    is_resolved = models.BooleanField(default=False)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'stock_alerts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['warehouse', 'is_resolved']),
            models.Index(fields=['alert_type', 'is_resolved']),
        ]
    
    def __str__(self):
        return f"{self.alert_type} - {self.product.name} at {self.warehouse.name}"


class BusinessWarehouse(models.Model):
    """Associates a warehouse with a business."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='business_warehouses')
    warehouse = models.OneToOneField(Warehouse, on_delete=models.CASCADE, related_name='business_link')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'business_warehouses'
        ordering = ['business__name', 'warehouse__name']

    def __str__(self):
        return f"{self.warehouse.name} -> {self.business.name}"


class BusinessStoreFront(models.Model):
    """Associates a storefront with a business."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='business_storefronts')
    storefront = models.OneToOneField(StoreFront, on_delete=models.CASCADE, related_name='business_link')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'business_storefronts'
        ordering = ['business__name', 'storefront__name']

    def __str__(self):
        return f"{self.storefront.name} -> {self.business.name}"


class StoreFrontEmployee(models.Model):
    """Employee assignments to storefronts within a business."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='storefront_employees')
    storefront = models.ForeignKey(StoreFront, on_delete=models.CASCADE, related_name='employees')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='storefront_assignments')
    role = models.CharField(max_length=20, choices=BusinessMembership.ROLE_CHOICES, default=BusinessMembership.STAFF)
    is_active = models.BooleanField(default=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    removed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'storefront_employees'
        unique_together = ['storefront', 'user']
        ordering = ['storefront__name', 'user__name']

    def __str__(self):
        return f"{self.user.name} @ {self.storefront.name}"

    def clean(self):
        if not BusinessStoreFront.objects.filter(business=self.business, storefront=self.storefront, is_active=True).exists():
            raise ValidationError('Storefront must belong to the specified business.')
        if not BusinessMembership.objects.filter(business=self.business, user=self.user, is_active=True).exists():
            raise ValidationError('User must be an active member of the business to be assigned.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class WarehouseEmployee(models.Model):
    """Employee assignments to warehouses within a business."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='warehouse_employees')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='employees')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='warehouse_assignments')
    role = models.CharField(max_length=20, choices=BusinessMembership.ROLE_CHOICES, default=BusinessMembership.STAFF)
    is_active = models.BooleanField(default=True)
    assigned_at = models.DateTimeField(auto_now_add=True)
    removed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'warehouse_employees'
        unique_together = ['warehouse', 'user']
        ordering = ['warehouse__name', 'user__name']

    def __str__(self):
        return f"{self.user.name} @ {self.warehouse.name}"

    def clean(self):
        if not BusinessWarehouse.objects.filter(business=self.business, warehouse=self.warehouse, is_active=True).exists():
            raise ValidationError('Warehouse must belong to the specified business.')
        if not BusinessMembership.objects.filter(business=self.business, user=self.user, is_active=True).exists():
            raise ValidationError('User must be an active member of the business to be assigned.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
