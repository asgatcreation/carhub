"""Seed the parts store (called from `manage.py seed_demo`)."""
import json
import random
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.utils import timezone

from cas.forms import parse_fitment
from cas.models import Brand, Category, Fitment, GarageVehicle, Order, OrderItem, Product, ProductImage, ProductSpec, Review
from cas import services

from .catalog import CATEGORIES, P, VENDORS

PHOTOS = json.loads((Path(__file__).parent / 'part_photos.json').read_text(encoding='utf-8'))
User = get_user_model()

DESCRIPTIONS = {
    'genuine': 'Genuine part supplied with the manufacturer\'s part number, so it fits exactly like the original. '
               'Sourced from an authorised distributor and sold with an invoice for your service records.',
    'aftermarket': 'Quality aftermarket part from a recognised brand, made to meet or beat the original specification '
                   'at a better price. Check the compatible cars list or match the part number before ordering.',
    'accessory': 'A popular upgrade with Nigerian drivers. Easy to fit at home with no special tools, and backed by the '
                 'vendor\'s warranty.',
}
REVIEW_LINES = [
    (5, 'Exactly as described', 'Arrived in two days, original packaging, fitted perfectly.'),
    (5, 'Perfect fit', 'My mechanic confirmed it\'s the right part. Car feels brand new again.'),
    (4, 'Good value', 'Works well and the price was better than the market. Delivery took an extra day.'),
    (5, 'Fast delivery to Lekki', 'Ordered in the morning, delivered the next afternoon. Will buy again.'),
    (4, 'Solid quality', 'Does the job. Packaging could be better but the product itself is great.'),
    (3, 'Okay', 'It works, but I expected slightly better finish for the price.'),
]


def _user(local, first, last, rng, domain):
    user = User.objects.create_user(email=f'{local}@{domain}', password=None, first_name=first, last_name=last, username=local)
    user.date_joined = timezone.now() - timedelta(days=rng.randint(200, 900))
    user.save(update_fields=['date_joined'])
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
    return user


