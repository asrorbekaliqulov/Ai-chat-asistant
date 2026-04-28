import os
import io
import json
from django.db.models import Q, Count
from asgiref.sync import sync_to_async

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, CallbackQueryHandler, filters
from telegram.constants import ParseMode

# Modellarni import qilish
from apps.warehouse.models.base import Product, ProductVariant

# AI Clientlarni tanlash (Sizning kodingizdagi sozlamalar bo'yicha)
from google import genai
from google.genai import types
from openai import AsyncOpenAI

AI_MODE = os.getenv("AI_MODE", "gemini").lower()
if AI_MODE == "chatgpt":
    ai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
else:
    ai_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# --- UTILS ---

@sync_to_async
def get_paginated_products(page=0):
    """Boshqarish tugmasi bosilganda mahsulotlar ro'yxati (Rangli pagination)"""
    per_page = 10
    offset = page * per_page
    products = list(Product.objects.annotate(v_total=Count('variants')).order_by('name')[offset:offset+per_page])
    total = Product.objects.count()

    keyboard = []
    # 2 qatorda 5 tadan
    for i in range(0, len(products), 2):
        row = []
        for p in products[i:i+2]:
            row.append(InlineKeyboardButton(
                f"({p.v_total}) {p.name}", 
                callback_data=f"adm_p:{p.id}",
                api_kwargs={"style": "primary"} # Ko'k rang
            ))
        keyboard.append(row)

    nav = []
    if page > 0: nav.append(InlineKeyboardButton("⬅️", callback_data=f"adm_page:{page-1}"))
    nav.append(InlineKeyboardButton("❌ Yopish", callback_data="adm_close", api_kwargs={"style": "danger"}))
    if offset + per_page < total: nav.append(InlineKeyboardButton("➡️", callback_data=f"adm_page:{page+1}"))
    keyboard.append(nav)
    
    return InlineKeyboardMarkup(keyboard)

async def ai_search_logic(update: Update):
    """Ovozli yoki matnli xabarni AI orqali tahlil qilib mahsulot nomini olish"""
    user_msg = update.message.text
    user_audio = None

    if update.message.voice:
        v_file = await update.message.voice.get_file()
        if AI_MODE == "chatgpt":
            # Whisper transkripsiya
            v_data = io.BytesIO()
            await v_file.download_to_memory(v_data)
            v_data.name = "voice.ogg"
            transcript = await ai_client.audio.transcriptions.create(model="whisper-1", file=v_data)
            user_msg = transcript.text
        else:
            # Gemini Audio tahlil
            v_data = io.BytesIO()
            await v_file.download_to_memory(v_data)
            user_audio = v_data.getvalue()

    # AI orqali kalit so'zni ajratish
    prompt = "Ushbu so'rovdan faqat mahsulot nomini ajratib ber: "
    if AI_MODE == "chatgpt":
        res = await ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt + user_msg}]
        )
        return res.choices[0].message.content.strip()
    else:
        parts = [types.Part.from_text(text=prompt + (user_msg or ""))]
        if user_audio:
            parts.append(types.Part.from_bytes(data=user_audio, mime_type="audio/ogg"))
        
        response = await sync_to_async(ai_client.models.generate_content)(
            model="gemini-2.0-flash",
            contents=[types.Content(role="user", parts=parts)]
        )
        return response.text.strip()

