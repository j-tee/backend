import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
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


class Batch(models.Model):
    """Batches of imported goods"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='batches')
    package_code = models.CharField(max_length=100, unique=True)
    arrival_date = models.DateField()
    supplier = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'batches'
        ordering = ['-arrival_date']
        indexes = [
            models.Index(fields=['warehouse', 'arrival_date']),
            models.Index(fields=['package_code']),
        ]
    
    def __str__(self):
        return f"{self.package_code} - {self.supplier}"


class Product(models.Model):
    """Products in the inventory"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    unit = models.CharField(max_length=50, default='pcs')
    retail_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    wholesale_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    cost = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'products'
        ordering = ['name']
        indexes = [
            models.Index(fields=['sku']),
            models.Index(fields=['category', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.sku})"
    
    def get_price(self, sale_type='retail'):
        """Get price based on sale type"""
        return self.wholesale_price if sale_type == 'wholesale' else self.retail_price


class BatchProduct(models.Model):
    """Products within specific batches (BatchItems)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name='batch_products')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='batch_products')
    quantity = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'batch_products'
        unique_together = ['batch', 'product']
        indexes = [
            models.Index(fields=['batch', 'product']),
        ]
    
    def __str__(self):
        return f"{self.product.name} - {self.batch.package_code} - Qty: {self.quantity}"


class Inventory(models.Model):
    """Current inventory levels (denormalized for performance)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='inventory')
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, null=True, blank=True, related_name='inventory')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='inventory')
    quantity = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'inventory'
        unique_together = ['product', 'batch', 'warehouse']
        indexes = [
            models.Index(fields=['product', 'warehouse']),
            models.Index(fields=['warehouse', 'quantity']),
            models.Index(fields=['batch', 'warehouse']),
        ]
    
    def __str__(self):
        return f"{self.product.name} - {self.warehouse.name} - Qty: {self.quantity}"


class Transfer(models.Model):
    """Transfers from warehouse to storefront"""
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_TRANSIT', 'In Transit'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='transfers')
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name='transfers')
    from_warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='outbound_transfers')
    to_storefront = models.ForeignKey(StoreFront, on_delete=models.CASCADE, related_name='inbound_transfers')
    quantity = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='requested_transfers')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_transfers')
    note = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'transfers'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['from_warehouse', 'status']),
            models.Index(fields=['to_storefront', 'status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.product.name} - {self.from_warehouse.name} to {self.to_storefront.name} - Qty: {self.quantity}"


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
