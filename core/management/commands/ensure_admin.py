"""Create (or update) the site administrator from environment variables.

    ADMIN_EMAIL=you@example.com ADMIN_PASSWORD=... python manage.py ensure_admin

Runs on every Render start, because the demo database is rebuilt on each deploy. Does nothing
when the variables are unset. The password is re-applied each time, so changing ADMIN_PASSWORD
in the dashboard and redeploying rotates it.
"""
import os

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Create or update the superuser from ADMIN_EMAIL / ADMIN_PASSWORD.'

    def handle(self, *args, **options):
        email = os.environ.get('ADMIN_EMAIL', '').strip().lower()
        password = os.environ.get('ADMIN_PASSWORD', '')
        if not email or not password:
            self.stdout.write('ADMIN_EMAIL / ADMIN_PASSWORD not set; skipping admin account.')
            return
        User = get_user_model()
        user = User.objects.filter(email__iexact=email).first()
        created = user is None
        if created:
            user = User.objects.create_user(email=email, password=password, username=email.split('@')[0][:30],
                                            first_name=os.environ.get('ADMIN_FIRST_NAME', 'Admin'))
        else:
            user.set_password(password)
        user.is_staff = user.is_superuser = user.is_active = True
        user.save()
        EmailAddress.objects.update_or_create(user=user, email=user.email, defaults={'verified': True, 'primary': True})
        self.stdout.write(self.style.SUCCESS(f'Admin account {"created" if created else "updated"}: {email}'))