# --- HANDLERS ---
async def global_admin_search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin xabar yozsa mahsulotni variantlari bilan topadi"""
    if not update.message: return

    if update.message.text == "⚙️ Boshqarish":
        kb = await get_paginated_products(0)
        await update.message.reply_text("📦 Mahsulotlar ro'yxati:", reply_markup=kb)
        return

    loading = await update.message.reply_text("🔍 Qidirilmoqda...")
    try:
        # AI orqali faqat asosiy nomni olamiz
        query_text = await ai_search_logic(update)
        
        # 'N/A', 'brendi' kabi so'zlarni AI qaytarsa, ularni tozalash (ehtiyot shart)
        clean_query = query_text.replace("Brendi: N/A", "").replace("N/A", "").strip()

        def get_variants():
            # Faqat mahsulot nomi bo'yicha qidiruv (brendni majburlamaymiz)
            return list(ProductVariant.objects.filter(
                Q(product__name__icontains=clean_query) | 
                Q(brand__icontains=clean_query)
            ).select_related('product').order_by('product__name'))

        variants = await sync_to_async(get_variants)()
        await loading.delete()

        if not variants:
            await update.message.reply_text(f"😕 '{clean_query}' bo'yicha mahsulot topilmadi.")
            return

        for v in variants:
            status_text = "🟢 Faol" if v.is_active else "🔴 O'chirilgan"
            action_btn = "O'chirish" if v.is_active else "Yoqish"
            btn_style = "danger" if v.is_active else "success"

            # Ma'lumotlarni chiqarish
            cap = (
                f"📦 <b>{v.product.name}</b>\n"
                f"🏭 Zavod: {v.brand or '---'}\n"
                f"📏 O'lcham: {v.size or '---'}\n"
                f"💰 Narxi: {v.selling_price:,.0f} so'm\n"
                f"📍 Holati: {status_text}"
            )
            
            kb = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    f"⚙️ {action_btn}", 
                    callback_data=f"adm_tog:{v.id}", 
                    api_kwargs={"style": btn_style}
                )
            ]])

            # Rasm: Variant rasmi bo'lmasa, mahsulot rasmi
            img_path = None
            if v.image and os.path.exists(v.image.path):
                img_path = v.image.path
            elif v.product.image and os.path.exists(v.product.image.path):
                img_path = v.product.image.path

            if img_path:
                with open(img_path, 'rb') as f:
                    await update.message.reply_photo(photo=f, caption=cap, parse_mode=ParseMode.HTML, reply_markup=kb)
            else:
                await update.message.reply_text(cap, parse_mode=ParseMode.HTML, reply_markup=kb)

    except Exception as e:
        await update.message.reply_text(f"⚠️ Xatolik: {e}")

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tugmalar bosilganda ishlaydigan global handler"""
    query = update.callback_query
    data = query.data
    await query.answer()

    # 1. Sahifalash
    if data.startswith("adm_page:"):
        page = int(data.split(":")[1])
        await query.edit_message_reply_markup(reply_markup=await get_paginated_products(page))

    # 2. Mahsulot tanlanganda variantlarni ko'rsatish
    elif data.startswith("adm_p:"):
        p_id = data.split(":")[1]
        variants = await sync_to_async(list)(ProductVariant.objects.filter(product_id=p_id))
        
        kb_list = []
        for v in variants:
            style = "success" if v.is_active else "danger"
            kb_list.append([InlineKeyboardButton(
                f"{v.brand} | {v.size} ({v.selling_price:,.0f})", 
                callback_data=f"adm_tog:{v.id}",
                api_kwargs={"style": style}
            )])
        kb_list.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="adm_page:0")])
        await query.edit_message_text("Variantni tanlang:", reply_markup=InlineKeyboardMarkup(kb_list))

    # 3. Yoqish/O'chirish (Toggle)
    elif data.startswith("adm_tog:"):
        v_id = data.split(":")[1]
        v = await sync_to_async(ProductVariant.objects.select_related('product').get)(id=v_id)
        
        # Holatni o'zgartirish
        v.is_active = not v.is_active
        await sync_to_async(v.save)()
        
        res_text = "yoqildi" if v.is_active else "o'chirildi"
        await query.message.reply_text(f"✅ {v.product.name} ({v.brand}) muvaffaqiyatli {res_text}!")
        # Xabarni yangilab qo'yish ham mumkin (ixtiyoriy)

    # 4. Yopish
    elif data == "adm_close":
        await query.message.delete()