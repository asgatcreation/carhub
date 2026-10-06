import hashlib
import hmac
import json
import shutil
import tempfile
from decimal import Decimal
from io import BytesIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from users.models import Conversation, Message, Notification

from . import services
from .models import Car, CarImage, CartItem, Order, WishlistItem

User = get_user_model()
TEMP_MEDIA = tempfile.mkdtemp(prefix='carhub-test-media-')


def make_user(email, **profile):
    user = User.objects.create_user(email=email, password='pass12345!', first_name='Test', last_name=email.split('@')[0])
    for key, value in profile.items():
        setattr(user.profile, key, value)
    if profile:
        user.profile.save()
    return user


def make_car(seller=None, **kwargs):
    defaults = dict(brand='Toyota', model='Camry', trim='SE', year=2021, price=Decimal('25000000'), mileage=40000,
                    body_type='sedan', location='Lekki', state='Lagos', created_by=seller)
    defaults.update(kwargs)
    car = Car.objects.create(**defaults)
    CarImage.objects.create(car=car, image_url='https://upload.wikimedia.org/x/1280px-car.jpg', credit='Tester', license='CC0')
    return car


def png_file(name='photo.png'):
    buffer = BytesIO()
    Image.new('RGB', (40, 30), 'orange').save(buffer, format='PNG')
    return SimpleUploadedFile(name, buffer.getvalue(), content_type='image/png')


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class BaseTestCase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.dealer = make_user('dealer@example.com', is_verified=True, company_name='Test Motors')
        self.buyer = make_user('buyer@example.com')
        self.car = make_car(self.dealer)


class CarModelTests(BaseTestCase):
    def test_verified_seller_listing_is_auto_approved(self):
        self.assertEqual(self.car.approval_status, 'approved')
        self.assertEqual(self.car.approved_by, self.dealer)

    def test_new_seller_listing_waits_for_review(self):
        car = make_car(self.buyer)
        self.assertEqual(car.approval_status, 'pending')
        self.assertNotIn(car, Car.objects.public())

    def test_slugs_are_unique(self):
        twin = make_car(self.dealer)
        self.assertNotEqual(twin.slug, self.car.slug)
        self.assertTrue(twin.slug.startswith('2021-toyota-camry-se'))

    def test_public_queryset_hides_sold_and_rejected(self):
        sold = make_car(self.dealer, status='sold')
        rejected = make_car(self.dealer)
        rejected.reject(self.dealer, 'bad photos')
        public = set(Car.objects.public())
        self.assertIn(self.car, public)
        self.assertNotIn(sold, public)
        self.assertNotIn(rejected, public)

    def test_condition_grade_is_derived_for_used_cars(self):
        self.assertEqual(self.car.condition_grade, 'good')

    def test_card_thumbnail_uses_smaller_rendition(self):
        self.assertIn('/500px-', self.car.thumbnail)
        self.assertIn('/1280px-', self.car.primary_image)


class BrowseTests(BaseTestCase):
    def test_filters_and_text_search(self):
        make_car(self.dealer, brand='Lexus', model='RX 350', body_type='suv', year=2019, price=Decimal('60000000'))
        url = reverse('cars:browse')
        self.assertEqual(self.client.get(url, {'body': 'suv'}).context['page_obj'].paginator.count, 1)
        self.assertEqual(self.client.get(url, {'q': '2019 lexus'}).context['page_obj'].paginator.count, 1)
        self.assertEqual(self.client.get(url, {'max_price': 30000000}).context['page_obj'].paginator.count, 1)
        self.assertEqual(self.client.get(url, {'q': 'camry lagos'}).context['page_obj'].paginator.count, 1)

    def test_invalid_params_do_not_crash(self):
        resp = self.client.get(reverse('cars:browse'), {'min_price': 'abc', 'page': '999', 'sort': 'nonsense'})
        self.assertEqual(resp.status_code, 200)

    def test_pending_listings_are_not_listed(self):
        make_car(self.buyer, brand='Honda', model='Pilot')
        resp = self.client.get(reverse('cars:browse'), {'brand': 'Honda'})
        self.assertEqual(resp.context['page_obj'].paginator.count, 0)

    def test_autocomplete(self):
        data = self.client.get(reverse('cars:suggest'), {'q': 'cam'}).json()
        self.assertEqual(data['results'][0]['label'], 'Toyota Camry')


class DetailTests(BaseTestCase):
    def test_detail_page_and_view_counter(self):
        resp = self.client.get(self.car.get_absolute_url())
        self.assertContains(resp, '2021 Toyota Camry')
        self.car.refresh_from_db()
        self.assertEqual(self.car.views_count, 1)

    def test_pending_listing_visible_only_to_owner_and_staff(self):
        car = make_car(self.buyer)
        self.assertEqual(self.client.get(car.get_absolute_url()).status_code, 404)
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get(car.get_absolute_url()).status_code, 200)
        staff = User.objects.create_user(email='staff@example.com', password='x', is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(car.get_absolute_url()).status_code, 200)


