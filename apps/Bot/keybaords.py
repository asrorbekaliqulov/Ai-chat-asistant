from telegram import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

admin_keyboardd = [
    [KeyboardButton("🛍 Sotish")],
    [KeyboardButton(text="📥 Qaytarish"), KeyboardButton(text="➕ Qo'shish")],
    [KeyboardButton(text="🔍 Qidirish"), KeyboardButton(text="📚 Katalog")],
    [KeyboardButton(text="📊 Tahlil")]
]
ADMIN_KYB = ReplyKeyboardMarkup(admin_keyboardd, resize_keyboard=True)