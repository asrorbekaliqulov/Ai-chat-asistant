import os
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from django.utils import timezone
from datetime import timedelta
from asgiref.sync import sync_to_async
from telegram.error import BadRequest  # Bu importni fayl tepasiga qo'shing

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, CommandHandler

# Modellarni import qilish (Yo'lni o'zingiznikiga moslang)
from apps.warehouse.models.base import ProductVariant, StockTransaction

# ---------------------------------------------------------
# 1. ANALYTICS MANAGER (Ma'lumotlarni hisoblash qismi)
# ---------------------------------------------------------
class AnalyticsManager:
    @staticmethod
    @sync_to_async
    def get_warehouse_summary():
        """Ombordagi umumiy moliyaviy holat tahlili"""
        variants = ProductVariant.objects.all()
        
        # Jami kirim narxi bo'yicha qiymat (Sizning pulingiz)
        total_purchase_value = variants.aggregate(
            total=Sum(F('stock') * F('purchase_price'), output_field=DecimalField())
        )['total'] or 0
        
        # Jami sotuv narxi bo'yicha qiymat
        total_selling_value = variants.aggregate(
            total=Sum(F('stock') * F('selling_price'), output_field=DecimalField())
        )['total'] or 0

        # Kam qolgan mahsulotlar soni
        low_stock_count = variants.filter(stock__lte=F('min_stock_limit')).count()
        
        return {
            "total_types": variants.count(),
            "purchase_value": float(total_purchase_value),
            "selling_value": float(total_selling_value),
            "expected_profit": float(total_selling_value - total_purchase_value),
            "low_stock_count": low_stock_count
        }

    @staticmethod
    @sync_to_async
    def get_sales_period_stats(days: int):
        """Ma'lum kunlik savdo hajmi va foydasini hisoblash"""
        start_date = timezone.now() - timedelta(days=days)
        # Faqat chiqim (sotuv) tranzaksiyalarini olamiz
        sales = StockTransaction.objects.filter(
            transaction_type='OUT', 
            created_at__gte=start_date
        ).select_related('variant')

        total_qty = 0
        total_sum = 0
        total_profit = 0

        for s in sales:
            qty = float(s.quantity)
            sell_price = float(s.variant.selling_price)
            buy_price = float(s.variant.purchase_price)
            
            total_qty += qty
            total_sum += (qty * sell_price)
            total_profit += (qty * (sell_price - buy_price))

        return {
            "days": days,
            "qty": total_qty,
            "sum": total_sum,
            "profit": total_profit
        }

# ---------------------------------------------------------
# 2. HANDLERS (Telegram interfeys qismi)
# ---------------------------------------------------------

async def analytics_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Asosiy analitika paneli"""
    summary = await AnalyticsManager.get_warehouse_summary()
    
    query = update.callback_query
    
    # Matnga vaqt belgisini qo'shib qo'ysangiz, "Yangilash" bosilganda 
    # soniyalar o'zgargani uchun "Message not modified" xatosi kamroq chiqadi
    now = timezone.now().strftime("%H:%M:%S")
    
    text = (
        f"📊 <b>OMBORNING UMUMIY HOLATI</b> (at {now})\n"
        "__________________________\n\n"
        f"📦 <b>Mahsulot turlari:</b> {summary['total_types']} ta\n"
        f"💰 <b>Ombordagi mollar (Kirim):</b> {summary['purchase_value']:,} so'm\n"
        f"💵 <b>Sotuv qiymati:</b> {summary['selling_value']:,} so'm\n"
        f"📈 <b>Kutilayotgan sof foyda:</b> {summary['expected_profit']:,} so'm\n"
        f"⚠️ <b>Tugayotgan mahsulotlar:</b> {summary['low_stock_count']} ta\n"
        "__________________________\n"
        "📅 <b>Savdo statistikasini ko'rish:</b>"
    )

    keyboard = [
        [
            InlineKeyboardButton("1 kun", callback_data="days:1"),
            InlineKeyboardButton("3 kun", callback_data="days:3"),
            InlineKeyboardButton("7 kun", callback_data="days:7")
        ],
        [
            InlineKeyboardButton("15 kun", callback_data="days:15"),
            InlineKeyboardButton("1 oy", callback_data="days:30")
        ],
        [InlineKeyboardButton("⚠️ Tugayotgan mahsulotlar", callback_data="low_stock_list")],
        [InlineKeyboardButton("🔄 Yangilash", callback_data="main_stats")]
    ]

    if query:
        try:
            # Tahrirlashga urinib ko'ramiz
            await query.edit_message_text(
                text, 
                parse_mode='HTML', 
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except BadRequest as e:
            # Agar xabar bir xil bo'lsa, xatoni shunchaki e'tiborsiz qoldiramiz
            if "Message is not modified" in str(e):
                # Foydalanuvchiga ma'lumotlar eng so'nggi holatda ekanini bildirish uchun query.answer ishlatamiz
                await query.answer("Ma'lumotlar allaqachon yangilangan.")
            else:
                # Boshqa turdagi BadRequest xatolari bo'lsa, ularni qayta ko'taramiz
                raise e
    else:
        # Agar callback emas, command bo'lsa yangi xabar yuboramiz
        await update.message.reply_text(
            text, 
            parse_mode='HTML', 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def analytics_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tugmalar bosilganda ishlovchi funksiya"""
    query = update.callback_query
    data = query.data
    await query.answer()

    # 1. Kunlik statistika tugmasi bosilganda
    if data.startswith("days:"):
        days = int(data.split(":")[1])
        stats = await AnalyticsManager.get_sales_period_stats(days)
        
        res_text = (
            f"📅 <b>Oxirgi {days} kunlik tahlil:</b>\n"
            "__________________________\n\n"
            f"🛒 <b>Sotilgan miqdor:</b> {stats['qty']:,}\n"
            f"💰 <b>Jami savdo summasi:</b> {stats['sum']:,} so'm\n"
            f"📈 <b>Sof foyda:</b> {stats['profit']:,} so'm\n"
            "__________________________\n"
            "<i>Eslatma: Foyda (Sotish - Kirim) narxi bo'yicha hisoblandi.</i>"
        )
        
        kb = [[InlineKeyboardButton("🔙 Orqaga", callback_data="main_stats")]]
        await query.edit_message_text(res_text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(kb))

    # 2. Tugayotgan mahsulotlar ro'yxati
    elif data == "low_stock_list":
        # Bazadan 20 tagacha kam qolganini olish
        low_items = await sync_to_async(list)(
            ProductVariant.objects.filter(stock__lte=F('min_stock_limit'))
            .select_related('product')[:20]
        )
        
        if not low_items:
            res_text = "✅ Hozirda barcha mahsulotlar yetarli miqdorda."
        else:
            res_text = "⚠️ <b>Zaxirasi kam qolganlar:</b>\n\n"
            for i in low_items:
                res_text += f"• {i.product.name} ({i.brand}) - <b>{i.stock}</b> {i.product.unit}\n"
        
        kb = [[InlineKeyboardButton("🔙 Orqaga", callback_data="main_stats")]]
        await query.edit_message_text(res_text, parse_mode='HTML', reply_markup=InlineKeyboardMarkup(kb))

    # 3. Asosiy sahifaga qaytish
    elif data == "main_stats":
        await analytics_dashboard(update, context)

# ---------------------------------------------------------
# 3. HANDLER REGISTRATION (Main faylga qo'shish uchun)
# ---------------------------------------------------------
# main.py faylingizda quyidagicha foydalaning:
# from analytics_handler import analytics_dashboard, analytics_callback_handler
