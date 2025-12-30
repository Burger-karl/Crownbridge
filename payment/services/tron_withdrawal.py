from tronpy import Tron
from tronpy.keys import PrivateKey
from decimal import Decimal
from django.conf import settings


def send_trx(to_address, amount):
    client = Tron()

    pk = PrivateKey(bytes.fromhex(settings.TRON_PLATFORM_PRIVATE_KEY))
    txn = (
        client.trx.transfer(
            settings.TRON_PLATFORM_ADDRESS,
            to_address,
            int(Decimal(amount) * 1_000_000)
        )
        .build()
        .sign(pk)
        .broadcast()
    )

    return txn["txid"]


from tronpy import Tron
from tronpy.keys import PrivateKey
from decimal import Decimal
from django.conf import settings

USDT_DECIMALS = 6


def send_usdt_trc20(to_address, amount):
    client = Tron()

    pk = PrivateKey(bytes.fromhex(settings.TRON_PLATFORM_PRIVATE_KEY))
    contract = client.get_contract(settings.USDT_TRC20_CONTRACT)

    txn = (
        contract.functions.transfer(
            to_address,
            int(Decimal(amount) * 10**USDT_DECIMALS)
        )
        .with_owner(settings.TRON_PLATFORM_ADDRESS)
        .fee_limit(5_000_000)
        .build()
        .sign(pk)
        .broadcast()
    )

    return txn["txid"]
