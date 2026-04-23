import os
import io
import json
import tempfile
from decimal import Decimal
from django.db import transaction
from django.db.models import Q
from asgiref.sync import sync_to_async

from apps.Bot.keybaords import ADMIN_KYB
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    ReplyKeyboardMarkup
)
from telegram.ext import (
    ContextTypes, 
    ConversationHandler, 
    MessageHandler, 
    CallbackQueryHandler,
    filters
)

# Modellarni import qilish
from apps.warehouse.models.base import ProductVariant, StockTransaction

# AI Importlari
from google import genai
from google.genai import types
from openai import AsyncOpenAI

# 1. AI Sozlamalari
AI_MODE = os.getenv("AI_MODE", "gemini").lower()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if AI_MODE == "chatgpt":
    ai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
else:
    ai_client = genai.Client(api_key=GEMINI_API_KEY)

tool_description = "Ombordagi mahsulotlarni nomi, brendi yoki o'lchami bo'yicha qidiradi."

# --- Gemini Tool ---
search_tool_gemini = types.FunctionDeclaration(
    name="search_warehouse",
    description=tool_description,
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "search_query": types.Schema(
                type="STRING", 
                description="Qidirilayotgan mahsulot kalit so'zlari (masalan: 'sement abusahiy')"
            ),
        },
        required=["search_query"]
    )
)
gemini_tools = [types.Tool(function_declarations=[search_tool_gemini])]

# --- ChatGPT Tool ---
openai_tools = [{
    "type": "function",
    "function": {
        "name": "search_warehouse",
        "description": tool_description,
        "parameters": {
            "type": "object",
            "properties": {
                "search_query": {
                    "type": "string", 
                    "description": "Qidirilayotgan mahsulot kalit so'zlari (masalan: 'sement abusahiy')"
                }
            },
            "required": ["search_query"]
        }
    }
}]

# Holatlar
SEARCHING, WAITING_QTY = range(2)

# 2. Mantiqiy boshqaruvchi
class SearchManager:
    @staticmethod
    @sync_to_async
    def db_search(query_text: str):
        """AI buyrug'i bo'yicha bazadan qidirish"""
        words = query_text.split()
        q_filter = Q()
        for word in words:
            if len(word) > 1:
                q_filter &= (Q(product__name__icontains=word) | 
                             Q(brand__icontains=word) | 
                             Q(size__icontains=word))
        
        variants = ProductVariant.objects.filter(q_filter).select_related('product')[:10]
        
        results = []
        for v in variants:
            img = v.image.path if v.image and os.path.exists(v.image.path) else \
                  (v.product.image.path if v.product.image and os.path.exists(v.product.image.path) else None)
            
            results.append({
                "id": v.id,
                "name": f"{v.product.name} | {v.brand} | {v.size}".strip(" | "),
                "price": float(v.selling_price),
                "stock": float(v.stock),
                "unit": v.product.get_unit_display(),
                "image": img
            })
        return results

    @staticmethod
    @sync_to_async
    def execute_sale(v_id, qty):
        """Sotuv amali"""
        try:
            with transaction.atomic():
                v = ProductVariant.objects.select_for_update().get(id=v_id)
                q = Decimal(str(qty))
                if v.stock < q: return False, f"❌ Ombor yetarli emas! (Mavjud: {v.stock})"
                StockTransaction.objects.create(variant=v, quantity=q, transaction_type='OUT', note="Bot orqali sotuv")
                v.refresh_from_db()
                return True, f"✅ Sotildi!\n📦 Yangi qoldiq: {v.stock} {v.product.unit}"
        except Exception as e: return False, f"⚠️ Xato: {e}"

# 3. Handler funksiyalari
async def start_search_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔍 <b>Aqlli Qidiruv Rejimi</b>\nMahsulotni yozing yoki ovozli xabar qoldiring:",
        parse_mode='HTML', reply_markup=ReplyKeyboardMarkup([['❌ Chiqish']], resize_keyboard=True)
    )
    return SEARCHING

