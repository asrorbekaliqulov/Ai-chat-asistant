from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone

class Category(models.Model):
    name = models.CharField(max_length=100)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='subcategories')

    def __str__(self):
        return self.name

class Supplier(models.Model):
    """ Ta'minotchilar (Zavod yoki dilerlar) """
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    balance = models.DecimalField(max_digits=20, decimal_places=2, default=0, help_text="Bizning ta'minotchidan qarzdorligimiz")

    def __str__(self):
        return self.name

class Product(models.Model):
    UNIT_CHOICES = [
        ('dona', 'Dona'), ('kg', 'Kilogramm'), ('m2', 'Kvadrat metr'), 
        ('m3', 'Kub metr'), ('metr', 'Metr'), ('qop', 'Qop')
    ]
    name = models.CharField(max_length=255, verbose_name="Mahsulot nomi")
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES, verbose_name="O'lchov birligi")
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='products/', blank=True, null=True, verbose_name="Asosiy rasm")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class ProductVariant(models.Model):
    """ 
    Asosiy model: Mahsulotning o'lchami va zavodiga qarab 
    alohida narx va qoldiq saqlanadi. 
    """
    product = models.ForeignKey(Product, related_name='variants', on_delete=models.CASCADE)
    brand = models.CharField(max_length=100, verbose_name="Zavod yoki Brand nomi")
    size = models.CharField(max_length=50, blank=True, null=True, verbose_name="O'lchami")
    purchase_price = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, verbose_name="Kirim narxi") # Oxirgi kirim narxi
    selling_price = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Sotish narxi")
    stock = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Qoldiq")
    min_stock_limit = models.DecimalField(max_digits=15, decimal_places=2, default=5, help_text="Ogohlantirish uchun minimal miqdor", verbose_name="Minimal qoldiq")
    image = models.ImageField(upload_to='variants/', blank=True, null=True, verbose_name="Variant rasmi")
    is_active = models.BooleanField(default=True, verbose_name="Sotuvda bormi?")
    embedding = models.JSONField(null=True, blank=True, verbose_name="Vektorli ma'lumot")
    
    def __str__(self):
        return f"{self.product.name} | {self.brand} | {self.size}"
    
    def get_search_text(self):
        """Vektor hosil qilish uchun asos bo'ladigan matn"""
        return f"{self.product.name} {self.brand} {self.size}".strip()

class PriceHistory(models.Model):
    """ Narxlar o'zgarishini kuzatish uchun """
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='price_history')
    old_purchase_price = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Eski kirim narxi")
    new_purchase_price = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Yangi kirim narxi")
    old_selling_price = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Eski sotish narxi")
    new_selling_price = models.DecimalField(max_digits=15, decimal_places=2, verbose_name="Yangi sotish narxi")
    changed_at = models.DateTimeField(auto_now_add=True)

class StockTransaction(models.Model):
    """ 
    Barcha kirim-chiqimlar tarixi. 
    Statistika aynan shu modeldan olinadi. 
    """
    TRANSACTION_TYPE = [('IN', 'Kirim'), ('OUT', 'Chiqim'), ('RETURN', 'Qaytarildi'), ('ADJUST', 'Tuzatish')]
    
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=15, decimal_places=2)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPE)
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Variant qoldig'ini avtomatik yangilash (Simple version)
        if self.transaction_type == 'IN':
            self.variant.stock += self.quantity
        elif self.transaction_type == 'OUT':
            self.variant.stock -= self.quantity
        self.variant.save()
        super().save(*args, **kwargs)

class InventoryAudit(models.Model):
    """ Omborni reviziya qilish (Inventarizatsiya) """
    audit_date = models.DateTimeField(auto_now_add=True)
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE)
    system_stock = models.DecimalField(max_digits=15, decimal_places=2) # Bazadagi qoldiq
    actual_stock = models.DecimalField(max_digits=15, decimal_places=2) # Sanalgandagi qoldiq
    difference = models.DecimalField(max_digits=15, decimal_places=2)
    reason = models.TextField(blank=True)