from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class Driver(models.Model):
	user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='driver_profile')
	bio = models.TextField(blank=True)
	photo = models.ImageField(upload_to='driver_photos/', blank=True, null=True)
	rating = models.DecimalField(max_digits=3, decimal_places=2, default=5.0)
	is_available = models.BooleanField(default=True)
	license_number = models.CharField(max_length=50)
	license_verified = models.BooleanField(default=False)
	experience_years = models.PositiveIntegerField(default=0)
	vehicle_types = models.CharField(max_length=200, blank=True, help_text='Comma-separated list of vehicle types the driver has experience with')
	daily_rate = models.DecimalField(max_digits=9, decimal_places=2, default=0.0)
	languages_spoken = models.CharField(max_length=200, blank=True, help_text='Comma-separated list of languages')
	# Car details
	car_make = models.CharField(max_length=100)
	car_model = models.CharField(max_length=100)
	car_year = models.PositiveIntegerField()
	car_color = models.CharField(max_length=50)
	car_plate_number = models.CharField(max_length=20)
	car_image = models.ImageField(upload_to='driver_car_images/', blank=True, null=True)
	car_description = models.TextField(blank=True)

	def __str__(self):
		return self.user.get_full_name() or self.user.username

class Service(models.Model):
	name = models.CharField(max_length=100)
	description = models.TextField(blank=True)
	price = models.DecimalField(max_digits=10, decimal_places=2)

	def __str__(self):
		return self.name


class Ride(models.Model):
	STATUS_CHOICES = [
		('pending', 'Pending'),
		('accepted', 'Accepted'),
		('declined', 'Declined'),
		('ongoing', 'Ongoing'),
		('completed', 'Completed'),
		('cancelled', 'Cancelled'),
	]
	ORDER_TYPE_CHOICES = [
		('hourly', 'Hourly'),
		('allday', 'All Day'),
		('interstate', 'Inter State'),
		('intercity', 'Inter City'),
		('weekly', 'Weekly'),
	]
	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='rides')
	driver = models.ForeignKey(Driver, on_delete=models.SET_NULL, null=True, related_name='rides')
	pickup = models.CharField(max_length=200)
	dropoff = models.CharField(max_length=200)
	order_type = models.CharField(max_length=20, choices=ORDER_TYPE_CHOICES, default='hourly')
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return f"Ride #{self.id} - {self.user.username}"

class DriverReview(models.Model):
	driver = models.ForeignKey(Driver, on_delete=models.CASCADE, related_name='reviews')
	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='driver_reviews')
	rating = models.PositiveIntegerField(default=5)
	comment = models.TextField(blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return f"Review by {self.user.username} for {self.driver.user.username}"
