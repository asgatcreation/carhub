from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from cars.models import Car
from cas.models import Category, Product
from driverzone.models import DriverProfile


class StaticSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        return ['home', 'cars:browse', 'cars:sell', 'cas:home', 'cas:shop', 'cas:sell', 'driverzone:home',
                'driverzone:drivers', 'driverzone:drive', 'about', 'contact', 'terms', 'privacy']

    def location(self, item):
        return reverse(item)


class CarSitemap(Sitemap):
    changefreq = 'daily'
    priority = 0.9

    def items(self):
        return Car.objects.public().order_by('-updated_at')

    def lastmod(self, obj):
        return obj.updated_at


class ProductSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.7

    def items(self):
        return Product.objects.public().order_by('-updated_at')

    def lastmod(self, obj):
        return obj.updated_at


class CategorySitemap(Sitemap):
    priority = 0.6

    def items(self):
        return Category.objects.all()


class SellerSitemap(Sitemap):
    priority = 0.5

    def items(self):
        from django.contrib.auth import get_user_model
        return get_user_model().objects.filter(cars_uploaded__in=Car.objects.public()).distinct().order_by('pk')

    def location(self, obj):
        return reverse('cars:seller_profile', args=[obj.pk])


class ChauffeurSitemap(Sitemap):
    priority = 0.4

    def items(self):
        return DriverProfile.objects.filter(is_active=True, license_verified=True, offers_chauffeur=True).order_by('pk')


SITEMAPS = {'pages': StaticSitemap, 'cars': CarSitemap, 'parts': ProductSitemap, 'categories': CategorySitemap,
            'sellers': SellerSitemap, 'chauffeurs': ChauffeurSitemap}
