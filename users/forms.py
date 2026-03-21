# users/forms.py
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import CustomUser, Profile


class RegisterForm(forms.ModelForm):
    password1 = forms.CharField(
        label="Password", widget=forms.PasswordInput(attrs={"class": "form-control"})
    )
    password2 = forms.CharField(
        label="Confirm Password", widget=forms.PasswordInput(attrs={"class": "form-control"})
    )

    bitcoin_id    = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Bitcoin wallet address (optional)"}))
    ethereum_id   = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ethereum wallet address (optional)"}))
    usdt_trc20_id = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "USDT TRC20 address (optional)"}))
    tron_id       = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Tron wallet address (optional)"}))
    bep20_id      = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "BEP20 wallet address (optional)"}))

    class Meta:
        model  = CustomUser
        fields = ("email", "full_name")
        widgets = {
            "email":     forms.EmailInput(attrs={"class": "form-control"}),
            "full_name": forms.TextInput(attrs={"class": "form-control"}),
        }

    def clean_password2(self):
        p1 = self.cleaned_data.get("password1")
        p2 = self.cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Passwords do not match")
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        user.is_active = True

        if commit:
            user.save()
            profile = user.profile
            profile.bitcoin_id    = self.cleaned_data.get("bitcoin_id", "")
            profile.ethereum_id   = self.cleaned_data.get("ethereum_id", "")
            profile.usdt_trc20_id = self.cleaned_data.get("usdt_trc20_id", "")
            profile.tron_id       = self.cleaned_data.get("tron_id", "")
            profile.bep20_id      = self.cleaned_data.get("bep20_id", "")
            profile.save()

        return user


class LoginForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email", widget=forms.EmailInput(attrs={"class": "form-control"})
    )
    password = forms.CharField(
        label="Password", widget=forms.PasswordInput(attrs={"class": "form-control"})
    )


class ProfileEditForm(forms.ModelForm):
    class Meta:
        model  = Profile
        fields = [
            "firstname", "lastname", "country", "email", "phone", "avatar",
            "bitcoin_id", "ethereum_id", "usdt_trc20_id", "tron_id", "bep20_id",
        ]
        widgets = {
            "firstname":    forms.TextInput(attrs={"class": "form-control", "placeholder": "First name"}),
            "lastname":     forms.TextInput(attrs={"class": "form-control", "placeholder": "Last name"}),
            "country":      forms.TextInput(attrs={"class": "form-control", "placeholder": "Country"}),
            "email":        forms.EmailInput(attrs={"class": "form-control", "readonly": "readonly"}),
            "phone":        forms.TextInput(attrs={"class": "form-control", "placeholder": "Phone number"}),
            "avatar":       forms.ClearableFileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "bitcoin_id":    forms.TextInput(attrs={"class": "form-control font-monospace", "placeholder": "e.g. bc1q..."}),
            "ethereum_id":   forms.TextInput(attrs={"class": "form-control font-monospace", "placeholder": "e.g. 0x..."}),
            "usdt_trc20_id": forms.TextInput(attrs={"class": "form-control font-monospace", "placeholder": "e.g. T..."}),
            "tron_id":       forms.TextInput(attrs={"class": "form-control font-monospace", "placeholder": "e.g. T..."}),
            "bep20_id":      forms.TextInput(attrs={"class": "form-control font-monospace", "placeholder": "e.g. 0x..."}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Pre-populate email from profile instance and keep it read-only
        if self.instance and self.instance.email:
            self.fields["email"].initial = self.instance.email

        self.fields["avatar"].required = False

        # Pre-populate wallet fields from profile instance
        # (ModelForm does this automatically, but being explicit ensures
        #  blank values don't overwrite existing ones on partial saves)
        wallet_fields = ["bitcoin_id", "ethereum_id", "usdt_trc20_id", "tron_id", "bep20_id"]
        for field in wallet_fields:
            self.fields[field].required = False
            if self.instance and getattr(self.instance, field, None):
                self.fields[field].initial = getattr(self.instance, field)