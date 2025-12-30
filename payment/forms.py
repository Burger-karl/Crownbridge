from django import forms
from decimal import Decimal
from .models import PlatformWallet
from django.contrib.auth import get_user_model

User = get_user_model()


# class WithdrawalRequestForm(forms.Form):
#     amount = forms.DecimalField(max_digits=32, decimal_places=8, min_value=Decimal('0.000001'))
#     to_address = forms.CharField(max_length=128)
#     chain = forms.ChoiceField(choices=[('ethereum', 'Ethereum'), ('bsc', 'BSC')])

class DepositForm(forms.Form):
    amount = forms.DecimalField(max_digits=32, decimal_places=8, min_value=Decimal('0.000001'))
    chain = forms.ChoiceField(choices=PlatformWallet.CHAIN_CHOICES)

class TransferForm(forms.Form):
    recipient = forms.CharField(max_length=254, help_text="Recipient's email or username")
    amount = forms.DecimalField(max_digits=32, decimal_places=8, min_value=Decimal('0.000001'))
    note = forms.CharField(max_length=255, required=False)

class P2PTransferForm(forms.Form):
    receiver_email = forms.EmailField(
        label="Receiver Email",
        widget=forms.EmailInput(attrs={
            "class": "form-control",
            "placeholder": "Enter receiver email"
        })
    )

    amount = forms.DecimalField(
        max_digits=18,
        decimal_places=8,
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "placeholder": "Enter amount",
            "step": "0.00000001"
        })
    )

    chain = forms.ChoiceField(
        choices=[
            ("tron", "TRON"),
            ("usdt_trc20", "USDT (TRC20)"),
            ("ethereum", "Ethereum (ETH)"),
            ("usdt_erc20", "USDT (ERC20)"),
            ("bitcoin", "Bitcoin (BTC)"),
        ],
        widget=forms.Select(attrs={"class": "form-select"})
    )
    



from django import forms
from .models import WithdrawalRequest

class WithdrawalRequestForm(forms.ModelForm):

    to_address = forms.ChoiceField(
        required=True,
        widget=forms.Select(attrs={'class': 'form-select form-select-lg'})
    )

    class Meta:
        model = WithdrawalRequest
        fields = ['amount', 'chain', 'to_address']
        widgets = {
            'amount': forms.NumberInput(attrs={'class': 'form-control form-control-lg'}),
            'chain': forms.Select(attrs={'class': 'form-select form-select-lg'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user')  # get logged-in user
        super().__init__(*args, **kwargs)

        profile = getattr(user, "profile", None)
        choices = []

        if profile:
            if profile.bitcoin_id:
                choices.append(("bitcoin:" + profile.bitcoin_id, f"BTC — {profile.bitcoin_id}"))
            if profile.ethereum_id:
                choices.append(("ethereum:" + profile.ethereum_id, f"ETH — {profile.ethereum_id}"))
            if profile.usdt_trc20_id:
                choices.append(("usdt_trc20:" + profile.usdt_trc20_id, f"USDT (TRC20) — {profile.usdt_trc20_id}"))
            if profile.tron_id:
                choices.append(("tron:" + profile.tron_id, f"TRON — {profile.tron_id}"))
            if profile.bep20_id:
                choices.append(("bep20:" + profile.bep20_id, f"BEP20 — {profile.bep20_id}"))

        # fallback if no wallet
        if not choices:
            choices = [("", "No wallet IDs found — update profile!")]

        self.fields['to_address'].choices = choices