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
@sync_to_async
def get_similar_company_data(user_message: str, limit: int = 10, threshold: float = 0.2):
    """
    Foydalanuvchi so‘rovi bilan eng o‘xshash 10 ta ma’lumotni qaytaradi.
    threshold – o‘xshashlik minimal foizi 0.0 - 1.0 oralig‘ida
    """
    all_data = list(CompanyData.objects.all().values_list("content", flat=True))
    scored = []

    for item in all_data:
        ratio = SequenceMatcher(None, user_message.lower(), item.lower()).ratio()
        if ratio >= threshold:
            scored.append((ratio, item))

    # eng o‘xshashlarini tartiblab olish
    scored.sort(reverse=True, key=lambda x: x[0])
    similar_data = [text for _, text in scored[:limit]]

    # agar hech narsa topilmasa – bo‘sh ro‘yxat qaytadi
    return similar_data


# 💬 AI asosida javob generatsiya qilish
async def generate_ai_response(user_message: str):
    similar_data = await get_similar_company_data(user_message)

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
