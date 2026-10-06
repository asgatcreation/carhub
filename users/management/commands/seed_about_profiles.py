from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from users.models import Profile

User = get_user_model()

class Command(BaseCommand):
    help = 'Seed sample About fields for the first few profiles (safe to run multiple times).'

    def handle(self, *args, **options):
        qs = Profile.objects.all()[:5]
        for i, p in enumerate(qs, start=1):
            if not p.business_description:
                p.business_description = f"Sample business description for {p.user.username or p.user.email}."
            if not p.years_in_business:
                p.years_in_business = 3 + i
            if not p.specialization:
                p.specialization = 'General vehicle sales'
            if not p.certifications:
                p.certifications = 'Basic Dealer Registration'
            if not p.why_choose:
                p.why_choose = 'Friendly service, transparent pricing.'
            p.save()
            self.stdout.write(self.style.SUCCESS(f"Seeded About for {p.user.username or p.user.email}"))

        if not qs:
            self.stdout.write('No profiles found to seed.')
