from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from ..utils import generate_ai_response
from ..decorators import typing_action


# 💬 Foydalanuvchi xabarini qabul qilish va AI javobini yuborish
@typing_action
async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    user_id = update.effective_user.id

    # AI dan javob olish
    ai_reply = await generate_ai_response(user_text, user_id)

    # # Mavzudan chet yoki javob yo‘q bo‘lsa
    # if "Menda bu savolga oid ma’lumot mavjud emas" in ai_reply or len(ai_reply) < 5:
    #     await update.message.reply_text(
    #         "😔 Savolingizni anglolmadim.\n"
    #         "👉 Quyidagi tugma orqali administrator bilan bog‘laning.",
    #         reply_markup=InlineKeyboardMarkup(
    #             [[InlineKeyboardButton("📞 Admin bilan bog‘lanish", url="https://t.me/asrorbek_10_02")]]
    #         ),
    #     )
    #     return

    # AI javobini yuborish
    await update.message.reply_text(
        f"🤖 <b>AI javobi:</b>\n{ai_reply}",
        parse_mode="HTML",
    )
