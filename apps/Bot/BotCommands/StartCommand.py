from telegram.ext import ContextTypes, ConversationHandler
from telegram import Update
from ..utils import save_user_to_db
from ..models.TelegramBot import TelegramUser
from ..decorators import (
    typing_action,
    mandatory_channel_required,
)
from telegram import ReplyKeyboardRemove

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton, ReplyKeyboardMarkup
from asgiref.sync import sync_to_async


async def user_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchi turini so'rash"""
    buttons = [
        [InlineKeyboardButton("🏢 Mutaxasis", callback_data="mutaxasis")],
        [InlineKeyboardButton("👥 Fuqaro", callback_data="fuqaro")],
    ]
    markup = InlineKeyboardMarkup(buttons)

    if update.callback_query:
        await update.callback_query.answer("Foydalanuvchi turini tanlang")
        await update.callback_query.edit_message_text(
            text="Iltimos, o'zingizni tanlang:", reply_markup=markup
        )
    else:
        await update.message.reply_text(
            text="Iltimos, o'zingizni tanlang:", reply_markup=markup
        )



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

    # user_typ = await TelegramUser.get_user_type(update.effective_user.id)
    # print(user_typ)
    # if user_typ is None:
    #     return await user_type(update, context)

    # Inline tugmalar (faqat username bor adminlar uchun)
    buttons = [
        [
            KeyboardButton(f"📚 Katalog"), 
            KeyboardButton("🛒 Savat")
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
    text="""<b>👋 Salom! Men — Aromazona.uz virtual yordamchisiman.</b> 

Sizga dunyo brendlarining eng sara premium iforlarini tanlashda yordam beraman.  🧴✨

Menga brend nomini yozing yoki xohishingizni bildiring.

Men sizga darhol eng yaxshi variantlarni topaman! 🚀

<b>Bog'lanish uchun:</b>
📞 +998333635333 📱 Instagram: @Aromazone.uz"""

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