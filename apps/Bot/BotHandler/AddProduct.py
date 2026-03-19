import os
import io
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, 
    ConversationHandler, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    filters
)
from .AddProductUtils import analyze_product_data

# Holatlar
INPUT_PRODUCT_DATA = 1

# --- 1. AI TAHLIL FUNKSIYASI (Yuqoridagi Client SDK asosida) ---
async def get_ai_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    
    # Audio yoki Matnni aniqlash
    if msg.voice:
        status_msg = await msg.reply_text("⏳ Ovoz eshitilmoqda, tahlil qilinmoqda...")
        file = await context.bot.get_file(msg.voice.file_id)
        
        # Faylni xotirada saqlash (Diskka yozmaslik uchun)
        audio_bytearray = await file.download_as_bytearray()
        
        # analyze_product_data funksiyasiga yuboramiz (avvalgi javobdagi funksiya)
        # Eslatma: data: audio_bytearray ko'rinishida yuboring
        data = await analyze_product_data(audio_bytes=audio_bytearray)
        await status_msg.delete()
    else:
        status_msg = await msg.reply_text("⏳ Matn tahlil qilinmoqda...")
        data = await analyze_product_data(text_content=msg.text)
        await status_msg.delete()

    if not data:
        await msg.reply_text("❌ Ma'lumotni tushunolmadim. Iltimos, aniqroq ayting yoki yozing.")
        return INPUT_PRODUCT_DATA

    # --- 2. MAJBURIY FIELDLARNI TEKSHIRISH ---
    required = {
        'name': 'Mahsulot nomi', 
        'purchase_price': 'Kirim narxi', 
        'quantity': 'Miqdori'
    }
    missing = [label for field, label in required.items() if data.get(field) is None]

    if missing:
        missing_str = ", ".join(missing)
        await msg.reply_text(
            f"⚠️ **Ma'lumot to'liq emas!**\n\nQuyidagilar aytilmadi: *{missing_str}*.\n"
            f"Iltimos, qaytadan to'liqroq ma'lumot bering.",
            parse_mode="Markdown"
        )
        return INPUT_PRODUCT_DATA

    # --- 3. TASDIQLASH ---
    context.user_data['draft_product'] = data
    
    res_text = (
f"""✅ **AI tahlil natijasi:**
📦 **Nomi:** {data['name']}
🏭 **Zavod:** {data.get('brand') or "Noma`lum"}
📏 **O'lcham:** {data.get('size') or '—'}
💰 **Kirim narxi:** {data['purchase_price']:,.0f} so'm
🔢 **Miqdori:** {data['quantity']} {data.get('unit') or ''}
Ma'lumotlar to'g'rimi?"""
    )

    keyboard = [
        [InlineKeyboardButton("✅ Ha, bazaga saqlansin", callback_data='confirm_ai_save')],
        [InlineKeyboardButton("🔄 Qaytadan aytish", callback_data='retry_ai_input')],
        [InlineKeyboardButton("❌ Bekor qilish", callback_data='cancel_ai')]
    ]
    
    await msg.reply_text(res_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return ConversationHandler.END

# --- 2. CONVERSATION HANDLER SOZLAMASI ---

WAITING_FOR_DATA = 1

async def start_add_product_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("🎤 Mahsulot haqida ovozli yoki matnli xabar yuboring...")
    else:
        await update.message.reply_text("🎤 Mahsulot haqida ovozli yoki matnli xabar yuboring...")
    
    return WAITING_FOR_DATA

async def cancel_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text("🚫 Bekor qilindi.")
    else:
        await update.message.reply_text("🚫 Bekor qilindi.")
    return ConversationHandler.END


product_ai_handler = ConversationHandler(
    entry_points=[
        # Agar tugma orqali bo'lsa CallbackQueryHandler, komanda bo'lsa CommandHandler
        CallbackQueryHandler(start_add_product_process, pattern='^add_product_ai$'),
        CommandHandler('add_product', start_add_product_process)
    ],
    states={
        WAITING_FOR_DATA: [
            MessageHandler(filters.TEXT | filters.VOICE, get_ai_analysis)
        ],
    },
    fallbacks=[
        CallbackQueryHandler(cancel_process, pattern='^cancel_ai$'),
        CommandHandler('cancel', cancel_process)
    ],
)