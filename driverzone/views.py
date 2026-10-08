import json
from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum
from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from users.models import Application

from . import services
from .forms import BookingForm, DriverApplicationForm, RatingForm
from .models import DriverProfile, Trip, TripRating

CITIES = {
    'Lagos': {'lat': 6.5244, 'lng': 3.3792, 'zoom': 12},
    'Abuja': {'lat': 9.0579, 'lng': 7.4951, 'zoom': 12},
}


def _ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


def _money(value):
    return f'₦{Decimal(value):,.0f}'


# ---------------------------------------------------------------- rider

def home(request):
    active = None
    if request.user.is_authenticated:
        active = request.user.trips.filter(status__in=Trip.ACTIVE).first()
    online = DriverProfile.objects.filter(is_online=True, is_active=True, license_verified=True)
    return render(request, 'driverzone/home.html', {
        'active_trip': active,
        'cities_json': json.dumps(CITIES),
        'online_count': online.count(),
        'chauffeurs': online.filter(offers_chauffeur=True).select_related('user').order_by('-rating_avg')[:4],
        'surge': services.surge_for(),
        'rates': services.RATES, 'booking_fee': services.BOOKING_FEE,
    })


@require_GET
def api_quote(request):
    try:
        pickup = (float(request.GET['plat']), float(request.GET['plng']))
        dropoff = (float(request.GET['dlat']), float(request.GET['dlng'])) if request.GET.get('dlat') else None
        hours = int(request.GET.get('hours') or 0)
    except (KeyError, ValueError):
        return HttpResponseBadRequest('pickup required')
    q = services.quote(pickup, dropoff, hours)
    r = q['route']
    return JsonResponse({
        'surge': str(q['surge']),
        'route': {'coords': r['coords'], 'distance_km': round(r['distance_m'] / 1000, 1),
                  'duration_min': max(1, round(r['duration_s'] / 60)), 'source': r['source']} if r else None,
        'options': [{**o, 'fare': str(o['fare']), 'fare_display': _money(o['fare']),
                     'rate': str(o.get('rate', '')), 'eta_min': max(1, round(o['eta_s'] / 60)) if o['eta_s'] else None}
                    for o in q['options']],
    })


@require_GET
def api_nearby(request):
    try:
        lat, lng = float(request.GET['lat']), float(request.GET['lng'])
    except (KeyError, ValueError):
        return HttpResponseBadRequest('lat/lng required')
    near = services.available_drivers(lat, lng)[:15]
    return JsonResponse({'drivers': [{'lat': round(d.lat, 5), 'lng': round(d.lng, 5), 'heading': d.heading,
                                      'cls': d.vehicle_class, 'm': int(m)} for m, d in near]})


@login_required
@require_POST
def book(request):
    if request.user.trips.filter(status__in=Trip.ACTIVE, scheduled_for__isnull=True).exists():
        msg = 'You already have a trip in progress.'
        return JsonResponse({'error': msg}, status=409) if _ajax(request) else redirect('driverzone:home')
    form = BookingForm(request.POST)
    if not form.is_valid():
        msg = ' '.join(e for errs in form.errors.values() for e in errs)
        if _ajax(request):
            return JsonResponse({'error': msg}, status=400)
        messages.error(request, msg)
        return redirect('driverzone:home')
    try:
        trip = services.request_trip(request.user, form.cleaned_data)
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400) if _ajax(request) else redirect('driverzone:home')
    url = trip.get_absolute_url()
    return JsonResponse({'ok': True, 'url': url}) if _ajax(request) else redirect(url)


def _trip_for(request, number):
    trip = get_object_or_404(Trip.objects.select_related('driver__user__profile', 'rider'), number=number)
    user = request.user
    is_driver = bool(trip.driver and trip.driver.user_id == user.id)
    if not (trip.rider_id == user.id or is_driver or user.is_staff):
        raise Http404
    return trip, is_driver


@login_required
def trip(request, number):
    t, is_driver = _trip_for(request, number)
    services.advance_simulation(t)
    return render(request, 'driverzone/trip.html', {
        'trip': t, 'is_driver': is_driver, 'rating_form': RatingForm(),
        'compliments': RatingForm.COMPLIMENTS, 'cancel_fee': services.CANCEL_FEE_AFTER_ARRIVAL,
        'trip_json': json.dumps({
            'liveUrl': reverse('driverzone:api_live', args=[t.number]), 'status': t.status,
            'pickup': [t.pickup_lat, t.pickup_lng], 'dropoff': [t.dropoff_lat, t.dropoff_lng] if t.dropoff_lat is not None else None,
            'route': t.route, 'approach': t.approach_route,
        }),
    })


