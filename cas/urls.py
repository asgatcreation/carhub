from django.urls import path
from . import views

app_name = 'cas'

urlpatterns = [
    path('', views.home_view, name='home'),
    # new product route: /cas/product/<brand_slug>/<product_slug>/
    path('product/<slug:brand_slug>/<slug:product_slug>/', views.product_detail, name='product_detail'),
    # keep old accessory route for compatibility
    path('accessory/<slug:slug>/', views.accessory_detail, name='accessory_detail'),
    path('category/<int:pk>/', views.category_view, name='category'),
    path('brand/<int:pk>/', views.brand_view, name='brand'),
    path('upload/', views.upload_accessory, name='upload_accessory'),
    path('upload-cas/', views.upload_accessory, name='upload_cas'),
    path('my-uploads/', views.my_uploads, name='my_uploads'),
    path('orders/', views.orders, name='orders'),
    path('profile/', views.profile, name='profile'),
    path('apply-cas-seller/', views.apply_cas_seller, name='apply_cas_seller'),
]
