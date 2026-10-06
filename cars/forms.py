from datetime import date

from django import forms
from django.conf import settings

from .models import (
    BODY_TYPE_CHOICES, CONDITION_CHOICES, ENGINE_CHOICES, STATE_CHOICES, TRANSMISSION_CHOICES, Car, Feature, Order,
)

SORT_CHOICES = [
    ('newest', 'Newest listings'),
    ('price_low', 'Price: low to high'),
    ('price_high', 'Price: high to low'),
    ('year_new', 'Year: newest first'),
    ('mileage_low', 'Mileage: lowest first'),
    ('popular', 'Most viewed'),
]


def _blank(choices, label='Any'):
    return [('', label)] + list(choices)


class SearchForm(forms.Form):
    q = forms.CharField(required=False, max_length=120)
    brand = forms.CharField(required=False, max_length=60)
    body = forms.ChoiceField(required=False, choices=_blank(BODY_TYPE_CHOICES))
    condition = forms.ChoiceField(required=False, choices=_blank(CONDITION_CHOICES))
    fuel = forms.ChoiceField(required=False, choices=_blank(ENGINE_CHOICES))
    transmission = forms.ChoiceField(required=False, choices=_blank(TRANSMISSION_CHOICES))
    state = forms.ChoiceField(required=False, choices=_blank(STATE_CHOICES, 'All of Nigeria'))
    min_price = forms.IntegerField(required=False, min_value=0)
    max_price = forms.IntegerField(required=False, min_value=0)
    min_year = forms.IntegerField(required=False, min_value=1980, max_value=2100)
    max_year = forms.IntegerField(required=False, min_value=1980, max_value=2100)
    max_mileage = forms.IntegerField(required=False, min_value=0)
    sort = forms.ChoiceField(required=False, choices=SORT_CHOICES)


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput(attrs={'accept': 'image/*', 'multiple': True}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        if isinstance(data, (list, tuple)):
            return [super(MultipleImageField, self).clean(d, initial) for d in data if d]
        return [super().clean(data, initial)] if data else []


class ListingForm(forms.ModelForm):
    photos = MultipleImageField(required=False, help_text='Up to 10 photos, 8 MB each. The first photo becomes the cover.')
    features = forms.ModelMultipleChoiceField(
        queryset=Feature.objects.all(), required=False, widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Car
        fields = [
            'brand', 'model', 'trim', 'year', 'price', 'body_type', 'condition', 'mileage',
            'engine_type', 'engine_size', 'transmission', 'drivetrain', 'exterior_color', 'interior_color',
            'num_seats', 'num_previous_owners', 'vin', 'duty_paid', 'location', 'state', 'description', 'features',
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Service history, accident history, extras, reason for selling…'}),
            'brand': forms.TextInput(attrs={'placeholder': 'e.g. Toyota', 'list': 'brand-options'}),
            'model': forms.TextInput(attrs={'placeholder': 'e.g. Camry'}),
            'trim': forms.TextInput(attrs={'placeholder': 'e.g. XSE V6'}),
            'engine_size': forms.TextInput(attrs={'placeholder': 'e.g. 2.5L 4-cyl'}),
            'location': forms.TextInput(attrs={'placeholder': 'e.g. Lekki Phase 1'}),
            'vin': forms.TextInput(attrs={'placeholder': '17 characters (optional)'}),
        }
        labels = {
            'num_seats': 'Seats', 'num_previous_owners': 'Previous owners', 'vin': 'VIN', 'duty_paid': 'Customs duty paid',
            'engine_type': 'Fuel', 'price': 'Asking price (₦)', 'mileage': 'Mileage (km)',
        }

    def clean_year(self):
        year = self.cleaned_data['year']
        if not 1980 <= year <= date.today().year + 1:
            raise forms.ValidationError('Enter a valid model year.')
        return year

    def clean_price(self):
        price = self.cleaned_data['price']
        if price < 100_000:
            raise forms.ValidationError('Enter the full price in Naira (e.g. 18500000).')
        return price

    def clean_photos(self):
        photos = self.cleaned_data.get('photos') or []
        if len(photos) > 10:
            raise forms.ValidationError('You can upload up to 10 photos.')
        limit = settings.MAX_IMAGE_UPLOAD_MB * 1024 * 1024
        for photo in photos:
            if photo.size > limit:
                raise forms.ValidationError(f'{photo.name} is larger than {settings.MAX_IMAGE_UPLOAD_MB} MB.')
        if not self.instance.pk and not photos:
            raise forms.ValidationError('Add at least one photo — listings with photos sell much faster.')
        return photos


class CheckoutDetailsForm(forms.Form):
    """Step 2 of checkout: contact + inspection preferences. Email is the account email and isn't editable."""
    full_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'autocomplete': 'name'}))
    phone = forms.CharField(max_length=30, widget=forms.TextInput(attrs={'placeholder': '+234 803 000 0000', 'autocomplete': 'tel'}))
    inspection_state = forms.ChoiceField(choices=_blank(STATE_CHOICES, 'Select a state'), label='Where will you inspect the car?')
    preferred_date = forms.DateField(label='Preferred inspection date', widget=forms.DateInput(attrs={'type': 'date'}))
    preferred_time = forms.ChoiceField(choices=Order.TIME_SLOTS, label='Preferred time', widget=forms.RadioSelect)
    notes = forms.CharField(required=False, label='Note for the seller',
                            widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'e.g. I will come with my mechanic'}))

    def clean_phone(self):
        phone = self.cleaned_data['phone']
        if len(''.join(ch for ch in phone if ch.isdigit())) < 10:
            raise forms.ValidationError('Enter a valid phone number.')
        return phone

    def clean_preferred_date(self):
        day = self.cleaned_data['preferred_date']
        today = date.today()
        if day <= today:
            raise forms.ValidationError('Choose a date from tomorrow onwards.')
        if (day - today).days > 30:
            raise forms.ValidationError('Reservations hold a car for up to 30 days — pick an earlier date.')
        return day


