import re
from telegram import Update
from telegram.ext import ContextTypes
from apps.Bot.BotHandler.catalog import product_detail_handler
from apps.Bot.models.TelegramBot import TelegramUser, Product, Cart, SelectedItem
from asgiref.sync import sync_to_async

async def handle_add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # callback_data dan mahsulot ID sini ajratib olamiz (masalan: add_to_cart_25)
    product_id = int(re.search(r'add_to_cart_(\d+)', query.data).group(1))
    user_id = query.from_user.id

    # 1. Foydalanuvchi va Savatni bazadan olish (aget/aget_or_create PTB uchun)
    user = await TelegramUser.objects.aget(user_id=user_id)
    cart, created = await Cart.objects.aget_or_create(user=user)
    
    # 2. Mahsulotni olish
    try:
        product = await Product.objects.aget(id=product_id)
        
        # 3. Savatga qo'shish (ManyToManyField bo'lgani uchun .aadd ishlatamiz)
        await cart.items.aadd(product)
        
        # 4. Foydalanuvchiga alert chiqarish (ekranda qisqa vaqt ko'rinib yo'qoladi)
        await query.answer(f"✅ {product.name} savatga qo'shildi!", show_alert=False)
        
    except Product.DoesNotExist:
        await query.answer("Xatolik: Mahsulot topilmadi", show_alert=True)
    finally:
        # 5. Mahsulot sahifasini yangilash (soni o'zgarishi uchun)
        await product_detail_handler(update, context)
    




async def handle_view_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id if query else update.effective_user.id
    
    # Xatolikni oldini olish uchun try-except
    from apps.Bot.utils import get_cart_markup
    text, markup = await get_cart_markup(user_id)
    
    try:
        if query:
            await query.answer()
            await query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
        else:
            await context.bot.send_message(
                chat_id=user_id,
                text=text,
                reply_markup=markup,
                parse_mode="HTML"
            )
    except Exception as e:
        # Agar xabar o'zgarmagan bo'lsa xato bermasligi uchun
        if "Message is not modified" not in str(e):
            raise e

async def handle_close_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Savatni yopish (Xabarni o'chirish)"""
    query = update.callback_query
    await query.answer("Savat yopildi")
    await query.message.delete()



async def handle_quantity_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Savatdagi mahsulot sonini bittaga oshiradi yoki kamaytiradi va UI ni yangilaydi"""
    query = update.callback_query
    data = query.data # "inc_25" yoki "dec_25" ko'rinishida keladi
    user_id = query.from_user.id
    
    # Callback datadan amal va mahsulot ID raqamini ajratib olish
    action, product_id = data.split("_")
    product_id = int(product_id)

    # 1. Bazadagi ma'lumotlarni olish
    user = await TelegramUser.objects.aget(user_id=user_id)
    cart, _ = await Cart.objects.aget_or_create(user=user) #
    product = await Product.objects.aget(id=product_id) #

    if action == "inc":
        # Savatga (Cart) va Nabor tanloviga (SelectedItem) qo'shish
        await cart.items.aadd(product) # ManyToManyga qo'shish
        await SelectedItem.objects.acreate(cart=cart, product=product) # Yangi nusxa yaratish
        
    elif action == "dec":
        # SelectedItem modelidan bitta nusxasini o'chirish
        item = await SelectedItem.objects.filter(cart=cart, product=product).afirst()
        if item:
            await item.adelete()
            
        # Agar bu atirdan boshqa nusxa qolmagan bo'lsa, umumiy savatdan (Cart.items) ham o'chiramiz
        still_exists = await SelectedItem.objects.filter(cart=cart, product=product).aexists()
        if not still_exists:
            await cart.items.aremove(product)


    await product_detail_handler(update, context)
    await query.answer("Savat yangilandi")