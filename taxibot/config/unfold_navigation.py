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
    # {
    #     "seperator": True,
    #     "title": _("Foydalanuvchilar"),
    #     "items": [
    #         {
    #             "title": _("Guruhlar"),
    #             "icon": "person_add",
    #             "link": reverse_lazy("admin:auth_group_changelist"),
    #             "permission": lambda request: user_has_group_or_permission(
    #                 request.user, "view_group"
    #             ),
    #         },
    #         {
    #             "title": _("Foydalanuvchilar"),
    #             "icon": "person_add",
    #             "link": reverse_lazy("admin:auth_user_changelist"),
    #             "permission": lambda request: user_has_group_or_permission(
    #                 request.user, "view_user"
    #             ),
    #         },
    #     ],
    # },
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
            {
                "title": _("Chat xabarlari"),
                "icon": "chat",
                "link": reverse_lazy("admin:Bot_chatmessage_changelist"),
                "permission": lambda request: user_has_group_or_permission(
                    request.user, "view_chatmessage"
                ),
            }
        ],
    },
    {
        "seperator": True,
        "title": _("Do'kon ma'lumotlari"),
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
    {
        "seperator": True,
        "title": _("Buyurtmalar"),
        "items": [
            {
                "title": _("Buyurtmalar"),
                "icon": "orders",
                "link": reverse_lazy("admin:Bot_order_changelist"),
                "permission": lambda request: user_has_group_or_permission(
                    request.user, "view_order"
                ),
            },
            {
                "title": _("Mahsulotlar"),
                "icon": "inventory",
                "link": reverse_lazy("admin:Bot_product_changelist"),
                "permission": lambda request: user_has_group_or_permission(
                    request.user, "view_product"
                ),
            },
            {
                "title": _("Savatlar"),
                "icon": "shopping_cart",
                "link": reverse_lazy("admin:Bot_cart_changelist"),
                "permission": lambda request: user_has_group_or_permission(
                    request.user, "view_cart"
                ),
            }
        ],
    }
    
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
            {
                "title": _("Chat xabarlari"),
                "link": reverse_lazy("admin:Bot_chatmessage_changelist"),
            },
            {
                "title": _("Buyurtmalar"),
                "link": reverse_lazy("admin:Bot_order_changelist"),
            },
            {
                "title": _("Mahsulotlar"),
                "link": reverse_lazy("admin:Bot_product_changelist"),
            },
            {
                "title": _("Savatlar"),
                "link": reverse_lazy("admin:Bot_cart_changelist"),
            }
        ],
    },
]
