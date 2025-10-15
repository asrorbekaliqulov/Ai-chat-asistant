from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (ContextTypes, ConversationHandler, MessageHandler, filters, CallbackQueryHandler)
from ..models.TelegramBot import CompanyData
from ..decorators import admin_required
from asgiref.sync import sync_to_async


admin_keyboard_list = [
    [
        InlineKeyboardButton(text="📨 Xabar yuborish", callback_data="send_messages"),
        InlineKeyboardButton(text="📊 Bot statistikasi", callback_data="botstats"),
    ],
    [
        InlineKeyboardButton(text="➕ Malumot qo'shish", callback_data="add_data"),
        InlineKeyboardButton(text="🗑️ Malumot o'chirish", callback_data="delete_data"),
    ],
    [InlineKeyboardButton(text="📋 Malumotlar ro'yxati", callback_data="data_list")],
    [
        InlineKeyboardButton(text="👮‍♂️ Admin qo'shish", callback_data="add_admin"),
        InlineKeyboardButton(text="🙅‍♂️ Admin o'chirish", callback_data="delete_admin"),
    ],
    [InlineKeyboardButton(text="🗒 Adminlar yo'yxati", callback_data="admin_list")],
    
]
Admin_keyboard = InlineKeyboardMarkup(admin_keyboard_list)


# Holatlarni aniqlash
WAITING_FOR_TEXT = 1

# ➕ Ma’lumot qo‘shish jarayonini boshlovchi funksiya
@admin_required
async def add_data_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    await update.callback_query.edit_message_text(
        "✍️ Yangi ma’lumotni kiriting:",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel")]]
        ),
    )
    return WAITING_FOR_TEXT


# Matnni qabul qilib, bazaga saqlovchi funksiya
async def save_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("❌ Ma’lumot bo‘sh bo‘lishi mumkin emas.")
        return WAITING_FOR_TEXT
    try:
        await sync_to_async(CompanyData.objects.create)(content=text)
        await update.message.reply_text("✅ <b>Ma’lumot muvaffaqiyatli qo‘shildi.</b>", reply_markup=Admin_keyboard, parse_mode="HTML")
        return ConversationHandler.END
    except Exception as e:
        await update.message.reply_text(f"❌ Xatolik yuz berdi qayta urinib ko‘ring. \n{e}")
        return WAITING_FOR_TEXT
    return ConversationHandler.END



# ❌ Bekor qilish tugmasi bosilganda
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Amal bekor qilindi.")
    await query.edit_message_text("❌ Amal bekor qilindi.")
    return ConversationHandler.END


# ConversationHandler’ni qaytarish
add_data_handler =  ConversationHandler(
        entry_points=[CallbackQueryHandler(add_data_start, pattern="^add_data$")],
        states={
            WAITING_FOR_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_data)
            ],
        },
        fallbacks=[CallbackQueryHandler(cancel, pattern="^cancel$"),],
    )