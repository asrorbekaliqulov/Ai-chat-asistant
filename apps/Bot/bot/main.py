
from apps.Bot.BotHandler.analytics_handler import analytics_callback_handler, analytics_dashboard
from apps.Bot.BotHandler.order import handle_checkout_messages

from ..BotCommands import start, set_user_type
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
    handle_text_catalog,
    catalog_pagination_handler,
    product_detail_handler,
    close_catalog_handler,
    handle_remove_item,
    handle_set_package,
    handle_toggle_select,
    handle_not_ready,
    handle_finalize_checkout,
    handle_add_to_cart,
    handle_view_cart,
    handle_quantity_change,
    product_ai_handler,
    ai_group_assistant,
    sale_conv,
    search_handler,
    stock_ai_conv,
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
    # app.add_handler(CommandHandler("set_role", user_type))


    # Conversation handlers
    app.add_handler(send_msg_handler)
    app.add_handler(add_admin_handler)
    app.add_handler(remove_admin_handler)
    app.add_handler(add_data_handler)
    app.add_handler(show_data_handler)
    app.add_handler(delete_data_handler)
    app.add_handler(product_ai_handler)
    app.add_handler(sale_conv)
    app.add_handler(search_handler)
    app.add_handler(stock_ai_conv)


    # Inline hanlder
    
    app.add_handler(CallbackQueryHandler(analytics_callback_handler, pattern="^(days:|low_stock_list|main_stats)"))
    app.add_handler(CallbackQueryHandler(start, pattern=r"^Main_Menu$"))
    app.add_handler(CallbackQueryHandler(bot_stats, pattern=r"^botstats$"))
    app.add_handler(CallbackQueryHandler(start, pattern=r"^cancel$"))
    app.add_handler(CallbackQueryHandler(start, pattern=r"^Check_mandatory_channel$"))
    app.add_handler(CallbackQueryHandler(AdminList, pattern=r"^admin_list$"))
    app.add_handler(CallbackQueryHandler(admin_menyu, pattern="^exit_admin$"))
    app.add_handler(CallbackQueryHandler(start, pattern=r"^BackToMainMenu$"))
    app.add_handler(CallbackQueryHandler(handle_remove_item, pattern=r"^remove_item_(\d+)$"))
    app.add_handler(CallbackQueryHandler(handle_set_package, pattern=r"^set_package_(5|10)_set$"))
    app.add_handler(CallbackQueryHandler(handle_toggle_select, pattern=r"^toggle_select_(\d+)$"))
    app.add_handler(CallbackQueryHandler(handle_not_ready, pattern=r"^not_ready$"))
    app.add_handler(CallbackQueryHandler(handle_finalize_checkout, pattern=r"^finalize_checkout$"))
    app.add_handler(CallbackQueryHandler(handle_add_to_cart, pattern=r"^add_to_cart_(\d+)$"))
    app.add_handler(CallbackQueryHandler(handle_quantity_change, pattern=r"^(inc|dec)_(\d+)$"))
    app.add_handler(CallbackQueryHandler(handle_text_catalog, pattern=r"^open_catalog$"))

    # Sahifalar o'rtasida navigatsiya uchun (masalan: cat_page_2)
    app.add_handler(CallbackQueryHandler(catalog_pagination_handler, pattern="^cat_page_"))

    # Alohida atir ma'lumotini ko'rish uchun (masalan: prod_15)
    app.add_handler(CallbackQueryHandler(product_detail_handler, pattern="^prod_"))

    # Katalogni yopish uchun
    app.add_handler(CallbackQueryHandler(close_catalog_handler, pattern="^close_catalog$"))

    app.add_handler(CallbackQueryHandler(InlineButton))
    app.add_handler(MessageHandler(filters.Text("📚 Katalog"), handle_text_catalog))
    app.add_handler(MessageHandler(filters.Regex("^🛒 Savat$"), handle_view_cart))
    app.add_handler(MessageHandler(filters.Text("^📊 Tahlil$"), analytics_dashboard))

    app.add_handler(MessageHandler(filters.CONTACT | filters.LOCATION, handle_checkout_messages))
    group_filter = filters.ChatType.GROUPS & filters.TEXT & (~filters.COMMAND)
    app.add_handler(MessageHandler(group_filter, ai_group_assistant))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_message))

    app.add_handler(MessageHandler(~filters.COMMAND & ~filters.TEXT, yoqfunksiya))

    # Bot start
    print("Bot running!!!")
    app.run_polling()
