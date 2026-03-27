import os
import io
import json
from decimal import Decimal
from django.db import transaction
from django.db.models import Q
from asgiref.sync import sync_to_async
from apps.Bot import ADMIN_KYB
from google import genai
from google.genai import types # type: ignore #ignore
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ContextTypes, 
    ConversationHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    CommandHandler, 
    filters
)

# 1. Modellarni import qilish
from apps.warehouse.models.base import ProductVariant, StockTransaction

# 2. Gemini Sozlamalari
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

find_product_tool = types.FunctionDeclaration(
    name="find_product",
    description="Ombordan mahsulotni nomi va miqdori bo'yicha qidiradi",
    parameters=types.Schema(
        type="OBJECT",
        properties={
            "search_query": types.Schema(type="STRING", description="Mahsulot nomi yoki brendi"),
            "quantity": types.Schema(type="NUMBER", description="Sotilayotgan miqdor")
        },
        required=["search_query", "quantity"]
    )
)

tools = [types.Tool(function_declarations=[find_product_tool])]
SELECTING_PRODUCT = 1

# 3. Mantiqiy qism: SaleManager
class SaleManager:
    @staticmethod
    @sync_to_async
    def get_all_product_names():
        """AI context uchun barcha mahsulot variantlarini olish"""
        names = ProductVariant.objects.select_related('product').values_list(
            'product__name', 'brand', 'size'
        )
        return [f"{n[0]} {n[1]} {n[2]}" for n in names]

    @staticmethod
    @sync_to_async
    def find_product_in_db(search_query: str, quantity: float):
        """Brend va o'lcham bo'yicha aqlli qidiruv"""
        variants = ProductVariant.objects.filter(
            Q(product__name__icontains=search_query) | 
            Q(brand__icontains=search_query) |
            Q(size__icontains=search_query)
        ).select_related('product')[:5]

        if not variants.exists():
            words = search_query.split()
            query = Q()
            for word in words:
                if len(word) > 2:
                    query |= Q(product__name__icontains=word) | Q(brand__icontains=word)
            variants = ProductVariant.objects.filter(query).select_related('product')[:5]

        if not variants.exists():
            return {"status": "not_found", "query": search_query}

        results = []
        for v in variants:
            results.append({
                "id": v.id,
                "name": f"{v.product.name} ({v.brand} - {v.size})",
                "stock": float(v.stock),
                "price": float(v.selling_price),
                "qty": quantity,
                "total": float(v.selling_price) * quantity,
                "unit": v.product.unit
            })
        return {"status": "found", "data": results}

    @staticmethod
    @sync_to_async
    def process_sale_db(variant_id: int, qty: float):
        """Tranzaksiya yaratish va qoldiqni ayirish"""
        try:
            with transaction.atomic():
                variant = ProductVariant.objects.select_for_update().get(id=variant_id)
                decimal_qty = Decimal(str(qty))
                
                if variant.stock < decimal_qty:
                    return f"❌ Ombor yetarli emas! (Qoldiq: {variant.stock} {variant.product.unit})"
                
                # Tranzaksiya yaratish (Modeldagi .save() qoldiqni yangilaydi)
                StockTransaction.objects.create(
                    variant=variant,
                    quantity=decimal_qty,
                    transaction_type='OUT',
                    note="Telegram bot (Ovozli/Matn) orqali sotuv"
                )
                
                variant.refresh_from_db()
                return (f"✅ Sotildi: <b>{variant.product.name}</b>\n"
                        f"📉 Miqdor: {decimal_qty} {variant.product.unit}\n"
                        f"📦 Yangi qoldiq: <b>{variant.stock} {variant.product.unit}</b>")
        except Exception as e:
            return f"❌ Xatolik: {str(e)}"

# 4. Yordamchi funksiyalar
def get_sale_markup(product_data):
    text = (
        f"🛒 <b>Sotuv ma'lumotlari:</b>\n\n"
        f"📦 Mahsulot: <b>{product_data['name']}</b>\n"
        f"🔢 Miqdor: <b>{product_data['qty']} {product_data['unit']}</b>\n"
        f"💰 Narxi: {product_data['price']:,} so'm\n"
        f"💵 Jami: <b>{product_data['total']:,} so'm</b>\n"
        f"📉 Omborda: {product_data['stock']} {product_data['unit']} bor"
    )
    keyboard = [
        [InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"conf_sale:{product_data['id']}:{product_data['qty']}")],
        [
            InlineKeyboardButton("🔄 Qayta aytish", callback_data="retry_input"),
            InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_item")
        ]
    ]
    return text, InlineKeyboardMarkup(keyboard)

