"""Cart, wishlist and order logic shared by views, signals and the context processor.

Guests keep their cart/wishlist in the session (lists of car ids); signed-in
users get database-backed records. On login the session data is merged in.
"""
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .models import Car, Cart, CartItem, Order, OrderItem, WishlistItem

CART_KEY = 'cart_car_ids'
WISHLIST_KEY = 'wishlist_car_ids'
RECENT_KEY = 'recently_viewed'


def _authed(request):
    return getattr(request, 'user', None) is not None and request.user.is_authenticated


def _session_ids(request, key):
    return [int(i) for i in request.session.get(key, []) if str(i).isdigit()]


# ----- cart -----

def cart_car_ids(request):
    if _authed(request):
        return list(CartItem.objects.filter(cart__user=request.user).values_list('car_id', flat=True))
    return _session_ids(request, CART_KEY)


def cart_cars(request):
    ids = cart_car_ids(request)
    cars = Car.objects.public().filter(pk__in=ids).prefetch_related('images').select_related('created_by')
    return sorted(cars, key=lambda c: ids.index(c.pk) if c.pk in ids else 0)


def add_to_cart(request, car):
    if _authed(request):
        cart, _ = Cart.objects.get_or_create(user=request.user)
        CartItem.objects.get_or_create(cart=cart, car=car)
    else:
        ids = _session_ids(request, CART_KEY)
        if car.pk not in ids:
            ids.insert(0, car.pk)
        request.session[CART_KEY] = ids


def remove_from_cart(request, car_id):
    if _authed(request):
        CartItem.objects.filter(cart__user=request.user, car_id=car_id).delete()
    else:
        request.session[CART_KEY] = [i for i in _session_ids(request, CART_KEY) if i != int(car_id)]


def clear_cart(request):
    if _authed(request):
        CartItem.objects.filter(cart__user=request.user).delete()
    request.session.pop(CART_KEY, None)


# ----- wishlist -----

def wishlist_car_ids(request):
    if _authed(request):
        return list(WishlistItem.objects.filter(user=request.user).values_list('car_id', flat=True))
    return _session_ids(request, WISHLIST_KEY)


def toggle_wishlist(request, car):
    """Returns True when the car is now saved, False when it was removed."""
    if _authed(request):
        item, created = WishlistItem.objects.get_or_create(user=request.user, car=car)
        if not created:
            item.delete()
        return created
    ids = _session_ids(request, WISHLIST_KEY)
    if car.pk in ids:
        ids.remove(car.pk)
        saved = False
    else:
        ids.insert(0, car.pk)
        saved = True
    request.session[WISHLIST_KEY] = ids
    return saved


def merge_session_into_account(request, user):
    cart_ids = _session_ids(request, CART_KEY)
    if cart_ids:
        cart, _ = Cart.objects.get_or_create(user=user)
        for car in Car.objects.public().filter(pk__in=cart_ids):
            CartItem.objects.get_or_create(cart=cart, car=car)
    for car in Car.objects.filter(pk__in=_session_ids(request, WISHLIST_KEY)):
        WishlistItem.objects.get_or_create(user=user, car=car)
    request.session.pop(CART_KEY, None)
    request.session.pop(WISHLIST_KEY, None)


# ----- recently viewed -----

def remember_viewed(request, car):
    ids = [i for i in _session_ids(request, RECENT_KEY) if i != car.pk]
    request.session[RECENT_KEY] = ([car.pk] + ids)[:12]


def recently_viewed(request, exclude=None, limit=4):
    ids = [i for i in _session_ids(request, RECENT_KEY) if i != getattr(exclude, 'pk', None)][:limit]
    cars = {c.pk: c for c in Car.objects.public().filter(pk__in=ids).prefetch_related('images')}
    return [cars[i] for i in ids if i in cars]


# ----- orders -----

def deposit_for(car):
    """Refundable reservation deposit charged online (the balance is paid after inspection)."""
    deposit = Decimal(str(getattr(settings, 'CAR_RESERVATION_DEPOSIT', 250_000)))
    return min(deposit, car.price)


def cart_summary(cars):
    vehicles = sum((c.price for c in cars), Decimal('0'))
    deposits = sum((deposit_for(c) for c in cars), Decimal('0'))
    return {'vehicles_total': vehicles, 'deposit_total': deposits, 'balance_total': vehicles - deposits, 'count': len(cars),
            'deposit_each': Decimal(str(getattr(settings, 'CAR_RESERVATION_DEPOSIT', 250_000)))}


@transaction.atomic
def create_order(user, cars, contact, provider):
    """Create a pending order for the given (available) cars with price snapshots."""
    summary = cart_summary(cars)
    order = Order.objects.create(
        user=user, provider=provider,
        vehicles_total=summary['vehicles_total'], deposit_total=summary['deposit_total'],
        **contact,
    )
    OrderItem.objects.bulk_create([
        OrderItem(order=order, car=c, seller=c.created_by, title=c.full_title, image_url=c.primary_image,
                  price=c.price, deposit=deposit_for(c))
        for c in cars
    ])
    return order


