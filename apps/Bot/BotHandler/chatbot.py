import os
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode, ChatType

from ..decorators import typing_action
from apps.Bot.models.TelegramBot import TelegramUser

@typing_action
async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_chat or update.effective_chat.type != ChatType.PRIVATE:
        return
    if not update.message or not update.message.text:
        return
    
    user_text = update.message.text
    user_id = update.effective_user.id

    try:
        from ..utils import generate_ai_response, get_chat_history_from_db, save_message_to_db
        from ..utils_admin import generate_admin_ai_response

        # 1. ADMIN TEKSHIRUVI
        is_admin = await TelegramUser.objects.filter(user_id=user_id, is_admin=True).aexists()
        
        if is_admin:
            await save_message_to_db(user_id, role="admin", content=user_text)
            admin_ai_resp = await generate_admin_ai_response(user_text)
            
            if admin_ai_resp:
                try:
                    await update.message.reply_text(
                        text=f"👑 <b>Admin Analitika:</b>\n\n{admin_ai_resp}", 
                        parse_mode=ParseMode.HTML
                    )
                except Exception:
                    # Agar HTML parslashda xato bersa, oddiy matn qilib yuboramiz
                    await update.message.reply_text(
                        text=f"👑 Admin Analitika (Plain Text):\n\n{admin_ai_resp}"
                    )
                await save_message_to_db(user_id, role="model", content=admin_ai_resp)
            return

        # 2. ODDIY FOYDALANUVCHI
        await save_message_to_db(user_id, role="user", content=user_text)
        chat_history = await get_chat_history_from_db(user_id, limit=15)
        ai_response = await generate_ai_response(user_text, user_id, chat_history)

        if ai_response.get("type") == "text":
            resp_text = ai_response["text"]
            await update.message.reply_text(text=resp_text, parse_mode=ParseMode.HTML)
            await save_message_to_db(user_id, role="model", content=resp_text)

    except Exception as e:
        print(f"Chatbot Handler Error: {e}")
        await update.message.reply_text("Tizimda nosozlik yuz berdi.")