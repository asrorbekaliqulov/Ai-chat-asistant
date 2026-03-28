import os
import io
import numpy as np
from asgiref.sync import sync_to_async
from django.db.models import Q
from google import genai
from google.genai import types

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, 
    ReplyKeyboardMarkup, ReplyKeyboardRemove
)
from telegram.constants import ChatAction, ParseMode, ChatMemberStatus
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler, 
    MessageHandler, filters, CallbackQueryHandler
)

# Modellarni import qilish
from apps.warehouse.models.base import ProductVariant, StockTransaction
from apps.Bot.models.TelegramBot import CompanyData
from apps.Bot.utils import save_message_to_db
from apps.Bot.decorators import typing_action
from apps.Bot.keybaords import ADMIN_KYB

# 1. Gemini Sozlamalari
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# Conversation States
WAITING_AI_INPUT, CONFIRM_ADD = range(2)

# Admin panel URL (Keyinchalik o'zgartirishingiz mumkin)
ADMIN_ADD_PRODUCT_URL = "https://your-admin-panel.com/warehouse/productvariant/add/"

# 2. AI Tools
ai_tools = [types.Tool(function_declarations=[
    types.FunctionDeclaration(
        name="process_stock_request",
        description="Foydalanuvchi mahsulot qo'shish istagini tahlil qiladi.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "product_name": types.Schema(type="STRING", description="Mahsulot nomi"),
                "quantity": types.Schema(type="INTEGER", description="Miqdor (bo'lsa)", nullable=True),
            },
            required=["product_name"]
        )
    )
])]

