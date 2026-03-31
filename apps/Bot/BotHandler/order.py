# from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
# from telegram.ext import ContextTypes
# from apps.Bot.models.TelegramBot import TelegramUser, Product, Cart, SelectedItem, Order, OrderItem
# from asgiref.sync import sync_to_async
# from telegram.error import BadRequest
# import re

# # 1. Faqat bazaga saqlash mantiqi (Sinxron qism)
# def _finalize_order_db(user_id):
#     user = TelegramUser.objects.get(user_id=user_id)
#     cart = Cart.objects.get(user=user)
#     # Faqat is_selected=True bo'lgan atirlarni olamiz
#     selected_items = SelectedItem.objects.filter(cart=cart, is_selected=True).select_related('product')
    
#     with transaction.atomic():
#         # Buyurtma yaratish
#         order = Order.objects.create(
#             user=user,
#             package_type=cart.selected_package,
#             phone=user.phone_number,
#             address=user.address
#         )
        
#         items_list_text = ""
#         for s_item in selected_items:
#             OrderItem.objects.create(
#                 order=order,
#                 product=s_item.product,
#                 quantity=1
#             )
#             items_list_text += f"• {s_item.product.brand} - {s_item.product.name}\n"

#         # Savatni va tanlanganlarni tozalash
#         cart.items.clear()
#         SelectedItem.objects.filter(cart=cart).delete()
#         user.state = "START"
#         user.save()
    
#     # Adminga yuborish uchun kerakli ma'lumotlarni qaytaramiz
#     return {
#         "order_id": order.id,
#         "items_text": items_list_text,
#         "user_name": f"{user.first_name} (@{user.username})" if user.username else user.first_name,
#         "phone": user.phone_number,
#         "package": order.get_package_type_display(),
#         "total_price": order.total_price,
#         "address": user.address
#     }

# # 2. Asosiy Handler (Asinxron qism)
# async def finalize_order_and_notify_admin(user_id, context):
#     # Sinxron DB mantiqini asinxron tarzda chaqiramiz
#     data = await sync_to_async(_finalize_order_db)(user_id)
    
#     ADMIN_ID = "-1003510156093"
#     admin_msg = (
#         f"🚨 <b>YANGI BUYURTMA #{data['order_id']}</b>\n"
#         f"👤 Mijoz: {data['user_name']}\n"
#         f"📞 Tel: {data['phone']}\n"
#         f"📦 Nabor: {data['package']}\n"
#         f"💰 Summa: {data['total_price']:,.0f} so'm\n"
#         f"📍 Manzil: {data['address']}\n\n"
#         f"🧪 <b>Atirlar:</b>\n{data['items_text']}"
#     )
    
#     # Asinxron kontekstda await dan foydalanish xavfsiz va to'g'ri
#     await context.bot.send_message(
#         chat_id=ADMIN_ID, 
#         text=admin_msg, 
#         parse_mode="HTML"
#     )

#     return data['order_id']

# async def handle_finalize_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """
#     Foydalanuvchi naborga kerakli miqdordagi atirlarni tanlab bo'lgach, 
#     rasmiylashtirish tugmasini bosganda ishlaydi.
#     """
#     query = update.callback_query
#     user_id = query.from_user.id

#     # 1. Foydalanuvchi holatini (state) WAITING_PHONE ga o'zgartiramiz.
#     # Bu orqali keyingi keladigan xabar telefon raqami ekanligini bilib olamiz.
#     await TelegramUser.objects.filter(user_id=user_id).aupdate(state="WAITING_PHONE")

#     # 2. Telefon raqamini yuborish uchun maxsus klaviatura tayyorlaymiz.
#     # request_contact=True foydalanuvchining o'z raqamini tugma orqali yuborishini ta'minlaydi.
#     contact_keyboard = ReplyKeyboardMarkup([
#         [KeyboardButton("📞 Raqamni yuborish", request_contact=True)]
#     ], resize_keyboard=True, one_time_keyboard=True)
    
#     # 3. Avvalgi inline menyu (atirlar ro'yxati) xabarini o'chiramiz.
#     await query.message.delete()
    
