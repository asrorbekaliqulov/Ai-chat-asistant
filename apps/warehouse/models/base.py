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
    name = models.CharField(max_length=255)
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    unit = models.CharField(max_length=10, choices=UNIT_CHOICES)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class ProductVariant(models.Model):
    """ 
    Asosiy model: Mahsulotning o'lchami va zavodiga qarab 
    alohida narx va qoldiq saqlanadi. 
    """
    product = models.ForeignKey(Product, related_name='variants', on_delete=models.CASCADE)
    brand = models.CharField(max_length=100)
    size = models.CharField(max_length=50, blank=True, null=True)
    purchase_price = models.DecimalField(max_digits=15, decimal_places=2) # Oxirgi kirim narxi
    selling_price = models.DecimalField(max_digits=15, decimal_places=2)
    stock = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    min_stock_limit = models.DecimalField(max_digits=15, decimal_places=2, default=5, help_text="Ogohlantirish uchun minimal miqdor")

    def __str__(self):
        return f"{self.product.name} | {self.brand} | {self.size}"

class PriceHistory(models.Model):
    """ Narxlar o'zgarishini kuzatish uchun """
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='price_history')
    old_purchase_price = models.DecimalField(max_digits=15, decimal_places=2)
    new_purchase_price = models.DecimalField(max_digits=15, decimal_places=2)
    old_selling_price = models.DecimalField(max_digits=15, decimal_places=2)
    new_selling_price = models.DecimalField(max_digits=15, decimal_places=2)
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