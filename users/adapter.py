import secrets

from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings


def _digits(n=6):
    return ''.join(secrets.choice('0123456789') for _ in range(n))


class AccountAdapter(DefaultAccountAdapter):
    """Six-digit numeric one-time codes, and branded emails with absolute links."""

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
        super().send_mail(template_prefix, email, context)