async def handle_search_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_msg = update.message.text if update.message.text else None
    user_audio = None
    voice_file_path = None

    if user_msg == "❌ Chiqish": 
        return await cancel_search(update, context)

    # Ovozli xabarni tahlil qilish
    if update.message.voice:
        v_file = await update.message.voice.get_file()
        
        if AI_MODE == "chatgpt":
            # ChatGPT uchun ovozni faylga saqlab, Whisper orqali matnga aylantiramiz
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tf:
                voice_file_path = tf.name
            await v_file.download_to_drive(custom_path=voice_file_path)
            
            try:
                with open(voice_file_path, "rb") as audio_file:
                    transcript = await ai_client.audio.transcriptions.create(
                        model="whisper-1", 
                        file=audio_file
                    )
                user_msg = transcript.text
            finally:
                if os.path.exists(voice_file_path):
                    os.remove(voice_file_path)
        else:
            # Gemini uchun to'g'ridan-to'g'ri baytlarni olamiz
            v_data = io.BytesIO()
            await v_file.download_to_memory(v_data)
            user_audio = v_data.getvalue()

    instruction = "Ushbu so'rovni tahlil qil va mahsulotni topish uchun 'search_warehouse' funksiyasini chaqir."
    extracted_queries = []

    try:
        if AI_MODE == "chatgpt":
            # --- ChatGPT bilan ishlash ---
            messages = [{"role": "system", "content": instruction}]
            if user_msg:
                messages.append({"role": "user", "content": user_msg})
            else:
                await update.message.reply_text("Iltimos, xabar yuboring.")
                return SEARCHING

            response = await ai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                tools=openai_tools,
                temperature=0.0
            )

            msg = response.choices[0].message
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    if tc.function.name == "search_warehouse":
                        args = json.loads(tc.function.arguments)
                        extracted_queries.append(args.get("search_query"))

        else:
            # --- Gemini bilan ishlash ---
            parts = []
            if user_msg:
                parts.append(types.Part.from_text(text=f"Foydalanuvchi so'rovi: {user_msg}. {instruction}"))
            elif user_audio:
                parts.append(types.Part.from_bytes(data=user_audio, mime_type="audio/ogg"))
                parts.append(types.Part.from_text(text=instruction))

            def call_gemini():
                return ai_client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=[types.Content(role="user", parts=parts)],
                    config=types.GenerateContentConfig(tools=gemini_tools, temperature=0.0)
                )
            
            response = await sync_to_async(call_gemini)()
            
            for part in response.candidates[0].content.parts:
                if part.function_call and part.function_call.name == "search_warehouse":
                    args = part.function_call.args
                    extracted_queries.append(args.get('search_query'))

        # Tahlil natijasiga ko'ra bazadan qidirish
        if not extracted_queries:
            await update.message.reply_text("🤔 Mahsulot nomini aniqlay olmadim. Iltimos, aniqroq yozing.")
            return SEARCHING

        for search_query in extracted_queries:
            products = await SearchManager.db_search(search_query)

            if not products:
                await update.message.reply_text(f"😔 '{search_query}' bo'yicha mahsulot topilmadi.")
                continue

            for p in products:
                cap = f"📦 <b>{p['name']}</b>\n💰 Narxi: {p['price']:,} so'm\n📉 Qoldiq: {p['stock']} {p['unit']}"
                kb = InlineKeyboardMarkup([[InlineKeyboardButton("🛒 Sotish", callback_data=f"q:{p['id']}:{p['name']}") ]])
                
                if p['image'] and os.path.exists(p['image']):
                    with open(p['image'], 'rb') as f:
                        await update.message.reply_photo(photo=f, caption=cap, parse_mode='HTML', reply_markup=kb)
                else:
                    await update.message.reply_text(cap, parse_mode='HTML', reply_markup=kb)

    except Exception as e:
        print(f"AI Error: {e}")
        await update.message.reply_text("⚠️ Xatolik yuz berdi. Qaytadan urinib ko'ring.")

    return SEARCHING

async def ask_qty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, v_id, v_name = query.data.split(":")
    context.user_data['sid'] = v_id
    await query.message.reply_text(f"🔢 <b>{v_name}</b>\nMiqdorni kiriting:", parse_mode='HTML')
    return WAITING_QTY

async def do_sale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    qty_text = update.message.text
    v_id = context.user_data.get('sid')
    try:
        ok, msg = await SearchManager.execute_sale(v_id, float(qty_text.replace(',', '.')))
        await update.message.reply_text(msg)
    except:
        await update.message.reply_text("❌ Miqdorni to'g'ri raqamda kiriting!")
    return SEARCHING

async def cancel_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Qidiruv yopildi.", reply_markup=ADMIN_KYB)
    return ConversationHandler.END

# Handler konfiguratsiyasi
search_handler = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex('^🔍 Qidirish$'), start_search_mode)],
    states={
        SEARCHING: [
            MessageHandler((filters.TEXT | filters.VOICE) & ~filters.COMMAND, handle_search_input),
            CallbackQueryHandler(ask_qty, pattern="^q:"),
        ],
        WAITING_QTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, do_sale)],
    },
    fallbacks=[MessageHandler(filters.Regex('^❌ Chiqish$'), cancel_search)],
    allow_reentry=True
)