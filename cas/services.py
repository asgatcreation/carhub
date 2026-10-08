"""Business logic for the parts store: cart, garage, delivery pricing, orders and fulfilment."""
from decimal import Decimal

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .models import CartItem, GarageVehicle, Order, OrderItem, Product

CART_KEY = 'parts_cart'          # guests: {product_id: quantity}
GARAGE_KEY = 'parts_garage'      # guests: {make, model, year}
MAX_QTY = 10

FREE_DELIVERY_FROM = Decimal('100000')
POD_STATES = {'Lagos', 'FCT'}    # pay on delivery is offered where our couriers collect cash
POD_LIMIT = Decimal('500000')
SOUTH_WEST = {'Ogun', 'Oyo', 'Osun', 'Ondo', 'Ekiti'}


def _authed(request):
    return getattr(request, 'user', None) is not None and request.user.is_authenticated


# ---------------------------------------------------------------- garage ("my car")

def get_vehicle(request):
    if _authed(request):
        v = GarageVehicle.objects.filter(user=request.user).first()
        if v:
            return v.as_dict()
    return request.session.get(GARAGE_KEY) or None


def set_vehicle(request, make, model, year):
    data = {'make': make.strip(), 'model': model.strip(), 'year': int(year)}
    if _authed(request):
        GarageVehicle.objects.update_or_create(user=request.user, defaults=data)
    request.session[GARAGE_KEY] = data
    return data


def clear_vehicle(request):
    if _authed(request):
        GarageVehicle.objects.filter(user=request.user).delete()
    request.session.pop(GARAGE_KEY, None)


def vehicle_label(vehicle):
    return f"{vehicle['year']} {vehicle['make']} {vehicle['model']}" if vehicle else ''


# ---------------------------------------------------------------- cart

def _session_cart(request):
    raw = request.session.get(CART_KEY) or {}
    return {int(k): max(1, min(int(v), MAX_QTY)) for k, v in raw.items() if str(k).isdigit()}


def cart_quantities(request):
    """{product_id: quantity} for the current visitor."""
    if _authed(request):
        return dict(CartItem.objects.filter(user=request.user).values_list('product_id', 'quantity'))
    return _session_cart(request)


def cart_count(request):
    return sum(cart_quantities(request).values())


def set_quantity(request, product, quantity):
    """Add / update / remove (quantity 0) a product, capped by stock and MAX_QTY. Returns the stored quantity."""
    quantity = max(0, min(int(quantity), MAX_QTY, product.stock))
    if _authed(request):
        if quantity:
            CartItem.objects.update_or_create(user=request.user, product=product, defaults={'quantity': quantity})
        else:
            CartItem.objects.filter(user=request.user, product=product).delete()
    else:
        cart = _session_cart(request)
        if quantity:
            cart[product.pk] = quantity
        else:
            cart.pop(product.pk, None)
        request.session[CART_KEY] = {str(k): v for k, v in cart.items()}
    return quantity


def add_to_cart(request, product, quantity=1):
    current = cart_quantities(request).get(product.pk, 0)
    return set_quantity(request, product, current + int(quantity))


def clear_cart(request):
    if _authed(request):
        CartItem.objects.filter(user=request.user).delete()
    request.session.pop(CART_KEY, None)


def merge_session_into_account(request, user):
    """Called on sign-in: guest cart and garage move into the account."""
    for pid, qty in _session_cart(request).items():
        product = Product.objects.public().filter(pk=pid).first()
        if product:
            item, created = CartItem.objects.get_or_create(user=user, product=product, defaults={'quantity': qty})
            if not created:
                item.quantity = min(MAX_QTY, max(item.quantity, qty))
                item.save(update_fields=['quantity'])
    request.session.pop(CART_KEY, None)
    vehicle = request.session.get(GARAGE_KEY)
    if vehicle and not GarageVehicle.objects.filter(user=user).exists():
        GarageVehicle.objects.create(user=user, **vehicle)


def cart_lines(request):
    """[(product, quantity, line_total)] for public, in-stock products; drops anything no longer buyable."""
    qty = cart_quantities(request)
    products = (Product.objects.public().filter(pk__in=qty).select_related('brand', 'vendor__profile', 'category')
                .prefetch_related('images', 'fitments'))
    lines = []
    for p in products:
        q = min(qty[p.pk], p.stock)
        if q:
            lines.append((p, q, p.price * q))
    return sorted(lines, key=lambda line: list(qty).index(line[0].pk))


# ---------------------------------------------------------------- pricing

def delivery_fee(state, subtotal, method='delivery'):
    if method == 'pickup' or not state:
        return Decimal('0')
    if subtotal >= FREE_DELIVERY_FROM:
        return Decimal('0')
    if state == 'Lagos':
        return Decimal('2500')
    if state == 'FCT':
        return Decimal('3000')
    if state in SOUTH_WEST:
        return Decimal('3500')
    return Decimal('5000')


