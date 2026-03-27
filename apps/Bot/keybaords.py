from telegram import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

admin_keyboardd = [
    [KeyboardButton("🔍 Qidirish")],
    [KeyboardButton(text="🛍 Sotish"), KeyboardButton(text="➕ Qo'shish")],
    [KeyboardButton(text="📥 Qaytarish"), KeyboardButton(text="📚 Katalog")],
    [KeyboardButton(text="📊 Tahlil")]
]
ADMIN_KYB = ReplyKeyboardMarkup(admin_keyboardd, resize_keyboard=True)