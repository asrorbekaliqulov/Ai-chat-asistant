from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from asgiref.sync import sync_to_async
from ..models.TelegramBot import Channel


# Barcha Channel ma'lumotlarini olish uchun asinxron funksiya
@sync_to_async
def get_all_channels():
    return list(Channel.objects.all())  # QuerySet ni ro'yxatga aylantirish


# Barcha Channel ma'lumotlarini olish uchun asinxron funksiya
@sync_to_async
def Delete_channels(channel_id):
    return Channel.objects.filter(
        channel_id=channel_id
    ).delete()  # QuerySet ni ro'yxatga aylantirish


async def start_delete_mandatory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboards = []

    # Barcha kanallarni olish
    channels = await get_all_channels()

    # Har bir kanal uchun tugma yaratish
    for channel in channels:
        keyboards.append(
            [
                InlineKeyboardButton(
                    text=f"{channel.name}",
                    callback_data=f"xDeleted_{channel.channel_id}",
                )
            ]
        )

    await update.callback_query.edit_message_text(
        text="<b>O'shirmoqchi bo'lgan kanalni tanlang</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboards),
    )


async def delete_mandatory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    channel_id = query.data.split("_")[1]
    try:
        salom = await Delete_channels(channel_id)
        await query.edit_message_text("Muvaffaqiyatli o'chirildi")
    except:
        await query.edit_message_text("Qandaydir xatolik ro'y berdi.")
