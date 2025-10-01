from django.contrib import admin
from .models import (
    Category, Warehouse, StoreFront, Product, Supplier, Stock, StockProduct,
    Inventory, Transfer, StockAlert
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


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'sku', 'category', 'unit', 'is_active']
    search_fields = ['name', 'sku', 'description']
    list_filter = ['category', 'is_active', 'created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'name', 'sku', 'description', 'category', 'unit', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['name', 'contact_person', 'email', 'phone_number', 'created_at']
    search_fields = ['name', 'contact_person', 'email', 'phone_number']
    list_filter = ['created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['name']


@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ['warehouse', 'arrival_date', 'created_at']
    search_fields = ['warehouse__name']
    list_filter = ['warehouse', 'arrival_date', 'created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-arrival_date']


@admin.register(StockProduct)
class StockProductAdmin(admin.ModelAdmin):
    list_display = ['product', 'warehouse', 'supplier', 'quantity', 'unit_cost', 'unit_tax_amount', 'unit_additional_cost', 'landed_unit_cost', 'expiry_date', 'created_at']
    search_fields = ['product__name', 'product__sku', 'stock__warehouse__name', 'supplier__name']
    list_filter = ['stock__warehouse', 'supplier', 'expiry_date', 'created_at']
    readonly_fields = ['id', 'created_at', 'updated_at', 'landed_unit_cost', 'total_base_cost', 'total_tax_amount', 'total_additional_cost', 'total_landed_cost']
    ordering = ['product__name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'stock', 'product', 'supplier', 'quantity', 'expiry_date', 'description')
        }),
        ('Cost Details', {
            'fields': ('unit_cost', 'unit_tax_rate', 'unit_tax_amount', 'unit_additional_cost')
        }),
        ('Calculated Costs', {
            'fields': ('landed_unit_cost', 'total_base_cost', 'total_tax_amount', 'total_additional_cost', 'total_landed_cost'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ['product', 'warehouse', 'stock', 'quantity', 'updated_at']
    search_fields = ['product__name', 'product__sku', 'warehouse__name', 'stock__product__name']
    list_filter = ['warehouse', 'updated_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['product__name']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product', 'warehouse', 'stock')


@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = ['product', 'stock', 'from_warehouse', 'to_storefront', 'quantity', 'status', 'created_at']
    search_fields = ['product__name', 'product__sku', 'stock__product__name', 'from_warehouse__name', 'to_storefront__name']
    list_filter = ['status', 'from_warehouse', 'to_storefront', 'created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Transfer Details', {
            'fields': ('id', 'product', 'stock', 'quantity', 'status')
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
