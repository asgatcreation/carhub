"""DriverZone: book a ride (driver's car) or hire a chauffeur (your car), tracked live on a map.

Drivers are approved through the staff console. Online drivers share their position; the rider
watches the car approach and follow the route. Trips assigned to demo drivers (who aren't really
driving) are simulated along the real road route so the live map still works end to end.
"""
import secrets
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone


class DriverProfile(models.Model):
    CLASS_CHOICES = [('economy', 'Economy'), ('comfort', 'Comfort')]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='driver_profile')
    bio = models.TextField(blank=True)
    languages = models.CharField(max_length=120, default='English')
    years_experience = models.PositiveSmallIntegerField(default=0)
    license_number = models.CharField(max_length=40)
    license_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, help_text='Staff can suspend a driver')
    city = models.CharField(max_length=60, default='Lagos')

    vehicle_make = models.CharField(max_length=40, blank=True)
    vehicle_model = models.CharField(max_length=60, blank=True)
    vehicle_year = models.PositiveSmallIntegerField(null=True, blank=True)
    vehicle_color = models.CharField(max_length=30, blank=True)
    plate_number = models.CharField(max_length=20, blank=True)
    vehicle_class = models.CharField(max_length=10, choices=CLASS_CHOICES, default='economy')
    offers_chauffeur = models.BooleanField(default=True, help_text='Will drive the customer\'s own car')
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('4500'))

    is_online = models.BooleanField(default=False)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    heading = models.FloatField(default=0)
    location_updated_at = models.DateTimeField(null=True, blank=True)
    is_simulated = models.BooleanField(default=False, help_text='Demo driver: movement is simulated along routes')

    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    rating_count = models.PositiveIntegerField(default=0)
    trips_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-rating_avg']

    def __str__(self):
        return self.user.get_full_name() or self.user.email

    def get_absolute_url(self):
        return reverse('driverzone:driver', args=[self.pk])

    @property
    def name(self):
        return self.user.first_name or self.user.get_full_name() or 'Your driver'

    @property
    def vehicle(self):
        return ' '.join(str(x) for x in (self.vehicle_color, self.vehicle_make, self.vehicle_model) if x)

    @property
    def is_live(self):
        """Has the driver's phone reported a position in the last minute?"""
        return bool(self.location_updated_at and (timezone.now() - self.location_updated_at).total_seconds() < 60)

    def refresh_rating(self):
        from django.db.models import Avg, Count
        agg = TripRating.objects.filter(trip__driver=self).aggregate(avg=Avg('stars'), n=Count('id'))
        self.rating_avg, self.rating_count = agg['avg'], agg['n']
        self.save(update_fields=['rating_avg', 'rating_count'])


def _trip_number():
    return 'DZ-' + secrets.token_hex(3).upper()


class Trip(models.Model):
    KIND_CHOICES = [('ride', 'Ride'), ('chauffeur', 'Chauffeur (your car)')]
    STATUS_CHOICES = [
        ('requested', 'Finding a driver'), ('accepted', 'Driver on the way'), ('arrived', 'Driver has arrived'),
        ('in_progress', 'On trip'), ('completed', 'Completed'), ('cancelled', 'Cancelled'), ('no_driver', 'No driver found'),
    ]
    PAYMENT_CHOICES = [('cash', 'Cash or transfer to the driver'), ('demo', 'Demo payment')]
    ACTIVE = ('requested', 'accepted', 'arrived', 'in_progress')

    number = models.CharField(max_length=16, unique=True, default=_trip_number, editable=False)
    rider = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='trips')
    driver = models.ForeignKey(DriverProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='trips')
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default='ride')
    vehicle_class = models.CharField(max_length=10, choices=DriverProfile.CLASS_CHOICES, default='economy')

    pickup_address = models.CharField(max_length=255)
    pickup_lat = models.FloatField()
    pickup_lng = models.FloatField()
    dropoff_address = models.CharField(max_length=255, blank=True)
    dropoff_lat = models.FloatField(null=True, blank=True)
    dropoff_lng = models.FloatField(null=True, blank=True)
    route = models.JSONField(default=list, blank=True, help_text='[[lat, lng], …] along the road')
    approach_route = models.JSONField(default=list, blank=True, help_text='Driver start → pickup')
    distance_m = models.PositiveIntegerField(default=0)
    duration_s = models.PositiveIntegerField(default=0)
    approach_s = models.PositiveIntegerField(default=0)
    hours = models.PositiveSmallIntegerField(default=0, help_text='Chauffeur bookings')
    scheduled_for = models.DateTimeField(null=True, blank=True)
    notes = models.CharField(max_length=300, blank=True)

    surge = models.DecimalField(max_digits=3, decimal_places=2, default=Decimal('1.00'))
    fare_estimate = models.DecimalField(max_digits=10, decimal_places=2)
    fare_final = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default='cash')

    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='requested', db_index=True)
    simulated = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    arrived_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.CharField(max_length=10, blank=True)
    cancel_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.number

    def get_absolute_url(self):
        return reverse('driverzone:trip', args=[self.number])

    @property
    def is_active(self):
        return self.status in self.ACTIVE

    @property
    def fare(self):
        return self.fare_final or self.fare_estimate

    @property
    def distance_km(self):
        return round(self.distance_m / 1000, 1)

    @property
    def duration_min(self):
        return max(1, round(self.duration_s / 60))

    def steps(self):
        """Progress for the status tracker: (label, state)."""
        order = ['requested', 'accepted', 'arrived', 'in_progress', 'completed']
        labels = ['Requested', 'Driver on the way', 'Arrived', 'On trip', 'Completed']
        if self.status in ('cancelled', 'no_driver'):
            return [(labels[0], 'done'), (self.get_status_display(), 'cancelled')]
        i = order.index(self.status)
        return [(label, 'done' if n < i or self.status == 'completed' else 'current' if n == i else 'todo')
                for n, label in enumerate(labels)]


class TripRating(models.Model):
    trip = models.OneToOneField(Trip, on_delete=models.CASCADE, related_name='rating')
    stars = models.PositiveSmallIntegerField()
    compliments = models.CharField(max_length=200, blank=True)
    comment = models.CharField(max_length=500, blank=True)
    tip = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0'))
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.stars}★ for {self.trip}'
