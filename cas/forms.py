import re
from datetime import date

from django import forms
from django.conf import settings

from cars.forms import MultipleImageField
from cars.models import STATE_CHOICES
from users.forms.application import SellerApplicationForm

from .models import Brand, Category, Order, Product

CURRENT_YEAR = date.today().year
KNOWN_MAKES = ['Land Rover', 'Mercedes-Benz', 'Mercedes', 'Alfa Romeo', 'Aston Martin', 'Rolls-Royce', 'Toyota', 'Lexus',
               'Honda', 'Acura', 'Nissan', 'Infiniti', 'Hyundai', 'Kia', 'Ford', 'Lincoln', 'Chevrolet', 'GMC', 'Jeep',
               'Dodge', 'BMW', 'Audi', 'Volkswagen', 'Porsche', 'Peugeot', 'Mitsubishi', 'Mazda', 'Subaru', 'Suzuki',
               'Volvo', 'Tesla', 'Range Rover', 'Innoson', 'Geely', 'Chery', 'Haval', 'Changan']
YEARS = re.compile(r'(?P<y1>(19|20)\d{2})\s*(?:[-–]\s*(?P<y2>(19|20)\d{2})|(?P<plus>\+))?\s*$')


def parse_fitment(line):
    """'Toyota Camry 2012-2017' -> ('Toyota', 'Camry', 2012, 2017). Model may be blank, years optional."""
    line = re.sub(r'\((all|all models)\)', '', line, flags=re.I).strip()
    y1 = y2 = None
    m = YEARS.search(line)
    if m:
        y1 = int(m['y1'])
        y2 = int(m['y2']) if m['y2'] else (None if m['plus'] else y1)
        line = line[:m.start()].strip()
    if not line or not line[0].isalpha():
        raise ValueError
    make = next((k for k in sorted(KNOWN_MAKES, key=len, reverse=True) if line.lower().startswith(k.lower())), None)
    if make:
        model = line[len(make):].strip()
    else:
        make, _, model = line.partition(' ')
        make = make.title()
    if y1 and y2 and y2 < y1:
        y1, y2 = y2, y1
    model = model.strip()
    return make, (model.title() if model.islower() else model), y1, y2


def _blank(choices, label):
    return [('', label)] + list(choices)


class GarageForm(forms.Form):
    make = forms.CharField(max_length=40)
    model = forms.CharField(max_length=60)
    year = forms.IntegerField(min_value=1990, max_value=CURRENT_YEAR + 1)


class ShopFilterForm(forms.Form):
    SORTS = [('popular', 'Most popular'), ('price_asc', 'Price: low to high'), ('price_desc', 'Price: high to low'),
             ('newest', 'Newest'), ('rating', 'Top rated')]
    q = forms.CharField(required=False)
    category = forms.CharField(required=False)
    brand = forms.CharField(required=False)
    part_type = forms.ChoiceField(required=False, choices=_blank(Product.PART_TYPES, 'Any type'))
    min_price = forms.IntegerField(required=False, min_value=0)
    max_price = forms.IntegerField(required=False, min_value=0)
    fits = forms.BooleanField(required=False)
    in_stock = forms.BooleanField(required=False)
    on_sale = forms.BooleanField(required=False)
    sort = forms.ChoiceField(required=False, choices=SORTS)


