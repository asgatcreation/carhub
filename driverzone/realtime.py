"""Broadcast trip changes over WebSockets (Django Channels).

Events carry no data: each connected screen recomputes its own view (rider, driver or staff),
so permissions stay in one place. Sends happen after the database commit so listeners never
read stale rows. Without a channel layer (or outside an ASGI server) this quietly does nothing
and the pages fall back to polling.
"""
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

logger = logging.getLogger(__name__)


def _send(group, event_type):
    layer = get_channel_layer()
    if layer is None:
        return

    def send():
        try:
            async_to_sync(layer.group_send)(group, {'type': event_type})
        except Exception:  # never let a broadcast break a request
            logger.exception('WebSocket broadcast to %s failed', group)

    transaction.on_commit(send)


def trip_changed(trip):
    """A trip's status, driver or the driver's position changed."""
    _send(f'trip_{trip.number}', 'trip.update')
    if trip.driver_id:
        _send(f'driver_{trip.driver_id}', 'driver.update')
    _send('ops', 'ops.update')


def driver_changed(driver_id):
    _send(f'driver_{driver_id}', 'driver.update')
    _send('ops', 'ops.update')