class PaymentForm(forms.Form):
    """Step 3 of checkout: confirm and choose how to pay the deposit."""
    method = forms.ChoiceField(choices=[('paystack', 'Card, bank transfer or USSD (Paystack)'), ('demo', 'Demo payment')],
                               widget=forms.RadioSelect)
    agree = forms.BooleanField(label='I understand the deposit is refundable if the car fails inspection or I cancel before it.')

    def __init__(self, *args, methods=('paystack', 'demo'), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['method'].choices = [c for c in self.fields['method'].choices if c[0] in methods]
        if len(self.fields['method'].choices) == 1:
            self.fields['method'].initial = self.fields['method'].choices[0][0]


class ScheduleInspectionForm(forms.Form):
    inspection_at = forms.DateTimeField(label='Inspection date & time',
                                        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
                                        input_formats=['%Y-%m-%dT%H:%M'])
    inspection_address = forms.CharField(max_length=255, label='Where')
    seller_note = forms.CharField(required=False, label='Note for the buyer', widget=forms.Textarea(attrs={'rows': 2}))


class CancelReservationForm(forms.Form):
    reason = forms.CharField(max_length=500, widget=forms.Textarea(attrs={'rows': 2}),
                             label='Why are you cancelling?')


class ReviewForm(forms.Form):
    rating = forms.IntegerField(min_value=1, max_value=5)
    communication = forms.IntegerField(min_value=1, max_value=5)
    professionalism = forms.IntegerField(min_value=1, max_value=5)
    punctuality = forms.IntegerField(min_value=1, max_value=5)
    condition = forms.IntegerField(min_value=1, max_value=5, label='Car as described')
    title = forms.CharField(max_length=120, required=False)
    body = forms.CharField(min_length=5, max_length=2000, widget=forms.Textarea(attrs={'rows': 4}))
