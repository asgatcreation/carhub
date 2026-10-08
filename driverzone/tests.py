from datetime import timedelta
from decimal import Decimal
from unittest import mock

import requests
from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from cars.tests import BaseTestCase, make_user
from users.models import Application

from . import services
from .models import DriverProfile, Trip, TripRating

LEKKI = (6.4478, 3.4723)
VI = (6.4253, 3.4216)
AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}


def make_driver(email, lat=6.45, lng=3.47, cls='economy', simulated=True, online=True, **kw):
    user = make_user(email)
    return DriverProfile.objects.create(user=user, license_number='LAG1', license_verified=True, is_online=online,
                                        lat=lat, lng=lng, vehicle_class=cls, vehicle_make='Toyota', vehicle_model='Corolla',
                                        vehicle_color='Silver', plate_number='LND-1-AA', is_simulated=simulated, **kw)


def book_data(**kw):
    data = {'option': 'economy', 'pickup_address': 'Lekki Phase 1', 'pickup_lat': LEKKI[0], 'pickup_lng': LEKKI[1],
            'dropoff_address': 'Eko Hotel', 'dropoff_lat': VI[0], 'dropoff_lng': VI[1], 'payment_method': 'cash', 'hours': ''}
    data.update(kw)
    return data


class DriverZoneTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        # Never call the real OSRM server from tests: routing falls back to a straight-line estimate.
        patcher = mock.patch('driverzone.services.requests.get', side_effect=requests.ConnectionError)
        patcher.start()
        self.addCleanup(patcher.stop)


class PricingTests(DriverZoneTestCase):
    def test_ride_fare_has_minimum_and_surge(self):
        self.assertEqual(services.ride_fare('economy', 500, 120), Decimal('2000'))  # minimum 1800 + 200 booking fee
        normal = services.ride_fare('economy', 10000, 1800)
        busy = services.ride_fare('economy', 10000, 1800, Decimal('1.3'))
        self.assertGreater(busy, normal)
        self.assertGreater(services.ride_fare('comfort', 10000, 1800), normal)

    def test_chauffeur_minimum_and_full_day(self):
        self.assertEqual(services.chauffeur_fare(1, Decimal('4000')), services.chauffeur_fare(3, Decimal('4000')))
        self.assertEqual(services.chauffeur_fare(10, Decimal('4000')), Decimal('36200'))  # 9 billable hours + fee

    def test_route_falls_back_offline(self):
        r = services.route(*LEKKI, *VI)
        self.assertEqual(r['source'], 'estimate')
        self.assertGreater(r['distance_m'], 5000)


