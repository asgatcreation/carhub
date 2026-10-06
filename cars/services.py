"""Cart, wishlist and order logic shared by views, signals and the context processor.

Guests keep their cart/wishlist in the session (lists of car ids); signed-in
users get database-backed records. On login the session data is merged in.
"""
from decimal import Decimal

from django.conf import settings
from django.db import transaction

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
    return {'vehicles_total': vehicles, 'deposit_total': deposits, 'balance_total': vehicles - deposits, 'count': len(cars)}


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
        OrderItem(order=order, car=c, title=c.full_title, image_url=c.primary_image, price=c.price, deposit=deposit_for(c))
        for c in cars
    ])
    return order
