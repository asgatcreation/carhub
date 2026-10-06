from django.db import models
from django.utils.text import slugify
from django.contrib.auth import get_user_model

User = get_user_model()

class Category(models.Model):
	name = models.CharField(max_length=100)
	description = models.TextField(blank=True)
	image = models.ImageField(upload_to='category_images/', blank=True, null=True)

	def __str__(self):
		return self.name

class Brand(models.Model):
	name = models.CharField(max_length=100)
	description = models.TextField(blank=True)
	logo = models.ImageField(upload_to='brand_logos/', blank=True, null=True)
	slug = models.SlugField(max_length=120, unique=True, blank=True)

	def __str__(self):
		return self.name

	def save(self, *args, **kwargs):
		# auto-generate slug from name if not provided
		if not self.slug and self.name:
			base = slugify(self.name)[:110]
			slug = base
			i = 1
			while Brand.objects.filter(slug=slug).exclude(pk=self.pk).exists():
				slug = f"{base}-{i}"
				i += 1
			self.slug = slug
		super().save(*args, **kwargs)

	@property
	def units_sold(self):
		"""Denormalized view: sum of quantities from related orders."""
		return self.orders.aggregate(total=models.Sum('quantity'))['total'] or 0

	@property
	def average_rating(self):
		"""Average rating computed from AccessoryReview entries."""
		from django.db.models import Avg
		res = self.reviews.aggregate(avg=Avg('rating'))
		return float(res['avg']) if res and res['avg'] is not None else None

class Accessory(models.Model):
	name = models.CharField(max_length=200)
	slug = models.SlugField(max_length=220, unique=True, blank=True)
	description = models.TextField()
	price = models.DecimalField(max_digits=10, decimal_places=2)
	image = models.ImageField(upload_to='accessory_images/')
	video_url = models.URLField(blank=True, null=True)
	category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='accessories')
	brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, related_name='accessories')
	in_stock = models.BooleanField(default=True)
	seller = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='accessories')
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return self.name

	def save(self, *args, **kwargs):
		# auto-generate slug from name if not provided
		if not self.slug:
			base = slugify(self.name)[:200]
			slug = base
			# ensure uniqueness
			i = 1
			while Accessory.objects.filter(slug=slug).exclude(pk=self.pk).exists():
				slug = f"{base}-{i}"
				i += 1
			self.slug = slug
		super().save(*args, **kwargs)


class AccessoryImage(models.Model):
	accessory = models.ForeignKey(Accessory, on_delete=models.CASCADE, related_name='images')
	image = models.ImageField(upload_to='accessory_images_gallery/')
	caption = models.CharField(max_length=200, blank=True)

	def __str__(self):
		return f"Image for {self.accessory.name}"


class AccessoryAttribute(models.Model):
	accessory = models.ForeignKey(Accessory, on_delete=models.CASCADE, related_name='attributes')
	name = models.CharField(max_length=100)
	value = models.CharField(max_length=200)

	def __str__(self):
		return f"{self.name}: {self.value}"

class Order(models.Model):
	STATUS_CHOICES = [
		('pending', 'Pending'),
		('processing', 'Processing'),
		('completed', 'Completed'),
		('cancelled', 'Cancelled'),
	]
	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='accessory_orders')
	accessory = models.ForeignKey(Accessory, on_delete=models.CASCADE, related_name='orders')
	quantity = models.PositiveIntegerField(default=1)
	status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return f"Order #{self.id} - {self.accessory.name}"

class AccessoryReview(models.Model):
	accessory = models.ForeignKey(Accessory, on_delete=models.CASCADE, related_name='reviews')
	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='accessory_reviews')
	rating = models.PositiveIntegerField(default=5)
	comment = models.TextField(blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	def __str__(self):
		return f"Review by {self.user.username} for {self.accessory.name}"
