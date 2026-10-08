import secrets
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from core.formatting import naira

# ======================
# CHOICES
# ======================

STATE_CHOICES = [(s, s) for s in [
    'Abia', 'Adamawa', 'Akwa Ibom', 'Anambra', 'Bauchi', 'Bayelsa', 'Benue', 'Borno', 'Cross River', 'Delta',
    'Ebonyi', 'Edo', 'Ekiti', 'Enugu', 'FCT', 'Gombe', 'Imo', 'Jigawa', 'Kaduna', 'Kano', 'Katsina', 'Kebbi',
    'Kogi', 'Kwara', 'Lagos', 'Nasarawa', 'Niger', 'Ogun', 'Ondo', 'Osun', 'Oyo', 'Plateau', 'Rivers', 'Sokoto',
    'Taraba', 'Yobe', 'Zamfara',
]]

CONDITION_CHOICES = [
    ('new', 'Brand new'),
    ('foreign_used', 'Foreign used'),
    ('nigerian_used', 'Nigerian used'),
]

CONDITION_GRADES = [
    ('excellent', 'Excellent'),
    ('good', 'Good'),
    ('fair', 'Fair'),
    ('needs_work', 'Needs work'),
]

ENGINE_CHOICES = [
    ('petrol_gas', 'Petrol'),
    ('diesel', 'Diesel'),
    ('hybrid', 'Hybrid'),
    ('electric', 'Electric'),
]

DRIVETRAIN_CHOICES = [
    ('fwd', 'Front-wheel drive'),
    ('rwd', 'Rear-wheel drive'),
    ('awd', 'All-wheel drive'),
    ('4wd', 'Four-wheel drive'),
]

TRANSMISSION_CHOICES = [
    ('automatic', 'Automatic'),
    ('manual', 'Manual'),
]

BODY_TYPE_CHOICES = [
    ('sedan', 'Sedan'),
    ('suv', 'SUV'),
    ('hatchback', 'Hatchback'),
    ('pickup', 'Pickup'),
    ('van', 'Minivan'),
    ('coupe', 'Coupe'),
]

STATUS_CHOICES = [
    ('available', 'Available'),
    ('reserved', 'Reserved'),
    ('sold', 'Sold'),
]

APPROVAL_CHOICES = [
    ('pending', 'Pending review'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
]


def validate_vin(value):
    if value and len(value) != 17:
        raise ValidationError('VIN must be exactly 17 characters.')


def validate_image_size(value):
    limit = getattr(settings, 'MAX_IMAGE_UPLOAD_MB', 8)
    if value and value.size > limit * 1024 * 1024:
        raise ValidationError(f'Images cannot be larger than {limit} MB.')


# ======================
# CATALOGUE
# ======================

class Feature(models.Model):
    CATEGORY_CHOICES = [
        ('Comfort', 'Comfort'),
        ('Technology', 'Technology'),
        ('Safety', 'Safety'),
        ('Performance', 'Performance'),
    ]
    name = models.CharField(max_length=100, unique=True)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, blank=True)

    class Meta:
        ordering = ['category', 'name']

    def __str__(self):
        return self.name


class CarQuerySet(models.QuerySet):
    def public(self):
        """Listings visitors can see: approved by moderation and not yet sold."""
        return self.filter(approval_status='approved').exclude(status='sold')

    def available(self):
        return self.public().filter(status='available')

    def by_seller(self, user):
        return self.filter(created_by=user)


