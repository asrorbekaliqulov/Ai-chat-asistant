from django.urls import path
from .views import base

urlpatterns = [
    path("chat/", base.admin_chat_page, name="warehouse_chat"),
    path("pandasai-query/", base.pandasai_query, name="pandasai_query"),
    path('add-product/', base.add_product_page, name='add_product_page'),
    
    # Mahsulotlarni nomi bo'yicha jonli qidirish (Live Search)
    path('search-products/', base.search_products, name='search_products'),
    
    # Barcha ma'lumotlarni (Product + Variants) bitta paketda saqlash
    path('save-mega-product/', base.save_mega_product, name='save_mega_product'),
]
