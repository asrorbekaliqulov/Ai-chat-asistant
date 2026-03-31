import os
import re
import json
from asgiref.sync import sync_to_async
from django.db.models import Q
from google import genai
from google.genai import types

from telegram import Update
from telegram.constants import ChatMemberStatus
from telegram.ext import ContextTypes

# Modellarni import qilish (Proyektingizdagi yo'llar bilan mosligini tekshiring)
from apps.warehouse.models.base import ProductVariant
from apps.Bot.models.TelegramBot import CompanyData, ChatMessage
from apps.Bot.utils import save_message_to_db
from apps.Bot.decorators import typing_action

# Gemini Client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

class AIManager:
    @staticmethod
    @sync_to_async
    def get_chat_history(t_user_id, limit=6):
        """Foydalanuvchi bilan bo'lgan oxirgi suhbatlar tarixini olish"""
        msgs = ChatMessage.objects.filter(user__user_id=t_user_id).order_by('-created_at')[:limit]
        history = []
        for m in reversed(msgs):
            role = "user" if m.role in ['user', 'admin'] else "model"
            history.append(types.Content(role=role, parts=[types.Part.from_text(text=m.content)]))
        return history

    @staticmethod
    @sync_to_async
    def get_inventory_data(keywords):
        """Ombordan mahsulotlarni qidirish mantiqi"""
        if not keywords: return None
        query_filter = Q()
        for word in keywords:
            query_filter |= Q(product__name__icontains=word) | Q(brand__icontains=word)
        
        variants = ProductVariant.objects.filter(query_filter).select_related('product').distinct()[:5]
        if not variants.exists(): return None
        
        data_list = []
        for v in variants:
            size_info = getattr(v, 'attribute', '') or getattr(v, 'size', '') or ""
            data_list.append({
                "product": f"{v.product.name} {size_info}".strip(),
                "price": f"{v.selling_price:,.0f} so'm",
                "stock": f"{v.stock} {v.product.unit}",
                "image_path": v.image.path if v.image and os.path.exists(v.image.path) else None,
            })
        return data_list

    @staticmethod
    @sync_to_async
    def get_company_info(topic):
        """Do'kon haqidagi umumiy ma'lumotlarni bazadan qidirish"""
        rules = CompanyData.objects.filter(Q(content__icontains=topic))[:3]
        if not rules.exists():
            rules = CompanyData.objects.all().order_by('-id')[:5]
        return "\n".join([f"- {r.content}" for r in rules])

# AI Toollar (Funksiyalar deklaratsiyasi)
tools = [types.Tool(function_declarations=[
    types.FunctionDeclaration(
        name="search_warehouse",
        description="Ombordan mahsulot qidirish (nomi, brendi yoki turi bo'yicha).",
        parameters=types.Schema(
            type="OBJECT", 
            properties={"keywords": types.Schema(type="ARRAY", items=types.Schema(type="STRING"))}, 
            required=["keywords"]
        )
    ),
    types.FunctionDeclaration(
        name="search_store_knowledge",
        description="Do'kon manzili, ish vaqti, Islom aka yoki Zohid raqamlari haqida ma'lumot.",
        parameters=types.Schema(type="OBJECT", properties={"topic": types.Schema(type="STRING")}, required=["topic"])
    )
])]

