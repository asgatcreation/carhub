"""Parts & accessories store (CAS).

Vendors (approved through the staff console) list products; every product is checked by a
moderator before it is public. Products declare which vehicles they fit, so buyers can shop
"for my car". Orders are paid in full (Paystack, demo payment or pay on delivery) and each
line is fulfilled by its vendor: processing -> shipped -> delivered.
"""
import secrets
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Greatest
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from cars.models import STATE_CHOICES


def unique_slug(instance, value, max_length=200):
    base = slugify(value)[:max_length] or 'item'
    slug, n = base, 2
    model = type(instance)
    while model.objects.filter(slug=slug).exclude(pk=instance.pk).exists():
        slug = f'{base}-{n}'
        n += 1
    return slug


class Category(models.Model):
    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=90, unique=True, blank=True)
    icon = models.CharField(max_length=30, default='wrench', help_text='Icon name from the site sprite')
    blurb = models.CharField(max_length=160, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['display_order', 'name']
        verbose_name_plural = 'categories'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, 80)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('cas:category', args=[self.slug])


class Brand(models.Model):
    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True, blank=True)
    country = models.CharField(max_length=60, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, self.name, 80)
        super().save(*args, **kwargs)


class ProductQuerySet(models.QuerySet):
    def public(self):
        """What shoppers can see: approved, switched on by the vendor, from an approved vendor."""
        return self.filter(status='approved', is_active=True, vendor__profile__is_cas_seller_approved=True)

    def fits(self, make, model='', year=None):
        """Products that fit the given vehicle (universal products always fit)."""
        rule = Q(fitments__make__iexact=make) & (Q(fitments__model='') | Q(fitments__model__iexact=model))
        if year:
            rule &= (Q(fitments__year_from__isnull=True) | Q(fitments__year_from__lte=year))
            rule &= (Q(fitments__year_to__isnull=True) | Q(fitments__year_to__gte=year))
        return self.filter(Q(universal_fit=True) | rule).distinct()


