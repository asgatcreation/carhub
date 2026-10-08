import json
import logging
import re
from datetime import date
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Avg, Count, F, Max, Min, Q
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from core.emails import send_branded
from users.models import Conversation, Message, Notification, Review

from . import payments, services
from .forms import (
    CancelReservationForm, CheckoutDetailsForm, ListingForm, PaymentForm, ReviewForm, ScheduleInspectionForm,
    SearchForm,
)
from core.formatting import naira_compact

from .models import (
    BODY_TYPE_CHOICES, CONDITION_CHOICES, ENGINE_CHOICES, STATE_CHOICES, TRANSMISSION_CHOICES, Car, CarImage, Order, OrderItem,
)

logger = logging.getLogger('carhub')
User = get_user_model()

SORTS = {
    'newest': '-created_at',
    'price_low': 'price',
    'price_high': '-price',
    'year_new': '-year',
    'mileage_low': 'mileage',
    'popular': '-views_count',
}


def _is_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', '')


def _back(request, fallback='cars:browse'):
    nxt = request.POST.get('next') or request.headers.get('referer')
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(nxt)
    return redirect(fallback)


# ======================
# BROWSE & SEARCH
# ======================

def _apply_text_query(qs, text):
    """Free-text search: '2020 toyota camry lagos' → year range, then every word must match a field."""
    years = [int(y) for y in re.findall(r'\b(19[89]\d|20\d{2})\b', text)]
    if years:
        qs = qs.filter(year__gte=min(years), year__lte=max(years))
        text = re.sub(r'\b(19[89]\d|20\d{2})\b', ' ', text)
    for word in re.findall(r'[\w-]+', text)[:6]:
        qs = qs.filter(
            Q(brand__icontains=word) | Q(model__icontains=word) | Q(trim__icontains=word)
            | Q(location__icontains=word) | Q(state__icontains=word) | Q(body_type__iexact=word)
        )
    return qs


def browse(request):
    form = SearchForm(request.GET or None)
    qs = Car.objects.public().select_related('created_by__profile').prefetch_related('images')
    data = form.cleaned_data if form.is_valid() else {}

    if data.get('q'):
        qs = _apply_text_query(qs, data['q'])
    if data.get('brand'):
        qs = qs.filter(brand__iexact=data['brand'])
    for field, key in (('body_type', 'body'), ('condition', 'condition'), ('engine_type', 'fuel'),
                       ('transmission', 'transmission'), ('state', 'state')):
        if data.get(key):
            qs = qs.filter(**{field: data[key]})
    if data.get('min_price') is not None:
        qs = qs.filter(price__gte=data['min_price'])
    if data.get('max_price') is not None:
        qs = qs.filter(price__lte=data['max_price'])
    if data.get('min_year'):
        qs = qs.filter(year__gte=data['min_year'])
    if data.get('max_year'):
        qs = qs.filter(year__lte=data['max_year'])
    if data.get('max_mileage') is not None:
        qs = qs.filter(mileage__lte=data['max_mileage'])

    sort = data.get('sort') or 'newest'
    qs = qs.order_by(SORTS.get(sort, '-created_at'), '-id')

    page = Paginator(qs, settings.ITEMS_PER_PAGE).get_page(request.GET.get('page'))
    page.object_list = services.annotate_insights(list(page.object_list))
    public = Car.objects.public()

    return render(request, 'cars/browse.html', {
        'form': form,
        'page_obj': page,
        'sort': sort,
        'active_filters': _active_filters(request, data),
        'heading': _browse_heading(data),
        'brands': public.values('brand').annotate(n=Count('id')).order_by('brand'),
        'body_counts': {row['body_type']: row['n'] for row in public.values('body_type').annotate(n=Count('id'))},
        'body_types': BODY_TYPE_CHOICES,
        'year_options': [str(y) for y in range(timezone.now().year + 1, 2009, -1)],
        'mileage_options': ['20000', '50000', '80000', '120000', '160000'],
        'saved_ids': set(services.wishlist_car_ids(request)),
    })


