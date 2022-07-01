import json
import os
import sys
import traceback

import websocket
import _thread
import time
import rel
import django
from django.db.models import Q
from web3 import Web3


from wallet.utils import (check_for_ether_transactions, update_transaction_status, on_token_transaction)

sys.path.append(
    os.path.join(os.path.dirname(__file__), 'wallet_project')
)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wallet_project.settings")

django.setup()
from django.conf import settings
from wallet.models import Coin


w3 = Web3(Web3.HTTPProvider(settings.WEB3_URL))

prev_block = 0
prev_log_block = 0

contract_addresses = [address for address in Coin.objects.exclude(Q(contract_address__isnull=True) | Q(contract_address='')).values_list('contract_address', flat=True)]


def on_message(ws, message):
    global prev_block
    global prev_log_block

    message_dict = json.loads(message)

    try:
        b_number = message_dict['params']['result'].get('number')
        if b_number is not None:
            # New head
            block = w3.eth.get_block(b_number, full_transactions=True)

            check_for_ether_transactions(block, reorg=prev_block==block['number'])
            # check_for_token_transactions(block, reorg=prev_block==block['number'])
            update_transaction_status(block)
            prev_block = block['number']

        log_block_no = message_dict['params']['result'].get('blockNumber')
        if log_block_no is not None:
            # New log
            result = message_dict['params']['result']

            on_token_transaction(result, reorg=prev_log_block==int(log_block_no, 16))

            prev_log_block = int(log_block_no, 16)

    except KeyError as e:
        traceback.print_exc()


def on_error(ws, error):
    print(error)


def on_close(ws, close_status_code, close_msg):
    print("### closed ###")


def on_open(ws):
    print("Opened connection")
    ws.send(json.dumps({"id": 1, "method": "eth_subscribe", "params": ["newHeads"]}))
    ws.send(json.dumps({"id": 1, "method": "eth_subscribe", "params": ["logs", {"address": contract_addresses, "topics": ["0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"]}]}))
    # ws.send(json.dumps({"id": 1, "method": "eth_subscribe", "params": ["newPendingTransactions"]}))


if __name__ == "__main__":
    websocket.enableTrace(True)
    ws = websocket.WebSocketApp(settings.WEB3_WEBSOCKET_URL,
                              on_open=on_open,
                              on_message=on_message,
                              on_error=on_error,
                              on_close=on_close)

    ws.run_forever(dispatcher=rel)  # Set dispatcher to automatic reconnection
    rel.signal(2, rel.abort)  # Keyboard Interrupt
    rel.dispatch()
