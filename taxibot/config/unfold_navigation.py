from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _


def user_has_group_or_permission(user, permission):
    if user.is_superuser:
        return True

    group_names = user.groups.values_list("name", flat=True)
    if not group_names:
        return True

    return user.groups.filter(permissions__codename=permission).exists()


PAGES = [
    {
        "seperator": True,
        "items": [
            {
                "title": _("Bosh sahifa"),
                "icon": "home",
                "link": reverse_lazy("admin:index"),
            },
        ],
    },
    {
        "seperator": True,
        "title": _("Foydalanuvchilar"),
        "items": [
            {
                "title": _("Guruhlar"),
                "icon": "person_add",
                "link": reverse_lazy("admin:auth_group_changelist"),
                "permission": lambda request: user_has_group_or_permission(
                    request.user, "view_group"
                ),
            },
            {
                "title": _("Foydalanuvchilar"),
                "icon": "person_add",
                "link": reverse_lazy("admin:auth_user_changelist"),
                "permission": lambda request: user_has_group_or_permission(
                    request.user, "view_user"
                ),
            },
        ],
    },
    {
        "seperator": True,
        "title": _("Telegram Bot"),
        "items": [
            {
                "title": _("Bot Foydalanuvchilar"),
                "icon": "person",
                "link": reverse_lazy("admin:Bot_telegramuser_changelist"),
                "permission": lambda request: user_has_group_or_permission(
                    request.user, "view_telegramuser"
                ),
            },
        ],
    },
    {
        "seperator": True,
        "title": _("Kampaniya ma'lumotlari"),
        "items": [
            {
                "title": _("Ma'lumotlar"),
                "icon": "info",
                "link": reverse_lazy("admin:Bot_companydata_changelist"),
                "permission": lambda request: user_has_group_or_permission(
                    request.user, "view_companydata"
                ),
            }
        ],
    },
    
]

TABS = [
    {
        "models": [
            "auth.user",
            "auth.group",
            "Bot.telegramuser",
        ],
        "items": [
            {
                "title": _("Foydalanuvchilar"),
                "link": reverse_lazy("admin:auth_user_changelist"),
            },
            {
                "title": _("Guruhlar"),
                "link": reverse_lazy("admin:auth_group_changelist"),
            },
            {
                "title": _("Bot Foydalanuvchilari"),
                "link": reverse_lazy("admin:Bot_telegramuser_changelist"),
            },
            {
                "title": _("Ma'lumotlar"),
                "link": reverse_lazy("admin:Bot_companydata_changelist"),
            },
        ],
    },
]