def pod_allowed(state, total, method='delivery'):
    return method == 'delivery' and state in POD_STATES and total <= POD_LIMIT


def summary(lines, state='', method='delivery'):
    subtotal = sum((line[2] for line in lines), Decimal('0'))
    fee = delivery_fee(state, subtotal, method)
    savings = sum(((p.compare_at_price - p.price) * q for p, q, _ in lines if p.on_sale), Decimal('0'))
    return {
        'items': sum(q for _, q, _ in lines),
        'subtotal': subtotal,
        'delivery_fee': fee,
        'total': subtotal + fee,
        'savings': savings,
        'to_free_delivery': max(Decimal('0'), FREE_DELIVERY_FROM - subtotal),
        'free_delivery_from': FREE_DELIVERY_FROM,
        'state_known': bool(state),
    }


# ---------------------------------------------------------------- orders

@transaction.atomic
def create_order(user, lines, details, payment_method):
    """Lock stock rows, then create a pending order with price snapshots. Raises ValueError if stock ran out."""
    ids = [p.pk for p, _, _ in lines]
    locked = {p.pk: p for p in Product.objects.select_for_update().filter(pk__in=ids)}
    for p, q, _ in lines:
        if locked[p.pk].stock < q or not locked[p.pk].is_active:
            raise ValueError(f'Only {locked[p.pk].stock} left of {p.name}. Please update your cart.')
    s = summary(lines, details['state'], details['delivery_method'])
    order = Order.objects.create(
        user=user, payment_method=payment_method,
        subtotal=s['subtotal'], delivery_fee=s['delivery_fee'], total=s['total'], **details,
    )
    OrderItem.objects.bulk_create([
        OrderItem(order=order, product=p, vendor=p.vendor, name=f'{p.brand.name + " " if p.brand else ""}{p.name}',
                  image_url=p.thumbnail, unit_price=p.price, quantity=q)
        for p, q, _ in lines
    ])
    return order


def _notify(user, actor, verb, message, link, subject, cta='View order'):
    from core.emails import send_branded
    from users.models import Notification
    if not user:
        return
    Notification.objects.create(user=user, actor=actor, verb=verb, message=message, link=link)
    send_branded(user.email, subject, heading=subject, body=message, cta_url=link, cta_label=cta)


def on_order_confirmed(order):
    by_vendor = {}
    for item in order.items.select_related('vendor'):
        by_vendor.setdefault(item.vendor, []).append(item)
    for vendor, items in by_vendor.items():
        names = ', '.join(f'{i.quantity} × {i.name}' for i in items)
        _notify(vendor, order.user, 'parts_order', f'New order {order.number} from {order.full_name}: {names}. '
                f'Please pack and ship it.', reverse('cas:vendor_orders'), 'You have a new order to ship', 'Open orders')
    pay = 'Pay the courier when it arrives.' if order.payment_method == 'pod' else 'Your payment is confirmed.'
    _notify(order.user, None, 'parts_order_confirmed',
            f'Thanks for your order! {pay} We will email you as each item ships.',
            order.get_absolute_url(), f'Order {order.number} confirmed')


def ship_item(item, courier, note, by):
    item.status, item.courier, item.tracking_note, item.shipped_at = 'shipped', courier, note, timezone.now()
    item.save()
    _notify(item.order.user, by, 'parts_shipped', f'{item.name} is on its way via {courier}.'
            + (f' {note}' if note else ''), item.order.get_absolute_url(), 'Your order has shipped', 'Track order')


def deliver_item(item, by):
    item.status, item.delivered_at = 'delivered', timezone.now()
    item.save()
    _notify(item.order.user, by, 'parts_delivered', f'{item.name} was delivered. Enjoy, and tell other drivers what '
            'you think by leaving a review.', item.order.get_absolute_url(), 'Delivered!', 'Leave a review')


def cancel_item(item, by, role, reason):
    """Cancel a line before it ships: restock it and refund what was paid for it."""
    from cars import payments
    from django.db.models import F
    item.status, item.cancel_reason = 'cancelled', reason
    item.save()
    if item.product_id:
        Product.objects.filter(pk=item.product_id).update(stock=F('stock') + item.quantity,
                                                          sold_count=F('sold_count') - item.quantity)
    order = item.order
    if order.is_paid and order.payment_method == 'paystack':
        payments.refund(order.payment_reference, item.line_total)
    other = item.vendor if role == 'buyer' else order.user
    _notify(other, by, 'parts_cancelled', f'{item.name} on order {order.number} was cancelled'
            + (f': {reason}' if reason else '.'), order.get_absolute_url() if role != 'buyer' else reverse('cas:vendor_orders'),
            'An item was cancelled', 'View details')


def bought(user, product):
    return OrderItem.objects.filter(order__user=user, product=product, status='delivered').exists()
