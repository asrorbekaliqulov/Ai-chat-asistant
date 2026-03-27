import pandas as pd
from pandasai import SmartDatalake
from pandasai_docker import DockerSandbox
from pandasai_litellm.litellm import LiteLLM
from django.apps import apps
from asgiref.sync import sync_to_async
import os

# Konfiguratsiya
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
llm = LiteLLM(model="gemini/gemini-2.5-flash", api_key=GEMINI_API_KEY)
# pai.config.set({"llm": llm})

@sync_to_async
def generate_pandasai_analysis(user_query: str):
    """Django jadvallarini DataFrame qilib AI ga tahlilga beradi"""
    all_dfs = []
    
    try:
        # 1. 'warehouse' appidagi barcha modellarni olamiz
        app_models = apps.get_app_config('warehouse').get_models() 
        
        for model in app_models:
            # QuerySetni DataFrame ga o'tkazamiz
            queryset = model.objects.all().values()
            if queryset.exists():
                df = pd.DataFrame(list(queryset))
                # AI jadvallarni bog'lay olishi uchun nomlaymiz
                df.name = model._meta.db_table 
                all_dfs.append(df)
        
        if not all_dfs:
            return "Bazada tahlil qilish uchun ma'lumot yetarli emas."

        # 2. SmartDatalake - ko'p jadvallar bilan ishlash uchun eng yaxshisi
        # DockerSandbox o'rnika qulayroq konfiguratsiyadan foydalanamiz
        dl = SmartDatalake(all_dfs, config={"llm": llm, "verbose": True, "enable_cache": False})
        
        # 3. AI tahlili
        response = dl.chat(user_query)
        
        # Agar AI rasm (grafik) chizgan bo'lsa, response fayl yo'li bo'lib keladi
        return str(response)

    except Exception as e:
        print(f"PandasAI Error: {e}")
        return f"Tahlil davomida xatolik: {str(e)}"

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

async def generate_admin_ai_response(user_message: str, user_id: int, chat_history: list = None):
    """Admin uchun PandasAI orqali MB tahlili"""
    
    # 1. Admin ekanligini yana bir bor tekshirish (xavfsizlik uchun)
    # Bu yerda o'zingizning ADMIN_ID tekshiruvingiz bor deb hisoblaymiz
    
    try:
        # PandasAI orqali tahlilni boshlaymiz
        # Bu funksiya MB dagi barcha jadvallarni AIga taqdim etadi
        analysis_result = await generate_pandasai_analysis(f"User xabari javobni O'zbek tilida qaytaring: {user_message}")
        
        # 2. Natijani formatlash
        # PandasAI ba'zan rasm yo'lini qaytaradi, shuni tekshirish kerak
        if ".png" in analysis_result or ".jpg" in analysis_result:
            return f"📊 Grafik tayyorlandi. (Eslatma: Grafik serverda saqlandi: {analysis_result})"
        
        return analysis_result

    except Exception as e:
        return f"⚠️ Tizim tahlilida nosozlik: {str(e)}"

# from .sale_handler import SaleManager, get_sale_confirmation_markup

# async def handle_sale_request(search_query: str, quantity: float):
#     """Bu funksiya Gemini tomonidan chaqiriladi"""
#     result = await SaleManager.find_product(search_query, quantity)
    
#     if result["status"] == "found":
#         # Birinchi topilgan mahsulotni tasdiqlashga yuboramiz
#         product = result["data"][0]
#         text, markup = get_sale_confirmation_markup(product)
#         return {
#             "status": "button_required",
#             "text": text,
#             "markup": markup
#         }
#     else:
#         return {
#             "status": "error",
#             "text": f"Kechirasiz, bazadan '{search_query}' topilmadi. Iltimos, nomini aniqroq ayting."
#         }