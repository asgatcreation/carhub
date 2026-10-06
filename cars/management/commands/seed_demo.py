"""Populate the marketplace with realistic demo data.

    python manage.py seed_demo          # first run
    python manage.py seed_demo --reset  # wipe demo data and start again

All demo accounts use the email domain @carhub.demo and the password below.
"""
import json
import random
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.test.utils import override_settings
from django.utils import timezone

from cars.models import Car, CarImage, Cart, CartItem, Feature, WishlistItem
from cars.seed.catalog import COLORS, FEATURES, LOCATIONS, MODELS
from allauth.account.models import EmailAddress

from cars import services
from cars.services import create_order
from users.models import Application, Conversation, Message, Notification, Review

User = get_user_model()

DEMO_DOMAIN = 'carhub.demo'
DEMO_PASSWORD = 'CarHubDemo!2026'  # demo-only credential, documented in README.md
PHOTOS = Path(__file__).resolve().parents[2] / 'seed' / 'photos.json'

DEALERS = [
    # email local part, first, last, company, city, state, years, specialization, bio
    ('harborpoint', 'Chinedu', 'Okeke', 'Harbor Point Motors', 'Lekki', 'Lagos', 11, 'Toyota & Lexus SUVs',
     'Foreign-used Toyota and Lexus specialists. Every car is inspected on a 150-point checklist before listing.'),
    ('crescent', 'Aisha', 'Bello', 'Crescent Auto Gallery', 'Wuse II', 'FCT', 8, 'Luxury German cars',
     'Abuja showroom for Mercedes-Benz, BMW and Range Rover. Duty-cleared, with verifiable service history.'),
    ('rivergate', 'Ebi', 'Tamuno', 'Rivergate Autos', 'Port Harcourt', 'Rivers', 6, 'Pickups & family SUVs',
     'Trusted by oil & gas fleets in Port Harcourt for rugged pickups and family SUVs.'),
    ('prestige', 'Kunle', 'Bakare', 'Prestige Wheels', 'Ikeja', 'Lagos', 14, 'Honda, Toyota & Hyundai',
     'Affordable, reliable everyday cars with financing partners and a 30-day engine warranty.'),
    ('sapphire', 'Ngozi', 'Eze', 'Sapphire Motors', 'Victoria Island', 'Lagos', 9, 'Premium & electric vehicles',
     'Premium, hybrid and electric vehicles for Lagos drivers who want the latest.'),
    ('northgate', 'Ibrahim', 'Musa', 'Northgate Cars', 'Kano', 'Kano', 5, 'Value SUVs & sedans',
     'Northern Nigeria’s go-to for honest prices on sedans and SUVs.'),
]
PRIVATE = [
    ('femi', 'Femi', 'Adebayo', 'Ibadan', 'Oyo'),
    ('blessing', 'Blessing', 'Okon', 'Enugu', 'Enugu'),
    ('yusuf', 'Yusuf', 'Danjuma', 'Gwarinpa', 'FCT'),
    ('grace', 'Grace', 'Nwosu', 'Benin City', 'Edo'),
]
BUYERS = [('buyer', 'Tolu', 'Adeyemi'), ('amaka', 'Amaka', 'Obi'), ('segun', 'Segun', 'Alabi'),
          ('halima', 'Halima', 'Sani'), ('david', 'David', 'Etim')]