@typing_action
async def ai_group_assistant(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    if not update.message or not update.message.text: return
    
    user = update.effective_user
    user_msg = update.message.text
    chat_id = update.effective_chat.id

    # Foydalanuvchi statusini tekshirish
    member = await context.bot.get_chat_member(chat_id, user.id)
    is_admin = member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    
    # Xabarni bazaga saqlash
    await save_message_to_db(user.id, 'admin' if is_admin else 'user', user_msg)

    # Admin xabarlariga AI javob bermaydi
    if is_admin: return

    # SYSTEM INSTRUCTION: Asosiy qoidalar to'plami
    system_instr = (
        "Sen 'Do'ngariq Stroy' do'konining rasmiy yordamchisisan. Isming: Do'ngariq AI. "
        "MUHIM KONTAKTLAR: Islom aka (+998330576161), Zohid (+998933222207). "
        "QOIDALAR: "
        "1. REKLAMA FILTRI: Agar xabar reklama (xizmat taklifi, yuk tashish e'lonlari, mahsulot sotish ro'yxati) bo'lsa, "
        "FAQAT 'Iltimos, guruhda reklama tarqatmang!' deb javob ber. "
        "2. TUSHUNARSIZ XABAR: Agar xabar do'konga tegishli bo'lmasa yoki shunchaki tushunarsiz so'zlar bo'lsa, "
        "HECH QANDAY JAVOB QAYTARMA (bo'sh matn yubor). "
        "3. FORMAT: Faqat oddiy matn (Plain text). HTML teglar (<b>, <i>) yoki Markdown (**bold**) ishlatma. "
        "4. Tushunarsiz salom-aliklarga qisqa alik ol, lekin keraksiz gap sotma."
    )

    try:
        # Suhbatlar tarixini olish
        history = await AIManager.get_chat_history(user.id)
        
        # 1-QADAM: AI xabarni tahlil qiladi
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=history + [types.Content(role="user", parts=[types.Part.from_text(text=user_msg)])],
            config=types.GenerateContentConfig(
                system_instruction=system_instr, 
                tools=tools,
                temperature=0.1 # Aniqlik uchun past harorat
            )
        )

        ai_response_text = response.text.strip() if response.text else ""
        
        # Agar AI xabarni tushunmasa yoki javob berish shart emas deb topsa
        if not ai_response_text and not any(p.function_call for p in response.candidates[0].content.parts):
            return

        call = next((p.function_call for p in response.candidates[0].content.parts if p.function_call), None)
        image_to_send = None

        # 2-QADAM: Agar AI funksiya chaqirsa (ombordan qidirish)
        if call:
            if call.name == "search_warehouse":
                data = await AIManager.get_inventory_data(call.args.get('keywords', []))
                if data:
                    # Ma'lumotlarni mijozga chiroyli matn qilib berish
                    context_msg = f"Mijoz: {user_msg}\nTopilgan ma'lumotlar: {data}\nShu asosida oddiy matnda javob yoz."
                    final_gen = client.models.generate_content(model="gemini-2.0-flash", contents=context_msg)
                    ai_response_text = final_gen.text
                    image_to_send = data[0]['image_path']
                else:
                    # Omborda yo'qligini chiroyli tushuntirish
                    ai_response_text = "Uzr, so'ralgan mahsulot hozirda omborimizda mavjud emas."

            elif call.name == "search_store_knowledge":
                knowledge = await AIManager.get_company_info(call.args.get('topic'))
                context_msg = f"Do'kon ma'lumoti: {knowledge}\nMijoz savoli: {user_msg}\nJavob ber."
                final_gen = client.models.generate_content(model="gemini-2.0-flash", contents=context_msg)
                ai_response_text = final_gen.text

        # 3-QADAM: Javobni tozalash va yuborish
        if ai_response_text:
            # Har qanday holatda ham teglarni tozalash
            clean_text = re.sub(r'<[^<]+?>', '', ai_response_text)
            clean_text = clean_text.replace('**', '').replace('__', '')

            # Ma'lumotlar bazasiga saqlash
            await save_message_to_db(user.id, 'model', clean_text)

            # Telegramga yuborish (Rasm bilan yoki rasmsiz)
            if image_to_send and os.path.exists(image_to_send):
                with open(image_to_send, 'rb') as photo:
                    await update.message.reply_photo(photo=photo, caption=clean_text)
            else:
                await update.message.reply_text(clean_text)

    except Exception as e:
        # Xatoliklarni log qilish (Faqat dev rejimda)
        print(f"AI ERROR: {e}")