FILTER_LABELS = {
    'q': lambda v: f'“{v}”',
    'brand': str,
    'body': dict(BODY_TYPE_CHOICES).get,
    'condition': dict(CONDITION_CHOICES).get,
    'fuel': dict(ENGINE_CHOICES).get,
    'transmission': dict(TRANSMISSION_CHOICES).get,
    'state': lambda v: f'In {v}',
    'min_price': lambda v: f'From {naira_compact(v)}',
    'max_price': lambda v: f'Up to {naira_compact(v)}',
    'min_year': lambda v: f'{v} or newer',
    'max_year': lambda v: f'{v} or older',
    'max_mileage': lambda v: f'Under {v:,} km',
}


def _active_filters(request, data):
    """Readable chips for applied filters, each with a link that removes just that filter."""
    chips = []
    for key, label in FILTER_LABELS.items():
        value = data.get(key)
        if value in (None, ''):
            continue
        query = request.GET.copy()
        query.pop(key, None)
        query.pop('page', None)
        chips.append({'label': label(value), 'remove_url': f'?{query.urlencode()}'})
    return chips


def _browse_heading(data):
    parts = []
    if data.get('condition'):
        parts.append(dict(CONDITION_CHOICES)[data['condition']])
    if data.get('fuel') in ('hybrid', 'electric'):
        parts.append(dict(ENGINE_CHOICES)[data['fuel']].lower())
    parts.append(data.get('brand') or '')
    body = dict(BODY_TYPE_CHOICES).get(data.get('body'), '')
    parts.append(f'{body}s' if body else 'cars')
    where = f" in {data['state']}" if data.get('state') else ' in Nigeria'
    text = ' '.join(p for p in parts if p).strip()
    return f'{text[:1].upper()}{text[1:]} for sale{where}'


@require_GET
def suggest(request):
    """Search-box autocomplete: brands and brand+model pairs."""
    term = request.GET.get('q', '').strip()
    if len(term) < 2:
        return JsonResponse({'results': []})
    rows = (Car.objects.public()
            .filter(Q(brand__icontains=term) | Q(model__icontains=term))
            .values('brand', 'model').annotate(n=Count('id')).order_by('-n')[:8])
    return JsonResponse({'results': [
        {'label': f"{r['brand']} {r['model']}", 'count': r['n'],
         'url': f"{reverse('cars:browse')}?{urlencode({'brand': r['brand'], 'q': r['model']})}"} for r in rows
    ]})


def legacy_category(request, category):
    mapping = {'new': 'condition=new', 'used': 'condition=foreign_used', 'hybrid': 'fuel=hybrid', 'electric': 'fuel=electric'}
    return redirect(f"{reverse('cars:browse')}?{mapping.get(category.lower(), '')}")


def legacy_search(request):
    return redirect(f"{reverse('cars:browse')}?q={request.GET.get('statement_search', '')}")


# ======================
# CAR DETAIL
# ======================

def car_detail(request, slug):
    car = get_object_or_404(
        Car.objects.select_related('created_by__profile').prefetch_related('images', 'features'), slug=slug,
    )
    is_owner = request.user.is_authenticated and car.created_by_id == request.user.pk
    if car.approval_status != 'approved' and not (is_owner or request.user.is_staff):
        return render(request, 'cars/unavailable.html', {'car': car}, status=404)

    Car.objects.filter(pk=car.pk).update(views_count=F('views_count') + 1)
    services.remember_viewed(request, car)

    seller = car.created_by
    seller_profile = getattr(seller, 'profile', None) if seller else None
    rating = None
    if seller_profile:
        rating = seller_profile.reviews.approved().aggregate(avg=Avg('rating'), n=Count('id'))

    similar = list(Car.objects.public().exclude(pk=car.pk)
                   .filter(Q(body_type=car.body_type) | Q(brand=car.brand))
                   .filter(price__gte=car.price * 6 / 10, price__lte=car.price * 15 / 10)
                   .select_related('created_by__profile').prefetch_related('images')[:4])
    recent = services.recently_viewed(request, exclude=car)
    services.annotate_insights([car, *similar, *recent])

    features_by_group = {}
    for feature in car.features.all():
        features_by_group.setdefault(feature.category or 'Other', []).append(feature)

    return render(request, 'cars/detail.html', {
        'car': car,
        'images': list(car.images.all()),
        'is_owner': is_owner,
        'seller': seller,
        'seller_profile': seller_profile,
        'seller_listings': Car.objects.public().filter(created_by=seller).count() if seller else 0,
        'rating': rating,
        'features_by_group': features_by_group,
        'similar': similar,
        'recent': recent,
        'in_cart': car.pk in services.cart_car_ids(request),
        'saved': car.pk in services.wishlist_car_ids(request),
        'deposit': services.deposit_for(car),
        'balance': car.price - services.deposit_for(car),
        'saved_ids': set(services.wishlist_car_ids(request)),
    })


