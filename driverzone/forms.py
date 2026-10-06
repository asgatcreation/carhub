from django import forms
from .models import Ride, DriverReview, Driver

class RideOrderForm(forms.ModelForm):
    class Meta:
        model = Ride
        fields = ['pickup', 'dropoff', 'order_type']

class DriverReviewForm(forms.ModelForm):
    class Meta:
        model = DriverReview
        fields = ['rating', 'comment']

class PilotApplicationForm(forms.ModelForm):
    class Meta:
        model = Driver
        fields = [
            'bio', 'photo', 'license_number', 'experience_years',
            'car_make', 'car_model', 'car_year', 'car_color', 'car_plate_number', 'car_image', 'car_description'
        ]
