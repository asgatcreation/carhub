# users/models.py (updated with correction_requested status)
from django.db import models
from django.contrib.auth.models import AbstractUser, UserManager as BaseUserManager
from django.utils import timezone

# Custom manager to handle email as primary identifier
class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)

# Nigerian states
NIGERIAN_STATES = [
    ('Abia', 'Abia'),
    ('Adamawa', 'Adamawa'),
    ('Akwa Ibom', 'Akwa Ibom'),
    ('Anambra', 'Anambra'),
    ('Bauchi', 'Bauchi'),
    ('Bayelsa', 'Bayelsa'),
    ('Benue', 'Benue'),
    ('Borno', 'Borno'),
    ('Cross River', 'Cross River'),
    ('Delta', 'Delta'),
    ('Ebonyi', 'Ebonyi'),
    ('Edo', 'Edo'),
    ('Ekiti', 'Ekiti'),
    ('Enugu', 'Enugu'),
    ('FCT', 'Federal Capital Territory'),
    ('Gombe', 'Gombe'),
    ('Imo', 'Imo'),
    ('Jigawa', 'Jigawa'),
    ('Kaduna', 'Kaduna'),
    ('Kano', 'Kano'),
    ('Katsina', 'Katsina'),
    ('Kebbi', 'Kebbi'),
    ('Kogi', 'Kogi'),
    ('Kwara', 'Kwara'),
    ('Lagos', 'Lagos'),
    ('Nasarawa', 'Nasarawa'),
    ('Niger', 'Niger'),
    ('Ogun', 'Ogun'),
    ('Ondo', 'Ondo'),
    ('Osun', 'Osun'),
    ('Oyo', 'Oyo'),
    ('Plateau', 'Plateau'),
    ('Rivers', 'Rivers'),
    ('Sokoto', 'Sokoto'),
    ('Taraba', 'Taraba'),
    ('Yobe', 'Yobe'),
    ('Zamfara', 'Zamfara'),
]

GENDER_CHOICES = [
    ('male', 'Male'),
    ('female', 'Female'),
    ('other', 'Other'),
    ('prefer_not_to_say', 'Prefer not to say'),
]

RACE_CHOICES = [
    ('african', 'African'),
    ('asian', 'Asian'),
    ('caucasian', 'Caucasian'),
    ('hispanic', 'Hispanic'),
    ('native_american', 'Native American'),
    ('pacific_islander', 'Pacific Islander'),
    ('other', 'Other'),
    ('prefer_not_to_say', 'Prefer not to say'),
]

# Create your models here.
class CustomUser(AbstractUser):
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=True, blank=True, null=True)  # Optional

    objects = CustomUserManager()  # Use the custom manager

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email

