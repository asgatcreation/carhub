from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission


class Command(BaseCommand):
    help = 'Create default role groups for the application (car_seller, cas_seller, pilot, buyer)'

    def handle(self, *args, **options):
        roles = [
            ('buyer', 'Buyer'),
            ('car_seller', 'Car Seller'),
            ('cas_seller', 'CAS Seller'),
            ('pilot', 'Pilot'),
        ]
        created = []
        for codename, name in roles:
            grp, ok = Group.objects.get_or_create(name=codename)
            if ok:
                created.append(codename)
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created groups: {", ".join(created)}'))
        else:
            self.stdout.write('No new groups were created. All groups already exist.')
