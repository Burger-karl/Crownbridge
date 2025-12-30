# import requests
# from decimal import Decimal
# from django.conf import settings

# TRONGRID_API = "https://api.trongrid.io"

# def verify_tron_transaction(tx_hash, expected_to, expected_amount=None, token_contract=None):
#     url = f"{TRONGRID_API}/v1/transactions/{tx_hash}"
#     r = requests.get(url, headers={
#         "TRON-PRO-API-KEY": settings.TRONGRID_API_KEY
#     })
#     data = r.json()

#     if not data.get("data"):
#         return None

#     tx = data["data"][0]

#     if tx["ret"][0]["contractRet"] != "SUCCESS":
#         return None

#     # parse transfer contract
#     contract = tx["raw_data"]["contract"][0]
#     value = contract["parameter"]["value"]

#     to_address = value.get("to_address")
#     amount = Decimal(value.get("amount", 0)) / Decimal(1_000_000)

#     if expected_amount and amount < expected_amount:
#         return None

#     return {
#         "from": value.get("owner_address"),
#         "to": to_address,
#         "amount": amount,
#         "confirmations": tx.get("confirmations", 0),
#     }



import requests
from decimal import Decimal
from django.conf import settings

TRONGRID_BASE = "https://api.trongrid.io"


def verify_tron_transaction(tx_hash, expected_to, expected_amount):
    """
    Verifies a TRON / USDT(TRC20) transaction on-chain.
    Returns dict if confirmed, otherwise None.
    """

    headers = {
        "TRON-PRO-API-KEY": settings.TRONGRID_API_KEY
    }

    # 1️⃣ Get transaction info
    tx_resp = requests.get(
        f"{TRONGRID_BASE}/v1/transactions/{tx_hash}",
        headers=headers,
        timeout=10
    )

    if tx_resp.status_code != 200:
        return None

    data = tx_resp.json().get("data", [])
    if not data:
        return None

    tx = data[0]

    # 2️⃣ Ensure transaction succeeded
    if tx.get("ret", [{}])[0].get("contractRet") != "SUCCESS":
        return None

    raw = tx.get("raw_data", {})
    contract = raw.get("contract", [])[0]
    value = contract.get("parameter", {}).get("value", {})

    to_address = value.get("to_address")
    owner_address = value.get("owner_address")
    amount_sun = value.get("amount")  # TRX in SUN

    # 3️⃣ Validate receiver
    if to_address != expected_to:
        return None

    # 4️⃣ Validate amount
    trx_amount = Decimal(amount_sun) / Decimal(1_000_000)
    if trx_amount < Decimal(expected_amount):
        return None

    # 5️⃣ Confirmations
    block_number = tx.get("blockNumber")
    latest_block = requests.get(
        f"{TRONGRID_BASE}/wallet/getnowblock",
        headers=headers
    ).json()["block_header"]["raw_data"]["number"]

    confirmations = latest_block - block_number

    return {
        "from": owner_address,
        "amount": trx_amount,
        "confirmations": confirmations,
        "tx_hash": tx_hash,
    }



import requests
from decimal import Decimal
from django.conf import settings

TRONGRID_BASE = "https://api.trongrid.io"


def verify_trc20_usdt(tx_hash, expected_to, expected_amount):
    headers = {
        "TRON-PRO-API-KEY": settings.TRONGRID_API_KEY
    }

    # 1️⃣ Fetch TRC20 events
    resp = requests.get(
        f"{TRONGRID_BASE}/v1/transactions/{tx_hash}/events",
        headers=headers,
        timeout=10
    )

    if resp.status_code != 200:
        return None

    events = resp.json().get("data", [])

    for event in events:
        if (
            event.get("contract_address") == settings.USDT_TRC20_CONTRACT
            and event.get("event_name") == "Transfer"
        ):
            to_address = event["result"]["to"]
            from_address = event["result"]["from"]
            amount = Decimal(event["result"]["value"]) / Decimal(1_000_000)

            if to_address != expected_to:
                continue

            if amount < Decimal(expected_amount):
                continue

            confirmations = event.get("block_number", 0)

            return {
                "from": from_address,
                "amount": amount,
                "confirmations": confirmations,
                "tx_hash": tx_hash,
            }

    return None