class Profile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    middle_name = models.CharField(max_length=30, blank=True)
    bio = models.TextField(blank=True)
    phone = models.CharField(max_length=15, blank=True)
    id_document = models.FileField(upload_to='id_documents/', blank=True, null=True)
    gender = models.CharField(max_length=10, blank=True)
    race = models.CharField(max_length=50, blank=True)
    state_of_origin = models.CharField(max_length=100, blank=True)
    lga_of_origin = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    profile_image = models.ImageField(upload_to='profile_images/', blank=True, null=True)
    # Auto-generated thumbnails (small & medium) stored alongside original
    profile_image_small = models.ImageField(upload_to='profile_images/thumbnails/', blank=True, null=True)
    profile_image_medium = models.ImageField(upload_to='profile_images/thumbnails/', blank=True, null=True)
    # Predefined avatar choice (e.g. 'c1','c2'...) if user selects a built-in avatar
    avatar_choice = models.CharField(max_length=64, blank=True, null=True)
    is_car_seller_approved = models.BooleanField(default=False)
    is_cas_seller_approved = models.BooleanField(default=False)
    is_pilot_approved = models.BooleanField(default=False)
    receive_news = models.BooleanField(default=False)
    # Allow seller to enable/disable direct chat from listings/car pages
    chat_enabled = models.BooleanField(default=True)
    # New seller/account classification
    SELLER_TYPE_CHOICES = [
        ('private', 'Private Seller'),
        ('dealer', 'Car Dealer'),
        ('accessory', 'Accessories Vendor'),
        ('driver', 'Driver'),
    ]
    seller_type = models.CharField(max_length=20, choices=SELLER_TYPE_CHOICES, blank=True)

    # Business display fields (for dealers/vendors)
    company_name = models.CharField(max_length=200, blank=True)
    company_logo = models.ImageField(upload_to='company_logos/', blank=True, null=True)
    whatsapp_number = models.CharField(max_length=32, blank=True, help_text='Optional WhatsApp contact number')
    # Profile accent/theme color (hex). Used to brand the profile header.
    theme_color = models.CharField(max_length=7, default='#0d6efd', help_text='Hex color used for profile accents, e.g. #0d6efd')

    # About / Business fields
    business_description = models.TextField(blank=True, help_text='Business description or extended bio')
    years_in_business = models.PositiveSmallIntegerField(null=True, blank=True, help_text='Years in business (numeric)')
    specialization = models.CharField(max_length=255, blank=True, help_text='Primary specialization or services offered')
    certifications = models.TextField(blank=True, help_text='Certifications or accreditations (comma separated or list)')
    why_choose = models.TextField(blank=True, help_text='Short note telling customers why they should choose this seller')
    # Trust & analytics fields
    is_verified = models.BooleanField(default=False)
    total_views = models.PositiveIntegerField(default=0)
    total_inquiries = models.PositiveIntegerField(default=0)
    avg_response_seconds = models.PositiveIntegerField(default=0)
    sold_count = models.PositiveIntegerField(default=0)
    active_listings_count = models.PositiveIntegerField(default=0)
    # Response tracking: how many inquiries received vs responded to
    responses_count = models.PositiveIntegerField(default=0)
    # Completed transactions separate from sold_count if you need distinct accounting
    completed_transactions = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.user.username}'s Profile"

    @property
    def display_name(self):
        """Return company name for business accounts, else full user name."""
        if self.company_name:
            return self.company_name
        full = ' '.join(filter(None, [self.user.first_name, self.user.last_name]))
        return full or (self.user.username or self.user.email)

    @property
    def member_since(self):
        return getattr(self.user, 'date_joined', None)

    def get_overall_rating(self):
        """Compute average rating from related Review objects."""
        try:
            qs = self.reviews.approved()
            if not qs.exists():
                return None
            agg = qs.aggregate(models.Avg('rating'))
            return float(agg.get('rating__avg') or 0.0)
        except Exception:
            return None

    def review_count(self):
        try:
            return self.reviews.approved().count()
        except Exception:
            return 0

    def get_theme_color(self):
        try:
            c = self.theme_color or '#0d6efd'
            if not c.startswith('#'):
                c = f'#{c}'
            return c
        except Exception:
            return '#0d6efd'

    @property
    def response_rate_percent(self):
        """Return response rate as integer percent (responses / inquiries * 100) or None."""
        try:
            if not self.total_inquiries:
                return None
            return int(round((float(self.responses_count or 0) / float(self.total_inquiries)) * 100))
        except Exception:
            return None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_image = self.profile_image.name if self.profile_image else ''

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        current = self.profile_image.name if self.profile_image else ''
        if current and current != self._original_image:
            self._generate_thumbnails()
        self._original_image = current

    def _generate_thumbnails(self):
        """Create small/medium JPEG thumbnails once, when the profile photo changes."""
        import io
        import os

        from django.core.files.base import ContentFile
        from PIL import Image, ImageOps

        try:
            self.profile_image.open('rb')
            img = ImageOps.exif_transpose(Image.open(self.profile_image)).convert('RGB')
        except Exception:
            return
        base = os.path.splitext(os.path.basename(self.profile_image.name))[0]
        for field, size, suffix in (('profile_image_medium', 800, 'med'), ('profile_image_small', 200, 'sm')):
            thumb = img.copy()
            thumb.thumbnail((size, size), Image.LANCZOS)
            buffer = io.BytesIO()
            thumb.save(buffer, format='JPEG', quality=85)
            old = getattr(self, field)
            if old:
                old.delete(save=False)
            getattr(self, field).save(f'{base}_{suffix}.jpg', ContentFile(buffer.getvalue()), save=False)
        # update_fields keeps this from re-triggering thumbnail generation
        super().save(update_fields=['profile_image_small', 'profile_image_medium'])

    @property
    def avatar_url(self):
        image = self.profile_image_small or self.profile_image
        return image.url if image else ''

    @property
    def roles(self):
        roles_list = []
        if self.is_car_seller_approved: roles_list.append('Car Seller')
        if self.is_cas_seller_approved: roles_list.append('CAS Seller')
        if self.is_pilot_approved: roles_list.append('Pilot')
        return ', '.join(roles_list) or 'Normal User'


