from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone

from .forms.user import CustomUserChangeForm, CustomUserCreationForm
from .models import Application, Conversation, CustomUser, Message, Notification, Profile, Review


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser
    list_display = ['email', 'first_name', 'last_name', 'is_staff', 'is_active', 'date_joined']
    list_filter = ['is_staff', 'is_active']
    fieldsets = (
        (None, {'fields': ('email', 'username', 'password')}),
        ('Personal', {'fields': ('first_name', 'last_name')}),
        ('Permissions', {'fields': ('is_staff', 'is_active', 'is_superuser', 'groups', 'user_permissions')}),
    )
    add_fieldsets = ((None, {'classes': ('wide',), 'fields': ('email', 'username', 'password1', 'password2', 'is_staff', 'is_active')}),)
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'company_name', 'phone', 'city', 'is_verified', 'is_car_seller_approved', 'responses_count', 'sold_count']
    list_filter = ['is_verified', 'is_car_seller_approved']
    search_fields = ['user__email', 'company_name', 'phone']
    fieldsets = (
        (None, {'fields': ('user', 'profile_image', 'phone', 'whatsapp_number', 'city', 'bio')}),
        ('Business', {'fields': ('company_name', 'company_logo', 'business_description', 'years_in_business', 'specialization')}),
        ('Trust', {'fields': ('is_verified', 'is_car_seller_approved', 'chat_enabled')}),
        ('Stats', {'fields': ('responses_count', 'avg_response_seconds', 'sold_count', 'completed_transactions')}),
    )
    readonly_fields = ('user',)


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'company_name', 'status', 'applied_at', 'reviewed_by']
    list_filter = ['status', 'role']
    search_fields = ['user__email', 'company_name', 'full_name']
    actions = ['approve']

    @admin.action(description='Approve and verify selected sellers')
    def approve(self, request, queryset):
        for app in queryset.filter(status='pending'):
            app.status, app.reviewed_by, app.reviewed_at = 'approved', request.user, timezone.now()
            app.save()
            Profile.objects.filter(user=app.user).update(is_car_seller_approved=True, is_verified=True)


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ('sender', 'content', 'created_at', 'read')


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['id', 'car', 'created_at', 'updated_at']
    inlines = [MessageInline]


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['profile', 'reviewer', 'rating', 'title', 'created_at']
    search_fields = ['profile__user__email', 'reviewer__email', 'body']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'verb', 'message', 'unread', 'created_at']
    list_filter = ['verb', 'unread']
