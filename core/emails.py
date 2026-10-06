"""Branded transactional email for app events (reservations, inspections, sales)."""
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def send_branded(to, subject, *, heading, body, cta_url='', cta_label='Open CarHub', preheader=''):
    """Send a short notification email in the CarHub template (HTML + plain text)."""
    if not to:
        return
    link = cta_url if cta_url.startswith('http') else f'{settings.SITE_URL}{cta_url}'
    ctx = {
        'heading': heading, 'body': body, 'cta_url': link if cta_url else '', 'cta_label': cta_label,
        'preheader': preheader or body, 'site_url': settings.SITE_URL,
    }
    msg = EmailMultiAlternatives(subject, render_to_string('emails/notification.txt', ctx), None, [to])
    msg.attach_alternative(render_to_string('emails/notification.html', ctx), 'text/html')
    msg.send(fail_silently=True)
