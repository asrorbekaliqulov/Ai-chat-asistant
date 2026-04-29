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


from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from apps.warehouse.models.base import Category, Product, ProductVariant
import json

def add_product_page(request):
    categories = Category.objects.all()
    return render(request, 'warehouse/add_product.html', {'categories': categories})

def search_products(request):
    """Mahsulot nomini bazadan qidirish"""
    query = request.GET.get('q', '')
    if len(query) < 2:
        return JsonResponse({'products': []})
    
    products = Product.objects.filter(name__icontains=query).values('id', 'name', 'category_id', 'unit')[:5]
    return JsonResponse({'products': list(products)})

@csrf_exempt
def save_mega_product(request):
    """Bitta product va uning bir nechta variantlarini saqlash"""
    if request.method == "POST":
        try:
            # 1. Asosiy mahsulot ma'lumotlari
            p_name = request.POST.get('product_name')
            p_category_id = request.POST.get('category')
            p_unit = request.POST.get('product_unit')
            
            if not p_name or not p_category_id:
                return JsonResponse({'status': 'error', 'message': 'Mahsulot nomi va kategoriya majburiy!'})

            category = Category.objects.get(id=p_category_id)

            # Mahsulotni yaratish yoki mavjudini olish
            product, created = Product.objects.get_or_create(
                name=p_name,
                category=category,
                defaults={'unit': p_unit}
            )

            # 2. Variantlarni qayta ishlash
            # Frontenddan keladigan variantlar sonini aniqlaymiz
            variant_indices = [k.split('_')[1] for k in request.POST.keys() if k.startswith('brand_')]
            
            for idx in variant_indices:
                brand = request.POST.get(f'brand_{idx}')
                price = request.POST.get(f'price_{idx}')
                size = request.POST.get(f'size_{idx}')
                stock = request.POST.get(f'stock_{idx}', 0)
                
                # Rasm (har bir variant uchun alohida)
                v_image = request.FILES.get(f'v_image_file_{idx}')

                if brand and price:
                    variant = ProductVariant.objects.create(
                        product=product,
                        brand=brand,
                        selling_price=price,
                        size=size,
                        stock=stock,
                        is_active=True
                    )
                    if v_image:
                        variant.image = v_image
                        variant.save()

            return JsonResponse({'status': 'success', 'message': 'Muvaffaqiyatli saqlandi!'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})