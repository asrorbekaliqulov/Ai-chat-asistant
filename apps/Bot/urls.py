from django.urls import path
from .views import base

urlpatterns = [
    path("chat/", base.admin_chat_page, name="bot_chat"),
    path("pandasai-query/", base.pandasai_query, name="pandasai_query"),
]
