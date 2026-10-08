from unittest import mock

from allauth.account.models import EmailAddress
from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse

from cars.models import CarImage
from cars.tests import BaseTestCase, make_user
from users.models import Application, Review

AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}


class StaffTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.staff = make_user('mod@example.com')
        self.staff.is_staff = True
        self.staff.save()


class ConsoleAccessTests(StaffTestCase):
    def test_pages_require_staff(self):
        for name in ('staff:overview', 'staff:reviews', 'staff:photos', 'staff:verifications', 'cars:moderation'):
            resp = self.client.get(reverse(name))
            self.assertEqual(resp.status_code, 302, name)
            self.client.force_login(self.buyer)
            self.assertEqual(self.client.get(reverse(name)).status_code, 302, name)
            self.client.force_login(self.staff)
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)
            self.client.logout()

    def test_admin_login_uses_branded_page(self):
        resp = self.client.get('/admin/login/?next=/admin/')
        self.assertRedirects(resp, reverse('staff:login') + '?next=/admin/', fetch_redirect_response=False)

    def test_staff_login_rejects_non_staff(self):
        resp = self.client.post(reverse('staff:login'), {'login': 'buyer@example.com', 'password': 'pass12345!'})
        self.assertContains(resp, "doesn&#x27;t have staff access")
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_staff_login_signs_in_staff(self):
        resp = self.client.post(reverse('staff:login'), {'login': 'mod@example.com', 'password': 'pass12345!'})
        self.assertRedirects(resp, reverse('staff:overview'), fetch_redirect_response=False)
        self.assertContains(self.client.get(reverse('staff:overview')), 'Marketplace pulse')


class ReviewModerationTests(StaffTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse('cars:seller_profile', args=[self.dealer.pk])

    def _submit(self):
        self.client.force_login(self.buyer)
        self.client.post(self.url, {'rating': 4, 'communication': 4, 'professionalism': 4, 'punctuality': 4,
                                    'condition': 4, 'title': 'Solid', 'body': 'Call me on 0803 123 4567 for deals'})
        return Review.objects.get()

    def test_new_review_is_hidden_until_published(self):
        review = self._submit()
        self.assertEqual(review.status, 'pending')
        page = self.client.get(self.url)
        self.assertContains(page, 'awaiting moderation')
        self.assertEqual(page.context['agg']['n'], 0)

        self.client.force_login(self.staff)
        queue = self.client.get(reverse('staff:reviews'))
        self.assertContains(queue, 'Contains contact details')
        resp = self.client.post(reverse('staff:review_decide', args=[review.pk]), {'decision': 'approve'}, **AJAX)
        self.assertEqual(resp.json(), {'ok': True})
        review.refresh_from_db()
        self.assertEqual(review.status, 'approved')
        self.assertEqual(self.client.get(self.url).context['agg']['n'], 1)
        self.assertEqual({m.to[0] for m in mail.outbox}, {'buyer@example.com', 'dealer@example.com'})

    def test_reject_needs_reason_and_tells_reviewer(self):
        review = self._submit()
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(reverse('staff:review_decide', args=[review.pk]), {'decision': 'reject'}).status_code, 400)
        self.client.post(reverse('staff:review_decide', args=[review.pk]), {'decision': 'reject', 'reason': 'Advertising'})
        review.refresh_from_db()
        self.assertEqual((review.status, review.moderation_note), ('rejected', 'Advertising'))
        self.assertTrue(self.buyer.notifications.filter(verb='review_rejected').exists())

    def test_editing_resubmits_for_moderation(self):
        review = self._submit()
        Review.objects.filter(pk=review.pk).update(status='approved')
        self._submit()
        review.refresh_from_db()
        self.assertEqual(review.status, 'pending')


