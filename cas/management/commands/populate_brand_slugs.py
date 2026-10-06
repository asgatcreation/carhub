from django.core.management.base import BaseCommand
from django.utils.text import slugify

from cas.models import Brand


class Command(BaseCommand):
    help = 'Populate missing Brand.slug values using slugified name'

    def handle(self, *args, **options):
        count = 0
        for b in Brand.objects.all():
            if not b.slug:
                base = slugify(b.name)[:110]
                slug = base
                # Ensure uniqueness by appending a counter if needed
                ix = 1
                while Brand.objects.filter(slug=slug).exists():
                    slug = f"{base}-{ix}"
                    ix += 1
                b.slug = slug[:120]
                b.save()
                count += 1
        self.stdout.write(self.style.SUCCESS(f'Populated slugs for {count} brands'))
