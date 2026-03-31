from telegram.ext import ContextTypes, ConversationHandler
from telegram import Update
from ..utils import save_user_to_db
from ..models.TelegramBot import TelegramUser
from ..decorators import (
    typing_action,
    mandatory_channel_required,
)
from telegram import ReplyKeyboardRemove
from apps.Bot import ADMIN_KYB
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton, ReplyKeyboardMarkup
from asgiref.sync import sync_to_async



# 🧩 start komandasi
@typing_action
@mandatory_channel_required
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Botni ishga tushirish uchun komanda.
    """
    remove = ReplyKeyboardRemove()
    data = update.effective_user

    # Callback'dan kelsa — xabarni tozalaymiz
    if update.callback_query:
        await update.callback_query.answer("Asosiy menyu")
        await update.callback_query.delete_message()

    # Foydalanuvchini bazaga saqlaymiz
    is_save = await save_user_to_db(data)


    # Inline tugmalar (faqat username bor adminlar uchun)
    buttons = [
        [
            # KeyboardButton(f"📚 Katalog"), 
            # KeyboardButton("🛒 Savat")
        ]
    ]


    markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True) if buttons else None

    # Agar user admin bo‘lsa, admin panelni ham ko‘rsatamiz
    admin_id = await TelegramUser.get_admin_ids()
    if update.effective_user.id in admin_id:
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text="<b>Main Menu 🖥\n<tg-spoiler>/admin_panel</tg-spoiler></b>",
            reply_markup=remove,
            parse_mode="html",
        )
    text="""<b>"DO‘NGARIQ STROY"</b> do'konimizga xush kelibsiz! Barcha mahsulotlar va buyurtmalar bo'yicha savollaringizga @dongariq_stroy guruhimizda tezkor javob olishingiz mumkin. Biz sizga yordam berishdan mamnunmiz! 🧱

<b>Bog'lanish uchun:</b>
📞 +998330576161 📱 Telegram: @dongariq_stroy"""

    if update.effective_user.id in admin_id:
        markup = ADMIN_KYB
    else:
        markup = ReplyKeyboardMarkup(buttons, resize_keyboard=True) if buttons else None
    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text=text,
        reply_markup=markup,
        parse_mode="html",
    )

    return ConversationHandler.END



async def set_user_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchi turini saqlash"""
    user_type = update.callback_query.data
    user_id = update.effective_user.id

    await TelegramUser.update_user_type(user_id, user_type)

    await update.callback_query.answer("Siz tanladingiz: " + ("Mutaxasis" if user_type == "mutaxasis" else "Fuqaro"))
    await update.callback_query.edit_message_text("Siz muvaffaqiyatli ro'yxatdan o'tdingiz!")

    # Start komandani chaqiramiz
    return await start(update, context)