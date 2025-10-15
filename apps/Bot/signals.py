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
        try:
            loop = asyncio.get_running_loop()
            # Agar loop ishlayotgan bo‘lsa (masalan bot ichida)
            loop.create_task(_generate_embedding_async(instance))
        except RuntimeError:
            # Agar loop mavjud bo‘lmasa (masalan admin panel orqali save qilingan bo‘lsa)
            asyncio.run(_generate_embedding_async(instance))


async def _generate_embedding_async(instance):
    """Embedding yaratish va saqlash (to‘liq async)"""
    try:
        print(f"🔄 Embedding yaratilmoqda: {instance.id}")

        response = await client.embeddings.create(
            model="text-embedding-3-small",
            input=instance.content,
        )
        embedding_vector = response.data[0].embedding
        instance.embedding = embedding_vector

        # Bazaga asinxron saqlaymiz
        await sync_to_async(instance.save, thread_sensitive=True)(update_fields=["embedding"])
        print(f"✅ Embedding avtomatik yaratildi: {instance.id}")

    except Exception as e:
        print(f"❌ Embedding yaratishda xato ({instance.id}): {e}")