class Product(models.Model):
    PART_TYPES = [('genuine', 'Genuine (OEM)'), ('aftermarket', 'Aftermarket'), ('accessory', 'Accessory')]
    STATUS_CHOICES = [('pending', 'Awaiting review'), ('approved', 'Live'), ('rejected', 'Rejected')]

    vendor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name='products')
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    sku = models.CharField('SKU / part number', max_length=60, blank=True)
    short_description = models.CharField(max_length=200, blank=True, help_text='One line shown on product cards')
    description = models.TextField()
    price = models.DecimalField(max_digits=12, decimal_places=2)
    compare_at_price = models.DecimalField('Was (before discount)', max_digits=12, decimal_places=2, null=True, blank=True)
    stock = models.PositiveIntegerField(default=0)
    part_type = models.CharField(max_length=12, choices=PART_TYPES, default='aftermarket')
    warranty_months = models.PositiveSmallIntegerField(default=0)
    universal_fit = models.BooleanField(default=False, help_text='Fits any car (e.g. phone holders, jump starters)')
    dispatch_days = models.PositiveSmallIntegerField(default=1, help_text='Working days before the vendor ships')

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', db_index=True)
    moderated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    moderated_at = models.DateTimeField(null=True, blank=True)
    moderation_note = models.CharField(max_length=300, blank=True)
    is_active = models.BooleanField(default=True, help_text='Vendors can hide a product without deleting it')

    sold_count = models.PositiveIntegerField(default=0)
    views_count = models.PositiveIntegerField(default=0)
    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    rating_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProductQuerySet.as_manager()

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['status', 'is_active']), models.Index(fields=['price'])]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(self, f'{self.brand.name if self.brand else ""} {self.name}', 170)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('cas:product', args=[self.slug])

    # --- display helpers
    def _first_image(self):
        images = list(self.images.all())  # uses prefetch when available
        return images[0] if images else None

    @property
    def primary_image(self):
        img = self._first_image()
        return img.src if img else static('img/part-placeholder.svg')

    @property
    def thumbnail(self):
        img = self._first_image()
        return img.thumb if img else static('img/part-placeholder.svg')

    @property
    def in_stock(self):
        return self.stock > 0

    @property
    def low_stock(self):
        return 0 < self.stock <= 5

    @property
    def on_sale(self):
        return bool(self.compare_at_price and self.compare_at_price > self.price)

    @property
    def discount_pct(self):
        return round((1 - self.price / self.compare_at_price) * 100) if self.on_sale else 0

    def fits(self, vehicle):
        """True / False for a garage vehicle dict ({make, model, year}); None when no vehicle is set."""
        if not vehicle:
            return None
        if self.universal_fit:
            return True
        return any(f.matches(vehicle.get('make'), vehicle.get('model'), vehicle.get('year')) for f in self.fitments.all())

    def refresh_rating(self):
        from django.db.models import Avg, Count
        agg = self.reviews.filter(status='approved').aggregate(avg=Avg('rating'), n=Count('id'))
        self.rating_avg, self.rating_count = agg['avg'], agg['n']
        self.save(update_fields=['rating_avg', 'rating_count'])


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='parts/', blank=True, null=True)
    image_url = models.URLField(max_length=500, blank=True)
    alt_text = models.CharField(max_length=200, blank=True)
    credit = models.CharField(max_length=200, blank=True)
    license = models.CharField(max_length=60, blank=True)
    source_url = models.URLField(max_length=500, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['display_order', 'pk']

    def __str__(self):
        return f'Photo of {self.product}'

    @property
    def src(self):
        if self.image:
            return self.image.url
        return self.image_url

    @property
    def thumb(self):
        # Wikimedia serves fixed thumbnail steps; 500px is plenty for cards and carts.
        if not self.image and '/1280px-' in self.image_url:
            return self.image_url.replace('/1280px-', '/500px-')
        return self.src


class ProductSpec(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='specs')
    name = models.CharField(max_length=60)
    value = models.CharField(max_length=120)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['display_order', 'pk']

    def __str__(self):
        return f'{self.name}: {self.value}'


class Fitment(models.Model):
    """A vehicle (range) the product fits. Blank model = every model of the make."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='fitments')
    make = models.CharField(max_length=40)
    model = models.CharField(max_length=60, blank=True)
    year_from = models.PositiveSmallIntegerField(null=True, blank=True)
    year_to = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['make', 'model', 'year_from']

    def __str__(self):
        return self.label

    @property
    def label(self):
        years = ''
        if self.year_from and self.year_to:
            years = f' {self.year_from}–{self.year_to}' if self.year_from != self.year_to else f' {self.year_from}'
        elif self.year_from:
            years = f' {self.year_from}+'
        elif self.year_to:
            years = f' up to {self.year_to}'
        return f'{self.make} {self.model or "(all models)"}{years}'

    def matches(self, make, model, year):
        if not make or self.make.lower() != str(make).lower():
            return False
        if self.model and model and self.model.lower() != str(model).lower():
            return False
        if self.model and not model:
            return False
        if year:
            year = int(year)
            if (self.year_from and year < self.year_from) or (self.year_to and year > self.year_to):
                return False
        return True


class GarageVehicle(models.Model):
    """The buyer's car, used to filter parts that fit. One per user (guests keep it in the session)."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='garage_vehicle')
    make = models.CharField(max_length=40)
    model = models.CharField(max_length=60)
    year = models.PositiveSmallIntegerField()

    def __str__(self):
        return f'{self.year} {self.make} {self.model}'

    def as_dict(self):
        return {'make': self.make, 'model': self.model, 'year': self.year}


class CartItem(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='parts_cart')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='+')
    quantity = models.PositiveSmallIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'product')
        ordering = ['added_at']


def _order_number():
    return 'CP-' + secrets.token_hex(3).upper()


