from django.test import TestCase

from .models import Brand


class BrandModelTests(TestCase):
    """The accessories store is not routed yet ("coming soon"); keep its models covered."""

    def test_brand_slug_is_generated_and_unique(self):
        first = Brand.objects.create(name='Michelin')
        second = Brand.objects.create(name='Michelin')
        self.assertEqual(first.slug, 'michelin')
        self.assertEqual(second.slug, 'michelin-1')