class BookingTests(DriverZoneTestCase):
    def setUp(self):
        super().setUp()
        self.near = make_driver('near@example.com', lat=6.448, lng=3.47)
        self.far = make_driver('far@example.com', lat=6.6, lng=3.35)
        self.comfort = make_driver('comfort@example.com', lat=6.447, lng=3.471, cls='comfort')

    def test_quote_lists_options_with_pickup_eta(self):
        resp = self.client.get(reverse('driverzone:api_quote'), {'plat': LEKKI[0], 'plng': LEKKI[1], 'dlat': VI[0], 'dlng': VI[1]})
        options = {o['key']: o for o in resp.json()['options']}
        self.assertEqual(set(options), {'economy', 'comfort', 'chauffeur'})
        self.assertEqual(options['economy']['drivers'], 2)
        self.assertLessEqual(options['economy']['eta_min'], 3)

    def test_booking_requires_login(self):
        resp = self.client.post(reverse('driverzone:book'), book_data())
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/accounts/login/', resp['Location'])

    def test_nearest_matching_driver_is_dispatched(self):
        self.client.force_login(self.buyer)
        resp = self.client.post(reverse('driverzone:book'), book_data(), **AJAX)
        trip = Trip.objects.get()
        self.assertEqual(resp.json()['url'], trip.get_absolute_url())
        self.assertEqual((trip.driver, trip.status, trip.simulated), (self.near, 'requested', True))
        self.assertGreater(trip.fare_estimate, 0)
        self.assertGreaterEqual(len(trip.route), 2)

    def test_busy_driver_is_skipped(self):
        self.client.force_login(self.buyer)
        other = make_user('other-rider@example.com')
        Trip.objects.create(rider=other, driver=self.near, pickup_address='x', pickup_lat=1, pickup_lng=1,
                            fare_estimate=1, status='in_progress')
        self.client.post(reverse('driverzone:book'), book_data(), **AJAX)
        self.assertEqual(Trip.objects.get(rider=self.buyer).driver, self.far)

    def test_validation(self):
        self.client.force_login(self.buyer)
        resp = self.client.post(reverse('driverzone:book'), book_data(dropoff_lat='', dropoff_lng=''), **AJAX)
        self.assertIn('Where are you going', resp.json()['error'])
        resp = self.client.post(reverse('driverzone:book'), book_data(pickup_lat=51.5, pickup_lng=-0.12), **AJAX)
        self.assertIn('Nigeria', resp.json()['error'])
        self.assertFalse(Trip.objects.exists())

    def test_no_driver_available(self):
        DriverProfile.objects.update(is_online=False)
        self.client.force_login(self.buyer)
        self.client.post(reverse('driverzone:book'), book_data(), **AJAX)
        self.assertEqual(Trip.objects.get().status, 'no_driver')

    def test_chauffeur_booking_without_destination(self):
        self.client.force_login(self.buyer)
        self.client.post(reverse('driverzone:book'), book_data(option='chauffeur', dropoff_lat='', dropoff_lng='', hours=5), **AJAX)
        trip = Trip.objects.get()
        self.assertEqual((trip.kind, trip.hours), ('chauffeur', 5))
        self.assertEqual(trip.fare_estimate, services.chauffeur_fare(5, trip.driver.hourly_rate))


class LiveTrackingTests(DriverZoneTestCase):
    def setUp(self):
        super().setUp()
        self.driver = make_driver('sim@example.com', lat=6.46, lng=3.48)
        self.client.force_login(self.buyer)
        self.client.post(reverse('driverzone:book'), book_data(), **AJAX)
        self.trip = Trip.objects.get()
        self.live = reverse('driverzone:api_live', args=[self.trip.number])

    def _at(self, seconds):
        return mock.patch('django.utils.timezone.now', return_value=self.trip.created_at + timedelta(seconds=seconds))

    def test_simulated_trip_runs_to_completion(self):
        self.assertEqual(self.client.get(self.live).json()['status'], 'requested')
        with self._at(10):
            state = self.client.get(self.live).json()
        self.assertEqual(state['status'], 'accepted')
        self.assertIsNotNone(state['driver']['lat'])
        self.assertGreater(state['eta_s'], 0)
        with self._at(1000):
            self.assertEqual(self.client.get(self.live).json()['status'], 'completed')
        self.trip.refresh_from_db()
        self.driver.refresh_from_db()
        self.assertEqual(self.trip.fare_final, self.trip.fare_estimate)
        self.assertEqual(self.driver.trips_count, 1)
        self.assertTrue(any('receipt' in m.subject for m in mail.outbox))

    def test_only_participants_can_watch(self):
        stranger = make_user('stranger@example.com')
        self.client.force_login(stranger)
        self.assertEqual(self.client.get(self.live).status_code, 404)

    def test_cancel_is_free_before_arrival_and_charged_after(self):
        self.client.post(reverse('driverzone:trip_cancel', args=[self.trip.number]))
        self.trip.refresh_from_db()
        self.assertEqual((self.trip.status, self.trip.fare_final), ('cancelled', None))
        self.client.post(reverse('driverzone:book'), book_data(), **AJAX)
        second = Trip.objects.exclude(pk=self.trip.pk).get()
        services.accept(second)
        services.mark_arrived(second)
        self.client.post(reverse('driverzone:trip_cancel', args=[second.number]))
        second.refresh_from_db()
        self.assertEqual(second.fare_final, services.CANCEL_FEE_AFTER_ARRIVAL)

    def test_rating_updates_driver(self):
        services.complete(self.trip)
        self.client.post(reverse('driverzone:trip_rate', args=[self.trip.number]), {'stars': 4, 'compliments': ['Clean car'], 'tip': 500})
        self.client.post(reverse('driverzone:trip_rate', args=[self.trip.number]), {'stars': 1})  # only once
        self.driver.refresh_from_db()
        self.assertEqual((self.driver.rating_count, float(self.driver.rating_avg)), (1, 4.0))
        self.assertEqual(TripRating.objects.get().tip, Decimal('500'))


