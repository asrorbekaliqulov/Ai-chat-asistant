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

    # Adminligini tekshirish
    member = await context.bot.get_chat_member(chat_id, user.id)
    is_admin = member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    
    await save_message_to_db(user.id, 'admin' if is_admin else 'user', user_msg)
    if is_admin: return

    system_instr = (
        "Sen 'Do'ngariq Stroy' do'konining rasmiy yordamchisisan. Isming: Do'ngariq AI. "
        "MUHIM KONTAKTLAR: Islom aka (+998330576161), Zohid (+998933222207). "
        "QOIDALAR: "
        "1. REKLAMA: Reklama bo'lsa 'Iltimos, guruhda reklama tarqatmang!' deb javob ber. "
        "2. BAZA: Mahsulot so'ralsa FAQAT 'search_warehouse' funksiyasini ishlat. "
        "3. FORMAT: Faqat oddiy matn. HTML yoki Markdown ishlatma."
    )

    try:
        # Suhbat tarixini yuklash
        history = await AIManager.get_chat_history(user.id)
        
        # AI bilan muloqot konteksini tayyorlash
        messages = history + [types.Content(role="user", parts=[types.Part.from_text(text=user_msg)])]
        
        image_to_send = None
        final_text = ""

        # Maksimal 2 marta urinish (1-savol, 2-funksiya natijasi tahlili)
        for _ in range(2):
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=messages,
                config=types.GenerateContentConfig(
                    system_instruction=system_instr, 
                    tools=tools,
                    temperature=0.0
                )
            )

            # AI javobini (content) xabarlar ro'yxatiga qo'shamiz
            res_content = response.candidates[0].content
            messages.append(res_content)

            # Funksiya chaqirildimi?
            call = next((p.function_call for p in res_content.parts if p.function_call), None)

            if call:
                db_res = None
                if call.name == "search_warehouse":
                    db_res = await AIManager.get_inventory_data(call.args.get('keywords', []))
                    if db_res: image_to_send = db_res[0].get('image_path')
                
                elif call.name == "search_store_knowledge":
                    db_res = await AIManager.get_company_info(call.args.get('topic'))

                # Funksiya natijasini AIga qaytarish (MUHIM QADAM)
                messages.append(types.Content(
                    role="user",
                    parts=[types.Part.from_function_response(name=call.name, response={"result": db_res})]
                ))
                continue # AI natijani ko'rib, odam tilida javob yozishi uchun loop davom etadi
            else:
                # Agar funksiya chaqirilmasa, demak AI yakuniy matnni qaytardi
                final_text = response.text
                break

        # Xabarni yuborish
        if final_text and final_text.strip():
            # Tozalash
            clean_text = re.sub(r'<(?!/?(b|i|code)\b)[^>]+>', '', final_text)
            clean_text = clean_text.replace('**', '').replace('__', '').strip()

            await save_message_to_db(user.id, 'model', clean_text)

            if image_to_send and os.path.exists(image_to_send):
                with open(image_to_send, 'rb') as photo:
                    await update.message.reply_photo(photo=photo, caption=clean_text)
            else:
                await update.message.reply_text(clean_text)

    except Exception as e:
        print(f"AI ERROR: {str(e)}")