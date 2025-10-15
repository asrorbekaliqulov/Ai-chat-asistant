from django.contrib import admin
from ..models.TelegramBot import TelegramUser, CompanyData
from unfold.admin import ModelAdmin


@admin.register(TelegramUser)
class UserAdmin(ModelAdmin):
    list_display = (
        "user_id",
        "first_name",
        "username",
        "is_active",
        "is_admin",
        "date_joined",
        "last_active",
    )
    list_filter = ("is_active", "is_admin")
    search_fields = ("username", "first_name")
    ordering = ("user_id",)
    list_editable = ("is_active", "is_admin")


@admin.register(CompanyData)
class CompanyDataAdmin(ModelAdmin):
    list_display = ("id", "content")
