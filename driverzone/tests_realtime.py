"""WebSocket consumers: access rules, initial state, and instant pushes on events."""
from unittest import mock

import requests
from asgiref.sync import async_to_sync, sync_to_async
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TransactionTestCase, override_settings

from config.routing import websocket_urlpatterns
from users.models import Notification

from . import services
from .models import DriverProfile, Trip

User = get_user_model()
LAYERS = {'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}}


def _user(email, staff=False):
    return User.objects.create_user(email=email, password='pass12345!', first_name=email.split('@')[0].title(), is_staff=staff)


async def _connect(path, user):
    comm = WebsocketCommunicator(URLRouter(websocket_urlpatterns), path)
    comm.scope['user'] = user
    connected, _ = await comm.connect()
    return comm, connected


@override_settings(CHANNEL_LAYERS=LAYERS)
class RealtimeTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        patcher = mock.patch('driverzone.services.requests.get', side_effect=requests.ConnectionError)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.rider = _user('rider@example.com')
        self.driver_user = _user('driver@example.com')
        self.driver = DriverProfile.objects.create(user=self.driver_user, license_number='L1', license_verified=True,
                                                   is_online=True, lat=6.45, lng=3.47, is_simulated=False,
                                                   vehicle_make='Toyota', vehicle_model='Corolla')
        self.trip = services.request_trip(self.rider, {
            'option': 'economy', 'pickup_address': 'Lekki', 'pickup_lat': 6.4478, 'pickup_lng': 3.4723,
            'dropoff_address': 'VI', 'dropoff_lat': 6.4253, 'dropoff_lng': 3.4216, 'payment_method': 'cash'})

    def test_rider_gets_state_then_instant_status_push(self):
        async def run():
            comm, ok = await _connect(f'/ws/trips/{self.trip.number}/', self.rider)
            self.assertTrue(ok)
            first = await comm.receive_json_from(timeout=3)
            self.assertEqual(first['status'], 'requested')
            await sync_to_async(services.accept)(await sync_to_async(Trip.objects.get)(pk=self.trip.pk))
            pushed = await comm.receive_json_from(timeout=3)
            self.assertEqual(pushed['status'], 'accepted')
            self.assertEqual(pushed['driver']['name'], 'Driver')
            await comm.disconnect()
        async_to_sync(run)()

    def test_strangers_and_guests_are_refused(self):
        from django.contrib.auth.models import AnonymousUser
        stranger = _user('stranger@example.com')

        async def run():
            for user in (stranger, AnonymousUser()):
                comm, ok = await _connect(f'/ws/trips/{self.trip.number}/', user)
                self.assertFalse(ok)
            comm, ok = await _connect('/ws/ops/', stranger)
            self.assertFalse(ok)
        async_to_sync(run)()

    def test_driver_streams_gps_and_rider_sees_it(self):
        services.accept(self.trip)

        async def run():
            rider, _ = await _connect(f'/ws/trips/{self.trip.number}/', self.rider)
            await rider.receive_json_from(timeout=3)
            drv, ok = await _connect('/ws/driver/', self.driver_user)
            self.assertTrue(ok)
            offer = await drv.receive_json_from(timeout=3)
            self.assertEqual(offer['trip']['number'], self.trip.number)
            await drv.send_json_to({'type': 'location', 'lat': 6.4462, 'lng': 3.4655, 'heading': 270})
            pushed = await rider.receive_json_from(timeout=3)
            self.assertEqual((pushed['driver']['lat'], pushed['driver']['live']), (6.4462, True))
            await rider.disconnect()
            await drv.disconnect()
        async_to_sync(run)()

    def test_staff_ops_snapshot(self):
        staff = _user('staff@example.com', staff=True)

        async def run():
            comm, ok = await _connect('/ws/ops/', staff)
            self.assertTrue(ok)
            snap = await comm.receive_json_from(timeout=3)
            self.assertEqual(len(snap['drivers']), 1)
            self.assertEqual(snap['trips'][0]['number'], self.trip.number)
            await comm.disconnect()
        async_to_sync(run)()

    def test_notifications_are_pushed_instantly(self):
        async def run():
            comm, ok = await _connect('/ws/notify/', self.rider)
            self.assertTrue(ok)
            await sync_to_async(Notification.objects.create)(user=self.rider, verb='test', message='Hello!', link='/x/')
            msg = await comm.receive_json_from(timeout=3)
            self.assertEqual((msg['message'], msg['link']), ('Hello!', '/x/'))
            self.assertGreaterEqual(msg['unread'], 1)
            await comm.disconnect()
        async_to_sync(run)()
