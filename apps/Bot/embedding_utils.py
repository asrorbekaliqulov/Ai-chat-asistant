import asyncio
import os
import numpy as np
from google import genai  # Yangi SDK
from django.conf import settings
from asgiref.sync import sync_to_async
from .models.TelegramBot import CompanyData

# 🔐 Yangi SDK Clientini sozlash
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

async def update_company_embeddings():
    """Bazadagi contentlardan yangi SDK orqali Gemini embedding yaratish va saqlash"""

    # 🧠 Embeddingi yo‘q ma’lumotlarni olish
    datas = await sync_to_async(list)(
        CompanyData.objects.filter(embedding__isnull=True)
    )

    if not datas:
        print("✅ Hamma ma'lumotlar Gemini embeddingiga o‘girilgan.")
        return

    print(f"🚀 {len(datas)} ta ma'lumotni qayta ishlash boshlandi...")

    # 🔁 Har bir ma’lumot uchun embedding yaratish
    for data in datas:
        try:
            print(f"🔄 Gemini embedding (v4) yaratilmoqda: {data.id}")
            
            # Yangi SDK-da metod: client.models.embed_content
            result = client.models.embed_content(
                model="gemini-embedding-001",
                contents=data.content,
                config={
                    'task_type': 'RETRIEVAL_DOCUMENT'
                }
            )

            # Natijani olish formati o'zgargan: .embeddings[0].values
            embedding_vector = result.embeddings[0].values

            # 🧩 Ma’lumotni saqlash
            data.embedding = embedding_vector
            await sync_to_async(data.save)(update_fields=["embedding"])

            print(f"✅ Muvaffaqiyatli saqlandi: {data.id}")

            # API Rate Limit'ga tushmaslik uchun juda qisqa tanaffus (ixtiyoriy)
            await asyncio.sleep(0.1) 

        except Exception as e:
            print(f"❌ Xato: ID {data.id} - {e}")

# 🔄 Scriptni ishga tushirish (Django muhitida)
if __name__ == "__main__":
   
    asyncio.run(update_company_embeddings())