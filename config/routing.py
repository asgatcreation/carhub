from django.urls import re_path

from users.consumers import ChatConsumer

websocket_urlpatterns = [
    re_path(r'ws/chat/(?P<convo_id>\d+)/$', ChatConsumer.as_asgi()),
]
