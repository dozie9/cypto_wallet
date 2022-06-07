from django.contrib import admin

from wallet.models import Wallet, Transaction, Coin


@admin.register(Coin)
class CoinAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'contract_address']


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ['user']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['wallet', 'status', 'transaction_type']