@login_required
@require_POST
def contact_seller(request, slug):
    car = get_object_or_404(Car.objects.public(), slug=slug)
    seller = car.created_by
    text = request.POST.get('message', '').strip()[:2000]
    if not seller or seller == request.user:
        messages.error(request, 'You cannot message yourself about your own listing.')
        return redirect(car)
    if not text:
        messages.error(request, 'Write a message for the seller.')
        return redirect(car)

    convo = (Conversation.objects.filter(car=car, participants=request.user)
             .filter(participants=seller).first())
    if not convo:
        convo = Conversation.objects.create(car=car)
        convo.participants.add(request.user, seller)
    Message.objects.create(conversation=convo, sender=request.user, content=text)
    messages.success(request, 'Message sent — the seller has been notified.')
    return redirect('users:conversation', convo_id=convo.pk)


# ======================
# CART & WISHLIST
# ======================

def cart_view(request):
    cars = services.cart_cars(request)
    return render(request, 'cars/cart.html', {
        'cars': cars,
        'summary': services.cart_summary(cars),
        'deposit_per_car': settings.CAR_RESERVATION_DEPOSIT,
    })


def _login_redirect(next_url):
    return f"{reverse('account_login')}?{urlencode({'next': next_url})}"


@require_POST
def cart_add(request, car_id):
    car = get_object_or_404(Car.objects.public(), pk=car_id)
    if not car.is_available:
        msg = 'This car has already been reserved.'
        if _is_ajax(request):
            return JsonResponse({'ok': False, 'error': msg}, status=409)
        messages.error(request, msg)
        return _back(request)
    if car.created_by_id and car.created_by_id == request.user.pk:
        msg = "That's your own listing."
        if _is_ajax(request):
            return JsonResponse({'ok': False, 'error': msg}, status=400)
        messages.error(request, msg)
        return _back(request)

    services.add_to_cart(request, car)
    buy_now = bool(request.POST.get('buy_now'))

    if not request.user.is_authenticated:
        # Reserving needs an account: keep the car in the guest cart (merged at sign-in) and come back to it.
        next_url = reverse('cars:checkout') if buy_now else car.get_absolute_url()
        if _is_ajax(request):
            return JsonResponse({'ok': False, 'auth_required': True, 'login_url': _login_redirect(next_url),
                                 'error': 'Sign in to reserve this car.'}, status=401)
        messages.info(request, f'Sign in to reserve the {car.title}. We saved it to your cart.')
        return redirect(_login_redirect(next_url))

    count = len(services.cart_car_ids(request))
    if _is_ajax(request):
        return JsonResponse({'ok': True, 'cart_count': count, 'message': f'{car.title} added to your cart'})
    if buy_now:
        return redirect('cars:checkout')
    messages.success(request, f'{car.title} added to your cart.')
    return _back(request)


@require_POST
def cart_remove(request, car_id):
    services.remove_from_cart(request, car_id)
    if _is_ajax(request):
        return JsonResponse({'ok': True, 'cart_count': len(services.cart_car_ids(request))})
    return redirect('cars:cart')


@require_POST
def wishlist_toggle(request, car_id):
    car = get_object_or_404(Car.objects.public(), pk=car_id)
    saved = services.toggle_wishlist(request, car)
    if _is_ajax(request):
        return JsonResponse({'ok': True, 'saved': saved, 'count': len(services.wishlist_car_ids(request))})
    messages.success(request, 'Saved to your list.' if saved else 'Removed from your saved cars.')
    return _back(request)


def wishlist_view(request):
    ids = services.wishlist_car_ids(request)
    cars = (Car.objects.filter(pk__in=ids, approval_status='approved')
            .select_related('created_by__profile').prefetch_related('images'))
    return render(request, 'cars/saved.html', {'cars': services.annotate_insights(list(cars)), 'saved_ids': set(ids)})


# ======================
# CHECKOUT (cart -> details -> review & pay -> confirmation)
# ======================

CHECKOUT_SESSION_KEY = 'checkout_details'


def _checkout_cars(request):
    cars = services.cart_cars(request)
    return [c for c in cars if c.is_available], [c for c in cars if not c.is_available]


