import json
from datetime import timedelta
from decimal import Decimal
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, F, Q, Sum
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from cars import payments
from cars.models import STATE_CHOICES, Car
from core.ratelimit import rate_limit
from users.models import Application

from . import services
from .forms import CheckoutForm, GarageForm, ProductForm, ReviewForm, ShopFilterForm, VendorApplicationForm
from .models import Brand, Category, Fitment, Order, OrderItem, Product, ProductImage, ProductSpec, Review

PER_PAGE = 24


def _ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


def _public():
    return (Product.objects.public().select_related('brand', 'category', 'vendor__profile')
            .prefetch_related('images', 'fitments'))


def vehicle_catalog():
    """{make: [models]} for the "my car" picker: every make/model on CarHub plus every fitment."""
    pairs = set(Car.objects.values_list('brand', 'model').distinct())
    pairs |= set(Fitment.objects.exclude(model='').values_list('make', 'model').distinct())
    catalog = {}
    for make, model in sorted(pairs):
        catalog.setdefault(make, [])
        if model not in catalog[make]:
            catalog[make].append(model)
    return catalog


def _base_context(request):
    vehicle = services.get_vehicle(request)
    qty = services.cart_quantities(request)
    return {'vehicle': vehicle, 'vehicle_label': services.vehicle_label(vehicle),
            'vehicle_catalog_json': json.dumps(vehicle_catalog()), 'parts_cart_qty': qty, 'parts_count': sum(qty.values())}


def _mark_fit(products, vehicle):
    for p in products:
        p.fit = p.fits(vehicle)
    return products


# ---------------------------------------------------------------- storefront

def home(request):
    ctx = _base_context(request)
    vehicle = ctx['vehicle']
    public = _public()
    ctx.update({
        'categories': Category.objects.annotate(n=Count('products', filter=Q(products__in=Product.objects.public()))),
        'deals': _mark_fit(list(public.filter(compare_at_price__gt=F('price')).order_by('-sold_count')[:8]), vehicle),
        'popular': _mark_fit(list(public.order_by('-sold_count')[:8]), vehicle),
        'newest': _mark_fit(list(public.order_by('-created_at')[:4]), vehicle),
        'for_my_car': _mark_fit(list(public.fits(vehicle['make'], vehicle['model'], vehicle['year'])
                                     .filter(universal_fit=False).order_by('-sold_count')[:8]), vehicle) if vehicle else [],
        'brands': Brand.objects.annotate(n=Count('products', filter=Q(products__in=Product.objects.public())))
                       .filter(n__gt=0).order_by('-n')[:12],
        'stats': {'products': public.count(), 'vendors': public.values('vendor').distinct().count()},
    })
    return render(request, 'cas/home.html', ctx)


def shop(request, category_slug=None):
    ctx = _base_context(request)
    vehicle = ctx['vehicle']
    category = get_object_or_404(Category, slug=category_slug) if category_slug else None
    form = ShopFilterForm(request.GET or None)
    form.is_valid()
    f = form.cleaned_data if form.is_bound else {}
    qs = _public()
    if category:
        qs = qs.filter(category=category)
    elif f.get('category'):
        qs = qs.filter(category__slug=f['category'])
    if f.get('q'):
        for word in f['q'].split():
            qs = qs.filter(Q(name__icontains=word) | Q(brand__name__icontains=word) | Q(sku__icontains=word)
                           | Q(category__name__icontains=word) | Q(fitments__model__icontains=word)
                           | Q(fitments__make__icontains=word)).distinct()
    if f.get('brand'):
        qs = qs.filter(brand__slug=f['brand'])
    if f.get('part_type'):
        qs = qs.filter(part_type=f['part_type'])
    if f.get('min_price') is not None:
        qs = qs.filter(price__gte=f['min_price'])
    if f.get('max_price') is not None:
        qs = qs.filter(price__lte=f['max_price'])
    if f.get('in_stock'):
        qs = qs.filter(stock__gt=0)
    if f.get('on_sale'):
        qs = qs.filter(compare_at_price__gt=F('price'))
    if f.get('fits') and vehicle:
        qs = qs.fits(vehicle['make'], vehicle['model'], vehicle['year'])
    sort = f.get('sort') or 'popular'
    qs = qs.order_by({'price_asc': 'price', 'price_desc': '-price', 'newest': '-created_at',
                      'rating': F('rating_avg').desc(nulls_last=True)}.get(sort, '-sold_count'))
    page = Paginator(qs, PER_PAGE).get_page(request.GET.get('page'))
    page.object_list = _mark_fit(list(page.object_list), vehicle)

    base = _public().filter(category=category) if category else _public()
    ctx.update({
        'category': category, 'form': form, 'page_obj': page, 'sort': sort, 'f': f,
        'categories': Category.objects.annotate(n=Count('products', filter=Q(products__in=Product.objects.public()))),
        'brand_facets': base.values('brand__slug', 'brand__name').annotate(n=Count('id')).order_by('-n')[:20],
        'total': qs.count(),
    })
    return render(request, 'cas/shop.html', ctx)


