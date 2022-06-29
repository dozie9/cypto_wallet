from django import forms
from django.conf import settings
from web3 import Web3

from .models import Coin, Transaction, Erc20Address
from .utils import get_token_balance


class SendEthForm(forms.Form):
    # coin = forms.ModelChoiceField(queryset=Coin.objects.all())
    to_address = forms.CharField()
    amount = forms.DecimalField(max_digits=36, decimal_places=18)
    transaction_type = forms.ChoiceField(
        choices=(
            (Transaction.TRANSFER, Transaction.TRANSFER.title()),
            (Transaction.WITHDRAW, Transaction.WITHDRAW.title()),
        )
    )

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        self.coin = kwargs.pop('coin', None)
        super().__init__(*args, **kwargs)

    def clean_to_address(self):
        data = self.cleaned_data['to_address']
        # transaction_type = self.cleaned_data['transaction_type']
        w3 = Web3(Web3.HTTPProvider(settings.WEB3_URL))

        if not w3.isAddress(data):
            raise forms.ValidationError('This is not a valid Ethereum address.')

        # if transaction_type == Transaction.TRANSFER and not Erc20Address.objects.filter(address__iexact=data).exists():
        #     raise forms.ValidationError('You can not transfer to this wallet, select withdraw instead.')

        return data

    def clean_amount(self):
        data = self.cleaned_data['amount']

        coin = self.coin

        if self.request.user.wallet.get_wallet_balance_obj(coin.code).balance < data:
            raise forms.ValidationError('Insufficient funds.')

        return data

    def clean(self):
        cleaned_data = super().clean()
        transaction_type = cleaned_data['transaction_type']
        to_address = cleaned_data['to_address']

        if transaction_type == Transaction.TRANSFER and not Erc20Address.objects.filter(address__iexact=to_address).exists():
            raise forms.ValidationError('You can not transfer to this wallet, select withdraw instead.')


