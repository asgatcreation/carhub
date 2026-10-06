from django.contrib import admin
# Register your CAS models here
from .models import Accessory, Category, Brand, Order, AccessoryReview
from .models import AccessoryImage
from .models import AccessoryAttribute

@admin.register(Accessory)
class AccessoryAdmin(admin.ModelAdmin):
	list_display = ('name', 'category', 'brand', 'price', 'in_stock', 'seller', 'created_at')
	list_filter = ('category', 'brand', 'in_stock')
	search_fields = ('name', 'category__name', 'brand__name', 'seller__username')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
	list_display = ('name', 'description')
	search_fields = ('name',)

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
	list_display = ('name', 'slug', 'description')
	search_fields = ('name','slug')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
	list_display = ('user', 'accessory', 'quantity', 'status', 'created_at')
	list_filter = ('status',)
	search_fields = ('user__username', 'accessory__name')

@admin.register(AccessoryReview)
class AccessoryReviewAdmin(admin.ModelAdmin):
	list_display = ('accessory', 'user', 'rating', 'created_at')
	search_fields = ('accessory__name', 'user__username')

@admin.register(AccessoryImage)
class AccessoryImageAdmin(admin.ModelAdmin):
	list_display = ('accessory', 'image')


@admin.register(AccessoryAttribute)
class AccessoryAttributeAdmin(admin.ModelAdmin):
	list_display = ('accessory', 'name', 'value')

