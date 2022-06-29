import binascii
import json
import traceback
import uuid
from decimal import Decimal

from django.conf import settings
from django.db import IntegrityError

from py_crypto_hd_wallet import HdWalletBipFactory, HdWalletSaver, HdWalletBip44Coins, HdWalletBipWordsNum, \
    HdWalletBipDataTypes

# Create a BIP-0044 Bitcoin wallet factory
# hd_wallet_fact = HdWalletBipFactory(HdWalletBip44Coins.BITCOIN)
# Create a BIP-0049 Litecoin wallet factory
from web3 import Web3, exceptions as w3_exceptions


# mnemonic = settings.MNEMONIC


def wallet_generator(addr_num=1, addr_off=0):
    hd_wallet_fact = HdWalletBipFactory(HdWalletBip44Coins.ETHEREUM)

    # hd_wallet = hd_wallet_fact.CreateFromMnemonic("my_wallet_name", settings.MNEMONIC)
    # priv_key = binascii.unhexlify(bytes(settings.MASTER_PRIVATE_KEY, 'utf-8'))
    hd_wallet = hd_wallet_fact.CreateFromExtendedKey("my_wallet_name", settings.MASTER_PRIVATE_KEY)
    if addr_off:
        hd_wallet.Generate(addr_num=addr_num, addr_off=addr_off)
        return hd_wallet
    hd_wallet.Generate(addr_num=addr_num)
    return hd_wallet


def gen_user_addr(address_id):
    address_index = address_id - 1
    hd_wallet = wallet_generator(addr_num=1, addr_off=address_index)
    addresses = hd_wallet.GetData(HdWalletBipDataTypes.ADDRESS)
    addr = addresses[0]

    return addr


def get_eth_balance(addr):
    w3 = Web3(Web3.HTTPProvider(settings.WEB3_URL))
    return w3.fromWei(w3.eth.get_balance(addr), 'ether')


def get_token_balance(addr, coin):
    w3 = Web3(Web3.HTTPProvider(settings.WEB3_URL))

    contract = w3.eth.contract(w3.toChecksumAddress(coin.contract_address), abi=coin.abi)
    decimals = contract.functions.decimals().call()
    DECIMALS = 10 ** decimals
    raw_balance = contract.functions.balanceOf(addr).call()
    return raw_balance / DECIMALS


def send_eth(from_wallet, to_wallet: str, amount):
    w3 = Web3(Web3.HTTPProvider(settings.WEB3_URL))

    nonce = w3.eth.getTransactionCount(from_wallet.erc20_address)
    # gas = w3.eth.gas_price
    base_fee_per_gas = w3.eth.get_block('latest')['baseFeePerGas']

    tx = dict(
        nonce=nonce,
        maxFeePerGas=base_fee_per_gas + w3.toWei(1, 'gwei'),
        maxPriorityFeePerGas=w3.toWei(1, 'gwei'),
        gas=21000,
        to=to_wallet,
        value=w3.toWei(amount, 'ether'),
        # data=b'',
        # type=2,  # (optional) the type is now implicitly set based on appropriate transaction params
        chainId=w3.eth.chain_id,
    )

    signed_txn = w3.eth.account.sign_transaction(
        tx, from_wallet.get_private_key()
    )

    tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)

    return w3.toHex(tx_hash)


def get_contract_obj(contract_address):
    from .models import Coin
    w3 = Web3(Web3.HTTPProvider(settings.WEB3_URL))

    coin = Coin.objects.get(contract_address__iexact=contract_address)

    contract = w3.eth.contract(w3.toChecksumAddress(contract_address), abi=coin.abi)
    # decimals = contract.functions.decimals().call()
    # DECIMALS = 10 ** decimals
    # amount_with_decimal = int(amount * DECIMALS)
    return contract


def create_user_wallet_balance(user):
    from .models import Coin, WalletBalance
    for coin in Coin.objects.all():
        WalletBalance.objects.get_or_create(
            wallet=user.wallet,
            coin=coin,
        )


def update_wallet_balances(user):
    from .models import Coin, WalletBalance
    for coin in Coin.objects.all():
        try:
            balance = WalletBalance.objects.get(
                wallet=user.wallet,
                coin=coin,
            )
            if coin.code == 'ETH':
                balance.balance = user.wallet.get_balance()
            else:
                balance.balance = get_token_balance(addr=user.wallet.erc20_address, coin=coin)
            balance.save()
            print(user.wallet, coin)
        except WalletBalance.DoesNotExist:
            pass