class DriverAppTests(DriverZoneTestCase):
    def setUp(self):
        super().setUp()
        self.real = make_driver('real@example.com', lat=6.448, lng=3.471, simulated=False)
        self.backup = make_driver('backup@example.com', lat=6.5, lng=3.4, simulated=False)
        self.client.force_login(self.buyer)
        self.client.post(reverse('driverzone:book'), book_data(), **AJAX)
        self.trip = Trip.objects.get()

    def _act(self, driver, action):
        self.client.force_login(driver.user)
        return self.client.post(reverse('driverzone:driver_action', args=[self.trip.number]), {'action': action})

    def test_real_driver_runs_the_trip(self):
        self.client.force_login(self.real.user)
        state = self.client.get(reverse('driverzone:api_driver_state')).json()
        self.assertEqual(state['trip']['number'], self.trip.number)
        for action, status in [('accept', 'accepted'), ('arrived', 'arrived'), ('start', 'in_progress'), ('complete', 'completed')]:
            self.assertEqual(self._act(self.real, action).json()['status'], status)
        self.assertEqual(self._act(self.real, 'start').status_code, 409)

    def test_decline_passes_to_next_driver(self):
        self._act(self.real, 'decline')
        self.trip.refresh_from_db()
        self.assertEqual(self.trip.driver, self.backup)

    def test_location_updates_are_used_live(self):
        self.client.force_login(self.real.user)
        self.client.post(reverse('driverzone:api_driver_location'), {'lat': 6.4501, 'lng': 3.4702, 'heading': 90})
        self._act(self.real, 'accept')
        self.client.force_login(self.buyer)
        state = self.client.get(reverse('driverzone:api_live', args=[self.trip.number])).json()
        self.assertEqual((state['driver']['lat'], state['driver']['live']), (6.4501, True))

    def test_non_drivers_are_sent_to_apply(self):
        self.client.force_login(self.buyer)
        self.assertRedirects(self.client.get(reverse('driverzone:dashboard')), reverse('driverzone:drive'))


class OnboardingTests(DriverZoneTestCase):
    def test_application_approval_creates_driver_profile(self):
        self.client.force_login(self.buyer)
        self.client.post(reverse('driverzone:drive'), {'full_name': 'Ade Driver', 'phone': '0803', 'address': 'Lagos',
                                                       'id_number': 'LAG123', 'experience_years': 6,
                                                       'vehicle_details': '2019 Toyota Corolla, grey, lnd-482-kj'})
        app = Application.objects.get(user=self.buyer, role='pilot')
        staff = make_user('mod@example.com')
        staff.is_staff = True
        staff.save()
        self.client.force_login(staff)
        self.client.post(reverse('staff:verification_decide', args=[app.pk]), {'decision': 'approve'})
        d = DriverProfile.objects.get(user=self.buyer)
        self.assertEqual((d.license_number, d.vehicle_year, d.vehicle_make, d.vehicle_model, d.vehicle_color, d.plate_number),
                         ('LAG123', 2019, 'Toyota', 'Corolla', 'Grey', 'LND-482-KJ'))
        self.assertTrue(d.license_verified)
        self.assertEqual(self.client.get(reverse('staff:live_data')).status_code, 200)