class Verification(models.Model):
    """Records verification steps for a profile (ID, phone, business documents, license).

    - `profile` : Profile being verified
    - `method` : ID, Phone, CAC, Insurance, License
    - `status` : pending/verified/rejected
    - `data` : optional JSON/details
    """
    VERIF_METHODS = [
        ('id', 'ID Document'),
        ('phone', 'Phone'),
        ('cac', 'CAC/Business Reg'),
        ('license', 'Driver License'),
        ('insurance', 'Insurance'),
    ]
    STATUS = [
        ('pending', 'Pending'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    ]
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='verifications')
    method = models.CharField(max_length=20, choices=VERIF_METHODS)
    status = models.CharField(max_length=20, choices=STATUS, default='pending')
    notes = models.TextField(blank=True)
    evidence = models.FileField(upload_to='verifications/', blank=True, null=True)
    reviewed_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='verification_reviews')
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('profile', 'method')

    def __str__(self):
        return f"{self.profile.user.email} - {self.method} ({self.status})"


from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


class ReviewQuerySet(models.QuerySet):
    def approved(self):
        return self.filter(status='approved')


class Review(models.Model):
    """Generic review attached to a Profile (as seller/driver) or to a Car/Accessory via profile.

    Ratings: overall + category breakdown. New reviews wait for a moderator before they are public.
    """
    STATUS_CHOICES = [('pending', 'Awaiting moderation'), ('approved', 'Published'), ('rejected', 'Rejected')]

    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='reviews')
    reviewer = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=5.0)
    communication = models.PositiveSmallIntegerField(default=5)
    punctuality = models.PositiveSmallIntegerField(default=5)
    condition = models.PositiveSmallIntegerField(default=5)
    professionalism = models.PositiveSmallIntegerField(default=5)
    title = models.CharField(max_length=255, blank=True)
    body = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', db_index=True)
    moderated_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='moderated_reviews')
    moderated_at = models.DateTimeField(null=True, blank=True)
    moderation_note = models.CharField(max_length=300, blank=True)

    objects = ReviewQuerySet.as_manager()

    def __str__(self):
        return f"Review {self.id} for {self.profile.user.email} - {self.rating}"


class SavedItem(models.Model):
    """Allow users to save generic objects (Car, Accessory, Driver profile) using GenericForeignKey."""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='saved_items')
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'content_type', 'object_id')

    def __str__(self):
        return f"Saved {self.content_type} for {self.user.email}"


class Subscription(models.Model):
    """Subscription plan for sellers/dealers."""
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='subscriptions')
    plan_name = models.CharField(max_length=120)
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=False)
    benefits = models.TextField(blank=True)

    def __str__(self):
        return f"{self.profile.user.email} - {self.plan_name} ({'active' if self.is_active else 'inactive'})"


class Wallet(models.Model):
    """Simple wallet for a profile to hold balance credits/debits."""
    profile = models.OneToOneField(Profile, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def __str__(self):
        return f"Wallet for {self.profile.user.email} - {self.balance}"


class WalletTransaction(models.Model):
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    TYPE_CHOICES = [('credit', 'Credit'), ('debit', 'Debit')]
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    reference = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.type.title()} {self.amount} for {self.wallet.profile.user.email}"


