from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class AuthTests(TestCase):
    def test_signup_stores_names_and_signs_in(self):
        resp = self.client.post(reverse('account_signup'), {
            'first_name': 'Tolu', 'last_name': 'Adeyemi', 'email': 'tolu@example.com',
            'password1': 'a-Strong-pass-2026', 'password2': 'a-Strong-pass-2026',
        })
        self.assertEqual(resp.status_code, 302)
        user = User.objects.get(email='tolu@example.com')
        self.assertEqual(user.get_full_name(), 'Tolu Adeyemi')
        self.assertTrue(hasattr(user, 'profile'))

    def test_login_and_logout(self):
        User.objects.create_user(email='a@example.com', password='pass12345!')
        resp = self.client.post(reverse('account_login'), {'login': 'a@example.com', 'password': 'pass12345!'})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.client.get(reverse('users:dashboard')).status_code, 200)
        self.client.post(reverse('account_logout'))
        self.assertEqual(self.client.get(reverse('users:dashboard')).status_code, 302)

    def test_logout_requires_post(self):
        User.objects.create_user(email='b@example.com', password='pass12345!')
        self.client.post(reverse('account_login'), {'login': 'b@example.com', 'password': 'pass12345!'})
        self.client.get(reverse('account_logout'))
        self.assertEqual(self.client.get(reverse('users:dashboard')).status_code, 200)

    def test_account_pages_require_login(self):
        for name in ('users:dashboard', 'users:settings', 'users:inbox', 'cars:orders', 'cars:my_listings'):
            resp = self.client.get(reverse(name))
            self.assertEqual(resp.status_code, 302, name)