# 3. Yordamchi Funksiyalar
def get_add_new_button():
    """Yangi mahsulot qo'shish tugmasini qaytaradi"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Yangi mahsulot yaratish (Admin Panel)", url=ADMIN_ADD_PRODUCT_URL)]
    ])

@sync_to_async
def execute_stock_update(variant_id, quantity, user_id):
    try:
        v = ProductVariant.objects.get(id=variant_id)
        v.stock += quantity
        v.save()
        StockTransaction.objects.create(
            variant=v, quantity=quantity, transaction_type='IN', 
            note=f"AI Bot orqali kirim (User ID: {user_id})"
        )
        return f"✅ <b>Muvaffaqiyatli!</b>\n{v.product.name} zaxirasiga {quantity} {v.product.unit} qo'shildi.\nYangilangan qoldiq: {v.stock}"
    except Exception as e:
        return f"❌ Xatolik yuz berdi: {str(e)}"

# 5. CONVERSATION HANDLER FUNKSIYALARI

@typing_action
async def start_stock_ai(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [['❌ Chiqish']]
    await update.message.reply_text(
        "🎤 <b>Omborga tovar qo'shish (AI)</b>\n\nMahsulot nomini ayting yoki yozing.\n"
        "<i>To'xtatish uchun '❌ Chiqish' tugmasini bosing.</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardMarkup(kb, resize_keyboard=True)
    )
    # Birinchi xabar bilan birga yangi mahsulot qo'shish tugmasini ham yuboramiz
    await update.message.reply_text(
        "Agar mahsulot bazada hali mavjud bo'lmasa, quyidagi tugma orqali qo'shishingiz mumkin:",
        reply_markup=get_add_new_button()
    )
    return WAITING_AI_INPUT

async def handle_ai_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_msg = update.message
    if user_msg.text == "❌ Chiqish":
        return await cancel_stock(update, context)

    content_parts = []
    if user_msg.voice:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.RECORD_VOICE)
        file = await context.bot.get_file(user_msg.voice.file_id)
        voice_data = await file.download_as_bytearray()
        content_parts.append(types.Part.from_bytes(data=bytes(voice_data), mime_type="audio/ogg"))
        prompt = "Ushbu ovozni eshit va mahsulot nomi hamda miqdorini aniqla."
    else:
        content_parts.append(types.Part.from_text(text=user_msg.text))
        prompt = "Matndagi mahsulot nomi va miqdorini aniqla."

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[types.Content(role="user", parts=content_parts + [types.Part.from_text(text=prompt)])],
            config=types.GenerateContentConfig(tools=ai_tools)
        )

        call = next((p.function_call for p in response.candidates[0].content.parts if p.function_call), None)
        if not call:
            await update.message.reply_text("❓ Tushunarsiz buyruq. Iltimos qayta urinib ko'ring.")
            return WAITING_AI_INPUT

        p_name = call.args['product_name']
        qty = call.args.get('quantity')

        products = await sync_to_async(list)(ProductVariant.objects.filter(
            Q(product__name__icontains=p_name) | Q(brand__icontains=p_name)
        ).select_related('product')[:5])

        if not products:
            await update.message.reply_text(
                f"🔍 '{p_name}' bo'yicha mahsulot topilmadi. Uni yangi mahsulot sifatida qo'shishingiz mumkin:",
                reply_markup=get_add_new_button()
            )
            return WAITING_AI_INPUT

        for p in products:
            text = f"📦 <b>{p.product.name}</b>\n🏷 Brend: {p.brand}\n🤏 O'lcham: {p.size}\n📊 Qoldiq: {p.stock} {p.product.unit}"
            kb_list = []
            if qty:
                kb_list.append([InlineKeyboardButton(f"✅ {qty} ta qo'shish", callback_data=f"confirm:{p.id}:{qty}")])
            else:
                kb_list.append([InlineKeyboardButton("➕ Miqdor yozish", callback_data=f"ask_qty:{p.id}")])
            
            await update.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(kb_list))
        
        return WAITING_AI_INPUT

    except Exception as e:
        await update.message.reply_text(f"Xatolik: {str(e)}")
        return WAITING_AI_INPUT

async def stock_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split(":")
    action, v_id = data[0], data[1]
    await query.answer()

    if action == "ask_qty":
        context.user_data['target_v_id'] = v_id
        await query.edit_message_text("🔢 Nechta qo'shmoqchisiz? Raqamni yozing:")
        return CONFIRM_ADD

    elif action == "confirm":
        qty = int(data[2])
        res = await execute_stock_update(v_id, qty, update.effective_user.id)
        await query.edit_message_text(res, parse_mode=ParseMode.HTML)
        # Mahsulot qo'shilgandan keyin yana kirish xabarini yuboramiz (Tsikl davom etadi)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Keyingi mahsulotni ayting yoki yozing:"
        )
        return WAITING_AI_INPUT

async def manual_qty_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "❌ Chiqish":
        return await cancel_stock(update, context)

    if not text.isdigit():
        await update.message.reply_text("Iltimos, faqat musbat raqam kiriting:")
        return CONFIRM_ADD
    
    v_id = context.user_data.get('target_v_id')
    res = await execute_stock_update(v_id, int(text), update.effective_user.id)
    await update.message.reply_text(res, parse_mode=ParseMode.HTML)
    
    # Ma'lumot qo'shilgach, tsiklni davom ettirish
    await update.message.reply_text("Keyingi mahsulotni ayting yoki yozing:")
    return WAITING_AI_INPUT

async def cancel_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📦 Ombor amallari yakunlandi.", reply_markup=ADMIN_KYB)
    return ConversationHandler.END

# 7. HANDLERLARNI RO'YXATDAN O'TKAZISH
stock_ai_conv = ConversationHandler(
    entry_points=[MessageHandler(filters.Regex("^➕ Qo'shish"), start_stock_ai)],
    states={
        WAITING_AI_INPUT: [
            MessageHandler(filters.TEXT | filters.VOICE, handle_ai_input),
            CallbackQueryHandler(stock_callback_handler, pattern="^(ask_qty|confirm):")
        ],
        CONFIRM_ADD: [
            # Bu yerda ham Chiqish tugmasini tekshirish kerak
            MessageHandler(filters.TEXT & ~filters.COMMAND, manual_qty_input)
        ],
    },
    fallbacks=[
        CommandHandler('cancel', cancel_stock),
        MessageHandler(filters.Regex('^❌ Chiqish$'), cancel_stock)
    ],
    allow_reentry=True
)