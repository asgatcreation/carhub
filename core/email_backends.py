"""Email backend for Brevo's transactional HTTP API.

Some hosts (including free web services on Render) block outbound SMTP ports, so
mail is sent over HTTPS instead. Set BREVO_API_KEY and verify the sender address
(DEFAULT_FROM_EMAIL) in Brevo; nothing else changes for the rest of the app.
"""
import logging
from email.utils import parseaddr

import requests
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)
API_URL = 'https://api.brevo.com/v3/smtp/email'


def _contact(address):
    name, email = parseaddr(address)
    return {'email': email, **({'name': name} if name else {})}


class BrevoEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages:
            payload = {
                'sender': _contact(message.from_email or settings.DEFAULT_FROM_EMAIL),
                'to': [_contact(a) for a in message.to],
                'subject': message.subject,
                'textContent': message.body,
            }
            if message.cc:
                payload['cc'] = [_contact(a) for a in message.cc]
            if message.bcc:
                payload['bcc'] = [_contact(a) for a in message.bcc]
            if message.reply_to:
                payload['replyTo'] = _contact(message.reply_to[0])
            for content, mimetype in getattr(message, 'alternatives', []):
                if mimetype == 'text/html':
                    payload['htmlContent'] = content
            try:
                resp = requests.post(API_URL, json=payload, timeout=15, headers={
                    'api-key': settings.BREVO_API_KEY, 'accept': 'application/json',
                })
                resp.raise_for_status()
                sent += 1
            except requests.RequestException:
                logger.exception('Brevo send failed for %s', message.to)
                if not self.fail_silently:
                    raise
        return sent
