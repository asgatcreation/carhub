from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse


class PageTests(TestCase):
    def test_public_pages_render(self):
        for name in ('home', 'about', 'contact', 'cas:home', 'drivers', 'cars:browse', 'cars:sell', 'cars:cart', 'cars:saved'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_404_page(self):
        resp = self.client.get('/no-such-page/')
        self.assertEqual(resp.status_code, 404)

    def test_old_urls_redirect(self):
        self.assertRedirects(self.client.get('/cas/'), reverse('cas:home'))
        self.assertRedirects(self.client.get('/cars/listings/?body=suv'), reverse('cars:browse') + '?body=suv')

    @override_settings(ADMINS=[('Ops', 'ops@example.com')])
    def test_contact_form_emails_the_team(self):
        resp = self.client.post(reverse('contact'), {
            'name': 'Ada', 'email': 'ada@example.com', 'topic': 'buying', 'message': 'Do you deliver to Abuja?',
        })
        self.assertRedirects(resp, reverse('contact'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Do you deliver to Abuja?', mail.outbox[0].body)
