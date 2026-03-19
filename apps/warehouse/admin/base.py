from django.contrib import admin
from django.db.models import Sum, F
from django.utils.html import format_html

# Unfold va Import-Export komponentlari
from unfold.admin import ModelAdmin, TabularInline, StackedInline
from unfold.contrib.filters.admin import RangeNumericFilter, ChoicesDropdownFilter, FieldTextFilter
from import_export.admin import ExportMixin
from import_export import resources, fields
from import_export.widgets import ForeignKeyWidget

from apps.warehouse.models.base import (
    Category, Supplier, Product, ProductVariant, 
    PriceHistory, StockTransaction, InventoryAudit
)

# --- 1. EXCEL EKSPORT RESURSLARI ---

class ProductVariantResource(resources.ModelResource):
    product_name = fields.Field(column_name='Mahsulot', attribute='product__name')
    category = fields.Field(column_name='Kategoriya', attribute='product__category__name')

    class Meta:
        model = ProductVariant
        fields = ('product_name', 'category', 'brand', 'size', 'purchase_price', 'selling_price', 'stock')
        export_order = fields

class StockTransactionResource(resources.ModelResource):
    product = fields.Field(column_name='Mahsulot', attribute='variant__product__name')
    brand = fields.Field(column_name='Zavod', attribute='variant__brand')
    type = fields.Field(column_name='Turi', attribute='get_transaction_type_display')

    class Meta:
        model = StockTransaction
        fields = ('id', 'product', 'brand', 'type', 'quantity', 'supplier__name', 'created_at', 'note')

# --- 2. INLINES (Bog'langan ma'lumotlarni bitta sahifada ko'rish) ---

class ProductVariantInline(TabularInline):
    model = ProductVariant
    extra = 0
    tab = True # Unfold tab ko'rinishi
    show_change_link = True
    fields = ["brand", "size", "purchase_price", "selling_price", "stock"]
    readonly_fields = ["stock"]

class PriceHistoryInline(TabularInline):
    model = PriceHistory
    extra = 0
    can_delete = False
    readonly_fields = ["old_purchase_price", "new_purchase_price", "old_selling_price", "new_selling_price", "changed_at"]

# --- 3. ADMIN KLASSLARI ---

@admin.register(Category)
class CategoryAdmin(ModelAdmin):
    list_display = ["name", "parent"]
    search_fields = ["name"]
    list_filter = ["parent"]

@admin.register(Supplier)
class SupplierAdmin(ModelAdmin):
    list_display = ["name", "phone", "display_balance"]
    search_fields = ["name", "phone"]

    @admin.display(description="Balans", ordering="balance")
    def display_balance(self, obj):
        color = "red" if obj.balance > 0 else "green"
        return format_html('<span style="color: {}; font-weight: bold;">{} so\'m</span>', color, f"{obj.balance:,.0f}")

@admin.register(Product)
class ProductAdmin(ModelAdmin):
    list_display = ["name", "category", "unit", "variant_count", "is_active"]
    list_filter = [("category", ChoicesDropdownFilter), "unit", "is_active"]
    search_fields = ["name"]
    inlines = [ProductVariantInline]

    @admin.display(description="Variantlar soni")
    def variant_count(self, obj):
        return obj.variants.count()

@admin.register(ProductVariant)
class ProductVariantAdmin(ExportMixin, ModelAdmin):
    resource_class = ProductVariantResource
    list_display = ["product", "brand", "size", "purchase_price", "selling_price", "stock_badge"]
    list_filter = [("brand", ChoicesDropdownFilter), ("stock", RangeNumericFilter)]
    search_fields = ["product__name", "brand"]
    readonly_fields = ["stock"]
    inlines = [PriceHistoryInline]

    @admin.display(description="Ombor qoldig'i")
    def stock_badge(self, obj):
        if obj.stock <= obj.min_stock_limit:
            return format_html('<span style="background: #fee2e2; color: #b91c1c; padding: 2px 8px; border-radius: 4px;">⚠️ {}</span>', obj.stock)
        return format_html('<span style="background: #dcfce7; color: #15803d; padding: 2px 8px; border-radius: 4px;">✅ {}</span>', obj.stock)

@admin.register(StockTransaction)
class StockTransactionAdmin(ExportMixin, ModelAdmin):
    resource_class = StockTransactionResource
    list_display = ["variant", "transaction_type", "quantity_display", "supplier", "created_at"]
    list_filter = ["transaction_type", ("created_at", ChoicesDropdownFilter), "supplier"]
    search_fields = ["variant__product__name", "note"]
    date_hierarchy = "created_at"
    list_per_page = 20

    @admin.display(description="Miqdor")
    def quantity_display(self, obj):
        prefix = "+" if obj.transaction_type in ['IN', 'RETURN'] else "-"
        color = "green" if prefix == "+" else "orange"
        return format_html('<b style="color: {};">{}{}</b>', color, prefix, obj.quantity)

    # Statistika uchun Actions
    actions = ["calculate_total_quantity"]

    @admin.action(description="Tanlanganlar miqdorini hisoblash")
    def calculate_total_quantity(self, request, queryset):
        total = queryset.aggregate(Sum('quantity'))['quantity__sum']
        self.message_user(request, f"Tanlangan tranzaksiyalarning jami miqdori: {total}")

@admin.register(InventoryAudit)
class InventoryAuditAdmin(ModelAdmin):
    list_display = ["variant", "system_stock", "actual_stock", "difference_display", "audit_date"]
    readonly_fields = ["audit_date"]

    @admin.display(description="Farq")
    def difference_display(self, obj):
        diff = obj.actual_stock - obj.system_stock
        color = "red" if diff < 0 else "blue"
        return format_html('<b style="color: {};">{}</b>', color, diff)

@admin.register(PriceHistory)
class PriceHistoryAdmin(ModelAdmin):
    list_display = ["variant", "old_selling_price", "new_selling_price", "changed_at"]
    readonly_fields = ["variant", "old_purchase_price", "new_purchase_price", "old_selling_price", "new_selling_price", "changed_at"]
    search_fields = ["variant__product__name"]