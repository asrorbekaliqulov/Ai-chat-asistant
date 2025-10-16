
from ..BotCommands import start, set_user_type, user_type
from ..BotAdmin import (
    admin_menyu,
    add_admin_handler,
    the_first_admin,
    remove_admin_handler,
    AdminList,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
from ..BotHandler import (
    send_msg_handler,
    bot_stats,
    InlineButton,
    add_data_handler,
    show_data_handler,
    delete_data_handler,
    handle_user_message,
    yoqfunksiya,
)

from ..BotCommands.DownDB import DownlBD
import os
from dotenv import load_dotenv

load_dotenv()

# Bot Token
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("BOT_TOKEN topilmadi! .env faylini tekshiring.")


def main():
    # Application yaratishda persistence va job_queue parametrlarini qo'shamiz
    app = Application.builder().token(TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("DownDataBaza", DownlBD))
    app.add_handler(CommandHandler("admin_panel", admin_menyu))
    app.add_handler(CommandHandler("kjiaufuyerfgvu", the_first_admin))
    app.add_handler(CommandHandler("set_role", user_type))


    # Conversation handlers
    app.add_handler(send_msg_handler)
    app.add_handler(add_admin_handler)
    app.add_handler(remove_admin_handler)
    app.add_handler(add_data_handler)
    app.add_handler(show_data_handler)
    app.add_handler(delete_data_handler)


    # Inline hanlder
    app.add_handler(CallbackQueryHandler(start, pattern=r"^Main_Menu$"))
    app.add_handler(CallbackQueryHandler(bot_stats, pattern=r"^botstats$"))
    app.add_handler(CallbackQueryHandler(start, pattern=r"^cancel$"))
    app.add_handler(CallbackQueryHandler(start, pattern=r"^Check_mandatory_channel$"))
    app.add_handler(CallbackQueryHandler(AdminList, pattern=r"^admin_list$"))
    app.add_handler(CallbackQueryHandler(admin_menyu, pattern="^exit_admin$"))
    app.add_handler(CallbackQueryHandler(start, pattern=r"^BackToMainMenu$"))
    app.add_handler(CallbackQueryHandler(set_user_type, pattern=r"^yolovchi|haydovchi$"))
 

    # app.add_handler(CallbackQueryHandler(EarnMoneyMenu, pattern=r"^earn_money$"))
    app.add_handler(CallbackQueryHandler(InlineButton))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_message))

    app.add_handler(MessageHandler(~filters.COMMAND & ~filters.TEXT, yoqfunksiya))

    # Bot start
    print("The bot is running!!!")
    app.run_polling()
