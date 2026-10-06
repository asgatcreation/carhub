import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.utils import timezone

from .models import Conversation, Message


class ChatConsumer(AsyncWebsocketConsumer):
    """Real-time chat for one conversation: ws/chat/<convo_id>/ (participants only)."""

    async def connect(self):
        self.convo_id = int(self.scope['url_route']['kwargs']['convo_id'])
        self.group_name = f'conversation_{self.convo_id}'
        user = self.scope.get('user')
        if not (user and user.is_authenticated and await self._is_participant(user)):
            await self.close()
            return
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data or '{}')
        except ValueError:
            return
        user = self.scope['user']
        if data.get('type') == 'typing':
            await self.channel_layer.group_send(self.group_name, {
                'type': 'chat.typing', 'sender_id': user.pk, 'typing': bool(data.get('typing')),
            })
            return
        content = (data.get('message') or '').strip()[:2000]
        if not content:
            return
        payload = await self._store(user, content)
        await self.channel_layer.group_send(self.group_name, {'type': 'chat.message', 'payload': payload})

    async def chat_message(self, event):
        payload = dict(event['payload'])
        payload['mine'] = payload.pop('sender_id') == self.scope['user'].pk
        await self.send(text_data=json.dumps({'kind': 'message', 'message': payload}))

    async def chat_typing(self, event):
        if event['sender_id'] != self.scope['user'].pk:
            await self.send(text_data=json.dumps({'kind': 'typing', 'typing': event['typing']}))

    @database_sync_to_async
    def _is_participant(self, user):
        return Conversation.objects.filter(pk=self.convo_id, participants=user).exists()

    @database_sync_to_async
    def _store(self, user, content):
        msg = Message.objects.create(conversation_id=self.convo_id, sender=user, content=content)
        return {
            'id': msg.pk,
            'content': msg.content,
            'sender_id': user.pk,
            'sender': user.get_full_name() or user.email,
            'time': timezone.localtime(msg.created_at).strftime('%H:%M'),
        }