class Car(models.Model):
    brand = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    trim = models.CharField(max_length=100, blank=True)
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    year = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=14, decimal_places=2)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cars_uploaded', verbose_name='seller',
    )

    # Specifications
    body_type = models.CharField(max_length=20, choices=BODY_TYPE_CHOICES, default='sedan')
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='foreign_used')
    condition_grade = models.CharField(max_length=20, choices=CONDITION_GRADES, blank=True)
    mileage = models.PositiveIntegerField(help_text='Kilometres')
    engine_type = models.CharField(max_length=20, choices=ENGINE_CHOICES, default='petrol_gas')
    engine_size = models.CharField(max_length=20, blank=True, help_text='e.g. 2.5L V6')
    drivetrain = models.CharField(max_length=10, choices=DRIVETRAIN_CHOICES, default='fwd')
    transmission = models.CharField(max_length=10, choices=TRANSMISSION_CHOICES, default='automatic')
    exterior_color = models.CharField(max_length=40, blank=True)
    interior_color = models.CharField(max_length=40, blank=True)
    num_seats = models.PositiveSmallIntegerField(default=5)
    num_previous_owners = models.PositiveSmallIntegerField(null=True, blank=True)
    vin = models.CharField(max_length=17, blank=True, validators=[validate_vin])
    warranty = models.CharField(max_length=100, blank=True)
    country_of_origin = models.CharField(max_length=100, blank=True)
    duty_paid = models.BooleanField(default=True, help_text='Customs duty cleared')

    # Location
    location = models.CharField(max_length=100, help_text='City or area')
    state = models.CharField(max_length=40, choices=STATE_CHOICES)

    # Content
    description = models.TextField(blank=True)
    features = models.ManyToManyField(Feature, related_name='cars', blank=True)
    cover_image = models.ImageField(upload_to='car_images/covers/', blank=True, null=True, validators=[validate_image_size])

    # Merchandising & analytics
    featured = models.BooleanField(default=False, help_text='Show on the homepage')
    views_count = models.PositiveIntegerField(default=0)

    # Lifecycle
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    approval_status = models.CharField(max_length=20, choices=APPROVAL_CHOICES, default='pending')
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_cars',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approval_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CarQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['approval_status', 'status']),
            models.Index(fields=['brand', 'model']),
            models.Index(fields=['price']),
            models.Index(fields=['year']),
            models.Index(fields=['body_type']),
            models.Index(fields=['state']),
        ]

    def __str__(self):
        return self.title

    # ----- display helpers -----
    @property
    def title(self):
        return f'{self.year} {self.brand} {self.model}'

    @property
    def full_title(self):
        return f'{self.title} {self.trim}'.strip()

    @property
    def price_display(self):
        return naira(self.price)

    @property
    def primary_image(self):
        if self.cover_image:
            return self.cover_image.url
        images = getattr(self, '_prefetched_objects_cache', {}).get('images')
        first = images[0] if images else self.images.first()
        return first.src if first else static('img/car-placeholder.svg')

    @property
    def thumbnail(self):
        """Card-sized image (smaller CDN rendition for hosted photos)."""
        if self.cover_image:
            return self.cover_image.url
        images = getattr(self, '_prefetched_objects_cache', {}).get('images')
        first = images[0] if images else self.images.first()
        return first.thumb if first else static('img/car-placeholder.svg')

    @property
    def is_available(self):
        return self.status == 'available' and self.approval_status == 'approved'

    def get_absolute_url(self):
        return reverse('cars:car_detail', kwargs={'slug': self.slug})

    # ----- lifecycle -----
    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(f'{self.year}-{self.brand}-{self.model}-{self.trim}')[:160] or 'car'
            slug, n = base, 1
            while Car.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                n += 1
                slug = f'{base}-{n}'
            self.slug = slug

        if self.condition != 'new' and not self.condition_grade and self.year and self.mileage is not None:
            age = timezone.now().year - self.year
            if age <= 2 and self.mileage <= 30000:
                self.condition_grade = 'excellent'
            elif age <= 5 and self.mileage <= 80000:
                self.condition_grade = 'good'
            elif age <= 10 and self.mileage <= 150000:
                self.condition_grade = 'fair'
            else:
                self.condition_grade = 'needs_work'

        # Trusted uploaders (staff or verified sellers) skip the moderation queue.
        if self._state.adding and self.approval_status == 'pending' and self.created_by_id and self._uploader_is_trusted():
            self.approval_status = 'approved'
            self.approved_by = self.created_by
            self.approved_at = timezone.now()
        super().save(*args, **kwargs)

    def _uploader_is_trusted(self):
        user = self.created_by
        if user.is_staff or user.is_superuser:
            return True
        profile = getattr(user, 'profile', None)
        return bool(profile and (profile.is_verified or profile.is_car_seller_approved))

    def approve(self, by_user, reason=''):
        self.approval_status = 'approved'
        self.approved_by = by_user
        self.approved_at = timezone.now()
        self.approval_reason = reason
        self.save(update_fields=['approval_status', 'approved_by', 'approved_at', 'approval_reason', 'updated_at'])

    def reject(self, by_user, reason=''):
        self.approval_status = 'rejected'
        self.approved_by = by_user
        self.approved_at = timezone.now()
        self.approval_reason = reason
        self.save(update_fields=['approval_status', 'approved_by', 'approved_at', 'approval_reason', 'updated_at'])


