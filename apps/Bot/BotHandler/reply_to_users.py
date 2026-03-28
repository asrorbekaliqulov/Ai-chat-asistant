import os
import numpy as np
from asgiref.sync import sync_to_async
from django.db.models import Q
from google import genai
from google.genai import types

from telegram import Update
from telegram.constants import ChatMemberStatus, ChatType, ParseMode
from telegram.ext import ContextTypes

# Modellarni import qilish
from apps.warehouse.models.base import ProductVariant
from apps.Bot.models.TelegramBot import CompanyData, ChatMessage, TelegramUser

from apps.Bot.decorators import typing_action

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# 1. Yordamchi Matematik Funksiya (Similarity tekshirish uchun)
def is_duplicate(new_vec, existing_vecs, threshold=0.85):
    for vec in existing_vecs:
        v1, v2 = np.array(new_vec), np.array(vec)
        norm = np.linalg.norm(v1) * np.linalg.norm(v2)
        score = np.dot(v1, v2) / norm if norm != 0 else 0
        if score > threshold:
            return True
    return False

# 2. Admin ma'lumotlarini o'rganish menejeri
class AdminLearningManager:
    @staticmethod
    async def process_admin_message(text: str):
        """Admin xabarini tahlil qilish va kerak bo'lsa CompanyData ga saqlash"""
        
        # 1. AI dan so'raymiz: Bu ma'lumot do'kon uchun muhimmi?
        analysis_prompt = (
            f"Ushbu xabarni tahlil qil: '{text}'. "
            "Agar bu xabar do'kon qoidalari, ish vaqti, narxlar o'zgarishi yoki "
            "mijozlar uchun muhim yangilik bo'lsa, 'IMPORTANT' so'zini qaytar. "
            "Aks holda 'IGNORE' qaytar."
        )
        
        res = client.models.generate_content(model="gemini-2.0-flash", contents=analysis_prompt)
        if "IMPORTANT" not in res.text.upper():
            return # Muhim emas

        # 2. Embedding olish
        new_embedding = await AIManager.get_embedding(text)
        if not new_embedding: return

        # 3. Takrorlanishni tekshirish (Duplicate check)
        existing_data = await sync_to_async(list)(CompanyData.objects.exclude(embedding__isnull=True))
        existing_vecs = [d.embedding for d in existing_data]

        if not is_duplicate(new_embedding, existing_vecs):
            # 4. Yangi ma'lumot sifatida saqlash
            await sync_to_async(CompanyData.objects.create)(
                content=text,
                embedding=new_embedding
            )
            print(f"DEBUG: Admin xabari CompanyData ga saqlandi: {text[:30]}...")

# 3. Asosiy AIManager klassi
class AIManager:
    @staticmethod
    async def get_embedding(text: str):
        try:
            res = client.models.embed_content(model="text-embedding-004", contents=text)
            return res.embeddings[0].values
        except: return None

    @staticmethod
    @sync_to_async
    def get_chat_history(t_user_id, limit=6):
        msgs = ChatMessage.objects.filter(user__user_id=t_user_id).order_by('-created_at')[:limit]
        history = []
        for m in reversed(msgs):
            role = "user" if m.role in ['user', 'admin'] else "model"
            history.append(types.Content(role=role, parts=[types.Part.from_text(text=m.content)]))
        return history

    @staticmethod
    @sync_to_async
    def search_inventory(query):
        variants = ProductVariant.objects.filter(
            Q(product__name__icontains=query) | Q(brand__icontains=query)
        ).select_related('product')[:3]
        if not variants.exists(): return "Afsuski, mahsulot topilmadi."
        
        res = "🔍 <b>Natijalar:</b>\n\n"
        for v in variants:
            res += f"📦 <b>{v.product.name}</b>\n💰 Narxi: {v.selling_price:,} so'm\n📊 {v.stock} {v.product.unit} bor.\n\n"
        return res

    @staticmethod
    @sync_to_async
    def search_company_rules(query_vec):
        """CompanyData dan eng yaqin ma'lumotni topish"""
        all_rules = CompanyData.objects.exclude(embedding__isnull=True)
        best_text, best_score = None, 0
        for rule in all_rules:
            score = get_cosine_similarity(query_vec, rule.embedding) # Avvalgi koddan similarity funksiyasi
            if score > best_score:
                best_score, best_text = score, rule.content
        return best_text if best_score > 0.75 else None

@sync_to_async
def save_message_to_db(user_id, role, content):
    user = TelegramUser.objects.get(user_id=user_id)
    ChatMessage.objects.create(user=user, role=role, content=content)

# 4. Guruhda ishlovchi Asosiy Funksiya
@typing_action
async def ai_group_assistant(update: Update, context: ContextTypes.DEFAULT_TYPE): 
    if not update.message or not update.message.text: return
    chat = update.effective_chat
    user = update.effective_user
    user_msg = update.message.text

    # 1. Admin tekshiruvi
    member = await context.bot.get_chat_member(chat.id, user.id)
    is_admin = member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]

    # 2. Xabarni xotiraga saqlash (ChatMessage)
    role = 'admin' if is_admin else 'user'
    await save_message_to_db(user.id, role, user_msg)

    # 3. AGAR ADMIN YOZSA: O'rganish tizimini ishga tushiramiz
    if is_admin:
        await AdminLearningManager.process_admin_message(user_msg)
        return # Adminlarga bot javob qaytarmaydi!

    # 4. AGAR ODDIY USER YOZSA: Javob berish mantiqi
    history = await AIManager.get_chat_history(user.id)
    
    tools = [types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="get_product_info",
            description="Mahsulot narxi va bor-yo'qligini tekshirish.",
            parameters=types.Schema(type="OBJECT", properties={"q": types.Schema(type="STRING")}, required=["q"])
        ),
        types.FunctionDeclaration(
            name="get_store_rules",
            description="Ish vaqti, manzil va umumiy qoidalar uchun.",
            parameters=types.Schema(type="OBJECT", properties={"topic": types.Schema(type="STRING")}, required=["topic"])
        )
    ])]

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=history + [types.Content(role="user", parts=[types.Part.from_text(text=user_msg)])],
            config=types.GenerateContentConfig(
                system_instruction="Sen do'kon yordamchisisan. Adminlardan olingan yangi ma'lumotlarni hisobga ol.",
                tools=tools
            )
        )

        call = next((p.function_call for p in response.candidates[0].content.parts if p.function_call), None)
        if not call: return

        if call.name == "get_product_info":
            info = await AIManager.search_inventory(call.args['q'])
            await update.message.reply_text(info, parse_mode=ParseMode.HTML)
            await save_message_to_db(user.id, 'model', info)

        elif call.name == "get_store_rules":
            vec = await AIManager.get_embedding(call.args['topic'])
            rule = await AIManager.search_company_rules(vec)
            if rule:
                final_res = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=f"Mijoz so'radi: {user_msg}\nBazadagi ma'lumot: {rule}\nChiroyli javob ber."
                )
                await update.message.reply_text(final_res.text)
                await save_message_to_db(user.id, 'model', final_res.text)

    except Exception as e:
        print(f"AI Assist Error: {e}")