from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
)
from ..models.TelegramBot import CompanyData
from asgiref.sync import sync_to_async

ITEMS_PER_PAGE = 10


# 📋 Ma’lumotlar ro‘yxatini ko‘rsatish
async def show_delete_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_delete_page(update, context, page=1)
    return 1  # Holatni qaytaramiz, shunda state ichida qoladi


# 🔁 Ma’lumotlar sahifasini yuborish
async def send_delete_page(update_or_query, context, page: int):
    data_count = await sync_to_async(CompanyData.objects.count)()
    total_pages = (data_count - 1) // ITEMS_PER_PAGE + 1 if data_count else 1

    start = (page - 1) * ITEMS_PER_PAGE
    end = start + ITEMS_PER_PAGE
    items = await sync_to_async(
        lambda: list(CompanyData.objects.all().order_by("id")[start:end])
    )()

    # 🧾 Matn tayyorlash
    if not items:
        text = "🕳 Ma’lumotlar topilmadi."
    else:
        text = "🗑 <b>O‘chirish uchun ma’lumotlar ro‘yxati</b>\n\n"
        for i, item in enumerate(items, start=start + 1):
            text += f"<b>{i}.</b> {item.content}\n"

    # 🔘 Inline tugmalar (10 tadan 2 qator)
    buttons = []
    row = []
    for i, item in enumerate(items, start=start + 1):
        row.append(InlineKeyboardButton(f"{i} 🗑", callback_data=f"del_{item.id}"))
        if len(row) == 5:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    # 📱 Navigatsion tugmalar (3 ta)
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("⬅️", callback_data=f"dpage_{page-1}"))
    else:
        nav_row.append(InlineKeyboardButton("⬅️❌", callback_data="noop"))

    nav_row.append(InlineKeyboardButton("🚪 Chiqish", callback_data="exit_delete"))

    if page < total_pages:
        nav_row.append(InlineKeyboardButton("➡️", callback_data=f"dpage_{page+1}"))
    else:
        nav_row.append(InlineKeyboardButton("➡️❌", callback_data="noop"))

    buttons.append(nav_row)
    markup = InlineKeyboardMarkup(buttons)

    # 🔄 Xabarni yangilash yoki yuborish
    if hasattr(update_or_query, "callback_query"):
        query = update_or_query.callback_query
        # ✅ Eski querylardan xato chiqmasligi uchun xavfsiz `answer()`
        try:
            await query.answer()
        except Exception:
            pass

        # 🔁 Xabarni tahrirlash
        try:
            await query.edit_message_text(
                text=text, reply_markup=markup, parse_mode="HTML"
            )
        except Exception:
            # Agar xabar tahrirlanmasa (masalan, "message is not modified" bo‘lsa)
            await query.message.edit_text(
                text=text, reply_markup=markup, parse_mode="HTML"
            )
    else:
        await update_or_query.message.reply_text(
            text=text, reply_markup=markup, parse_mode="HTML"
        )

# 📄 Sahifani o‘zgartirish
async def paginate_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    page = int(query.data.split("_")[1])
    await send_delete_page(update, context, page)
    return 1  # State ichida qoladi


# 🗑 Ma’lumotni o‘chirish
async def delete_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    item_id = int(query.data.split("_")[1])

    await sync_to_async(CompanyData.objects.filter(id=item_id).delete)()
    await query.answer("🗑 O‘chirildi!", show_alert=False)

    await send_delete_page(update, context, page=1)
    return 1

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

# 🚪 Chiqish tugmasi
async def exit_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🔙 Admin panelga qaytdingiz.", reply_markup=Admin_keyboard)
    return ConversationHandler.END


# 🔧 Handler’ni qaytarish
delete_data_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(show_delete_list, pattern="^delete_data$")],
    states={
        1: [
            CallbackQueryHandler(paginate_delete, pattern=r"^dpage_\d+$"),
            CallbackQueryHandler(delete_item, pattern=r"^del_\d+$"),
            CallbackQueryHandler(lambda u, c: u.callback_query.answer(), pattern="^noop$"),
        ],
    },
    fallbacks=[CallbackQueryHandler(exit_delete, pattern="^exit_delete$")],
)