class CarImage(models.Model):
    """A gallery photo: either an uploaded file or an externally hosted URL (with credit)."""
    car = models.ForeignKey(Car, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='car_images/', blank=True, null=True, validators=[validate_image_size])
    image_url = models.URLField(max_length=500, blank=True)
    alt_text = models.CharField(max_length=200, blank=True)
    credit = models.CharField(max_length=200, blank=True, help_text='Photographer / author')
    license = models.CharField(max_length=60, blank=True)
    source_url = models.URLField(max_length=500, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    # Staff photo check: new photos appear in the console until a moderator approves or removes them.
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='+')

    class Meta:
        ordering = ['display_order', 'id']

    def __str__(self):
        return f'Photo of {self.car}'

    def clean(self):
        if not self.image and not self.image_url:
            raise ValidationError('Upload an image or provide an image URL.')

    @property
    def src(self):
        return self.image.url if self.image else self.image_url

    @property
    def thumb(self):
        # Wikimedia serves fixed thumbnail steps; 500px is plenty for cards.
        if not self.image and '/1280px-' in self.image_url:
            return self.image_url.replace('/1280px-', '/500px-')
        return self.src


# ======================
# SHOPPING
# ======================

class Cart(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Cart of {self.user}'


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, related_name='items', on_delete=models.CASCADE)
    car = models.ForeignKey(Car, related_name='cart_items', on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-added_at']
        constraints = [models.UniqueConstraint(fields=['cart', 'car'], name='unique_car_per_cart')]

    def __str__(self):
        return f'{self.car} in {self.cart}'


class WishlistItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='wishlist_items', on_delete=models.CASCADE)
    car = models.ForeignKey(Car, related_name='wishlisted_by', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['user', 'car'], name='unique_wishlist_car')]

    def __str__(self):
        return f'{self.user} saved {self.car}'


def _order_number():
    return 'CH-' + secrets.token_hex(3).upper()


