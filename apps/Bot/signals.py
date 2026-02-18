import os
import asyncio
from google import genai
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from asgiref.sync import sync_to_async
from .models.TelegramBot import CompanyData

# SDK Clientini yaratish
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

MAX_SAVE_RETRIES = 5
SAVE_RETRY_DELAY = 0.5

@receiver(post_save, sender=CompanyData)
def create_embedding_on_save(sender, instance, created, **kwargs):
    if created and not instance.embedding:
        def _after_commit():
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(_generate_and_save_embedding(instance.id))
            except RuntimeError:
                asyncio.run(_generate_and_save_embedding(instance.id))

        transaction.on_commit(_after_commit)

async def _generate_and_save_embedding(instance_id: int):
    try:
        instance = await sync_to_async(CompanyData.objects.get)(id=instance_id)
    except Exception:
        return

    try:
        print(f"🔄 Yangi SDK orqali embedding: {instance_id}")
        # Yangi SDK-da metod nomi biroz boshqacha
        result = client.models.embed_content(
            model="gemini-embedding-001",
            contents=instance.content,
            config={
                'task_type': 'RETRIEVAL_DOCUMENT'
            }
        )
        # Natija olish formati: result.embeddings[0].values
        embedding_vector = result.embeddings[0].values
    except Exception as e:
        print(f"❌ Xatolik: {e}")
        return

    # Saqlash qismi (o'zgarishsiz qoladi)
    for attempt in range(1, MAX_SAVE_RETRIES + 1):
        try:
            inst = await sync_to_async(CompanyData.objects.get)(id=instance_id)
            inst.embedding = embedding_vector
            await sync_to_async(inst.save, thread_sensitive=True)(update_fields=["embedding"])
            print(f"✅ Embedding yangi SDK orqali saqlandi.")
            return
        except Exception as e:
            if "locked" in str(e).lower():
                await asyncio.sleep(SAVE_RETRY_DELAY * attempt)
                continue
            break