class CartTests(BaseTestCase):
    def test_guest_cart_is_merged_on_login(self):
        self.client.post(reverse('cars:cart_add', args=[self.car.pk]))
        self.assertEqual(self.client.session[services.CART_KEY], [self.car.pk])
        self.client.post(reverse('account_login'), {'login': 'buyer@example.com', 'password': 'pass12345!'})
        self.assertTrue(CartItem.objects.filter(cart__user=self.buyer, car=self.car).exists())

    def test_ajax_add_returns_count(self):
        resp = self.client.post(reverse('cars:cart_add', args=[self.car.pk]), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.json()['cart_count'], 1)

    def test_cannot_add_own_or_reserved_car(self):
        self.client.force_login(self.dealer)
        self.client.post(reverse('cars:cart_add', args=[self.car.pk]))
        self.assertFalse(CartItem.objects.exists())
        self.car.status = 'reserved'
        self.car.save()
        self.client.force_login(self.buyer)
        resp = self.client.post(reverse('cars:cart_add', args=[self.car.pk]), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 409)

    def test_remove_from_cart(self):
        self.client.force_login(self.buyer)
        self.client.post(reverse('cars:cart_add', args=[self.car.pk]))
        self.client.post(reverse('cars:cart_remove', args=[self.car.pk]))
        self.assertFalse(CartItem.objects.exists())

    def test_wishlist_toggle(self):
        self.client.force_login(self.buyer)
        url = reverse('cars:wishlist_toggle', args=[self.car.pk])
        self.assertTrue(self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest').json()['saved'])
        self.assertFalse(self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest').json()['saved'])
        self.assertFalse(WishlistItem.objects.exists())


CHECKOUT_DATA = {'full_name': 'Buyer Person', 'email': 'buyer@example.com', 'phone': '+234 803 000 0000',
                 'inspection_state': 'Lagos', 'notes': '', 'agree': 'on'}


class CheckoutTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.buyer)
        self.client.post(reverse('cars:cart_add', args=[self.car.pk]))

    def test_checkout_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse('cars:checkout'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/accounts/login/', resp['Location'])

    @override_settings(PAYSTACK_SECRET_KEY='', DEMO_CHECKOUT=True)
    def test_demo_checkout_reserves_car(self):
        resp = self.client.post(reverse('cars:checkout'), CHECKOUT_DATA)
        order = Order.objects.get()
        self.assertRedirects(resp, order.get_absolute_url())
        self.assertEqual((order.status, order.provider), ('paid', 'demo'))
        self.assertEqual(order.deposit_total, Decimal('250000'))
        self.assertEqual(order.items.get().price, self.car.price)
        self.car.refresh_from_db()
        self.assertEqual(self.car.status, 'reserved')
        self.assertFalse(CartItem.objects.exists())

    @override_settings(PAYSTACK_SECRET_KEY='', DEMO_CHECKOUT=False)
    def test_no_payment_without_provider(self):
        """Regression: the old checkout marked purchases complete when the payment provider was unavailable."""
        self.client.post(reverse('cars:checkout'), CHECKOUT_DATA)
        self.assertFalse(Order.objects.filter(status='paid').exists())
        self.car.refresh_from_db()
        self.assertEqual(self.car.status, 'available')

    @override_settings(PAYSTACK_SECRET_KEY='sk_test_x', DEMO_CHECKOUT=False)
    def test_paystack_checkout_redirects_and_waits_for_payment(self):
        with mock.patch('cars.payments.requests.post') as post:
            post.return_value.json.return_value = {'status': True, 'data': {'authorization_url': 'https://checkout.paystack.com/abc'}}
            resp = self.client.post(reverse('cars:checkout'), CHECKOUT_DATA)
        self.assertEqual(resp['Location'], 'https://checkout.paystack.com/abc')
        order = Order.objects.get()
        self.assertEqual(order.status, 'pending')
        self.assertEqual(post.call_args.kwargs['json']['amount'], 25_000_000)  # ₦250,000 in kobo

    @override_settings(PAYSTACK_SECRET_KEY='', DEMO_CHECKOUT=True)
    def test_checkout_rejects_car_reserved_meanwhile(self):
        Car.objects.filter(pk=self.car.pk).update(status='reserved')
        self.client.post(reverse('cars:checkout'), CHECKOUT_DATA)
        self.assertFalse(Order.objects.exists())


@override_settings(PAYSTACK_SECRET_KEY='sk_test_secret')
class PaystackWebhookTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.order = services.create_order(self.buyer, [self.car], {k: v for k, v in CHECKOUT_DATA.items() if k != 'agree'}, 'paystack')
        self.order.payment_reference = 'REF-1'
        self.order.save()

    def _post(self, payload, secret='sk_test_secret'):
        body = json.dumps(payload).encode()
        sig = hmac.new(secret.encode(), body, hashlib.sha512).hexdigest()
        return self.client.post(reverse('cars:paystack_webhook'), body, content_type='application/json', HTTP_X_PAYSTACK_SIGNATURE=sig)

    def test_valid_signature_marks_order_paid(self):
        resp = self._post({'event': 'charge.success', 'data': {'reference': 'REF-1', 'amount': 25_000_000}})
        self.assertEqual(resp.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')

    def test_bad_signature_is_rejected(self):
        resp = self._post({'event': 'charge.success', 'data': {'reference': 'REF-1', 'amount': 25_000_000}}, secret='wrong')
        self.assertEqual(resp.status_code, 400)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'pending')

    def test_amount_mismatch_is_ignored(self):
        self._post({'event': 'charge.success', 'data': {'reference': 'REF-1', 'amount': 100}})
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'pending')


class SellingTests(BaseTestCase):
    def listing_data(self, **extra):
        data = {'brand': 'Honda', 'model': 'Accord', 'trim': 'Sport', 'year': 2020, 'price': 22000000,
                'body_type': 'sedan', 'condition': 'foreign_used', 'mileage': 50000, 'engine_type': 'petrol_gas',
                'transmission': 'automatic', 'drivetrain': 'fwd', 'num_seats': 5, 'location': 'Ikeja', 'state': 'Lagos'}
        data.update(extra)
        return data

    def test_new_seller_listing_goes_to_moderation(self):
        self.client.force_login(self.buyer)
        resp = self.client.post(reverse('cars:listing_create'), self.listing_data(photos=[png_file(), png_file('b.png')]))
        self.assertRedirects(resp, reverse('cars:my_listings'))
        car = Car.objects.get(model='Accord')
        self.assertEqual(car.approval_status, 'pending')
        self.assertEqual(car.images.count(), 2)

    def test_listing_requires_a_photo(self):
        self.client.force_login(self.buyer)
        resp = self.client.post(reverse('cars:listing_create'), self.listing_data())
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Car.objects.filter(model='Accord').exists())

    def test_only_owner_can_edit(self):
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get(reverse('cars:listing_edit', args=[self.car.slug])).status_code, 404)

    def test_mark_sold_updates_seller_stats(self):
        self.client.force_login(self.dealer)
        self.client.post(reverse('cars:listing_status', args=[self.car.slug]), {'action': 'sold'})
        self.car.refresh_from_db()
        self.dealer.profile.refresh_from_db()
        self.assertEqual(self.car.status, 'sold')
        self.assertEqual(self.dealer.profile.sold_count, 1)


