from django.contrib import admin
from .models import (
    Category, Warehouse, StoreFront, Product, Supplier, Stock, StockProduct,
    StoreFrontInventory, TransferRequest, TransferRequestLineItem, StockAlert
)
from .stock_adjustments import (
    StockAdjustment, StockAdjustmentPhoto, StockAdjustmentDocument,
    StockCount, StockCountItem
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
    list_display = ['arrival_date', 'created_at']
    search_fields = ['description']
    list_filter = ['arrival_date', 'created_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['-arrival_date']


@admin.register(StockProduct)
class StockProductAdmin(admin.ModelAdmin):
    list_display = ['product', 'warehouse', 'supplier', 'quantity', 'unit_cost', 'unit_tax_amount', 'unit_additional_cost', 'landed_unit_cost', 'expiry_date', 'created_at']
    search_fields = ['product__name', 'product__sku', 'warehouse__name', 'supplier__name']
    list_filter = ['warehouse', 'supplier', 'expiry_date', 'created_at']
    readonly_fields = ['id', 'created_at', 'updated_at', 'landed_unit_cost', 'total_base_cost', 'total_tax_amount', 'total_additional_cost', 'total_landed_cost']
    ordering = ['product__name']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'stock', 'warehouse', 'product', 'supplier', 'quantity', 'expiry_date', 'description')
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


@admin.register(StoreFrontInventory)
class StoreFrontInventoryAdmin(admin.ModelAdmin):
    list_display = ['product', 'storefront', 'quantity', 'updated_at']
    search_fields = ['product__name', 'product__sku', 'storefront__name']
    list_filter = ['storefront', 'updated_at']
    readonly_fields = ['id', 'created_at', 'updated_at']
    ordering = ['product__name']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product', 'storefront')


class TransferRequestLineItemInline(admin.TabularInline):
    model = TransferRequestLineItem
    extra = 0
    fields = ['product', 'requested_quantity', 'unit_of_measure', 'notes', 'created_at', 'updated_at']
    readonly_fields = ['created_at', 'updated_at']
    show_change_link = False


@admin.register(TransferRequest)
class TransferRequestAdmin(admin.ModelAdmin):
    list_display = ['storefront', 'business', 'priority', 'status', 'requested_by', 'fulfilled_by', 'cancelled_by', 'created_at']
    search_fields = ['storefront__name', 'business__name', 'requested_by__name', 'fulfilled_by__name', 'cancelled_by__name']
    list_filter = ['status', 'priority', 'storefront', 'business', 'created_at']
    readonly_fields = ['id', 'business', 'fulfilled_at', 'fulfilled_by', 'cancelled_at', 'cancelled_by', 'created_at', 'updated_at']
    ordering = ['-created_at']
    inlines = [TransferRequestLineItemInline]

    fieldsets = (
        ('Request Details', {
            'fields': ('id', 'storefront', 'business', 'priority', 'status', 'notes')
        }),
        ('People', {
            'fields': ('requested_by', 'fulfilled_by', 'cancelled_by')
        }),
        ('Timeline', {
            'fields': ('fulfilled_at', 'cancelled_at', 'created_at', 'updated_at'),
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


class StockAdjustmentPhotoInline(admin.TabularInline):
    model = StockAdjustmentPhoto
    extra = 0
    fields = ['photo', 'description', 'uploaded_at', 'uploaded_by']
    readonly_fields = ['uploaded_at', 'uploaded_by']


class StockAdjustmentDocumentInline(admin.TabularInline):
    model = StockAdjustmentDocument
    extra = 0
    fields = ['document', 'document_type', 'description', 'uploaded_at', 'uploaded_by']
    readonly_fields = ['uploaded_at', 'uploaded_by']


@admin.register(StockAdjustment)
class StockAdjustmentAdmin(admin.ModelAdmin):
    list_display = [
        'created_at', 'adjustment_type', 'stock_product', 'quantity',
        'total_cost', 'status', 'created_by', 'approved_by'
    ]
    search_fields = [
        'stock_product__product__name', 'reason', 'reference_number',
        'created_by__email', 'approved_by__email'
    ]
    list_filter = [
    'adjustment_type', 'status', 'requires_approval',
    'created_at', 'stock_product__warehouse'
    ]
    readonly_fields = [
        'id', 'total_cost', 'financial_impact', 'is_increase', 'is_decrease',
        'created_at', 'approved_at', 'completed_at'
    ]
    ordering = ['-created_at']
    inlines = [StockAdjustmentPhotoInline, StockAdjustmentDocumentInline]
    
    fieldsets = (
        ('Adjustment Details', {
            'fields': (
                'id', 'business', 'stock_product', 'adjustment_type',
                'quantity', 'unit_cost', 'total_cost'
            )
        }),
        ('Documentation', {
            'fields': ('reason', 'reference_number', 'has_photos', 'has_documents')
        }),
        ('Approval', {
            'fields': (
                'status', 'requires_approval', 'created_by',
                'approved_by', 'approved_at'
            )
        }),
        ('Related Items', {
            'fields': ('related_sale',)
        }),
        ('Computed', {
            'fields': ('financial_impact', 'is_increase', 'is_decrease'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_adjustments', 'complete_adjustments']
    
    def approve_adjustments(self, request, queryset):
        """Approve selected pending adjustments"""
        pending = queryset.filter(status='PENDING')
        count = 0
        for adjustment in pending:
            try:
                adjustment.approve(request.user)
                count += 1
            except Exception:
                pass
        self.message_user(request, f"{count} adjustments approved.")
    approve_adjustments.short_description = "Approve selected adjustments"
    
    def complete_adjustments(self, request, queryset):
        """Complete selected approved adjustments"""
        approved = queryset.filter(status='APPROVED')
        count = 0
        errors = 0
        for adjustment in approved:
            try:
                adjustment.complete()
                count += 1
            except Exception:
                errors += 1
        self.message_user(request, f"{count} adjustments completed, {errors} errors.")
    complete_adjustments.short_description = "Complete selected approved adjustments"


@admin.register(StockAdjustmentPhoto)
class StockAdjustmentPhotoAdmin(admin.ModelAdmin):
    list_display = ['adjustment', 'description', 'uploaded_at', 'uploaded_by']
    search_fields = ['adjustment__reason', 'description']
    list_filter = ['uploaded_at']
    readonly_fields = ['id', 'uploaded_at']
    ordering = ['-uploaded_at']


@admin.register(StockAdjustmentDocument)
class StockAdjustmentDocumentAdmin(admin.ModelAdmin):
    list_display = ['adjustment', 'document_type', 'description', 'uploaded_at', 'uploaded_by']
    search_fields = ['adjustment__reason', 'description']
    list_filter = ['document_type', 'uploaded_at']
    readonly_fields = ['id', 'uploaded_at']
    ordering = ['-uploaded_at']


class StockCountItemInline(admin.TabularInline):
    model = StockCountItem
    extra = 0
    fields = [
        'stock_product', 'system_quantity', 'counted_quantity',
        'discrepancy', 'counter_name', 'adjustment_created'
    ]
    readonly_fields = ['discrepancy', 'counted_at', 'adjustment_created']


@admin.register(StockCount)
class StockCountAdmin(admin.ModelAdmin):
    list_display = [
        'count_date', 'business', 'storefront', 'warehouse',
        'status', 'created_by', 'created_at'
    ]
    search_fields = ['business__name', 'notes']
    list_filter = ['status', 'count_date', 'storefront', 'warehouse']
    readonly_fields = ['id', 'created_at', 'completed_at']
    ordering = ['-count_date']
    inlines = [StockCountItemInline]
    
    fieldsets = (
        ('Count Details', {
            'fields': ('id', 'business', 'count_date', 'status', 'notes')
        }),
        ('Scope', {
            'fields': ('storefront', 'warehouse')
        }),
        ('Audit', {
            'fields': ('created_by', 'created_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['complete_counts']
    
    def complete_counts(self, request, queryset):
        """Complete selected stock counts"""
        in_progress = queryset.filter(status='IN_PROGRESS')
        count = 0
        for stock_count in in_progress:
            try:
                stock_count.complete()
                count += 1
            except Exception:
                pass
        self.message_user(request, f"{count} stock counts completed.")
    complete_counts.short_description = "Complete selected stock counts"


@admin.register(StockCountItem)
class StockCountItemAdmin(admin.ModelAdmin):
    list_display = [
        'stock_count', 'stock_product', 'system_quantity',
        'counted_quantity', 'discrepancy', 'adjustment_created'
    ]
    search_fields = [
        'stock_count__id', 'stock_product__product__name',
        'counter_name'
    ]
    list_filter = ['stock_count__count_date', 'stock_count__status']
    readonly_fields = ['id', 'discrepancy', 'counted_at']
    ordering = ['-counted_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'stock_count', 'stock_product', 'stock_product__product'
        )
