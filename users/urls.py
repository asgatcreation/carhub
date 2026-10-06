from django.urls import path
from django.views.generic import RedirectView

from . import views

app_name = 'users'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('settings/', views.settings_view, name='settings'),
    path('inbox/', views.inbox, name='inbox'),
    path('conversation/<int:convo_id>/', views.conversation, name='conversation'),
    path('conversation/<int:convo_id>/poll/', views.conversation_poll, name='conversation_poll'),
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/mark-read/', views.notifications_mark_read, name='notifications_mark_read'),
    path('verify/', views.apply_seller, name='apply_seller'),
    path('applications/', views.applications, name='applications'),

    # Old URLs kept as redirects
    path('profile/', RedirectView.as_view(pattern_name='users:settings')),
    path('cart/', RedirectView.as_view(pattern_name='cars:cart')),
    path('wishlist/', RedirectView.as_view(pattern_name='cars:saved')),
    path('saved-items/', RedirectView.as_view(pattern_name='cars:saved')),
    path('my-uploads/', RedirectView.as_view(pattern_name='cars:my_listings')),
    path('transactions/', RedirectView.as_view(pattern_name='cars:orders')),
    path('checkout/', RedirectView.as_view(pattern_name='cars:checkout')),
    path('logout/', RedirectView.as_view(pattern_name='account_logout')),
]
