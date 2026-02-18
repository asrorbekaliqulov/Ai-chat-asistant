import asyncio
from asgiref.sync import sync_to_async
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from apps.Bot.BotHandler.catalog import get_catalog_markup
from .models.TelegramBot import TelegramUser, Channel, CompanyData, ChatMessage, Order, Product, OrderItem
import os
import re
from django.db.models import Sum


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

import os
import numpy as np
from google import genai
from google.genai import types
from asgiref.sync import sync_to_async
from apps.Bot.models.TelegramBot import CompanyData, TelegramUser, Product, Order, OrderItem

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

@sync_to_async
def save_order_to_db(user_id, package_type, products_list, phone, address):
    """Nabor buyurtmasini va uning ichidagi atirlarni bazaga saqlash"""
    user = TelegramUser.objects.get(user_id=user_id)
    
    # Modelda avtomatik narx hisoblash mantiqi bor, shunchaki yaratamiz
    order = Order.objects.create(
        user=user,
        package_type=package_type,
        phone=phone,
        address=address
    )
    
    # Har bir tanlangan atirni OrderItem ga bog'lash
    for item in products_list:
        # Atirni nomi bo'yicha bazadan qidiramiz
        product = Product.objects.filter(name__icontains=item['name']).first()
        if product:
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=item.get('qty', 1)
            )
    return order.id



# 1. KOSINUS O'XSHASHLIGI (Embeddinglar uchun)
def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

# 2. RAG: BAZADAN O'XSHASH ATIRLARNI TOPISH
@sync_to_async
def get_similar_products(user_vector, top_k=5):
    """
    Foydalanuvchi xabariga qarab Product modelidan 
    tavsif bo'yicha eng yaqin atirlarni topib beradi.
    """
    # Eslatma: CompanyData modelida atirlar haqida matnli ma'lumot va 
    # ularning embeddinglari saqlangan deb faraz qilamiz.
    datas = CompanyData.objects.exclude(embedding=None).values("id", "content", "embedding")
    scored = []
    
    for d in datas:
        emb = np.array(d["embedding"])
        sim = cosine_similarity(user_vector, emb)
        scored.append((sim, d["content"]))
    
    # Eng yuqori o'xshashlikdagi 5 ta natijani olish
    top_matches = sorted(scored, key=lambda x: x[0], reverse=True)[:top_k]
    
    # Faqat 0.7 dan yuqori aniqlikdagilarni qaytarish
    result_text = "\n".join([m[1] for m in top_matches if m[0] > 0.7])
    return result_text if result_text else "Katalogdan mos atir topilmadi."



async def finalize_order(user_id: int, package_type: str, products: list, phone: str, address: str):
    """AI tomonidan chaqiriladigan buyurtma yakunlash funksiyasi"""
    order_id = await save_order_to_db(user_id, package_type, products, phone, address)
    
    atirlar_text = "\n".join([f"• {p['name']} ({p.get('qty', 1)} ta)" for p in products])
    
    admin_message = (
        f"🚨 <b>YANGI BUYURTMA #{order_id}</b>\n"
        f"📦 Nabor: {package_type}\n"
        f"🧪 Atirlar:\n{atirlar_text}\n"
        f"📞 Tel: {phone}\n"
        f"📍 Manzil: {address}"
    )
    return {
        "admin_msg": admin_message, 
        "user_msg": f"✅ Buyurtmangiz qabul qilindi! Buyurtma raqami: <b>#{order_id}</b>"
    }

# Gemini Tools Declarations
order_tool = types.FunctionDeclaration(
    name="finalize_order",
    description="Foydalanuvchi nabor sotib olishga qaror qilganda va barcha ma'lumotlar mavjud bo'lganda chaqiriladi.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "package_type": {"type": "STRING", "description": "Nabor turi: '5_set' yoki '10_set'"},
            "products": {
                "type": "ARRAY", 
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "name": {"type": "STRING", "description": "Atir nomi"},
                        "qty": {"type": "INTEGER", "description": "Soni"}
                    }
                },
                "description": "Nabor ichidagi atirlar ro'yxati"
            },
            "phone": {"type": "STRING", "description": "Telefon raqami"},
            "address": {"type": "STRING", "description": "Yetkazib berish manzili"}
        },
        "required": ["package_type", "products", "phone", "address"]
    }
)