class Order(models.Model):
    STATUS_CHOICES = [('pending', 'Awaiting payment'), ('confirmed', 'Confirmed'), ('failed', 'Payment failed'),
                      ('cancelled', 'Cancelled')]
    PAYMENT_CHOICES = [('paystack', 'Card, transfer or USSD (Paystack)'), ('demo', 'Demo payment'),
                       ('pod', 'Pay on delivery')]
    DELIVERY_CHOICES = [('delivery', 'Home or office delivery'), ('pickup', "Pick up from the vendor")]

    number = models.CharField(max_length=16, unique=True, default=_order_number, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='parts_orders')
    full_name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=30)
    delivery_method = models.CharField(max_length=10, choices=DELIVERY_CHOICES, default='delivery')
    state = models.CharField(max_length=40, choices=STATE_CHOICES)
    city = models.CharField(max_length=80)
    address = models.CharField(max_length=255, blank=True)
    delivery_notes = models.CharField(max_length=300, blank=True)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    total = models.DecimalField(max_digits=12, decimal_places=2)
    payment_reference = models.CharField(max_length=60, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.number

    def get_absolute_url(self):
        return reverse('cas:order_detail', args=[self.number])

    @property
    def amount_due(self):
        """What the payment provider should charge now (the whole order)."""
        return self.total

    @property
    def is_paid(self):
        return self.paid_at is not None

    def confirm(self, reference=''):
        """Idempotently confirm the order: reserve stock and hand each line to its vendor."""
        if self.status == 'confirmed':
            return False
        self.status = 'confirmed'
        if self.payment_method != 'pod':
            self.paid_at = timezone.now()
        if reference:
            self.payment_reference = reference
        self.save(update_fields=['status', 'paid_at', 'payment_reference'])
        for item in self.items.select_related('product'):
            if item.product_id:
                Product.objects.filter(pk=item.product_id).update(
                    stock=Greatest(F('stock') - item.quantity, 0),
                    sold_count=F('sold_count') + item.quantity)
        self.items.filter(status='pending').update(status='processing', updated_at=timezone.now())
        from .services import on_order_confirmed
        on_order_confirmed(self)
        return True


class OrderItem(models.Model):
    STATUS_CHOICES = [('pending', 'Awaiting payment'), ('processing', 'Preparing'), ('shipped', 'On the way'),
                      ('delivered', 'Delivered'), ('cancelled', 'Cancelled')]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, related_name='order_items')
    vendor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='parts_sales')
    name = models.CharField(max_length=200)
    image_url = models.CharField(max_length=500, blank=True)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='pending')
    courier = models.CharField(max_length=80, blank=True)
    tracking_note = models.CharField(max_length=200, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.CharField(max_length=300, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['pk']

    def __str__(self):
        return f'{self.quantity} × {self.name}'

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    def timeline(self):
        """(label, when, state) steps for order tracking."""
        steps = [('Order confirmed', self.order.created_at if self.order.status == 'confirmed' else None),
                 ('Packed by the vendor', None), ('Shipped', self.shipped_at), ('Delivered', self.delivered_at)]
        if self.status == 'cancelled':
            return [(steps[0][0], steps[0][1], 'done'), ('Cancelled', self.updated_at, 'cancelled')]
        progress = {'pending': 0, 'processing': 1, 'shipped': 3, 'delivered': 4}[self.status]
        return [(label, when, 'done' if i < progress else 'current' if i == progress else 'todo')
                for i, (label, when) in enumerate(steps)]


class Review(models.Model):
    STATUS_CHOICES = [('pending', 'Awaiting moderation'), ('approved', 'Published'), ('rejected', 'Rejected')]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='part_reviews')
    rating = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=120, blank=True)
    body = models.TextField()
    verified_purchase = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', db_index=True)
    moderated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    moderated_at = models.DateTimeField(null=True, blank=True)
    moderation_note = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('product', 'user')

    def __str__(self):
        return f'{self.rating}★ {self.product}'
