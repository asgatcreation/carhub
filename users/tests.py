import os
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from cars.tests import png_file

from .models import Application, Profile

User = get_user_model()
TEMP_MEDIA = tempfile.mkdtemp(prefix='carhub-test-media-')


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ProfileTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.user = User.objects.create_user(email='ada@example.com', password='pass12345!', first_name='Ada')

    def test_profile_is_created_with_user(self):
        self.assertTrue(Profile.objects.filter(user=self.user).exists())

    def test_thumbnails_are_generated_once(self):
        """Regression: Profile.save used to recurse and write thousands of thumbnail files."""
        profile = self.user.profile
        profile.profile_image = png_file('avatar.png')
        profile.save()
        profile.save()  # saving again without a new photo must not regenerate thumbnails
        thumbs_dir = os.path.join(TEMP_MEDIA, 'profile_images', 'thumbnails')
        self.assertEqual(len(os.listdir(thumbs_dir)), 2)
        self.assertTrue(profile.avatar_url.endswith('_sm.jpg'))

    def test_settings_update(self):
        self.client.force_login(self.user)
        resp = self.client.post(reverse('users:settings'), {
            'first_name': 'Adaeze', 'last_name': 'Okafor', 'phone': '+2348030000000', 'city': 'Lekki',
            'company_name': 'Ada Autos', 'chat_enabled': 'on',
        })
        self.assertRedirects(resp, reverse('users:settings'))
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Adaeze')
        self.assertEqual(self.user.profile.company_name, 'Ada Autos')


class SellerVerificationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='seller@example.com', password='pass12345!')
        self.staff = User.objects.create_user(email='staff@example.com', password='pass12345!', is_staff=True)

    def test_apply_and_get_approved(self):
        self.client.force_login(self.user)
        self.client.post(reverse('users:apply_seller'), {
            'full_name': 'Seller One', 'phone': '08030000000', 'company_name': 'One Motors', 'address': 'Lagos',
            'id_type': 'cac', 'id_number': 'RC123', 'experience_years': 3, 'additional_info': '',
        })
        app = Application.objects.get(user=self.user)
        self.assertEqual(app.status, 'pending')

        self.client.force_login(self.staff)
        self.client.post(reverse('users:applications'), {'app_id': app.pk, 'action': 'approve'})
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.is_verified)
        self.assertEqual(self.user.profile.company_name, 'One Motors')
        self.assertTrue(self.user.notifications.filter(verb='application_approved').exists())

    def test_applications_page_is_staff_only(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('users:applications')).status_code, 302)
