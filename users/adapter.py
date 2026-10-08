import logging
import secrets

from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings
from django.contrib import messages

logger = logging.getLogger(__name__)


def _digits(n=6):
    return ''.join(secrets.choice('0123456789') for _ in range(n))


class AccountAdapter(DefaultAccountAdapter):
    """Six-digit numeric one-time codes, branded emails, and friendlier account messages."""

    error_messages = {
        **DefaultAccountAdapter.error_messages,
        'unknown_email': "We couldn't find a CarHub account with that email. Check the spelling, or create an account.",
        'email_taken': 'An account with this email already exists. Sign in, use Continue with Google, '
                       'or reset your password.',
        'incorrect_code': "That code isn't right. Check the latest email from CarHub and try again.",
    }

    def generate_email_verification_code(self):
        return _digits()

    def generate_password_reset_code(self):
        return _digits()

    def send_mail(self, template_prefix, email, context):
        context = {**context, 'site_url': settings.SITE_URL, 'support_email': settings.DEFAULT_FROM_EMAIL}
        if 'user' not in context and isinstance(email, str):
            # Password-reset emails don't carry the user; look them up so the greeting can use their name.
            from allauth.account.models import EmailAddress
            address = EmailAddress.objects.filter(email__iexact=email).select_related('user').first()
            if address:
                context['user'] = address.user
        user = context.get('user')
        context['google_only'] = bool(user and not user.has_usable_password())
        try:
            super().send_mail(template_prefix, email, context)
        except Exception:  # SMTP refused/blocked, API down, timeout...
            # Never turn a mail outage into a 500: log it for the server logs and tell the visitor.
            logger.exception('Could not send %s email to %s', template_prefix, email)
            request = getattr(self, 'request', None)
            if request is not None:
                messages.error(request, "We couldn't send the email just now. Please wait a minute and try "
                                        "again; if it keeps happening, contact us.")
