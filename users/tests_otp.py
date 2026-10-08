import re

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

User = get_user_model()
SIGNUP = {'first_name': 'Ada', 'last_name': 'Okafor', 'email': 'ada@example.com',
          'password1': 'a-Strong-pass-2026', 'password2': 'a-Strong-pass-2026'}


def code_from(message):
    return re.search(r'\b(\d{6})\b', message.body).group(1)


def html_text(message):
    """The HTML part with tags and whitespace removed (the code is drawn one digit per box)."""
    return re.sub(r'\s+', '', re.sub(r'<[^>]+>', '', message.alternatives[0][0]))


def preheader(message):
    html = message.alternatives[0][0]
    return re.search(r'<div style="display:none[^>]*>(.*?)</div>', html, re.S).group(1)


@override_settings(ACCOUNT_EMAIL_VERIFICATION='mandatory', ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED=True)
class SignupVerificationTests(TestCase):
    def setUp(self):
        cache.clear()  # allauth rate limits live in the cache

    def test_signup_sends_code_and_code_activates_account(self):
        resp = self.client.post(reverse('account_signup'), SIGNUP)
        self.assertRedirects(resp, reverse('account_email_verification_sent'))
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        code = code_from(message)
        # The code is only inside the email: not in the subject or the inbox preview text.
        self.assertNotIn(code, message.subject)
        self.assertNotIn(code, preheader(message))
        self.assertIn(code, html_text(message))

        page = self.client.get(reverse('account_email_verification_sent'))
        self.assertContains(page, 'ada@example.com')
        self.assertContains(page, 'data-otp')

        resp = self.client.post(reverse('account_email_verification_sent'), {'code': code})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(EmailAddress.objects.get(email='ada@example.com').verified)
        self.assertEqual(self.client.get(reverse('users:dashboard')).status_code, 200)

    def test_wrong_code_is_rejected(self):
        self.client.post(reverse('account_signup'), SIGNUP)
        resp = self.client.post(reverse('account_email_verification_sent'), {'code': '000000'})
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(EmailAddress.objects.get(email='ada@example.com').verified)

    def test_unverified_user_cannot_sign_in_without_code(self):
        user = User.objects.create_user(email='new@example.com', password='pass12345!')
        EmailAddress.objects.create(user=user, email=user.email, verified=False, primary=True)
        self.client.post(reverse('account_login'), {'login': 'new@example.com', 'password': 'pass12345!'})
        self.assertEqual(self.client.get(reverse('users:dashboard')).status_code, 302)
        self.assertEqual(len(mail.outbox), 1)


class PasswordResetByCodeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(email='tolu@example.com', password='old-pass-123!', first_name='Tolu')
        EmailAddress.objects.create(user=self.user, email=self.user.email, verified=True, primary=True)

    def test_full_reset_flow(self):
        page = self.client.get(reverse('account_reset_password'))
        self.assertContains(page, 'Forgot your password?')
        resp = self.client.post(reverse('account_reset_password'), {'email': 'tolu@example.com'})
        self.assertRedirects(resp, reverse('account_confirm_password_reset_code'))
        message = mail.outbox[0]
        code = code_from(message)
        self.assertNotIn(code, message.subject)
        self.assertNotIn(code, preheader(message))
        self.assertIn('Hi Tolu', message.alternatives[0][0])

        resp = self.client.post(reverse('account_confirm_password_reset_code'), {'code': code})
        self.assertRedirects(resp, reverse('account_complete_password_reset'), fetch_redirect_response=False)
        resp = self.client.post(reverse('account_complete_password_reset'),
                                {'password1': 'brand-New-pass-77', 'password2': 'brand-New-pass-77'})
        self.assertEqual(resp.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('brand-New-pass-77'))
        # Signed straight in, and told by email that the password changed.
        self.assertEqual(self.client.get(reverse('users:dashboard')).status_code, 200)
        self.assertIn('password was reset', mail.outbox[-1].subject)

    def test_wrong_code_does_not_unlock_reset(self):
        self.client.post(reverse('account_reset_password'), {'email': 'tolu@example.com'})
        resp = self.client.post(reverse('account_confirm_password_reset_code'), {'code': '000000'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'data-otp')

    def test_unknown_email_gets_no_code(self):
        resp = self.client.post(reverse('account_reset_password'), {'email': 'nobody@example.com'})
        self.assertContains(resp, "couldn&#x27;t find a CarHub account")
        self.assertEqual(len(mail.outbox), 0)


class GoogleButtonTests(TestCase):
    @override_settings(SOCIAL_LOGIN_ENABLED=True)
    def test_button_posts_to_google(self):
        resp = self.client.get(reverse('account_login'))
        self.assertContains(resp, 'Continue with Google')
        self.assertContains(resp, reverse('google_login'))

    @override_settings(SOCIAL_LOGIN_ENABLED=False)
    def test_button_hidden_without_keys(self):
        self.assertNotContains(self.client.get(reverse('account_login')), 'Continue with Google')
