import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, CallbackContext
import os
from dotenv import load_dotenv


load_dotenv()


# Bot Token
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("BOT_TOKEN topilmadi! .env faylini tekshiring.")


async def start(update: Update, context: CallbackContext):
    """Botga /start komandasi kelganda ishlaydi"""
    await update.message.reply_text("Salom! Django bilan birga ishlayman!")


def main():
    """Asinxron botni ishga tushiradi"""
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))

    print("Bot ishga tushdi...")
    app.run_polling()