ENGINE_SIZES = {
    'corolla': '1.8L 4-cyl', 'camry': '2.5L 4-cyl', 'rav4': '2.5L 4-cyl', 'rav4h': '2.5L hybrid', 'highlander': '3.5L V6',
    'lc300': '3.5L twin-turbo V6', 'prado': '4.0L V6', 'hilux': '2.8L turbo-diesel', 'sienna': '2.5L hybrid',
    'venza': '2.5L hybrid', 'prius': '1.8L hybrid', 'rx': '3.5L V6', 'rxh': '3.5L V6 hybrid', 'es': '3.5L V6',
    'gx': '4.6L V8', 'lx': '3.4L twin-turbo V6', 'accord': '1.5L turbo', 'civic': '2.0L 4-cyl', 'crv': '1.5L turbo',
    'pilot': '3.5L V6', 'c205': '2.0L turbo', 'c206': '2.0L turbo', 'e213': '3.0L turbo I6', 'gle': '3.0L turbo I6',
    'glc': '2.0L turbo', 'gclass': '4.0L twin-turbo V8', 'bmw3': '2.0L turbo', 'x5': '3.0L turbo I6', 'x3': '2.0L turbo',
    'elantra': '2.0L 4-cyl', 'tucson': '2.5L 4-cyl', 'santafe': '2.5L turbo', 'ioniq5': 'Dual motor, 77 kWh',
    'sportage': '2.5L 4-cyl', 'sorento': '2.5L turbo', 'explorer': '2.3L EcoBoost', 'ranger': '2.0L bi-turbo diesel',
    'p3008': '1.6L turbo', 'altima': '2.5L 4-cyl', 'rr': '3.0L mild-hybrid I6', 'rrs': '3.0L mild-hybrid I6',
    'velar': '2.0L turbo', 'tiguan': '2.0L TSI', 'model3': 'Dual motor, 75 kWh', 'modely': 'Dual motor, 75 kWh',
}
ORIGINS = {'Toyota': 'Japan', 'Lexus': 'Japan', 'Honda': 'Japan', 'Nissan': 'Japan', 'Mercedes-Benz': 'Germany',
           'BMW': 'Germany', 'Volkswagen': 'Germany', 'Hyundai': 'South Korea', 'Kia': 'South Korea',
           'Ford': 'United States', 'Tesla': 'United States', 'Land Rover': 'United Kingdom', 'Peugeot': 'France'}


