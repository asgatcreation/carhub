from django import forms
from django.conf import settings

from ..models import CustomUser, Profile


class AccountForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name']


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = [
            'profile_image', 'phone', 'whatsapp_number', 'city', 'bio',
            'company_name', 'company_logo', 'business_description', 'years_in_business', 'specialization',
            'chat_enabled',
        ]
        labels = {
            'profile_image': 'Profile photo',
            'whatsapp_number': 'WhatsApp number',
            'company_name': 'Dealership / business name',
            'business_description': 'About your business',
            'chat_enabled': 'Let buyers message me about my listings',
        }
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 3, 'placeholder': 'A short intro buyers will see on your seller page'}),
            'business_description': forms.Textarea(attrs={'rows': 4}),
            'profile_image': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
            'company_logo': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
        }

    def _check_image(self, field):
        image = self.cleaned_data.get(field)
        limit = settings.MAX_IMAGE_UPLOAD_MB * 1024 * 1024
        if image and hasattr(image, 'size') and image.size > limit:
            raise forms.ValidationError(f'Images must be under {settings.MAX_IMAGE_UPLOAD_MB} MB.')
        return image

    def clean_profile_image(self):
        return self._check_image('profile_image')

    def clean_company_logo(self):
        return self._check_image('company_logo')
