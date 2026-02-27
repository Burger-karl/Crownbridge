
from django import forms
from .models import KYCVerification

FILE_SIZE_LIMIT_MB = 5


class KYCForm(forms.ModelForm):
    full_name = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Enter your full legal name",
        }),
    )

    class Meta:
        model = KYCVerification
        fields = ["full_name", "id_document", "selfie"]
        widgets = {
            "id_document": forms.ClearableFileInput(attrs={
                "class": "form-control form-control-lg",
                "accept": "image/*,application/pdf",
            }),
            "selfie": forms.ClearableFileInput(attrs={
                "class": "form-control form-control-lg",
                "accept": "image/*",
            }),
        }

    def clean_id_document(self):
        doc = self.cleaned_data.get("id_document")
        if doc and hasattr(doc, "size"):
            if doc.size > FILE_SIZE_LIMIT_MB * 1024 * 1024:
                raise forms.ValidationError(f"ID document must be smaller than {FILE_SIZE_LIMIT_MB} MB.")
        return doc

    def clean_selfie(self):
        selfie = self.cleaned_data.get("selfie")
        if selfie and hasattr(selfie, "size"):
            if selfie.size > FILE_SIZE_LIMIT_MB * 1024 * 1024:
                raise forms.ValidationError(f"Selfie must be smaller than {FILE_SIZE_LIMIT_MB} MB.")
        return selfie


class KYCRejectForm(forms.Form):
    rejection_reason = forms.CharField(
        label="Rejection reason (shown to user)",
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 3,
            "placeholder": "e.g. ID document is blurry, please resubmit a clearer photo.",
        }),
        required=True,
        max_length=500,
    )
    admin_notes = forms.CharField(
        label="Internal notes (optional, not shown to user)",
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 2,
            "placeholder": "Optional internal notes…",
        }),
        required=False,
        max_length=1000,
    )