@login_required
def checkout(request):
    """Step 2: contact details (email is the account email) and inspection preferences."""
    cars, unavailable = _checkout_cars(request)
    if not cars:
        messages.info(request, 'Your cart is empty. Add a car to reserve it.')
        return redirect('cars:cart')

    user = request.user
    saved = request.session.get(CHECKOUT_SESSION_KEY) or {}
    initial = {'full_name': user.get_full_name(), 'phone': user.profile.phone, 'inspection_state': cars[0].state,
               'preferred_time': 'morning', **saved}
    form = CheckoutDetailsForm(request.POST or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        data = dict(form.cleaned_data)
        data['preferred_date'] = data['preferred_date'].isoformat()
        request.session[CHECKOUT_SESSION_KEY] = data
        if not user.profile.phone:
            user.profile.phone = data['phone']
            user.profile.save(update_fields=['phone'])
        return redirect('cars:checkout_review')

    return render(request, 'cars/checkout.html', {
        'form': form, 'cars': cars, 'unavailable': unavailable, 'summary': services.cart_summary(cars), 'step': 2,
    })


def _payment_methods():
    methods = []
    if payments.is_configured():
        methods.append('paystack')
    if settings.DEMO_CHECKOUT:
        methods.append('demo')
    return methods


@login_required
def checkout_review(request):
    """Step 3: review everything, choose a payment method and pay the deposit."""
    cars, unavailable = _checkout_cars(request)
    details = request.session.get(CHECKOUT_SESSION_KEY)
    if not cars:
        return redirect('cars:cart')
    if not details:
        return redirect('cars:checkout')

    methods = _payment_methods()
    form = PaymentForm(request.POST or None, methods=methods)
    if request.method == 'POST' and form.is_valid():
        method = form.cleaned_data['method']
        contact = {k: details.get(k, '') for k in ('full_name', 'phone', 'inspection_state', 'preferred_time', 'notes')}
        contact.update(email=request.user.email, preferred_date=date.fromisoformat(details['preferred_date']))
        with transaction.atomic():
            # Lock the rows so two buyers can't reserve the same car at once.
            locked = list(Car.objects.select_for_update().filter(pk__in=[c.pk for c in cars], status='available'))
            if len(locked) != len(cars):
                messages.error(request, 'One of the cars was just reserved by someone else. Please review your cart.')
                return redirect('cars:cart')
            order = services.create_order(request.user, cars, contact, provider=method)

        if method == 'paystack':
            try:
                return redirect(payments.initialize(order, request.build_absolute_uri(reverse('cars:paystack_callback'))))
            except payments.PaymentError as exc:
                order.status = 'failed'
                order.save(update_fields=['status'])
                messages.error(request, str(exc))
                return redirect('cars:checkout_review')

        order.mark_paid(reference=f'DEMO-{order.number}')
        services.clear_cart(request)
        request.session.pop(CHECKOUT_SESSION_KEY, None)
        return redirect(f'{order.get_absolute_url()}?confirmed=1')

    return render(request, 'cars/checkout_review.html', {
        'form': form, 'cars': cars, 'unavailable': unavailable, 'summary': services.cart_summary(cars),
        'details': {**details, 'preferred_date': date.fromisoformat(details['preferred_date'])},
        'time_label': dict(Order.TIME_SLOTS).get(details.get('preferred_time'), ''),
        'methods': methods, 'step': 3,
    })


@login_required
def paystack_callback(request):
    reference = request.GET.get('reference', '')
    order = get_object_or_404(Order, payment_reference=reference, user=request.user)
    tx = payments.verify(reference)
    if tx and int(tx.get('amount', 0)) == int(order.deposit_total * 100):
        order.mark_paid(reference)
        services.clear_cart(request)
        request.session.pop(CHECKOUT_SESSION_KEY, None)
        return redirect(f'{order.get_absolute_url()}?confirmed=1')
    if order.status != 'paid':
        messages.error(request, "We couldn't confirm your payment yet. If you were charged, it will update shortly.")
    return redirect(order)


@csrf_exempt
@require_POST
def paystack_webhook(request):
    if not payments.valid_webhook_signature(request.body, request.headers.get('x-paystack-signature', '')):
        return HttpResponseBadRequest('invalid signature')
    try:
        event = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest('invalid json')
    if event.get('event') == 'charge.success':
        data = event.get('data') or {}
        order = Order.objects.filter(payment_reference=data.get('reference', '')).first()
        if order and int(data.get('amount', 0)) == int(order.deposit_total * 100):
            order.mark_paid(order.payment_reference)
    return HttpResponse(status=200)


# ======================
# ORDERS (buyer) & RESERVATIONS (seller)
# ======================

@login_required
def orders(request):
    return render(request, 'cars/orders.html', {
        'orders': request.user.orders.exclude(status='failed').prefetch_related('items').all(),
    })


@login_required
def order_detail(request, number):
    order = get_object_or_404(Order.objects.prefetch_related('items__car', 'items__seller__profile'),
                              number=number, user=request.user)
    return render(request, 'cars/order_detail.html', {
        'order': order, 'confirmed': request.GET.get('confirmed') == '1', 'cancel_form': CancelReservationForm(),
    })


@login_required
@require_POST
def order_item_cancel(request, item_id):
    item = get_object_or_404(OrderItem.objects.select_related('order', 'car', 'seller'), pk=item_id, order__user=request.user)
    form = CancelReservationForm(request.POST)
    if item.is_active and form.is_valid():
        services.cancel_reservation(item, request.user, 'buyer', form.cleaned_data['reason'])
        if item.refund_status == 'refunded':
            messages.success(request, 'Reservation cancelled and your deposit refunded.')
        else:
            messages.success(request, 'Reservation cancelled. Your deposit refund is being processed.')
    else:
        messages.error(request, 'This reservation can no longer be cancelled.')
    return redirect(item.order)


@login_required
def sales(request):
    mine = OrderItem.objects.filter(seller=request.user).exclude(status='awaiting_payment')
    status = request.GET.get('status', 'active')
    items = mine.select_related('order__user__profile', 'car')
    if status == 'active':
        items = items.filter(status__in=['reserved', 'scheduled'])
    elif status in ('completed', 'cancelled'):
        items = items.filter(status=status)
    counts = dict(mine.values_list('status').annotate(n=Count('id')))
    return render(request, 'cars/sales.html', {
        'items': items, 'status': status,
        'counts': {'active': counts.get('reserved', 0) + counts.get('scheduled', 0),
                   'completed': counts.get('completed', 0), 'cancelled': counts.get('cancelled', 0)},
    })


@login_required
@require_POST
def sale_action(request, item_id):
    item = get_object_or_404(OrderItem.objects.select_related('order__user', 'car'), pk=item_id, seller=request.user)
    action = request.POST.get('action')
    if action == 'schedule' and item.status in ('reserved', 'scheduled'):
        form = ScheduleInspectionForm(request.POST)
        if form.is_valid():
            services.schedule_inspection(item, form.cleaned_data['inspection_at'], form.cleaned_data['inspection_address'],
                                         form.cleaned_data['seller_note'], request.user)
            messages.success(request, 'Inspection scheduled. The buyer has been notified.')
        else:
            messages.error(request, 'Enter a valid inspection date, time and address.')
    elif action == 'complete' and item.status == 'scheduled':
        services.complete_sale(item, request.user)
        messages.success(request, f'Sale of {item.title} completed. Congratulations!')
    elif action == 'cancel' and item.is_active:
        form = CancelReservationForm(request.POST)
        if form.is_valid():
            services.cancel_reservation(item, request.user, 'seller', form.cleaned_data['reason'])
            messages.success(request, 'Reservation cancelled and the buyer refunded.')
        else:
            messages.error(request, 'Tell the buyer why you are cancelling.')
    else:
        messages.error(request, "That action isn't available for this reservation.")
    return redirect('cars:sales')


# ======================
# SELLING
# ======================

def sell(request):
    return render(request, 'cars/sell.html', {
        'live_count': Car.objects.public().count(),
        'seller_count': Car.objects.public().values('created_by').distinct().count(),
    })


def _save_photos(car, photos):
    start = car.images.count()
    for i, photo in enumerate(photos):
        CarImage.objects.create(car=car, image=photo, alt_text=car.full_title, display_order=start + i)


@login_required
def listing_create(request):
    form = ListingForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        car = form.save(commit=False)
        car.created_by = request.user
        car.save()
        form.save_m2m()
        _save_photos(car, form.cleaned_data['photos'])
        if car.approval_status == 'approved':
            messages.success(request, 'Your listing is live!')
        else:
            messages.success(request, 'Listing submitted — our team reviews new listings within 24 hours.')
            for admin in User.objects.filter(is_staff=True):
                Notification.objects.create(user=admin, actor=request.user, verb='listing_submitted',
                                            message=f'New listing to review: {car.full_title}', link=reverse('cars:moderation'))
        return redirect('cars:my_listings')
    return render(request, 'cars/listing_form.html', {'form': form, 'brands': _brand_options()})


@login_required
def listing_edit(request, slug):
    car = get_object_or_404(Car, slug=slug, created_by=request.user)
    form = ListingForm(request.POST or None, request.FILES or None, instance=car)
    if request.method == 'POST' and form.is_valid():
        car = form.save(commit=False)
        if car.approval_status == 'rejected' or (car.approval_status == 'approved' and not car._uploader_is_trusted()):
            car.approval_status = 'pending'  # edited listings from new sellers are re-reviewed
        car.save()
        form.save_m2m()
        _save_photos(car, form.cleaned_data['photos'])
        messages.success(request, 'Listing updated.')
        return redirect('cars:my_listings')
    return render(request, 'cars/listing_form.html', {'form': form, 'car': car, 'brands': _brand_options()})


@login_required
@require_POST
def listing_status(request, slug):
    car = get_object_or_404(Car, slug=slug, created_by=request.user)
    action = request.POST.get('action')
    if action == 'sold':
        car.status = 'sold'
        car.save(update_fields=['status', 'updated_at'])
        messages.success(request, f'{car.title} marked as sold. Congratulations!')
    elif action == 'available' and car.status != 'reserved':
        car.status = 'available'
        car.save(update_fields=['status', 'updated_at'])
        messages.success(request, f'{car.title} is listed as available again.')
    elif action == 'delete_photo':
        car.images.filter(pk=request.POST.get('photo_id')).delete()
        return redirect('cars:listing_edit', slug=car.slug)
    return redirect('cars:my_listings')


@login_required
def my_listings(request):
    listings = Car.objects.by_seller(request.user).prefetch_related('images').annotate(
        enquiries=Count('conversations', distinct=True),
        saves=Count('wishlisted_by', distinct=True),
    )
    stats = {
        'live': sum(1 for c in listings if c.approval_status == 'approved' and c.status == 'available'),
        'pending': sum(1 for c in listings if c.approval_status == 'pending'),
        'views': sum(c.views_count for c in listings),
        'enquiries': sum(c.enquiries for c in listings),
    }
    return render(request, 'cars/my_listings.html', {'listings': listings, 'stats': stats})


def _brand_options():
    return Car.objects.order_by('brand').values_list('brand', flat=True).distinct()


# ======================
# MODERATION (staff)
# ======================

@staff_member_required
def moderation(request):
    status = request.GET.get('status', 'pending')
    qs = (Car.objects.filter(approval_status=status)
          .select_related('created_by__profile').prefetch_related('images', 'features')
          .order_by('created_at' if status == 'pending' else '-approved_at'))
    page = Paginator(qs, 10).get_page(request.GET.get('page'))
    cars = services.annotate_insights(list(page.object_list))
    listing_counts = dict(Car.objects.filter(created_by__in={c.created_by_id for c in cars})
                          .values_list('created_by').annotate(n=Count('id')))
    for car in cars:
        photos = len(car.images.all())
        car.review_checks = [
            (photos >= 3, f'{photos} photo{"s" if photos != 1 else ""}'),
            (bool(car.vin), 'VIN provided' if car.vin else 'No VIN'),
            (len(car.description) >= 80, 'Detailed description' if len(car.description) >= 80 else 'Short description'),
            (not car.insight or car.insight['level'] != 'great' or car.insight['pct'] > -30,
             'Price looks realistic' if not car.insight or car.insight['pct'] > -30 else 'Suspiciously cheap'),
        ]
        car.seller_listings = listing_counts.get(car.created_by_id, 0)
    page.object_list = cars
    return render(request, 'cars/moderation.html', {
        'section': 'listings',
        'page_obj': page,
        'status': status,
        'counts': dict(Car.objects.values_list('approval_status').annotate(n=Count('id'))),
        'reasons': ['Photos are not of the actual car', 'Price looks unrealistic', 'Add more photos (front, back, interior)',
                    'Description is too short', 'Duplicate listing'],
    })


@staff_member_required
@require_POST
def moderate(request, car_id):
    car = get_object_or_404(Car, pk=car_id)
    decision = request.POST.get('decision')
    reason = request.POST.get('reason', '').strip()[:500]
    if decision not in ('approve', 'reject'):
        return HttpResponseBadRequest('unknown decision')
    (car.approve if decision == 'approve' else car.reject)(request.user, reason)

    uploader = car.created_by
    if uploader:
        verb = 'approved' if decision == 'approve' else 'rejected'
        text = f'Your listing "{car.full_title}" was {verb}.' + (f' Note: {reason}' if reason else '')
        Notification.objects.create(user=uploader, actor=request.user, verb=verb, message=text,
                                    link=car.get_absolute_url() if decision == 'approve' else reverse('cars:my_listings'))
        send_branded(uploader.email, f'Your CarHub listing was {verb}', heading=f'Your listing was {verb}', body=text,
                     cta_url=car.get_absolute_url() if decision == 'approve' else reverse('cars:my_listings'),
                     cta_label='View listing' if decision == 'approve' else 'Edit listing')

    if _is_ajax(request):
        return JsonResponse({'ok': True, 'status': car.approval_status})
    messages.success(request, f'{car.full_title} {car.get_approval_status_display().lower()}.')
    return redirect('cars:moderation')


# ======================
# SELLERS
# ======================

def seller_profile(request, seller_id):
    seller = get_object_or_404(User.objects.select_related('profile'), pk=seller_id, is_active=True)
    profile = seller.profile
    form = ReviewForm(request.POST or None)

    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect(f"{settings.LOGIN_URL}?next={request.path}")
        if request.user == seller:
            messages.error(request, "You can't review yourself.")
        elif form.is_valid():
            Review.objects.update_or_create(profile=profile, reviewer=request.user,
                                            defaults={**form.cleaned_data, 'status': 'pending', 'moderation_note': ''})
            messages.success(request, 'Thanks! Your review will appear once our team has checked it, usually within a day.')
            return redirect(f'{request.path}#reviews')

    inventory = Car.objects.public().filter(created_by=seller)
    brand = request.GET.get('brand', '')
    sort = request.GET.get('sort', 'newest')
    listings = inventory.filter(brand=brand) if brand else inventory
    listings = listings.order_by({'price_asc': 'price', 'price_desc': '-price', 'year': '-year'}.get(sort, '-created_at'))
    listings = listings.prefetch_related('images')
    listings_page = Paginator(listings, 9).get_page(request.GET.get('page'))
    listings_page.object_list = services.annotate_insights(list(listings_page.object_list))
    reviews = profile.reviews.approved().select_related('reviewer').order_by('-created_at')
    my_review = (profile.reviews.filter(reviewer=request.user).exclude(status='approved').first()
                 if request.user.is_authenticated else None)
    agg = reviews.aggregate(
        overall=Avg('rating'), communication=Avg('communication'), professionalism=Avg('professionalism'),
        punctuality=Avg('punctuality'), condition=Avg('condition'), n=Count('id'),
    )
    breakdown = [(label, agg[key]) for key, label in (
        ('communication', 'Communication'), ('professionalism', 'Professionalism'),
        ('punctuality', 'Punctuality'), ('condition', 'Car as described'))] if agg['n'] else []

    return render(request, 'cars/seller.html', {
        'seller': seller,
        'profile': profile,
        'listings_page': listings_page,
        'listing_count': inventory.count(),
        'sold_count': Car.objects.filter(created_by=seller, status='sold').count(),
        'recently_sold': Car.objects.filter(created_by=seller, status='sold').prefetch_related('images').order_by('-updated_at')[:4],
        'inventory_brands': inventory.values('brand').annotate(n=Count('id')).order_by('-n', 'brand'),
        'price_range': inventory.aggregate(low=Min('price'), high=Max('price')),
        'brand': brand,
        'sort': sort,
        'certifications': [c.strip() for c in profile.certifications.replace('\n', ',').split(',') if c.strip()],
        'reviews_page': Paginator(reviews, 5).get_page(request.GET.get('rpage')),
        'my_review': my_review,
        'agg': agg,
        'breakdown': breakdown,
        'form': form,
        'saved_ids': set(services.wishlist_car_ids(request)),
    })
