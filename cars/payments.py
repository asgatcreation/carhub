"""Minimal Paystack client: initialise a transaction, verify it, check webhook signatures."""
import hashlib
import hmac
import logging

import requests
from django.conf import settings

logger = logging.getLogger('carhub')
API = 'https://api.paystack.co'


class PaymentError(Exception):
    pass


def is_configured():
    return bool(settings.PAYSTACK_SECRET_KEY)


def _headers():
    return {'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}', 'Content-Type': 'application/json'}


def initialize(order, callback_url):
    """Start a Paystack checkout for the order's deposit; returns the hosted payment URL."""
    payload = {
        'email': order.email,
        'amount': int(order.deposit_total * 100),  # kobo
        'currency': 'NGN',
        'reference': f'{order.number}-{order.pk}',
        'callback_url': callback_url,
        'metadata': {'order_number': order.number},
    }
    try:
        resp = requests.post(f'{API}/transaction/initialize', json=payload, headers=_headers(), timeout=15)
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning('Paystack initialize failed: %s', exc)
        raise PaymentError('Could not reach the payment provider. Please try again.') from exc
    if not data.get('status'):
        raise PaymentError(data.get('message') or 'Payment could not be started.')
    order.payment_reference = payload['reference']
    order.save(update_fields=['payment_reference'])
    return data['data']['authorization_url']


def verify(reference):
    """Return Paystack's transaction data if the payment succeeded, else None."""
    try:
        resp = requests.get(f'{API}/transaction/verify/{reference}', headers=_headers(), timeout=15)
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        logger.warning('Paystack verify failed: %s', exc)
        return None
    tx = data.get('data') or {}
    return tx if data.get('status') and tx.get('status') == 'success' else None


def valid_webhook_signature(body, signature):
    if not (settings.PAYSTACK_SECRET_KEY and signature):
        return False
    expected = hmac.new(settings.PAYSTACK_SECRET_KEY.encode(), body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature)
