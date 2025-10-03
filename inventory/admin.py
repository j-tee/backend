from django.contrib import admin
from .models import (
    Category, Warehouse, StoreFront, Product, Supplier, Stock, StockProduct,
    Inventory, StoreFrontInventory, Transfer, TransferLineItem, TransferAuditEntry, StockAlert
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


@admin.register(StoreFrontInventory)
class StoreFrontInventoryAdmin(admin.ModelAdmin):
    list_display = ['product', 'storefront', 'quantity', 'updated_at']
    search_fields = ['product__name', 'product__sku', 'storefront__name']
    list_filter = ['storefront', 'updated_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['product__name']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product', 'storefront')


class TransferLineItemInline(admin.TabularInline):
    model = TransferLineItem
    extra = 0
    fields = ['product', 'requested_quantity', 'approved_quantity', 'fulfilled_quantity', 'unit_of_measure', 'notes']
    readonly_fields = ['created_at', 'updated_at']
    show_change_link = True


class TransferAuditEntryInline(admin.TabularInline):
    model = TransferAuditEntry
    extra = 0
    fields = ['action', 'actor', 'remarks', 'created_at']
    readonly_fields = ['action', 'actor', 'remarks', 'created_at']
    can_delete = False
    ordering = ['created_at']


@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = ['reference', 'business', 'source_warehouse', 'destination_storefront', 'status', 'submitted_at', 'approved_at', 'dispatched_at', 'completed_at']
    search_fields = ['reference', 'business__name', 'source_warehouse__name', 'destination_storefront__name']
    list_filter = ['status', 'source_warehouse', 'destination_storefront', 'created_at']
    readonly_fields = [
        'id', 'reference', 'business', 'status', 'requested_by', 'approved_by', 'fulfilled_by',
        'submitted_at', 'approved_at', 'dispatched_at', 'completed_at', 'rejected_at', 'cancelled_at',
        'created_at', 'updated_at'
    ]
    ordering = ['-created_at']
    inlines = [TransferLineItemInline, TransferAuditEntryInline]

    fieldsets = (
        ('Transfer Details', {
            'fields': ('id', 'reference', 'business', 'status', 'notes')
        }),
        ('Participants', {
            'fields': ('source_warehouse', 'destination_storefront', 'requested_by', 'approved_by', 'fulfilled_by')
        }),
        ('Timeline', {
            'fields': ('submitted_at', 'approved_at', 'dispatched_at', 'completed_at', 'rejected_at', 'cancelled_at', 'created_at', 'updated_at'),
            'classes': ('collapse',)
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
