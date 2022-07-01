import json

from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from py_crypto_hd_wallet import HdWalletBipKeyTypes

from wallet.utils import send_erc_20_token, send_eth

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
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True)
    # erc20_address = models.TextField(unique=True)

    def __str__(self):
        return f'{self.user.username} | wallet'

    @property
    def erc20_address(self):
        try:
            return self.erc20address_set.filter(is_default=True).first().address
        except AttributeError:
            return None

    def get_private_key(self):
        from .utils import gen_user_addr

        address_obj = self.erc20address_set.filter(address=self.erc20_address).first()

        addr = gen_user_addr(address_id=address_obj.id)
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


class Erc20Address(models.Model):
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE)
    address = models.TextField()
    is_default = models.BooleanField(default=False)


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

    @transaction.atomic
    def deposit(self, value, transaction_type='deposit', description=None, trx_hash=None, create_transaction=True, is_internal=True):
        """Deposits a value to the wallet.
        Also creates a new transaction with the deposit
        value.
        """
        if create_transaction:
            self.wallet.transaction_set.create(
                # value=value,
                running_balance=self.balance + value,
                transaction_type=transaction_type,
                description=description,
                trx_hash=trx_hash,
                status='complete'
            )
        else:
            if trx_hash is not None:
                self.wallet.transaction_set.filter(trx_hash=trx_hash).update(
                    running_balance=self.balance + value
                )
        self.balance += value
        self.save()

    @transaction.atomic
    def withdraw(self, value, transaction_type='withdraw', description=None, trx_hash=None, status='pending', is_internal=False):
        """Withdraw's a value from the wallet.
        Also creates a new transaction with the withdraw
        value.
        Should the withdrawn balance is greater than the
        balance this wallet currently has, it raises an
        :mod:`InsufficientBalance` error. This exception
        inherits from :mod:`django.db.IntegrityError`. So
        that it automatically rolls-back during a
        transaction lifecycle.
        """
        from .utils import InsufficientBalance

        if value > self.balance:
            raise InsufficientBalance('This wallet has insufficient balance.')

        trx = Transaction.objects.create(
            wallet=self.wallet,
            # value=-value,
            running_balance=self.balance - value,
            transaction_type=transaction_type,
            description=description,
            trx_hash=trx_hash,
            status=status,
            is_internal=is_internal
        )
        self.balance -= value
        self.save()
        return trx

    @transaction.atomic
    def transfer(self, wallet_balance, value, transaction_type='transfer',
                 description=None, trx_hash=None, create_transaction=False, is_internal=True, status='complete'):
        """Transfers an value to another wallet.
        Uses `deposit` and `withdraw` internally.
        """
        trx = self.withdraw(value, transaction_type, description, trx_hash, status='complete')
        wallet_balance.deposit(value, transaction_type, description, trx_hash, create_transaction=create_transaction, is_internal=is_internal)
        return trx

    @transaction.atomic
    def external_transfer(self, value, to_address, transaction_type='withdraw', description=None, trx_hash=None, is_internal=False):
        withdraw_trx = self.withdraw(value, transaction_type, description, trx_hash, is_internal=False)
        if self.coin.is_token:

            tx_hash = send_erc_20_token(
                        self.coin.contract_address, json.dumps(self.coin.abi),
                        self.wallet, to_address, value
                    )
            withdraw_trx.contract_address = self.coin.contract_address
        else:
            tx_hash = send_eth(self.wallet, to_address, value)

        withdraw_trx.trx_hash = tx_hash
        withdraw_trx.save()
        return withdraw_trx


class Transaction(models.Model):
    DEPOSIT = 'deposit'
    WITHDRAW = 'withdraw'
    TRANSFER = 'transfer'

    TRANSACTION_TYPES = (
        (DEPOSIT, DEPOSIT.title()),
        (WITHDRAW, WITHDRAW.title()),
        (TRANSFER, TRANSFER.title()),
    )

    PENDING = 'pending'
    COMPLETED = 'complete'

    STATUS_CHOICES = (
        (PENDING, PENDING.title()),
        (COMPLETED, COMPLETED.title()),
    )
    NEW_HEADS = 'newHeads'
    LOGS = 'logs'
    SUBSCRIPTION_CHOICES = (
        (NEW_HEADS, NEW_HEADS),
        (LOGS, LOGS)
    )

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE)

    # The value of the wallet at the time of this transaction.
    running_balance = models.DecimalField(decimal_places=18, max_digits=36, null=True, blank=True)
    status = models.CharField(max_length=250, default=PENDING, choices=STATUS_CHOICES)
    is_internal = models.BooleanField(default=True)

    created_at = models.DateTimeField(default=timezone.now)
    transaction_type = models.CharField(max_length=250, choices=TRANSACTION_TYPES)
    description = models.TextField(blank=True, null=True)
    trx_hash = models.TextField(_("Transaction hash"), null=True)
    block_number = models.PositiveBigIntegerField(null=True, blank=True)
    contract_address = models.TextField(blank=True, null=True)
    subscription_type = models.CharField(max_length=200, choices=STATUS_CHOICES, blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