def build(rng, password, domain, buyers):
    """Create categories, vendors, ~60 products with photos and fitment, reviews and sample orders."""
    cats = {}
    for i, (name, slug, icon, blurb) in enumerate(CATEGORIES):
        cats[slug], _ = Category.objects.update_or_create(slug=slug, defaults={'name': name, 'icon': icon, 'blurb': blurb, 'display_order': i})

    vendors = []
    for local, first, last, shop, city, state, years, about in VENDORS:
        v = _user(local, first, last, rng, domain)
        v.set_password(password)
        v.save(update_fields=['password'])
        p = v.profile
        p.company_name, p.city, p.years_in_business, p.business_description = shop, city, years, about
        p.is_cas_seller_approved = p.is_verified = True
        p.phone = f'+234 80{rng.randint(1, 9)} {rng.randint(100, 999)} {rng.randint(1000, 9999)}'
        p.save()
        vendors.append(v)

    products = []
    used = {}
    for n, (vi, cat, brand, name, ptype, price, was, stock, sku, warranty, short, specs, fits, photo) in enumerate(P):
        b, _ = Brand.objects.get_or_create(name=brand)
        product = Product.objects.create(
            vendor=vendors[vi], category=cats[cat], brand=b, name=name, sku=sku, short_description=short,
            description=f'{short}\n\n{DESCRIPTIONS[ptype]}', price=Decimal(price),
            compare_at_price=Decimal(was) if was else None, stock=stock, part_type=ptype, warranty_months=warranty,
            universal_fit=fits is True, dispatch_days=rng.choice([1, 1, 2, 3]), status='approved',
            moderated_at=timezone.now(), sold_count=rng.randint(3, 180), views_count=rng.randint(40, 900),
        )
        Product.objects.filter(pk=product.pk).update(created_at=timezone.now() - timedelta(days=rng.randint(2, 120)))
        pool = PHOTOS[photo]
        start = used.get(photo, 0)
        used[photo] = start + 1
        for i in range(min(3, len(pool))):  # rotate so products of the same type lead with different photos
            ph = pool[(start + i) % len(pool)]
            ProductImage.objects.create(product=product, image_url=ph['url'], credit=ph['credit'], license=ph['license'],
                                        source_url=ph['source'], alt_text=name, display_order=i)
        ProductSpec.objects.bulk_create([ProductSpec(product=product, name=k, value=v, display_order=i)
                                         for i, (k, v) in enumerate(specs.items())])
        if fits is not True:
            Fitment.objects.bulk_create([Fitment(product=product, make=mk, model=md, year_from=y1, year_to=y2)
                                         for mk, md, y1, y2 in (parse_fitment(f) for f in fits)])
        products.append(product)

    # Three fresh listings wait in the staff console's Products queue
    for product in rng.sample([p for p in products if p.vendor == vendors[3]], 3):
        Product.objects.filter(pk=product.pk).update(status='pending', moderated_at=None, sold_count=0)

    # Published reviews (and a couple waiting for moderation)
    for product in rng.sample(products, 30):
        for reviewer in rng.sample(buyers, rng.randint(1, 3)):
            stars, title, body = rng.choice(REVIEW_LINES)
            r = Review.objects.create(product=product, user=reviewer, rating=stars, title=title, body=body,
                                      verified_purchase=rng.random() < .7, status='approved', moderated_at=timezone.now())
            Review.objects.filter(pk=r.pk).update(created_at=timezone.now() - timedelta(days=rng.randint(1, 90)))
        product.refresh_rating()
    waiting = [p for p in products if not p.reviews.filter(user=buyers[1]).exists()][:2]
    Review.objects.create(product=waiting[0], user=buyers[1], rating=1, title='WhatsApp me 0803 555 1234',
                          body='I sell this cheaper, call me', status='pending')
    Review.objects.create(product=waiting[1], user=buyers[1], rating=5, title='Brilliant',
                          body='Fitted it myself in ten minutes and it works perfectly.', status='pending', verified_purchase=True)

    # Orders for the demo buyer at every stage; vendors get items to ship
    buyer = buyers[0]
    GarageVehicle.objects.update_or_create(user=buyer, defaults={'make': 'Toyota', 'model': 'Camry', 'year': 2021})
    live = [p for p in products if p.status == 'approved']
    camry = [p for p in live if p.fits({'make': 'Toyota', 'model': 'Camry', 'year': 2021})]
    _order(buyer, rng.sample(camry, 2), 'demo', 40, ['delivered', 'delivered'])
    _order(buyer, rng.sample(camry, 1) + rng.sample([p for p in live if p.universal_fit], 1), 'demo', 4, ['shipped', 'processing'])
    _order(buyer, rng.sample([p for p in live if p.universal_fit], 1), 'pod', 1, ['processing'])
    for other in buyers[1:4]:
        _order(other, rng.sample([p for p in live if p.vendor == vendors[0]], 1), rng.choice(['demo', 'pod']),
               rng.randint(0, 3), ['processing'])
    return products


def _order(user, products, method, days_ago, statuses):
    lines = [(p, 1, p.price) for p in products]
    details = {'full_name': user.get_full_name(), 'email': user.email, 'phone': user.profile.phone or '+234 803 000 0000',
               'delivery_method': 'delivery', 'state': 'Lagos', 'city': 'Lekki', 'address': '12 Admiralty Way',
               'delivery_notes': ''}
    order = services.create_order(user, lines, details, method)
    order.confirm(reference=f'DEMO-{order.number}' if method == 'demo' else '')
    when = timezone.now() - timedelta(days=days_ago, hours=3)
    Order.objects.filter(pk=order.pk).update(created_at=when, paid_at=when if method != 'pod' else None)
    for item, status in zip(order.items.all(), statuses):
        extra = {}
        if status in ('shipped', 'delivered'):
            extra.update(courier='GIG Logistics', tracking_note='Waybill GIG-' + order.number[-4:], shipped_at=when + timedelta(days=1))
        if status == 'delivered':
            extra['delivered_at'] = when + timedelta(days=2)
        OrderItem.objects.filter(pk=item.pk).update(status=status, **extra)
    return order