# 5. Handlerlar
async def start_sale_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🛒 <b>Sotuv rejimi faol.</b>\n"
        "Mahsulot nomi va miqdorini yozing yoki <b>ovozli xabar</b> yuboring.",
        parse_mode='HTML',
        reply_markup=ReplyKeyboardMarkup([['❌ Chiqish']], resize_keyboard=True)
    )
    return SELECTING_PRODUCT

async def handle_sale_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_msg = None
    user_audio = None

    if update.message.text:
        user_msg = update.message.text
        if user_msg == "❌ Chiqish":
            return await cancel_all(update, context)
    elif update.message.voice:
        voice_file = await update.message.voice.get_file()
        voice_data = io.BytesIO()
        await voice_file.download_to_memory(voice_data)
        user_audio = voice_data.getvalue()

    try:
        existing_names = await SaleManager.get_all_product_names()
        
        # System instructions - Bir nechta mahsulotni aniqlash uchun ko'rsatma
        prompt_text = (
            f"Vazifa: Foydalanuvchi aytgan barcha mahsulotlar va ularning miqdorini aniqla.\n"
            f"Mavjud mahsulotlar ro'yxati: {existing_names[:150]}\n\n"
            f"QOIDALAR:\n"
            f"1. Agar foydalanuvchi bir nechta mahsulot aytsa (masalan: '2 ta sement va 5 kg mix'), "
            f"har biri uchun alohida 'find_product' funksiyasini chaqir.\n"
            f"2. Matematik hisob: Agar sement o'lchami '50 kg' bo'lsa va '1 tonna' deyilsa, quantity=20 deb yubor.\n"
            f"3. Har bir mahsulotni aniq topishga harakat qil."
        )

        parts = [types.Part.from_text(text=prompt_text)]

        if user_msg:
            parts.append(types.Part.from_text(text=f"Foydalanuvchi xabari: {user_msg}"))
        elif user_audio:
            parts.append(types.Part.from_bytes(data=user_audio, mime_type="audio/ogg"))

        response = client.models.generate_content(
            model="gemini-2.0-flash", # Barqaror versiya
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(tools=tools)
        )

        # MUHIM: Barcha function_call larni yig'ib olamiz (tsikl orqali)
        calls = [p.function_call for p in response.candidates[0].content.parts if p.function_call]

        if calls:
            found_any = False
            for call in calls:
                result = await SaleManager.find_product_in_db(
                    call.args['search_query'], 
                    call.args['quantity']
                )
                
                if result["status"] == "found":
                    found_any = True
                    # Har bir topilgan mahsulot uchun alohida xabar va tugma chiqarish
                    for prod in result["data"]:
                        text, markup = get_sale_markup(prod)
                        await update.message.reply_text(text, reply_markup=markup, parse_mode='HTML')
                else:
                    await update.message.reply_text(f"❓ '{call.args['search_query']}' topilmadi.")
            
            if not found_any:
                await update.message.reply_text("Aytilgan mahsulotlar bazadan topilmadi.")
        else:
            # Agar AI hech qanday mahsulot topmasa
            ai_text = response.text if response.text else "Tushunmadim. Iltimos, mahsulotlarni va miqdorini aniqroq ayting."
            await update.message.reply_text(ai_text)

    except Exception as e:
        print(f"Gemini Multi-Sale Error: {e}")
        await update.message.reply_text("⚠️ Xabarni tahlil qilishda xatolik yuz berdi.")
    
    return SELECTING_PRODUCT
async def confirm_sale_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    _, v_id, qty = query.data.split(":")
    res_msg = await SaleManager.process_sale_db(int(v_id), float(qty))
    
    await query.edit_message_text(f"{res_msg}\n\n♻️ <b>Keyingi mahsulot?</b>", parse_mode='HTML')
    return SELECTING_PRODUCT

async def retry_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("🔄 Marhamat, ma'lumotni qayta yuboring (ovoz yoki matn):")
    return SELECTING_PRODUCT

async def cancel_item_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text("❌ Bekor qilindi. Keyingi mahsulotni aytishingiz mumkin:")
    return SELECTING_PRODUCT



async def cancel_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Sotuv rejimi yakunlandi.", reply_markup=ADMIN_KYB)
    return ConversationHandler.END

# 6. Conversation Handler
sale_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex('^🛍 Sotish$'), start_sale_mode)],
    states={
        SELECTING_PRODUCT: [
            MessageHandler((filters.TEXT | filters.VOICE) & ~filters.COMMAND, handle_sale_input),
            CallbackQueryHandler(confirm_sale_callback, pattern="^conf_sale:"),
            CallbackQueryHandler(retry_callback, pattern="^retry_input$"),
            CallbackQueryHandler(cancel_item_callback, pattern="^cancel_item$")
        ],
    },
    fallbacks=[CommandHandler('cancel', cancel_all), MessageHandler(filters.Regex('^❌ Chiqish$'), cancel_all)],
    allow_reentry=True
)