class CheckoutForm(forms.Form):
    full_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'autocomplete': 'name'}))
    phone = forms.CharField(max_length=30, widget=forms.TextInput(attrs={'autocomplete': 'tel', 'placeholder': '+234 803 000 0000'}))
    delivery_method = forms.ChoiceField(choices=Order.DELIVERY_CHOICES, widget=forms.RadioSelect, initial='delivery')
    state = forms.ChoiceField(choices=_blank(STATE_CHOICES, 'Select a state'))
    city = forms.CharField(max_length=80, widget=forms.TextInput(attrs={'autocomplete': 'address-level2', 'placeholder': 'e.g. Lekki'}))
    address = forms.CharField(max_length=255, required=False,
                              widget=forms.TextInput(attrs={'autocomplete': 'street-address', 'placeholder': 'House number, street, landmark'}))
    delivery_notes = forms.CharField(max_length=300, required=False, label='Note for the courier',
                                     widget=forms.TextInput(attrs={'placeholder': 'e.g. Call when you reach the gate'}))
    payment_method = forms.ChoiceField(choices=Order.PAYMENT_CHOICES, widget=forms.RadioSelect)

    def __init__(self, *args, methods=('paystack', 'demo', 'pod'), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['payment_method'].choices = [c for c in Order.PAYMENT_CHOICES if c[0] in methods]

    def clean_phone(self):
        phone = self.cleaned_data['phone']
        if len(re.sub(r'\D', '', phone)) < 10:
            raise forms.ValidationError('Enter a valid phone number.')
        return phone

    def clean(self):
        data = super().clean()
        if data.get('delivery_method') == 'delivery' and not data.get('address', '').strip():
            self.add_error('address', 'Enter the delivery address.')
        return data


class ProductForm(forms.ModelForm):
    brand_name = forms.CharField(max_length=80, required=False, label='Brand',
                                 help_text='e.g. Bosch, Michelin, Toyota Genuine. Leave blank for unbranded items.')
    photos = MultipleImageField(required=False, help_text='Up to 8 photos, 8 MB each. Clear photos on a plain background sell best.')
    specs_text = forms.CharField(required=False, label='Specifications', widget=forms.Textarea(attrs={'rows': 5,
                                 'placeholder': 'Size: 205/55 R16\nLoad index: 91\nSpeed rating: V'}),
                                 help_text='One per line, as "Name: value".')
    fitment_text = forms.CharField(required=False, label='Fits these cars', widget=forms.Textarea(attrs={'rows': 5,
                                   'placeholder': 'Toyota Camry 2012-2017\nToyota Corolla 2014+\nLexus (all models)'}),
                                   help_text='One per line: make, model and years (e.g. "Honda Accord 2013-2017"). '
                                             'Leave empty and tick "Fits any car" for universal items.')

    class Meta:
        model = Product
        fields = ['category', 'name', 'sku', 'short_description', 'description', 'price', 'compare_at_price', 'stock',
                  'part_type', 'warranty_months', 'dispatch_days', 'universal_fit', 'is_active']
        widgets = {'description': forms.Textarea(attrs={'rows': 6}),
                   'short_description': forms.TextInput(attrs={'placeholder': 'e.g. Long-life AGM battery, 70Ah'})}
        labels = {'price': 'Price (₦)', 'compare_at_price': 'Was (₦), optional', 'is_active': 'Show this product in the store',
                  'universal_fit': 'Fits any car', 'dispatch_days': 'Ships within (working days)'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = Category.objects.all()
        if self.instance.pk:
            self.fields['brand_name'].initial = self.instance.brand.name if self.instance.brand else ''
            self.fields['specs_text'].initial = '\n'.join(f'{s.name}: {s.value}' for s in self.instance.specs.all())
            self.fields['fitment_text'].initial = '\n'.join(
                f'{f.make} {f.model}{" " + str(f.year_from) if f.year_from else ""}'
                f'{"-" + str(f.year_to) if f.year_to and f.year_to != f.year_from else ("+" if f.year_from and not f.year_to else "")}'.strip()
                for f in self.instance.fitments.all())

    def clean_photos(self):
        photos = self.cleaned_data.get('photos') or []
        if len(photos) > 8:
            raise forms.ValidationError('You can upload up to 8 photos.')
        limit = settings.MAX_IMAGE_UPLOAD_MB * 1024 * 1024
        for photo in photos:
            if photo.size > limit:
                raise forms.ValidationError(f'{photo.name} is larger than {settings.MAX_IMAGE_UPLOAD_MB} MB.')
        if not self.instance.pk and not photos:
            raise forms.ValidationError('Add at least one photo of the actual product.')
        return photos

    def clean_specs_text(self):
        specs = []
        for line in self.cleaned_data.get('specs_text', '').splitlines():
            if not line.strip():
                continue
            if ':' not in line:
                raise forms.ValidationError(f'"{line.strip()}" needs a colon, like "Size: 205/55 R16".')
            name, value = line.split(':', 1)
            specs.append((name.strip()[:60], value.strip()[:120]))
        return specs

    def clean_fitment_text(self):
        fits = []
        for line in self.cleaned_data.get('fitment_text', '').splitlines():
            if not line.strip():
                continue
            try:
                fits.append(parse_fitment(line))
            except ValueError:
                raise forms.ValidationError(f'Could not read "{line.strip()}". Use e.g. "Toyota Camry 2012-2017".')
        return fits

    def clean(self):
        data = super().clean()
        price, was = data.get('price'), data.get('compare_at_price')
        if price is not None and price <= 0:
            self.add_error('price', 'Enter a price above ₦0.')
        if was and price and was <= price:
            self.add_error('compare_at_price', 'The "was" price must be higher than the price.')
        if not data.get('universal_fit') and not data.get('fitment_text'):
            self.add_error('fitment_text', 'List at least one car this fits, or tick "Fits any car".')
        return data

    def save_brand(self):
        name = self.cleaned_data.get('brand_name', '').strip()
        if not name:
            return None
        brand = Brand.objects.filter(name__iexact=name).first()
        return brand or Brand.objects.create(name=name)


class ReviewForm(forms.Form):
    rating = forms.IntegerField(min_value=1, max_value=5)
    title = forms.CharField(max_length=120, required=False)
    body = forms.CharField(min_length=10, max_length=2000, widget=forms.Textarea(attrs={'rows': 4}))


class VendorApplicationForm(SellerApplicationForm):
    class Meta(SellerApplicationForm.Meta):
        labels = {**SellerApplicationForm.Meta.labels,
                  'company_name': 'Shop or business name', 'experience_years': 'Years selling parts',
                  'address': 'Shop or warehouse address'}
