from asgiref.sync import sync_to_async
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from apps.Bot.BotHandler.catalog import get_catalog_markup
from .models.TelegramBot import TelegramUser, Channel, CompanyData, ChatMessage, Order, Product, OrderItem, Cart, SelectedItem
import os
import numpy as np
from google import genai
from google.genai import types
from asgiref.sync import sync_to_async

import re
from django.db.models import Sum, Count


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
        },
        "required": ["page"]
    }
)

async def generate_ai_response(user_message: str, user_id: int, chat_history: list = None):
    # 1. RAG qismi (Atirlar haqida ma'lumot)
    user_emb_resp = client.models.embed_content(model="gemini-embedding-001", contents=user_message)
    user_vector = np.array(user_emb_resp.embeddings[0].values)
    context_data = await get_similar_products(user_vector)

    # 2. System Instruction (Aromazona qoidalari)
    system_instr = f"""
Siz "DO‘NGARIQ STROY" do'konining professional ombor maslahatchisi va savdo yordamchisiz. Sizning vazifangiz mijozlarga qurilish materiallarini tanlashda yordam berish, ombordagi qoldiqlar haqida ma'lumot berish va buyurtma berish jarayonini tushuntirish.

BAZADAN TOPILGAN MALUMOTLAR (Context):
{context_data}

NARX VA O'LCHOV BIRLIKLARI:
- Mahsulotlar turi va zavodiga qarab narxlari farq qiladi.
- O'lchov birliklari: kg, dona, m2, m3, metr, qop.
- Har bir mahsulotning "Brend" (Zavod) va "O'lcham" xususiyatlariga e'tibor bering.


QOIDALAR:
- Til: O'zbek tilida, samimiy, lekin jiddiy (ishbilarmonlik uslubida) javob bering.
- Aniqlik: Foydalanuvchi mahsulot so'rasa, uning zavodi (brand) va o'lchamini aniq ko'rsating.
- Qoldiqlar: Agar mahsulot omborda kam qolgan bo'lsa (stock < 10), bu haqda mijozni ogohlantiring.
- Maslahat: Foydalanuvchi tanlovda qiynalsa, mahsulotning tavsifidan (description) kelib chiqib tavsiya bering.
- Formatlash: Bot <b>HTML</b> formatini qo'llab-quvvatlaydi. Narxlarni <b>150,000 so'm</b> ko'rinishida qalin qilib yozing.
- Yo'naltirish: Foydalanuvchi mahsulotlarni ko'rmoqchi bo'lsa, har doim "📚 Katalog" bo'limiga o'tishni maslahat bering.
- Katalog Funksiyasi: Agar foydalanuvchi mahsulotlar ro'yxatini yoki katalogni ko'rishni xohlasa, "catalog" funksiyasini chaqiring.
- Yakun: Buyurtma oxirida telefon va manzil yuborish tugmalaridan foydalanishni eslatish shart.

DIQQAT: Siz faqat bazadagi (context_data) malumotlar asosida javob berolasiz mavzudan chetlashmang.
"""
#     BUYURTMA BERISH TARTIBI:
# 1. 📚 Katalog orqali mahsulotlarni va ularning variantlarini (zavodi/o'lchami) ko'ring.
# 2. Kerakli mahsulotni tanlab, "🛒 Savatga qo'shish" tugmasini bosing.
# 3. Miqdorni (masalan: 50 qop yoki 100 metr) kiriting.
# 4. "🛒 Savat" bo'limiga o'tib, buyurtmani tekshiring va "Rasmiylashtirish"ni bosing.
# 5. Bot orqali telefon raqamingizni va yetkazib berish manzilini (lokatsiya) yuboring.


    # 3. Chat tarixini tayyorlash
    contents = []
    if chat_history:
        for msg in chat_history[-15:]:
            role = "user" if msg['role'] == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part.from_text(text=msg['content'])]))
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_message)]))

    tool_config = types.ToolConfig(
        function_calling_config=types.FunctionCallingConfig(
            mode="AUTO",  # Model qachon funksiya chaqirishni o'zi hal qiladi
        )
    )
    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=contents,
            config={
                'system_instruction': system_instr,
                'tools': [types.Tool(function_declarations=[catalog_tool, order_tool])],
                'tool_config': tool_config,
                'temperature': 0.1,
            }
        )

        parts = response.candidates[0].content.parts
        
        for part in parts:
            if part.function_call:
                fn_name = part.function_call.name
                fn_args = part.function_call.args
                
                if fn_name == "catalog":
                    print(f"AI requested catalog page: {fn_args.get('page', 1)}")  # Debug log
                    return {"type": "catalog", "page": fn_args.get("page", 1)}
                
                elif fn_name == "finalize_order":
                    res = await finalize_order(user_id, **fn_args)
                    return {"type": "order_completed", **res}
            
            if part.text:
                print(f"AI responded with text: {part.text}")  # Debug log
                # Agar model baribir matn qaytarsa (lekin ichida catalog so'zi bo'lsa)
                # Bu qo'shimcha "straxovka" (ixtiyoriy)
                if "catalog(" in part.text:
                     return {"type": "catalog", "page": 1}
                return {"type": "text", "text": part.text}

        return {"type": "text", "text": "Tushunarsiz so'rov."}

    except Exception as e:
        print(f"AI Error: {e}")
        return {"type": "text", "text": "Hozircha javob bera olmayman, tizimni yangilayapman."}