def product(request, slug):
    p = get_object_or_404(Product.objects.select_related('brand', 'category', 'vendor__profile')
                          .prefetch_related('images', 'specs', 'fitments'), slug=slug)
    staff_or_owner = request.user.is_authenticated and (request.user.is_staff or request.user == p.vendor)
    if not (p.status == 'approved' and p.is_active) and not staff_or_owner:
        raise Http404
    Product.objects.filter(pk=p.pk).update(views_count=F('views_count') + 1)
    ctx = _base_context(request)
    vehicle = ctx['vehicle']
    p.fit = p.fits(vehicle)
    reviews = p.reviews.filter(status='approved').select_related('user')
    breakdown = {r['rating']: r['n'] for r in reviews.values('rating').annotate(n=Count('id'))}
    my_review = p.reviews.filter(user=request.user).first() if request.user.is_authenticated else None
    related = _public().filter(category=p.category).exclude(pk=p.pk).order_by('-sold_count')[:4]
    vendor_stats = Product.objects.public().filter(vendor=p.vendor).aggregate(n=Count('id'), sold=Sum('sold_count'))
    ctx.update({
        'p': p, 'reviews': reviews[:10], 'my_review': my_review,
        'breakdown': [(n, breakdown.get(n, 0), round(breakdown.get(n, 0) * 100 / (p.rating_count or 1))) for n in (5, 4, 3, 2, 1)],
        'can_review': request.user.is_authenticated and request.user != p.vendor,
        'review_form': ReviewForm(), 'related': _mark_fit(list(related), vehicle),
        'in_cart': ctx['parts_cart_qty'].get(p.pk, 0), 'vendor_stats': vendor_stats,
        'delivery_table': [('Lagos', 2500), ('Abuja (FCT)', 3000), ('South-West', 3500), ('Other states', 5000)],
        'free_delivery_from': services.FREE_DELIVERY_FROM,
        'fitment_groups': _group_fitments(p.fitments.all()),
    })
    return render(request, 'cas/product.html', ctx)


def _group_fitments(fitments):
    groups = {}
    for f in fitments:
        groups.setdefault(f.make, []).append(f)
    return sorted(groups.items())


@require_POST
def garage_set(request):
    form = GarageForm(request.POST)
    nxt = request.POST.get('next') or reverse('cas:shop')
    if form.is_valid():
        v = services.set_vehicle(request, **form.cleaned_data)
        messages.success(request, f'Showing parts for your {services.vehicle_label(v)}.')
        if 'fits=' not in nxt and '/p/' not in nxt:
            nxt += ('&' if '?' in nxt else '?') + 'fits=on'
    else:
        messages.error(request, 'Pick the make, model and year of your car.')
    return redirect(nxt if nxt.startswith('/') else reverse('cas:shop'))


@require_POST
def garage_clear(request):
    services.clear_vehicle(request)
    nxt = request.POST.get('next') or reverse('cas:home')
    return redirect(nxt.replace('fits=on', '') if nxt.startswith('/') else reverse('cas:home'))


# ---------------------------------------------------------------- cart

def cart(request):
    ctx = _base_context(request)
    lines = services.cart_lines(request)
    state = request.GET.get('state') or getattr(getattr(request.user, 'profile', None), 'state_of_origin', '') or ''
    ctx.update({'lines': lines, 'summary': services.summary(lines, state if state in dict(STATE_CHOICES) else ''),
                'suggestions': _mark_fit(list(_public().filter(universal_fit=True).exclude(pk__in=[p.pk for p, _, _ in lines])
                                              .order_by('-sold_count')[:4]), ctx['vehicle'])})
    return render(request, 'cas/cart.html', ctx)


