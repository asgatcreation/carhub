"""Seed DriverZone (called from `manage.py seed_demo`): demo drivers around Lagos and Abuja, trip history, ratings."""
import random
from datetime import timedelta
from decimal import Decimal

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.utils import timezone

from . import services
from .models import DriverProfile, Trip, TripRating

User = get_user_model()

SPOTS = {
    'Lagos': [('Lekki Phase 1', 6.4478, 3.4723), ('Victoria Island', 6.4281, 3.4219), ('Ikoyi', 6.4547, 3.4337),
              ('Yaba', 6.5095, 3.3711), ('Ikeja GRA', 6.5844, 3.3561), ('Surulere', 6.4987, 3.3618),
              ('Ajah', 6.4698, 3.5852), ('Maryland', 6.5710, 3.3666), ('Gbagada', 6.5560, 3.3889), ('Oniru', 6.4350, 3.4520)],
    'Abuja': [('Wuse 2', 9.0790, 7.4730), ('Maitama', 9.0960, 7.4920), ('Garki', 9.0380, 7.4890),
              ('Jabi', 9.0640, 7.4250), ('Gwarinpa', 9.1080, 7.4100), ('Asokoro', 9.0430, 7.5280)],
}
PLACES = {
    'Lagos': [('The Palms Shopping Mall, Lekki', 6.4352, 3.4529), ('Eko Hotel & Suites, Victoria Island', 6.4253, 3.4216),
              ('Ikeja City Mall, Alausa', 6.6142, 3.3577), ('Murtala Muhammed Airport, Ikeja', 6.5774, 3.3212),
              ('National Theatre, Iganmu', 6.4774, 3.3740), ('Lekki Conservation Centre', 6.4410, 3.5370),
              ('Yaba College of Technology', 6.5193, 3.3747), ('Ikoyi Club 1938', 6.4547, 3.4337)],
    'Abuja': [('Jabi Lake Mall', 9.0640, 7.4250), ('Nnamdi Azikiwe International Airport', 9.0068, 7.2632),
              ('Transcorp Hilton, Maitama', 9.0743, 7.4926), ('Wuse Market', 9.0647, 7.4637)],
}
DRIVERS = [
    # first, last, city, class, make, model, year, colour, years experience, languages
    ('Kunle', 'Adebayo', 'Lagos', 'comfort', 'Toyota', 'Camry', 2021, 'Black', 11, 'English, Yoruba'),
    ('Chidi', 'Okafor', 'Lagos', 'economy', 'Toyota', 'Corolla', 2018, 'Silver', 7, 'English, Igbo, Pidgin'),
    ('Musa', 'Bello', 'Lagos', 'economy', 'Honda', 'Accord', 2017, 'Grey', 9, 'English, Hausa'),
    ('Tunde', 'Bakare', 'Lagos', 'comfort', 'Lexus', 'ES 350', 2020, 'White', 14, 'English, Yoruba'),
    ('Efe', 'Okoro', 'Lagos', 'economy', 'Hyundai', 'Elantra', 2019, 'Blue', 5, 'English, Pidgin'),
    ('Sola', 'Ogunleye', 'Lagos', 'economy', 'Toyota', 'Corolla', 2016, 'White', 8, 'English, Yoruba'),
    ('Ifeanyi', 'Eze', 'Lagos', 'comfort', 'Toyota', 'Highlander', 2020, 'Black', 12, 'English, Igbo'),
    ('Bayo', 'Adeyemi', 'Lagos', 'economy', 'Kia', 'Rio', 2018, 'Red', 4, 'English, Yoruba'),
    ('Peter', 'Akpan', 'Lagos', 'economy', 'Toyota', 'Camry', 2015, 'Gold', 10, 'English, Ibibio'),
    ('Yemi', 'Alade', 'Lagos', 'comfort', 'Mercedes-Benz', 'C 300', 2019, 'Grey', 9, 'English, Yoruba, French'),
    ('Abdullahi', 'Sani', 'Abuja', 'economy', 'Toyota', 'Corolla', 2019, 'White', 6, 'English, Hausa'),
    ('Grace', 'Nwosu', 'Abuja', 'comfort', 'Toyota', 'Camry', 2022, 'Black', 8, 'English, Igbo'),
    ('Ibrahim', 'Musa', 'Abuja', 'economy', 'Honda', 'Civic', 2018, 'Silver', 7, 'English, Hausa'),
    ('Ada', 'Obi', 'Abuja', 'comfort', 'Lexus', 'RX 350', 2019, 'White', 10, 'English, Igbo'),
    ('Danjuma', 'Yakubu', 'Abuja', 'economy', 'Hyundai', 'Accent', 2017, 'Grey', 5, 'English, Hausa'),
    ('Fatima', 'Abubakar', 'Abuja', 'economy', 'Toyota', 'Corolla', 2020, 'Blue', 6, 'English, Hausa, Arabic'),
]
COMMENTS = ['Very professional and calm in traffic.', 'Car was spotless and cold AC. Thank you!',
            'Knew a shortcut around the Lekki toll, saved us time.', 'Arrived early and helped with my bags.',
            'Smooth ride, would book again.', 'Friendly and safe driver.']
COMPLIMENTS = ['Great driving', 'Clean car', 'On time', 'Friendly', 'Knew the way']


def _straight(lat1, lng1, lat2, lng2):
    d = services.haversine_m(lat1, lng1, lat2, lng2) * 1.35
    return [[lat1, lng1], [lat2, lng2]], int(d), int(d / 24000 * 3600) + 60


