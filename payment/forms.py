from django import forms
from decimal import Decimal
from .models import PlatformWallet
from django.contrib.auth import get_user_model

User = get_user_model()


class WithdrawalRequestForm(forms.Form):
    amount = forms.DecimalField(max_digits=32, decimal_places=8, min_value=Decimal('0.000001'))
    to_address = forms.CharField(max_length=128)
    chain = forms.ChoiceField(choices=[('ethereum', 'Ethereum'), ('bsc', 'BSC')])

class DepositForm(forms.Form):
    amount = forms.DecimalField(max_digits=32, decimal_places=8, min_value=Decimal('0.000001'))
    chain = forms.ChoiceField(choices=PlatformWallet.CHAIN_CHOICES)

class TransferForm(forms.Form):
    recipient = forms.CharField(max_length=254, help_text="Recipient's email or username")
    amount = forms.DecimalField(max_digits=32, decimal_places=8, min_value=Decimal('0.000001'))
    note = forms.CharField(max_length=255, required=False)

class P2PTransferForm(forms.Form):
    receiver_email = forms.EmailField(label="Receiver Email")
    amount = forms.DecimalField(max_digits=12, decimal_places=2)
