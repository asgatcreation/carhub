from django import forms


class CustomSignupForm(forms.Form):
    """Extra fields on allauth's signup form (allauth handles email + password)."""
    first_name = forms.CharField(max_length=30, widget=forms.TextInput(attrs={'autocomplete': 'given-name', 'placeholder': 'Ada'}))
    last_name = forms.CharField(max_length=30, widget=forms.TextInput(attrs={'autocomplete': 'family-name', 'placeholder': 'Okafor'}))

    field_order = ['first_name', 'last_name', 'email', 'password1', 'password2']

    def signup(self, request, user):
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.save(update_fields=['first_name', 'last_name'])
