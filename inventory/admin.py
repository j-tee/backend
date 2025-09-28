from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Category, Warehouse, StoreFront, Batch, Product, 
    BatchProduct, Inventory, Transfer, StockAlert
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'parent', 'created_at']
    search_fields = ['name', 'description']
    list_filter = ['parent', 'created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['name']


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ['name', 'location', 'manager', 'created_at']
    search_fields = ['name', 'location']
    list_filter = ['manager', 'created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['name']


@admin.register(StoreFront)
class StoreFrontAdmin(admin.ModelAdmin):
    list_display = ['name', 'user', 'location', 'manager', 'created_at']
    search_fields = ['name', 'location', 'user__name']
    list_filter = ['user', 'manager', 'created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['name']


class BatchProductInline(admin.TabularInline):
    model = BatchProduct
    extra = 0
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    inlines = [BatchProductInline]
    list_display = ['package_code', 'warehouse', 'supplier', 'arrival_date', 'created_at']
    search_fields = ['package_code', 'supplier', 'description']
    list_filter = ['warehouse', 'arrival_date', 'created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-arrival_date']
    date_hierarchy = 'arrival_date'


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'sku', 'category', 'retail_price', 'wholesale_price', 'cost', 'is_active']
    search_fields = ['name', 'sku', 'description']
    list_filter = ['category', 'is_active', 'created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'sku', 'description', 'category', 'unit', 'is_active')
        }),
        ('Pricing', {
            'fields': ('cost', 'retail_price', 'wholesale_price')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(BatchProduct)
class BatchProductAdmin(admin.ModelAdmin):
    list_display = ['batch', 'product', 'quantity', 'created_at']
    search_fields = ['batch__package_code', 'product__name', 'product__sku']
    list_filter = ['batch__warehouse', 'created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-created_at']


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ['product', 'warehouse', 'batch', 'quantity', 'updated_at']
    search_fields = ['product__name', 'product__sku', 'warehouse__name']
    list_filter = ['warehouse', 'updated_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['product__name']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product', 'warehouse', 'batch')


@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = ['product', 'from_warehouse', 'to_storefront', 'quantity', 'status', 'created_at']
    search_fields = ['product__name', 'product__sku', 'from_warehouse__name', 'to_storefront__name']
    list_filter = ['status', 'from_warehouse', 'to_storefront', 'created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Transfer Details', {
            'fields': ('id', 'product', 'batch', 'quantity', 'status')
        }),
        ('Location', {
            'fields': ('from_warehouse', 'to_storefront')
        }),
        ('Authorization', {
            'fields': ('requested_by', 'approved_by')
        }),
        ('Additional Info', {
            'fields': ('note', 'created_at', 'updated_at')
        }),
    )


@admin.register(StockAlert)
class StockAlertAdmin(admin.ModelAdmin):
    list_display = ['product', 'warehouse', 'alert_type', 'current_quantity', 'threshold_quantity', 'is_resolved', 'created_at']
    search_fields = ['product__name', 'product__sku', 'warehouse__name']
    list_filter = ['alert_type', 'is_resolved', 'warehouse', 'created_at']
    readonly_fields = ['id', 'created_at', 'resolved_at']
    ordering = ['-created_at']
    
    actions = ['mark_resolved']
    
    def mark_resolved(self, request, queryset):
        from django.utils import timezone
        queryset.update(is_resolved=True, resolved_at=timezone.now())
        self.message_user(request, f"{queryset.count()} alerts marked as resolved.")
    mark_resolved.short_description = "Mark selected alerts as resolved"
