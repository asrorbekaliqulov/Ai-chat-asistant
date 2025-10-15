import asyncio
import os
from openai import AsyncOpenAI
from django.conf import settings
from asgiref.sync import sync_to_async
from .models.TelegramBot import CompanyData

# 🔐 API kalit
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = AsyncOpenAI(api_key=OPENAI_API_KEY)


async def update_company_embeddings():
    """Bazadagi contentlardan embedding yaratish va saqlash (to‘liq asinxron)"""

    # 🧠 Embedding yo‘q ma’lumotlarni olish (asinxron)
    datas = await sync_to_async(list)(
        CompanyData.objects.filter(embedding__isnull=True)
    )

    if not datas:
        print("✅ Hamma ma'lumotlar embeddingga o‘girilgan.")
        return

    # 🔁 Har bir ma’lumot uchun embedding yaratish
    for data in datas:
        try:
            print(f"🔄 Embedding yaratilmoqda: {data.id}")
            response = await client.embeddings.create(
                model="text-embedding-3-small",  # 🔹 Arzon va tez model
                input=data.content,
            )

            embedding_vector = response.data[0].embedding

            # 🧩 Ma’lumotni saqlash (asinxron)
            await sync_to_async(setattr)(data, "embedding", embedding_vector)
            await sync_to_async(data.save)()

            print(f"✅ Embedding saqlandi: {data.id}")

        except Exception as e:
            print(f"❌ Xato: {data.id} - {e}")


# 🔄 Test uchun ishga tushirish (shell yoki scriptda)
if __name__ == "__main__":
    asyncio.run(update_company_embeddings())