#     # 4. Foydalanuvchiga yangi xabar va tugmani yuboramiz.
#     await context.bot.send_message(
#         chat_id=user_id, 
#         text=(
#             "<b>🎉 Ajoyib! Atirlar tanlandi.</b>\n\n"
#             "Endi buyurtmani rasmiylashtirish uchun pastdagi tugma orqali "
#             "<b>telefon raqamingizni</b> yuboring:"
#         ), 
#         reply_markup=contact_keyboard,
#         parse_mode="HTML"
#     )
    
#     # Telegram aylanib turmasligi uchun callback_query-ga javob beramiz.
#     await query.answer()


# async def handle_remove_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     print("handle_remove_item called")
#     query = update.callback_query
#     # Callback data formatidan ID ni olish
#     match = re.search(r'remove_item_(\d+)', query.data)
#     if not match:
#         await query.answer("Xatolik: ID topilmadi")
#         return

#     item_id = int(match.group(1))
#     user_id = query.from_user.id

#     # 1. Mahsulotni savatdan o'chirish logicasi
#     item = await SelectedItem.objects.filter(id=item_id).afirst()
#     print(f"Trying to remove item with ID: {item_id}, found: {item}")
    
#     if item:
#         product_id = item.product_id
#         cart_id = item.cart_id
#         await item.adelete()
        
#         # Savatda shu mahsulotdan boshqa qolgan-qolmaganini tekshirish
#         cart = await Cart.objects.aget(id=cart_id)
#         exists = await SelectedItem.objects.filter(cart=cart, product_id=product_id).aexists()
        
#         if not exists:
#             product = await Product.objects.aget(id=product_id)
#             await cart.items.aremove(product)
        
#         message_to_user = "Mahsulot o'chirildi"
#     else:
#         message_to_user = "Mahsulot allaqachon o'chirilgan"

#     # 2. Savatning yangi holatini olish
#     from apps.Bot.utils import get_cart_markup
#     text, markup = await get_cart_markup(user_id)

#     # 3. Xabarni tahrirlash (Xatolikni oldini olish bilan)
#     try:
#         await query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
#     except BadRequest as e:
#         if "Message is not modified" in str(e):
#             # Agar xabar bir xil bo'lsa, xatolikni e'tiborsiz qoldiramiz
#             pass
#         else:
#             # Boshqa turdagi BadRequest xatolari bo'lsa, ularni ko'rsatish
#             print(f"Telegram error: {e}")

#     # Tugma ustidagi "aylanayotgan" yuklanishni to'xtatish
#     await query.answer(message_to_user)



# async def handle_set_package(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     query = update.callback_query
#     package_type = query.data.replace("set_package_", "") # '5_set' yoki '10_set'
#     user_id = query.from_user.id
#     target = 5 if package_type == '5_set' else 10

#     user = await TelegramUser.objects.aget(user_id=user_id)
#     cart = await Cart.objects.aget(user=user)
    
#     # 1. Cart modelida nabor turini saqlaymiz
#     await Cart.objects.filter(user=user).aupdate(selected_package=package_type)
    
#     # # 2. Eskidan qolgan tanlovlarni (SelectedItem) tozalaymiz
#     # await SelectedItem.objects.filter(cart=cart).adelete()
    
#     # 3. Savatdagi barcha mahsulotlarni olamiz (SelectedItem orqali jami nusxalarni sanaymiz)
#     # Eslatib o'tamiz: SelectedItem bu yerda savatdagi "slot"lar kabi ishlatiladi
#     # available_items = await SelectedItem.objects.filter(cart=cart).select_related('product').all()
#     pool_count = await SelectedItem.objects.filter(cart=cart).acount()

#     # MANTIQ: Agar savatdagi atirlar soni tanlangan naborga TENG bo'lsa
#     if pool_count == target:
#         # Hamma atirlarni avtomatik "tanlangan" (selected) deb belgilash shart emas, 
#         # chunki ular allaqachon savatda bor. To'g'ridan-to'g'ri telefon so'rashga o'tamiz.
#         await query.answer("Nabor to'liq, rasmiylashtirishga o'tamiz...")
#         return await handle_finalize_checkout(update, context)

#     # MANTIQ: Agar savatda atirlar naboridan KO'P bo'lsa, tanlash sahifasini ochamiz
#     elif pool_count > target:
#         from apps.Bot.utils import get_nabor_selection_markup
#         text, markup = await get_nabor_selection_markup(user_id, package_type)
#         await query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
#         await query.answer("Atirlarni tanlang")
    
