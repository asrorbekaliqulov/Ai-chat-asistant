import asyncio
from django.db.models.signals import post_save
from django.dispatch import receiver
from asgiref.sync import sync_to_async
from .models.TelegramBot import CompanyData
from openai import AsyncOpenAI
import os

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = AsyncOpenAI(api_key=OPENAI_API_KEY)


@receiver(post_save, sender=CompanyData)
def create_embedding_on_save(sender, instance, created, **kwargs):
    """Yangi ma’lumot qo‘shilganda avtomatik embedding yaratish"""
    if created and not instance.embedding:
        # Signal sync ishlaydi, lekin embedding async — shuning uchun toza bridge orqali ishga tushiramiz
        asyncio.create_task(_generate_embedding_async(instance))


async def _generate_embedding_async(instance):
    """Embedding yaratish va saqlash (to‘liq async)"""
    try:
        response = await client.embeddings.create(
            model="text-embedding-3-small",
            input=instance.content,
        )
        embedding_vector = response.data[0].embedding

        # Bazaga asinxron saqlaymiz
        await sync_to_async(instance.save, thread_sensitive=True)(update_fields=["embedding"])
        instance.embedding = embedding_vector

        print(f"✅ Embedding avtomatik yaratildi: {instance.id}")
    except Exception as e:
        print(f"❌ Embedding yaratishda xato ({instance.id}): {e}")
