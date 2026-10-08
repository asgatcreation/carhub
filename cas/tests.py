from decimal import Decimal
from io import BytesIO
from unittest import mock

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image

from cars.tests import TEMP_MEDIA, BaseTestCase, make_user
from users.models import Application

from . import services
from .forms import parse_fitment
from .models import Brand, CartItem, Category, Fitment, Order, Product, ProductImage, Review

AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}


def make_product(vendor, name='Brake pads', price='20000', stock=10, fits=('Toyota Camry 2018-2024',), universal=False, **kw):
    cat, _ = Category.objects.get_or_create(slug='brakes', defaults={'name': 'Brakes'})
    kw.setdefault('status', 'approved')
    p = Product.objects.create(vendor=vendor, category=cat, brand=Brand.objects.get_or_create(name='Bosch')[0], name=name,
                               description='Good pads for daily driving.', price=Decimal(price), stock=stock,
                               universal_fit=universal, **kw)
    ProductImage.objects.create(product=p, image_url='https://upload.wikimedia.org/x/1280px-pad.jpg')
    for line in fits:
        mk, md, y1, y2 = parse_fitment(line)
        Fitment.objects.create(product=p, make=mk, model=md, year_from=y1, year_to=y2)
    return p


class StoreTestCase(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.vendor = make_user('parts@example.com', is_cas_seller_approved=True, company_name='Parts Co')
        self.pads = make_product(self.vendor)
        self.charger = make_product(self.vendor, name='USB charger', price='9000', fits=(), universal=True)


class FitmentTests(StoreTestCase):
    def test_parse_fitment_lines(self):
        self.assertEqual(parse_fitment('Toyota Camry 2012-2017'), ('Toyota', 'Camry', 2012, 2017))
        self.assertEqual(parse_fitment('Land Rover Range Rover Sport 2014+'), ('Land Rover', 'Range Rover Sport', 2014, None))
        self.assertEqual(parse_fitment('Lexus (all models)'), ('Lexus', '', None, None))

    def test_fits_queryset_and_product(self):
        camry = Product.objects.public().fits('Toyota', 'Camry', 2021)
        self.assertEqual(set(camry), {self.pads, self.charger})
        self.assertEqual(list(Product.objects.public().fits('Toyota', 'Camry', 2010)), [self.charger])
        self.assertTrue(self.pads.fits({'make': 'toyota', 'model': 'camry', 'year': 2020}))
        self.assertFalse(self.pads.fits({'make': 'Honda', 'model': 'Accord', 'year': 2020}))
        self.assertIsNone(self.pads.fits(None))

    def test_shop_fit_filter_uses_my_car(self):
        honda_only = make_product(self.vendor, name='Honda pads', fits=('Honda Accord 2018-2022',))
        self.client.post(reverse('cas:garage_set'), {'make': 'Toyota', 'model': 'Camry', 'year': 2021, 'next': '/accessories/shop/'})
        resp = self.client.get(reverse('cas:shop'), {'fits': 'on'})
        names = [p.name for p in resp.context['page_obj']]
        self.assertIn('Brake pads', names)
        self.assertNotIn(honda_only.name, names)
        self.assertContains(resp, 'Fits your Camry')

    def test_unapproved_products_are_hidden(self):
        hidden = make_product(self.vendor, name='Secret part', status='pending')
        self.assertNotIn(hidden, Product.objects.public())
        self.assertEqual(self.client.get(hidden.get_absolute_url()).status_code, 404)
        self.client.force_login(self.vendor)
        self.assertEqual(self.client.get(hidden.get_absolute_url()).status_code, 200)


class CartTests(StoreTestCase):
    def test_guest_cart_merges_on_login(self):
        resp = self.client.post(reverse('cas:cart_add', args=[self.pads.pk]), {'quantity': 2}, **AJAX)
        self.assertEqual(resp.json()['parts_count'], 2)
        self.client.post(reverse('account_login'), {'login': 'buyer@example.com', 'password': 'pass12345!'})
        self.assertEqual(CartItem.objects.get(user=self.buyer, product=self.pads).quantity, 2)

    def test_quantity_capped_by_stock(self):
        self.client.force_login(self.buyer)
        low = make_product(self.vendor, name='Rare part', stock=3)
        self.client.post(reverse('cas:cart_add', args=[low.pk]), {'quantity': 9})
        self.assertEqual(CartItem.objects.get(product=low).quantity, 3)
        self.client.post(reverse('cas:cart_update', args=[low.pk]), {'quantity': 0})
        self.assertFalse(CartItem.objects.filter(product=low).exists())

    def test_delivery_fees(self):
        self.assertEqual(services.delivery_fee('Lagos', Decimal('20000')), Decimal('2500'))
        self.assertEqual(services.delivery_fee('Kano', Decimal('20000')), Decimal('5000'))
        self.assertEqual(services.delivery_fee('Kano', Decimal('150000')), Decimal('0'))
        self.assertEqual(services.delivery_fee('Kano', Decimal('20000'), 'pickup'), Decimal('0'))


CHECKOUT = {'full_name': 'Buyer Person', 'phone': '+234 803 000 0000', 'delivery_method': 'delivery', 'state': 'Lagos',
            'city': 'Lekki', 'address': '1 Admiralty Way', 'delivery_notes': ''}


@override_settings(PAYSTACK_SECRET_KEY='', DEMO_CHECKOUT=True)
class CheckoutTests(StoreTestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.buyer)
        self.client.post(reverse('cas:cart_add', args=[self.pads.pk]), {'quantity': 2})

    def test_demo_checkout_confirms_and_reduces_stock(self):
        resp = self.client.post(reverse('cas:checkout'), {**CHECKOUT, 'payment_method': 'demo'})
        order = Order.objects.get()
        self.assertRedirects(resp, f'{order.get_absolute_url()}?confirmed=1', fetch_redirect_response=False)
        self.assertEqual((order.status, order.subtotal, order.delivery_fee, order.total),
                         ('confirmed', Decimal('40000'), Decimal('2500'), Decimal('42500')))
        self.assertEqual(order.email, 'buyer@example.com')
        self.pads.refresh_from_db()
        self.assertEqual((self.pads.stock, self.pads.sold_count), (8, 2))
        self.assertEqual(order.items.get().status, 'processing')
        self.assertFalse(CartItem.objects.exists())
        self.assertEqual({m.to[0] for m in mail.outbox}, {'buyer@example.com', 'parts@example.com'})

    def test_pay_on_delivery_only_in_lagos_and_abuja(self):
        self.client.post(reverse('cas:checkout'), {**CHECKOUT, 'state': 'Kano', 'payment_method': 'pod'})
        self.assertFalse(Order.objects.exists())
        self.client.post(reverse('cas:checkout'), {**CHECKOUT, 'payment_method': 'pod'})
        order = Order.objects.get()
        self.assertEqual((order.status, order.is_paid), ('confirmed', False))

    def test_pickup_needs_no_address_and_no_fee(self):
        self.client.post(reverse('cas:checkout'), {**CHECKOUT, 'delivery_method': 'pickup', 'address': '', 'payment_method': 'demo'})
        self.assertEqual(Order.objects.get().delivery_fee, Decimal('0'))

    def test_cart_is_capped_when_stock_drops(self):
        Product.objects.filter(pk=self.pads.pk).update(stock=1)
        self.client.post(reverse('cas:checkout'), {**CHECKOUT, 'payment_method': 'demo'})
        self.assertEqual(Order.objects.get().items.get().quantity, 1)
        self.pads.refresh_from_db()
        self.assertEqual(self.pads.stock, 0)

    def test_stock_is_locked_at_order_time(self):
        """Race: stock sold elsewhere between building the cart and placing the order."""
        Product.objects.filter(pk=self.pads.pk).update(stock=1)
        with self.assertRaises(ValueError):
            services.create_order(self.buyer, [(self.pads, 2, self.pads.price * 2)], {**CHECKOUT, 'email': 'b@x.com'}, 'demo')
        self.assertFalse(Order.objects.exists())

    @override_settings(PAYSTACK_SECRET_KEY='sk_test_x', DEMO_CHECKOUT=False)
    def test_paystack_charges_the_full_total(self):
        with mock.patch('cars.payments.requests.post') as post:
            post.return_value.json.return_value = {'status': True, 'data': {'authorization_url': 'https://checkout.paystack.com/x'}}
            resp = self.client.post(reverse('cas:checkout'), {**CHECKOUT, 'payment_method': 'paystack'})
        self.assertEqual(resp['Location'], 'https://checkout.paystack.com/x')
        self.assertEqual(post.call_args.kwargs['json']['amount'], 4_250_000)  # ₦42,500 in kobo
        self.assertEqual(Order.objects.get().status, 'pending')


@override_settings(PAYSTACK_SECRET_KEY='', DEMO_CHECKOUT=True)
class FulfilmentTests(StoreTestCase):
    def setUp(self):
        super().setUp()
        order = services.create_order(self.buyer, [(self.pads, 1, self.pads.price)], {**CHECKOUT, 'email': 'buyer@example.com'}, 'demo')
        order.confirm('DEMO')
        self.item = order.items.get()

    def test_vendor_ships_then_delivers(self):
        self.client.force_login(self.vendor)
        url = reverse('cas:vendor_item_action', args=[self.item.pk])
        self.client.post(url, {'action': 'ship', 'courier': 'GIG Logistics', 'note': 'Waybill 123'})
        self.item.refresh_from_db()
        self.assertEqual((self.item.status, self.item.courier), ('shipped', 'GIG Logistics'))
        self.client.post(url, {'action': 'deliver'})
        self.item.refresh_from_db()
        self.assertEqual(self.item.status, 'delivered')
        self.assertTrue(self.buyer.notifications.filter(verb='parts_delivered').exists())

    def test_buyer_cancel_restocks(self):
        self.client.force_login(self.buyer)
        self.client.post(reverse('cas:order_item_cancel', args=[self.item.pk]), {'reason': 'Ordered the wrong one'})
        self.item.refresh_from_db()
        self.pads.refresh_from_db()
        self.assertEqual((self.item.status, self.pads.stock), ('cancelled', 10))

    def test_other_vendors_cannot_touch_the_item(self):
        other = make_user('other-vendor@example.com', is_cas_seller_approved=True)
        self.client.force_login(other)
        self.assertEqual(self.client.post(reverse('cas:vendor_item_action', args=[self.item.pk]), {'action': 'deliver'}).status_code, 404)


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class VendorAndModerationTests(StoreTestCase):
    def setUp(self):
        super().setUp()
        self.staff = make_user('mod@example.com')
        self.staff.is_staff = True
        self.staff.save()

    def _png(self):
        buf = BytesIO()
        Image.new('RGB', (40, 30), 'blue').save(buf, format='PNG')
        return SimpleUploadedFile('p.png', buf.getvalue(), content_type='image/png')

    def test_new_product_waits_for_approval(self):
        self.client.force_login(self.vendor)
        cat = Category.objects.get(slug='brakes')
        resp = self.client.post(reverse('cas:product_create'), {
            'category': cat.pk, 'name': 'Wiper blades', 'brand_name': 'Bosch', 'description': 'Flat wiper blades.',
            'price': '15000', 'stock': 12, 'part_type': 'aftermarket', 'warranty_months': 0, 'dispatch_days': 1,
            'is_active': 'on', 'fitment_text': 'Toyota Corolla 2019-2024\nHonda Civic 2016+',
            'specs_text': 'Length: 650 mm', 'photos': self._png()})
        self.assertRedirects(resp, reverse('cas:vendor'))
        p = Product.objects.get(name='Wiper blades')
        self.assertEqual(p.status, 'pending')
        self.assertEqual([f.label for f in p.fitments.all()], ['Honda Civic 2016+', 'Toyota Corolla 2019–2024'])
        self.assertNotIn(p, Product.objects.public())

        self.client.force_login(self.staff)
        self.assertContains(self.client.get(reverse('staff:products')), 'Wiper blades')
        self.client.post(reverse('staff:product_decide', args=[p.pk]), {'decision': 'approve'}, **AJAX)
        self.assertIn(p, Product.objects.public())
        self.assertTrue(self.vendor.notifications.filter(verb='product_approved').exists())

    def test_non_vendor_is_sent_to_apply(self):
        self.client.force_login(self.buyer)
        self.assertRedirects(self.client.get(reverse('cas:vendor')), reverse('cas:sell'))
        self.client.post(reverse('cas:sell'), {'full_name': 'B', 'phone': '0803', 'company_name': 'Shop', 'address': 'Lagos',
                                               'id_type': 'cac', 'id_number': 'RC1', 'experience_years': 2})
        self.assertTrue(Application.objects.filter(user=self.buyer, role='cas_seller', status='pending').exists())

    def test_product_review_moderation_updates_rating(self):
        self.client.force_login(self.buyer)
        self.client.post(reverse('cas:review', args=[self.pads.slug]), {'rating': 4, 'title': 'Good', 'body': 'Fitted well on my Camry.'})
        review = Review.objects.get()
        self.assertEqual(review.status, 'pending')
        self.pads.refresh_from_db()
        self.assertEqual(self.pads.rating_count, 0)
        self.client.force_login(self.staff)
        self.assertContains(self.client.get(reverse('staff:reviews'), {'kind': 'parts'}), 'Fitted well')
        self.client.post(reverse('staff:part_review_decide', args=[review.pk]), {'decision': 'approve'}, **AJAX)
        self.pads.refresh_from_db()
        self.assertEqual((self.pads.rating_count, float(self.pads.rating_avg)), (1, 4.0))


@override_settings(PAYSTACK_SECRET_KEY='sk_test_secret')
class PartsWebhookTests(StoreTestCase):
    def test_webhook_confirms_parts_order(self):
        import hashlib
        import hmac
        import json
        order = services.create_order(self.buyer, [(self.pads, 1, self.pads.price)], {**CHECKOUT, 'email': 'b@x.com'}, 'paystack')
        order.payment_reference = 'CP-REF-1'
        order.save()
        body = json.dumps({'event': 'charge.success', 'data': {'reference': 'CP-REF-1', 'amount': int(order.total * 100)}}).encode()
        sig = hmac.new(b'sk_test_secret', body, hashlib.sha512).hexdigest()
        self.client.post(reverse('cars:paystack_webhook'), body, content_type='application/json', HTTP_X_PAYSTACK_SIGNATURE=sig)
        order.refresh_from_db()
        self.assertEqual(order.status, 'confirmed')