@login_required
@require_GET
def api_live(request, number):
    t, _ = _trip_for(request, number)
    return JsonResponse(services.live_state(t))


@login_required
@require_POST
def trip_cancel(request, number):
    t, is_driver = _trip_for(request, number)
    if t.status not in ('requested', 'accepted', 'arrived'):
        messages.error(request, 'This trip can no longer be cancelled.')
    else:
        fee = services.cancel(t, 'driver' if is_driver else 'rider', request.POST.get('reason', ''))
        messages.success(request, f'Trip cancelled. A {_money(fee)} late-cancellation fee applies.' if fee else 'Trip cancelled. No charge.')
    return redirect('driverzone:dashboard' if is_driver else t.get_absolute_url())


@login_required
@require_POST
def trip_rate(request, number):
    t, _ = _trip_for(request, number)
    if t.rider_id != request.user.id or t.status != 'completed' or hasattr(t, 'rating'):
        return redirect(t)
    form = RatingForm(request.POST)
    if form.is_valid():
        d = form.cleaned_data
        TripRating.objects.create(trip=t, stars=d['stars'], compliments=', '.join(d['compliments']),
                                  comment=d['comment'], tip=d['tip'] or 0)
        if t.driver:
            t.driver.refresh_rating()
        messages.success(request, 'Thanks for rating your trip!')
    else:
        messages.error(request, 'Pick a star rating.')
    return redirect(t)


@login_required
def trips(request):
    qs = request.user.trips.select_related('driver__user').prefetch_related('rating')
    return render(request, 'driverzone/trips.html', {
        'page_obj': Paginator(qs, 15).get_page(request.GET.get('page')),
        'spent': qs.filter(status='completed').aggregate(s=Sum('fare_final'))['s'] or 0,
        'count': qs.filter(status='completed').count(),
    })


def drivers(request):
    qs = DriverProfile.objects.filter(is_active=True, license_verified=True, offers_chauffeur=True).select_related('user')
    city = request.GET.get('city', '')
    if city:
        qs = qs.filter(city=city)
    return render(request, 'driverzone/drivers.html', {'drivers': qs.order_by('-is_online', '-rating_avg')[:30],
                                                       'city': city, 'cities': list(CITIES)})


def driver(request, pk):
    d = get_object_or_404(DriverProfile.objects.select_related('user'), pk=pk, is_active=True, license_verified=True)
    ratings = TripRating.objects.filter(trip__driver=d).select_related('trip__rider').order_by('-created_at')
    compliments = {}
    for r in ratings:
        for c in filter(None, (x.strip() for x in r.compliments.split(','))):
            compliments[c] = compliments.get(c, 0) + 1
    return render(request, 'driverzone/driver.html', {
        'd': d, 'ratings': ratings.exclude(comment='')[:6],
        'compliments': sorted(compliments.items(), key=lambda x: -x[1])[:6],
        'breakdown': [(n, ratings.filter(stars=n).count()) for n in (5, 4, 3, 2, 1)],
        'chauffeur_day': services.chauffeur_fare(services.CHAUFFEUR_DAY_HOURS, d.hourly_rate),
    })


# ---------------------------------------------------------------- become a driver

def drive(request):
    app, profile = None, None
    if request.user.is_authenticated:
        profile = getattr(request.user, 'driver_profile', None)
        if profile and profile.license_verified:
            return redirect('driverzone:dashboard')
        app = Application.objects.filter(user=request.user, role='pilot').order_by('-applied_at').first()
    form = DriverApplicationForm(request.POST or None, request.FILES or None, initial={
        'full_name': request.user.get_full_name() if request.user.is_authenticated else '',
        'phone': request.user.profile.phone if request.user.is_authenticated else ''})
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect(f"{reverse('account_login')}?next={reverse('driverzone:drive')}")
        if form.is_valid() and not (app and app.status == 'pending'):
            new = form.save(commit=False)
            new.user, new.role, new.id_type = request.user, 'pilot', 'drivers_licence'
            new.save()
            messages.success(request, "Application received. We'll verify your licence within 2 working days.")
            return redirect('driverzone:drive')
    return render(request, 'driverzone/drive.html', {'form': form, 'application': app,
                                                     'earnings': services.chauffeur_fare(8, Decimal('4500'))})


