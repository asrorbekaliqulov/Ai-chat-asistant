from telegram import Update
from telegram.ext import CallbackContext
from ..models.TelegramBot import TelegramUser
from ..decorators import admin_required
import os
from dotenv import load_dotenv

load_dotenv()

# Bot Token
TOKEN = os.getenv("BOT_TOKEN")


async def today_new_users():
    today_new_users = await TelegramUser.get_today_new_users()
    return len(today_new_users)


@admin_required
async def bot_stats(update: Update, context: CallbackContext):
    msg = update.callback_query
    await msg.answer("Malumotlar yuklanmoqda...")
    bot_token = TOKEN
    blocked_count = await TelegramUser.find_inactive_users(bot_token)
    bot = await context.bot.get_me()
    total_users = await TelegramUser.get_total_users()
    active_users_count = total_users - blocked_count
    admin_users_count = await TelegramUser.count_admin_users()
    new_users_count = await today_new_users()

    await msg.edit_message_text(
        text=f"""
<b>@{bot.username} ning statistikasi:

👥 <i>Bot foydalanuvchilar soni:</i> {total_users} ta
——————————
🆕 <i>Yangi qo'shilgan foydalanuvchilar soni:</i> {new_users_count if new_users_count else 0} ta
——————————
👮‍♂️ <i>Adminlar soni:</i> {admin_users_count} ta
——————————
🔥 <i>Faol foydalanuvchilar:</i> {active_users_count} ta
——————————
🚫 <i>Nofaol foydalanuvchilar:</i> {blocked_count} ta
</b>""",
        parse_mode="HTML",
    )
