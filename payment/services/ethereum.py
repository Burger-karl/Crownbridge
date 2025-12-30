import requests
from decimal import Decimal
from django.conf import settings


def verify_eth_transfer(tx_hash, expected_to, expected_amount):
    url = "https://api.etherscan.io/api"

    params = {
        "module": "proxy",
        "action": "eth_getTransactionByHash",
        "txhash": tx_hash,
        "apikey": settings.ETHERSCAN_API_KEY,
    }

    tx = requests.get(url, params=params, timeout=10).json().get("result")
    if not tx:
        return None

    to_address = tx["to"].lower()
    value_wei = int(tx["value"], 16)

    eth_amount = Decimal(value_wei) / Decimal(10**18)

    if to_address != expected_to.lower():
        return None

    if eth_amount < Decimal(expected_amount):
        return None

    return {
        "from": tx["from"],
        "amount": eth_amount,
        "tx_hash": tx_hash,
        "confirmations": 1,  # updated later
    }


def verify_erc20_usdt(tx_hash, expected_to, expected_amount):
    url = "https://api.etherscan.io/api"

    params = {
        "module": "account",
        "action": "tokentx",
        "txhash": tx_hash,
        "apikey": settings.ETHERSCAN_API_KEY,
    }

    data = requests.get(url, params=params, timeout=10).json().get("result", [])

    for tx in data:
        if tx["contractAddress"].lower() != settings.USDT_ERC20_CONTRACT.lower():
            continue

        to_address = tx["to"].lower()
        amount = Decimal(tx["value"]) / Decimal(10**6)

        if to_address != expected_to.lower():
            continue

        if amount < Decimal(expected_amount):
            continue

        return {
            "from": tx["from"],
            "amount": amount,
            "tx_hash": tx_hash,
            "confirmations": int(tx["confirmations"]),
        }

    return None