@require_POST
@rate_limit('cas-cart', 60)
def cart_add(request, product_id):
    p = get_object_or_404(Product.objects.public(), pk=product_id)
    if not p.in_stock:
        msg = 'Sorry, this item is out of stock.'
        if _ajax(request):
            return JsonResponse({'error': msg}, status=409)
        messages.error(request, msg)
        return redirect(p)
    qty = services.add_to_cart(request, p, request.POST.get('quantity', 1))
    if _ajax(request):
        return JsonResponse({'ok': True, 'quantity': qty, 'parts_count': services.cart_count(request), 'name': p.name})
    if request.POST.get('buy_now'):
        return redirect('cas:checkout')
    messages.success(request, f'{p.name} added to your parts cart.')
    return redirect(request.POST.get('next') or p.get_absolute_url())


@require_POST
def cart_update(request, product_id):
    p = get_object_or_404(Product, pk=product_id)
    qty = services.set_quantity(request, p, request.POST.get('quantity', 0))
    if _ajax(request):
        lines = services.cart_lines(request)
        s = services.summary(lines)
        return JsonResponse({'ok': True, 'quantity': qty, 'parts_count': services.cart_count(request),
                             'subtotal': str(s['subtotal']), 'to_free_delivery': str(s['to_free_delivery'])})
    return redirect('cas:cart')


# ---------------------------------------------------------------- checkout

def _methods():
    methods = []
    if payments.is_configured():
        methods.append('paystack')
    if settings.DEMO_CHECKOUT:
        methods.append('demo')
    methods.append('pod')
    return methods


@login_required
def checkout(request):
    lines = services.cart_lines(request)
    if not lines:
        messages.info(request, 'Your parts cart is empty.')
        return redirect('cas:cart')
    user = request.user
    initial = {'full_name': user.get_full_name(), 'phone': user.profile.phone, 'city': user.profile.city,
               'delivery_method': 'delivery', 'payment_method': 'paystack' if payments.is_configured() else 'demo'}
    form = CheckoutForm(request.POST or None, initial=initial, methods=_methods())
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        method = d.pop('payment_method')
        s = services.summary(lines, d['state'], d['delivery_method'])
        if method == 'pod' and not services.pod_allowed(d['state'], s['total'], d['delivery_method']):
            form.add_error('payment_method', 'Pay on delivery is available for deliveries in Lagos and Abuja up to ₦500,000.')
        else:
            try:
                order = services.create_order(user, lines, {**d, 'email': user.email}, method)
            except ValueError as exc:
                messages.error(request, str(exc))
                return redirect('cas:cart')
            if not user.profile.phone:
                user.profile.phone = d['phone']
                user.profile.save(update_fields=['phone'])
            if method == 'paystack':
                try:
                    return redirect(payments.initialize(order, request.build_absolute_uri(reverse('cas:paystack_callback'))))
                except payments.PaymentError as exc:
                    order.status = 'failed'
                    order.save(update_fields=['status'])
                    messages.error(request, str(exc))
                    return redirect('cas:checkout')
            order.confirm(reference=f'DEMO-{order.number}' if method == 'demo' else '')
            services.clear_cart(request)
            return redirect(f'{order.get_absolute_url()}?confirmed=1')

    state = form['state'].value() or ''
    method = form['delivery_method'].value() or 'delivery'
    ctx = _base_context(request)
    ctx.update({
        'form': form, 'lines': lines, 'summary': services.summary(lines, state, method),
        'fees_json': json.dumps({s: str(services.delivery_fee(s, Decimal('0'))) for s, _ in STATE_CHOICES}),
        'subtotal': services.summary(lines)['subtotal'], 'free_from': services.FREE_DELIVERY_FROM,
        'pod_states': sorted(services.POD_STATES), 'pod_limit': services.POD_LIMIT,
    })
    return render(request, 'cas/checkout.html', ctx)


@login_required
def paystack_callback(request):
    reference = request.GET.get('reference', '')
    order = get_object_or_404(Order, payment_reference=reference, user=request.user)
    tx = payments.verify(reference)
    if tx and int(tx.get('amount', 0)) == int(order.total * 100):
        order.confirm(reference)
        services.clear_cart(request)
        return redirect(f'{order.get_absolute_url()}?confirmed=1')
    if order.status != 'confirmed':
        messages.error(request, "We couldn't confirm your payment yet. If you were charged, it will update shortly.")
    return redirect(order)


# ---------------------------------------------------------------- buyer orders & reviews

@login_required
def orders(request):
    qs = request.user.parts_orders.exclude(status__in=['failed']).prefetch_related('items')
    return render(request, 'cas/orders.html', {**_base_context(request), 'orders': qs})


