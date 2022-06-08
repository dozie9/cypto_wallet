import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render
from django.views.generic import FormView, ListView, DetailView, TemplateView
from django.views.generic.detail import SingleObjectMixin
from django.views.generic.edit import FormMixin

from .forms import SendEthForm
from .models import Transaction, Coin, Wallet
from .utils import send_eth, send_erc_20_token, get_token_balance


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
        if self.object.is_token:
            context.update({
                'balance': get_token_balance(
                    self.request.user.wallet.erc20_address, self.object
                )
            })
        else:
            context.update({
                'balance': self.request.user.wallet.get_balance()
            })
        return context

    def form_valid(self, form):
        # self.object = self.get_object()
        res = super().form_valid(form)

        user_wallet = self.request.user.wallet

        to_addr = form.cleaned_data['to_address']
        amount = form.cleaned_data['amount']
        coin_obj = self.get_object()

        if not coin_obj.is_token:
            running_balance = user_wallet.get_balance()
            try:
                tx_hash = send_eth(user_wallet, to_addr, amount)
            except ValueError as e:
                messages.error(self.request, 'Insufficient fund for gas.')
                return self.form_invalid(form)
        else:
            running_balance = get_token_balance(user_wallet.erc20_address, coin_obj)
            try:
                tx_hash = send_erc_20_token(
                    coin_obj.contract_address, json.dumps(coin_obj.abi),
                    user_wallet, to_addr, amount
                )
            except ValueError as e:
                messages.error(self.request, 'Insufficient fund for gas.')
                return self.form_invalid(form)

        Transaction.objects.create(
            wallet=user_wallet,
            running_balance=running_balance,
            trx_hash=tx_hash,
            transaction_type=Transaction.WITHDRAW
        )

        to_wallet_qs = Wallet.objects.filter(erc20_address__iexact=to_addr)

        # Checks if wallet is an internal wallet

        if to_wallet_qs.exists():
            Transaction.objects.create(
                wallet=to_wallet_qs.first(),
                running_balance=to_wallet_qs.first().get_balance() if not coin_obj.is_token else get_token_balance(to_wallet_qs.first().erc20_address, coin_obj),
                trx_hash=tx_hash,
                transaction_type=Transaction.DEPOSIT
            )

        messages.success(
            self.request, f'Transaction has successfully been sent to the blockchain. The Transaction hash is {tx_hash}'
        )

        return res


class MyTransactionView(LoginRequiredMixin, ListView):
    model = Transaction
    template_name = 'my_transactions.html'

    def get_queryset(self):
        return Transaction.objects.filter(wallet=self.request.user.wallet)
