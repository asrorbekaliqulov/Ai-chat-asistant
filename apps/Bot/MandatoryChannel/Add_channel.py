from telegram import (
    Update,
    KeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButtonRequestChat,
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    CommandHandler,
)
from ..utils import create_channel
from ..models.TelegramBot import Channel
from asgiref.sync import sync_to_async
from warnings import filterwarnings
from telegram.warnings import PTBUserWarning

filterwarnings(
    action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning
)

# Keyboard button
keybord = [
    [
        KeyboardButton(
            text="Kanal",
            request_chat=KeyboardButtonRequestChat(
                request_id=1,
                chat_is_channel=True,
                bot_is_member=True,
                request_title=True,
            ),
        ),
        KeyboardButton(
            text="Guruh",
            request_chat=KeyboardButtonRequestChat(
                request_id=2,
                chat_is_channel=False,
                bot_is_member=True,
                request_title=True,
            ),
        ),
    ],
]

reply_markup = ReplyKeyboardMarkup(
    keybord,
    one_time_keyboard=True,
    resize_keyboard=True,
    input_field_placeholder="👇Quyidagi tugmalardan foydalaning👇",
)


@sync_to_async
def GetChannelByID(chat_id):
    try:
        channel = Channel.objects.get(channel_id=chat_id)
        return channel
    except:
        return None


async def start_add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kanal yoki guruhni qo‘shishni boshlaydi."""
    # Keyboard button
    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text="<b>Iltimos quyidagi tugmalarni bosgan holda kerakli kanal/guruhni tanlang.</b>\n\n<i>Kanal yoki Guruh o'shishdan avval botga administrator huquqlarini berganinggizga ishonch hosil qiling</i>",
        parse_mode="HTML",
        reply_markup=reply_markup,
    )
    return "START_ADD_CHANNEL"


async def Check_bot_administrator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kanal yoki guruh xabarini qayta ishlaydi va inline tugmalarni ko‘rsatadi."""
    if update.message.chat_shared is None:
        await update.message.reply_text(
            "<b>Menimcha siz pastdagi tugmani bosmadingiz😤</b>\nIltimos quyidagi tugmalarni bosing",
            reply_markup=reply_markup,
            parse_mode="HTML",
        )
        return "START_ADD_CHANNEL"
        # User tanlagan Kanal/Guruh ID sini olish
    channel_or_group_ID = update.message.chat_shared.chat_id
    channel_or_group_name = update.message.chat_shared.title
    chat_type = ""
    request_id = update.message.chat_shared.request_id

    if request_id == 1:
        chat_type = "channel"
    elif request_id == 2:
        chat_type = "group"
    bot = await context.bot.get_me()

    is_saved = await GetChannelByID(channel_or_group_ID)
    if is_saved:
        await update.message.reply_text(
            "<b>Kanal/Guruh allaqachon mavjud!</b>", parse_mode="HTML"
        )
        return ConversationHandler.END

    try:
        invite_link = await context.bot.create_chat_invite_link(
            chat_id=channel_or_group_ID, name=f"{bot.first_name}"
        )

        channel_save = await create_channel(
            chat_id=channel_or_group_ID,
            chat_name=channel_or_group_name,
            chat_type=chat_type,
            url=invite_link.invite_link,
        )
        if channel_save:
            await update.message.reply_text(
                "<b>Muvaffaqiyatli saqlandi!!!</b>", parse_mode="HTML"
            )
            return ConversationHandler.END
    except:
        await update.message.reply_text(
            "Xatolik ro'y berdi menimcha botni admin qilmadingiz."
        )
        return "START_ADD_CHANNEL"


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ConversationHandler ni bekor qilish."""
    await update.message.reply_text("Amal bekor qilindi.")
    return ConversationHandler.END


AddChannel_ConvHandler = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_add_channel, pattern=r"^Add_mandatory$")],
    states={
        "START_ADD_CHANNEL": [MessageHandler(filters.USER, Check_bot_administrator)]
    },
    fallbacks=[CommandHandler("cancel", cancel)],
)
