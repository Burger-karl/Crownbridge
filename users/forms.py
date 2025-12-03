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

    bitcoin_id = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    ethereum_id = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    usdt_trc20_id = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    tron_id = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    bep20_id = forms.CharField(required=False, widget=forms.TextInput(attrs={"class": "form-control"}))


    class Meta:
        model = CustomUser
        fields = ("email", "full_name")
        widgets = {
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "full_name": forms.TextInput(attrs={"class": "form-control"}),
        }

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords do not match")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        user.is_verified = False

        if commit:
            user.save()
            # Save crypto IDs into Profile
            profile = user.profile
            profile.bitcoin_id = self.cleaned_data.get("bitcoin_id")
            profile.ethereum_id = self.cleaned_data.get("ethereum_id")
            profile.usdt_trc20_id = self.cleaned_data.get("usdt_trc20_id")
            profile.tron_id = self.cleaned_data.get("tron_id")
            profile.bep20_id = self.cleaned_data.get("bep20_id")
            profile.save()

        return user



class LoginForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email", widget=forms.EmailInput(attrs={"class": "form-control"})
    )
    password = forms.CharField(
        label="Password", widget=forms.PasswordInput(attrs={"class": "form-control"})
    )


class VerifyOTPForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={"class": "form-control"}))
    otp = forms.CharField(max_length=6, widget=forms.TextInput(attrs={"class": "form-control"}))



class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = [
            "firstname",
            "lastname",
            "country",
            "email",
            "phone",
            "avatar",
            "bitcoin_id",
            "ethereum_id",
            "usdt_trc20_id",
            "tron_id",
            "bep20_id",
        ]

        widgets = {
            "firstname": forms.TextInput(attrs={"class": "form-control"}),
            "lastname": forms.TextInput(attrs={"class": "form-control"}),
            "country": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "readonly": "readonly"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
            "avatar": forms.FileInput(attrs={"class": "form-control"}),
            "bitcoin_id": forms.TextInput(attrs={"class": "form-control"}),
            "ethereum_id": forms.TextInput(attrs={"class": "form-control"}),
            "usdt_trc20_id": forms.TextInput(attrs={"class": "form-control"}),
            "tron_id": forms.TextInput(attrs={"class": "form-control"}),
            "bep20_id": forms.TextInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add placeholder text automatically
        for field_name, field in self.fields.items():
            if field.widget.attrs.get("readonly"):
                continue  # Skip readonly fields like email

            field.widget.attrs.setdefault("placeholder", field.label)

        # Ensure file input is visible/styled
        if "avatar" in self.fields:
            self.fields["avatar"].widget.attrs["class"] = "form-control"
