from django.core.management.base import BaseCommand
from apps.Bot.bot.main import main  # ✅ Botni chaqiramiz


class Command(BaseCommand):
    help = "Telegram botni ishga tushirish"

    def handle(self, *args, **kwargs):
        main()
