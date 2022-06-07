from django.conf import settings
from py_crypto_hd_wallet import HdWalletBipFactory, HdWalletSaver, HdWalletBip44Coins, HdWalletBipWordsNum, \
    HdWalletBipDataTypes

# Create a BIP-0044 Bitcoin wallet factory
# hd_wallet_fact = HdWalletBipFactory(HdWalletBip44Coins.BITCOIN)
# Create a BIP-0049 Litecoin wallet factory
from web3 import Web3


# mnemonic = settings.MNEMONIC


def wallet_generator(addr_num=1):
    hd_wallet_fact = HdWalletBipFactory(HdWalletBip44Coins.ETHEREUM)
    hd_wallet = hd_wallet_fact.CreateFromMnemonic("my_wallet_name", settings.MNEMONIC)
    hd_wallet.Generate(addr_num=addr_num)
    return hd_wallet


def gen_user_addr(user_id):
    hd_wallet = wallet_generator(user_id)
    addresses = hd_wallet.GetData(HdWalletBipDataTypes.ADDRESS)
    addr = addresses[user_id - 1]

    return addr


def get_eth_balance(addr):
    w3 = Web3(Web3.HTTPProvider(settings.WEB3_URL))
    return w3.fromWei(w3.eth.get_balance(addr), 'ether')


def get_token_balance(addr, coin):
    w3 = Web3(Web3.HTTPProvider(settings.WEB3_URL))

    contract = w3.eth.contract(coin.contract_address, abi=coin.abi)
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
        maxFeePerGas=base_fee_per_gas + 1,
        maxPriorityFeePerGas=1,
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
            print(log['data'])
            return decode_parameter_amount(bytes.fromhex(log['data'][2:]))[0]


def check_for_wallet_transaction(block):
    from wallet.models import Wallet, Transaction
    wallets = Wallet.objects.all()
    w3 = Web3(Web3.HTTPProvider(settings.WEB3_URL))

    # if block and block['transactions']:
    for tx_hash in block['transactions']:
        tx = w3.eth.get_transaction(w3.toHex(tx_hash))
        tx_data = w3.eth.get_transaction_receipt(w3.toHex(tx_hash))
        number_of_confirmations = w3.eth.blockNumber - tx.blockNumber

        # check if to address is contract
        if w3.eth.getCode(tx['to']) != "0x":
            to_address = get_token_receiver_address(tx_data['logs'])
            contract_address = tx['to']
        else:
            to_address = tx['to']

        # print(tx)
        # print(tx_data['logs'])

        # print(get_token_amount(tx_data['logs']))
        # for log in tx_data['logs']:
        #     print(log['data'])
        #     print(log['address'])
            # print(w3.eth.decode)
        to_wallet_qs = wallets.filter(erc20_address__iexact=to_address)
        if to_wallet_qs.exists():
            Transaction.objects.create(
                running_balance=to_wallet_qs.first().get_balance(),
                wallet=to_wallet_qs.first(),
                trx_hash=w3.toHex(tx_hash),
                transaction_type=Transaction.DEPOSIT
            )


def send_erc_20_token(contract_address, abi, from_wallet, to_addr, amount):
    w3 = Web3(Web3.HTTPProvider(settings.WEB3_URL))

    contract = w3.eth.contract(contract_address, abi=abi)

    nonce = w3.eth.get_transaction_count(from_wallet.erc20_address)

    base_fee_per_gas = w3.eth.get_block('latest')['baseFeePerGas']

    txn = contract.functions.transfer(to_addr, amount).build_transaction({
        'chainId': w3.eth.chain_id,
        'gas': 21000,
        'maxFeePergas': base_fee_per_gas + 1,
        'maxPriorityFeePerGas': 1,
        'nonce': nonce
    }) # .transact({'from': to_addr})
    signed_txn = w3.eth.account.sign_transaction(txn, private_key=from_wallet.get_private_key())
    w3.eth.send_raw_transaction(signed_txn.rawTransaction)

    return w3.toHex(signed_txn.hash)
