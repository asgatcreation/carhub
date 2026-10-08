from django.core.cache import cache
from django.test import TestCase

from cars.tests import make_car, make_user


class SiteHardeningTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_health_check(self):
        r = self.client.get('/healthz/')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, b'ok')

    def test_robots_points_to_sitemap_and_hides_private_areas(self):
        body = self.client.get('/robots.txt').content.decode()
        self.assertIn('Sitemap: http://testserver/sitemap.xml', body)
        for path in ('/account/', '/staff/', '/admin/'):
            self.assertIn(f'Disallow: {path}', body)

    def test_sitemap_lists_approved_cars_only(self):
        live = make_car(approval_status='approved')
        hidden = make_car(model='Corolla', approval_status='pending')
        body = self.client.get('/sitemap.xml').content.decode()
        self.assertIn(live.get_absolute_url(), body)
        self.assertNotIn(hidden.get_absolute_url(), body)
        self.assertIn('/privacy/', body)

    def test_legal_and_offline_pages(self):
        for url in ('/terms/', '/privacy/', '/offline/'):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_security_headers(self):
        r = self.client.get('/')
        self.assertIn('geolocation=(self)', r['Permissions-Policy'])
        self.assertIn('camera=()', r['Permissions-Policy'])

    def test_service_worker_served_from_root(self):
        r = self.client.get('/sw.js')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Service-Worker-Allowed'], '/')
        self.assertIn('application/javascript', r['Content-Type'])

    def test_pages_carry_link_preview_meta(self):
        car = make_car(approval_status='approved')
        html = self.client.get(car.get_absolute_url()).content.decode()
        self.assertIn('property="og:title"', html)
        self.assertIn('rel="manifest"', html)
        self.assertIn('property="og:image" content="http', html)

    def test_rate_limit_returns_429(self):
        url = '/drivers/api/quote/?plat=6.45&plng=3.39'
        statuses = [self.client.get(url, HTTP_ACCEPT='application/json').status_code for _ in range(42)]
        self.assertNotIn(429, statuses[:40])
        self.assertEqual(statuses[-1], 429)

    def test_dashboard_shows_all_sections(self):
        user = make_user('dash@example.com')
        self.client.force_login(user)
        html = self.client.get('/account/').content.decode()
        for text in ('Parts orders', 'Trips taken', 'Car reservations', 'Book a ride'):
            self.assertIn(text, html)
