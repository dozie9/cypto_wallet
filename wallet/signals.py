from django.contrib.auth import get_user_model
from django.db.models.signals import pre_save, post_save
from django.dispatch.dispatcher import receiver
from py_crypto_hd_wallet import HdWalletBipKeyTypes

from .models import Wallet
from .utils import gen_user_addr

User = get_user_model()


@receiver(post_save, sender=User)
def user_post_save(sender, instance: User, created, **kwargs):
    if created:
        wallet = Wallet.objects.create(user=instance)

        addr = gen_user_addr(user_id=instance.id)
        wallet.erc20_address = addr.GetKey(HdWalletBipKeyTypes.ADDRESS)
        wallet.save()
