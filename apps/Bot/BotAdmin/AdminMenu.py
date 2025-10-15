from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import CallbackContext, ConversationHandler
from ..decorators import admin_required


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


@admin_required
async def admin_menyu(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    await context.bot.send_message(
        chat_id=user_id,
        text="<b>Salom Admin\nNima qilamiz bugun</b>",
        parse_mode="HTML",
        reply_markup=Admin_keyboard,
    )
    return ConversationHandler.END
