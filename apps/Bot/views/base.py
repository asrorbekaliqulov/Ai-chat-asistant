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
    return render(request, 'admin/chat.html')

def pandasai_query(request):
    """AI bilan savol-javob qilish"""
    if request.method == "POST":
        user_query = request.POST.get('query')
        
        # 1. Loyihadagi barcha jadvallarni (modellarni) yig'amiz
        all_pai_dataframes = []
        try:
            # 'main' o'rniga o'z app-ingiz nomini yozing
            app_models = apps.get_app_config('Bot').get_models() 
            
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