def build(rng, password, domain, buyers):
    drivers = []
    for n, (first, last, city, cls, make, model, year, colour, years, langs) in enumerate(DRIVERS):
        local = 'driver' if n == 0 else f'{first.lower()}.{last.lower()}'
        user = User.objects.create_user(email=f'{local}@{domain}', password=password, first_name=first, last_name=last, username=local)
        user.date_joined = timezone.now() - timedelta(days=rng.randint(120, 800))
        user.save(update_fields=['date_joined'])
        EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
        p = user.profile
        p.city, p.is_pilot_approved = city, True
        p.phone = f'+234 80{rng.randint(1, 9)} {rng.randint(100, 999)} {rng.randint(1000, 9999)}'
        p.save()
        _, lat, lng = rng.choice(SPOTS[city])
        drivers.append(DriverProfile.objects.create(
            user=user, city=city, vehicle_class=cls, vehicle_make=make, vehicle_model=model, vehicle_year=year,
            vehicle_color=colour, years_experience=years, languages=langs,
            plate_number=f'{"LND" if city == "Lagos" else "ABJ"}-{rng.randint(100, 999)}-{rng.choice("ABCDEFGHJKLMNPRSTXY")}{rng.choice("ABCDEFGHJKLMNPRSTXY")}',
            license_number=f'{"LAG" if city == "Lagos" else "FCT"}{rng.randint(10000, 99999)}AA{rng.randint(10, 99)}',
            license_verified=True, offers_chauffeur=rng.random() < .75,
            hourly_rate=Decimal(rng.choice([4000, 4500, 5000, 6000])) + (Decimal('1500') if cls == 'comfort' else 0),
            bio=f'{years} years behind the wheel in {city}. Safe, punctual and discreet.',
            is_online=n != 7, is_simulated=True, lat=lat + rng.uniform(-.012, .012), lng=lng + rng.uniform(-.012, .012),
            heading=rng.randint(0, 359), location_updated_at=None,
        ))

    # Trip history with ratings so drivers have real-looking reputations
    riders = buyers
    for d in drivers:
        for _ in range(rng.randint(4, 9)):
            rider = rng.choice(riders)
            a, b = rng.sample(PLACES[d.city], 2)
            coords, dist, dur = _straight(a[1], a[2], b[1], b[2])
            when = timezone.now() - timedelta(days=rng.randint(1, 120), hours=rng.randint(0, 12))
            fare = services.ride_fare(d.vehicle_class, dist, dur)
            t = Trip.objects.create(rider=rider, driver=d, kind='ride', vehicle_class=d.vehicle_class,
                                    pickup_address=a[0], pickup_lat=a[1], pickup_lng=a[2], dropoff_address=b[0],
                                    dropoff_lat=b[1], dropoff_lng=b[2], route=coords, distance_m=dist, duration_s=dur,
                                    fare_estimate=fare, fare_final=fare, status='completed', simulated=True)
            Trip.objects.filter(pk=t.pk).update(created_at=when, accepted_at=when, started_at=when + timedelta(minutes=8),
                                                completed_at=when + timedelta(seconds=dur + 480))
            if rng.random() < .8:
                stars = rng.choice([5, 5, 5, 4, 4, 3])
                TripRating.objects.create(trip=t, stars=stars, compliments=', '.join(rng.sample(COMPLIMENTS, rng.randint(0, 2))),
                                          comment=rng.choice(COMMENTS) if rng.random() < .5 else '')
        d.trips_count = d.trips.filter(status='completed').count() + rng.randint(40, 600)
        d.save(update_fields=['trips_count'])
        d.refresh_rating()

    # The demo driver (driver@) has already done a few trips today
    kunle = drivers[0]
    for hours_ago in (5, 3, 1):
        a, b = rng.sample(PLACES['Lagos'], 2)
        coords, dist, dur = _straight(a[1], a[2], b[1], b[2])
        when = timezone.now() - timedelta(hours=hours_ago)
        fare = services.ride_fare(kunle.vehicle_class, dist, dur)
        t = Trip.objects.create(rider=rng.choice(riders), driver=kunle, kind='ride', vehicle_class=kunle.vehicle_class,
                                pickup_address=a[0], pickup_lat=a[1], pickup_lng=a[2], dropoff_address=b[0],
                                dropoff_lat=b[1], dropoff_lng=b[2], route=coords, distance_m=dist, duration_s=dur,
                                fare_estimate=fare, fare_final=fare, status='completed', simulated=True)
        Trip.objects.filter(pk=t.pk).update(created_at=when, accepted_at=when, started_at=when + timedelta(minutes=6),
                                            completed_at=when + timedelta(seconds=dur + 360))

    # An upcoming chauffeur booking for the demo buyer
    buyer = buyers[0]
    chauffeur = next(d for d in drivers if d.offers_chauffeur and d.city == 'Lagos')
    when = (timezone.localtime() + timedelta(days=2)).replace(hour=9, minute=0, second=0, microsecond=0)
    t = Trip.objects.create(rider=buyer, driver=chauffeur, kind='chauffeur', pickup_address='Lekki Phase 1, Lagos',
                            pickup_lat=6.4478, pickup_lng=3.4723, hours=8, scheduled_for=when,
                            fare_estimate=services.chauffeur_fare(8, chauffeur.hourly_rate), status='accepted',
                            accepted_at=timezone.now(), simulated=True, notes='Errands around Lekki and VI, then the airport.')
    return drivers
