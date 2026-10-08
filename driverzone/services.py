"""Routing, pricing, dispatch and live tracking for DriverZone.

Routes come from OSRM (OpenStreetMap road network) and are cached; if OSRM can't be reached we fall
back to a straight-line estimate so booking never breaks. Prices are computed server-side from the
route, never trusted from the browser.

Live tracking: a real driver's phone posts its GPS position. Demo drivers aren't really driving, so
their trips are *simulated*: the car moves along the stored road route on a compressed clock
(settings.DRIVERZONE_SIM_SPEED), and the trip advances accepted → arrived → on trip → completed.
"""
import hashlib
import logging
import math
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

import requests
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import F
from django.urls import reverse
from django.utils import timezone

from . import realtime
from .models import DriverProfile, Trip

logger = logging.getLogger(__name__)
OSRM = 'https://router.project-osrm.org/route/v1/driving/{a};{b}?overview=full&geometries=geojson'
TRAFFIC = 1.45              # OSRM times are free-flow; Lagos/Abuja traffic is not
ARRIVE_WAIT_S = 12          # simulated seconds the driver waits at pickup
ACCEPT_AFTER_S = 4          # simulated "driver accepts" delay

RATES = {
    #           base, per km, per min, minimum
    'economy': (Decimal('700'), Decimal('260'), Decimal('30'), Decimal('1800')),
    'comfort': (Decimal('1200'), Decimal('420'), Decimal('45'), Decimal('3500')),
}
BOOKING_FEE = Decimal('200')
CHAUFFEUR_MIN_HOURS = 3
CHAUFFEUR_DAY_HOURS = 10    # a full day is billed as 9 hours
CANCEL_FEE_AFTER_ARRIVAL = Decimal('500')


def sim_speed():
    return getattr(settings, 'DRIVERZONE_SIM_SPEED', 8)


# ---------------------------------------------------------------- geometry

