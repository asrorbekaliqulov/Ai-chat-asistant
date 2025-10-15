# apps/Bot/signals.py
import asyncio
import time
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from asgiref.sync import sync_to_async
from openai import AsyncOpenAI
import os

from .models.TelegramBot import CompanyData

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

MAX_SAVE_RETRIES = 5
SAVE_RETRY_DELAY = 0.5  # boshida kutish (soniyalar)


@receiver(post_save, sender=CompanyData)
def create_embedding_on_save(sender, instance, created, **kwargs):
    """
    Yangi CompanyData yaratilganda commit tugagach embedding yaratish ishini boshlaydi.
    Bu transaction.on_commit orqali amalga oshadi — shunda DB lock ehtimoli kamayadi.
    """
    if created and not instance.embedding:
        # on_commit ichida biz sync funksiya ishlatamiz, u esa eventloop mavjud bo'lsa create_task qiladi,
        # aks holda asyncio.run orqali bajaradi.
        def _after_commit():
            try:
                loop = asyncio.get_running_loop()
                # agar loop ishlayotgan bo'lsa (masalan bot ichida) — fon task yaratamiz
                loop.create_task(_generate_and_save_embedding(instance.id))
            except RuntimeError:
                # agar event loop mavjud bo'lmasa (masalan admin paneldan save qilingan) — yangi loop bilan ishlatamiz
                asyncio.run(_generate_and_save_embedding(instance.id))

        transaction.on_commit(_after_commit)


async def _generate_and_save_embedding(instance_id: int):
    """
    Berilgan instance_id uchun embedding yaratadi va retry bilan saqlaydi.
    Db-lock holatlariga qarshi retry qo'llanadi.
    """
    try:
        # Avval instance'ni DBdan olamiz (sync)
        instance = await sync_to_async(CompanyData.objects.get)(id=instance_id)
    except Exception as e:
        print(f"❌ Embedding: instance topilmadi {instance_id} — {e}")
        return

    # Embedding yaratilishi
    try:
        print(f"🔄 Embedding yaratilmoqda: {instance_id}")
        resp = await client.embeddings.create(
            model="text-embedding-3-small",
            input=instance.content,
        )
        embedding_vector = resp.data[0].embedding
    except Exception as e:
        print(f"❌ Embedding yaratishda xato ({instance_id}): {e}")
        return

    # Saqlashni retry bilan amalga oshiramiz
    for attempt in range(1, MAX_SAVE_RETRIES + 1):
        try:
            # instance ni qayta olish — concurrency holatlarida to'g'ri ob'ektni olamiz
            inst = await sync_to_async(CompanyData.objects.select_for_update().get)(id=instance_id)
            inst.embedding = embedding_vector
            # saqlash (sync to async)
            await sync_to_async(inst.save, thread_sensitive=True)(update_fields=["embedding"])
            print(f"✅ Embedding avtomatik saqlandi: {instance_id}")
            return
        except Exception as e:
            msg = str(e).lower()
            # SQLite locked xatosi uchun qayta urin
            if "database is locked" in msg or "database is busy" in msg or "database is locked" in msg:
                wait = SAVE_RETRY_DELAY * attempt
                print(f"⚠️ DB locked, retry {attempt}/{MAX_SAVE_RETRIES} — kutilyapti {wait}s")
                await asyncio.sleep(wait)
                continue
            else:
                # boshqa xato bo'lsa — log qiling va chiqamiz
                print(f"❌ Embedding saqlash xatosi ({instance_id}): {e}")
                return

    print(f"❌ Embedding saqlanmadi — maksimal retry tugadi: {instance_id}")
