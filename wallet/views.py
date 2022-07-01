import json
import traceback

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views.generic import FormView, ListView, DetailView, TemplateView
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.edit import FormMixin
from web3 import Web3

from .forms import SendEthForm
from .models import Transaction, Coin, Wallet, WalletBalance, Erc20Address
from .utils import send_eth, send_erc_20_token, get_token_balance, gen_trxn_id

w3 = Web3(Web3.HTTPProvider(settings.WEB3_URL))


class CoinListView(LoginRequiredMixin, ListView):
    model = Coin
    template_name = 'coin_list.html'


class SendEthView(LoginRequiredMixin, SingleObjectMixin, FormView):
    template_name = 'send-eth.html'
    form_class = SendEthForm
    slug_url_kwarg = 'coin'
    slug_field = 'code'
    model = Coin
    # pk_url_kwarg = 'code'
    # success_url = '/'

    def get_success_url(self):
        return self.request.path

    # def get_object(self, queryset=None):
    #     print(self.kwargs.get('code'))
    #     return self.model.objects.get(code=self.kwargs.get('code'))

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().post(request, *args, **kwargs)

    def get_form_kwargs(self):

        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        kwargs['coin'] = self.get_object()
        return kwargs

    def get_context_data(self, **kwargs):
        context = super(SendEthView, self).get_context_data(**kwargs)
        context.update({
            'balance': self.request.user.wallet.get_wallet_balance_obj(self.object.code).balance
        })
        # if self.object.is_token:
        #     context.update({
        #         'balance': get_token_balance(
        #             self.request.user.wallet.erc20_address, self.object
        #         )
        #     })
        # else:
        #     context.update({
        #         'balance': self.request.user.wallet.get_balance()
        #     })
        return context

    def form_valid(self, form):
        # self.object = self.get_object()
        res = super().form_valid(form)

        user_wallet = self.request.user.wallet

        to_addr = form.cleaned_data['to_address']
        amount = form.cleaned_data['amount']
        # trx_type = form.cleaned_data['transaction_type']
        coin_obj = self.get_object()
        wallet_balance = user_wallet.get_wallet_balance_obj(coin_obj.code)

        try:

            if Erc20Address.objects.filter(address__iexact=to_addr).exists():
                receiver = WalletBalance.objects.filter(wallet__erc20address__address__iexact=to_addr, coin=coin_obj).first()
                transaction = wallet_balance.transfer(
                    wallet_balance=receiver,
                    value=amount,
                    transaction_type='transfer',
                    description=None,
                    trx_hash=gen_trxn_id(),
                    create_transaction=True,
                    is_internal=True,
                    status='complete'
                )

                messages.success(
                    self.request,
                    f'Transaction has successful. '
                )
            else:
                transaction = wallet_balance.external_transfer(
                    value=amount, to_address=to_addr
                )

                messages.success(
                    self.request,
                    f'Transaction has successfully been sent to the blockchain. '
                    f'The Transaction hash is <a target="_blank" href="https://kovan.etherscan.io/tx/{transaction.trx_hash}">{transaction.trx_hash}</a>'
                )
        except ValueError as e:
            messages.error(self.request, 'Insufficient fund for gas.')
            return self.form_invalid(form)

        return res


class MyTransactionView(LoginRequiredMixin, ListView):
    model = Transaction
    template_name = 'my_transactions.html'

    def get_queryset(self):
        return Transaction.objects.filter(wallet=self.request.user.wallet)
