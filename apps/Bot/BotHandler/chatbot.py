from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode, ChatType
from .catalog import get_catalog_markup 
from ..decorators import typing_action
from apps.Bot.models.TelegramBot import TelegramUser, ChatMessage

# Admin ID Aromazona.uz buyurtmalarini qabul qilish uchun
ADMIN_ID = 6194484795 
import os
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode, ChatType

@typing_action
async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1. Shaxsiy chat tekshiruvi
    if not update.effective_chat or update.effective_chat.type != ChatType.PRIVATE:
        return

    if not update.message or not update.message.text:
        return
    
    user_text = update.message.text
    user_id = update.effective_user.id

    try:
        from ..utils import generate_ai_response, get_chat_history_from_db, save_message_to_db
        from ..utils_admin import generate_admin_ai_response

        # 2. ADMINLAR UCHUN MAXSUS MANTIQ
        is_admin = await TelegramUser.objects.filter(user_id=user_id, is_admin=True).aexists()
        
        if is_admin:
            admin_history = await get_chat_history_from_db(user_id, limit=10)
            
            # PandasAI natijani (matn yoki rasm yo'li) qaytaradi
            admin_ai_resp = await generate_admin_ai_response(user_text, user_id, admin_history)
            
            # --- GRAFIKNI TEKSHIRISH VA YUBORISH ---
            # PandasAI odatda rasm yo'lini qaytarsa, u string ko'rinishida bo'ladi
            if isinstance(admin_ai_resp, str) and (admin_ai_resp.endswith('.png') or 'exports/charts' in admin_ai_resp):
                if os.path.exists(admin_ai_resp):
                    await update.message.reply_photo(
                        photo=open(admin_ai_resp, 'rb'),
                        caption="📊 <b>Tahlil natijasi grafik ko'rinishida:</b>",
                        parse_mode=ParseMode.HTML
                    )
                    # Rasmni yuborgach, serverda joy egallamasligi uchun o'chirib yuborish mumkin (ixtiyoriy)
                    # os.remove(admin_ai_resp) 
                else:
                    await update.message.reply_text("Grafik yaratildi, lekin fayl topilmadi.")
            else:
                # Agar natija shunchaki matn bo'lsa
                await update.message.reply_text(
                    text=f"👑 <b>AI Javobi:</b>\n\n{admin_ai_resp}", 
                    parse_mode=ParseMode.HTML
                )
            
            await save_message_to_db(user_id, role="admin", content=user_text)
            return 

        # 3. ODDIY USERLAR UCHUN MANTIQ (O'zgarishsiz qoladi)
        await save_message_to_db(user_id, role="user", content=user_text)
        chat_history = await get_chat_history_from_db(user_id, limit=15)
        ai_response = await generate_ai_response(user_text, user_id, chat_history)

        if ai_response["type"] == "text":
            resp_text = ai_response["text"]
            await update.message.reply_text(text=resp_text, parse_mode=ParseMode.HTML)
            await save_message_to_db(user_id, role="model", content=resp_text)

        elif ai_response["type"] == "catalog":
            page_num = ai_response.get("page", 1)
            text, markup = await get_catalog_markup(page=page_num)
            await update.message.reply_text(text=text, reply_markup=markup, parse_mode=ParseMode.HTML)
            await save_message_to_db(user_id, role="model", content="Katalog ko'rsatildi.")

        elif ai_response["type"] == "order_completed":
            await update.message.reply_text(text=ai_response["user_msg"], parse_mode=ParseMode.HTML)
            await context.bot.send_message(chat_id=ADMIN_ID, text=ai_response["admin_msg"], parse_mode=ParseMode.HTML)
            await save_message_to_db(user_id, role="model", content="Buyurtma qabul qilindi.")

    except Exception as e:
        print(f"Chatbot Handler Error: {e}")
        if update.message:
            await update.message.reply_text("Tizimda kichik nosozlik yuz berdi.")