@login_required
def order_detail(request, number):
    order = get_object_or_404(Order.objects.prefetch_related('items__vendor__profile'), number=number, user=request.user)
    return render(request, 'cas/order_detail.html', {**_base_context(request), 'order': order,
                                                     'confirmed': request.GET.get('confirmed') == '1'})


@login_required
@require_POST
def order_item_cancel(request, item_id):
    item = get_object_or_404(OrderItem.objects.select_related('order', 'vendor'), pk=item_id, order__user=request.user)
    if item.status in ('pending', 'processing'):
        services.cancel_item(item, request.user, 'buyer', request.POST.get('reason', '').strip()[:300])
        messages.success(request, f'{item.name} cancelled.' + (' Your refund is on its way.' if item.order.is_paid else ''))
    else:
        messages.error(request, 'This item has already shipped, so it can no longer be cancelled.')
    return redirect(item.order)


@login_required
@require_POST
@rate_limit('cas-review', 5)
def review_submit(request, slug):
    p = get_object_or_404(Product.objects.public(), slug=slug)
    if request.user == p.vendor:
        messages.error(request, "You can't review your own product.")
        return redirect(p)
    form = ReviewForm(request.POST)
    if form.is_valid():
        Review.objects.update_or_create(product=p, user=request.user, defaults={
            **form.cleaned_data, 'status': 'pending', 'moderation_note': '',
            'verified_purchase': services.bought(request.user, p)})
        messages.success(request, 'Thanks! Your review will appear once our team has checked it.')
    else:
        messages.error(request, 'Pick a star rating and write at least a sentence.')
    return redirect(f'{p.get_absolute_url()}#reviews')


# ---------------------------------------------------------------- vendors

def vendor_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.profile.is_cas_seller_approved:
            messages.info(request, 'Become an approved vendor to sell parts on CarHub.')
            return redirect('cas:sell')
        return view(request, *args, **kwargs)
    return wrapper


def sell(request):
    app = None
    if request.user.is_authenticated:
        if request.user.profile.is_cas_seller_approved:
            return redirect('cas:vendor')
        app = Application.objects.filter(user=request.user, role='cas_seller').order_by('-applied_at').first()
    form = VendorApplicationForm(request.POST or None, request.FILES or None, initial={
        'full_name': request.user.get_full_name() if request.user.is_authenticated else '',
        'phone': request.user.profile.phone if request.user.is_authenticated else ''})
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect(f"{settings.LOGIN_URL}?next={reverse('cas:sell')}")
        if form.is_valid() and not (app and app.status == 'pending'):
            new = form.save(commit=False)
            new.user, new.role = request.user, 'cas_seller'
            new.save()
            messages.success(request, "Application received. We'll review it within 2 working days.")
            return redirect('cas:sell')
    return render(request, 'cas/sell.html', {**_base_context(request), 'form': form, 'application': app})


@vendor_required
def vendor(request):
    mine = Product.objects.filter(vendor=request.user).select_related('category', 'brand').prefetch_related('images')
    tab = request.GET.get('tab', 'all')
    listing = {'live': mine.filter(status='approved', is_active=True), 'review': mine.exclude(status='approved'),
               'low': mine.filter(stock__lte=5), 'hidden': mine.filter(is_active=False)}.get(tab, mine)
    items = OrderItem.objects.filter(vendor=request.user, order__status='confirmed')
    since = timezone.now() - timedelta(days=30)
    return render(request, 'cas/vendor.html', {
        **_base_context(request), 'products': listing, 'tab': tab,
        'stats': {
            'live': mine.filter(status='approved', is_active=True).count(),
            'review': mine.filter(status='pending').count(),
            'low': mine.filter(stock__lte=5).count(),
            'to_ship': items.filter(status='processing').count(),
            'revenue_30d': sum((i.line_total for i in items.filter(order__created_at__gte=since).exclude(status='cancelled')), Decimal('0')),
        },
        'counts': {'all': mine.count(), 'live': mine.filter(status='approved', is_active=True).count(),
                   'review': mine.exclude(status='approved').count(), 'low': mine.filter(stock__lte=5).count(),
                   'hidden': mine.filter(is_active=False).count()},
    })


