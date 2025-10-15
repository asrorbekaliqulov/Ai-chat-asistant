from datetime import timedelta
from django.utils.timezone import now
from django.contrib.humanize.templatetags.humanize import intcomma
from django.utils.safestring import mark_safe
from apps.Bot.models.TelegramBot import TelegramUser
from functools import lru_cache

from django.utils.translation import gettext_lazy as _
from django.views.generic import RedirectView


class DashView(RedirectView):
    pattern_name = "admin:index"


# def get_users():
#     users = TelegramUser.objects.all()
#     return list(users)


def dashboard_callback(request, context):
    context.update(random_data())
    return context


# @lru_cache
def get_users():
    users = TelegramUser.objects.all()
    return list(users)


def random_data():
    today = now()

    # Vaqt oralig‘ini aniqlash
    last_week_start = today - timedelta(days=14)
    last_week_end = today - timedelta(days=7)
    this_week_start = today - timedelta(days=7)

    last_6_to_3_days_start = today - timedelta(days=6)
    last_3_days_start = today - timedelta(days=3)
    last_2_days_start = today - timedelta(days=2)
    last_1_day_start = today - timedelta(days=1)

    # Foydalanuvchilar sonini olish
    last_week_users = TelegramUser.objects.filter(
        date_joined__range=(last_week_start, last_week_end)
    ).count()
    this_week_users = TelegramUser.objects.filter(
        date_joined__gte=this_week_start
    ).count()

    last_6_to_3_days_users = TelegramUser.objects.filter(
        date_joined__range=(last_6_to_3_days_start, last_3_days_start)
    ).count()
    last_3_days_users = TelegramUser.objects.filter(
        date_joined__gte=last_3_days_start
    ).count()

    last_2_days_users = TelegramUser.objects.filter(
        date_joined__range=(last_2_days_start, last_1_day_start)
    ).count()
    last_1_day_users = TelegramUser.objects.filter(
        date_joined__gte=last_1_day_start
    ).count()

    # O‘zgarishlarni hisoblash
    week_change = this_week_users - last_week_users
    last_3_days_change = last_3_days_users - last_6_to_3_days_users
    last_1_day_change = last_1_day_users - last_2_days_users

    # KPI formatlash
    def format_kpi(title, count, change, number):
        change_color = "text-green-700" if change >= 0 else "text-red-700"
        sign = "+" if change >= 0 else ""
        return {
            "title": title,
            "metric": f"{count} users",
            "footer": mark_safe(
                f'<strong class="{change_color} font-semibold">{sign}{intcomma(change)}</strong>&nbsp;users change from previous period'
            ),
            "number": f"Last {number} days",
        }

    return {
        "kpi": [
            format_kpi(
                "New Users in Last 1 Day", last_1_day_users, last_1_day_change, 1
            ),
            format_kpi(
                "New Users in Last 3 Days", last_3_days_users, last_3_days_change, 3
            ),
            format_kpi("New Users in Last 7 Days", this_week_users, week_change, 7),
        ],
        "tgusers": list(
            TelegramUser.objects.order_by("-date_joined").values(
                "user_id",
                "first_name",
                "username",
                "date_joined",
                "last_active",
                "is_admin",
                "is_active",
            )[
                :10
            ]  # Faqat 10 ta
        ),
    }
