import os
import re
from django.db.models import Sum, F, Q, Count
from django.utils import timezone
from datetime import timedelta
from asgiref.sync import sync_to_async
from google import genai
from google.genai import types

# Modellarni import qilish
from apps.warehouse.models.base import Product, ProductVariant, StockTransaction
from apps.Bot.models.TelegramBot import TelegramUser, ChatMessage

class AdminTaskManager:
    @staticmethod
    @sync_to_async
    def get_inventory_stock(product_name: str = None):
        """Ombordagi mahsulotlar qoldig'ini olish (Decimal -> float o'tkazilgan)"""
        try:
            queryset = ProductVariant.objects.select_related('product').all()
            if product_name:
                queryset = queryset.filter(
                    Q(product__name__icontains=product_name) | Q(brand__icontains=product_name)
                )
            
            # .values() ichidagi Decimal maydonlarni (stock, selling_price) 
            # qo'lda float'ga o'tkazish yoki tahrirlash:
            raw_data = list(queryset.values('product__name', 'brand', 'size', 'stock', 'selling_price'))
            
            # Decimal xatosini oldini olish uchun float'ga o'tkazamiz
            processed_data = []
            for item in raw_data:
                processed_data.append({
                    "name": item['product__name'],
                    "brand": item['brand'],
                    "size": item['size'],
                    "stock": float(item['stock']) if item['stock'] is not None else 0,
                    "price": float(item['selling_price']) if item['selling_price'] is not None else 0
                })
            
            return {"inventory": processed_data} if processed_data else {"message": "Mahsulot topilmadi"}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    @sync_to_async
    def get_sales_analytics(days: int = 1):
        """Savdo tahlili (Decimal xatosi tuzatilgan)"""
        try:
            start_date = timezone.now() - timedelta(days=days)
            transactions = StockTransaction.objects.filter(
                transaction_type='OUT', 
                created_at__gte=start_date
            )
            
            res = transactions.aggregate(
                total=Sum(F('quantity') * F('variant__selling_price'))
            )
            
            # Natijani float'ga o'tkazamiz
            total_sum = float(res['total']) if res['total'] else 0.0
            count = transactions.count()
            
            return {
                "total_sales_sum": total_sum, 
                "transactions_count": count, 
                "period_days": days
            }
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    @sync_to_async
    def get_chat_daily_report():
        """Chat tahlili (Xabarlar soni va top foydalanuvchilar)"""
        try:
            yesterday = timezone.now() - timedelta(days=1)
            messages = ChatMessage.objects.filter(created_at__gte=yesterday)
            
            total_msgs = messages.count()
            # Django annotate natijalari odatda int bo'ladi, lekin ehtiyotkorlik uchun list'ga olamiz
            top_users = list(messages.values('user__first_name').annotate(count=Count('id')).order_by('-count')[:5])
            recent_texts = list(messages.values_list('content', flat=True).order_by('-created_at')[:20])
            
            return {
                "total_messages": total_msgs,
                "top_active_users": top_users,
                "sample_messages": recent_texts
            }
        except Exception as e:
            return {"error": str(e)}
        
# Gemini Tools Deklaratsiyasi
tools = [types.Tool(function_declarations=[
    types.FunctionDeclaration(
        name="get_inventory_stock",
        description="Ombordagi mahsulotlar qoldig'ini ko'rish. Mahsulot nomi bo'yicha qidirish mumkin.",
        parameters=types.Schema(
            type="OBJECT",
            properties={"product_name": types.Schema(type="STRING", description="Mahsulot nomi (masalan: sement)")}
        )
    ),
    types.FunctionDeclaration(
        name="get_sales_analytics",
        description="Savdo hajmi va tushumni hisoblash.",
        parameters=types.Schema(
            type="OBJECT",
            properties={"days": types.Schema(type="INTEGER", description="Necha kunlik savdo (standart 1)")}
        )
    ),
    types.FunctionDeclaration(
        name="get_chat_daily_report",
        description="Oxirgi 1 kunlik chat faolligi va foydalanuvchilar suhbatini tahlil qilish."
    )
])]

ADMIN_INSTR = (
    "Siz 'Do'ngariq Stroy' admin yordamchisisiz. "
    "Mavjud funksiyalar yordamida ma'lumot oling va ularni chiroyli HTML formatda tushuntiring. "
    "Hech qachon texnik JSON natijani ko'rsatman, uni odam tiliga o'giring."
)

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

async def generate_admin_ai_response(user_msg: str):
    try:
        chat_contents = [types.Content(role="user", parts=[types.Part.from_text(text=user_msg)])]
        
        for _ in range(3):
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=chat_contents,
                config=types.GenerateContentConfig(system_instruction=ADMIN_INSTR, tools=tools, temperature=0.0)
            )
            
            res_content = response.candidates[0].content
            chat_contents.append(res_content)
            call = next((p.function_call for p in res_content.parts if p.function_call), None)

            if call:
                # Funksiya nomiga qarab tegishli metodni chaqiramiz
                if call.name == "get_inventory_stock":
                    db_res = await AdminTaskManager.get_inventory_stock(call.args.get('product_name'))
                elif call.name == "get_sales_analytics":
                    db_res = await AdminTaskManager.get_sales_analytics(call.args.get('days', 1))
                elif call.name == "get_chat_daily_report":
                    db_res = await AdminTaskManager.get_chat_daily_report()
                
                chat_contents.append(types.Content(
                    role="user", 
                    parts=[types.Part.from_function_response(name=call.name, response={"result": db_res})]
                ))
                continue
            else:
                raw_text = response.text
                break
        
        # HTML Tozalash
        clean_text = raw_text.replace('<p>', '').replace('</p>', '\n')
        clean_text = re.sub(r'<(?!/?(b|i|code|u|a|pre)\b)[^>]+>', '', clean_text)
        return clean_text.strip()

    except Exception as e:
        return f"⚠️ <b>Xatolik:</b> <code>{str(e)}</code>"