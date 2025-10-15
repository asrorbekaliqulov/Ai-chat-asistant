from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from ..models.TelegramBot import Channel
from asgiref.sync import sync_to_async
from ..decorators import admin_required


async def get_admins():
    """
    Admin bo'lgan ma'lumotini qaytaradi.
    """
    return await sync_to_async(lambda: list(Channel.objects.all()))()


@admin_required
async def MandatoryChannelOrGroupList(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    channels = await get_admins()
    bot_username = await context.bot.get_me()
    message = f"<b>@{bot_username.username} dagi majburiy kanal/guruh ro'yxati.</b>\n\n"
    index = 1
    for channel in channels:
        if channel.type in "channel":
            message += f"<b>{index}.📢 Kanal:</b> <a href='{channel.url}'>{channel.name}</a>\n————\n"
        elif channel.type in "group":
            message += f"<b>{index}.💬 Guruh:</b> <a href='{channel.url}'>{channel.name}</a>\n————\n"
        else:
            message += f"<b>{index}.🤷‍♂️ Other:</b> <a href='{channel.url}'>{channel.name}</a>\n————\n"
        index += 1
    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text=message,
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    return ConversationHandler.END
