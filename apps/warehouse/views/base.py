import pandas as pd
import pandasai as pai
from pandasai_docker import DockerSandbox
from pandasai_litellm.litellm import LiteLLM
from django.apps import apps
from django.http import JsonResponse
from django.shortcuts import render
import os

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

llm = LiteLLM(model="gemini/gemini-2.5-flash", api_key=GEMINI_API_KEY)
pai.config.set({"llm": llm})

def admin_chat_page(request):
    """Chat sahifasini ochish"""
    return render(request, 'admin/warehouse_chat.html')

def pandasai_query(request):
    """AI bilan savol-javob qilish"""
    if request.method == "POST":
        user_query = request.POST.get('query')
        
        # 1. Loyihadagi barcha jadvallarni (modellarni) yig'amiz
        all_pai_dataframes = []
        try:
            # 'main' o'rniga o'z app-ingiz nomini yozing
            app_models = apps.get_app_config('warehouse').get_models() 
            
            for model in app_models:
                queryset = model.objects.all().values()
                if queryset.exists():
                    df = pd.DataFrame(list(queryset))
                    # Har bir modelni AI tushunadigan formata o'tkazamiz
                    pai_df = pai.DataFrame(df, name=model._meta.db_table)
                    all_pai_dataframes.append(pai_df)
            
            if not all_pai_dataframes:
                return JsonResponse({'status': 'error', 'message': "Bazada ma'lumot topilmadi!"})

            # 2. Xavfsiz Sandboxni ishga tushiramiz
            sandbox = DockerSandbox()
            sandbox.start()

            try:
                # 3. AI muloqoti
                # Savolni beramiz va barcha jadvallarni yuboramiz (*all_pai_dataframes)
                response = pai.chat(user_query, *all_pai_dataframes, sandbox=sandbox)
                
                return JsonResponse({
                    'status': 'success',
                    'result': str(response),
                    'chart_url': None # Agar chart bo'lsa yo'lini bu yerga yozish mumkin
                })
            finally:
                sandbox.stop() # Sandboxni doim to'xtatamiz

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

    return JsonResponse({'status': 'error', 'message': 'Invalid request'})



import os
import json
import base64
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
# Yangi SDK ni import qilish
from google import genai
from google.genai import types
from apps.warehouse.models.base import Category, Product, ProductVariant

# Clientni global sozlash
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def add_product_page(request):
    """HTML sahifani ochish"""
    categories = Category.objects.all()
    return render(request, 'warehouse/add_product.html', {'categories': categories})


@csrf_exempt
def analyze_product_image(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            image_data = data.get('image')

            # 1. Kontekst tayyorlash
            existing_products = list(Product.objects.values_list('name', flat=True))
            products_context = ", ".join(existing_products) if existing_products else "Baza bo'sh."
            categories = [cat.name for cat in Category.objects.all()]
            
            # 2. Rasmni decode qilish
            header, encoded = image_data.split(",", 1)
            image_bytes = base64.b64decode(encoded)

            prompt = f"""
            Siz qurilish do'koni yordamchisisiz. Rasmdagi mahsulotni aniqlang.
            MAVJUD MAHSULOTLAR: [{products_context}]
            KATEGORIYALAR: {categories}

            QOIDALAR:
            1. Agar mahsulot ro'yxatda bo'lsa, shuni qaytaring.
            2. Javobni FAQAT bitta JSON obyekti ko'rinishida bering.
            3. Til: O'zbek tili (Lotin alifbosi).
            
            Format:
            {{
                "name": "Nomi",
                "brand": "Brendi (yo'q bo'lsa bo'sh qoldiring)",
                "size": "O'lchami (yo'q bo'lsa bo'sh qoldiring)",
                "unit": "dona, kg, qop, m2 lardan biri",
                "description": "Qisqa ta'rif",
                "category": "Kategoriya nomi (ro'yxatdan tanlang)"
            }}
            """

            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[
                    types.Content(
                        parts=[
                            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                            types.Part.from_text(text=prompt)
                        ]
                    )
                ],
                config=types.GenerateContentConfig(
                    response_mime_type='application/json',
                    temperature=0.0,
                )
            )

            ai_json = json.loads(response.text)
            
            # MUHIM: Agar AI [{...}] (list) qaytarsa, ichidagi obyektni olamiz
            if isinstance(ai_json, list) and len(ai_json) > 0:
                ai_json = ai_json[0]

            print("Tozalangan AI javobi:", ai_json)
            return JsonResponse({'status': 'success', 'data': ai_json})

        except Exception as e:
            print(f"Xatolik: {e}")
            return JsonResponse({'status': 'error', 'message': str(e)})
            
    return JsonResponse({'status': 'error', 'message': 'Faqat POST so\'rovi qabul qilinadi'})

@csrf_exempt
def save_final_product(request):
    """Frontenddan kelgan yakuniy ma'lumotlarni rasm bilan saqlash"""
    if request.method == "POST":
        try:
            # Matnli ma'lumotlar
            p_name = request.POST.get('name')
            p_brand = request.POST.get('brand')
            p_category_id = request.POST.get('category')
            
            # Fayllar (Rasm)
            product_image = request.FILES.get('product_image')
            variant_image = request.FILES.get('variant_image')

            category = Category.objects.get(id=p_category_id)

            # 1. Asosiy mahsulotni yaratish yoki yangilash
            product, created = Product.objects.get_or_create(
                name=p_name,
                category=category,
                defaults={'unit': request.POST.get('unit')}
            )
            
            if product_image:
                product.image = product_image # Modelda ImageField bo'lishi shart
                product.save()

            # 2. Variantni yaratish
            variant = ProductVariant.objects.create(
                product=product,
                brand=p_brand,
                size=request.POST.get('size'),
                purchase_price=request.POST.get('purchase_price'),
                selling_price=request.POST.get('selling_price'),
                stock=request.POST.get('stock')
            )

            if variant_image:
                variant.image = variant_image
                variant.save()

            return JsonResponse({'status': 'success', 'message': 'Saqlandi!'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})