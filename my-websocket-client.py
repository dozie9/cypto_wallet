import json
import os
import sys
import traceback

import websocket
import _thread
import time
import rel
import django
from web3 import Web3

from wallet.utils import check_for_ether_transactions, update_transaction_status, check_for_token_transactions

sys.path.append(
    os.path.join(os.path.dirname(__file__), 'wallet_project')
)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wallet_project.settings")

django.setup()
from django.conf import settings

w3 = Web3(Web3.HTTPProvider(settings.WEB3_URL))

prev_block = 0


def on_message(ws, message):
    global prev_block

    message_dict = json.loads(message)

    try:
        b_number = message_dict['params']['result']['number']
        block = w3.eth.get_block(b_number, full_transactions=True)

        check_for_ether_transactions(block, reorg=prev_block==block['number'])
        check_for_token_transactions(block, reorg=prev_block==block['number'])
        update_transaction_status(block)

        prev_block = block['number']
    except KeyError as e:
        traceback.print_exc()


def on_error(ws, error):
    print(error)


def on_close(ws, close_status_code, close_msg):
    print("### closed ###")


def on_open(ws):
    print("Opened connection")
    ws.send(json.dumps({"id": 1, "method": "eth_subscribe", "params": ["newHeads"]}))
    # ws.send(json.dumps({"id": 1, "method": "eth_subscribe", "params": ["newPendingTransactions"]}))


if __name__ == "__main__":
    websocket.enableTrace(False)
    ws = websocket.WebSocketApp(settings.WEB3_WEBSOCKET_URL,
                              on_open=on_open,
                              on_message=on_message,
                              on_error=on_error,
                              on_close=on_close)

    ws.run_forever(dispatcher=rel)  # Set dispatcher to automatic reconnection
    rel.signal(2, rel.abort)  # Keyboard Interrupt
    rel.dispatch()
