from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from ..models.TelegramBot import TelegramUser
from asgiref.sync import sync_to_async
from ..decorators import admin_required


async def get_admins():
    """
    Admin bo'lgan ma'lumotini qaytaradi.
    """
    return await sync_to_async(
        lambda: list(TelegramUser.objects.filter(is_admin=True))
    )()


@admin_required
async def AdminList(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admins_list = await get_admins()
    await update.callback_query.answer()
    bot_username = await context.bot.get_me()
    message = f"<b>@{bot_username.username} dagi adminlar ro'yxati.</b>\n\n"
    index = 1
    for admins in admins_list:
        message += f"<b>{index}. Admin:</b> <a href='tg://user?id={admins.user_id}'>{admins.first_name}</a>\n————\n"
        index += 1
    await context.bot.send_message(
        chat_id=update.effective_user.id, text=message, parse_mode="HTML"
    )
    return ConversationHandler.END
