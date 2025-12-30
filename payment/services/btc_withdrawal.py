import requests
from django.conf import settings


def send_btc_tatum(to_address, amount):
    url = "https://api.tatum.io/v3/bitcoin/transaction"

    payload = {
        "fromAddress": [{
            "address": settings.BTC_PLATFORM_ADDRESS,
            "privateKey": settings.BTC_PLATFORM_PRIVATE_KEY,
        }],
        "to": [{
            "address": to_address,
            "value": amount,
        }],
    }

    headers = {
        "x-api-key": settings.TATUM_API_KEY
    }

    r = requests.post(url, json=payload, headers=headers, timeout=20)
    r.raise_for_status()

    return r.json()["txId"]
