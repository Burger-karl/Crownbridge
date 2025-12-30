from web3 import Web3
from decimal import Decimal
from django.conf import settings


w3 = Web3(Web3.HTTPProvider(settings.ETH_RPC_URL))


def send_eth(to_address, amount):
    nonce = w3.eth.get_transaction_count(settings.ETH_PLATFORM_ADDRESS)

    tx = {
        "nonce": nonce,
        "to": Web3.to_checksum_address(to_address),
        "value": w3.to_wei(Decimal(amount), "ether"),
        "gas": 21000,
        "gasPrice": w3.eth.gas_price,
        "chainId": 1,
    }

    signed_tx = w3.eth.account.sign_transaction(
        tx, settings.ETH_PLATFORM_PRIVATE_KEY
    )

    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)

    return tx_hash.hex()



from web3 import Web3
from decimal import Decimal
from django.conf import settings

ERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"},
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    }
]

w3 = Web3(Web3.HTTPProvider(settings.ETH_RPC_URL))


def send_usdt_erc20(to_address, amount):
    contract = w3.eth.contract(
        address=Web3.to_checksum_address(settings.USDT_ERC20_CONTRACT),
        abi=ERC20_ABI,
    )

    nonce = w3.eth.get_transaction_count(settings.ETH_PLATFORM_ADDRESS)

    tx = contract.functions.transfer(
        Web3.to_checksum_address(to_address),
        int(Decimal(amount) * 10**6),
    ).build_transaction({
        "from": settings.ETH_PLATFORM_ADDRESS,
        "nonce": nonce,
        "gas": 100_000,
        "gasPrice": w3.eth.gas_price,
        "chainId": 1,
    })

    signed_tx = w3.eth.account.sign_transaction(
        tx, settings.ETH_PLATFORM_PRIVATE_KEY
    )

    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)

    return tx_hash.hex()
