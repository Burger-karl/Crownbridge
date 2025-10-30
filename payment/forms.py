from django import forms
from decimal import Decimal

class WithdrawalRequestForm(forms.Form):
    amount = forms.DecimalField(max_digits=32, decimal_places=8, min_value=Decimal('0.000001'))
    to_address = forms.CharField(max_length=128)
    chain = forms.ChoiceField(choices=[('ethereum', 'Ethereum'), ('bsc', 'BSC')])
