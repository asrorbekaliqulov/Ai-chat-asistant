import os
import re
import json
from asgiref.sync import sync_to_async
from django.db.models import Q

# Gemini importlari
from google import genai
from google.genai import types

# OpenAI importi (ChatGPT uchun)
from openai import AsyncOpenAI

from telegram import Update
from telegram.constants import ChatMemberStatus
from telegram.ext import ContextTypes

# Modellarni import qilish (Proyektingizdagi yo'llarga moslang)
from apps.warehouse.models.base import Product, ProductVariant # Yo'lni to'g'rilab oling
from apps.Bot.models.TelegramBot import CompanyData, ChatMessage
from apps.Bot.utils import save_message_to_db
from apps.Bot.decorators import typing_action

# .env faylidan API kalitlarni olish
AI_MODE = os.getenv("AI_MODE", "gemini").lower()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Aktiv AI modelni initsializatsiya qilish
if AI_MODE == "chatgpt":
    ai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
else:
    ai_client = genai.Client(api_key=GEMINI_API_KEY)

class AIManager:
    @staticmethod
    @sync_to_async
    def get_chat_history_raw(t_user_id, limit=6):
        """Suhbat tarixini universal formatda olish"""
        msgs = ChatMessage.objects.filter(user__user_id=t_user_id).order_by('-created_at')[:limit]
        history = []
        for m in reversed(msgs):
            role = "user" if m.role in ['user', 'admin'] else "assistant"
            history.append({"role": role, "content": m.content})
        return history

    @staticmethod
    @sync_to_async
    def get_all_product_names():
        """Barcha aktiv mahsulotlarning nomlarini ro'yxat shaklida olish (AI o'zakni to'g'ri topishi uchun)"""
        return list(Product.objects.filter(is_active=True).values_list('name', flat=True).distinct())

    @staticmethod
    @sync_to_async
    def get_inventory_data(keywords):
        """Aktiv va noaktiv mahsulotlarni qidirish"""
        if not keywords: return None
        query_filter = Q()
        for word in keywords:
            query_filter |= Q(product__name__icontains=word) | Q(brand__icontains=word)
        
        # Diqqat: filterdan is_active=True olib tashlandi, AI o'zi tekshirishi uchun
        variants = ProductVariant.objects.filter(query_filter).select_related('product').distinct()[:5]
        if not variants.exists(): return None
        
        data_list = []
        for v in variants:
            img_path = None
            if v.image and os.path.exists(v.image.path):
                img_path = v.image.path
            elif v.product.image and os.path.exists(v.product.image.path):
                img_path = v.product.image.path

            data_list.append({
                "product": f"{v.product.name} - {v.brand}".strip(),
                "price": f"{v.selling_price:,.0f} so'm",
                "is_available": v.is_active, # True/False holati
                "image_path": img_path,
            })
        return data_list


    @staticmethod
    @sync_to_async
    def get_company_info(topic):
        rules = CompanyData.objects.filter(Q(content__icontains=topic))[:3]
        if not rules.exists():
            rules = CompanyData.objects.all().order_by('-id')[:5]
        return "\n".join([f"- {r.content}" for r in rules])

# === AI TOOLLAR SXEMALARI ===
tool_description = "Ombordan mahsulot qidirish. DIQQAT: Faqat mahsulotning toza o'zagini kiriting."

gemini_tools = [types.Tool(function_declarations=[
    types.FunctionDeclaration(
        name="search_warehouse",
        description=tool_description,
        parameters=types.Schema(
            type="OBJECT", 
            properties={"keywords": types.Schema(type="ARRAY", items=types.Schema(type="STRING"))}, 
            required=["keywords"]
        )
    )
])]

openai_tools = [{
    "type": "function",
    "function": {
        "name": "search_warehouse",
        "description": tool_description,
        "parameters": {
            "type": "object",
            "properties": {"keywords": {"type": "array", "items": {"type": "string"}}},
            "required": ["keywords"]
        }
    }
}]