class Command(BaseCommand):
    help = 'Create demo users, ~100 car listings, reviews, conversations and an order.'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Delete existing demo data first.')
        parser.add_argument('--seed', type=int, default=2026)
        parser.add_argument('--if-empty', action='store_true', help='Do nothing when demo data already exists (for deploy scripts).')

    def handle(self, *args, **opts):
        self.rng = random.Random(opts['seed'])
        demo_users = User.objects.filter(email__endswith='@' + DEMO_DOMAIN)
        if demo_users.exists() and opts['if_empty']:
            self.stdout.write('Demo data already present — skipping.')
            return
        if demo_users.exists():
            if not opts['reset']:
                raise CommandError('Demo data already exists. Re-run with --reset to recreate it.')
            self._wipe(demo_users)
        if not PHOTOS.exists():
            raise CommandError('cars/seed/photos.json is missing — run `python manage.py fetch_car_photos` first.')
        self.photos = json.loads(PHOTOS.read_text(encoding='utf-8'))

        # Seeding triggers reservation notifications; don't send real email for them.
        with transaction.atomic(), override_settings(EMAIL_BACKEND='django.core.mail.backends.dummy.EmailBackend'):
            Site.objects.update_or_create(pk=1, defaults={'domain': 'localhost:8000', 'name': 'CarHub'})
            self._features()
            self._users()
            cars = self._cars()
            self._activity(cars)
            self._reservations(cars)

        self.stdout.write(self.style.SUCCESS(
            f'Seeded {Car.objects.count()} cars, {User.objects.count()} users. '
            f'Demo logins use @{DEMO_DOMAIN} emails — see README.md.'))

    # ------------------------------------------------------------------
    def _wipe(self, demo_users):
        from cars.models import Order
        Order.objects.filter(user__in=demo_users).delete()
        Car.objects.filter(created_by__in=demo_users).delete()
        Conversation.objects.filter(participants__in=demo_users).delete()
        demo_users.delete()
        self.stdout.write('Removed previous demo data.')

    def _user(self, local, first, last, **extra):
        user = User.objects.create_user(
            email=f'{local}@{DEMO_DOMAIN}', password=DEMO_PASSWORD, first_name=first, last_name=last,
            username=local, **extra,
        )
        user.date_joined = timezone.now() - timedelta(days=self.rng.randint(120, 900))
        user.save(update_fields=['date_joined'])
        # Demo inboxes don't exist, so mark the address verified (sign-in requires a verified email).
        EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
        return user

    def _features(self):
        self.features = {}
        for category, names in FEATURES.items():
            for name in names:
                self.features[name], _ = Feature.objects.get_or_create(name=name, defaults={'category': category})

    def _users(self):
        # A staff moderator (not a superuser) so a public demo can't be used to wreck the data.
        self.admin = self._user('moderator', 'Musa', 'Okafor', is_staff=True)
        self.admin.user_permissions.set(Permission.objects.filter(
            content_type__app_label__in=['cars', 'users'],
            codename__in=['view_car', 'change_car', 'view_carimage', 'view_order', 'view_application', 'change_application'],
        ))
        self.buyers = [self._user(*b) for b in BUYERS]
        for b in self.buyers:
            b.profile.phone = f'+234 80{self.rng.randint(1, 9)} {self.rng.randint(100, 999)} {self.rng.randint(1000, 9999)}'
            b.profile.city = self.rng.choice(['Lekki', 'Ikeja', 'Wuse II', 'Port Harcourt'])
            b.profile.save()

        self.dealers = []
        for local, first, last, company, city, state, years, spec, bio in DEALERS:
            user = self._user(local, first, last)
            p = user.profile
            p.company_name, p.city, p.years_in_business, p.specialization = company, city, years, spec
            p.bio = bio
            p.business_description = (f'{bio} Visit our {city} showroom Monday–Saturday, 9am–6pm. '
                                      'We accept bank transfer and can arrange inspection by an independent mechanic.')
            p.phone = f'+234 81{self.rng.randint(0, 9)} {self.rng.randint(100, 999)} {self.rng.randint(1000, 9999)}'
            p.whatsapp_number = p.phone
            p.is_verified = p.is_car_seller_approved = True
            p.seller_type = 'dealer'
            p.save()
            user.home = (city, state)
            self.dealers.append(user)

        self.private = []
        for local, first, last, city, state in PRIVATE:
            user = self._user(local, first, last)
            p = user.profile
            p.city, p.seller_type = city, 'private'
            p.bio = 'Private seller — car has been well looked after and regularly serviced.'
            p.phone = f'+234 70{self.rng.randint(1, 9)} {self.rng.randint(100, 999)} {self.rng.randint(1000, 9999)}'
            p.save()
            user.home = (city, state)
            self.private.append(user)

    # ------------------------------------------------------------------
    def _cars(self):
        rng = self.rng
        now = timezone.now()
        this_year = now.year
        cars = []
        for spec in MODELS:
            photos = self.photos.get(spec['key']) or []
            for i in range(spec['count']):
                seller = rng.choice(self.dealers) if rng.random() < 0.82 else rng.choice(self.private)
                y0, y1 = spec['years']
                year = rng.randint(y0, y1)
                age = this_year - year
                is_new = year >= this_year - 1 and rng.random() < 0.35
                condition = 'new' if is_new else ('foreign_used' if rng.random() < 0.68 else 'nigerian_used')
                mileage = rng.randint(5, 60) if is_new else max(4_000, int(age * rng.randint(9_000, 19_000) * (1.25 if condition == 'nigerian_used' else 1)))

                lo, hi = spec['price']
                position = (year - y0) / max(1, y1 - y0)
                price_m = lo + (hi - lo) * (0.25 + 0.6 * position) * rng.uniform(0.85, 1.12)
                if condition == 'nigerian_used':
                    price_m *= 0.82
                if is_new:
                    price_m = max(price_m, hi * 0.95)
                price = Decimal(int(round(price_m * 1_000_000 / 50_000) * 50_000))

                city, state = seller.home if rng.random() < 0.85 else rng.choice([(c, s) for c, s, _ in LOCATIONS])
                drive = rng.choice(spec['drive'])
                manual = spec['body'] == 'pickup' and rng.random() < 0.35
                trim = rng.choice(spec['trims'])
                feature_count = 6 + int(min(10, spec['price'][1] / 40)) + rng.randint(0, 3)
                features = rng.sample(list(self.features.values()), min(feature_count, len(self.features)))

                car = Car(
                    brand=spec['brand'], model=spec['model'], trim=trim, year=year, price=price,
                    created_by=seller, body_type=spec['body'], condition=condition, mileage=mileage,
                    engine_type=spec['engine'], engine_size=ENGINE_SIZES.get(spec['key'], ''),
                    drivetrain=drive, transmission='manual' if manual else 'automatic',
                    exterior_color=rng.choice(COLORS), interior_color=rng.choice(['Black', 'Beige', 'Brown', 'Grey', 'Red']),
                    num_seats=spec['seats'], num_previous_owners=None if is_new else rng.randint(1, 3),
                    vin=self._vin(), country_of_origin=ORIGINS.get(spec['brand'], ''),
                    duty_paid=rng.random() < 0.92, location=city, state=state,
                    warranty='Manufacturer warranty' if is_new else rng.choice(['', '', '30-day engine & gearbox', '3-month dealer warranty']),
                    views_count=rng.randint(15, 2600),
                )
                car.description = self._description(car, spec, condition)
                car.save()
                car.features.set(features)
                # vary the cover between cars of the same model, but never lead with an interior shot
                exterior = [p for p in photos if not p.get('interior')]
                interior = [p for p in photos if p.get('interior')]
                shift = i % len(exterior) if exterior else 0
                ordered = exterior[shift:] + exterior[:shift] + interior
                CarImage.objects.bulk_create([
                    CarImage(car=car, image_url=p['url'], alt_text=f'{car.full_title}', credit=p['author'],
                             license=p['license'], source_url=p['source'], display_order=n)
                    for n, p in enumerate(ordered)
                ])
                Car.objects.filter(pk=car.pk).update(created_at=now - timedelta(days=rng.randint(0, 75), hours=rng.randint(0, 23)))
                cars.append(car)

        # Private sellers' listings: most approved by the admin, a few left for the moderation queue demo
        for n, car in enumerate([c for c in cars if c.approval_status == 'pending']):
            if n < 4:
                continue
            if n == 4:
                car.reject(self.admin, 'Photos do not match the listed model year. Please upload photos of the actual car.')
            else:
                car.approve(self.admin)

        live = [c for c in cars if c.approval_status == 'approved']
        for car in rng.sample(live, 12):
            Car.objects.filter(pk=car.pk).update(featured=True)
        for car in rng.sample(live, 4):
            car.status = 'sold'
            car.save(update_fields=['status', 'updated_at'])
        for c in cars:
            c.refresh_from_db()
        return cars

    def _vin(self):
        chars = 'ABCDEFGHJKLMNPRSTUVWXYZ0123456789'
        return ''.join(self.rng.choice(chars) for _ in range(17))

    def _description(self, car, spec, condition):
        rng = self.rng
        opener = {
            'new': f'Brand new {car.full_title}, zero mileage and still under manufacturer warranty.',
            'foreign_used': f'Clean foreign-used (tokunbo) {car.full_title}, recently cleared and in excellent shape.',
            'nigerian_used': f'Neatly used {car.full_title}, first-body paint with a complete service record.',
        }[condition]
        lines = [opener]
        lines.append(rng.choice([
            'Engine and gearbox are perfect, AC blowing ice cold.',
            'No accident history — verifiable CarFax report available on request.',
            'Interior is spotless with no tears or stains on the seats.',
            'Just serviced: new oil, filters, brake pads and tyres.',
        ]))
        if spec['engine'] in ('hybrid', 'electric'):
            lines.append('Excellent fuel economy — battery health checked and in great condition.'
                         if spec['engine'] == 'hybrid' else 'Battery health above 90% with home charger included.')
        lines.append(rng.choice([
            'Inspection is welcome at our showroom; an independent mechanic can come along.',
            'Price is slightly negotiable for a serious buyer after inspection.',
            'Available for viewing any day of the week — send a message to book a time.',
        ]))
        return ' '.join(lines)

    # ------------------------------------------------------------------
    def _activity(self, cars):
        rng = self.rng
        live = [c for c in cars if c.approval_status == 'approved' and c.status == 'available']
        buyer = self.buyers[0]
        bodies = [
            ('Smooth, honest transaction', 'The car was exactly as described and the paperwork was ready on the day. Highly recommend.'),
            ('Very professional', 'Quick to respond on chat and patient during the inspection. Will buy from them again.'),
            ('Good experience overall', 'Price was fair. Delivery took a day longer than promised but they kept me updated.'),
            ('Excellent after-sales', 'They fixed a small issue with the AC free of charge a week after purchase.'),
            ('Trustworthy dealer', 'No hidden costs, the car passed my mechanic’s inspection with flying colours.'),
            ('Great selection', 'Lots of options in my budget and they let me test drive three cars.'),
        ]
        for dealer in self.dealers:
            for reviewer in rng.sample(self.buyers, rng.randint(3, 5)):
                title, body = rng.choice(bodies)
                score = rng.choice([5, 5, 5, 4, 4, 3])
                review = Review.objects.create(
                    profile=dealer.profile, reviewer=reviewer, rating=score, title=title, body=body,
                    communication=min(5, score + rng.randint(0, 1)), professionalism=score,
                    punctuality=max(3, score - rng.randint(0, 1)), condition=min(5, score + rng.randint(-1, 1)),
                )
                Review.objects.filter(pk=review.pk).update(created_at=timezone.now() - timedelta(days=rng.randint(3, 200)))

        # Buyer ↔ seller conversations (signals create notifications + response stats)
        threads = [
            ['Hello, is this car still available?', 'Yes it is! You are welcome to inspect it any day this week.',
             'Great. Is the price negotiable?', 'Slightly — come and see it and we can talk.'],
            ['Good afternoon. Has the car ever been in an accident?', 'No accident history at all. We can share the CarFax report.'],
            ['Can I bring my mechanic for inspection on Saturday?'],
        ]
        for lines, car in zip(threads, rng.sample([c for c in live if c.created_by in self.dealers], 3)):
            convo = Conversation.objects.create(car=car)
            convo.participants.add(buyer, car.created_by)
            start = timezone.now() - timedelta(days=rng.randint(1, 5))
            for n, text in enumerate(lines):
                sender = buyer if n % 2 == 0 else car.created_by
                msg = Message.objects.create(conversation=convo, sender=sender, content=text, read=n < len(lines) - 1)
                sent_at = start + timedelta(minutes=17 * (n + 1))
                Message.objects.filter(pk=msg.pk).update(created_at=sent_at)
                Notification.objects.filter(verb='message', created_at__gte=msg.created_at).update(created_at=sent_at, unread=not msg.read)

        # Saved cars and something in the cart (reservations are created in _reservations)
        remaining = [c for c in live if c.price < 120_000_000]
        for car in rng.sample(remaining, 6):
            WishlistItem.objects.create(user=buyer, car=car)
        cart = Cart.objects.create(user=buyer)
        CartItem.objects.create(cart=cart, car=rng.choice(remaining))

        # Pending seller verification for the moderation demo
        applicant = self.private[0]
        Application.objects.create(
            user=applicant, role='car_seller', full_name=applicant.get_full_name(), phone=applicant.profile.phone,
            company_name='Adebayo Autos', address='14 Ring Road, Ibadan', id_type='cac', id_number='RC 1849203',
            experience_years=3, additional_info='I sell 3–5 cars a month and want my listings to go live faster.',
        )
        Notification.objects.create(user=self.admin, verb='application', message='New seller verification request from Femi Adebayo')

    # ------------------------------------------------------------------
    def _reserve(self, buyer, car, days_ago, note=''):
        """A paid demo reservation, back-dated so the timeline reads naturally."""
        when = timezone.now() - timedelta(days=days_ago, hours=self.rng.randint(1, 8))
        order = create_order(buyer, [car], {
            'full_name': buyer.get_full_name(), 'email': buyer.email, 'phone': buyer.profile.phone,
            'inspection_state': car.state, 'notes': note,
            'preferred_date': (timezone.now() + timedelta(days=self.rng.randint(2, 6))).date(),
            'preferred_time': self.rng.choice(['morning', 'afternoon', 'evening']),
        }, provider='demo')
        order.mark_paid(reference=f'DEMO-{order.number}')
        type(order).objects.filter(pk=order.pk).update(created_at=when, paid_at=when + timedelta(minutes=3))
        order.refresh_from_db()
        car.refresh_from_db()
        return order.items.get()

    def _schedule(self, item, in_days, hour):
        when = (timezone.localtime() + timedelta(days=in_days)).replace(hour=hour, minute=0, second=0, microsecond=0)
        seller = item.seller
        address = f"{seller.profile.company_name or seller.get_full_name()} showroom, {seller.profile.city}"
        services.schedule_inspection(item, when, address, 'Ask for the sales desk at the gate. Bring a valid ID.', seller)

    def _reservations(self, cars):
        """Reservations at every stage of the lifecycle, so buyer and dealer dashboards have content.

        Demo buyer (buyer@):   one awaiting the seller, one inspection scheduled, one completed purchase.
        Demo dealer (harborpoint@): new reservations to confirm, a scheduled inspection, a completed and a cancelled sale.
        """
        rng = self.rng
        harbor = self.dealers[0]
        tolu, amaka, segun, halima, david = self.buyers
        in_cart = set(CartItem.objects.values_list('car_id', flat=True))
        pool = {d.pk: [c for c in cars if c.created_by_id == d.pk and c.approval_status == 'approved'
                       and c.status == 'available' and c.price < 150_000_000 and c.pk not in in_cart]
                for d in self.dealers}
        take = lambda dealer: pool[dealer.pk].pop(rng.randrange(len(pool[dealer.pk])))  # noqa: E731
        others = self.dealers[1:]

        # Demo buyer
        self._reserve(tolu, take(rng.choice(others)), 1, 'I would like to inspect on a Saturday morning.')
        self._schedule(self._reserve(tolu, take(rng.choice(others)), 3, 'Coming with my mechanic.'), 2, 11)
        bought = self._reserve(tolu, take(rng.choice(others)), 30)
        self._schedule(bought, -26, 10)
        services.complete_sale(bought, bought.seller)
        type(bought).objects.filter(pk=bought.pk).update(completed_at=bought.inspection_at + timedelta(hours=2))

        # Demo dealer
        self._reserve(amaka, take(harbor), 0, 'Is the price slightly negotiable after inspection?')
        self._reserve(david, take(harbor), 1)
        self._schedule(self._reserve(segun, take(harbor), 4, 'Please have the service records ready.'), 1, 14)
        sold = self._reserve(halima, take(harbor), 21)
        self._schedule(sold, -18, 12)
        services.complete_sale(sold, harbor)
        type(sold).objects.filter(pk=sold.pk).update(completed_at=sold.inspection_at + timedelta(hours=3))
        cancelled = self._reserve(segun, take(harbor), 12)
        services.cancel_reservation(cancelled, segun, 'buyer', 'Found a car closer to home, sorry.')
