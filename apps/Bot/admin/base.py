from django.contrib import admin
from ..models.TelegramBot import TelegramUser, CompanyData, ChatMessage, Order, OrderItem, Product
from unfold.admin import ModelAdmin
from django.db.models import Sum
from django.utils.html import format_html


@admin.register(TelegramUser)
class UserAdmin(ModelAdmin):
    list_display = (
        "user_id",
        "first_name",
        "username",
        "is_active",
        "is_admin",
        "date_joined",
        "last_active",
    )
    list_filter = ("is_active", "is_admin")
    search_fields = ("username", "first_name")
    ordering = ("user_id",)
    list_editable = ("is_active", "is_admin")


@admin.register(CompanyData)
class CompanyDataAdmin(ModelAdmin):
    list_display = ("id", "content")

@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    # Ro'yxatda ko'rinadigan ustunlar
    list_display = ('user', 'role', 'short_content', 'created_at')
    
    # Filtrlash imkoniyati
    list_filter = ('role', 'created_at', 'user')
    
    # Qidiruv maydonlari
    search_fields = ('content', 'user__first_name', 'user__username')
    
    # Faqat o'qish uchun maydonlar (tarixni o'zgartirib bo'lmasligi kerak)
    readonly_fields = ('created_at',)

    def short_content(self, obj):
        return obj.content[:50] + "..." if len(obj.content) > 50 else obj.content
    short_content.short_description = "Xabar matni"

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1  # Yangi buyurtma uchun kamida 1 ta bo'sh qator ko'rsatadi
    # readonly_fields ni olib tashladik, chunki yangi orderda atir tanlash kerak
    fields = ('product', 'quantity')

@admin.register(Order)
class OrderAdmin(ModelAdmin):
    # Ro'yxatda ko'rinadigan ustunlar
    list_display = (
        'id', 
        'user_link', 
        'package_display', 
        'price_with_discount', 
        'phone', 
        'status',
        'status_colored', 
        'created_at'
    )
    
    # Ro'yxatning o'zida statusni tezkor o'zgartirish
    list_editable = ('status',)
    
    # Filtrlash (O'ng tomonda)
    list_filter = ('status', 'package_type', 'created_at')
    
    # Qidiruv (ID, Telefon, Manzil va Mijoz ismi bo'yicha)
    search_fields = ('id', 'phone', 'address', 'user__first_name', 'user__username')
    
    # Buyurtma ichidagi atirlarni qo'shish
    inlines = [OrderItemInline]
    
    # Ma'lumotlarni tahrirlash oynasidagi guruhlar
    fieldsets = (
        ("Mijoz ma'lumotlari", {
            'fields': ('user', 'phone', 'address')
        }),
        ("Buyurtma tafsilotlari", {
            'fields': ('package_type', 'original_price', 'total_price', 'status')
        }),
        ("Vaqt", {
            'fields': ('created_at',),
        }),
    )
    
    # Narxlar va vaqtni o'zgartirib bo'lmaydi (avtomatik hisoblanadi)
    readonly_fields = ('original_price', 'total_price', 'created_at')

    # --- Maxsus ustunlar mantiqi ---

    def user_link(self, obj):
        if obj.user:
            return format_html('<a href="/admin/bot/telegramuser/{}/change/">{}</a>', 
                               obj.user.id, obj.user.first_name)
        return "Noma'lum"
    user_link.short_description = "Mijoz"

    def package_display(self, obj):
        return obj.get_package_type_display()
    package_display.short_description = "Nabor turi"

    def price_with_discount(self, obj):
        return format_html(
            '<span style="text-decoration: line-through; color: #999;">{}</span> <br> <b>{} so\'m</b>',
            obj.original_price, obj.total_price
        )
    price_with_discount.short_description = "Narxi (Chegirma)"

    def status_colored(self, obj):
        colors = {
            'new': '#d4a017',      # Oltin/Sariq
            'confirmed': '#28a745', # Yashil
            'delivered': '#007bff', # Ko'k
        }
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            colors.get(obj.status, 'black'),
            obj.get_status_display()
        )
    status_colored.short_description = "Status"

    # Buyurtmalarni yangisidan eskisiga saralash
    ordering = ('-created_at',)



@admin.register(Product)
class ProductAdmin(ModelAdmin):
    # Ro'yxatda ko'rinadigan ustunlar
    list_display = ('name', 'brand', 'gender', 'total_sold_display', 'is_active')
    
    # Filtrlash (Brend, Jins va Sotuvda borligi bo'yicha)
    list_filter = ('brand', 'gender', 'is_active')
    
    # Qidiruv (Atir nomi va brendi bo'yicha)
    search_fields = ('name', 'brand')
    
    # Sotuvda borligini ro'yxatning o'zida o'zgartirish
    list_editable = ('is_active',)
    
    # Faqat o'qish uchun (Statistikani o'zgartirib bo'lmaydi)
    readonly_fields = ('total_sold_display',)

    def total_sold_display(self, obj):
        """
        Har bir atirning naborlar ichida jami necha dona sotilganini 
        hisoblab chiqaruvchi funksiya.
        """
        # OrderItem modelidagi quantity ustunini yig'indisini hisoblaymiz
        total = obj.sales.aggregate(total=Sum('quantity'))['total']
        
        if total and total > 0:
            return f"{total} dona (10ml)"
        return "Sotilmagan"
    
    total_sold_display.short_description = "Jami sotuv (Statistika)"

    # Ma'lumot qo'shish oynasini guruhlash
    fieldsets = (
        ("Asosiy ma'lumotlar", {
            'fields': ('brand', 'name', 'gender', 'is_active')
        }),
        ("Tavsif va Akkordlar", {
            'fields': ('description',),
            'description': "Katalogdagi kabi sitrusli, mevali yoki yog'ochli kabi ma'lumotlarni yozing."
        }),
        ("Statistika", {
            'fields': ('total_sold_display',),
        }),
    )
