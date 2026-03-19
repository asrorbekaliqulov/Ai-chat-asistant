import os
import logging
from telegram import Update, constants
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from google import genai
from google.genai import types

# --- KONFIGURATSIYA ---
TELEGRAM_TOKEN = '8250586027:AAFpVaQsV5c5ohOTk9br7HYbehydfZ3j1_c'
GEMINI_API_KEY = 'AIzaSyCadJM-nDk7xuDWNgm1U6OwksRmtAjhdyQ'
MODEL_NAME = "gemini-2.5-flash" # Tezkor va multimodal model

# Gemini Clientini initsializatsiya qilish (Yangi SDK)
client = genai.Client(api_key=GEMINI_API_KEY)

# Loglarni sozlash
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- ASOSIY FUNKTSYA ---
async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ovozli xabarni qabul qilib, unga javob qaytaruvchi funksiya."""
    
    # 0. Tekshirish: Ovozli xabar bormi?
    if not update.message.voice:
        return

    # Foydalanuvchiga jarayon boshlanganini bildirish
    status_message = await update.message.reply_text("🎧 Ovozli xabar eshitilmoqda...")
    
    # Bot "yozmoqda..." statusini ko'rsatib turishi uchun
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=constants.ChatAction.TYPING)

    file_path = f"voice_{update.message.voice.file_id}.ogg"

    try:
        # 1. Ovozli xabarni Telegram serveridan yuklab olish
        voice_file = await context.bot.get_file(update.message.voice.file_id)
        await voice_file.download_to_drive(file_path)
        logging.info(f"Fayl yuklandi: {file_path}")

        # 2. Faylni o'qish (binary formatda)
        with open(file_path, "rb") as f:
            audio_data = f.read()

        # 3. Gemini-ga murakkab so'rov yuborish
        # Biz AIdan ham transkripsiyani, ham javobni alohida ajratib berishni so'raymiz
        prompt = (
            "Ushbu audio faylni diqqat bilan eshit. "
            "Avval audiodagi gaplarni so'zma-so'z matnga aylantir (transkripsiya). "
            "Keyin, o'sha gaplardan kelib chiqib foydalanuvchiga samimiy javob yoz. "
            "Javobingni aniq struktura bilan ber: "
            "START_TRANSCRIPT [matn shu yerga] END_TRANSCRIPT "
            "START_ANSWER [javob shu yerga] END_ANSWER"
        )

        logging.info("Gemini API-ga so'rov yuborilmoqda...")
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[
                prompt,
                types.Part.from_bytes(data=audio_data, mime_type="audio/ogg")
            ]
        )
        
        raw_text = response.text
        logging.info(f"Gemini raw javobi: {raw_text}")

        # 4. Gemini javobini parse qilish (ajratib olish)
        # Murakkab prompt berganimiz sababli, javobni qismlarga ajratamiz
        try:
            transcript = raw_text.split("START_TRANSCRIPT")[1].split("END_TRANSCRIPT")[0].strip()
            answer = raw_text.split("START_ANSWER")[1].split("END_ANSWER")[0].strip()
        except IndexError:
            # Agar AI strukturaga rioya qilmasa (kamdan-kam bo'ladi)
            transcript = "Ovozni tushunib bo'lmadi."
            answer = raw_text # Butun matnni javob sifatida beramiz

        # 5. Natijani chiroyli formatda foydalanuvchiga qaytarish
        final_response = (
            f"📝 **Sizning xabaringiz:**\n_{transcript}_\n\n"
            f"🤖 **Bot javobi:**\n{answer}"
        )

        # "Eshitilmoqda..." xabarini o'chirib, o'rniga haqiqiy javobni yuborish
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=status_message.message_id)
        await update.message.reply_text(final_response, parse_mode=constants.ParseMode.MARKDOWN)

    except Exception as e:
        logging.error(f"Xatolik: {e}")
        await status_message.edit_text("Kechirasiz, ovozni tahlil qilishda texnik xatolik yuz berdi.")
    
    finally:
        # 6. Vaqtinchalik faylni o'chirish (server xotirasini to'ldirmaslik uchun)
        if os.path.exists(file_path):
            os.remove(file_path)
            logging.info(f"Vaqtinchalik fayl o'chirildi: {file_path}")

# --- BOTNI ISHGA TUSHIRISH ---
if __name__ == '__main__':
    # Application qurish
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Faqat ovozli xabarlarni (filters.VOICE) qayta ishlovchi handler
    voice_handler = MessageHandler(filters.VOICE & ~filters.COMMAND, handle_voice)
    application.add_handler(voice_handler)
    
    print(f"Bot ishga tushdi...")
    # Polling rejimida ishga tushirish
    application.run_polling()