@typing_action
async def ai_group_assistant(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    if not update.message or not update.message.text: return
    
    user = update.effective_user
    user_msg = update.message.text
    chat_id = update.effective_chat.id

    member = await context.bot.get_chat_member(chat_id, user.id)
    is_admin = member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    
    await save_message_to_db(user.id, 'admin' if is_admin else 'user', user_msg)
    if is_admin: return

    try:
        # AI bazada nimalar borligini aniq bilishi uchun mahsulotlar ro'yxatini yuklaymiz
        product_names = await AIManager.get_all_product_names()
        product_names_str = ", ".join(product_names)

        # QAT'IY SYSTEM PROMPT
        system_instr = (
            "Sen FAQAT mahsulot qidiruvchi botsan. Boshqa mavzularda (do'kon manzili, raqami, salom-alik) FAQAT 'IGNORE' deb javob ber.\n"
            f"BAZADAGI MAHSULOTLAR: [{product_names_str}].\n"
            "VAZIFANG:\n"
            "1. Mijoz mahsulot so'rasa `search_warehouse` orqali bazani tekshir.\n"
            "2. Agar `is_available: True` bo'lsa: Faqat nomi va narxini yozib, bor deb ayt.\n"
                "Misol: 'Sement Xuaxin bor. Narxi: 50,000 so'm'.\n"
            "3. Agar `is_available: False` bo'lsa: 'Ushbu mahsulot hozirda tugab qolgan, tez kunda keladi' deb javob ber.\n"
            "4. Agar mahsulot bazadan umuman topilmasa yoki boshqa har qanday gap yozilsa, FAQAT 'IGNORE' so'zini qaytar."
        )

        raw_history = await AIManager.get_chat_history_raw(user.id)
        image_to_send = None
        final_text = ""

        if AI_MODE == "chatgpt":
            # --- CHATGPT ---
            messages = [{"role": "system", "content": system_instr}]
            messages.extend(raw_history)
            messages.append({"role": "user", "content": user_msg})

            for _ in range(2):
                response = await ai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    tools=openai_tools,
                    temperature=0.0 # Nolgacha tushirdik, xushmuomalalik qilib yubormasligi uchun
                )
                
                response_msg = response.choices[0].message
                messages.append(response_msg)

                if response_msg.tool_calls:
                    tool_call = response_msg.tool_calls[0]
                    args = json.loads(tool_call.function.arguments)

                    db_res = None
                    if tool_call.function.name == "search_warehouse":
                        db_res = await AIManager.get_inventory_data(args.get('keywords', []))
                        if db_res: image_to_send = db_res[0].get('image_path')

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": tool_call.function.name,
                        "content": json.dumps({"result": db_res}, ensure_ascii=False) if db_res else json.dumps({"result": "Topilmadi"})
                    })
                    continue
                else:
                    final_text = response_msg.content
                    break

        else:
            # --- GEMINI ---
            messages = []
            for msg in raw_history:
                r = "user" if msg["role"] == "user" else "model"
                messages.append(types.Content(role=r, parts=[types.Part.from_text(text=msg["content"])]))
            messages.append(types.Content(role="user", parts=[types.Part.from_text(text=user_msg)]))

            for _ in range(2):
                def call_gemini():
                    return ai_client.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=messages,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instr, 
                            tools=gemini_tools,
                            temperature=0.0
                        )
                    )
                
                response = await sync_to_async(call_gemini)()
                res_content = response.candidates[0].content
                messages.append(res_content)

                call = next((p.function_call for p in res_content.parts if p.function_call), None)

                if call:
                    db_res = None
                    if call.name == "search_warehouse":
                        db_res = await AIManager.get_inventory_data(call.args.get('keywords', []))
                        if db_res: image_to_send = db_res[0].get('image_path')

                    messages.append(types.Content(
                        role="user",
                        parts=[types.Part.from_function_response(name=call.name, response={"result": db_res})]
                    ))
                    continue
                else:
                    final_text = response.text
                    break

        # Natijani tozalash va yuborish
        if final_text and final_text.strip():
            # Agar AI javobi ichida IGNORE bo'lsa, mutlaqo jim turamiz
            if "IGNORE" in final_text.upper():
                return

            clean_text = final_text.replace('**', '').replace('__', '').strip()
            
            # Faqat is_available bo'lgandagina rasm yuborish mantiqi
            # (db_res ma'lumotini saqlab qolgan bo'lsangiz)
            if image_to_send and os.path.exists(image_to_send):
                # Faqat mahsulot topilgan va u True bo'lgan holatda rasm chiqadi
                await update.message.reply_photo(photo=open(image_to_send, 'rb'), caption=clean_text)
            else:
                await update.message.reply_text(clean_text)

    except Exception as e:
        print(f"AI ERROR: {str(e)}")