catalog_tool = types.FunctionDeclaration(
    name="catalog",
    description="Foydalanuvchi katalogni ko'rishni, atirlar ro'yxatini yoki eng yaxshilarini so'raganda chaqiriladi.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "page": {"type": "INTEGER", "description": "Sahifa raqami, odatda 1"}
        }
    }
)

async def generate_ai_response(user_message: str, user_id: int, chat_history: list = None):
    # 1. RAG qismi (Atirlar haqida ma'lumot)
    user_emb_resp = client.models.embed_content(model="gemini-embedding-001", contents=user_message)
    user_vector = np.array(user_emb_resp.embeddings[0].values)
    context_data = await get_similar_products(user_vector)

    # 2. System Instruction (Aromazona qoidalari)
    system_instr = f"""
    Siz "Aromazona.uz" do'konining professional konsultantisiz. 
    
    NARXLAR (Mega chegirma):
    - 5 dona (10ml) nabor: 250,000 so’m (Asl: 500,000) [cite: 843, 844, 1145]
    - 10 dona (10ml) nabor: 500,000 so’m (Asl: 1,000,000) [cite: 843, 844, 1145]
    
    MAHSULOTLAR (Katalogdan topilganlar):
    {context_data}
    
    QOIDALAR:
    - O'zbek tilida juda qisqa va londa javob bering. 
    - Foydalanuvchi atir tanlamoqchi bo'lsa, uni nabor sotib olishga yo'naltiring.
    - Katalog yoki mahsulotlarni ko'rishni so'rasa, darhol 'catalog' funksiyasini chaqiring.
    - Buyurtma uchun: Nabor turi, Atirlar ro'yxati, Telefon va Manzilni to'liq oling, so'ng 'finalize_order'ni chaqiring.
    """

    # 3. Chat tarixini tayyorlash
    contents = []
    if chat_history:
        for msg in chat_history[-15:]:
            role = "user" if msg['role'] == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part.from_text(text=msg['content'])]))
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_message)]))

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents,
            config={
                'system_instruction': system_instr,
                'tools': [types.Tool(function_declarations=[order_tool, catalog_tool])],
                'temperature': 0.1,
            }
        )

        part = response.candidates[0].content.parts[0]

        # Funksiya chaqiruvini tekshirish
        if part.function_call:
            fn_name = part.function_call.name
            fn_args = part.function_call.args
            
            if fn_name == "catalog":
                # Katalog mantiqi handlers.py dagi get_catalog_markup ga ulanishi kerak
                from .handlers import get_catalog_markup
                text, markup = await get_catalog_markup(page=fn_args.get("page", 1))
                return {"type": "catalog", "text": text, "markup": markup}
            
            elif fn_name == "finalize_order":
                res = await finalize_order(user_id, **fn_args)
                return {"type": "order_completed", **res}
        
        return {"type": "text", "text": part.text or "Tushunarsiz so'rov."}

    except Exception as e:
        print(f"AI Error: {e}")
        return {"type": "text", "text": "Hozircha javob bera olmayman, tizimni yangilayapman."}

@sync_to_async
def get_chat_history_from_db(user_id, limit=15):
    # Oxirgi limit miqdoridagi xabarlarni olish
    messages = ChatMessage.objects.filter(user__user_id=user_id).order_by('-created_at')[:limit]
    # Gemini formatiga moslash uchun ro'yxatni teskari qilish (eskidan yangiga)
    return [{'role': m.role, 'content': m.content} for m in reversed(messages)]

@sync_to_async
def save_message_to_db(user_id, role, content):
    user = TelegramUser.objects.get(user_id=user_id)
    ChatMessage.objects.create(user=user, role=role, content=content)

@sync_to_async
def save_order_to_db(user_id, product_name, phone, address):
    user = TelegramUser.objects.get(user_id=user_id)
    order = Order.objects.create(
        user=user,
        product_name=product_name,
        phone=phone,
        address=address
    )
    return order.id


