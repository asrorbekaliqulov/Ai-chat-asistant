from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from ..decorators import typing_action

# Admin ID Aromazona.uz buyurtmalarini qabul qilish uchun
ADMIN_ID = 6194484795 

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

# Katalog markup funksiyasini import qilamiz
from .catalog import get_catalog_markup 
from ..decorators import typing_action

ADMIN_ID = 6194484795 

@typing_action
async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    if not user_text: 
        return
    
    user_id = update.effective_user.id

    try:
        from ..utils import (
            generate_ai_response, 
            get_chat_history_from_db, 
            save_message_to_db
        )
        # 1. Foydalanuvchi xabarini bazaga saqlash
        await save_message_to_db(user_id, role="user", content=user_text)

        # 2. Bazadan chat tarixini yuklash
        chat_history = await get_chat_history_from_db(user_id, limit=15)

        # 3. AI dan javob olish
        ai_response = await generate_ai_response(user_text, user_id, chat_history)

        # 4. AI javob turiga qarab harakat qilish
        
        # --- ODDIIY MATN ---
        if ai_response["type"] == "text":
            resp_text = ai_response["text"]
            await update.message.reply_text(text=resp_text, parse_mode=ParseMode.HTML)
            await save_message_to_db(user_id, role="model", content=resp_text)

        # --- KATALOG CHAQIRILGANDA ---
        elif ai_response["type"] == "catalog":
            # AI dan kelgan sahifa raqamini olamiz (agar bo'lmasa 1-sahifa)
            page_num = ai_response.get("page", 1)
            
            # Katalog matni va tugmalarini generatsiya qilamiz
            text, markup = await get_catalog_markup(page=page_num)
            
            await update.message.reply_text(
                text=text,
                reply_markup=markup,
                parse_mode=ParseMode.HTML
            )
            # Tarixga katalog ko'rsatilganini qayd etamiz
            await save_message_to_db(user_id, role="model", content="Katalog sahifasi ko'rsatildi.")

        # --- BUYURTMA YAKUNLANGANDA ---
        elif ai_response["type"] == "order_completed":
            await update.message.reply_text(
                text=ai_response["user_msg"],
                parse_mode=ParseMode.HTML
            )
            
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=ai_response["admin_msg"],
                parse_mode=ParseMode.HTML
            )
            await save_message_to_db(user_id, role="model", content="Buyurtma qabul qilindi.")

    except Exception as e:
        print(f"Chatbot Handler Error: {e}")
        await update.message.reply_text(
            "Kechirasiz, tizimda nosozlik yuz berdi. Iltimos, qayta urinib ko'ring."
        )