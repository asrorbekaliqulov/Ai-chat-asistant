from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from ..decorators import admin_required


@admin_required
async def DownlBD(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = open("db.sqlite3", "rb")
    await context.bot.send_document(update.effective_user.id, document=file)
    if update.callback_query:
        update.callback_query.answer("Yuklandi!")
    return ConversationHandler.END
