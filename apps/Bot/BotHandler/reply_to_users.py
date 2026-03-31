import os
from asgiref.sync import sync_to_async
from django.db.models import Q
from google import genai
from google.genai import types

from telegram import Update
from telegram.constants import ChatMemberStatus
from telegram.ext import ContextTypes

# Modellarni import qilish
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
        msgs = ChatMessage.objects.filter(user__user_id=t_user_id).order_by('-created_at')[:limit]
        history = []
        for m in reversed(msgs):
            role = "user" if m.role in ['user', 'admin'] else "model"
            history.append(types.Content(role=role, parts=[types.Part.from_text(text=m.content)]))
        return history

    @staticmethod
    @sync_to_async
    def get_inventory_data(keywords):
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
        rules = CompanyData.objects.filter(Q(content__icontains=topic))[:3]
        if not rules.exists():
            rules = CompanyData.objects.all().order_by('-id')[:5]
        return "\n".join([f"- {r.content}" for r in rules])

# AI Toollar
tools = [types.Tool(function_declarations=[
    types.FunctionDeclaration(
        name="search_warehouse",
        description="Ombordan mahsulot qidirish.",
        parameters=types.Schema(
            type="OBJECT", 
            properties={"keywords": types.Schema(type="ARRAY", items=types.Schema(type="STRING"))}, 
            required=["keywords"]
        )
    ),
    types.FunctionDeclaration(
        name="search_store_knowledge",
        description="Do'kon ma'lumotlari, Islom aka va Zohid raqamlari haqida.",
        parameters=types.Schema(type="OBJECT", properties={"topic": types.Schema(type="STRING")}, required=["topic"])
    )
])]

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

    history = await AIManager.get_chat_history(user.id)
    
    # SYSTEM INSTRUCTION: FAQAT ODDY MATN (NO HTML)
    system_instr = (
        "Sen 'Do'ngariq Stroy' do'kon yordamchisisan. "
        "MUHIM: Islom aka (+998330576161), Zohid (+998933222207). "
        "QOIDA: HECH QANDAY HTML TEG (<b>, <i>, <p>) ISHLATMA. "
        "Faqat oddiy matn ko'rinishida javob ber. "
        "Mahsulot bo'lsa narxi va qoldig'ini oddiy qatorlarda yoz."
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=history + [types.Content(role="user", parts=[types.Part.from_text(text=user_msg)])],
            config=types.GenerateContentConfig(system_instruction=system_instr, tools=tools)
        )

        call = next((p.function_call for p in response.candidates[0].content.parts if p.function_call), None)
        
        ai_response_text = ""
        image_to_send = None

        if call:
            if call.name == "search_warehouse":
                data = await AIManager.get_inventory_data(call.args.get('keywords', []))
                if data:
                    prompt = f"Mijoz: {user_msg}\nMa'lumotlar: {data}\nDo'kon nomidan mahsulotlar haqida ODDY MATNda javob ber (Teglar ishlatma)."
                    final_gen = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
                    ai_response_text = final_gen.text
                    image_to_send = data[0]['image_path']
                else:
                    knowledge = await AIManager.get_company_info(user_msg)
                    prompt = f"Omborda yo'q. Bazadagi ma'lumot: {knowledge}. Mijozga oddiy matnda tushuntir."
                    final_gen = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
                    ai_response_text = final_gen.text

            elif call.name == "search_store_knowledge":
                knowledge = await AIManager.get_company_info(call.args.get('topic'))
                prompt = f"Ma'lumot: {knowledge}\nMijoz: {user_msg}\nOddiy matnda (teglarsiz) javob ber. Raqamlarni ochiq ayt."
                final_gen = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
                ai_response_text = final_gen.text
        else:
            ai_response_text = response.text

        if ai_response_text:
            # Har qanday holatda ham teglarni tozalash (xavfsizlik uchun)
            import re
            clean_text = re.sub('<[^<]+?>', '', ai_response_text)
            clean_text = clean_text.replace('**', '').replace('__', '') # Markdownni ham tozalash

            if image_to_send and os.path.exists(image_to_send):
                with open(image_to_send, 'rb') as photo:
                    await update.message.reply_photo(photo=photo, caption=clean_text)
            else:
                await update.message.reply_text(clean_text)
            
            await save_message_to_db(user.id, 'model', clean_text)

    except Exception as e:
        print(f"AI ERROR: {e}")