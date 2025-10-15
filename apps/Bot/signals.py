import asyncio
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models.TelegramBot import CompanyData
from openai import AsyncOpenAI
import os

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

@receiver(post_save, sender=CompanyData)
def create_embedding_on_save(sender, instance, created, **kwargs):
    """Yangi ma’lumot qo‘shilganda avtomatik embedding yaratish"""
    if created and not instance.embedding:
        # AsyncOpenAI asinxron, signal esa sync bo‘ladi — shuning uchun asyncio.run ishlatamiz
        try:
            asyncio.run(generate_embedding(instance))
        except RuntimeError:
            # Agar event loop allaqachon ishlayotgan bo‘lsa
            loop = asyncio.get_event_loop()
            loop.create_task(generate_embedding(instance))

async def generate_embedding(instance):
    """Embedding yaratish va saqlash"""
    try:
        response = await client.embeddings.create(
            model="text-embedding-3-small",  # Tez va arzon model
            input=instance.content,
        )
        instance.embedding = response.data[0].embedding
        instance.save(update_fields=["embedding"])
        print(f"✅ Embedding avtomatik yaratildi: {instance.id}")
    except Exception as e:
        print(f"❌ Embedding yaratishda xato ({instance.id}): {e}")