async def generate_admin_ai_response(user_message: str, user_id: int, chat_history: list = None):
    # 1. Admin uchun maxsus kontekst (Masalan: Bugungi savdolar yoki ombor holati)
    # Bu yerda ixtiyoriy ravishda SQL dan ma'lumot olish funksiyasini chaqirishingiz mumkin
    # Masalan: admin_stats = await get_daily_statistics()
    
    admin_system_instr = f"""
Siz "DO‘NGARIQ STROY" boshqaruv tizimining intellektual tahlilchisisiz. 
Sizning vazifangiz adminga do'kon holati, mijozlar bilan muloqot va tizim samaradorligi bo'yicha ma'lumot berish.

Sizning vakolatlaringiz:
- Tizim xatolarini tahlil qilish.
- Mahsulotlar qoldig'i haqida hisobot berish.
- Admin bergan buyruqlarni tushunish va ijro etish usullarini ko'rsatish.

QOIDALAR:
- Til: O'zbek tili, ochiq va professional tahliliy uslub.
- Ma'lumot: Faqat admin ko'rishi mumkin bo'lgan maxfiy ma'lumotlar bilan ishlaysiz.
- Format: bu xabar telegram uchun shuning uchun parse_mode=<b>HTML</b> formatidan foydalaning. Muhim raqamlarni <code>kod</code> yoki <b>qalin</b> ko'rinishda yozing.
- Cheklov: Mijozlarga beriladigan samimiy ("Xush kelibsiz") ohangidan foydalanmang, qisqa va aniq javob bering.
"""

    # 2. Chat tarixini tayyorlash
    contents = []
    if chat_history:
        for msg in chat_history[-10:]: # Admin uchun qisqaroq tarix kifoya
            role = "user" if msg['role'] == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part.from_text(text=msg['content'])]))
    
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_message)]))

    try:
        # Admin uchun Gemini-1.5-Pro yoki Flash modelidan foydalanamiz
        response = client.models.generate_content(
            model="gemini-2.0-flash", # Yoki murakkabroq tahlil uchun gemini-1.5-pro
            contents=contents,
            config={
                'system_instruction': admin_system_instr,
                'temperature': 0.2, # Admin uchun aniqroq javoblar kerak
            }
        )

        # Admin uchun hozircha funksiya chaqiruvlari (tools) shart emas deb hisobladim
        # Agar kerak bo'lsa, bu yerga ham tool qo'shish mumkin
        ai_text = response.candidates[0].content.parts[0].text
        
        if ai_text:
            print(f"Admin AI Response: {ai_text[:50]}...") # Debug log
            return ai_text
        
        return "Admin, so'rovingiz bo'yicha ma'lumot topilmadi."

    except Exception as e:
        print(f"Admin AI Error: {e}")
        return "Tizim tahlilida xatolik yuz berdi. Iltimos, server loglarini tekshiring."

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


