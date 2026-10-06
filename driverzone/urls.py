from django.urls import path
from . import views

urlpatterns = [
    path('', views.home_view, name='home'),
    path('driver/<int:pk>/', views.driver_detail, name='driver_detail'),
    path('order-driver/<int:pk>/', views.order_driver, name='order_driver'),
    path('my-rides/', views.my_rides, name='my_rides'),
    path('profile/', views.profile, name='profile'),
    path('order-confirmation/<int:pk>/', views.order_confirmation, name='order_confirmation'),
    path('ride/<int:pk>/update-status/', views.update_ride_status, name='update_ride_status'),
    path('ride/<int:pk>/accept/', views.accept_ride, name='accept_ride'),
    path('ride/<int:pk>/decline/', views.decline_ride, name='decline_ride'),
    path('driver/<int:pk>/publish-toggle/', views.publish_driver, name='publish_driver'),
    path('assigned-rides/', views.assigned_rides, name='assigned_rides'),
    path('apply-pilot/', views.apply_pilot, name='apply_pilot'),
    path('toggle-availability/', views.toggle_availability, name='toggle_availability'),
]
