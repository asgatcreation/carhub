from django.contrib import admin, messages
from django.utils.html import format_html

from .models import Car, CarImage, Cart, CartItem, Feature, Order, OrderItem, WishlistItem


class CarImageInline(admin.TabularInline):
    model = CarImage
    extra = 1
    fields = ('preview', 'image', 'image_url', 'alt_text', 'credit', 'license', 'display_order')
    readonly_fields = ('preview',)

    @admin.display(description='Preview')
    def preview(self, obj):
        if obj.pk and obj.src:
            return format_html('<img src="{}" style="height:56px;border-radius:6px" alt="">', obj.src)
        return '—'


@admin.register(Car)
class CarAdmin(admin.ModelAdmin):
    list_display = ('thumb', 'full_title', 'price_display', 'condition', 'state', 'seller', 'approval_badge', 'status', 'featured', 'created_at')
    list_display_links = ('thumb', 'full_title')
    list_filter = ('approval_status', 'status', 'condition', 'body_type', 'engine_type', 'brand', 'state', 'featured')
    list_editable = ('featured',)
    search_fields = ('brand', 'model', 'trim', 'vin', 'location', 'created_by__email')
    readonly_fields = ('slug', 'views_count', 'approved_by', 'approved_at', 'created_at', 'updated_at')
    autocomplete_fields = ('created_by',)
    filter_horizontal = ('features',)
    inlines = [CarImageInline]
    actions = ('approve_selected', 'reject_selected', 'mark_sold')
    list_per_page = 30
    fieldsets = (
        ('Listing', {'fields': ('brand', 'model', 'trim', 'year', 'price', 'created_by', 'slug')}),
        ('Specifications', {'fields': (
            ('body_type', 'condition', 'condition_grade'),
            ('mileage', 'engine_type', 'engine_size'),
            ('drivetrain', 'transmission', 'num_seats'),
            ('exterior_color', 'interior_color', 'num_previous_owners'),
            ('vin', 'warranty'), ('country_of_origin', 'duty_paid'),
        )}),
        ('Location', {'fields': (('location', 'state'),)}),
        ('Content', {'fields': ('description', 'features', 'cover_image')}),
        ('Moderation & status', {'fields': (
            ('approval_status', 'status', 'featured'), 'approval_reason', ('approved_by', 'approved_at'),
            ('views_count', 'created_at', 'updated_at'),
        )}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('created_by').prefetch_related('images')

    @admin.display(description='')
    def thumb(self, obj):
        return format_html('<img src="{}" style="width:64px;height:44px;object-fit:cover;border-radius:6px" alt="">', obj.primary_image)

    @admin.display(description='Price', ordering='price')
    def price_display(self, obj):
        return obj.price_display

    @admin.display(description='Seller', ordering='created_by__email')
    def seller(self, obj):
        return obj.created_by or '—'

    @admin.display(description='Approval', ordering='approval_status')
    def approval_badge(self, obj):
        colors = {'approved': '#15803d', 'pending': '#b45309', 'rejected': '#b91c1c'}
        return format_html('<b style="color:{}">{}</b>', colors.get(obj.approval_status, '#555'), obj.get_approval_status_display())

    @admin.action(description='Approve selected listings')
    def approve_selected(self, request, queryset):
        for car in queryset:
            car.approve(request.user)
        messages.success(request, f'Approved {queryset.count()} listing(s).')

    @admin.action(description='Reject selected listings')
    def reject_selected(self, request, queryset):
        for car in queryset:
            car.reject(request.user)
        messages.success(request, f'Rejected {queryset.count()} listing(s).')

    @admin.action(description='Mark as sold')
    def mark_sold(self, request, queryset):
        for car in queryset:
            car.status = 'sold'
            car.save(update_fields=['status', 'updated_at'])


@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    list_display = ('name', 'category')
    list_filter = ('category',)
    search_fields = ('name',)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('car', 'title', 'price', 'deposit')
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('number', 'user', 'status', 'provider', 'deposit_total', 'vehicles_total', 'created_at', 'paid_at')
    list_filter = ('status', 'provider')
    search_fields = ('number', 'user__email', 'full_name', 'payment_reference')
    readonly_fields = ('number', 'created_at', 'paid_at', 'vehicles_total', 'deposit_total', 'payment_reference')
    inlines = [OrderItemInline]


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'updated_at')
    inlines = [CartItemInline]


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ('user', 'car', 'created_at')