class Order(models.Model):
    """One checkout: the buyer pays a refundable deposit per car (one OrderItem per car)."""
    STATUS_CHOICES = [
        ('pending', 'Awaiting payment'),
        ('paid', 'Deposit paid'),
        ('failed', 'Payment failed'),
        ('cancelled', 'Cancelled'),
    ]
    PROVIDER_CHOICES = [
        ('paystack', 'Paystack'),
        ('demo', 'Demo payment'),
    ]
    TIME_SLOTS = [
        ('morning', 'Morning (9am – 12pm)'),
        ('afternoon', 'Afternoon (12pm – 3pm)'),
        ('evening', 'Late afternoon (3pm – 6pm)'),
    ]
    number = models.CharField(max_length=16, unique=True, default=_order_number, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='orders', on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='paystack')
    payment_reference = models.CharField(max_length=100, blank=True, db_index=True)

    full_name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=30)
    inspection_state = models.CharField(max_length=40, choices=STATE_CHOICES, blank=True)
    preferred_date = models.DateField(null=True, blank=True)
    preferred_time = models.CharField(max_length=20, choices=TIME_SLOTS, blank=True)
    notes = models.TextField(blank=True)

    vehicles_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    deposit_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))

    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Order {self.number}'

    @property
    def balance_due(self):
        return self.vehicles_total - self.deposit_total

    def get_absolute_url(self):
        return reverse('cars:order_detail', kwargs={'number': self.number})

    @property
    def amount_due(self):
        """What the payment provider should charge now: the refundable deposit."""
        return self.deposit_total

    def mark_paid(self, reference=''):
        """Idempotently mark the order paid and reserve its cars."""
        if self.status == 'paid':
            return False
        self.status = 'paid'
        self.paid_at = timezone.now()
        if reference:
            self.payment_reference = reference
        self.save(update_fields=['status', 'paid_at', 'payment_reference'])
        Car.objects.filter(order_items__order=self, status='available').update(status='reserved')
        self.items.filter(status='awaiting_payment').update(status='reserved', updated_at=timezone.now())
        from .services import on_order_paid
        on_order_paid(self)
        return True


class OrderItem(models.Model):
    """A single car reservation inside an order, with its own lifecycle managed by buyer and seller."""
    STATUS_CHOICES = [
        ('awaiting_payment', 'Awaiting payment'),
        ('reserved', 'Reserved — awaiting seller'),
        ('scheduled', 'Inspection scheduled'),
        ('completed', 'Purchase completed'),
        ('cancelled', 'Cancelled'),
    ]
    REFUND_CHOICES = [
        ('', 'No refund'),
        ('requested', 'Refund processing'),
        ('refunded', 'Deposit refunded'),
    ]
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    car = models.ForeignKey(Car, related_name='order_items', on_delete=models.SET_NULL, null=True)
    seller = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='sales', on_delete=models.SET_NULL, null=True)
    title = models.CharField(max_length=200)
    image_url = models.CharField(max_length=500, blank=True)
    price = models.DecimalField(max_digits=14, decimal_places=2)
    deposit = models.DecimalField(max_digits=14, decimal_places=2)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='awaiting_payment')
    inspection_at = models.DateTimeField(null=True, blank=True)
    inspection_address = models.CharField(max_length=255, blank=True)
    seller_note = models.TextField(blank=True)
    cancel_reason = models.TextField(blank=True)
    cancelled_by = models.CharField(max_length=10, blank=True)  # 'buyer' | 'seller' | 'staff'
    refund_status = models.CharField(max_length=20, choices=REFUND_CHOICES, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-order__created_at', 'id']

    def __str__(self):
        return f'{self.title} ({self.order.number})'

    @property
    def balance(self):
        return self.price - self.deposit

    @property
    def is_active(self):
        return self.status in ('reserved', 'scheduled')

    def timeline(self):
        """Order-tracking steps as (label, when, state) — state is done / current / todo / cancelled."""
        steps = [
            ('Deposit paid — car reserved', self.order.paid_at),
            ('Inspection scheduled with the seller', self.inspection_at),
            ('Balance paid & keys handed over', self.completed_at),
        ]
        if self.status == 'cancelled':
            refund = 'done' if self.refund_status == 'refunded' else 'current'
            return [
                (steps[0][0], steps[0][1], 'done'),
                (f'Reservation cancelled by {self.cancelled_by or "buyer"}', self.updated_at, 'cancelled'),
                (self.get_refund_status_display() or 'Refund', None, refund),
            ]
        progress = {'awaiting_payment': 0, 'reserved': 1, 'scheduled': 2, 'completed': 3}[self.status]
        return [(label, when, 'done' if i < progress else 'current' if i == progress else 'todo')
                for i, (label, when) in enumerate(steps)]
