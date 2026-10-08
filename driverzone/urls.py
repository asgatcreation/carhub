from django.urls import path

from . import views

app_name = 'driverzone'

urlpatterns = [
    path('', views.home, name='home'),
    path('book/', views.book, name='book'),
    path('trips/', views.trips, name='trips'),
    path('trips/<str:number>/', views.trip, name='trip'),
    path('trips/<str:number>/cancel/', views.trip_cancel, name='trip_cancel'),
    path('trips/<str:number>/rate/', views.trip_rate, name='trip_rate'),
    path('chauffeurs/', views.drivers, name='drivers'),
    path('chauffeurs/<int:pk>/', views.driver, name='driver'),
    path('drive/', views.drive, name='drive'),
    path('driver-app/', views.dashboard, name='dashboard'),
    path('driver-app/trips/<str:number>/', views.driver_action, name='driver_action'),

    path('api/quote/', views.api_quote, name='api_quote'),
    path('api/nearby/', views.api_nearby, name='api_nearby'),
    path('api/trips/<str:number>/live/', views.api_live, name='api_live'),
    path('api/driver/state/', views.api_driver_state, name='api_driver_state'),
    path('api/driver/location/', views.api_driver_location, name='api_driver_location'),
    path('api/driver/online/', views.api_driver_online, name='api_driver_online'),
]
