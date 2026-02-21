from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler
from django.db.models import Sum
from apps.Bot.models.TelegramBot import Product, TelegramUser, Cart, SelectedItem
from asgiref.sync import sync_to_async
from ..decorators import typing_action


@sync_to_async
def get_paginated_products(page=1, limit=10):
    """Sotilish soni bo'yicha saralangan atirlarni pagination bilan olish"""
    offset = (page - 1) * limit
    # Sotilish soni (total_sold) bo'yicha kamayish tartibida saralash
    products = Product.objects.filter(is_active=True).annotate(
        total_sold=Sum('sales__quantity')
    ).order_by('-total_sold', 'brand')[offset:offset + limit]
    
    total_count = Product.objects.filter(is_active=True).count()
    return list(products), total_count

@sync_to_async
def get_product_by_id(product_id):
    """ID bo'yicha atir ma'lumotlarini olish"""
    return Product.objects.filter(id=product_id).first()

# Katalog sahifasini generatsiya qilish
async def get_catalog_markup(page=1):
    products, total_count = await get_paginated_products(page=page)
    
    text = "<b>📚 Aromazona Katalog</b>\n\n"
    keyboard = []
    
    # 1. Atirlar ro'yxati matni va raqamli tugmalar (2 qatorda 5 tadan)
    row1, row2 = [], []
    for i, product in enumerate(products, 1):
        global_index = (page - 1) * 10 + i
        text += f"{global_index}. <b>{product.name}</b> - {product.brand}\n"
        
        button = InlineKeyboardButton(f"{global_index}", callback_data=f"prod_{product.id}")
        if i <= 5: row1.append(button)
        else: row2.append(button)
    
    keyboard.append(row1)
    keyboard.append(row2)
    
    # 2. Boshqaruv tugmalari (Oldinga, Chiqish, Keyingi)
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ Oldingi", callback_data=f"cat_page_{page-1}", api_kwargs={"style": "primary"}))
    else:
        nav_row.append(InlineKeyboardButton("❌", callback_data="none", api_kwargs={"style": "danger"})) # Bo'sh joy uchun
        
    nav_row.append(InlineKeyboardButton("🏠 Chiqish", callback_data="close_catalog"))
    
    if (page * 10) < total_count:
        nav_row.append(InlineKeyboardButton("Keyingi ➡️", callback_data=f"cat_page_{page+1}", api_kwargs={"style": "primary"}))
    
    keyboard.append(nav_row)
    return text, InlineKeyboardMarkup(keyboard)

from telegram.constants import ParseMode

# 1. Katalog sahifalari uchun (Pagination)
async def catalog_pagination_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Callback datadan sahifa raqamini ajratib olish
    page = int(query.data.split("_")[-1])
    
    text, markup = await get_catalog_markup(page=page)
    await query.edit_message_text(text=text, reply_markup=markup, parse_mode=ParseMode.HTML)

from telegram.error import BadRequest

@typing_action
async def product_detail_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    product_id = int(query.data.split("_")[-1])
    
    # 1. Ma'lumotlarni olish
    product = await Product.objects.aget(id=product_id)
    user = await TelegramUser.objects.aget(user_id=user_id)
    cart, _ = await Cart.objects.aget_or_create(user=user)
    
    quantity = await SelectedItem.objects.filter(cart=cart, product=product).acount()

    # 2. Xabar matni va tugmalarini tayyorlash
    detail_text = (
        f"<b>✨ {product.brand} - {product.name}</b>\n\n"
        f"👤 <b>Jins:</b> {product.get_gender_display()}\n"
        f"📝 <b>Tavsif:</b> {product.description}\n"
    )

    keyboard = []
    if quantity > 0:
        keyboard.append([
            InlineKeyboardButton("➖", callback_data=f"dec_{product.id}", api_kwargs={"style": "danger"}),
            InlineKeyboardButton(f"📦 {quantity} ta", callback_data="none"),
            InlineKeyboardButton("➕", callback_data=f"inc_{product.id}", api_kwargs={"style": "success"})
        ])
    else:
        keyboard.append([
            InlineKeyboardButton("🛒 Savatga qo'shish", callback_data=f"inc_{product.id}", api_kwargs={"style": "success"})
        ])

    keyboard.append([
        InlineKeyboardButton("⬅️ Orqaga", callback_data="cat_page_1", api_kwargs={"style": "primary"}),
        InlineKeyboardButton("🔝 Bosh menyu", callback_data="close_catalog", api_kwargs={"style": "primary"})
    ])

    # 3. Xatolikdan himoyalangan tahrirlash
    try:
        await query.edit_message_text(
            text=detail_text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML
        )
    except BadRequest as e:
        if "Message is not modified" in str(e):
            # Agar xabar o'zgarmagan bo'lsa, xatoni shunchaki e'tiborsiz qoldiramiz
            pass
        else:
            # Boshqa turdagi BadRequest xatolarini qayta yuboramiz
            raise e
# 3. Katalogni yopish uchun
async def close_catalog_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.delete_message()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="<b>Aromazona</b> premium xizmatidan foydalanganingiz uchun rahmat! 😊\nSavol bormi? Mendan so'rashingiz mumkin!",
        parse_mode=ParseMode.HTML
    )

@typing_action
async def handle_text_catalog(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer("Katalog ochilmoqda...")
        await update.callback_query.delete_message()
    text, markup = await get_catalog_markup(page=1)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=text, reply_markup=markup, parse_mode="HTML")
    return ConversationHandler.END