import requests
from decimal import Decimal


BLOCKSTREAM_API = "https://blockstream.info/api"


def verify_btc_transaction(tx_hash, expected_to, expected_amount):
    # 1️⃣ Fetch TX
    tx_resp = requests.get(
        f"{BLOCKSTREAM_API}/tx/{tx_hash}",
        timeout=10
    )

    if tx_resp.status_code != 200:
        return None

    tx = tx_resp.json()

    # 2️⃣ Find matching output
    received_satoshis = 0

    for vout in tx["vout"]:
        addresses = vout["scriptpubkey_address"]
        value = Decimal(vout["value"]) / Decimal(1e8)

        if addresses == expected_to:
            received_satoshis += value

    if received_satoshis < Decimal(expected_amount):
        return None

    # 3️⃣ Confirmations
    status = tx["status"]
    confirmations = 0

    if status["confirmed"]:
        tip_height = requests.get(
            f"{BLOCKSTREAM_API}/blocks/tip/height",
            timeout=10
        ).text

        confirmations = int(tip_height) - status["block_height"] + 1

    return {
        "amount": received_satoshis,
        "confirmations": confirmations,
        "tx_hash": tx_hash,
    }
