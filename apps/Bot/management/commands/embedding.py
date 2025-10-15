from django.core.management.base import BaseCommand
from apps.Bot.embedding_utils import update_company_embeddings    # ✅ Botni chaqiramiz
import asyncio

class Command(BaseCommand):
    help = "Telegram botni ishga tushirish"

    def handle(self, *args, **kwargs):
        asyncio.run(update_company_embeddings())
