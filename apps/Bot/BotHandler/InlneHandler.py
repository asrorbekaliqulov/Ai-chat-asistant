from telegram import Update
from telegram.ext import ContextTypes


async def InlineButton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("Coming soon")
