from django.contrib import admin
# Register your DriverZone models here
from .models import Driver, Service, Ride, DriverReview

@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
	list_display = ('user', 'car_make', 'car_model', 'car_year', 'car_plate_number', 'is_available', 'license_verified', 'daily_rate')
	search_fields = ('user__username', 'car_make', 'car_model', 'car_plate_number')

@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
	list_display = ('name', 'price')
	search_fields = ('name',)

@admin.register(Ride)
class RideAdmin(admin.ModelAdmin):
	list_display = ('user', 'driver', 'pickup', 'dropoff', 'order_type', 'status', 'created_at')
	list_filter = ('order_type', 'status')
	search_fields = ('user__username', 'driver__user__username', 'pickup', 'dropoff')

@admin.register(DriverReview)
class DriverReviewAdmin(admin.ModelAdmin):
	list_display = ('driver', 'user', 'rating', 'created_at')
	search_fields = ('driver__user__username', 'user__username')
