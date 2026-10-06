from django import forms

from ..models import Application


class SellerApplicationForm(forms.ModelForm):
    """Application to become a verified dealer (verified sellers' listings go live instantly)."""

    class Meta:
        model = Application
        fields = ['full_name', 'phone', 'company_name', 'address', 'id_type', 'id_number', 'experience_years', 'additional_info', 'documents']
        labels = {
            'company_name': 'Business name (optional for private sellers)',
            'id_type': 'ID type',
            'id_number': 'ID / CAC number',
            'experience_years': 'Years selling cars',
            'additional_info': 'Anything else we should know?',
            'documents': 'Supporting document (CAC certificate or ID)',
        }
        widgets = {
            'address': forms.Textarea(attrs={'rows': 2}),
            'additional_info': forms.Textarea(attrs={'rows': 3}),
            'id_type': forms.Select(choices=[('', 'Select…'), ('nin', 'NIN slip'), ('passport', 'International passport'),
                                             ('drivers_licence', "Driver's licence"), ('cac', 'CAC registration')]),
        }

    def clean_documents(self):
        doc = self.cleaned_data.get('documents')
        if doc and hasattr(doc, 'size') and doc.size > 8 * 1024 * 1024:
            raise forms.ValidationError('Documents must be under 8 MB.')
        return doc