def decode_parameter_address(data):
    from eth_abi import decode_abi

    decodeABI = decode_abi(['address'], data)
    return decodeABI


def decode_parameter_amount(data):
    from eth_abi import decode_abi

    decodeABI = decode_abi(['uint256'], data)
    return decodeABI


def get_token_receiver_address(logs):
    w3 = Web3(Web3.HTTPProvider(settings.WEB3_URL))
    for log in logs:
        if w3.toHex(log['topics'][0]) == '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef':
            # print(w3.toHex(log['topics'][2]))
            return decode_parameter_address(log['topics'][2])[0]


def get_token_amount(logs):
    w3 = Web3(Web3.HTTPProvider(settings.WEB3_URL))
    for log in logs:
        if w3.toHex(log['topics'][0]) == '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef':
            # print(log['data'])
            return decode_parameter_amount(bytes.fromhex(log['data'][2:]))[0]


def get_to_address(tx):
    w3 = Web3(Web3.HTTPProvider(settings.WEB3_URL))
    if not is_contract_address(tx):
        return tx['to']

    try:
        tx_data = w3.eth.get_transaction_receipt(w3.toHex(tx['hash']))

    except KeyError:
        tx_data = tx

    to_address = get_token_receiver_address(tx_data['logs'])
    if to_address is not None:
        to_address = w3.toChecksumAddress(to_address)
    # raw_amount = get_token_amount(tx_data['logs'])
    return to_address, tx_data


def is_contract_address(tx):
    if tx['to'] is None:
        return False
    w3 = Web3(Web3.HTTPProvider(settings.WEB3_URL))
    return not w3.toHex(w3.eth.get_code(tx['to'])) == '0x'


def get_token_decimal_and_symbol(contract_address):
    # w3 = Web3(Web3.HTTPProvider(settings.WEB3_URL))
    contract = get_contract_obj(contract_address)
    decimals = contract.functions.decimals().call()
    symbol = contract.functions.symbol().call()
    DECIMALS = 10 ** decimals
    return DECIMALS, symbol


def check_for_ether_transactions(block, reorg):
    from wallet.models import Wallet, Transaction, Erc20Address
    address_qs = Erc20Address.objects.all()
    w3 = Web3(Web3.HTTPProvider(settings.WEB3_URL))

    # delete transaction if reorganisation
    if reorg:
        reorg_trx_qs = Transaction.objects.filter(block_number=block['number'])
        if reorg_trx_qs.exists():
            Transaction.objects.filter(block_number=block['number']).delete()

    wallet_address_set = set(Erc20Address.objects.all().values_list('address', flat=True))
    to_addresses = set([x['to'] for x in block['transactions']])

    common_addresses = wallet_address_set & to_addresses
    # print('common', common_addresses)

    if len(common_addresses) == 0:
        return None

    for trx in block['transactions']:
        if trx['to'] in common_addresses:

            # to_wallet_qs = wallets.filter(erc20_address__iexact=trx['to'])
            wallet = address_qs.filter(address__iexact=trx['to']).first().wallet

            Transaction.objects.create(
                running_balance=wallet.get_wallet_balance_obj('ETH').balance + w3.fromWei(trx['value'], 'ether'),
                wallet=wallet,
                trx_hash=w3.toHex(trx['hash']),
                transaction_type=Transaction.DEPOSIT,
                block_number=block['number'],
                is_internal=False
            )


def check_for_token_transactions(block, reorg):
    from wallet.models import Wallet, Transaction, Erc20Address
    address_qs = Erc20Address.objects.all()
    w3 = Web3(Web3.HTTPProvider(settings.WEB3_URL))
    try:

        # delete transaction if reorganisation
        if reorg:
            reorg_trx_qs = Transaction.objects.filter(block_number=block['number'])
            if reorg_trx_qs.exists():
                Transaction.objects.filter(block_number=block['number']).delete()

        wallet_address_set = set(Erc20Address.objects.all().values_list('address', flat=True))
        block_token_transactions = [trx for trx in block['transactions'] if is_contract_address(trx)]
        my_transactions_addresses = set([get_to_address(trx)[0] for trx in block_token_transactions])

        common_addresses = wallet_address_set & my_transactions_addresses
        # print('common', common_addresses)

        if len(common_addresses) == 0:
            return None

        my_transactions = [y[1] for trx in block_token_transactions if (y := get_to_address(trx))[0] in common_addresses]

        for trx in my_transactions:
            print(trx)

            to_address, trx_receipt = get_to_address(trx)
            raw_amount = get_token_amount(trx_receipt['logs'])
            DECIMAL, symbol = get_token_decimal_and_symbol(trx['to'])

            amount = Decimal(raw_amount / DECIMAL)

            wallet = address_qs.filter(address__iexact=to_address).first().wallet

            Transaction.objects.create(
                running_balance=wallet.get_wallet_balance_obj(symbol).balance + amount,
                wallet=wallet,
                trx_hash=w3.toHex(trx['transactionHash']),
                transaction_type=Transaction.DEPOSIT,
                block_number=block['number'],
                contract_address=trx['logs'][0]['address'],
                is_internal=False
            )
    except Exception:
        traceback.print_exc()