class Transaction(models.Model):
    """Generic transaction record for sales/purchases/service bookings."""
    TRANS_TYPES = [
        ('sale', 'Sale'),
        ('purchase', 'Purchase'),
        ('service', 'Service'),
    ]
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANS_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=8, default='NGN')
    related_object_ct = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.SET_NULL)
    related_object_id = models.PositiveIntegerField(null=True, blank=True)
    related_object = GenericForeignKey('related_object_ct', 'related_object_id')
    status = models.CharField(max_length=30, default='completed')
    reference = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction_type} {self.amount} ({self.currency}) for {self.profile.user.email}"


class ServiceBooking(models.Model):
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='service_bookings')
    booked_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='service_requests')
    title = models.CharField(max_length=200)
    details = models.TextField(blank=True)
    scheduled_for = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=30, default='scheduled')
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"ServiceBooking {self.id} for {self.profile.user.email} - {self.status}"

class Application(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('correction_requested', 'Correction Requested'),
    ]
    ROLE_CHOICES = [
        ('car_seller', 'Car Seller'),
        ('cas_seller', 'CAS Seller'),
        ('pilot', 'Pilot'),
    ]
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    applied_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_applications')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    # Additional applicant details
    full_name = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)
    id_type = models.CharField(max_length=100, blank=True)
    id_number = models.CharField(max_length=100, blank=True)
    company_name = models.CharField(max_length=200, blank=True)
    vehicle_details = models.CharField(max_length=300, blank=True)
    experience_years = models.PositiveIntegerField(default=0)
    additional_info = models.TextField(blank=True)
    documents = models.FileField(upload_to='application_documents/', blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.role} ({self.status})"


class Conversation(models.Model):
    participants = models.ManyToManyField(CustomUser, related_name='conversations')
    car = models.ForeignKey('cars.Car', on_delete=models.SET_NULL, null=True, blank=True, related_name='conversations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"Conversation #{self.id} - {', '.join([u.email for u in self.participants.all()][:3])}"

    def other_participant(self, user):
        return next((p for p in self.participants.all() if p.pk != user.pk), None)


# Ensure a Wallet exists for each Profile
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=Profile)
def ensure_wallet(sender, instance, created, **kwargs):
    try:
        # avoid creating wallet if migrations/tables are not yet available
        from django.db import connection
        tables = []
        try:
            tables = connection.introspection.table_names()
        except Exception:
            tables = []
        if 'users_wallet' not in tables:
            return
        if created:
            Wallet.objects.create(profile=instance, balance=0)
        else:
            # if wallet missing, create it
            Wallet.objects.get_or_create(profile=instance, defaults={'balance': 0})
    except Exception:
        # Fail silently; wallet is non-critical
        pass


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Message {self.id} from {self.sender.email}"


class ProfileImage(models.Model):
    """Additional images uploaded by users for their profile gallery.

    - Linked to `Profile`.
    - `is_primary` indicates a preferred image (used for avatar/thumbnail).
    """
    profile = models.ForeignKey(Profile, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='profile_images/gallery/')
    is_primary = models.BooleanField(default=False)
    caption = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_primary', '-uploaded_at']

    def __str__(self):
        return f"{self.profile.user.email} - {self.image.name}"


class UsernameChange(models.Model):
    """Record username change history for auditing and enforcement.

    - `user`: the user whose username changed
    - `old_username` / `new_username`
    - `changed_at`: timestamp
    """
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='username_changes')
    old_username = models.CharField(max_length=150, blank=True, null=True)
    new_username = models.CharField(max_length=150, blank=True, null=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email}: {self.old_username} -> {self.new_username} at {self.changed_at.isoformat()}"


class Notification(models.Model):
    """Simple in-app notification for users.

    - `user`: recipient
    - `actor`: optional user who triggered the notification
    - `verb`: short action (e.g., 'approved', 'rejected')
    - `message`: display text
    - `link`: optional relative URL to target (e.g., car detail)
    """
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications')
    actor = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='notifications_from')
    verb = models.CharField(max_length=120, blank=True)
    message = models.TextField(blank=True)
    link = models.CharField(max_length=400, blank=True, help_text='Relative URL for the notification target')
    unread = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification to {self.user.email}: {self.verb} - {self.message[:40]}"