@vendor_required
def vendor_orders(request):
    status = request.GET.get('status', 'processing')
    items = (OrderItem.objects.filter(vendor=request.user, order__status='confirmed').select_related('order__user', 'product')
             .order_by('-order__created_at'))
    counts = dict(items.values_list('status').annotate(n=Count('id')))
    return render(request, 'cas/vendor_orders.html', {
        **_base_context(request), 'items': items.filter(status=status), 'status': status, 'counts': counts,
        'stats': {'to_ship': counts.get('processing', 0)},
        'couriers': ['GIG Logistics', 'DHL', 'Kwik Delivery', 'Sendbox', 'Own rider'],
    })


@vendor_required
@require_POST
def vendor_item_action(request, item_id):
    item = get_object_or_404(OrderItem.objects.select_related('order__user'), pk=item_id, vendor=request.user)
    action = request.POST.get('action')
    if action == 'ship' and item.status == 'processing':
        courier = request.POST.get('courier', '').strip()[:80]
        if not courier:
            messages.error(request, 'Choose the courier.')
        else:
            services.ship_item(item, courier, request.POST.get('note', '').strip()[:200], request.user)
            messages.success(request, f'Marked as shipped. {item.order.full_name} has been notified.')
    elif action == 'deliver' and item.status == 'shipped':
        services.deliver_item(item, request.user)
        messages.success(request, 'Marked as delivered.')
    elif action == 'cancel' and item.status == 'processing':
        reason = request.POST.get('reason', '').strip()[:300]
        if not reason:
            messages.error(request, 'Tell the buyer why you are cancelling.')
        else:
            services.cancel_item(item, request.user, 'vendor', reason)
            messages.success(request, 'Item cancelled and the buyer refunded.')
    else:
        messages.error(request, "That action isn't available for this item.")
    return redirect(f"{reverse('cas:vendor_orders')}?status={request.POST.get('return_status', 'processing')}")


@vendor_required
def product_form(request, slug=None):
    product = get_object_or_404(Product, slug=slug, vendor=request.user) if slug else None
    form = ProductForm(request.POST or None, request.FILES or None, instance=product)
    if request.method == 'POST' and form.is_valid():
        p = form.save(commit=False)
        p.vendor = request.user
        p.brand = form.save_brand()
        content_changed = not product or any(k in form.changed_data for k in (
            'name', 'description', 'short_description', 'category', 'photos', 'part_type', 'brand_name'))
        if content_changed:  # new or materially edited products are checked again before going live
            p.status, p.moderation_note = 'pending', ''
        p.save()
        start = p.images.count()
        for i, photo in enumerate(form.cleaned_data['photos']):
            ProductImage.objects.create(product=p, image=photo, alt_text=p.name, display_order=start + i)
        p.specs.all().delete()
        ProductSpec.objects.bulk_create([ProductSpec(product=p, name=n, value=v, display_order=i)
                                         for i, (n, v) in enumerate(form.cleaned_data['specs_text'])])
        p.fitments.all().delete()
        Fitment.objects.bulk_create([Fitment(product=p, make=mk, model=md, year_from=y1, year_to=y2)
                                     for mk, md, y1, y2 in form.cleaned_data['fitment_text']])
        if p.status == 'pending':
            messages.success(request, 'Saved. Our team checks new and edited products before they go live, usually within a day.')
        else:
            messages.success(request, 'Saved.')
        return redirect('cas:vendor')
    return render(request, 'cas/product_form.html', {**_base_context(request), 'form': form, 'product': product})


@vendor_required
@require_POST
def product_quick_update(request, slug):
    """Inline stock / visibility changes from the vendor dashboard (no re-review needed)."""
    p = get_object_or_404(Product, slug=slug, vendor=request.user)
    if 'stock' in request.POST:
        try:
            p.stock = max(0, int(request.POST['stock']))
        except ValueError:
            messages.error(request, 'Stock must be a whole number.')
            return redirect('cas:vendor')
    if 'toggle_active' in request.POST:
        p.is_active = not p.is_active
    p.save(update_fields=['stock', 'is_active', 'updated_at'])
    if _ajax(request):
        return JsonResponse({'ok': True, 'stock': p.stock, 'is_active': p.is_active})
    messages.success(request, f'{p.name} updated.')
    return redirect(request.POST.get('next') or 'cas:vendor')


@vendor_required
@require_POST
def product_image_delete(request, slug, image_id):
    p = get_object_or_404(Product, slug=slug, vendor=request.user)
    if p.images.count() <= 1:
        messages.error(request, 'Keep at least one photo.')
    else:
        img = get_object_or_404(ProductImage, pk=image_id, product=p)
        if img.image:
            img.image.delete(save=False)
        img.delete()
    return redirect('cas:product_edit', slug=p.slug)

