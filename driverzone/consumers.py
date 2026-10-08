"""WebSocket endpoints for instant live tracking.

ws/trips/<number>/   rider, driver or staff watching one trip
ws/driver/           the driver app: offers, trip updates, and GPS sent up from the phone
ws/ops/              staff live map

Real events (status changes, a driver's GPS fix) are pushed the moment they happen via channel-layer
groups (see realtime.py). Simulated demo trips have no real events between statuses, so their sockets
also tick once a second while the car is moving.
"""
import asyncio
import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone

from . import realtime, services
from .models import DriverProfile, Trip

TICK_S = 1.0
OPS_TICK_S = 3.0


class TickingConsumer(AsyncWebsocketConsumer):
    """Base: send a fresh payload on group events, and on a timer while `should_tick()` is true."""
    tick_seconds = TICK_S
    group = None

    async def start_ticking(self):
        self._ticker = asyncio.create_task(self._tick())

    async def _tick(self):
        try:
            while True:
                await asyncio.sleep(self.tick_seconds)
                if await self.should_tick():
                    await self.push()
        except asyncio.CancelledError:
            pass

    async def disconnect(self, code):
        if getattr(self, '_ticker', None):
            self._ticker.cancel()
        if self.group:
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def should_tick(self):
        return False

    async def push(self):
        raise NotImplementedError


class TripConsumer(TickingConsumer):
    async def connect(self):
        self.number = self.scope['url_route']['kwargs']['number']
        user = self.scope.get('user')
        if not (user and user.is_authenticated and await self._allowed(user)):
            await self.close()
            return
        self.group = f'trip_{self.number}'
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
        await self.push()
        await self.start_ticking()

    @database_sync_to_async
    def _allowed(self, user):
        t = Trip.objects.filter(number=self.number).select_related('driver').first()
        return bool(t and (t.rider_id == user.id or (t.driver and t.driver.user_id == user.id) or user.is_staff))

    @database_sync_to_async
    def _state(self):
        t = Trip.objects.select_related('driver__user__profile').get(number=self.number)
        self._moving = t.simulated and t.is_active and not t.scheduled_for
        return services.live_state(t)

    async def should_tick(self):
        return getattr(self, '_moving', False)

    async def push(self):
        await self.send(text_data=json.dumps(await self._state()))

    async def trip_update(self, event):
        await self.push()


class DriverConsumer(TickingConsumer):
    tick_seconds = 5.0

    async def connect(self):
        user = self.scope.get('user')
        self.driver_id = await self._driver_id(user) if user and user.is_authenticated else None
        if not self.driver_id:
            await self.close()
            return
        self.group = f'driver_{self.driver_id}'
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
        await self.push()
        await self.start_ticking()

    @database_sync_to_async
    def _driver_id(self, user):
        d = DriverProfile.objects.filter(user=user, license_verified=True, is_active=True).first()
        return d.pk if d else None

    @database_sync_to_async
    def _state(self):
        return services.driver_state(DriverProfile.objects.get(pk=self.driver_id))

    async def should_tick(self):
        return True  # simulated trips advance on their own; a slow heartbeat keeps the app in step

    async def push(self):
        await self.send(text_data=json.dumps(await self._state()))

    async def driver_update(self, event):
        await self.push()

    async def receive(self, text_data=None, bytes_data=None):
        """The phone streams its GPS position up the same socket."""
        try:
            data = json.loads(text_data or '{}')
            if data.get('type') == 'location':
                await self._save_location(float(data['lat']), float(data['lng']), float(data.get('heading') or 0))
        except (ValueError, KeyError, TypeError):
            return

    @database_sync_to_async
    def _save_location(self, lat, lng, heading):
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            return
        d = DriverProfile.objects.get(pk=self.driver_id)
        d.lat, d.lng, d.heading, d.location_updated_at, d.is_simulated = lat, lng, heading, timezone.now(), False
        d.save(update_fields=['lat', 'lng', 'heading', 'location_updated_at', 'is_simulated'])
        trip = d.trips.filter(status__in=('accepted', 'arrived', 'in_progress')).first()
        if trip:
            realtime.trip_changed(trip)
        else:
            realtime.driver_changed(d.pk)


class OpsConsumer(TickingConsumer):
    tick_seconds = OPS_TICK_S
    group = 'ops'

    async def connect(self):
        user = self.scope.get('user')
        if not (user and user.is_authenticated and user.is_staff):
            await self.close()
            return
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
        await self.push()
        await self.start_ticking()

    @database_sync_to_async
    def _snapshot(self):
        return services.ops_snapshot()

    async def should_tick(self):
        return True

    async def push(self):
        await self.send(text_data=json.dumps(await self._snapshot()))

    async def ops_update(self, event):
        await self.push()
