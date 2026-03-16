import pandas as pd
from pandasai_litellm.litellm import LiteLLM
from telegram import Update
from telegram.ext import ContextTypes
import dotenv
import os

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

llm = LiteLLM(model="gemini/gemini-2.5-flash", api_key=GEMINI_API_KEY)
db_path = "db.sqlite3"
def db():
    import sqlite3
    return sqlite3.connect(db_path)

import pandas as pd
from pandasai import SmartDataframe


async def admin_connect_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # 1. Ma'lumotlar bazasiga ulanish (misol uchun sqlite)
    # db_engine yoki connection obyekti oldindan yaratilgan bo'lishi kerak
    query = "SELECT * FROM bot_telegramuser" # Jadval nomini o'zgartiring
    
    try:
        # 2. Ma'lumotlarni o'qish
        df = pd.read_sql(query, db()) # 'db' bu yerda connection yoki engine bo'lishi shart
        
        # 3. PandasAI sozlamalari
        # 'llm' obyekti funksiyadan tashqarida yoki ichida aniqlangan bo'lishi kerak
        config = {"llm": llm}
        sdf = SmartDataframe(df, config=config)
        
        # 4. Promptni tayyorlash
        user_prompt = update.message.text
        # LLM ga natijani HTML formatida qaytarishni qat'iy tayinlaymiz
        full_prompt = (
            f"{user_prompt}\n\n"
            "MUHIM: Javobni faqat Telegram HTML parse_mode formatiga mos qilib qaytar. "
            "Masalan, <b>qalin</b>, <i>kursiv</i> yoki <code>kod</code> teglari bilan."
        )
        
        # 5. Savolga javob olish
        result = sdf.chat(full_prompt)
        
        # 6. Natijani yuborish
        if result:
            await update.message.reply_text(str(result), parse_mode='HTML')
        else:
            await update.message.reply_text("Ma'lumot topilmadi yoki xatolik yuz berdi.")
            
    except Exception as e:
        await update.message.reply_text(f"Xatolik yuz berdi: <code>{str(e)}</code>", parse_mode='HTML')