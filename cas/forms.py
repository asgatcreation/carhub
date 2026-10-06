from django import forms
from .models import Accessory, AccessoryReview, Order

class AccessoryForm(forms.ModelForm):
    class Meta:
        model = Accessory
        fields = ['name', 'description', 'price', 'image', 'category', 'brand', 'in_stock']

class AccessoryReviewForm(forms.ModelForm):
    class Meta:
        model = AccessoryReview
        fields = ['rating', 'comment']

class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['quantity']