class PhotoQueueTests(StaffTestCase):
    def setUp(self):
        super().setUp()
        self.image = self.car.images.get()
        self.client.force_login(self.staff)

    def test_new_photo_is_listed_and_can_be_approved(self):
        self.assertContains(self.client.get(reverse('staff:photos')), self.car.full_title)
        self.client.post(reverse('staff:photo_decide', args=[self.image.pk]), {'decision': 'approve'}, **AJAX)
        self.image.refresh_from_db()
        self.assertIsNotNone(self.image.reviewed_at)
        self.assertNotContains(self.client.get(reverse('staff:photos')), self.car.full_title)

    def test_removing_a_photo_notifies_seller(self):
        self.client.post(reverse('staff:photo_decide', args=[self.image.pk]), {'decision': 'reject', 'reason': 'Not the actual car'}, **AJAX)
        self.assertFalse(CarImage.objects.filter(pk=self.image.pk).exists())
        self.assertTrue(self.dealer.notifications.filter(verb='photo_removed').exists())


class VerificationTests(StaffTestCase):
    def test_driver_approval_sets_flag(self):
        app = Application.objects.create(user=self.buyer, role='pilot', full_name='Test Driver', id_number='X1')
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(reverse('staff:verifications'), {'role': 'pilot'}), 'Test Driver')
        self.client.post(reverse('staff:verification_decide', args=[app.pk]), {'decision': 'approve'})
        self.buyer.profile.refresh_from_db()
        self.assertTrue(self.buyer.profile.is_pilot_approved)

    def test_request_changes_needs_note(self):
        app = Application.objects.create(user=self.buyer, role='car_seller', full_name='X')
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(reverse('staff:verification_decide', args=[app.pk]), {'decision': 'correction'}).status_code, 400)
        self.client.post(reverse('staff:verification_decide', args=[app.pk]), {'decision': 'correction', 'reason': 'Upload your CAC certificate'})
        app.refresh_from_db()
        self.assertEqual(app.status, 'correction_requested')


class EnsureAdminTests(BaseTestCase):
    def test_creates_verified_superuser_from_env(self):
        with mock.patch.dict('os.environ', {'ADMIN_EMAIL': 'Owner@Example.com', 'ADMIN_PASSWORD': 'Sup3r-secret!'}):
            call_command('ensure_admin', stdout=mock.MagicMock())
            call_command('ensure_admin', stdout=mock.MagicMock())  # idempotent
        user = type(self.buyer).objects.get(email='owner@example.com')
        self.assertTrue(user.is_superuser and user.is_staff and user.check_password('Sup3r-secret!'))
        self.assertTrue(EmailAddress.objects.get(user=user).verified)


class PasswordResetMessagesTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def test_unknown_email_is_reported(self):
        resp = self.client.post(reverse('account_reset_password'), {'email': 'nobody@example.com'})
        self.assertContains(resp, "couldn&#x27;t find a CarHub account")
        self.assertEqual(len(mail.outbox), 0)

    def test_google_only_account_can_add_a_password(self):
        google_user = make_user('gmailer@example.com')
        google_user.set_unusable_password()
        google_user.save()
        # First: recognised as a Google account and offered a choice, no email yet.
        resp = self.client.post(reverse('account_reset_password'), {'email': 'gmailer@example.com'})
        self.assertContains(resp, 'You sign in with Google')
        self.assertContains(resp, 'Create a password too')
        self.assertEqual(len(mail.outbox), 0)
        # Choosing "create a password" sends the code.
        resp = self.client.post(reverse('account_reset_password'), {'email': 'gmailer@example.com', 'add_password': '1'})
        self.assertRedirects(resp, reverse('account_confirm_password_reset_code'))
        self.assertIn('sign in with Google', mail.outbox[0].alternatives[0][0])

    def test_password_account_goes_straight_to_code(self):
        resp = self.client.post(reverse('account_reset_password'), {'email': 'buyer@example.com'})
        self.assertRedirects(resp, reverse('account_confirm_password_reset_code'))
        self.assertEqual(len(mail.outbox), 1)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.smtp.EmailBackend')
    def test_mail_outage_does_not_crash(self):
        with mock.patch('django.core.mail.backends.smtp.EmailBackend.send_messages', side_effect=OSError('blocked')):
            resp = self.client.post(reverse('account_reset_password'), {'email': 'buyer@example.com'}, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "couldn&#x27;t send the email")
