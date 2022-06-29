from django.contrib import admin

from wallet.models import Wallet, WalletBalance, Transaction, Coin, Erc20Address


@admin.register(Coin)
class CoinAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'contract_address']


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ['user', 'default_address']

    def default_address(self, obj):
        try:
            return obj.erc20_address
        except AttributeError:
            return None

    default_address.short_description = 'default address'
    default_address.admin_order_field = 'default_address'


@admin.register(WalletBalance)
class WalletBalanceAdmin(admin.ModelAdmin):
    list_display = ['wallet', 'coin', 'balance']


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['wallet', 'status', 'transaction_type', 'created_at']
    list_filter = ['status']


@admin.register(Erc20Address)
class Erc20AddressAdmin(admin.ModelAdmin):
    list_display = ['wallet', 'address', 'is_default']
    list_filter = ['is_default']
