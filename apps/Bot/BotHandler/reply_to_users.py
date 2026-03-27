from telegram import Update
from telegram.constants import ChatMemberStatus, ChatType
from telegram.ext import ContextTypes
from telegram.error import BadRequest

async def reply_to_users_only(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1. Xabar ob'ekti va chat mavjudligini tekshiramiz
    if not update.message or not update.effective_chat or not update.effective_user:
        return

    # 2. Faqat guruhlarda ishlashi uchun filtr
    if update.effective_chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    try:
        # 3. Foydalanuvchi statusini tekshirish
        member = await context.bot.get_chat_member(chat_id, user_id)
        
        # Admin va Creator statuslarini tekshirish
        is_admin_or_owner = member.status in [
            ChatMemberStatus.ADMINISTRATOR, 
            ChatMemberStatus.OWNER
        ]

        # 4. Agar foydalanuvchi oddiy user bo'lsa
        if not is_admin_or_owner:
            user_name = update.effective_user.first_name
            response_text = f"Hurmatli {user_name}, savolingiz qabul qilindi! Adminlar tez orada javob berishadi."
            
            # Xabarga reply (javob) tarzida yuborish
            await update.message.reply_text(response_text)

    except BadRequest as e:
        # Agar bot guruhda admin bo'lmasa yoki Peer_id_invalid xatosi chiqsa
        print(f"Xatolik yuz berdi: {e.message}")
    except Exception as e:
        print(f"Kutilmagan xato: {e}")