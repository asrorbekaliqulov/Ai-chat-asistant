from telegram.ext import ContextTypes, ConversationHandler
from telegram import Update
from ..utils import save_user_to_db
from ..models.TelegramBot import TelegramUser
from ..decorators import (
    typing_action,
    mandatory_channel_required,
)
from telegram import ReplyKeyboardRemove

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
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
    buttons = [[InlineKeyboardButton(f"📞 Admin bilan bog'lanish", url=f"https://t.me/Rizogo_Support")]]


    markup = InlineKeyboardMarkup(buttons) if buttons else None

    # Agar user admin bo‘lsa, admin panelni ham ko‘rsatamiz
    admin_id = await TelegramUser.get_admin_ids()
    if update.effective_user.id in admin_id:
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text="<b>Main Menu 🖥\n<tg-spoiler>/admin_panel</tg-spoiler></b>",
            reply_markup=remove,
            parse_mode="html",
        )

    # Asosiy salomlashuv xabari
    text = (
        "<b>👋 Salom! Men sizga yordam beruvchi botman.</b>\n\n"
        "Siz Rizo Go kompaniyasining rasmiy yordamchisiga yozdingiz.\n"
        "Savolingizni yozing AI sizga javob beradi yoki quyidagi adminlar orqali bog‘lanishingiz mumkin 👇"
    )

    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text=text,
        reply_markup=markup,
        parse_mode="html",
    )

    return ConversationHandler.END