# ----- reservation lifecycle -----

def _notify(user, actor, verb, message, link):
    from users.models import Notification
    if not user:
        return
    Notification.objects.create(user=user, actor=actor, verb=verb, message=message, link=link)
    if user.email:
        from core.emails import send_branded
        body, cta = EMAIL_COPY.get(verb, ('', 'Open CarHub'))
        send_branded(user.email, message, heading=message, body=body, cta_url=link, cta_label=cta)


EMAIL_COPY = {
    'reservation': ('A buyer paid a refundable deposit, so the car is off the market. Confirm an inspection '
                    'time so they can come and see it.', 'Confirm inspection'),
    'order_paid': ('Your deposit is in and the car is reserved for you. The seller will confirm an inspection '
                   'time shortly; you pay the balance only after you have seen the car.', 'View reservation'),
    'inspection': ('The seller has confirmed when and where you can inspect the car. Bring your mechanic if '
                   'you like; if anything is wrong, you can cancel and your deposit is refunded.', 'See details'),
    'completed': ('The sale is complete and the car is yours. Thanks for buying on CarHub. Leaving the seller '
                  'a review helps other buyers.', 'View order'),
    'cancelled': ('This reservation has been cancelled and the car is available again. Any deposit paid is '
                  'refunded to the original payment method.', 'View details'),
}


def on_order_paid(order):
    """Tell every seller they have a new reservation, and confirm to the buyer."""
    for item in order.items.select_related('seller'):
        _notify(item.seller, order.user, 'reservation',
                f'{order.full_name} reserved your {item.title} — confirm an inspection time',
                reverse('cars:sales'))
    _notify(order.user, None, 'order_paid', f'Reservation {order.number} confirmed', order.get_absolute_url())


def schedule_inspection(item, when, address, note, by):
    item.status = 'scheduled'
    item.inspection_at = when
    item.inspection_address = address
    item.seller_note = note
    item.save()
    local = timezone.localtime(when).strftime('%a %d %b, %I:%M %p')
    _notify(item.order.user, by, 'inspection', f'Inspection for {item.title} set for {local}', item.order.get_absolute_url())


@transaction.atomic
def complete_sale(item, by):
    item.status = 'completed'
    item.completed_at = timezone.now()
    item.save()
    if item.car:
        item.car.status = 'sold'
        item.car.save(update_fields=['status', 'updated_at'])
    _notify(item.order.user, by, 'completed', f'Purchase of {item.title} completed — enjoy your car!', item.order.get_absolute_url())


@transaction.atomic
def cancel_reservation(item, by, role, reason=''):
    """Cancel an active reservation, release the car and refund the deposit."""
    from . import payments
    item.status = 'cancelled'
    item.cancelled_by = role
    item.cancel_reason = reason
    if item.order.provider == 'demo':
        item.refund_status = 'refunded'
    else:
        item.refund_status = 'refunded' if payments.refund(item.order.payment_reference, item.deposit) else 'requested'
    item.save()
    if item.car and item.car.status == 'reserved':
        item.car.status = 'available'
        item.car.save(update_fields=['status', 'updated_at'])
    other = item.seller if role == 'buyer' else item.order.user
    link = reverse('cars:sales') if role == 'buyer' else item.order.get_absolute_url()
    _notify(other, by, 'cancelled', f'Reservation for {item.title} was cancelled', link)


# ----- price insight -----

YEARLY_DEPRECIATION = Decimal('0.07')
INSIGHT_LEVELS = [  # (max % vs market, key, label)
    (Decimal('-8'), 'great', 'Great price'),
    (Decimal('-3'), 'good', 'Good price'),
    (Decimal('8'), 'fair', 'Fair price'),
    (None, 'high', 'Above market'),
]


def annotate_insights(cars):
    """Attach `car.insight` (level, label, pct, market, low, high) by comparing each car with listings of the
    same make & model, normalising their prices to the car's model year. Needs at least two comparables."""
    cars = [c for c in cars if c is not None]
    if not cars:
        return cars
    from django.db.models import Q
    query = Q()
    for brand, model in {(c.brand, c.model) for c in cars}:
        query |= Q(brand=brand, model=model)
    pool = list(Car.objects.public().filter(query).values_list('pk', 'brand', 'model', 'year', 'price'))
    for car in cars:
        comps = [price * (1 + YEARLY_DEPRECIATION) ** (car.year - year)
                 for pk, brand, model, year, price in pool
                 if pk != car.pk and brand == car.brand and model == car.model]
        car.insight = None
        if len(comps) < 2:
            continue
        market = sum(comps) / len(comps)
        pct = (car.price - market) / market * 100
        level, label = next((key, text) for limit, key, text in INSIGHT_LEVELS if limit is None or pct <= limit)
        car.insight = {
            'level': level, 'label': label, 'pct': round(float(pct)), 'market': market,
            'low': min(comps + [car.price]), 'high': max(comps + [car.price]), 'count': len(comps),
        }
        span = car.insight['high'] - car.insight['low']
        car.insight['position'] = round(float((car.price - car.insight['low']) / span * 100)) if span else 50
    return cars
