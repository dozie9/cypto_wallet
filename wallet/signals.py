from django.contrib.auth import get_user_model
from django.db.models.signals import pre_save, post_save
from django.dispatch.dispatcher import receiver
from py_crypto_hd_wallet import HdWalletBipKeyTypes

from .models import Wallet, Coin, WalletBalance, Transaction
from .utils import gen_user_addr, get_contract_obj

User = get_user_model()


@receiver(post_save, sender=User)
def user_post_save(sender, instance: User, created, **kwargs):
    if created:
        # create wallet for this user
        wallet = Wallet.objects.create(user=instance)

        # create wallet balance for each coin for this user
        for coin in Coin.objects.all():
            WalletBalance.objects.create(
                wallet=wallet,
                coin=coin,
            )

        # Generate erc20 address for user
        addr = gen_user_addr(user_id=instance.id)
        wallet.erc20_address = addr.GetKey(HdWalletBipKeyTypes.ADDRESS)
        wallet.save()


@receiver(post_save, sender=Transaction)
def transaction_post_save(sender, instance: Transaction, created, **kwargs):
    if created:
        if instance.contract_address:
            if not Coin.objects.filter(contract_address__iexact=instance.contract_address).exists():
                return None
            contract = get_contract_obj(instance.contract_address)
            symbol = contract.functions.symbol().call()
        else:
            symbol = 'ETH'
        instance.running_balance = instance.wallet.get_coin_balance(code=symbol)
        instance.save()