def haversine_m(lat1, lng1, lat2, lng2):
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def bearing(lat1, lng1, lat2, lng2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lng2 - lng1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def point_along(coords, fraction):
    """(lat, lng, heading) at a fraction (0..1) of the way along a polyline."""
    if not coords:
        return None
    if len(coords) == 1 or fraction <= 0:
        a, b = coords[0], coords[min(1, len(coords) - 1)]
        return a[0], a[1], bearing(a[0], a[1], b[0], b[1]) if a != b else 0
    seg = [haversine_m(*coords[i], *coords[i + 1]) for i in range(len(coords) - 1)]
    target = sum(seg) * min(1.0, fraction)
    for i, d in enumerate(seg):
        if target <= d or i == len(seg) - 1:
            t = 0 if d == 0 else min(1, target / d)
            (la1, ln1), (la2, ln2) = coords[i], coords[i + 1]
            return la1 + (la2 - la1) * t, ln1 + (ln2 - ln1) * t, bearing(la1, ln1, la2, ln2)
        target -= d
    last = coords[-1]
    return last[0], last[1], 0


def _thin(coords, max_points=350):
    if len(coords) <= max_points:
        return coords
    step = len(coords) / max_points
    return [coords[int(i * step)] for i in range(max_points)] + [coords[-1]]


def route(lat1, lng1, lat2, lng2):
    """Road route between two points: {'coords': [[lat, lng], …], 'distance_m', 'duration_s', 'source'}."""
    key = 'dz-route-' + hashlib.md5(f'{lat1:.5f},{lng1:.5f},{lat2:.5f},{lng2:.5f}'.encode()).hexdigest()
    cached = cache.get(key)
    if cached:
        return cached
    result = None
    try:
        resp = requests.get(OSRM.format(a=f'{lng1},{lat1}', b=f'{lng2},{lat2}'), timeout=6,
                            headers={'User-Agent': 'CarHubPortfolioDemo/1.0'})
        data = resp.json()
        if data.get('code') == 'Ok' and data.get('routes'):
            r = data['routes'][0]
            result = {'coords': _thin([[c[1], c[0]] for c in r['geometry']['coordinates']]),
                      'distance_m': int(r['distance']), 'duration_s': int(r['duration'] * TRAFFIC), 'source': 'osrm'}
    except (requests.RequestException, ValueError, KeyError) as exc:
        logger.warning('OSRM route failed: %s', exc)
    if not result:  # straight-line fallback: roads are ~35% longer, ~24 km/h average in town
        d = haversine_m(lat1, lng1, lat2, lng2) * 1.35
        result = {'coords': [[lat1, lng1], [lat2, lng2]], 'distance_m': int(d), 'duration_s': int(d / 24000 * 3600) + 60,
                  'source': 'estimate'}
    cache.set(key, result, 60 * 60 * 6)
    return result


# ---------------------------------------------------------------- pricing

def surge_for(when=None):
    """Busier weekday rush hours cost a little more."""
    when = timezone.localtime(when or timezone.now())
    if when.weekday() < 5 and (7 <= when.hour < 10 or 16 <= when.hour < 20):
        return Decimal('1.30')
    return Decimal('1.00')


def _round(amount, to=50):
    return (Decimal(amount) / to).quantize(Decimal('1'), rounding=ROUND_HALF_UP) * to


def ride_fare(vehicle_class, distance_m, duration_s, surge=Decimal('1')):
    base, per_km, per_min, minimum = RATES[vehicle_class]
    fare = base + per_km * Decimal(distance_m) / 1000 + per_min * Decimal(duration_s) / 60
    return _round(max(minimum, fare * surge) + BOOKING_FEE)


def chauffeur_fare(hours, rate=Decimal('4500')):
    hours = max(CHAUFFEUR_MIN_HOURS, int(hours))
    billable = hours - 1 if hours >= CHAUFFEUR_DAY_HOURS else hours
    return _round(Decimal(rate) * billable + BOOKING_FEE)


# ---------------------------------------------------------------- drivers

def busy_driver_ids():
    """Drivers on a trip now, or with a booking starting within the hour."""
    from django.db.models import Q
    soon = timezone.now() + timedelta(hours=1)
    return set(Trip.objects.filter(status__in=Trip.ACTIVE, driver__isnull=False)
               .filter(Q(scheduled_for__isnull=True) | Q(scheduled_for__lte=soon)).values_list('driver_id', flat=True))


def available_drivers(lat, lng, vehicle_class=None, chauffeur=False, exclude=()):
    """Online, approved, idle drivers sorted by distance: [(meters, driver)]."""
    qs = DriverProfile.objects.filter(is_online=True, is_active=True, license_verified=True, lat__isnull=False)
    qs = qs.select_related('user').exclude(pk__in=busy_driver_ids() | set(exclude))
    if chauffeur:
        qs = qs.filter(offers_chauffeur=True)
    elif vehicle_class:
        qs = qs.filter(vehicle_class=vehicle_class)
    ranked = sorted(((haversine_m(lat, lng, d.lat, d.lng), d) for d in qs), key=lambda x: x[0])
    return [r for r in ranked if r[0] < 25000]


def pickup_eta_s(meters):
    """Rough time for a nearby driver to reach the rider (town speeds, plus getting going)."""
    return int(meters * 1.35 / 28000 * 3600) + 90


def quote(pickup, dropoff=None, hours=0, when=None):
    """Options for the booking panel. pickup/dropoff are (lat, lng)."""
    surge = surge_for(when)
    options, r = [], None
    if dropoff:
        r = route(pickup[0], pickup[1], dropoff[0], dropoff[1])
        for cls, label, blurb in (('economy', 'Economy', 'Affordable everyday rides'),
                                  ('comfort', 'Comfort', 'Newer cars, top-rated drivers')):
            near = available_drivers(pickup[0], pickup[1], cls)
            options.append({'key': cls, 'kind': 'ride', 'label': label, 'blurb': blurb, 'seats': 4,
                            'fare': ride_fare(cls, r['distance_m'], r['duration_s'], surge),
                            'eta_s': pickup_eta_s(near[0][0]) if near else None, 'drivers': len(near)})
    near = available_drivers(pickup[0], pickup[1], chauffeur=True)
    rate = near[0][1].hourly_rate if near else Decimal('4500')
    hours = max(CHAUFFEUR_MIN_HOURS, int(hours or CHAUFFEUR_MIN_HOURS))
    options.append({'key': 'chauffeur', 'kind': 'chauffeur', 'label': 'Chauffeur', 'blurb': 'A vetted driver drives your car',
                    'hours': hours, 'rate': rate, 'fare': chauffeur_fare(hours, rate),
                    'eta_s': pickup_eta_s(near[0][0]) if near else None, 'drivers': len(near)})
    return {'route': r, 'surge': surge, 'options': options}


# ---------------------------------------------------------------- trip lifecycle

def _notify(user, verb, message, link, subject, cta='View trip'):
    from core.emails import send_branded
    from users.models import Notification
    if not user:
        return
    Notification.objects.create(user=user, verb=verb, message=message, link=link)
    send_branded(user.email, subject, heading=subject, body=message, cta_url=link, cta_label=cta)


@transaction.atomic
def dispatch(trip, exclude=()):
    """Offer the trip to the nearest suitable idle driver. Demo drivers accept automatically."""
    candidates = available_drivers(trip.pickup_lat, trip.pickup_lng, trip.vehicle_class,
                                   chauffeur=trip.kind == 'chauffeur', exclude=exclude)
    if not candidates:
        trip.status, trip.driver = 'no_driver', None
        trip.save(update_fields=['status', 'driver'])
        realtime.trip_changed(trip)
        return None
    meters, driver = candidates[0]
    trip.driver = driver
    trip.simulated = driver.is_simulated
    approach = route(driver.lat, driver.lng, trip.pickup_lat, trip.pickup_lng)
    trip.approach_route, trip.approach_s = approach['coords'], max(120, approach['duration_s'])
    trip.save(update_fields=['driver', 'simulated', 'approach_route', 'approach_s'])
    realtime.trip_changed(trip)
    if not driver.is_simulated:
        _notify(driver.user, 'trip_request', f'New {trip.get_kind_display().lower()} request from {trip.pickup_address}.',
                reverse('driverzone:dashboard'), 'New trip request', 'Open driver app')
    return driver


def accept(trip, when=None):
    trip.status, trip.accepted_at = 'accepted', when or timezone.now()
    trip.save(update_fields=['status', 'accepted_at'])
    realtime.trip_changed(trip)
    d = trip.driver
    if trip.scheduled_for and trip.scheduled_for > timezone.now():
        when = timezone.localtime(trip.scheduled_for).strftime('%a %d %b at %I:%M %p').replace(' 0', ' ')
        _notify(trip.rider, 'trip_accepted', f'{d.name} ({d.vehicle}) is confirmed for {when}. Live tracking starts '
                'when your driver sets off.', trip.get_absolute_url(), 'Your booking is confirmed', 'View booking')
        return
    _notify(trip.rider, 'trip_accepted', f'{d.name} is on the way in a {d.vehicle} ({d.plate_number}).',
            trip.get_absolute_url(), 'Your driver is on the way', 'Track your driver')


def mark_arrived(trip, when=None):
    trip.status, trip.arrived_at = 'arrived', when or timezone.now()
    trip.save(update_fields=['status', 'arrived_at'])
    realtime.trip_changed(trip)


def start(trip, when=None):
    trip.status, trip.started_at = 'in_progress', when or timezone.now()
    trip.save(update_fields=['status', 'started_at'])
    realtime.trip_changed(trip)


def complete(trip, when=None):
    trip.status, trip.completed_at = 'completed', when or timezone.now()
    trip.fare_final = trip.fare_estimate
    trip.save(update_fields=['status', 'completed_at', 'fare_final'])
    realtime.trip_changed(trip)
    if trip.driver:
        DriverProfile.objects.filter(pk=trip.driver_id).update(trips_count=F('trips_count') + 1)
        if trip.dropoff_lat is not None:  # the driver is now where the trip ended
            DriverProfile.objects.filter(pk=trip.driver_id, is_simulated=True).update(lat=trip.dropoff_lat, lng=trip.dropoff_lng)
    _notify(trip.rider, 'trip_completed', f'Thanks for riding with CarHub. Your fare was ₦{trip.fare:,.0f}, '
            f'paid {"to the driver" if trip.payment_method == "cash" else "with the demo payment"}. How was {trip.driver.name if trip.driver else "your driver"}?',
            trip.get_absolute_url(), 'Trip completed: your receipt', 'Rate your trip')


def cancel(trip, by, reason=''):
    fee = CANCEL_FEE_AFTER_ARRIVAL if (by == 'rider' and trip.status == 'arrived') else Decimal('0')
    trip.status, trip.cancelled_at, trip.cancelled_by, trip.cancel_reason = 'cancelled', timezone.now(), by, reason[:200]
    trip.fare_final = fee or None
    trip.save(update_fields=['status', 'cancelled_at', 'cancelled_by', 'cancel_reason', 'fare_final'])
    realtime.trip_changed(trip)
    if by == 'driver':
        _notify(trip.rider, 'trip_cancelled', 'Your driver cancelled. Please book again; you have not been charged.',
                trip.get_absolute_url(), 'Your trip was cancelled')
    elif trip.driver and not trip.driver.is_simulated:
        _notify(trip.driver.user, 'trip_cancelled', f'Trip {trip.number} was cancelled by the rider.',
                reverse('driverzone:dashboard'), 'Trip cancelled', 'Open driver app')
    return fee


MAX_SIM_APPROACH = 60      # demo: the driver reaches you within a minute however far away
MAX_SIM_RIDE = 90          # demo: the trip itself plays out in at most a minute and a half


def _sim_lengths(trip):
    """Real-world seconds compressed onto the demo clock: (approach, ride)."""
    speed = sim_speed()
    ride_total = trip.duration_s if trip.kind == 'ride' else min(trip.hours * 3600, 1800)
    return min(trip.approach_s / speed, MAX_SIM_APPROACH), min(ride_total / speed, MAX_SIM_RIDE), ride_total


def _sim_clock(trip):
    """Simulated seconds elapsed since the request, on the compressed demo clock."""
    return (timezone.now() - trip.created_at).total_seconds()


def advance_simulation(trip):
    """Move a demo trip forward according to the compressed clock. Idempotent; called on every poll."""
    if not trip.simulated or not trip.is_active or trip.scheduled_for:
        return  # scheduled bookings are driven by the real driver's app, not the demo clock
    approach_sim, ride_sim, _ = _sim_lengths(trip)
    t = _sim_clock(trip)
    base = trip.created_at
    accept_at = ACCEPT_AFTER_S
    arrive_at = accept_at + approach_sim
    start_at = arrive_at + ARRIVE_WAIT_S
    finish_at = start_at + ride_sim
    if trip.status == 'requested' and t >= accept_at:
        accept(trip, base + timedelta(seconds=accept_at))
    if trip.status == 'accepted' and t >= arrive_at:
        mark_arrived(trip, base + timedelta(seconds=arrive_at))
    if trip.status == 'arrived' and t >= start_at:
        start(trip, base + timedelta(seconds=start_at))
    if trip.status == 'in_progress' and t >= finish_at:
        complete(trip, base + timedelta(seconds=finish_at))


def live_state(trip):
    """Everything the live map needs, for the rider's and the driver's screens."""
    advance_simulation(trip)
    d = trip.driver
    state = {'status': trip.status, 'label': trip.get_status_display(), 'simulated': trip.simulated, 'eta_s': None, 'progress': 0, 'driver': None,
             'fare': str(trip.fare), 'steps': trip.steps()}
    if not d:
        return state
    pos = None
    now = timezone.now()
    if trip.scheduled_for and trip.scheduled_for > now and trip.status == 'accepted':
        state['scheduled'] = timezone.localtime(trip.scheduled_for).isoformat()
        pos = (d.lat, d.lng, d.heading) if d.lat is not None else None
    elif trip.simulated:
        approach_sim, ride_sim, ride_total = _sim_lengths(trip)
        if trip.status == 'accepted' and trip.accepted_at:
            frac = (now - trip.accepted_at).total_seconds() / max(1, approach_sim)
            pos = point_along(trip.approach_route, frac)
            state['eta_s'] = max(0, int(trip.approach_s * (1 - min(1, frac))))
            state['progress'] = min(1, frac)
        elif trip.status == 'arrived':
            pos = (trip.pickup_lat, trip.pickup_lng, 0)
            state['eta_s'] = 0
        elif trip.status == 'in_progress' and trip.started_at:
            frac = (now - trip.started_at).total_seconds() / max(1, ride_sim)
            pos = point_along(trip.route, frac) if trip.route else (trip.pickup_lat, trip.pickup_lng, 0)
            state['eta_s'] = max(0, int(ride_total * (1 - min(1, frac))))
            state['progress'] = min(1, frac)
        elif trip.status == 'completed' and trip.route:
            last = trip.route[-1]
            pos = (last[0], last[1], 0)
        else:
            pos = (d.lat, d.lng, d.heading)
    else:
        pos = (d.lat, d.lng, d.heading) if d.lat is not None else None
        if pos and trip.status == 'accepted':
            state['eta_s'] = pickup_eta_s(haversine_m(d.lat, d.lng, trip.pickup_lat, trip.pickup_lng)) - 90
        elif pos and trip.status == 'in_progress' and trip.dropoff_lat is not None:
            state['eta_s'] = pickup_eta_s(haversine_m(d.lat, d.lng, trip.dropoff_lat, trip.dropoff_lng)) - 90
    state['driver'] = {
        'name': d.name, 'vehicle': d.vehicle, 'plate': d.plate_number, 'phone': d.user.profile.phone,
        'rating': str(d.rating_avg or ''), 'trips': d.trips_count, 'initials': (d.user.first_name[:1] + d.user.last_name[:1]).upper(),
        'lat': pos[0] if pos else None, 'lng': pos[1] if pos else None, 'heading': round(pos[2]) if pos else 0,
        'live': d.is_live,
    }
    return state


def request_trip(rider, data):
    """Create and dispatch a trip from validated booking data. Route and price are recomputed here."""
    pickup = (data['pickup_lat'], data['pickup_lng'])
    dropoff = (data['dropoff_lat'], data['dropoff_lng']) if data.get('dropoff_lat') is not None else None
    surge = surge_for(data.get('scheduled_for'))
    r = route(*pickup, *dropoff) if dropoff else None
    if data['option'] == 'chauffeur':
        near = available_drivers(*pickup, chauffeur=True)
        rate = near[0][1].hourly_rate if near else Decimal('4500')
        fare = chauffeur_fare(data.get('hours') or CHAUFFEUR_MIN_HOURS, rate)
        kind, cls = 'chauffeur', 'economy'
    else:
        if not r:
            raise ValueError('Choose where you are going.')
        kind, cls = 'ride', data['option']
        fare = ride_fare(cls, r['distance_m'], r['duration_s'], surge)
    trip = Trip.objects.create(
        rider=rider, kind=kind, vehicle_class=cls, pickup_address=data['pickup_address'][:255],
        pickup_lat=pickup[0], pickup_lng=pickup[1], dropoff_address=data.get('dropoff_address', '')[:255],
        dropoff_lat=dropoff[0] if dropoff else None, dropoff_lng=dropoff[1] if dropoff else None,
        route=r['coords'] if r else [], distance_m=r['distance_m'] if r else 0, duration_s=r['duration_s'] if r else 0,
        hours=max(CHAUFFEUR_MIN_HOURS, int(data.get('hours') or 0)) if kind == 'chauffeur' else 0,
        scheduled_for=data.get('scheduled_for'), notes=data.get('notes', '')[:300], surge=surge if kind == 'ride' else 1,
        fare_estimate=fare, payment_method=data.get('payment_method', 'cash'),
    )
    driver = dispatch(trip)
    if driver and trip.scheduled_for:  # scheduled bookings are confirmed with a driver straight away
        accept(trip)
    return trip


# ---------------------------------------------------------------- payloads shared by HTTP and WebSocket

def driver_state(d):
    """What the driver app shows: online flag plus the current offer or active trip."""
    from django.db.models import Q
    d.refresh_from_db()
    soon = timezone.now() + timedelta(minutes=45)
    t = (d.trips.filter(status__in=Trip.ACTIVE).filter(Q(scheduled_for__isnull=True) | Q(scheduled_for__lte=soon))
         .select_related('rider__profile').order_by('created_at').first())
    payload = {'online': d.is_online, 'trip': None}
    if t:
        payload['trip'] = {
            'number': t.number, 'status': t.status, 'kind': t.get_kind_display(), 'fare': f'₦{t.fare_estimate:,.0f}',
            'pickup': {'address': t.pickup_address, 'lat': t.pickup_lat, 'lng': t.pickup_lng},
            'dropoff': {'address': t.dropoff_address, 'lat': t.dropoff_lat, 'lng': t.dropoff_lng} if t.dropoff_lat is not None else None,
            'rider': t.rider.first_name or 'Rider', 'rider_phone': t.rider.profile.phone, 'notes': t.notes,
            'distance_km': t.distance_km, 'duration_min': t.duration_min, 'hours': t.hours,
            'route': t.route, 'action_url': reverse('driverzone:driver_action', args=[t.number]),
            'pickup_m': int(haversine_m(d.lat, d.lng, t.pickup_lat, t.pickup_lng)) if d.lat is not None else None,
        }
    return payload


def ops_snapshot():
    """Every online driver and active trip, for the staff live map."""
    busy = busy_driver_ids()
    drivers = DriverProfile.objects.filter(is_online=True, lat__isnull=False).select_related('user')
    trips = []
    for t in Trip.objects.filter(status__in=Trip.ACTIVE, scheduled_for__isnull=True).select_related('driver__user'):
        advance_simulation(t)
        if t.is_active:
            state = live_state(t) if t.driver else {}
            pos = (state.get('driver') or {})
            trips.append({'number': t.number, 'status': t.status, 'url': t.get_absolute_url(),
                          'pickup': [t.pickup_lat, t.pickup_lng], 'pickup_address': t.pickup_address,
                          'dropoff': [t.dropoff_lat, t.dropoff_lng] if t.dropoff_lat is not None else None,
                          'route': t.route[::3], 'driver': t.driver.name if t.driver else '',
                          'driver_id': t.driver_id, 'car': [pos['lat'], pos['lng'], pos['heading']] if pos.get('lat') else None})
    on_trip = {t['driver_id']: t['car'] for t in trips if t['car']}
    return {
        'drivers': [{'lat': on_trip[d.pk][0] if d.pk in on_trip else d.lat, 'lng': on_trip[d.pk][1] if d.pk in on_trip else d.lng,
                     'heading': on_trip[d.pk][2] if d.pk in on_trip else d.heading, 'cls': d.vehicle_class,
                     'busy': d.pk in busy, 'name': d.name, 'vehicle': d.vehicle} for d in drivers],
        'trips': trips,
    }
