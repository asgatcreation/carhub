from django.urls import path

from . import views

app_name = 'cas'

urlpatterns = [
    path('', views.home, name='home'),
    path('shop/', views.shop, name='shop'),
    path('c/<slug:category_slug>/', views.shop, name='category'),
    path('p/<slug:slug>/', views.product, name='product'),
    path('p/<slug:slug>/review/', views.review_submit, name='review'),
    path('my-car/', views.garage_set, name='garage_set'),
    path('my-car/clear/', views.garage_clear, name='garage_clear'),

    path('cart/', views.cart, name='cart'),
    path('cart/add/<int:product_id>/', views.cart_add, name='cart_add'),
    path('cart/update/<int:product_id>/', views.cart_update, name='cart_update'),
    path('checkout/', views.checkout, name='checkout'),
    path('checkout/paystack/callback/', views.paystack_callback, name='paystack_callback'),
    path('orders/', views.orders, name='orders'),
    path('orders/<str:number>/', views.order_detail, name='order_detail'),
    path('orders/item/<int:item_id>/cancel/', views.order_item_cancel, name='order_item_cancel'),

    path('sell/', views.sell, name='sell'),
    path('vendor/', views.vendor, name='vendor'),
    path('vendor/orders/', views.vendor_orders, name='vendor_orders'),
    path('vendor/orders/<int:item_id>/', views.vendor_item_action, name='vendor_item_action'),
    path('vendor/products/new/', views.product_form, name='product_create'),
    path('vendor/products/<slug:slug>/edit/', views.product_form, name='product_edit'),
    path('vendor/products/<slug:slug>/quick/', views.product_quick_update, name='product_quick'),
    path('vendor/products/<slug:slug>/photos/<int:image_id>/delete/', views.product_image_delete, name='product_image_delete'),
]
