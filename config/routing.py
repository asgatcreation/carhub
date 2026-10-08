from django.urls import re_path

from driverzone.consumers import DriverConsumer, OpsConsumer, TripConsumer
from users.consumers import ChatConsumer, NotificationConsumer

websocket_urlpatterns = [
    re_path(r'ws/chat/(?P<convo_id>\d+)/$', ChatConsumer.as_asgi()),
    re_path(r'ws/notify/$', NotificationConsumer.as_asgi()),
    re_path(r'ws/trips/(?P<number>DZ-[0-9A-F]+)/$', TripConsumer.as_asgi()),
    re_path(r'ws/driver/$', DriverConsumer.as_asgi()),
    re_path(r'ws/ops/$', OpsConsumer.as_asgi()),
]
