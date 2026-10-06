from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = 'cars'

urlpatterns = [
    # Browse
    path('', views.browse, name='browse'),
    path('api/suggest/', views.suggest, name='suggest'),
    path('car/<slug:slug>/', views.car_detail, name='car_detail'),
    path('car/<slug:slug>/message/', views.contact_seller, name='contact_seller'),
    path('seller/<int:seller_id>/', views.seller_profile, name='seller_profile'),

    # Cart, saved cars, checkout, orders
    path('cart/', views.cart_view, name='cart'),
    path('cart/add/<int:car_id>/', views.cart_add, name='cart_add'),
    path('cart/remove/<int:car_id>/', views.cart_remove, name='cart_remove'),
    path('saved/', views.wishlist_view, name='saved'),
    path('saved/toggle/<int:car_id>/', views.wishlist_toggle, name='wishlist_toggle'),
    path('checkout/', views.checkout, name='checkout'),
    path('checkout/review/', views.checkout_review, name='checkout_review'),
    path('checkout/paystack/callback/', views.paystack_callback, name='paystack_callback'),
    path('webhooks/paystack/', views.paystack_webhook, name='paystack_webhook'),
    path('orders/', views.orders, name='orders'),
    path('orders/<str:number>/', views.order_detail, name='order_detail'),
    path('orders/item/<int:item_id>/cancel/', views.order_item_cancel, name='order_item_cancel'),
    path('reservations/', views.sales, name='sales'),
    path('reservations/<int:item_id>/', views.sale_action, name='sale_action'),

    # Selling
    path('sell/', views.sell, name='sell'),
    path('sell/new/', views.listing_create, name='listing_create'),
    path('my-listings/', views.my_listings, name='my_listings'),
    path('my-listings/<slug:slug>/edit/', views.listing_edit, name='listing_edit'),
    path('my-listings/<slug:slug>/status/', views.listing_status, name='listing_status'),

    # Moderation (staff)
    path('moderation/', views.moderation, name='moderation'),
    path('moderation/<int:car_id>/', views.moderate, name='moderate'),

    # Old URLs kept as redirects
    path('listings/', RedirectView.as_view(pattern_name='cars:browse', query_string=True)),
    path('category/<str:category>/', views.legacy_category),
    path('statement-search/', views.legacy_search),
    path('sell-car/', RedirectView.as_view(pattern_name='cars:sell')),
    path('upload-car/', RedirectView.as_view(pattern_name='cars:listing_create')),
    path('my-uploads/', RedirectView.as_view(pattern_name='cars:my_listings')),
    path('wishlist/', RedirectView.as_view(pattern_name='cars:saved')),
    path('saved-items/', RedirectView.as_view(pattern_name='cars:saved')),
    path('pending-uploads/', RedirectView.as_view(pattern_name='cars:moderation')),
]