class ModerationTests(BaseTestCase):
    def test_moderation_is_staff_only(self):
        self.client.force_login(self.buyer)
        self.assertEqual(self.client.get(reverse('cars:moderation')).status_code, 302)

    def test_approve_notifies_seller(self):
        car = make_car(self.buyer)
        staff = User.objects.create_user(email='mod@example.com', password='x', is_staff=True)
        self.client.force_login(staff)
        self.client.post(reverse('cars:moderate', args=[car.pk]), {'decision': 'approve'})
        car.refresh_from_db()
        self.assertEqual(car.approval_status, 'approved')
        self.assertTrue(Notification.objects.filter(user=self.buyer, verb='approved').exists())


class MessagingTests(BaseTestCase):
    def test_contact_seller_creates_conversation_and_notification(self):
        self.client.force_login(self.buyer)
        resp = self.client.post(reverse('cars:contact_seller', args=[self.car.slug]), {'message': 'Is it available?'})
        convo = Conversation.objects.get(car=self.car)
        self.assertRedirects(resp, reverse('users:conversation', args=[convo.pk]))
        self.assertEqual(set(convo.participants.all()), {self.buyer, self.dealer})
        self.assertTrue(Notification.objects.filter(user=self.dealer, verb='message').exists())

    def test_cannot_message_yourself(self):
        self.client.force_login(self.dealer)
        self.client.post(reverse('cars:contact_seller', args=[self.car.slug]), {'message': 'hi'})
        self.assertFalse(Conversation.objects.exists())

    def test_outsiders_cannot_read_conversations(self):
        convo = Conversation.objects.create(car=self.car)
        convo.participants.add(self.buyer, self.dealer)
        Message.objects.create(conversation=convo, sender=self.buyer, content='secret')
        outsider = make_user('outsider@example.com')
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(reverse('users:conversation', args=[convo.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('users:conversation_poll', args=[convo.pk])).status_code, 404)

    def test_message_html_is_escaped(self):
        convo = Conversation.objects.create(car=self.car)
        convo.participants.add(self.buyer, self.dealer)
        Message.objects.create(conversation=convo, sender=self.buyer, content='<img src=x onerror=alert(1)>')
        self.client.force_login(self.dealer)
        resp = self.client.get(reverse('users:conversation', args=[convo.pk]))
        self.assertNotContains(resp, '<img src=x onerror')
        self.assertContains(resp, '&lt;img src=x onerror')
