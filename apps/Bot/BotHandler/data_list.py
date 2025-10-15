from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from ..models.TelegramBot import CompanyData
from ..decorators import admin_required
from asgiref.sync import sync_to_async

ITEMS_PER_PAGE = 10
WAITING_FOR_EDIT = 1


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


# 📋 Ma’lumotlar ro‘yxatini ko‘rsatish
@admin_required
async def show_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Conversation boshlanadi va state qaytariladi — shunda callback query handlerlar ishlaydi.
    """
    await send_page(update, context, page=1)
    return WAITING_FOR_EDIT


async def send_page(update_or_query, context, page: int):
    MAX_MSG_LEN = 3900  # xavfsiz limit (4096 dan kichik)
    ITEMS_PER_PAGE = 10

    all_items = await sync_to_async(lambda: list(CompanyData.objects.all().order_by("id")))()
    if not all_items:
        text = "🕳 Ma’lumotlar topilmadi."
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("🚪 Chiqish", callback_data="exit_admin")]])
        if hasattr(update_or_query, "callback_query") and update_or_query.callback_query:
            query = update_or_query.callback_query
            await query.answer()
            await query.edit_message_text(text=text, reply_markup=markup, parse_mode="HTML")
        else:
            await update_or_query.message.reply_text(text=text, reply_markup=markup, parse_mode="HTML")
        return

    # 🔹 Sahifalarni belgilash — uzunlikka qarab dinamik bo‘linadi
    pages = []
    current_page = []
    current_length = 0

    for i, item in enumerate(all_items, start=1):
        entry = f"<b>{i}.</b> {item.content.strip()}\n\n"
        entry_len = len(entry)

        # Agar 10 taga yetgan bo‘lsa yoki matn sig‘masa, yangi sahifa boshlaymiz
        if len(current_page) >= ITEMS_PER_PAGE or current_length + entry_len > MAX_MSG_LEN:
            pages.append(current_page)
            current_page = []
            current_length = 0

        current_page.append(entry)
        current_length += entry_len

    if current_page:
        pages.append(current_page)

    total_pages = len(pages)
    page = max(1, min(page, total_pages))  # Sahifa chegaradan chiqmasin

    # 🔸 Tanlangan sahifa uchun matn
    text = "📋 <b>Ma’lumotlar ro‘yxati</b>\n\n" + "".join(pages[page - 1])

    # 🔹 Inline tugmalar (tahrirlash uchun)
    buttons = []
    row = []
    start_index = sum(len(p) for p in pages[: page - 1])
    current_items = all_items[start_index : start_index + len(pages[page - 1])]

    for idx, item in enumerate(current_items, start=start_index + 1):
        row.append(InlineKeyboardButton(f"{idx} ✏️", callback_data=f"edit_{item.id}"))
        if len(row) == 5:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    # 🔹 Navigatsiya
    prev_button = InlineKeyboardButton(
        "⬅️ ❌" if page <= 1 else "⬅️",
        callback_data=f"page_{page-1}" if page > 1 else "none",
    )
    exit_button = InlineKeyboardButton("🚪 Chiqish", callback_data="exit_admin")
    next_button = InlineKeyboardButton(
        "➡️ ❌" if page >= total_pages else "➡️",
        callback_data=f"page_{page+1}" if page < total_pages else "none",
    )
    buttons.append([prev_button, exit_button, next_button])
    markup = InlineKeyboardMarkup(buttons)

    # 🔹 Xabarni yangilash yoki yuborish
    if hasattr(update_or_query, "callback_query") and update_or_query.callback_query:
        query = update_or_query.callback_query
        await query.answer()
        await query.edit_message_text(text=text, reply_markup=markup, parse_mode="HTML")
    elif hasattr(update_or_query, "message") and update_or_query.message:
        await update_or_query.message.reply_text(text=text, reply_markup=markup, parse_mode="HTML")
    else:
        chat_id = update_or_query.effective_chat.id
        await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=markup, parse_mode="HTML")

# 📄 Sahifani o‘zgartirish — CallbackQuery orqali
async def paginate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.data == "none":
        await query.answer("⛔ Bu sahifaga o'tib bo‘lmaydi", show_alert=True)
        return WAITING_FOR_EDIT

    # data shakli: "page_2"
    try:
        page = int(query.data.split("_")[1])
    except Exception:
        await query.answer("⛔ Noto'g'ri so'rov", show_alert=True)
        return WAITING_FOR_EDIT

    await send_page(update, context, page)
    return WAITING_FOR_EDIT


# ✏️ (Tahrirlash jarayoni boshlanishi)
async def start_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    item_id = int(query.data.split("_")[1])
    context.user_data["edit_id"] = item_id

    item = await sync_to_async(CompanyData.objects.get)(id=item_id)
    await query.edit_message_text(
        f"✏️ <b>Hozirgi matn:</b>\n<code>{item.content}</code>\n\nYangi matnni yuboring:",
        parse_mode="HTML"
    )
    return WAITING_FOR_EDIT


# 💾 Yangi matnni qabul qilib, saqlash
async def save_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_text = update.message.text.strip()
    item_id = context.user_data.get("edit_id")

    if not item_id or not new_text:
        await update.message.reply_text("❌ Noto‘g‘ri amal.")
        return ConversationHandler.END

    item = await sync_to_async(CompanyData.objects.get)(id=item_id)
    item.content = new_text
    await sync_to_async(item.save)()

    # Tahrirdan so‘ng yangilangan ro‘yxatni 1-sahifadan ko‘rsatamiz
    await send_page(update, context, page=1)
    return WAITING_FOR_EDIT


# 🚪 Admin panelga qaytish (chiqish)
async def go_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🔙 Admin panelga qaytdingiz.")
    await query.edit_message_text("🏠 Admin panel", parse_mode="HTML", reply_markup=Admin_keyboard)
    return ConversationHandler.END


# noop — faol bo'lmagan prev/next tugmalar uchun (oddiy javob)
async def noop_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("⛔ Bu tugma faol emas", show_alert=False)
    return WAITING_FOR_EDIT


# 🔧 Handler’ni qaytarish
show_data_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(show_data, pattern="^data_list$")],
    states={
        WAITING_FOR_EDIT: [
            # matn kiritilganda tahrirni saqlash
            MessageHandler(filters.TEXT & ~filters.COMMAND, save_edit),

            # callback query handlerlar — pagination, edit, exit, va noop
            CallbackQueryHandler(paginate, pattern=r"^page_\d+$"),
            CallbackQueryHandler(start_edit, pattern=r"^edit_\d+$"),
            CallbackQueryHandler(go_to_admin, pattern=r"^exit_admin$"),
            CallbackQueryHandler(noop_handler, pattern=r"^none$"),
        ],
    },
    fallbacks=[],
)
