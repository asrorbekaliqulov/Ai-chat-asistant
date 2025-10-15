from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CallbackContext,
    ConversationHandler,
    ContextTypes,
    CallbackQueryHandler,
)
from ..models.TelegramBot import TelegramUser  # Django modelingizni import qiling
from ..decorators import admin_required
from django.db.models import QuerySet
from asgiref.sync import sync_to_async

from warnings import filterwarnings
from telegram.warnings import PTBUserWarning

filterwarnings(
    action="ignore", message=r".*CallbackQueryHandler", category=PTBUserWarning
)


# Conversation bosqichlari
SELECT_ADMIN, CONFIRM_REMOVE = range(2)


# Sync function to get admins
@sync_to_async
def get_admins():
    return list(TelegramUser.objects.filter(is_admin=True))


# Sync function to check if admins exist
@sync_to_async
def admins_exist() -> bool:
    return TelegramUser.objects.filter(is_admin=True).exists()


@admin_required
async def start_remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Adminlikdan o'chirish jarayonini boshlaydi.
    """
    msg = update.callback_query
    # Get admins list asynchronously
    admins = await get_admins()

    if not await admins_exist():
        await update.message.reply_text("Hozircha hech qanday admin yo'q.")
        return ConversationHandler.END

    # Inline keyboard creation
    keyboard = [
        [
            InlineKeyboardButton(
                (
                    f"{admin.first_name} @{admin.username}"
                    if admin.username
                    else admin.first_name
                ),
                callback_data=f"remove_admin_{admin.user_id}",
            )
        ]
        for admin in admins
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await msg.edit_message_text(
        "Iltimos, adminlikdan o'chirmoqchi bo'lgan foydalanuvchini tanlang:",
        reply_markup=reply_markup,
    )
    return SELECT_ADMIN


@admin_required
async def select_admin(update: Update, context: CallbackContext) -> int:
    """
    Tanlangan adminni qayta ishlash.
    """
    query = update.callback_query
    await query.answer()
    userID = update.effective_user.id
    # Admin user_id ni olish
    user_id = int(query.data.split("_")[-1])
    context.user_data["remove_user_id"] = user_id

    # Sync function to get admins
    @sync_to_async
    def get_user_data(user_id):
        return TelegramUser.objects.get(user_id=user_id)

    if userID == user_id:
        await context.bot.send_message(
            chat_id=userID, text="Siz o'zingizni adminlikdan o'chira olmaysiz!"
        )
        return SELECT_ADMIN
    user = await get_user_data(user_id)

    await query.edit_message_text(
        f"Siz {user.first_name} @{user.username} (ID: {user_id}) ni adminlikdan o'chirmoqchisiz. Tasdiqlaysizmi? (Ha/Yo'q)",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Ha", callback_data="confirm_remove"),
                    InlineKeyboardButton("Yo'q", callback_data="cancel_remove"),
                ]
            ]
        ),
    )
    return CONFIRM_REMOVE


@admin_required
async def confirm_remove(update: Update, context: CallbackContext) -> int:
    """
    Adminni o'chirishni tasdiqlash.
    """
    query = update.callback_query
    await query.answer()

    user_id = context.user_data.get("remove_user_id")
    user = await TelegramUser.remove_admin(user_id=user_id)

    if user:
        await query.edit_message_text(
            f"{user.first_name} @{user.username} adminlikdan muvaffaqiyatli o'chirildi."
        )

        # Foydalanuvchiga xabar yuborish
        try:
            await context.bot.send_message(
                chat_id=user.user_id, text="Siz adminlikdan o'chirildingiz."
            )
        except Exception as e:
            print(f"Xabar yuborishda xatolik yuz berdi: {e}")
    else:
        await query.edit_message_text("Bunday foydalanuvchi topilmadi yoki admin emas.")

    return ConversationHandler.END


async def cancel_remove(update: Update, context: CallbackContext) -> int:
    """
    Jarayonni bekor qilish.
    """
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Adminlikdan o'chirish bekor qilindi.")
    return ConversationHandler.END


# ConversationHandler ni sozlash
remove_admin_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_remove_admin, pattern=r"^delete_admin$")],
    states={
        SELECT_ADMIN: [CallbackQueryHandler(select_admin, pattern="^remove_admin_")],
        CONFIRM_REMOVE: [
            CallbackQueryHandler(confirm_remove, pattern="^confirm_remove$"),
            CallbackQueryHandler(cancel_remove, pattern="^cancel_remove$"),
        ],
    },
    fallbacks=[],
)