# ---------------------------------------------------------------- driver app

def driver_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        profile = getattr(request.user, 'driver_profile', None)
        if not profile or not profile.license_verified or not profile.is_active:
            messages.info(request, 'Get verified as a CarHub driver to use the driver app.')
            return redirect('driverzone:drive')
        request.driver = profile
        return view(request, *args, **kwargs)
    return wrapper


@driver_required
def dashboard(request):
    d = request.driver
    done = d.trips.filter(status='completed')
    today = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    return render(request, 'driverzone/dashboard.html', {
        'd': d,
        'today': {'trips': done.filter(completed_at__gte=today).count(),
                  'earned': done.filter(completed_at__gte=today).aggregate(s=Sum('fare_final'))['s'] or 0},
        'week_earned': done.filter(completed_at__gte=today - timezone.timedelta(days=7)).aggregate(s=Sum('fare_final'))['s'] or 0,
        'recent': done.select_related('rider')[:8],
        'upcoming': d.trips.filter(status='accepted', scheduled_for__gt=timezone.now()).select_related('rider')[:5],
        'state_url': reverse('driverzone:api_driver_state'),
    })


@driver_required
@require_GET
def api_driver_state(request):
    """The driver app polls this: current offer or active trip, with the live state."""
    d = request.driver
    t = (d.trips.filter(status__in=Trip.ACTIVE).filter(scheduled_for__isnull=True) |
         d.trips.filter(status__in=Trip.ACTIVE, scheduled_for__lte=timezone.now() + timezone.timedelta(minutes=45))
         ).select_related('rider__profile').order_by('created_at').first()
    payload = {'online': d.is_online, 'trip': None}
    if t:
        payload['trip'] = {
            'number': t.number, 'status': t.status, 'kind': t.get_kind_display(), 'fare': _money(t.fare_estimate),
            'pickup': {'address': t.pickup_address, 'lat': t.pickup_lat, 'lng': t.pickup_lng},
            'dropoff': {'address': t.dropoff_address, 'lat': t.dropoff_lat, 'lng': t.dropoff_lng} if t.dropoff_lat is not None else None,
            'rider': t.rider.first_name or 'Rider', 'rider_phone': t.rider.profile.phone, 'notes': t.notes,
            'distance_km': t.distance_km, 'duration_min': t.duration_min, 'hours': t.hours,
            'route': t.route, 'action_url': reverse('driverzone:driver_action', args=[t.number]),
            'pickup_m': int(services.haversine_m(d.lat, d.lng, t.pickup_lat, t.pickup_lng)) if d.lat is not None else None,
        }
    return JsonResponse(payload)


@driver_required
@require_POST
def api_driver_location(request):
    d = request.driver
    try:
        lat, lng = float(request.POST['lat']), float(request.POST['lng'])
        heading = float(request.POST.get('heading') or d.heading or 0)
    except (KeyError, ValueError):
        return HttpResponseBadRequest('lat/lng required')
    d.lat, d.lng, d.heading, d.location_updated_at = lat, lng, heading, timezone.now()
    d.is_simulated = False  # a real phone is reporting: stop simulating this driver
    d.save(update_fields=['lat', 'lng', 'heading', 'location_updated_at', 'is_simulated'])
    return JsonResponse({'ok': True})


@driver_required
@require_POST
def api_driver_online(request):
    d = request.driver
    d.is_online = request.POST.get('online') == '1'
    d.save(update_fields=['is_online'])
    return JsonResponse({'ok': True, 'online': d.is_online})


@driver_required
@require_POST
def driver_action(request, number):
    d = request.driver
    t = get_object_or_404(Trip, number=number, driver=d)
    action = request.POST.get('action')
    if action == 'accept' and t.status == 'requested':
        services.accept(t)
    elif action == 'decline' and t.status == 'requested':
        services.dispatch(t, exclude={d.pk})
    elif action == 'arrived' and t.status == 'accepted':
        services.mark_arrived(t)
    elif action == 'start' and t.status == 'arrived':
        services.start(t)
    elif action == 'complete' and t.status == 'in_progress':
        services.complete(t)
    elif action == 'cancel' and t.status in ('accepted', 'arrived'):
        services.cancel(t, 'driver', request.POST.get('reason', ''))
    else:
        return JsonResponse({'error': "That action isn't available now."}, status=409)
    return JsonResponse({'ok': True, 'status': Trip.objects.get(pk=t.pk).status})
