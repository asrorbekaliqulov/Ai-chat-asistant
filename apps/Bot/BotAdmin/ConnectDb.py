import os
import json
from django.db.models import Count, Sum, Q, F
from django.utils import timezone
from asgiref.sync import sync_to_async
from google import genai
from google.genai import types
from telegram import Update
from telegram.ext import ContextTypes
# Modellarni import qilish
from apps.warehouse.models.base import Product, ProductVariant, StockTransaction
from apps.Bot.models.TelegramBot import TelegramUser, ChatMessage, CompanyData

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

class AdminAssistant:
    @staticmethod
    @sync_to_async
    def get_warehouse_stats(query_type, params=None):
        """
        AI uchun ma'lumot yetkazib beruvchi asosiy funksiya.
        SQL o'rniga Django QuerySet ishlatiladi.
        """
        if query_type == "low_stock":
            # Qoldig'i minimal limitdan kam bo'lganlar
            items = ProductVariant.objects.filter(stock__lte=F('min_stock_limit')).select_related('product')
            return [{"name": f"{i.product.name} ({i.brand})", "stock": float(i.stock)} for i in items]

        elif query_type == "most_asked":
            # ChatMessage larni tahlil qilib, qaysi so'zlar ko'p ishlatilganini taxminiy olish
            # (Oddiyroq usul: Eng ko'p xabar yozgan userlar yoki keyword qidirish)
            recent_msgs = ChatMessage.objects.filter(role='user').values('content')[:100]
            return list(recent_msgs)

        elif query_type == "top_selling":
            # Eng ko'p chiqim (sotuv) bo'lgan tovarlar
            top = StockTransaction.objects.filter(transaction_type='OUT')\
                .values('variant__product__name')\
                .annotate(total_qty=Sum('quantity'))\
                .order_by('-total_qty')[:5]
            return list(top)

        elif query_type == "user_stats":
            # Foydalanuvchilar statistikasi
            total = TelegramUser.objects.count()
            new_today = TelegramUser.objects.filter(date_joined__date=timezone.now().date()).count()
            return {"total_users": total, "new_today": new_today}

        return None

# AI uchun Tool deklaratsiyasi
tools = [types.Tool(function_declarations=[
    types.FunctionDeclaration(
        name="get_warehouse_stats",
        description="Ombor, foydalanuvchilar va chat statistikasi haqida ma'lumot oladi.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "query_type": types.Schema(
                    type="STRING", 
                    enum=["low_stock", "most_asked", "top_selling", "user_stats"],
                    description="Qanday turdagi ma'lumot kerakligi."
                ),
                "params": types.Schema(type="STRING", description="Qo'shimcha filtrlar (ixtiyoriy).")
            },
            required=["query_type"]
        )
    )
])]

async def admin_connect_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_prompt = update.message.text
    
    # 1-QADAM: AI ga so'rov yuborish
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction="Siz 'Do'ngariq Stroy' admin yordamchisisiz. HTML formatida javob bering.",
            tools=tools
        )
    )

    # Funksiya chaqiruvini tekshirish
    call = next((p.function_call for p in response.candidates[0].content.parts if p.function_call), None)

    if call:
        # 2-QADAM: Django bazasidan QuerySet orqali ma'lumot olish
        db_data = await AdminAssistant.get_warehouse_stats(
            call.args.get('query_type'), 
            call.args.get('params')
        )

        # 3-QADAM: Olingan ma'lumotni AI ga qaytarish (AI buni chiroyli matn qiladi)
        final_response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                types.Content(role="user", parts=[types.Part.from_text(text=user_prompt)]),
                types.Content(role="model", parts=[types.Part.from_function_call(name=call.name, args=call.args)]),
                types.Content(role="user", parts=[
                    types.Part.from_function_response(name=call.name, response={"result": db_data})
                ])
            ]
        )
        answer = final_response.text
    else:
        answer = response.text

    # HTML formatida yuborish
    await update.message.reply_text(answer, parse_mode='HTML')