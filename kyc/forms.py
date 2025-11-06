from django import forms
from .models import KYCVerification

class KYCForm(forms.ModelForm):
    class Meta:
        model = KYCVerification
        fields = ["id_document", "selfie"]
