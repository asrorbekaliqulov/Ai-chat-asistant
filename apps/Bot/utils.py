from asgiref.sync import sync_to_async
from .models.TelegramBot import TelegramUser, Channel, CompanyData
import os
import re
from openai import AsyncOpenAI


async def save_user_to_db(data):
    user_id = data.id
    first_name = data.first_name
    username = data.username

    try:
        # Wrap the ORM operation with sync_to_async
        @sync_to_async
        def update_or_create_user():
            return TelegramUser.objects.update_or_create(
                user_id=user_id,  # Modeldagi `telegram_id` maydoniga moslashtirildi
                defaults={
                    "first_name": first_name,
                    "username": username,
                },
            )

        user, created = await update_or_create_user()
        return True
    except Exception as error:
        print(f"Error saving user to DB: {error}")
        return False


@sync_to_async
def create_channel(chat_id, chat_name: str, chat_type: str, url=None):
    channel = Channel.objects.create(
        channel_id=chat_id, name=chat_name, type=chat_type, url=url
    )
    return channel




OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

from difflib import SequenceMatcher

# 🧠 Bazadagi eng o‘xshash ma’lumotlarni olish
import numpy as np
from openai import AsyncOpenAI
from asgiref.sync import sync_to_async
from .models.TelegramBot import CompanyData
import os

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# 🧮 Kosinus o‘xshashligini hisoblash
def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    

@sync_to_async
def get_top_similar_data(user_vector, top_k=5):
    """Embedding asosida bazadan eng o‘xshash ma’lumotlarni olish"""
    datas = CompanyData.objects.exclude(embedding=None).values("id", "content", "embedding")
    scored = []

    for d in datas:
        emb = np.array(d["embedding"])
        sim = cosine_similarity(user_vector, emb)
        scored.append((sim, d["content"]))

    # Eng o‘xshash top_k ta ma’lumotni qaytarish
    top_matches = sorted(scored, key=lambda x: x[0], reverse=True)[:top_k]
    return "\n\n".join([m[1] for m in top_matches])



# 💬 AI asosida javob generatsiya qilish
async def generate_ai_response(user_message: str):
    similar_data = await get_top_similar_data(user_message)

    # 🔍 agar o‘xshash ma’lumot topilsa — shuni yuboramiz
    if similar_data:
        company_info = "\n\n".join(similar_data)
        context_info = f"🧾 Kompaniya haqida mos ma’lumotlar:\n{company_info}"
    else:
        context_info = "⚠️ Hech qanday mos ma’lumot topilmadi."

    # 🧠 AI uchun kontekstli prompt
    prompt = f"""
Siz Rizo Go kompaniyasi uchun mo‘ljallangan virtual yordamchisiz.
Faqat kompaniya faoliyati, xizmatlari, narxlari, joylashuvi, haydovchilar, mijozlarga xizmat, buyurtma berish kabi mavzularga oid savollarga javob bering.

Agar foydalanuvchi salomlashsa, shunday javob qaytaring:
> Assalomu alaykum! 👋 Siz Rizo Go kompaniyasining rasmiy chat botidasiz. Qanday yordam bera olaman?

Agar foydalanuvchi savoli Rizo Go kompaniyaga aloqador bo‘lmasa yoki quyidagi ma’lumotlarda javob topilmasa,
unga muloyim tarzda ayting:
> Bu savol bo‘yicha ma’lumot topilmadi. Iltimos, @Rizogo_Support bilan bog‘laning.

Foydalanuvchiga yordam berishga harakat qiling, lekin faqat kompaniya bilan bog‘liq mavzularda javob bering.
Foydalanuvchi qaysi tilda savol bersa o'sh javobingizni o'sha tilga tarjima qilib bering.
Javobingiz qisqa va aniq bo‘lsin.
{context_info}
"""

    # 🧩 ChatGPT’dan javob olish
    response = await client.chat.completions.create(
        model="gpt-4o-mini",  # yoki 3.5-turbo, yoki 4o agar byudjet bo‘lsa
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_message},
        ],
        max_tokens=300,
        temperature=0.3,
    )

    return response.choices[0].message.content.strip()


async def generate_ai_response(user_message: str):
    """AI asosida kontekstli javob yaratish"""
    
    # 1️⃣ User so‘rovini embeddingga o‘giramiz
    embedding_response = await client.embeddings.create(
        model="text-embedding-3-small",
        input=user_message,
    )
    user_vector = np.array(embedding_response.data[0].embedding)

    # 2️⃣ Bazadan eng o‘xshash ma’lumotlarni olish
    similar_info = await get_top_similar_data(user_vector, top_k=5)

    # 3️⃣ AI uchun kontekstli prompt
    prompt = f"""
Siz Rizo Go nomli kompaniya uchun mo‘ljallangan virtual yordamchisiz. Faqat Rizo Go kompaniya faoliyati, xizmatlari, narxlari, ish vaqti, joylashuvi, haydovchilar, mijozlarga xizmat, buyurtma berish va shunga o‘xshash mavzularga oid savollarga javob bering. Agar foydalanuvchi salomlashsa (masalan: "salom", "assalomu alaykum", "hi", "hello"), unga qulay va muloyim tarzda salom qaytaring, masalan: > "Assalomu alaykum! 👋 Siz Rizo Go kompaniyasining rasmiy chat botidasiz. Qanday yordam bera olaman?" Agar foydalanuvchi savoli Rizo Go kompaniyaga aloqador bo‘lmasa, yoki quyidagi kompaniya ma’lumotlari ichida aniq javob topilmasa foydalanuchi adminga bog'lanishini sizda bu savolga javob yo'qligini ayting, adminning telegram usernamesi @Rizogo_Support bilan bog'lanishini tavsiya qiling. Iloji boricha foydalanuvchiga yordam berishga harakat qiling, lekin faqat yuqoridagi mavzular doirasida javob bering va qisqa javob berishga harakat qiling.

🧾 Kompaniya haqida foydali ma’lumotlar:
{similar_info}
"""

    # 4️⃣ AI javobini olish
    response = await client.chat.completions.create(
        model="gpt-4o-mini",  # yoki 3.5-turbo agar arzonroq bo‘lishi kerak bo‘lsa
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_message},
        ],
        max_tokens=300,
        temperature=0.4,
    )

    return response.choices[0].message.content.strip()

