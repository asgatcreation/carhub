"""Email verification by one-time code became mandatory. Accounts created before that
have no verified EmailAddress row, so mark their current email verified instead of
locking them out on their next sign-in."""
from django.conf import settings
from django.db import migrations


def verify_existing(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split('.'))
    EmailAddress = apps.get_model('account', 'EmailAddress')
    have = set(EmailAddress.objects.values_list('user_id', flat=True))
    EmailAddress.objects.bulk_create([
        EmailAddress(user_id=u.pk, email=u.email, verified=True, primary=True)
        for u in User.objects.exclude(email='').exclude(pk__in=have)
    ], ignore_conflicts=True)
    EmailAddress.objects.filter(verified=False, primary=True).update(verified=True)


class Migration(migrations.Migration):
    dependencies = [
        ('users', '0019_alter_conversation_options_conversation_car_and_more'),
        ('account', '0009_emailaddress_unique_primary_email'),
    ]
    operations = [migrations.RunPython(verify_existing, migrations.RunPython.noop)]