def send_erc_20_token(contract_address, abi, from_wallet, to_addr, amount):
    w3 = Web3(Web3.HTTPProvider(settings.WEB3_URL))

    contract = w3.eth.contract(w3.toChecksumAddress(contract_address), abi=abi)
    decimals = contract.functions.decimals().call()
    DECIMALS = 10 ** decimals
    amount_with_decimal = int(amount * DECIMALS)

    nonce = w3.eth.get_transaction_count(from_wallet.erc20_address)

    latest_block = w3.eth.get_block('latest')
    gas_limit = latest_block['gasLimit']
    base_fee_per_gas = latest_block['baseFeePerGas']
    tip = 1

    txn = contract.functions.transfer(to_addr, amount_with_decimal).buildTransaction({
        'chainId': w3.eth.chain_id,
        'gas': 80000,
        'maxFeePerGas': base_fee_per_gas + w3.toWei(tip, 'gwei'),
        'maxPriorityFeePerGas': w3.toWei(tip, 'gwei'),
        'nonce': nonce
    }) # .transact({'from': to_addr})
    signed_txn = w3.eth.account.sign_transaction(txn, private_key=from_wallet.get_private_key())
    w3.eth.send_raw_transaction(signed_txn.rawTransaction)

    return w3.toHex(w3.keccak(signed_txn.rawTransaction))


def update_transaction_status(block):
    from wallet.models import Transaction, Coin
    # transactions = Transaction.objects.all()
    w3 = Web3(Web3.HTTPProvider(settings.WEB3_URL))

    # for tx_hash in block['transactions']:
    transactions_qs = Transaction.objects.filter(status=Transaction.PENDING, is_internal=False)
    if not transactions_qs.exists():
        return None

    for transaction in transactions_qs:
        try:
            tx = w3.eth.get_transaction(transaction.trx_hash)
            # print(tx)
            number_of_confirmations = w3.eth.blockNumber - tx.blockNumber
            if number_of_confirmations > 4:
                transaction.status = Transaction.COMPLETED

                # Check if transaction for a token or eth
                if transaction.contract_address:
                    if not Coin.objects.filter(contract_address__iexact=transaction.contract_address).exists():
                        return None
                    DECIMALS, symbol = get_token_decimal_and_symbol(transaction.contract_address)

                    trx_receipt = w3.eth.get_transaction_receipt(transaction.trx_hash)
                    raw_amount = get_token_amount(trx_receipt['logs'])
                    wallet_balance = transaction.wallet.get_wallet_balance_obj(symbol)
                    wallet_balance.deposit(
                        value=Decimal(raw_amount / DECIMALS),
                        create_transaction=False,
                        trx_hash=w3.toHex(tx['hash'])
                    )
                    # wallet_balance.balance = raw_balance / DECIMALS
                    # wallet_balance.save()
                else:
                    wallet_balance = transaction.wallet.get_wallet_balance_obj('ETH')
                    wallet_balance.deposit(
                        value=w3.fromWei(tx['value'], 'ether'),
                        create_transaction=False,
                        trx_hash=w3.toHex(tx['hash'])
                    )
                    # wallet_balance.balance = transaction.wallet.get_balance()
                    # wallet_balance.save()

                transaction.save()
        except w3_exceptions.TransactionNotFound:
            pass
        except Exception:
            traceback.print_exc()


def gen_trxn_id():
    from wallet.models import Transaction

    t_id = uuid.uuid4()
    if not Transaction.objects.filter(trx_hash=str(t_id)).exists():
        return str(t_id)
    return gen_trxn_id()


class InsufficientBalance(IntegrityError):
    """Raised when a wallet has insufficient balance to
    run an operation.
    We're subclassing from :mod:`django.db.IntegrityError`
    so that it is automatically rolled-back during django's
    transaction lifecycle.
    """
