from django import forms
from .models import KYCVerification

class KYCForm(forms.ModelForm):
    full_name = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'Enter your full name'})
    )

    class Meta:
        model = KYCVerification
        fields = ["full_name", "id_document", "selfie"]
        widgets = {
            'id_document': forms.ClearableFileInput(attrs={'class': 'form-control form-control-lg'}),
            'selfie': forms.ClearableFileInput(attrs={'class': 'form-control form-control-lg'}),
        }
