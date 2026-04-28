from telegram import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

admin_keyboardd = [
    [KeyboardButton("⚙️ Boshqarish")],
    [KeyboardButton(text="🔍 Qidirish"), KeyboardButton(text="📊 Tahlil")], 
    [KeyboardButton(text="➕ Qo'shish")],
    # [KeyboardButton(text="📥 Qaytarish"), KeyboardButton(text="📚 Katalog")]
   # [KeyboardButton(text="🛍 Sotish")]
]
ADMIN_KYB = ReplyKeyboardMarkup(admin_keyboardd, resize_keyboard=True)