import os
from django.db.models.signals import post_save
from django.dispatch import receiver
from google import genai
from apps.warehouse.models.base import ProductVariant

# Gemini Client sozlamasi
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

@receiver(post_save, sender=ProductVariant)
def update_product_embedding(sender, instance, created, **kwargs):
    """
    Mahsulot yaratilganda yoki tahrirlanganda embeddingni yangilash.
    """
    # 1. Embedding uchun matn tayyorlash
    # Masalan: "Sement Abu Saxiy 50kg"
    search_text = f"{instance.product.name} {instance.brand} {instance.size}".strip().lower()

    # 2. Tekshiruv: Agar tahrirlanayotgan bo'lsa va matn o'zgarmagan bo'lsa, 
    # qayta embedding qilish shart emas (API xarajatini tejash uchun)
    # Buning uchun vaqtinchalik 'old_text' ni tekshirish mantiqi kerak bo'lishi mumkin,
    # lekin soddalik uchun har doim yangilaymiz yoki null bo'lsa yangilaymiz.
    
    # 3. Faqat kerak bo'lganda embedding olish mantiqi
    try:
        # Gemini API orqali vektor olish
        response = client.models.embed_content(
            model="gemini-embedding-001",
            contents=search_text
        )
        vector = response.embeddings[0].values

        # 4. 'post_save' ichida 'save()' chaqirishda 'recursion' (cheksiz takrorlanish) 
        # bo'lmasligi uchun 'update' metodidan foydalanamiz
        ProductVariant.objects.filter(pk=instance.pk).update(embedding=vector)
        
    except Exception as e:
        print(f"Embedding yaratishda xatolik: {e}")