@sync_to_async
def get_cart_markup(user_id):
    user = TelegramUser.objects.get(user_id=user_id)
    cart, _ = Cart.objects.get_or_create(user=user)
    
    # SelectedItem'larni mahsulot bo'yicha guruhlaymiz va sonini sanaymiz
    items_data = (
        SelectedItem.objects.filter(cart=cart)
        .values('product__id', 'product__name')
        .annotate(qty=Count('id'))
        .order_by('product__name')
    )
    
    # Umumiy tanlangan atirlar soni (nabor uchun kerak)
    total_count = sum(item['qty'] for item in items_data)
    
    keyboard = []
    current_row = []

    # 1. Atirlar tugmalarini generatsiya qilish
    for item in items_data:
        p_id = item['product__id']
        name = item['product__name'][:8] # Tugma sig'ishi uchun qisqartma
        qty = item['qty']
        
        # Agar soni 1 tadan ko'p bo'lsa, qavs ichida ko'rsatamiz
        display_name = f"❌ {name}" if qty == 1 else f"❌ {name} ({qty})"
        
        btn = InlineKeyboardButton(
            display_name, 
            callback_data=f"remove_item_{p_id}", # Endi butun guruh uchun callback
            api_kwargs={"style": "danger"}
        )
        current_row.append(btn)
        
        # Eniga 5 tadan tugma bo'lganda yangi qatorga o'tish
        if len(current_row) == 4:
            keyboard.append(current_row)
            current_row = []
            
    # Qolib ketgan tugmalarni oxirgi qatorga qo'shish
    if current_row:
        keyboard.append(current_row)

    # 2. Pastki boshqaruv tugmalari
    control_buttons = []
    if total_count < 5:
        control_buttons.append(InlineKeyboardButton("➕ Atir qo'shish", callback_data="open_catalog", api_kwargs={"style": "success"}))
        text = f"🛒 <b>Savat</b>\n\nSizda jami {total_count} ta atir bor. Nabor uchun yana {5-total_count} ta qo'shing."
    else:
        control_buttons.append(InlineKeyboardButton("🎁 5 talik", callback_data="set_package_5_set"))
        control_buttons.append(InlineKeyboardButton("🎁 10 talik", callback_data="set_package_10_set"))
        text = f"🛒 <b>Savat</b>\n\nSizda jami {total_count} ta atir bor. Nabor turini tanlang:"
    
    if control_buttons:
        keyboard.append(control_buttons)

    # 3. Chiqish tugmasi
    keyboard.append([InlineKeyboardButton("🚪 Chiqish", callback_data="close_cart")])

    return text, InlineKeyboardMarkup(keyboard)

from django.db.models import Count, Q

@sync_to_async
def get_nabor_selection_markup(user_id, package_type):
    user = TelegramUser.objects.get(user_id=user_id)
    cart = Cart.objects.get(user=user)
    
    # Savatdagi barcha atirlarni guruhlab olamiz
    # 'total' - savatda nechta borligi, 'selected' - nechtasi tanlangani
    items_data = (
        SelectedItem.objects.filter(cart=cart)
        .values('product__id', 'product__name')
        .annotate(
            total=Count('id'),
            selected=Count('id', filter=Q(is_selected=True))
        )
        .order_by('product__name')
    )
    
    # Jami tanlanganlar soni (global limit uchun)
    global_selected = SelectedItem.objects.filter(cart=cart, is_selected=True).count()
    target = 5 if package_type == '5_set' else 10
    is_ready = (global_selected == target)

    keyboard = []
    current_row = []

    for item in items_data:
        p_id = item['product__id']
        name = item['product__name'][:10] # Tugma sig'ishi uchun
        total = item['total']
        selected = item['selected']
        
        # Tugma matni mantiqi
        if selected == 0:
            # Hali birortasi tanlanmagan
            display_name = f"{name} ({total})" if total > 1 else name
        elif 0 < selected < total:
            # Qisman tanlangan (masalan: 1/3)
            display_name = f"({selected}/{total}) {name}"
        else:
            # Hammasi tanlangan
            display_name = f"✅ {name}"
            
        btn = InlineKeyboardButton(
            display_name, 
            callback_data=f"toggle_select_{p_id}",
            api_kwargs={"style": "success" if selected > 0 else ""}
        )
        current_row.append(btn)
        
        if len(current_row) == 5:
            keyboard.append(current_row)
            current_row = []
            
    if current_row: keyboard.append(current_row)

    # Rasmiylashtirish tugmasi
    btn_style = "primary" if is_ready else ""
    btn_cb = "finalize_checkout" if is_ready else "not_ready"
    keyboard.append([InlineKeyboardButton(
        f"🚀 Tasdiqlash ({global_selected}/{target})", 
        callback_data=btn_cb, 
        api_kwargs={"style": btn_style}
    )])

    return f"🎁 <b>{target} talik nabor</b> uchun atirlarni tanlang:", InlineKeyboardMarkup(keyboard)

@sync_to_async
def get_product_count_in_cart(user, product):
    # Agar CartItem modelini ishlatsangiz:
    # item = CartItem.objects.filter(cart__user=user, product=product).first()
    # return item.quantity if item else 0
    
    # Agar oddiy ManyToMany bo'lsa, faqat bor/yo'qligini tekshiramiz:
    return 1 if user.cart.items.filter(id=product.id).exists() else 0
