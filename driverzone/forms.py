from datetime import timedelta

from django import forms
from django.utils import timezone

from users.forms.application import SellerApplicationForm

from .models import Trip

NIGERIA = {'lat': (4.0, 14.0), 'lng': (2.5, 14.9)}


def _in_nigeria(lat, lng):
    return NIGERIA['lat'][0] <= lat <= NIGERIA['lat'][1] and NIGERIA['lng'][0] <= lng <= NIGERIA['lng'][1]


class BookingForm(forms.Form):
    OPTIONS = [('economy', 'Economy'), ('comfort', 'Comfort'), ('chauffeur', 'Chauffeur')]
    option = forms.ChoiceField(choices=OPTIONS)
    pickup_address = forms.CharField(max_length=255)
    pickup_lat = forms.FloatField()
    pickup_lng = forms.FloatField()
    dropoff_address = forms.CharField(max_length=255, required=False)
    dropoff_lat = forms.FloatField(required=False)
    dropoff_lng = forms.FloatField(required=False)
    hours = forms.IntegerField(required=False, min_value=3, max_value=12)
    scheduled_for = forms.DateTimeField(required=False, input_formats=['%Y-%m-%dT%H:%M'])
    payment_method = forms.ChoiceField(choices=Trip.PAYMENT_CHOICES, initial='cash')
    notes = forms.CharField(max_length=300, required=False)

    def clean(self):
        d = super().clean()
        if d.get('pickup_lat') is not None and not _in_nigeria(d['pickup_lat'], d['pickup_lng']):
            raise forms.ValidationError('DriverZone currently operates in Nigeria only. Pick a pickup point in Nigeria.')
        has_drop = d.get('dropoff_lat') is not None and d.get('dropoff_lng') is not None
        if d.get('option') in ('economy', 'comfort') and not has_drop:
            raise forms.ValidationError('Where are you going? Choose a destination for your ride.')
        if has_drop and not _in_nigeria(d['dropoff_lat'], d['dropoff_lng']):
            raise forms.ValidationError('Choose a destination in Nigeria.')
        if not has_drop:
            d['dropoff_lat'] = d['dropoff_lng'] = None
        when = d.get('scheduled_for')
        if when:
            when = timezone.make_aware(when) if timezone.is_naive(when) else when
            if when < timezone.now() + timedelta(minutes=30):
                raise forms.ValidationError('Scheduled trips must be at least 30 minutes from now, or choose "Now".')
            if when > timezone.now() + timedelta(days=30):
                raise forms.ValidationError('You can book up to 30 days ahead.')
            d['scheduled_for'] = when
        return d


class RatingForm(forms.Form):
    COMPLIMENTS = ['Great driving', 'Clean car', 'On time', 'Friendly', 'Knew the way', 'Great music']
    stars = forms.IntegerField(min_value=1, max_value=5)
    compliments = forms.MultipleChoiceField(choices=[(c, c) for c in COMPLIMENTS], required=False)
    comment = forms.CharField(max_length=500, required=False)
    tip = forms.DecimalField(required=False, min_value=0, max_value=20000, decimal_places=0)


class DriverApplicationForm(SellerApplicationForm):
    class Meta(SellerApplicationForm.Meta):
        fields = ['full_name', 'phone', 'address', 'id_number', 'experience_years', 'vehicle_details', 'additional_info', 'documents']
        labels = {**SellerApplicationForm.Meta.labels, 'id_number': "Driver's licence number",
                  'experience_years': 'Years of driving experience', 'address': 'Home address',
                  'vehicle_details': 'Your car (if you have one): year, make & model, colour, plate',
                  'documents': "Photo of your driver's licence",
                  'additional_info': 'Languages you speak, areas you know well, anything else'}
        widgets = {**SellerApplicationForm.Meta.widgets,
                   'vehicle_details': forms.TextInput(attrs={'placeholder': 'e.g. 2019 Toyota Corolla, grey, LND-482-KJ'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['id_number'].required = True
