from django.core.management.base import BaseCommand
from cars.models import Car
from django.utils.text import slugify

class Command(BaseCommand):
    help = 'Update slugs for existing Car objects'

    def handle(self, *args, **options):
        cars = Car.objects.all()
        updated = 0
        for car in cars:
            if not car.slug or car.slug != slugify(f"{car.name}-{car.model}-{car.year}-{car.vin or ''}"):
                car.slug = slugify(f"{car.name}-{car.model}-{car.year}-{car.vin or ''}")
                car.save()
                updated += 1
        self.stdout.write(self.style.SUCCESS(f'Updated slugs for {updated} cars.'))