import json
import os
import sys

import websocket
import _thread
import time
import rel
import django
from web3 import Web3

from wallet.utils import check_for_wallet_transaction, update_transaction_status

sys.path.append(
    os.path.join(os.path.dirname(__file__), 'wallet_project')
)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wallet_project.settings")

django.setup()
from django.conf import settings
from wallet.models import Wallet

w3 = Web3(Web3.HTTPProvider(settings.WEB3_URL))


def on_message(ws, message):
    message_dict = json.loads(message)
    # print(message_dict)
    try:
        new_head_hash = message_dict['params']['result']['hash']
        block = w3.eth.get_block(new_head_hash)
        # print(block)
        check_for_wallet_transaction(block)
        update_transaction_status(block)
    except KeyError as e:
        print(e)
    # print(message_dict)


def on_error(ws, error):
    print(error)


def on_close(ws, close_status_code, close_msg):
    print("### closed ###")


def on_open(ws):
    print("Opened connection")
    ws.send(json.dumps({"id": 1, "method": "eth_subscribe", "params": ["newHeads"]}))


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
