from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views.generic import FormView

from .forms import SendEthForm
from .models import Transaction, Coin
from .utils import send_eth, send_erc_20_token, get_token_balance


class SendEthView(LoginRequiredMixin, FormView):
    template_name = 'send-eth.html'
    form_class = SendEthForm
    # success_url = '/'

    def get_success_url(self):
        return self.request.path

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def form_valid(self, form):
        res = super().form_valid(form)

        user_wallet = self.request.user.wallet

        to_addr = form.cleaned_data['to_address']
        amount = form.cleaned_data['amount']
        coin_obj = form.cleaned_data['coin']

        if not coin_obj.is_token:
            running_balance = user_wallet.get_balance()
            tx_hash = send_eth(user_wallet, to_addr, amount)
        else:
            running_balance = get_token_balance(user_wallet.erc20_address, coin_obj)
            tx_hash = send_erc_20_token(
                coin_obj.contract_address, coin_obj.abi,
                user_wallet, to_addr, amount
            )

        Transaction.objects.create(
            wallet=user_wallet,
            running_balance=running_balance,
            trx_hash=tx_hash,
            transaction_type=Transaction.WITHDRAW
        )

        messages.success(
            self.request, f'Transaction has successfully been sent to the blockchain. The Transaction hash is {tx_hash}'
        )

        return res
