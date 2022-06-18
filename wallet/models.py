from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from py_crypto_hd_wallet import HdWalletBipKeyTypes


User = get_user_model()


class Coin(models.Model):
    name = models.CharField(max_length=256)
    code = models.CharField(max_length=10)
    contract_address = models.TextField(blank=True, null=True)
    abi = models.JSONField(blank=True, null=True)
    is_token = models.BooleanField(default=True)

    def __str__(self):
        return self.code


class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True)
    erc20_address = models.TextField(unique=True)

    def __str__(self):
        return f'{self.user.username} | wallet'

    def get_private_key(self):
        from .utils import gen_user_addr

        addr = gen_user_addr(user_id=self.id)
        return addr.GetKey(HdWalletBipKeyTypes.RAW_PRIV)

    def get_balance(self):
        from .utils import get_eth_balance

        return get_eth_balance(self.erc20_address)

    def send_eth(self, to_wallet, amount):
        from .utils import send_eth

        return send_eth(self, to_wallet, amount)

    def get_coin_balance(self, code):
        wallet_bal_qs = self.walletbalance_set.filter(coin__code=code)
        if not wallet_bal_qs.exists():
            return 0
        return wallet_bal_qs.first().balance

    def get_wallet_balance_obj(self, code):
        return self.walletbalance_set.filter(coin__code=code).first()


class WalletBalance(models.Model):
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE)
    coin = models.ForeignKey(Coin, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=36, decimal_places=18, default=0)

    class Meta:
        unique_together = [
            ['wallet', 'coin']
        ]

    def __str__(self):
        return f'{self.wallet.user.username} | {self.coin.code}'


class Transaction(models.Model):
    DEPOSIT = 'deposit'
    WITHDRAW = 'withdraw'

    TRANSACTION_TYPES = (
        (DEPOSIT, DEPOSIT.title()),
        (WITHDRAW, WITHDRAW.title()),
    )

    PENDING = 'pending'
    COMPLETED = 'complete'

    STATUS_CHOICES = (
        (PENDING, PENDING.title()),
        (COMPLETED, COMPLETED.title()),
    )

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE)

    # The value of the wallet at the time of this transaction.
    running_balance = models.DecimalField(decimal_places=18, max_digits=36, null=True, blank=True)
    status = models.CharField(max_length=250, default=PENDING, choices=STATUS_CHOICES)

    created_at = models.DateTimeField(default=timezone.now)
    transaction_type = models.CharField(max_length=250, choices=TRANSACTION_TYPES)
    description = models.TextField(blank=True, null=True)
    trx_hash = models.TextField(_("Transaction hash"), null=True)
    block_number = models.PositiveBigIntegerField(null=True)
    contract_address = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