#     else:
#         # Bu holat nazariy jihatdan get_cart_markup dagi filtr tufayli sodir bo'lmasligi kerak
#         await query.answer(f"Nabor uchun kamida {target} ta atir bo'lishi kerak!", show_alert=True)

# async def handle_toggle_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     query = update.callback_query
#     product_id = int(re.search(r'toggle_select_(\d+)', query.data).group(1))
#     user_id = query.from_user.id

#     user = await TelegramUser.objects.aget(user_id=user_id)
#     cart = await Cart.objects.aget(user=user)
#     target = 5 if cart.selected_package == '5_set' else 10

#     # 1. Global tanlanganlar sonini tekshirish
#     global_count = await SelectedItem.objects.filter(cart=cart, is_selected=True).acount()
    
#     # 2. Shu mahsulotning holatini tekshirish
#     unselected_item = await SelectedItem.objects.filter(
#         cart=cart, product_id=product_id, is_selected=False
#     ).afirst()

#     if unselected_item:
#         # Hali tanlanmagan nusxasi bor bo'lsa
#         if global_count < target:
#             unselected_item.is_selected = True
#             await unselected_item.asave()
#         else:
#             await query.answer(f"Limitga yetdingiz ({target} ta)!", show_alert=True)
#             return
#     else:
#         # Agar hamma nusxalar tanlangan bo'lsa, ushbu mahsulot bo'yicha tanlovni nolga tushiramiz (Toggle)
#         await SelectedItem.objects.filter(
#             cart=cart, product_id=product_id
#         ).aupdate(is_selected=False)

#     # Markupni yangilash
#     from apps.Bot.utils import get_nabor_selection_markup
#     text, markup = await get_nabor_selection_markup(user_id, cart.selected_package)
    
#     try:
#         await query.edit_message_text(text, reply_markup=markup, parse_mode="HTML")
#     except Exception:
#         pass


# # 4. Yetarli tanlanmaganda ogohlantirish
# async def handle_not_ready(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     await update.callback_query.answer("Nabor to'lishi uchun yana atir tanlang!", show_alert=True)

# from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
# from telegram.ext import ContextTypes
# from django.db import transaction

# async def handle_checkout_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     user_id = update.effective_user.id
#     user = await TelegramUser.objects.aget(user_id=user_id) #

#     # 1-Bosqich: Telefon raqamini qabul qilish
#     if user.state == "WAITING_PHONE":
#         if update.message.contact:
#             user.phone_number = update.message.contact.phone_number #
#         else:
#             # Agar foydalanuvchi raqamni qo'lda yozsa
#             user.phone_number = update.message.text #
        
#         user.state = "WAITING_LOCATION" #
#         await user.asave()
        
#         # Lokatsiya so'rash uchun keyboard
#         location_kb = ReplyKeyboardMarkup([
#             [KeyboardButton("📍 Lokatsiyani yuborish", request_location=True)]
#         ], resize_keyboard=True, one_time_keyboard=True)
        
#         await update.message.reply_text(
#             "Rahmat! Endi mahsulot yetkazib berilishi kerak bo'lgan <b>manzilni</b> yuboring yoki pastdagi tugmani bosing:",
#             reply_markup=location_kb,
#             parse_mode="HTML"
#         )

#     # 2-Bosqich: Manzilni qabul qilish va Buyurtmani yakunlash
#     elif user.state == "WAITING_LOCATION":
#         if update.message.location:
#             loc = update.message.location
#             user.address = f"Google Map: https://www.google.com/maps?q={loc.latitude},{loc.longitude}" #
#         else:
#             user.address = update.message.text #
        
#         await user.asave()
        
#         # Buyurtmani rasmiylashtirish va Adminga yuborish
#         order_id = await finalize_order_and_notify_admin(user_id, context)
        
#         await update.message.reply_text(
#             f"✅ Buyurtmangiz qabul qilindi! \nBuyurtma raqami: <b>#{order_id}</b>\nTez orada operatorlarimiz bog'lanishadi.",
#             reply_markup=ReplyKeyboardRemove(),
#             parse_mode="HTML"
#         )