from django import forms
from django.conf import settings
from web3 import Web3

from .models import Coin


class SendEthForm(forms.Form):
    coin = forms.ModelChoiceField(queryset=Coin.objects.all())
    to_address = forms.CharField()
    amount = forms.DecimalField(max_digits=36, decimal_places=18)

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

    def clean_to_address(self):
        data = self.cleaned_data['to_address']
        w3 = Web3(Web3.HTTPProvider(settings.WEB3_URL))

        if not w3.isAddress(data):
            raise forms.ValidationError('This is not a valid Ethereum address.')
        return data

    def clean_amount(self):
        data = self.cleaned_data['amount']

        coin = self.cleaned_data['coin']

        if not coin.is_token:

            if self.request.user.wallet.get_balance() <= data:
                raise forms.ValidationError('Insufficient funds.')
        else:
            if self.request.user.wallet.get_token_balance() <= data:
                raise forms.ValidationError('Insufficient funds.')

        return data

