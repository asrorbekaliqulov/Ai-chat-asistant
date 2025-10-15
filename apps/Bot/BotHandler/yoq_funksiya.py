from telegram import Update
from telegram.ext import ContextTypes

async def yoqfunksiya(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Botga faqat matnli xabar yuboring.")