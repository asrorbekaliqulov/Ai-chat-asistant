import re
import json
from google import genai
import os

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Clientni sozlash
client = genai.Client(api_key=GEMINI_API_KEY)

async def analyze_product_data(audio_path=None, text_content=None):
    """
    Matn yoki audio orqali mahsulot ma'lumotlarini tahlil qiladi.
    """
    prompt = """
    Sen professional ombor yordamchisisan. Quyidagi ma'lumotdan mahsulot detallarini ajratib ol.
    
    MAJBURIY MAYDONLAR: 
    1. name (mahsulot nomi)
    2. purchase_price (kirim narxi - faqat raqam)
    3. quantity (miqdori - faqat raqam)
    
    Ixtiyoriy: brand, size, selling_price, unit.

    Faqatgina JSON formatida javob qaytar:
    {
        "name": "string or null",
        "brand": "string or null",
        "size": "string or null",
        "purchase_price": number or null,
        "selling_price": number or null,
        "quantity": number or null,
        "unit": "string or null"
    }
    """

    try:
        if audio_path:
            with open(audio_path, "rb") as f:
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=[prompt, {"mime_type": "audio/ogg", "data": f.read()}]
                )
        else:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=f"{prompt}\n\nMa'lumot: {text_content}"
            )

        # JSONni tozalab olish
        match = re.search(r'\{.*\}', response.text, re.DOTALL)
        if match:
            return json.loads(match.group())
        return None
    except Exception as e:
        print(f"Gemini Error: {e}")
        return None