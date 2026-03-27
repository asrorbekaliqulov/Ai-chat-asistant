from django.urls import path
from .views import base

urlpatterns = [
    path("chat/", base.admin_chat_page, name="warehouse_chat"),
    path("pandasai-query/", base.pandasai_query, name="pandasai_query"),
    path('add-product/', base.add_product_page, name='add_product_page'),
    path('analyze-vision/', base.analyze_product_image, name='analyze_product_image'),
    path('save-product/', base.save_final_product, name='save_final_product'),
]
